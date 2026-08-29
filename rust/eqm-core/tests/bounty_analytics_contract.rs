use chrono::{DateTime, Utc};

use eqm_core::bounty_analytics::{
    evaluate_bounty_analytics, BountyAnalyticsInput, BountyTick, INPUT_SCHEMA, OUTPUT_SCHEMA,
};

fn timestamp(value: &str) -> DateTime<Utc> {
    value.parse().unwrap()
}

fn tick(
    id: &str,
    occurred_at: &str,
    bucket_start: &str,
    pilot_id: i64,
    pilot_name: &str,
    reference_id: i64,
    net: f64,
    tax: Option<f64>,
) -> BountyTick {
    BountyTick {
        tick_id: id.to_string(),
        occurred_at: timestamp(occurred_at),
        bucket_start: timestamp(bucket_start),
        character_eve_id: pilot_id,
        character_name: pilot_name.to_string(),
        corporation_eve_id: Some(98_000_001),
        corporation_name: Some("Example Corporation".to_string()),
        reference_ids: vec![reference_id],
        net_isk: net,
        corporate_tax_isk: tax,
        gross_isk: tax.map(|value| net + value),
    }
}

#[test]
fn bounty_contract_builds_summary_timeline_and_traceable_leaderboard() {
    let output = evaluate_bounty_analytics(BountyAnalyticsInput {
        schema_version: INPUT_SCHEMA.to_string(),
        ticks: vec![
            tick(
                "90000002:2026-08-18T06:00:00+00:00",
                "2026-08-18T06:00:00Z",
                "2026-08-18T05:00:00Z",
                90_000_002,
                "Pilot Two",
                201,
                3000.0,
                None,
            ),
            tick(
                "90000001:2026-08-18T05:00:00+00:00",
                "2026-08-18T05:00:00Z",
                "2026-08-18T05:00:00Z",
                90_000_001,
                "Pilot One",
                102,
                1900.0,
                Some(100.0),
            ),
            tick(
                "90000001:2026-08-17T04:30:00+00:00",
                "2026-08-17T04:30:00Z",
                "2026-08-17T05:00:00Z",
                90_000_001,
                "Pilot One",
                101,
                950.0,
                Some(50.0),
            ),
        ],
    })
    .unwrap();

    assert_eq!(output.schema_version, OUTPUT_SCHEMA);
    assert_eq!(output.summary.net_isk, 5850.0);
    assert_eq!(output.summary.tick_count, 3);
    assert_eq!(output.summary.average_tick_isk, 1950.0);
    assert_eq!(output.summary.highest_tick_pilot.as_deref(), Some("Pilot Two"));
    assert_eq!(output.summary.known_corporate_tax_isk, 150.0);
    assert_eq!(output.summary.known_gross_isk, 3000.0);
    assert!(!output.summary.tax_coverage_complete);
    assert_eq!(output.summary.corporate_tax_isk, None);
    assert_eq!(output.timeline.len(), 2);
    assert_eq!(output.timeline[1].summary.net_isk, 4900.0);
    assert_eq!(output.leaderboard[0].character_name, "Pilot Two");
    assert_eq!(output.leaderboard[1].reference_ids, vec![102, 101]);
}

#[test]
fn empty_bounty_contract_matches_python_zero_semantics() {
    let output = evaluate_bounty_analytics(BountyAnalyticsInput {
        schema_version: INPUT_SCHEMA.to_string(),
        ticks: vec![],
    })
    .unwrap();

    assert_eq!(output.summary.tick_count, 0);
    assert_eq!(output.summary.net_isk, 0.0);
    assert_eq!(output.summary.corporate_tax_isk, Some(0.0));
    assert_eq!(output.summary.gross_isk, Some(0.0));
    assert!(output.summary.tax_coverage_complete);
}

#[test]
fn monetary_totals_accumulate_in_exact_isk_cents() {
    let output = evaluate_bounty_analytics(BountyAnalyticsInput {
        schema_version: INPUT_SCHEMA.to_string(),
        ticks: vec![
            tick(
                "one",
                "2026-08-18T06:00:00Z",
                "2026-08-18T05:00:00Z",
                1,
                "Pilot",
                1,
                1_336_390_000.11,
                Some(0.1),
            ),
            tick(
                "two",
                "2026-08-18T05:00:00Z",
                "2026-08-18T05:00:00Z",
                1,
                "Pilot",
                2,
                585.15,
                Some(0.2),
            ),
        ],
    })
    .unwrap();

    assert_eq!(output.summary.net_isk, 1_336_390_585.26);
    assert_eq!(output.summary.known_corporate_tax_isk, 0.3);
}
