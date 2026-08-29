use chrono::{TimeZone, Utc};
use eqm_core::analytics_summary::{
    evaluate_analytics_summary, AnalyticsSummaryInput, CharacterCategoryRow, CharacterRow,
    CorporationRow, StandingRow, INPUT_SCHEMA, OUTPUT_SCHEMA,
};

fn character(
    id: i64,
    character_id: i64,
    name: &str,
    value: f64,
    month: u32,
    day: u32,
) -> CharacterRow {
    CharacterRow {
        id,
        character_id,
        character_name: name.to_string(),
        total_skill_points: value,
        recorded_at: Utc.with_ymd_and_hms(2026, month, day, 0, 0, 0).unwrap(),
    }
}

fn corporation(
    id: i64,
    value: f64,
    members: f64,
    blueprints: f64,
    month: u32,
    day: u32,
) -> CorporationRow {
    CorporationRow {
        id,
        corporation_id: 7,
        corporation_name: "Rustaceans".to_string(),
        wallet_balance: value,
        member_count: members,
        blueprint_count: blueprints,
        recorded_at: Utc.with_ymd_and_hms(2026, month, day, 0, 0, 0).unwrap(),
    }
}

#[test]
fn analytics_summary_contract_separates_coverage_and_builds_rankings() {
    let cutoff = Utc.with_ymd_and_hms(2026, 8, 1, 0, 0, 0).unwrap();
    let existing = vec![
        character(1, 10, "Existing", 100.0, 7, 31),
        character(2, 10, "Existing", 110.0, 8, 3),
    ];
    let newcomer = vec![
        character(3, 20, "New", 200.0, 8, 2),
        character(4, 20, "New", 205.0, 8, 4),
    ];
    let mut all_characters = existing.clone();
    all_characters.extend(newcomer.clone());
    let category_rows = vec![
        CharacterCategoryRow {
            id: 1,
            character_id: 10,
            category_name: Some("Engineering".to_string()),
            category_skill_points: 40.0,
            recorded_at: Utc.with_ymd_and_hms(2026, 7, 31, 0, 0, 0).unwrap(),
        },
        CharacterCategoryRow {
            id: 2,
            character_id: 10,
            category_name: Some("Engineering".to_string()),
            category_skill_points: 50.0,
            recorded_at: Utc.with_ymd_and_hms(2026, 8, 3, 0, 0, 0).unwrap(),
        },
    ];
    let corporations = vec![
        corporation(1, 1_000.0, 10.0, 20.0, 7, 31),
        corporation(2, 1_250.0, 11.0, 23.0, 8, 3),
    ];
    let standings = vec![
        StandingRow {
            id: 1,
            series_key: "pilot-navy".to_string(),
            recorded_at: Utc.with_ymd_and_hms(2026, 7, 31, 0, 0, 0).unwrap(),
            metric_value: 1.0,
            source_type: "npc_corp".to_string(),
            source_eve_id: 99,
            source_name: "Navy".to_string(),
        },
        StandingRow {
            id: 2,
            series_key: "pilot-navy".to_string(),
            recorded_at: Utc.with_ymd_and_hms(2026, 8, 3, 0, 0, 0).unwrap(),
            metric_value: 1.5,
            source_type: "npc_corp".to_string(),
            source_eve_id: 99,
            source_name: "Navy".to_string(),
        },
    ];
    let output = evaluate_analytics_summary(AnalyticsSummaryInput {
        schema_version: INPUT_SCHEMA.to_string(),
        cutoff,
        character_rows: all_characters.clone(),
        identified_character_rows: all_characters,
        character_category_rows: category_rows,
        corporation_rows: corporations,
        standing_rows: standings,
    })
    .unwrap();

    assert_eq!(output.schema_version, OUTPUT_SCHEMA);
    assert_eq!(output.cards.character_count, 2);
    assert_eq!(output.cards.wallet_total, 1_250.0);
    assert_eq!(output.change_composition.skill_points.current, 315.0);
    assert_eq!(output.change_composition.skill_points.organic_delta, 15.0);
    assert_eq!(output.change_composition.skill_points.coverage_delta, 200.0);
    assert_eq!(output.top_sp_gainers[0].name, "Existing");
    assert_eq!(output.top_skill_category_gainers[0].delta, 10.0);
    assert_eq!(output.wallet_growth[0].delta, 250.0);
    assert_eq!(output.standings_movement.corporations.gains[0].delta, 0.5);
    assert_eq!(output.series.wallet_totals[0].date, "2026-08-01");
}

#[test]
fn analytics_summary_rejects_unknown_schema() {
    let result = evaluate_analytics_summary(AnalyticsSummaryInput {
        schema_version: "eqm.analytics-summary-input.v999".to_string(),
        cutoff: Utc.with_ymd_and_hms(2026, 8, 1, 0, 0, 0).unwrap(),
        character_rows: vec![],
        identified_character_rows: vec![],
        character_category_rows: vec![],
        corporation_rows: vec![],
        standing_rows: vec![],
    });
    assert!(result
        .unwrap_err()
        .contains("unsupported analytics summary schema"));
}
