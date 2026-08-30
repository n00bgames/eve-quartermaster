use std::collections::HashMap;

use chrono::DateTime;
use serde::{Deserialize, Serialize};

const INPUT_SCHEMA: &str = "eqm.threat-analytics-input.v1";
const OUTPUT_SCHEMA: &str = "eqm.threat-analytics-output.v1";

#[derive(Debug, Deserialize)]
pub struct ThreatAnalyticsInput {
    pub schema_version: String,
    pub evaluated_at: String,
    pub refresh_hours: i64,
    #[serde(default)]
    pub rows: Vec<ThreatObservation>,
}

#[derive(Debug, Deserialize)]
pub struct ThreatObservation {
    pub killmail_time: String,
    #[serde(default)]
    pub total_value_cents: i64,
    #[serde(default)]
    pub victim_hull: Option<String>,
    #[serde(default)]
    pub location_kind: Option<String>,
    #[serde(default)]
    pub location_name: Option<String>,
    #[serde(default)]
    pub final_blow_hull: Option<String>,
    #[serde(default)]
    pub attacker_count: i64,
    #[serde(default)]
    pub attacker_corporations: Vec<String>,
    #[serde(default)]
    pub attacker_alliances: Vec<String>,
    #[serde(default)]
    pub victim_corporation: Option<String>,
    #[serde(default)]
    pub victim_alliance: Option<String>,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct RankedThreat {
    pub name: String,
    pub count: i64,
    pub total_value_cents: i64,
}

#[derive(Debug, Serialize)]
pub struct ThreatAnalyticsOutput {
    pub schema_version: &'static str,
    pub total_kills: usize,
    pub total_destroyed_value_cents: i64,
    pub latest_killmail_time: Option<String>,
    pub risk_score: i64,
    pub risk_label: &'static str,
    pub top_victim_hulls: Vec<RankedThreat>,
    pub top_time_periods: Vec<RankedThreat>,
    pub top_attacker_corporations: Vec<RankedThreat>,
    pub top_attacker_alliances: Vec<RankedThreat>,
    pub top_victim_corporations: Vec<RankedThreat>,
    pub top_victim_alliances: Vec<RankedThreat>,
    pub most_dangerous_locations: Vec<RankedThreat>,
    pub top_final_blow_hulls: Vec<RankedThreat>,
    pub top_attacker_group_sizes: Vec<RankedThreat>,
}

#[derive(Default)]
struct Ranking {
    values: HashMap<String, (i64, i64, usize)>,
    next_order: usize,
}

impl Ranking {
    fn add(&mut self, name: String, value_cents: i64) {
        let next_order = self.next_order;
        let entry = self.values.entry(name).or_insert_with(|| {
            self.next_order += 1;
            (0, 0, next_order)
        });
        entry.0 += 1;
        entry.1 += value_cents;
    }

    fn finish(self) -> Vec<RankedThreat> {
        let mut rows: Vec<_> = self
            .values
            .into_iter()
            .map(|(name, (count, total_value_cents, order))| {
                (order, RankedThreat { name, count, total_value_cents })
            })
            .collect();
        rows.sort_by(|left, right| right.1.count.cmp(&left.1.count).then(left.0.cmp(&right.0)));
        rows.into_iter().take(5).map(|(_, row)| row).collect()
    }
}

fn text_or(value: &Option<String>, fallback: &str) -> String {
    value.as_ref().filter(|value| !value.is_empty()).cloned().unwrap_or_else(|| fallback.to_string())
}

fn time_period(value: &str) -> Result<String, String> {
    let stamp = DateTime::parse_from_rfc3339(value)
        .map_err(|error| format!("invalid killmail_time: {error}"))?;
    let hour = stamp.timestamp().div_euclid(3600).rem_euclid(24);
    Ok(format!("{hour:02}:00-{:02}:00 UTC", (hour + 1) % 24))
}

fn risk_label(score: i64) -> &'static str {
    if score >= 70 { "hot" } else if score >= 35 { "active" } else if score > 0 { "warm" } else { "quiet" }
}

