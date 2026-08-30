use std::collections::{BTreeMap, HashMap};

use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

const SCHEMA: &str = "eqm.financial-analytics.v1";

#[derive(Debug, Deserialize)]
pub struct FinancialAnalyticsInput {
    pub schema_version: String,
    pub operation: String,
    #[serde(default)]
    pub personal: Option<PersonalInput>,
    #[serde(default)]
    pub corporation: Option<CorporationInput>,
}

#[derive(Debug, Deserialize)]
pub struct SnapshotRow {
    pub id: i64,
    #[serde(default)]
    pub group_id: Option<i64>,
    pub recorded_at: String,
    pub balance: f64,
}

#[derive(Debug, Deserialize)]
pub struct JournalRow {
    pub id: i64,
    pub occurred_at: String,
    pub amount: f64,
    pub timeline: Value,
}

#[derive(Debug, Deserialize)]
pub struct PersonalInput {
    pub start_date: String,
    pub cutoff: String,
    pub now: String,
    #[serde(default)]
    pub current_balance: Option<f64>,
    #[serde(default)]
    pub snapshots: Vec<SnapshotRow>,
    #[serde(default)]
    pub journal: Vec<JournalRow>,
}

#[derive(Debug, Deserialize)]
pub struct CorporationInput {
    pub start_date: String,
    pub raw_visible: bool,
    #[serde(default)]
    pub character_snapshots: Vec<SnapshotRow>,
    #[serde(default)]
    pub division_snapshots: Vec<SnapshotRow>,
    #[serde(default)]
    pub current_character_balances: Vec<f64>,
    #[serde(default)]
    pub current_division_balances: Vec<f64>,
}

#[derive(Debug, Clone, Serialize)]
struct Point {
    date: String,
    value: f64,
}

fn parse_date(value: &str, label: &str) -> Result<NaiveDate, String> {
    NaiveDate::parse_from_str(value, "%Y-%m-%d")
        .map_err(|error| format!("invalid {label}: {error}"))
}

fn parse_stamp(value: &str, label: &str) -> Result<DateTime<Utc>, String> {
    DateTime::parse_from_rfc3339(value)
        .map(|stamp| stamp.with_timezone(&Utc))
        .map_err(|error| format!("invalid {label}: {error}"))
}

fn observed_day(row: &SnapshotRow, start: NaiveDate) -> Result<NaiveDate, String> {
    let day = DateTime::parse_from_rfc3339(&row.recorded_at)
        .map_err(|error| format!("invalid recorded_at: {error}"))?
        .date_naive();
    Ok(day.max(start))
}

fn daily_closing(rows: &[SnapshotRow], start: NaiveDate) -> Result<Vec<Point>, String> {
    let mut latest: BTreeMap<NaiveDate, &SnapshotRow> = BTreeMap::new();
    for row in rows {
        let day = observed_day(row, start)?;
        let replace = latest.get(&day).map_or(true, |previous| {
            (row.recorded_at.as_str(), row.id) > (previous.recorded_at.as_str(), previous.id)
        });
        if replace {
            latest.insert(day, row);
        }
    }
    Ok(latest
        .into_iter()
        .map(|(day, row)| Point {
            date: day.to_string(),
            value: row.balance,
        })
        .collect())
}

fn grouped_daily(rows: &[SnapshotRow], start: NaiveDate) -> Result<Vec<Point>, String> {
    let mut latest: HashMap<(NaiveDate, i64), &SnapshotRow> = HashMap::new();
    let mut group_order = Vec::new();
    for row in rows {
        let group = row
            .group_id
            .ok_or_else(|| "group_id is required".to_string())?;
        if !group_order.contains(&group) {
            group_order.push(group);
        }
        let day = observed_day(row, start)?;
        let key = (day, group);
        let replace = latest.get(&key).map_or(true, |previous| {
            (row.recorded_at.as_str(), row.id) > (previous.recorded_at.as_str(), previous.id)
        });
        if replace {
            latest.insert(key, row);
        }
    }
    let mut observations: BTreeMap<NaiveDate, HashMap<i64, f64>> = BTreeMap::new();
    for ((day, group), row) in latest {
        observations
            .entry(day)
            .or_default()
            .insert(group, row.balance);
    }
    let mut state = HashMap::new();
    let mut points = Vec::new();
    for (day, values) in observations {
        state.extend(values);
        let total = group_order
            .iter()
            .map(|group| state.get(group).copied().unwrap_or(0.0))
            .sum();
        points.push(Point {
            date: day.to_string(),
            value: total,
        });
    }
    Ok(points)
}

