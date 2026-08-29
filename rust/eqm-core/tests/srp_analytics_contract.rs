use eqm_core::srp_analytics::{evaluate_srp_analytics, SrpAnalyticsInput};

fn evaluate(json: &str) -> serde_json::Value {
    let input: SrpAnalyticsInput = serde_json::from_str(json).unwrap();
    serde_json::to_value(evaluate_srp_analytics(input).unwrap()).unwrap()
}

#[test]
fn exact_money_summary_series_quality_and_breakdowns_match_srp_semantics() {
    let result = evaluate(
        r#"{
      "schema_version":"eqm.srp-analytics-input.v1","calendar_days":3,"active_loss_days":2,"granularity":"day","rows":[
        {"request_id":1,"bucket":"2026-08-01","authoritative_loss_cents":10000,"requested_cents":5000,"approved_cents":4000,"paid_cents":null,"status":"approved","data_source":"manual","dimensions":{"doctrines":{"id":10,"label":"Shield Line"},"ship_types":{"id":621,"label":"Caracal"}}},
        {"request_id":2,"bucket":"2026-08-03","authoritative_loss_cents":30000,"requested_cents":5000,"approved_cents":5000,"paid_cents":5000,"status":"paid","data_source":"killmail","dimensions":{"doctrines":{"id":10,"label":"Shield Line"},"ship_types":{"id":621,"label":"Caracal"}}},
        {"request_id":3,"bucket":"2026-08-03","authoritative_loss_cents":null,"requested_cents":5000,"approved_cents":null,"paid_cents":null,"status":"rejected","data_source":"manual","dimensions":{"doctrines":{"id":null,"label":"Armor Line"},"ship_types":{"id":null,"label":"Unknown"}}}
      ]
    }"#,
    );
    assert_eq!(result["summary"]["loss_count"], 3);
    assert_eq!(result["summary"]["valued_loss_count"], 2);
    assert_eq!(result["summary"]["total_isk_lost_cents"], 40000);
    assert_eq!(result["summary"]["average_isk_per_loss_cents"], 13333);
    assert_eq!(
        result["summary"]["average_isk_per_active_loss_day_cents"],
        20000
    );
    assert_eq!(result["summary"]["rejected_reimbursement_cents"], 5000);
    assert_eq!(result["quality"]["unvalued_percentage_units"], 3333);
    assert_eq!(result["quality"]["missing_doctrine_count"], 1);
    assert_eq!(result["quality"]["manual_count"], 2);
    assert_eq!(result["time_series"][1]["loss_count"], 2);
    assert_eq!(result["breakdowns"]["doctrines"][0]["label"], "Shield Line");
    assert_eq!(
        result["breakdowns"]["doctrines"][0]["average_isk_cents"],
        20000
    );
    assert_eq!(result["top"]["ships_by_losses"][0]["label"], "Caracal");
}

#[test]
fn monetary_averages_use_decimal_half_even_rounding() {
    let result = evaluate(
        r#"{
      "schema_version":"eqm.srp-analytics-input.v1","calendar_days":2,"active_loss_days":2,"granularity":"day","rows":[
        {"request_id":1,"bucket":"2026-08-01","authoritative_loss_cents":1,"requested_cents":null,"approved_cents":null,"paid_cents":null,"status":"approved","data_source":"manual","dimensions":{"doctrines":{"id":1,"label":"A"},"ship_types":{"id":1,"label":"A"}}},
        {"request_id":2,"bucket":"2026-08-02","authoritative_loss_cents":null,"requested_cents":null,"approved_cents":null,"paid_cents":null,"status":"approved","data_source":"manual","dimensions":{"doctrines":{"id":1,"label":"A"},"ship_types":{"id":1,"label":"A"}}}
      ]
    }"#,
    );
    assert_eq!(result["summary"]["average_isk_per_loss_cents"], 0);
    assert_eq!(result["summary"]["average_isk_per_calendar_day_cents"], 0);
    assert_eq!(result["breakdowns"]["doctrines"][0]["average_isk_cents"], 1);
}

#[test]
fn empty_contract_preserves_null_averages_and_zero_quality() {
    let result = evaluate(
        r#"{"schema_version":"eqm.srp-analytics-input.v1","calendar_days":0,"active_loss_days":0,"granularity":"day","rows":[]}"#,
    );
    assert_eq!(result["summary"]["loss_count"], 0);
    assert!(result["summary"]["average_isk_per_loss_cents"].is_null());
    assert_eq!(result["quality"]["unvalued_percentage_units"], 0);
    assert_eq!(result["time_series"], serde_json::json!([]));
    assert_eq!(result["breakdowns"]["doctrines"], serde_json::json!([]));
    assert_eq!(
        result["breakdowns"]["security_classes"],
        serde_json::json!([])
    );
}
