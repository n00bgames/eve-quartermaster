use eqm_core::settlement_math::{evaluate_settlement_math, SettlementMathInput};

fn evaluate(json: &str) -> serde_json::Value {
    let input: SettlementMathInput = serde_json::from_str(json).unwrap();
    serde_json::to_value(evaluate_settlement_math(input).unwrap()).unwrap()
}

#[test]
fn equal_isk_shares_distribute_the_remainder_deterministically() {
    let result = evaluate(r#"{
        "schema_version":"eqm.settlement-math-input.v1","settlement_mode":"isk",
        "gross_cents":100000,"reserve_cents":0,"deduction_cents":0,"distributable_cents":100000,
        "participants":[
          {"index":0,"compensation_method":"shares","fixed_rate_units":null,"share_weight_units":100000000},
          {"index":1,"compensation_method":"shares","fixed_rate_units":null,"share_weight_units":100000000},
          {"index":2,"compensation_method":"shares","fixed_rate_units":null,"share_weight_units":100000000}],
        "outputs":[{"index":0,"quantity":"10"}]
    }"#);
    let payouts = result["participants"].as_array().unwrap().iter()
        .map(|row| row["payout_cents"].as_i64().unwrap()).collect::<Vec<_>>();
    assert_eq!(payouts, vec![33334, 33333, 33333]);
    assert_eq!(result["participant_payout_total_cents"], 100000);
    assert_eq!(result["unallocated_cents"], 0);
}

#[test]
fn mixed_fixed_and_share_indexes_are_preserved() {
    let result = evaluate(r#"{
        "schema_version":"eqm.settlement-math-input.v1","settlement_mode":"isk",
        "gross_cents":100000,"reserve_cents":0,"deduction_cents":0,"distributable_cents":100000,
        "participants":[
          {"index":0,"compensation_method":"fixed_percentage","fixed_rate_units":500000000,"share_weight_units":null},
          {"index":1,"compensation_method":"shares","fixed_rate_units":null,"share_weight_units":100000000},
          {"index":2,"compensation_method":"shares","fixed_rate_units":null,"share_weight_units":300000000}],
        "outputs":[]
    }"#);
    let payouts = result["participants"].as_array().unwrap().iter()
        .map(|row| row["payout_cents"].as_i64().unwrap()).collect::<Vec<_>>();
    assert_eq!(payouts, vec![5000, 23750, 71250]);
}

#[test]
fn mineral_units_use_largest_remainder_and_retain_reserve() {
    let result = evaluate(r#"{
        "schema_version":"eqm.settlement-math-input.v1","settlement_mode":"minerals",
        "gross_cents":100000,"reserve_cents":10000,"deduction_cents":0,"distributable_cents":90000,
        "participants":[
          {"index":0,"compensation_method":"shares","fixed_rate_units":null,"share_weight_units":60000000},
          {"index":1,"compensation_method":"shares","fixed_rate_units":null,"share_weight_units":40000000}],
        "outputs":[{"index":0,"quantity":"100"}]
    }"#);
    assert_eq!(result["outputs"][0]["distributed_quantity"], 90);
    assert_eq!(result["outputs"][0]["retained_quantity"], 10);
    assert_eq!(result["participants"][0]["mineral_payouts"][0]["quantity"], 54);
    assert_eq!(result["participants"][1]["mineral_payouts"][0]["quantity"], 36);
}

#[test]
fn unpriced_minerals_still_allocate_all_whole_units() {
    let result = evaluate(r#"{
        "schema_version":"eqm.settlement-math-input.v1","settlement_mode":"minerals",
        "gross_cents":0,"reserve_cents":0,"deduction_cents":0,"distributable_cents":0,
        "participants":[
          {"index":0,"compensation_method":"shares","fixed_rate_units":null,"share_weight_units":100000000},
          {"index":1,"compensation_method":"shares","fixed_rate_units":null,"share_weight_units":100000000}],
        "outputs":[{"index":0,"quantity":"11"}]
    }"#);
    assert_eq!(result["participants"][0]["mineral_payouts"][0]["quantity"], 6);
    assert_eq!(result["participants"][1]["mineral_payouts"][0]["quantity"], 5);
    assert_eq!(result["participants"][0]["payout_ratio_units"], 5000000000_i64);
}