fn combine_series(series: &[Vec<Point>]) -> Vec<Point> {
    let mut dates: BTreeMap<String, ()> = BTreeMap::new();
    let maps: Vec<HashMap<&str, f64>> = series
        .iter()
        .map(|points| {
            points
                .iter()
                .map(|point| {
                    dates.insert(point.date.clone(), ());
                    (point.date.as_str(), point.value)
                })
                .collect()
        })
        .collect();
    let mut current = vec![0.0; series.len()];
    dates
        .into_keys()
        .map(|date| {
            for (index, values) in maps.iter().enumerate() {
                if let Some(value) = values.get(date.as_str()) {
                    current[index] = *value;
                }
            }
            Point {
                date,
                value: current.iter().sum(),
            }
        })
        .collect()
}

fn wallet_statistics(points: &[Point], current_balance: Option<f64>) -> Result<Value, String> {
    if points.is_empty() {
        return Ok(json!({
            "current": current_balance,
            "net_change": 0.0,
            "percentage_growth": null,
            "average_daily_growth": 0.0,
            "largest_gain": 0.0,
            "largest_loss": 0.0,
        }));
    }
    let first = points[0].value;
    let latest = current_balance.unwrap_or_else(|| points.last().unwrap().value);
    let mut largest_gain: f64 = 0.0;
    let mut largest_loss: f64 = 0.0;
    for pair in points.windows(2) {
        let change = pair[1].value - pair[0].value;
        largest_gain = largest_gain.max(change);
        largest_loss = largest_loss.min(change);
    }
    let first_day = parse_date(&points[0].date, "first point date")?;
    let last_day = parse_date(&points.last().unwrap().date, "last point date")?;
    let elapsed_days = (last_day - first_day).num_days().max(1) as f64;
    let net = latest - first;
    let growth = if first == 0.0 {
        Value::Null
    } else {
        json!((latest - first) / first * 100.0)
    };
    Ok(json!({
        "current": latest,
        "net_change": net,
        "percentage_growth": growth,
        "average_daily_growth": net / elapsed_days,
        "largest_gain": largest_gain,
        "largest_loss": largest_loss,
    }))
}

fn distribution(values: &[f64]) -> Value {
    if values.is_empty() {
        return json!({"median": null, "average": null});
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|left, right| left.total_cmp(right));
    let middle = sorted.len() / 2;
    let median = if sorted.len() % 2 == 0 {
        (sorted[middle - 1] + sorted[middle]) / 2.0
    } else {
        sorted[middle]
    };
    json!({"median": median, "average": values.iter().sum::<f64>() / values.len() as f64})
}

fn evaluate_personal(input: PersonalInput) -> Result<Value, String> {
    let start = parse_date(&input.start_date, "start_date")?;
    let points = daily_closing(&input.snapshots, start)?;
    let mut stats = wallet_statistics(&points, input.current_balance)?;
    let income: f64 = input
        .journal
        .iter()
        .filter(|row| row.amount > 0.0)
        .map(|row| row.amount)
        .sum();
    let spending: f64 = input
        .journal
        .iter()
        .filter(|row| row.amount < 0.0)
        .map(|row| row.amount.abs())
        .sum();
    let cutoff = parse_stamp(&input.cutoff, "cutoff")?;
    let now = parse_stamp(&input.now, "now")?;
    let elapsed_days = (now - cutoff).num_days().max(1) as f64;
    let stats_object = stats.as_object_mut().expect("stats object");
    stats_object.insert("income".to_string(), json!(income));
    stats_object.insert("spending".to_string(), json!(spending));
    stats_object.insert(
        "spending_velocity".to_string(),
        json!(spending / elapsed_days),
    );

    let mut notable: Vec<(usize, &JournalRow)> = input.journal.iter().enumerate().collect();
    notable.sort_by(|(left_order, left), (right_order, right)| {
        right
            .amount
            .abs()
            .total_cmp(&left.amount.abs())
            .then_with(|| left_order.cmp(right_order))
    });
    notable.truncate(30);
    let mut timeline: Vec<(usize, &JournalRow)> = notable
        .into_iter()
        .enumerate()
        .map(|(rank, (_, row))| (rank, row))
        .collect();
    timeline.sort_by(|(left_rank, left), (right_rank, right)| {
        right
            .occurred_at
            .cmp(&left.occurred_at)
            .then_with(|| left_rank.cmp(right_rank))
    });
    Ok(json!({
        "schema_version": SCHEMA,
        "stats": stats,
        "points": points,
        "timeline": timeline.into_iter().map(|(_, row)| row.timeline.clone()).collect::<Vec<_>>(),
    }))
}

