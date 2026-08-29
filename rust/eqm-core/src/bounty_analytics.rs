use std::cmp::Ordering;
use std::collections::{BTreeMap, HashMap, HashSet};

use chrono::{DateTime, SecondsFormat, Timelike, Utc};
use serde::{Deserialize, Serialize};

pub const INPUT_SCHEMA: &str = "eqm.bounty-analytics-input.v1";
pub const OUTPUT_SCHEMA: &str = "eqm.bounty-analytics-output.v1";

#[derive(Debug, Clone, Deserialize)]
pub struct BountyAnalyticsInput {
    pub schema_version: String,
    #[serde(default)]
    pub ticks: Vec<BountyTick>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BountyTick {
    pub tick_id: String,
    pub occurred_at: DateTime<Utc>,
    pub bucket_start: DateTime<Utc>,
    pub character_eve_id: i64,
    pub character_name: String,
    pub corporation_eve_id: Option<i64>,
    pub corporation_name: Option<String>,
    #[serde(default)]
    pub reference_ids: Vec<i64>,
    pub net_isk: f64,
    pub corporate_tax_isk: Option<f64>,
    pub gross_isk: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BountySummary {
    pub net_isk: f64,
    pub tick_count: usize,
    pub average_tick_isk: f64,
    pub highest_tick_isk: Option<f64>,
    pub highest_tick_id: Option<String>,
    pub highest_tick_pilot: Option<String>,
    pub most_recent_at: Option<String>,
    pub active_pilots: usize,
    pub corporate_tax_isk: Option<f64>,
    pub known_corporate_tax_isk: f64,
    pub gross_isk: Option<f64>,
    pub known_gross_isk: f64,
    pub effective_tax_rate: Option<f64>,
    pub tax_coverage_complete: bool,
    pub tax_known_ticks: usize,
    pub tax_unknown_ticks: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BountyTimelinePoint {
    pub bucket_start: String,
    #[serde(flatten)]
    pub summary: BountySummary,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BountyLeaderboardRow {
    pub rank: usize,
    pub character_eve_id: i64,
    pub character_name: String,
    pub corporation_eve_id: Option<i64>,
    pub corporation_name: Option<String>,
    #[serde(flatten)]
    pub summary: BountySummary,
    pub tick_ids: Vec<String>,
    pub reference_ids: Vec<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BountyAnalyticsOutput {
    pub schema_version: String,
    pub summary: BountySummary,
    pub timeline: Vec<BountyTimelinePoint>,
    pub leaderboard: Vec<BountyLeaderboardRow>,
}

fn summarize(ticks: &[&BountyTick]) -> BountySummary {
    let tick_count = ticks.len();
    let net_isk = sum_isk(ticks.iter().map(|tick| tick.net_isk));
    let known = ticks
        .iter()
        .filter(|tick| tick.corporate_tax_isk.is_some() && tick.gross_isk.is_some())
        .copied()
        .collect::<Vec<_>>();
    let known_corporate_tax_isk = sum_isk(known.iter().filter_map(|tick| tick.corporate_tax_isk));
    let known_gross_isk = sum_isk(known.iter().filter_map(|tick| tick.gross_isk));
    let tax_coverage_complete = known.len() == tick_count;

    let mut highest: Option<&BountyTick> = None;
    let mut recent: Option<&BountyTick> = None;
    for tick in ticks {
        if highest
            .map(|current| tick.net_isk > current.net_isk)
            .unwrap_or(true)
        {
            highest = Some(tick);
        }
        if recent
            .map(|current| tick.occurred_at > current.occurred_at)
            .unwrap_or(true)
        {
            recent = Some(tick);
        }
    }
    let active_pilots = ticks
        .iter()
        .map(|tick| tick.character_eve_id)
        .collect::<HashSet<_>>()
        .len();

    BountySummary {
        net_isk,
        tick_count,
        average_tick_isk: if tick_count == 0 {
            0.0
        } else {
            net_isk / tick_count as f64
        },
        highest_tick_isk: highest.map(|tick| tick.net_isk),
        highest_tick_id: highest.map(|tick| tick.tick_id.clone()),
        highest_tick_pilot: highest.map(|tick| tick.character_name.clone()),
        most_recent_at: recent.map(|tick| isoformat(tick.occurred_at)),
        active_pilots,
        corporate_tax_isk: tax_coverage_complete.then_some(known_corporate_tax_isk),
        known_corporate_tax_isk,
        gross_isk: tax_coverage_complete.then_some(known_gross_isk),
        known_gross_isk,
        effective_tax_rate: if tax_coverage_complete && known_gross_isk != 0.0 {
            Some(known_corporate_tax_isk / known_gross_isk * 100.0)
        } else {
            None
        },
        tax_coverage_complete,
        tax_known_ticks: known.len(),
        tax_unknown_ticks: tick_count - known.len(),
    }
}

fn sum_isk(values: impl Iterator<Item = f64>) -> f64 {
    let cents = values
        .map(|value| (value * 100.0).round() as i128)
        .sum::<i128>();
    cents as f64 / 100.0
}

fn isoformat(value: DateTime<Utc>) -> String {
    let precision = if value.nanosecond() == 0 {
        SecondsFormat::Secs
    } else {
        SecondsFormat::Micros
    };
    value.to_rfc3339_opts(precision, false)
}

fn leaderboard(ticks: &[BountyTick]) -> Vec<BountyLeaderboardRow> {
    let mut grouped: HashMap<i64, Vec<&BountyTick>> = HashMap::new();
    for tick in ticks {
        grouped
            .entry(tick.character_eve_id)
            .or_default()
            .push(tick);
    }
    let mut result = grouped
        .into_iter()
        .map(|(character_eve_id, rows)| BountyLeaderboardRow {
            rank: 0,
            character_eve_id,
            character_name: rows[0].character_name.clone(),
            corporation_eve_id: rows[0].corporation_eve_id,
            corporation_name: rows[0].corporation_name.clone(),
            summary: summarize(&rows),
            tick_ids: rows.iter().map(|tick| tick.tick_id.clone()).collect(),
            reference_ids: rows
                .iter()
                .flat_map(|tick| tick.reference_ids.iter().copied())
                .collect(),
        })
        .collect::<Vec<_>>();
    result.sort_by(|left, right| {
        right
            .summary
            .net_isk
            .partial_cmp(&left.summary.net_isk)
            .unwrap_or(Ordering::Equal)
            .then_with(|| {
                right
                    .summary
                    .highest_tick_isk
                    .unwrap_or(0.0)
                    .partial_cmp(&left.summary.highest_tick_isk.unwrap_or(0.0))
                    .unwrap_or(Ordering::Equal)
            })
            .then_with(|| right.character_name.cmp(&left.character_name))
    });
    for (index, row) in result.iter_mut().enumerate() {
        row.rank = index + 1;
    }
    result
}

fn timeline(ticks: &[BountyTick]) -> Vec<BountyTimelinePoint> {
    let mut buckets: BTreeMap<DateTime<Utc>, Vec<&BountyTick>> = BTreeMap::new();
    for tick in ticks {
        buckets.entry(tick.bucket_start).or_default().push(tick);
    }
    buckets
        .into_iter()
        .map(|(bucket_start, rows)| BountyTimelinePoint {
            bucket_start: isoformat(bucket_start),
            summary: summarize(&rows),
        })
        .collect()
}

pub fn evaluate_bounty_analytics(
    input: BountyAnalyticsInput,
) -> Result<BountyAnalyticsOutput, String> {
    if input.schema_version != INPUT_SCHEMA {
        return Err(format!(
            "unsupported bounty analytics schema: {}",
            input.schema_version
        ));
    }
    if input.ticks.iter().any(|tick| {
        !tick.net_isk.is_finite()
            || tick
                .corporate_tax_isk
                .is_some_and(|value| !value.is_finite())
            || tick.gross_isk.is_some_and(|value| !value.is_finite())
    }) {
        return Err("bounty analytics contains a non-finite monetary value".to_string());
    }
    let refs = input.ticks.iter().collect::<Vec<_>>();
    Ok(BountyAnalyticsOutput {
        schema_version: OUTPUT_SCHEMA.to_string(),
        summary: summarize(&refs),
        timeline: timeline(&input.ticks),
        leaderboard: leaderboard(&input.ticks),
    })
}
