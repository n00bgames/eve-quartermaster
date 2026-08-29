use std::cmp::Ordering;
use std::collections::{BTreeMap, HashMap};

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};

pub const INPUT_SCHEMA: &str = "eqm.analytics-summary-input.v1";
pub const OUTPUT_SCHEMA: &str = "eqm.analytics-summary-output.v1";

#[derive(Debug, Clone, Deserialize)]
pub struct AnalyticsSummaryInput {
    pub schema_version: String,
    pub cutoff: DateTime<Utc>,
    #[serde(default)]
    pub character_rows: Vec<CharacterRow>,
    #[serde(default)]
    pub identified_character_rows: Vec<CharacterRow>,
    #[serde(default)]
    pub character_category_rows: Vec<CharacterCategoryRow>,
    #[serde(default)]
    pub corporation_rows: Vec<CorporationRow>,
    #[serde(default)]
    pub standing_rows: Vec<StandingRow>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CharacterRow {
    pub id: i64,
    pub character_id: i64,
    pub character_name: String,
    pub total_skill_points: f64,
    pub recorded_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CharacterCategoryRow {
    pub id: i64,
    pub character_id: i64,
    pub category_name: Option<String>,
    pub category_skill_points: f64,
    pub recorded_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CorporationRow {
    pub id: i64,
    pub corporation_id: i64,
    pub corporation_name: String,
    pub wallet_balance: f64,
    pub member_count: f64,
    pub blueprint_count: f64,
    pub recorded_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct StandingRow {
    pub id: i64,
    pub series_key: String,
    pub recorded_at: DateTime<Utc>,
    pub metric_value: f64,
    pub source_type: String,
    pub source_eve_id: i64,
    pub source_name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AnalyticsSummaryOutput {
    pub schema_version: String,
    pub cards: AnalyticsCards,
    pub change_composition: ChangeComposition,
    pub top_sp_gainers: Vec<GrowthRow>,
    pub top_sp_losses: Vec<GrowthRow>,
    pub top_skill_category_gainers: Vec<NamedDelta>,
    pub top_skill_category_losses: Vec<NamedDelta>,
    pub wallet_growth: Vec<GrowthRow>,
    pub member_growth: Vec<GrowthRow>,
    pub blueprint_growth: Vec<GrowthRow>,
    pub standings_movement: StandingMovement,
    pub series: CorporationSeries,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AnalyticsCards {
    pub wallet_total: f64,
    pub blueprint_total: f64,
    pub member_total: f64,
    pub character_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ChangeComposition {
    pub skill_points: ChangeBreakdown,
    pub corporation_wallets: ChangeBreakdown,
    pub members: ChangeBreakdown,
    pub blueprints: ChangeBreakdown,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ChangeBreakdown {
    pub current: f64,
    pub total_delta: f64,
    pub organic_delta: f64,
    pub coverage_delta: f64,
    pub newly_tracked_count: usize,
    pub newly_tracked: Vec<NewlyTracked>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct NewlyTracked {
    pub id: i64,
    pub name: String,
    pub value: f64,
    pub first_observed_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GrowthRow {
    pub id: i64,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<f64>,
    pub delta: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct NamedDelta {
    pub name: String,
    pub delta: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CorporationSeries {
    pub wallet_totals: Vec<SeriesPoint>,
    pub member_counts: Vec<SeriesPoint>,
    pub blueprint_counts: Vec<SeriesPoint>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SeriesPoint {
    pub date: String,
    pub corporation_id: i64,
    pub corporation_name: String,
    pub value: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct StandingMovement {
    pub basis: String,
    pub corporations: MovementGroup,
    pub factions: MovementGroup,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MovementGroup {
    pub gains: Vec<StandingDelta>,
    pub losses: Vec<StandingDelta>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct StandingDelta {
    pub id: i64,
    pub name: String,
    pub delta: f64,
}

fn numeric_desc(left: f64, right: f64) -> Ordering {
    right.partial_cmp(&left).unwrap_or(Ordering::Equal)
}

fn sorted_character_groups(rows: &[CharacterRow]) -> BTreeMap<i64, Vec<&CharacterRow>> {
    let mut grouped: BTreeMap<i64, Vec<&CharacterRow>> = BTreeMap::new();
    for row in rows {
        grouped.entry(row.character_id).or_default().push(row);
    }
    for history in grouped.values_mut() {
        history.sort_by_key(|row| (row.recorded_at, row.id));
    }
    grouped
}

fn sorted_corporation_groups(rows: &[CorporationRow]) -> BTreeMap<i64, Vec<&CorporationRow>> {
    let mut grouped: BTreeMap<i64, Vec<&CorporationRow>> = BTreeMap::new();
    for row in rows {
        grouped.entry(row.corporation_id).or_default().push(row);
    }
    for history in grouped.values_mut() {
        history.sort_by_key(|row| (row.recorded_at, row.id));
    }
    grouped
}

fn character_change_breakdown(rows: &[CharacterRow], cutoff: DateTime<Utc>) -> ChangeBreakdown {
    let grouped = sorted_character_groups(rows);
    change_breakdown(
        grouped.into_iter().map(|(id, history)| {
            let first = history[0];
            let latest = history[history.len() - 1];
            (
                id,
                latest.character_name.clone(),
                first.total_skill_points,
                latest.total_skill_points,
                first.recorded_at,
                history.len(),
            )
        }),
        cutoff,
    )
}

fn corporation_change_breakdown(
    rows: &[CorporationRow],
    cutoff: DateTime<Utc>,
    value: fn(&CorporationRow) -> f64,
) -> ChangeBreakdown {
    let grouped = sorted_corporation_groups(rows);
    change_breakdown(
        grouped.into_iter().map(|(id, history)| {
            let first = history[0];
            let latest = history[history.len() - 1];
            (
                id,
                latest.corporation_name.clone(),
                value(first),
                value(latest),
                first.recorded_at,
                history.len(),
            )
        }),
        cutoff,
    )
}

fn change_breakdown<I>(history: I, cutoff: DateTime<Utc>) -> ChangeBreakdown
where
    I: Iterator<Item = (i64, String, f64, f64, DateTime<Utc>, usize)>,
{
    let mut current = 0.0;
    let mut organic_delta = 0.0;
    let mut coverage_delta = 0.0;
    let mut newly_tracked = Vec::new();
    for (id, name, first_value, latest_value, first_at, count) in history {
        current += latest_value;
        if first_at >= cutoff {
            coverage_delta += first_value;
            newly_tracked.push(NewlyTracked {
                id,
                name,
                value: first_value,
                first_observed_at: first_at.to_rfc3339(),
            });
        }
        if count > 1 {
            organic_delta += latest_value - first_value;
        }
    }
    newly_tracked.sort_by(|left, right| numeric_desc(left.value, right.value));
    let newly_tracked_count = newly_tracked.len();
    newly_tracked.truncate(12);
    ChangeBreakdown {
        current,
        total_delta: organic_delta + coverage_delta,
        organic_delta,
        coverage_delta,
        newly_tracked_count,
        newly_tracked,
    }
}

fn character_growth(rows: &[CharacterRow]) -> Vec<GrowthRow> {
    let mut result = Vec::new();
    for (id, history) in sorted_character_groups(rows) {
        if history.len() < 2 {
            continue;
        }
        let first = history[0];
        let latest = history[history.len() - 1];
        result.push(GrowthRow {
            id,
            name: latest.character_name.clone(),
            value: Some(latest.total_skill_points),
            delta: latest.total_skill_points - first.total_skill_points,
        });
    }
    result.sort_by(|left, right| numeric_desc(left.delta, right.delta));
    result.truncate(12);
    result
}

fn corporation_growth(
    rows: &[CorporationRow],
    value: fn(&CorporationRow) -> f64,
) -> Vec<GrowthRow> {
    let mut result = Vec::new();
    for (id, history) in sorted_corporation_groups(rows) {
        if history.len() < 2 {
            continue;
        }
        let first = history[0];
        let latest = history[history.len() - 1];
        result.push(GrowthRow {
            id,
            name: latest.corporation_name.clone(),
            value: Some(value(latest)),
            delta: value(latest) - value(first),
        });
    }
    result.sort_by(|left, right| numeric_desc(left.delta, right.delta));
    result.truncate(12);
    result
}

fn skill_point_losses(rows: &[CharacterRow]) -> Vec<GrowthRow> {
    let mut result = Vec::new();
    for (id, history) in sorted_character_groups(rows) {
        let mut loss = 0.0;
        for pair in history.windows(2) {
            if pair[1].total_skill_points < pair[0].total_skill_points {
                loss += pair[0].total_skill_points - pair[1].total_skill_points;
            }
        }
        if loss > 0.0 {
            result.push(GrowthRow {
                id,
                name: history.last().unwrap().character_name.clone(),
                value: None,
                delta: loss,
            });
        }
    }
    result.sort_by(|left, right| numeric_desc(left.delta, right.delta));
    result.truncate(12);
    result
}

fn category_analytics(rows: &[CharacterCategoryRow]) -> (Vec<NamedDelta>, Vec<NamedDelta>) {
    let mut grouped: BTreeMap<(i64, String), Vec<&CharacterCategoryRow>> = BTreeMap::new();
    for row in rows {
        grouped
            .entry((
                row.character_id,
                row.category_name
                    .clone()
                    .unwrap_or_else(|| "Uncategorized".to_string()),
            ))
            .or_default()
            .push(row);
    }
    let mut gains: BTreeMap<String, f64> = BTreeMap::new();
    let mut losses: BTreeMap<String, f64> = BTreeMap::new();
    for ((_character_id, raw_category), mut history) in grouped {
        history.sort_by_key(|row| (row.recorded_at, row.id));
        if history.len() < 2 {
            continue;
        }
        let display = if raw_category == "Skill" {
            "All skill groups (legacy)".to_string()
        } else {
            raw_category
        };
        let first = history[0].category_skill_points;
        let latest = history[history.len() - 1].category_skill_points;
        *gains.entry(display.clone()).or_default() += latest - first;
        for pair in history.windows(2) {
            if pair[1].category_skill_points < pair[0].category_skill_points {
                *losses.entry(display.clone()).or_default() +=
                    pair[0].category_skill_points - pair[1].category_skill_points;
            }
        }
    }
    let mut gain_rows: Vec<_> = gains
        .into_iter()
        .map(|(name, delta)| NamedDelta { name, delta })
        .collect();
    gain_rows.sort_by(|left, right| numeric_desc(left.delta, right.delta));
    gain_rows.truncate(12);
    let mut loss_rows: Vec<_> = losses
        .into_iter()
        .filter(|(_, delta)| *delta > 0.0)
        .map(|(name, delta)| NamedDelta { name, delta })
        .collect();
    loss_rows.sort_by(|left, right| numeric_desc(left.delta, right.delta));
    loss_rows.truncate(12);
    (gain_rows, loss_rows)
}

fn daily_series(
    rows: &[CorporationRow],
    cutoff: DateTime<Utc>,
    value: fn(&CorporationRow) -> f64,
) -> Vec<SeriesPoint> {
    let mut latest: HashMap<(i64, NaiveDate), &CorporationRow> = HashMap::new();
    for row in rows {
        let effective = if row.recorded_at < cutoff {
            cutoff
        } else {
            row.recorded_at
        };
        let key = (row.corporation_id, effective.date_naive());
        match latest.get(&key) {
            Some(previous) if previous.recorded_at >= row.recorded_at => {}
            _ => {
                latest.insert(key, row);
            }
        }
    }
    let mut result: Vec<_> = latest
        .into_iter()
        .map(|((corporation_id, day), row)| SeriesPoint {
            date: day.to_string(),
            corporation_id,
            corporation_name: row.corporation_name.clone(),
            value: value(row),
        })
        .collect();
    result.sort_by(|left, right| {
        left.date
            .cmp(&right.date)
            .then_with(|| left.corporation_name.cmp(&right.corporation_name))
            .then_with(|| left.corporation_id.cmp(&right.corporation_id))
    });
    result
}

fn standing_movement(rows: &[StandingRow], cutoff: DateTime<Utc>) -> StandingMovement {
    let mut by_series: BTreeMap<&str, Vec<&StandingRow>> = BTreeMap::new();
    for row in rows {
        by_series.entry(&row.series_key).or_default().push(row);
    }
    let mut movement: BTreeMap<(String, i64), StandingDelta> = BTreeMap::new();
    for mut history in by_series.into_values() {
        history.sort_by_key(|row| (row.recorded_at, row.id));
        let baseline = history[0];
        if baseline.recorded_at >= cutoff {
            continue;
        }
        let latest = history[history.len() - 1];
        let source_type = if latest.source_type.is_empty() {
            &baseline.source_type
        } else {
            &latest.source_type
        };
        let source_eve_id = if latest.source_eve_id > 0 {
            latest.source_eve_id
        } else {
            baseline.source_eve_id
        };
        if latest.id == baseline.id
            || !matches!(source_type.as_str(), "npc_corp" | "faction")
            || source_eve_id <= 0
        {
            continue;
        }
        let source_name = if !latest.source_name.is_empty() {
            latest.source_name.clone()
        } else if !baseline.source_name.is_empty() {
            baseline.source_name.clone()
        } else {
            format!("{} {}", source_type.replace('_', " "), source_eve_id)
        };
        let key = (source_type.clone(), source_eve_id);
        let item = movement.entry(key).or_insert_with(|| StandingDelta {
            id: source_eve_id,
            name: source_name.clone(),
            delta: 0.0,
        });
        item.name = source_name;
        item.delta = ((item.delta + latest.metric_value - baseline.metric_value) * 10_000.0)
            .round()
            / 10_000.0;
    }
    let ranked = |source_type: &str, loss: bool| {
        let mut values: Vec<_> = movement
            .iter()
            .filter(|((kind, _), item)| {
                kind == source_type
                    && if loss {
                        item.delta < 0.0
                    } else {
                        item.delta > 0.0
                    }
            })
            .map(|(_, item)| StandingDelta {
                id: item.id,
                name: item.name.clone(),
                delta: if loss { item.delta.abs() } else { item.delta },
            })
            .collect();
        values.sort_by(|left, right| {
            numeric_desc(left.delta, right.delta).then_with(|| left.name.cmp(&right.name))
        });
        values.truncate(10);
        values
    };
    StandingMovement {
        basis: "base".to_string(),
        corporations: MovementGroup {
            gains: ranked("npc_corp", false),
            losses: ranked("npc_corp", true),
        },
        factions: MovementGroup {
            gains: ranked("faction", false),
            losses: ranked("faction", true),
        },
    }
}

pub fn evaluate_analytics_summary(
    input: AnalyticsSummaryInput,
) -> Result<AnalyticsSummaryOutput, String> {
    if input.schema_version != INPUT_SCHEMA {
        return Err(format!(
            "unsupported analytics summary schema: {}",
            input.schema_version
        ));
    }
    let character_groups = sorted_character_groups(&input.character_rows);
    let corporation_groups = sorted_corporation_groups(&input.corporation_rows);
    let cards = AnalyticsCards {
        wallet_total: corporation_groups
            .values()
            .map(|rows| rows.last().unwrap().wallet_balance)
            .sum(),
        blueprint_total: corporation_groups
            .values()
            .map(|rows| rows.last().unwrap().blueprint_count)
            .sum(),
        member_total: corporation_groups
            .values()
            .map(|rows| rows.last().unwrap().member_count)
            .sum(),
        character_count: character_groups.len(),
    };
    let (category_gainers, category_losses) = category_analytics(&input.character_category_rows);
    Ok(AnalyticsSummaryOutput {
        schema_version: OUTPUT_SCHEMA.to_string(),
        cards,
        change_composition: ChangeComposition {
            skill_points: character_change_breakdown(&input.character_rows, input.cutoff),
            corporation_wallets: corporation_change_breakdown(
                &input.corporation_rows,
                input.cutoff,
                |row| row.wallet_balance,
            ),
            members: corporation_change_breakdown(&input.corporation_rows, input.cutoff, |row| {
                row.member_count
            }),
            blueprints: corporation_change_breakdown(
                &input.corporation_rows,
                input.cutoff,
                |row| row.blueprint_count,
            ),
        },
        top_sp_gainers: character_growth(&input.identified_character_rows),
        top_sp_losses: skill_point_losses(&input.identified_character_rows),
        top_skill_category_gainers: category_gainers,
        top_skill_category_losses: category_losses,
        wallet_growth: corporation_growth(&input.corporation_rows, |row| row.wallet_balance),
        member_growth: corporation_growth(&input.corporation_rows, |row| row.member_count),
        blueprint_growth: corporation_growth(&input.corporation_rows, |row| row.blueprint_count),
        standings_movement: standing_movement(&input.standing_rows, input.cutoff),
        series: CorporationSeries {
            wallet_totals: daily_series(&input.corporation_rows, input.cutoff, |row| {
                row.wallet_balance
            }),
            member_counts: daily_series(&input.corporation_rows, input.cutoff, |row| {
                row.member_count
            }),
            blueprint_counts: daily_series(&input.corporation_rows, input.cutoff, |row| {
                row.blueprint_count
            }),
        },
    })
}
