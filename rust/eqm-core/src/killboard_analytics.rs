use std::collections::{BTreeMap, BTreeSet, HashMap};

use chrono::NaiveDate;
use serde::{Deserialize, Serialize};

pub const INPUT_SCHEMA: &str = "eqm.killboard-analytics-input.v1";
pub const OUTPUT_SCHEMA: &str = "eqm.killboard-analytics-output.v1";
const RATE_SCALE: i128 = 10_000_000_000;

#[derive(Debug, Clone, Deserialize)]
pub struct KillboardAnalyticsInput {
    pub schema_version: String,
    pub as_of_date: String,
    #[serde(default)]
    pub events: Vec<KillboardEventInput>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct KillboardEventInput {
    pub date: String,
    pub is_kill: bool,
    pub is_loss: bool,
    pub value_cents: Option<i64>,
    pub solo: Option<bool>,
    pub damage_taken: i64,
    pub victim_hull: String,
    pub system_name: String,
    pub region_name: Option<String>,
    pub security_class: String,
    pub kill_opponent: Option<String>,
    #[serde(default)]
    pub loss_opponents: Vec<String>,
    #[serde(default)]
    pub matching_attackers: Vec<MatchingAttackerInput>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MatchingAttackerInput {
    pub ship_name: String,
    pub damage_done: i64,
    pub final_blow: bool,
    pub character_name: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RankedValue {
    pub name: String,
    pub count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KillboardSummaryOutput {
    pub kills: i64,
    pub losses: i64,
    pub isk_destroyed_cents: i64,
    pub isk_lost_cents: i64,
    pub efficiency_rate_units: Option<i64>,
    pub solo_kills: i64,
    pub fleet_kills: i64,
    pub final_blows: i64,
    pub damage_done: i64,
    pub damage_contribution_rate_units: Option<i64>,
    pub inactivity_days: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HullRankingsOutput {
    pub most_used: Vec<RankedValue>,
    pub most_killed: Vec<RankedValue>,
    pub most_lost: Vec<RankedValue>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GeographyOutput {
    pub systems: Vec<RankedValue>,
    pub regions: Vec<RankedValue>,
    pub security_classes: Vec<RankedValue>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StreaksOutput {
    pub current_kind: Option<String>,
    pub current: i64,
    pub longest_kill: i64,
    pub longest_loss: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WingmateOutput {
    pub characters: Vec<String>,
    pub shared_kills: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TimelineOutput {
    pub date: String,
    pub kills: i64,
    pub losses: i64,
    pub isk_destroyed_cents: i64,
    pub isk_lost_cents: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KillboardAnalyticsOutput {
    pub schema_version: String,
    pub unknown_value_records: i64,
    pub summary: KillboardSummaryOutput,
    pub hulls: HullRankingsOutput,
    pub geography: GeographyOutput,
    pub opponents: Vec<RankedValue>,
    pub streaks: StreaksOutput,
    pub wingmates: Vec<WingmateOutput>,
    pub timeline: Vec<TimelineOutput>,
}

#[derive(Default)]
struct OrderedCounter {
    positions: HashMap<String, usize>,
    rows: Vec<(String, i64)>,
}

impl OrderedCounter {
    fn increment(&mut self, name: &str) {
        if let Some(position) = self.positions.get(name).copied() {
            self.rows[position].1 += 1;
        } else {
            self.positions.insert(name.to_string(), self.rows.len());
            self.rows.push((name.to_string(), 1));
        }
    }

    fn ranked(&self, limit: usize) -> Vec<RankedValue> {
        let mut rows = self
            .rows
            .iter()
            .enumerate()
            .map(|(order, (name, count))| (order, name.clone(), *count))
            .collect::<Vec<_>>();
        rows.sort_by(|left, right| right.2.cmp(&left.2).then_with(|| left.0.cmp(&right.0)));
        rows.into_iter()
            .take(limit)
            .map(|(_, name, count)| RankedValue { name, count })
            .collect()
    }
}

fn rate_units(numerator: i128, denominator: i128) -> Option<i64> {
    if denominator <= 0 {
        return None;
    }
    let scaled = numerator * RATE_SCALE;
    let quotient = scaled / denominator;
    let remainder = scaled % denominator;
    Some((quotient + i128::from(remainder * 2 >= denominator)) as i64)
}

pub fn evaluate_killboard_analytics(input: KillboardAnalyticsInput) -> Result<KillboardAnalyticsOutput, String> {
    if input.schema_version != INPUT_SCHEMA {
        return Err(format!("unsupported killboard analytics schema: {}", input.schema_version));
    }
    let as_of_date = NaiveDate::parse_from_str(&input.as_of_date, "%Y-%m-%d")
        .map_err(|_| "as_of_date must use YYYY-MM-DD".to_string())?;

    let mut kills = 0_i64;
    let mut losses = 0_i64;
    let mut isk_destroyed_cents = 0_i64;
    let mut isk_lost_cents = 0_i64;
    let mut unknown_value_records = 0_i64;
    let mut solo_kills = 0_i64;
    let mut fleet_kills = 0_i64;
    let mut final_blows = 0_i64;
    let mut damage_done = 0_i64;
    let mut total_target_damage = 0_i64;
    let mut used_hulls = OrderedCounter::default();
    let mut killed_hulls = OrderedCounter::default();
    let mut lost_hulls = OrderedCounter::default();
    let mut systems = OrderedCounter::default();
    let mut regions = OrderedCounter::default();
    let mut security_classes = OrderedCounter::default();
    let mut opponents = OrderedCounter::default();
    let mut wingmate_positions: HashMap<(String, String), usize> = HashMap::new();
    let mut wingmate_rows: Vec<((String, String), i64)> = Vec::new();
    let mut timeline: BTreeMap<String, TimelineOutput> = BTreeMap::new();
    let mut results: Vec<&str> = Vec::new();

    for event in &input.events {
        NaiveDate::parse_from_str(&event.date, "%Y-%m-%d")
            .map_err(|_| format!("event date must use YYYY-MM-DD: {}", event.date))?;
        if event.damage_taken < 0 || event.value_cents.is_some_and(|value| value < 0) {
            return Err("killboard values and damage cannot be negative".to_string());
        }
        systems.increment(&event.system_name);
        security_classes.increment(&event.security_class);
        if let Some(region) = &event.region_name {
            regions.increment(region);
        }
        let day = timeline.entry(event.date.clone()).or_insert_with(|| TimelineOutput {
            date: event.date.clone(),
            kills: 0,
            losses: 0,
            isk_destroyed_cents: 0,
            isk_lost_cents: 0,
        });

        if event.is_kill {
            kills += 1;
            results.push("kill");
            day.kills += 1;
            if let Some(value) = event.value_cents {
                isk_destroyed_cents += value;
                day.isk_destroyed_cents += value;
            } else {
                unknown_value_records += 1;
            }
            if event.solo == Some(true) {
                solo_kills += 1;
            } else {
                fleet_kills += 1;
            }
            killed_hulls.increment(&event.victim_hull);
            let mut participating = BTreeSet::new();
            for attacker in &event.matching_attackers {
                if attacker.damage_done < 0 {
                    return Err("attacker damage cannot be negative".to_string());
                }
                used_hulls.increment(&attacker.ship_name);
                damage_done += attacker.damage_done;
                final_blows += i64::from(attacker.final_blow);
                if let Some(name) = &attacker.character_name {
                    participating.insert(name.clone());
                }
            }
            total_target_damage += event.damage_taken;
            if let Some(opponent) = &event.kill_opponent {
                opponents.increment(opponent);
            }
            let names = participating.into_iter().collect::<Vec<_>>();
            for left in 0..names.len() {
                for right in (left + 1)..names.len() {
                    let key = (names[left].clone(), names[right].clone());
                    if let Some(position) = wingmate_positions.get(&key).copied() {
                        wingmate_rows[position].1 += 1;
                    } else {
                        wingmate_positions.insert(key.clone(), wingmate_rows.len());
                        wingmate_rows.push((key, 1));
                    }
                }
            }
        }
        if event.is_loss {
            losses += 1;
            results.push("loss");
            day.losses += 1;
            if let Some(value) = event.value_cents {
                isk_lost_cents += value;
                day.isk_lost_cents += value;
            } else {
                unknown_value_records += 1;
            }
            lost_hulls.increment(&event.victim_hull);
            for opponent in &event.loss_opponents {
                opponents.increment(opponent);
            }
        }
    }

    let current_kind = results.first().map(|value| (*value).to_string());
    let current = current_kind.as_deref().map_or(0, |kind| {
        results.iter().take_while(|value| **value == kind).count() as i64
    });
    let mut longest_kill = 0_i64;
    let mut longest_loss = 0_i64;
    let mut running_kill = 0_i64;
    let mut running_loss = 0_i64;
    for result in results.iter().rev() {
        running_kill = if *result == "kill" { running_kill + 1 } else { 0 };
        running_loss = if *result == "loss" { running_loss + 1 } else { 0 };
        longest_kill = longest_kill.max(running_kill);
        longest_loss = longest_loss.max(running_loss);
    }

    let inactivity_days = input.events.first().map(|event| {
        let latest = NaiveDate::parse_from_str(&event.date, "%Y-%m-%d").unwrap();
        (as_of_date - latest).num_days().max(0)
    });
    let known_total = i128::from(isk_destroyed_cents) + i128::from(isk_lost_cents);
    let mut ranked_wingmates = wingmate_rows
        .into_iter()
        .enumerate()
        .map(|(order, (characters, count))| (order, characters, count))
        .collect::<Vec<_>>();
    ranked_wingmates.sort_by(|left, right| right.2.cmp(&left.2).then_with(|| left.0.cmp(&right.0)));

    Ok(KillboardAnalyticsOutput {
        schema_version: OUTPUT_SCHEMA.to_string(),
        unknown_value_records,
        summary: KillboardSummaryOutput {
            kills,
            losses,
            isk_destroyed_cents,
            isk_lost_cents,
            efficiency_rate_units: rate_units(i128::from(isk_destroyed_cents), known_total),
            solo_kills,
            fleet_kills,
            final_blows,
            damage_done,
            damage_contribution_rate_units: rate_units(i128::from(damage_done), i128::from(total_target_damage)),
            inactivity_days,
        },
        hulls: HullRankingsOutput {
            most_used: used_hulls.ranked(8),
            most_killed: killed_hulls.ranked(8),
            most_lost: lost_hulls.ranked(8),
        },
        geography: GeographyOutput {
            systems: systems.ranked(8),
            regions: regions.ranked(8),
            security_classes: security_classes.ranked(8),
        },
        opponents: opponents.ranked(12),
        streaks: StreaksOutput { current_kind, current, longest_kill, longest_loss },
        wingmates: ranked_wingmates
            .into_iter()
            .take(10)
            .map(|(_, (left, right), shared_kills)| WingmateOutput { characters: vec![left, right], shared_kills })
            .collect(),
        timeline: timeline.into_values().collect(),
    })
}