pub fn evaluate_threat_analytics(input: ThreatAnalyticsInput) -> Result<ThreatAnalyticsOutput, String> {
    if input.schema_version != INPUT_SCHEMA {
        return Err(format!("unsupported threat analytics schema: {}", input.schema_version));
    }
    let evaluated_at = DateTime::parse_from_rfc3339(&input.evaluated_at)
        .map_err(|error| format!("invalid evaluated_at: {error}"))?;
    let mut rows = input.rows;
    rows.sort_by(|left, right| right.killmail_time.cmp(&left.killmail_time));

    let mut victim_hulls = Ranking::default();
    let mut periods = Ranking::default();
    let mut attacker_corporations = Ranking::default();
    let mut attacker_alliances = Ranking::default();
    let mut victim_corporations = Ranking::default();
    let mut victim_alliances = Ranking::default();
    let mut locations = Ranking::default();
    let mut final_hulls = Ranking::default();
    let mut group_sizes = Ranking::default();
    let mut total_value_cents = 0_i64;

    for row in &rows {
        total_value_cents = total_value_cents.checked_add(row.total_value_cents)
            .ok_or_else(|| "threat total exceeds supported range".to_string())?;
        victim_hulls.add(text_or(&row.victim_hull, "Unknown hull"), row.total_value_cents);
        periods.add(time_period(&row.killmail_time)?, row.total_value_cents);
        locations.add(
            format!("{} · {}", text_or(&row.location_kind, "space"), text_or(&row.location_name, "Unknown location")),
            row.total_value_cents,
        );
        final_hulls.add(text_or(&row.final_blow_hull, "Unknown final-blow hull"), row.total_value_cents);
        group_sizes.add(
            format!("{} attacker{}", row.attacker_count, if row.attacker_count == 1 { "" } else { "s" }),
            row.total_value_cents,
        );
        let mut seen = std::collections::HashSet::new();
        for name in &row.attacker_corporations {
            if seen.insert(name) { attacker_corporations.add(name.clone(), row.total_value_cents); }
        }
        seen.clear();
        for name in &row.attacker_alliances {
            if seen.insert(name) { attacker_alliances.add(name.clone(), row.total_value_cents); }
        }
        if let Some(name) = row.victim_corporation.as_ref().filter(|value| !value.is_empty()) {
            victim_corporations.add(name.clone(), row.total_value_cents);
        }
        if let Some(name) = row.victim_alliance.as_ref().filter(|value| !value.is_empty()) {
            victim_alliances.add(name.clone(), row.total_value_cents);
        }
    }

    let latest = rows.first().map(|row| row.killmail_time.clone());
    let mut score = rows.len() as i64 * 10;
    score += ((total_value_cents / 100_000_000_000) * 5).min(40);
    if let Some(latest_text) = &latest {
        let latest_at = DateTime::parse_from_rfc3339(latest_text)
            .map_err(|error| format!("invalid latest killmail_time: {error}"))?;
        let age_hours = ((evaluated_at - latest_at).num_milliseconds() as f64 / 3_600_000.0).max(0.0);
        if age_hours <= 1.0 {
            score += 35;
        } else if age_hours <= 6.0 {
            score += 20;
        } else if age_hours <= (input.refresh_hours as f64 / 2.0).max(12.0) {
            score += 10;
        }
    }
    score = score.min(100);

    Ok(ThreatAnalyticsOutput {
        schema_version: OUTPUT_SCHEMA,
        total_kills: rows.len(),
        total_destroyed_value_cents: total_value_cents,
        latest_killmail_time: latest,
        risk_score: score,
        risk_label: risk_label(score),
        top_victim_hulls: victim_hulls.finish(),
        top_time_periods: periods.finish(),
        top_attacker_corporations: attacker_corporations.finish(),
        top_attacker_alliances: attacker_alliances.finish(),
        top_victim_corporations: victim_corporations.finish(),
        top_victim_alliances: victim_alliances.finish(),
        most_dangerous_locations: locations.finish(),
        top_final_blow_hulls: final_hulls.finish(),
        top_attacker_group_sizes: group_sizes.finish(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reduces_rankings_values_and_risk_deterministically() {
        let result = evaluate_threat_analytics(ThreatAnalyticsInput {
            schema_version: INPUT_SCHEMA.to_string(),
            evaluated_at: "2026-08-29T12:30:00+00:00".to_string(),
            refresh_hours: 24,
            rows: vec![
                ThreatObservation { killmail_time: "2026-08-29T12:00:00+00:00".to_string(), total_value_cents: 150_000_000_000, victim_hull: Some("Badger".to_string()), location_kind: Some("gate".to_string()), location_name: Some("Stargate".to_string()), final_blow_hull: Some("Tornado".to_string()), attacker_count: 3, attacker_corporations: vec!["Pirates".to_string(), "Pirates".to_string()], attacker_alliances: vec!["Bad Alliance".to_string()], victim_corporation: Some("Haulers".to_string()), victim_alliance: None },
                ThreatObservation { killmail_time: "2026-08-28T11:00:00+00:00".to_string(), total_value_cents: 50_000_000_000, victim_hull: Some("Badger".to_string()), location_kind: None, location_name: None, final_blow_hull: Some("Catalyst".to_string()), attacker_count: 1, attacker_corporations: vec!["Pirates".to_string()], attacker_alliances: vec![], victim_corporation: Some("Haulers".to_string()), victim_alliance: None },
            ],
        }).unwrap();
        assert_eq!(result.total_destroyed_value_cents, 200_000_000_000);
        assert_eq!(result.risk_score, 65);
        assert_eq!(result.risk_label, "active");
        assert_eq!(result.top_victim_hulls[0], RankedThreat { name: "Badger".to_string(), count: 2, total_value_cents: 200_000_000_000 });
        assert_eq!(result.top_attacker_corporations[0].count, 2);
    }
}
