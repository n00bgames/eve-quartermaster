use std::collections::{BTreeMap, HashMap, HashSet};

use chrono::{DateTime, Datelike, Duration, TimeZone, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

const SCHEMA: &str = "eqm.event-analytics.v1";

#[derive(Debug, Deserialize)]
pub struct EventAnalyticsInput {
    pub schema_version: String,
    pub operation: String,
    #[serde(default)]
    pub range: Option<RangeInput>,
    #[serde(default)]
    pub composition: Option<CompositionInput>,
}

#[derive(Debug, Deserialize)]
pub struct RangeInput {
    pub from_at: String,
    pub to_at: String,
    pub bucket: String,
    #[serde(default)]
    pub events: Vec<EventRow>,
}

#[derive(Debug, Deserialize)]
pub struct EventRow {
    pub event_type: String,
    pub start_at: String,
    #[serde(default)]
    pub responses: Vec<ResponseRow>,
    #[serde(default)]
    pub registrations: Vec<RegistrationRow>,
    #[serde(default)]
    pub attendance: Vec<AttendanceRow>,
}

#[derive(Debug, Deserialize)]
pub struct ResponseRow {
    pub user_id: i64,
    pub status: String,
}

#[derive(Debug, Deserialize)]
pub struct RegistrationRow {
    pub id: i64,
    pub user_id: i64,
    pub registration_status: String,
    #[serde(default)]
    pub confirmation_status: Option<String>,
    #[serde(default)]
    pub role_label: Option<String>,
    #[serde(default)]
    pub hull_label: Option<String>,
    #[serde(default)]
    pub doctrine_requirement_id: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub struct AttendanceRow {
    #[serde(default)]
    pub registration_id: Option<i64>,
    pub attendance_status: String,
}

#[derive(Debug, Deserialize)]
pub struct CompositionInput {
    #[serde(default)]
    pub responses: Vec<ResponseRow>,
    #[serde(default)]
    pub registrations: Vec<RegistrationRow>,
    #[serde(default)]
    pub attendance: Vec<AttendanceRow>,
    #[serde(default)]
    pub role_requirements: Vec<RequirementRow>,
    #[serde(default)]
    pub doctrine_requirements: Vec<RequirementRow>,
}

#[derive(Debug, Deserialize)]
pub struct RequirementRow {
    pub id: i64,
    pub label: String,
    pub requested: i64,
    #[serde(default)]
    pub sort_order: i64,
}

#[derive(Debug, Default, Clone, Serialize)]
pub struct Counts {
    event_count: i64,
    rsvp_going: i64,
    rsvp_maybe: i64,
    rsvp_declined: i64,
    rsvp_waitlisted: i64,
    registered_characters: i64,
    attended_registered: i64,
    attended_unregistered: i64,
    no_show: i64,
    excused: i64,
    unmarked: i64,
}

fn parse_utc(value: &str, label: &str) -> Result<DateTime<Utc>, String> {
    DateTime::parse_from_rfc3339(value)
        .map(|stamp| stamp.with_timezone(&Utc))
        .map_err(|error| format!("invalid {label}: {error}"))
}

fn add_counts(target: &mut Counts, event: &EventRow) {
    target.event_count += 1;
    for response in &event.responses {
        match response.status.as_str() {
            "going" => target.rsvp_going += 1,
            "maybe" => target.rsvp_maybe += 1,
            "declined" => target.rsvp_declined += 1,
            "waitlisted" => target.rsvp_waitlisted += 1,
            _ => {}
        }
    }
    let registered: HashSet<i64> = event
        .registrations
        .iter()
        .filter(|row| row.registration_status == "registered")
        .map(|row| row.id)
        .collect();
    target.registered_characters += registered.len() as i64;
    let mut marked = HashSet::new();
    for row in &event.attendance {
        if row
            .registration_id
            .is_some_and(|id| registered.contains(&id))
        {
            marked.insert(row.registration_id.unwrap());
            match row.attendance_status.as_str() {
                "attended" => target.attended_registered += 1,
                "no_show" => target.no_show += 1,
                "excused" => target.excused += 1,
                _ => {}
            }
        } else if row.attendance_status == "attended" {
            target.attended_unregistered += 1;
        }
    }
    target.unmarked += registered.difference(&marked).count() as i64;
}

fn round_half_even(numerator: i64, denominator: i64) -> i64 {
    let quotient = numerator / denominator;
    let remainder = numerator % denominator;
    let doubled = remainder.abs() * 2;
    if doubled > denominator.abs() || (doubled == denominator.abs() && quotient % 2 != 0) {
        quotient + numerator.signum() * denominator.signum()
    } else {
        quotient
    }
}

fn finalized(counts: &Counts) -> Value {
    let mut value = serde_json::to_value(counts).expect("counts serialize");
    let percent = if counts.registered_characters == 0 {
        Value::Null
    } else {
        json!(
            round_half_even(
                counts.attended_registered * 1000,
                counts.registered_characters
            ) as f64
                / 10.0
        )
    };
    value.as_object_mut().unwrap().insert(
        "attendance_rate".to_string(),
        json!({
            "numerator": counts.attended_registered,
            "denominator": counts.registered_characters,
            "percent": percent,
        }),
    );
    value
}

fn period_start(value: DateTime<Utc>, bucket: &str) -> Result<DateTime<Utc>, String> {
    let day = Utc
        .with_ymd_and_hms(value.year(), value.month(), value.day(), 0, 0, 0)
        .single()
        .ok_or_else(|| "invalid event day".to_string())?;
    match bucket {
        "day" => Ok(day),
        "week" => Ok(day - Duration::days(day.weekday().num_days_from_monday() as i64)),
        "month" => Utc
            .with_ymd_and_hms(value.year(), value.month(), 1, 0, 0, 0)
            .single()
            .ok_or_else(|| "invalid event month".to_string()),
        _ => Err(format!("unsupported event analytics bucket: {bucket}")),
    }
}

fn evaluate_range(input: RangeInput) -> Result<Value, String> {
    let from_at = parse_utc(&input.from_at, "from_at")?;
    let to_at = parse_utc(&input.to_at, "to_at")?;
    let mut totals = Counts::default();
    let mut by_type: BTreeMap<String, Counts> = BTreeMap::new();
    let mut by_period: BTreeMap<DateTime<Utc>, Counts> = BTreeMap::new();
    for event in &input.events {
        add_counts(&mut totals, event);
        add_counts(by_type.entry(event.event_type.clone()).or_default(), event);
        let start = period_start(parse_utc(&event.start_at, "event start_at")?, &input.bucket)?;
        add_counts(by_period.entry(start).or_default(), event);
    }
    let by_event_type: Vec<Value> = by_type
        .into_iter()
        .map(|(event_type, counts)| {
            let mut row = finalized(&counts);
            row.as_object_mut()
                .unwrap()
                .insert("event_type".to_string(), json!(event_type));
            row
        })
        .collect();
    let series: Vec<Value> = by_period
        .into_iter()
        .map(|(start, counts)| {
            let mut row = finalized(&counts);
            row.as_object_mut()
                .unwrap()
                .insert("period_start".to_string(), json!(start.to_rfc3339()));
            row
        })
        .collect();
    Ok(json!({
        "schema_version": SCHEMA,
        "from_at": from_at.to_rfc3339(),
        "to_at": to_at.to_rfc3339(),
        "bucket": input.bucket,
        "totals": finalized(&totals),
        "by_event_type": by_event_type,
        "series": series,
    }))
}

fn count_map(values: impl Iterator<Item = String>) -> BTreeMap<String, i64> {
    let mut counts = BTreeMap::new();
    for value in values {
        *counts.entry(value).or_insert(0) += 1;
    }
    counts
}

fn evaluate_composition(mut input: CompositionInput) -> Result<Value, String> {
    let rsvp = count_map(input.responses.iter().map(|row| row.status.clone()));
    let registration = count_map(
        input
            .registrations
            .iter()
            .map(|row| row.registration_status.clone()),
    );
    let confirmation = count_map(
        input
            .registrations
            .iter()
            .map(|row| row.confirmation_status.clone().unwrap_or_default()),
    );
    let roles = count_map(input.registrations.iter().map(|row| {
        row.role_label
            .clone()
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| "unassigned".to_string())
    }));
    let hulls = count_map(input.registrations.iter().map(|row| {
        row.hull_label
            .clone()
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| "Undecided".to_string())
    }));
    let doctrine_counts: HashMap<i64, i64> = input
        .registrations
        .iter()
        .filter_map(|row| row.doctrine_requirement_id)
        .fold(HashMap::new(), |mut map, id| {
            *map.entry(id).or_insert(0) += 1;
            map
        });
    let attendance_by_registration: HashSet<i64> = input
        .attendance
        .iter()
        .filter_map(|row| row.registration_id)
        .collect();
    let attended = input
        .attendance
        .iter()
        .filter(|row| row.attendance_status == "attended")
        .count();
    let no_show = input
        .attendance
        .iter()
        .filter(|row| row.attendance_status == "no_show")
        .count();
    let excused = input
        .attendance
        .iter()
        .filter(|row| row.attendance_status == "excused")
        .count();
    let unmarked = input
        .registrations
        .iter()
        .filter(|row| !attendance_by_registration.contains(&row.id))
        .count();
    let registered_users: HashSet<i64> =
        input.registrations.iter().map(|row| row.user_id).collect();
    let response_users: HashSet<i64> = input
        .responses
        .iter()
        .filter(|row| matches!(row.status.as_str(), "going" | "maybe"))
        .map(|row| row.user_id)
        .collect();

    input.role_requirements.sort_by_key(|row| row.sort_order);
    input
        .doctrine_requirements
        .sort_by_key(|row| row.sort_order);
    let role_requirements: Vec<Value> = input.role_requirements.into_iter().map(|row| {
        let registered = roles.get(&row.label).copied().unwrap_or(0);
        json!({"id": row.id, "label": row.label, "requested": row.requested, "registered": registered, "remaining": (row.requested - registered).max(0)})
    }).collect();
    let doctrine_requirements: Vec<Value> = input.doctrine_requirements.into_iter().map(|row| {
        let registered = doctrine_counts.get(&row.id).copied().unwrap_or(0);
        json!({"id": row.id, "label": row.label, "requested": row.requested, "registered": registered, "remaining": (row.requested - registered).max(0)})
    }).collect();
    Ok(json!({
        "schema_version": SCHEMA,
        "totals": {"rsvp": rsvp, "registration": registration, "confirmation": confirmation, "attendance": {"attended": attended, "no_show": no_show, "excused": excused, "unmarked": unmarked}},
        "roles": roles.into_iter().map(|(label, count)| json!({"label": label, "count": count})).collect::<Vec<_>>(),
        "hulls": hulls.into_iter().map(|(label, count)| json!({"label": label, "count": count})).collect::<Vec<_>>(),
        "role_requirements": role_requirements,
        "doctrine_requirements": doctrine_requirements,
        "users_without_characters": response_users.difference(&registered_users).count(),
    }))
}

