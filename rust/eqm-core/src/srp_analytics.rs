use std::collections::{BTreeMap, HashMap};

use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const INPUT_SCHEMA: &str = "eqm.srp-analytics-input.v1";
pub const OUTPUT_SCHEMA: &str = "eqm.srp-analytics-output.v1";
const BREAKDOWN_SECTIONS: [&str; 12] = [
    "doctrines",
    "fits",
    "ship_types",
    "ship_groups",
    "characters",
    "operations",
    "corporations",
    "alliances",
    "systems",
    "regions",
    "statuses",
    "security_classes",
];

#[derive(Debug, Clone, Deserialize)]
pub struct SrpAnalyticsInput {
    pub schema_version: String,
    pub calendar_days: i64,
    pub active_loss_days: i64,
    pub granularity: String,
    #[serde(default)]
    pub rows: Vec<SrpAnalyticsRowInput>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SrpAnalyticsRowInput {
    pub request_id: i64,
    pub bucket: String,
    pub authoritative_loss_cents: Option<i64>,
    pub requested_cents: Option<i64>,
    pub approved_cents: Option<i64>,
    pub paid_cents: Option<i64>,
    pub status: String,
    pub data_source: String,
    #[serde(default)]
    pub dimensions: BTreeMap<String, SrpDimensionInput>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SrpDimensionInput {
    pub id: Value,
    pub label: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SrpSummaryOutput {
    pub loss_count: i64,
    pub valued_loss_count: i64,
    pub total_isk_lost_cents: i64,
    pub average_isk_per_loss_cents: Option<i64>,
    pub average_isk_per_calendar_day_cents: Option<i64>,
    pub average_isk_per_active_loss_day_cents: Option<i64>,
    pub calendar_days: i64,
    pub active_loss_days: i64,
    pub requested_reimbursement_cents: i64,
    pub approved_reimbursement_cents: i64,
    pub rejected_reimbursement_cents: i64,
    pub paid_reimbursement_cents: i64,
    pub loss_less_approved_cents: i64,
    pub loss_less_paid_cents: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SrpSeriesOutput {
    pub bucket: String,
    pub loss_count: i64,
    pub valued_count: i64,
    pub total_isk_cents: i64,
    pub request_ids: Vec<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SrpBreakdownOutput {
    pub id: Value,
    pub label: String,
    pub loss_count: i64,
    pub valued_count: i64,
    pub total_isk_cents: i64,
    pub average_isk_cents: Option<i64>,
    pub request_ids: Vec<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SrpTopOutput {
    pub doctrines_by_isk: Vec<SrpBreakdownOutput>,
    pub doctrines_by_losses: Vec<SrpBreakdownOutput>,
    pub ships_by_losses: Vec<SrpBreakdownOutput>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SrpQualityOutput {
    pub unvalued_count: i64,
    pub unvalued_percentage_units: i64,
    pub missing_doctrine_count: i64,
    pub missing_ship_type_count: i64,
    pub manual_count: i64,
    pub imported_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SrpAnalyticsOutput {
    pub schema_version: String,
    pub summary: SrpSummaryOutput,
    pub time_series: Vec<SrpSeriesOutput>,
    pub granularity: String,
    pub breakdowns: BTreeMap<String, Vec<SrpBreakdownOutput>>,
    pub top: SrpTopOutput,
    pub quality: SrpQualityOutput,
}

#[derive(Debug, Clone)]
struct BreakdownAccumulator {
    id: Value,
    label: String,
    loss_count: i64,
    valued_count: i64,
    total_isk_cents: i64,
    request_ids: Vec<i64>,
}

#[derive(Debug, Default)]
struct SeriesAccumulator {
    loss_count: i64,
    valued_count: i64,
    total_isk_cents: i64,
    request_ids: Vec<i64>,
}

fn round_half_even(numerator: i128, denominator: i128) -> i64 {
    let quotient = numerator / denominator;
    let remainder = numerator % denominator;
    let doubled = remainder.abs() * 2;
    let adjustment = if doubled > denominator.abs()
        || (doubled == denominator.abs() && quotient.abs() % 2 == 1)
    {
        numerator.signum() * denominator.signum()
    } else {
        0
    };
    (quotient + adjustment) as i64
}

fn average_cents(total: i64, count: i64) -> Option<i64> {
    (count > 0).then(|| round_half_even(i128::from(total), i128::from(count)))
}

fn dimension_key(dimension: &SrpDimensionInput) -> Result<String, String> {
    Ok(format!(
        "{}\u{1f}{}",
        serde_json::to_string(&dimension.id).map_err(|error| error.to_string())?,
        dimension.label
    ))
}

fn sort_breakdowns(rows: &mut [SrpBreakdownOutput]) {
    rows.sort_by(|left, right| {
        right
            .total_isk_cents
            .cmp(&left.total_isk_cents)
            .then_with(|| right.loss_count.cmp(&left.loss_count))
            .then_with(|| left.label.cmp(&right.label))
    });
}

pub fn evaluate_srp_analytics(input: SrpAnalyticsInput) -> Result<SrpAnalyticsOutput, String> {
    if input.schema_version != INPUT_SCHEMA {
        return Err(format!(
            "unsupported SRP analytics schema: {}",
            input.schema_version
        ));
    }
    if input.calendar_days < 0 || input.active_loss_days < 0 {
        return Err("SRP day counts cannot be negative".to_string());
    }
    if !matches!(input.granularity.as_str(), "day" | "week" | "month") {
        return Err("SRP granularity must be day, week, or month".to_string());
    }

    let mut total_isk_lost_cents = 0_i64;
    let mut valued_loss_count = 0_i64;
    let mut requested_cents = 0_i64;
    let mut approved_cents = 0_i64;
    let mut rejected_cents = 0_i64;
    let mut paid_cents = 0_i64;
    let mut manual_count = 0_i64;
    let mut series: BTreeMap<String, SeriesAccumulator> = BTreeMap::new();
    let mut group_positions: BTreeMap<String, HashMap<String, usize>> = BTreeMap::new();
    let mut group_rows: BTreeMap<String, Vec<BreakdownAccumulator>> = BTreeMap::new();
    for section in BREAKDOWN_SECTIONS {
        group_positions.insert(section.to_string(), HashMap::new());
        group_rows.insert(section.to_string(), Vec::new());
    }

    for row in &input.rows {
        if [
            row.authoritative_loss_cents,
            row.requested_cents,
            row.approved_cents,
            row.paid_cents,
        ]
        .into_iter()
        .flatten()
        .any(|value| value < 0)
        {
            return Err("SRP monetary values cannot be negative".to_string());
        }
        if let Some(value) = row.authoritative_loss_cents {
            total_isk_lost_cents += value;
            valued_loss_count += 1;
        }
        requested_cents += row.requested_cents.unwrap_or(0);
        approved_cents += row.approved_cents.unwrap_or(0);
        paid_cents += row.paid_cents.unwrap_or(0);
        if row.status == "rejected" {
            rejected_cents += row.requested_cents.unwrap_or(0);
        }
        manual_count += i64::from(row.data_source == "manual");

        let bucket = series.entry(row.bucket.clone()).or_default();
        bucket.loss_count += 1;
        bucket.request_ids.push(row.request_id);
        if let Some(value) = row.authoritative_loss_cents {
            bucket.valued_count += 1;
            bucket.total_isk_cents += value;
        }

        for (section, dimension) in &row.dimensions {
            let key = dimension_key(dimension)?;
            let positions = group_positions.entry(section.clone()).or_default();
            let groups = group_rows.entry(section.clone()).or_default();
            let position = if let Some(position) = positions.get(&key).copied() {
                position
            } else {
                let position = groups.len();
                positions.insert(key, position);
                groups.push(BreakdownAccumulator {
                    id: dimension.id.clone(),
                    label: dimension.label.clone(),
                    loss_count: 0,
                    valued_count: 0,
                    total_isk_cents: 0,
                    request_ids: Vec::new(),
                });
                position
            };
            let group = &mut groups[position];
            group.loss_count += 1;
            group.request_ids.push(row.request_id);
            if let Some(value) = row.authoritative_loss_cents {
                group.valued_count += 1;
                group.total_isk_cents += value;
            }
        }
    }

    let mut breakdowns = BTreeMap::new();
    for (section, groups) in group_rows {
        let mut output = groups
            .into_iter()
            .map(|group| SrpBreakdownOutput {
                id: group.id,
                label: group.label,
                loss_count: group.loss_count,
                valued_count: group.valued_count,
                total_isk_cents: group.total_isk_cents,
                average_isk_cents: average_cents(group.total_isk_cents, group.valued_count),
                request_ids: group.request_ids,
            })
            .collect::<Vec<_>>();
        sort_breakdowns(&mut output);
        breakdowns.insert(section, output);
    }
    let doctrines = breakdowns.get("doctrines").cloned().unwrap_or_default();
    let ships = breakdowns.get("ship_types").cloned().unwrap_or_default();
    let mut doctrines_by_losses = doctrines.clone();
    doctrines_by_losses.sort_by(|left, right| {
        right
            .loss_count
            .cmp(&left.loss_count)
            .then_with(|| left.label.cmp(&right.label))
    });
    let mut ships_by_losses = ships;
    ships_by_losses.sort_by(|left, right| {
        right
            .loss_count
            .cmp(&left.loss_count)
            .then_with(|| left.label.cmp(&right.label))
    });

    let loss_count = input.rows.len() as i64;
    let unvalued_count = loss_count - valued_loss_count;
    Ok(SrpAnalyticsOutput {
        schema_version: OUTPUT_SCHEMA.to_string(),
        summary: SrpSummaryOutput {
            loss_count,
            valued_loss_count,
            total_isk_lost_cents,
            average_isk_per_loss_cents: average_cents(total_isk_lost_cents, loss_count),
            average_isk_per_calendar_day_cents: average_cents(
                total_isk_lost_cents,
                input.calendar_days,
            ),
            average_isk_per_active_loss_day_cents: average_cents(
                total_isk_lost_cents,
                input.active_loss_days,
            ),
            calendar_days: input.calendar_days,
            active_loss_days: input.active_loss_days,
            requested_reimbursement_cents: requested_cents,
            approved_reimbursement_cents: approved_cents,
            rejected_reimbursement_cents: rejected_cents,
            paid_reimbursement_cents: paid_cents,
            loss_less_approved_cents: total_isk_lost_cents - approved_cents,
            loss_less_paid_cents: total_isk_lost_cents - paid_cents,
        },
        time_series: series
            .into_iter()
            .map(|(bucket, row)| SrpSeriesOutput {
                bucket,
                loss_count: row.loss_count,
                valued_count: row.valued_count,
                total_isk_cents: row.total_isk_cents,
                request_ids: row.request_ids,
            })
            .collect(),
        granularity: input.granularity,
        breakdowns,
        top: SrpTopOutput {
            doctrines_by_isk: doctrines.into_iter().take(10).collect(),
            doctrines_by_losses: doctrines_by_losses.into_iter().take(10).collect(),
            ships_by_losses: ships_by_losses.into_iter().take(10).collect(),
        },
        quality: SrpQualityOutput {
            unvalued_count,
            unvalued_percentage_units: if loss_count > 0 {
                round_half_even(i128::from(unvalued_count) * 10_000, i128::from(loss_count))
            } else {
                0
            },
            missing_doctrine_count: input
                .rows
                .iter()
                .filter(|row| {
                    row.dimensions
                        .get("doctrines")
                        .is_some_and(|value| value.id.is_null())
                })
                .count() as i64,
            missing_ship_type_count: input
                .rows
                .iter()
                .filter(|row| {
                    row.dimensions
                        .get("ship_types")
                        .is_some_and(|value| value.id.is_null())
                })
                .count() as i64,
            manual_count,
            imported_count: loss_count - manual_count,
        },
    })
}