fn evaluate_corporation(input: CorporationInput) -> Result<Value, String> {
    let start = parse_date(&input.start_date, "start_date")?;
    let character_points = grouped_daily(&input.character_snapshots, start)?;
    let division_points = grouped_daily(&input.division_snapshots, start)?;
    let absolute_points = combine_series(&[character_points, division_points]);
    let character_total: f64 = input.current_character_balances.iter().sum();
    let corporation_total: f64 = input.current_division_balances.iter().sum();
    let has_current =
        !input.current_character_balances.is_empty() || !input.current_division_balances.is_empty();
    let current_total = has_current.then_some(character_total + corporation_total);
    let mut stats = wallet_statistics(&absolute_points, current_total)?;
    let points = if input.raw_visible {
        absolute_points
    } else {
        let baseline = absolute_points
            .first()
            .map(|point| point.value)
            .unwrap_or(0.0);
        absolute_points
            .into_iter()
            .map(|point| Point {
                date: point.date,
                value: point.value - baseline,
            })
            .collect()
    };
    let stats_object = stats.as_object_mut().expect("stats object");
    stats_object.insert(
        "current".to_string(),
        if input.raw_visible {
            json!(current_total)
        } else {
            Value::Null
        },
    );
    let wealth = if input.raw_visible {
        distribution(&input.current_character_balances)
    } else {
        json!({"median": null, "average": null})
    };
    for (key, value) in wealth.as_object().expect("wealth object") {
        stats_object.insert(key.clone(), value.clone());
    }
    Ok(json!({
        "schema_version": SCHEMA,
        "tracked_characters": input.current_character_balances.len(),
        "corporation_wallet_divisions": input.current_division_balances.len(),
        "corporation_wallet_total": if input.raw_visible { json!(corporation_total) } else { Value::Null },
        "character_wallet_total": if input.raw_visible { json!(character_total) } else { Value::Null },
        "series_mode": if input.raw_visible { "absolute" } else { "change" },
        "stats": stats,
        "points": points,
    }))
}

pub fn evaluate_financial_analytics(input: FinancialAnalyticsInput) -> Result<Value, String> {
    if input.schema_version != SCHEMA {
        return Err(format!(
            "unsupported financial analytics schema: {}",
            input.schema_version
        ));
    }
    match input.operation.as_str() {
        "personal" => evaluate_personal(
            input
                .personal
                .ok_or_else(|| "personal payload is required".to_string())?,
        ),
        "corporation" => evaluate_corporation(
            input
                .corporation
                .ok_or_else(|| "corporation payload is required".to_string())?,
        ),
        _ => Err(format!(
            "unsupported financial analytics operation: {}",
            input.operation
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn personal_summary_uses_daily_close_growth_and_notable_order() {
        let output = evaluate_personal(PersonalInput {
            start_date: "2026-08-01".to_string(),
            cutoff: "2026-08-01T00:00:00+00:00".to_string(),
            now: "2026-08-03T00:00:00+00:00".to_string(),
            current_balance: Some(130.0),
            snapshots: vec![
                SnapshotRow {
                    id: 1,
                    group_id: None,
                    recorded_at: "2026-08-01T08:00:00+00:00".to_string(),
                    balance: 100.0,
                },
                SnapshotRow {
                    id: 2,
                    group_id: None,
                    recorded_at: "2026-08-01T20:00:00+00:00".to_string(),
                    balance: 140.0,
                },
                SnapshotRow {
                    id: 3,
                    group_id: None,
                    recorded_at: "2026-08-02T08:00:00+00:00".to_string(),
                    balance: 120.0,
                },
            ],
            journal: vec![JournalRow {
                id: 1,
                occurred_at: "2026-08-02T10:00:00+00:00".to_string(),
                amount: -50.0,
                timeline: json!({"id": 1}),
            }],
        })
        .unwrap();
        assert_eq!(output["points"][0]["value"], 140.0);
        assert_eq!(output["stats"]["net_change"], -10.0);
        assert_eq!(output["stats"]["spending_velocity"], 25.0);
        assert_eq!(output["timeline"][0]["id"], 1);
    }

    #[test]
    fn corporation_change_mode_hides_absolute_values() {
        let output = evaluate_corporation(CorporationInput {
            start_date: "2026-08-01".to_string(),
            raw_visible: false,
            character_snapshots: vec![SnapshotRow {
                id: 1,
                group_id: Some(10),
                recorded_at: "2026-08-01T08:00:00+00:00".to_string(),
                balance: 100.0,
            }],
            division_snapshots: vec![SnapshotRow {
                id: 2,
                group_id: Some(1),
                recorded_at: "2026-08-02T08:00:00+00:00".to_string(),
                balance: 500.0,
            }],
            current_character_balances: vec![120.0],
            current_division_balances: vec![500.0],
        })
        .unwrap();
        assert_eq!(output["points"][0]["value"], 0.0);
        assert!(output["stats"]["current"].is_null());
        assert!(output["corporation_wallet_total"].is_null());
    }
}