pub fn evaluate_event_analytics(input: EventAnalyticsInput) -> Result<Value, String> {
    if input.schema_version != SCHEMA {
        return Err(format!(
            "unsupported event analytics schema: {}",
            input.schema_version
        ));
    }
    match input.operation.as_str() {
        "range" => evaluate_range(
            input
                .range
                .ok_or_else(|| "range payload is required".to_string())?,
        ),
        "composition" => evaluate_composition(
            input
                .composition
                .ok_or_else(|| "composition payload is required".to_string())?,
        ),
        _ => Err(format!(
            "unsupported event analytics operation: {}",
            input.operation
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn range_counts_registered_and_unregistered_attendance() {
        let output = evaluate_range(RangeInput {
            from_at: "2026-08-01T00:00:00+00:00".to_string(),
            to_at: "2026-08-03T00:00:00+00:00".to_string(),
            bucket: "day".to_string(),
            events: vec![EventRow {
                event_type: "fleet".to_string(),
                start_at: "2026-08-01T19:00:00+00:00".to_string(),
                responses: vec![ResponseRow {
                    user_id: 1,
                    status: "going".to_string(),
                }],
                registrations: vec![
                    RegistrationRow {
                        id: 1,
                        user_id: 1,
                        registration_status: "registered".to_string(),
                        confirmation_status: Some("confirmed".to_string()),
                        role_label: None,
                        hull_label: None,
                        doctrine_requirement_id: None,
                    },
                    RegistrationRow {
                        id: 2,
                        user_id: 2,
                        registration_status: "registered".to_string(),
                        confirmation_status: None,
                        role_label: None,
                        hull_label: None,
                        doctrine_requirement_id: None,
                    },
                ],
                attendance: vec![
                    AttendanceRow {
                        registration_id: Some(1),
                        attendance_status: "attended".to_string(),
                    },
                    AttendanceRow {
                        registration_id: None,
                        attendance_status: "attended".to_string(),
                    },
                ],
            }],
        })
        .unwrap();
        assert_eq!(output["totals"]["registered_characters"], 2);
        assert_eq!(output["totals"]["attended_unregistered"], 1);
        assert_eq!(output["totals"]["unmarked"], 1);
        assert_eq!(output["totals"]["attendance_rate"]["percent"], 50.0);
    }

    #[test]
    fn attendance_percentage_uses_python_half_even_rounding() {
        assert_eq!(round_half_even(1_000, 16) as f64 / 10.0, 6.2);
    }

    #[test]
    fn composition_counts_fleet_gaps_and_unregistered_rsvps() {
        let output = evaluate_composition(CompositionInput {
            responses: vec![
                ResponseRow {
                    user_id: 1,
                    status: "going".to_string(),
                },
                ResponseRow {
                    user_id: 2,
                    status: "maybe".to_string(),
                },
            ],
            registrations: vec![RegistrationRow {
                id: 10,
                user_id: 1,
                registration_status: "registered".to_string(),
                confirmation_status: Some("confirmed".to_string()),
                role_label: Some("logistics".to_string()),
                hull_label: Some("Guardian".to_string()),
                doctrine_requirement_id: Some(20),
            }],
            attendance: vec![],
            role_requirements: vec![RequirementRow {
                id: 30,
                label: "logistics".to_string(),
                requested: 3,
                sort_order: 0,
            }],
            doctrine_requirements: vec![RequirementRow {
                id: 20,
                label: "Armor logistics".to_string(),
                requested: 2,
                sort_order: 0,
            }],
        })
        .unwrap();
        assert_eq!(
            output["roles"][0],
            json!({"label": "logistics", "count": 1})
        );
        assert_eq!(output["hulls"][0], json!({"label": "Guardian", "count": 1}));
        assert_eq!(output["role_requirements"][0]["remaining"], 2);
        assert_eq!(output["doctrine_requirements"][0]["remaining"], 1);
        assert_eq!(output["totals"]["attendance"]["unmarked"], 1);
        assert_eq!(output["users_without_characters"], 1);
    }
}
