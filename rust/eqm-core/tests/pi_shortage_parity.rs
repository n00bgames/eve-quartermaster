use eqm_core::pi_shortage::{
    available_planetary_shortage_targets, build_planetary_shortage_report, PlanetaryIndustryPayload,
};
use serde_json::Value;

fn assert_json_equivalent(actual: &Value, expected: &Value, path: &str) {
    match (actual, expected) {
        (Value::Number(left), Value::Number(right)) => {
            let left = left.as_f64().expect("actual number is finite");
            let right = right.as_f64().expect("expected number is finite");
            assert!(
                (left - right).abs() <= 0.000001,
                "number mismatch at {path}: {left} != {right}"
            );
        }
        (Value::Array(left), Value::Array(right)) => {
            assert_eq!(left.len(), right.len(), "array length mismatch at {path}");
            for (index, (left, right)) in left.iter().zip(right).enumerate() {
                assert_json_equivalent(left, right, &format!("{path}[{index}]"));
            }
        }
        (Value::Object(left), Value::Object(right)) => {
            assert_eq!(
                left.keys().collect::<Vec<_>>(),
                right.keys().collect::<Vec<_>>(),
                "object keys differ at {path}"
            );
            for (key, left) in left {
                assert_json_equivalent(left, &right[key], &format!("{path}.{key}"));
            }
        }
        _ => assert_eq!(actual, expected, "value mismatch at {path}"),
    }
}

fn fixture() -> PlanetaryIndustryPayload {
    serde_json::from_str(include_str!(
        "../../../frontend/tests/fixtures/planetary-shortage-input.v1.json"
    ))
    .expect("valid PI input fixture")
}

#[test]
fn rust_report_matches_the_typescript_golden_contract() {
    let report =
        build_planetary_shortage_report(&fixture(), Some(2870), "2026-08-28T12:30:00.000Z");
    let actual = serde_json::to_value(report).expect("report serializes");
    let expected: Value = serde_json::from_str(include_str!(
        "../../../frontend/tests/fixtures/planetary-shortage-report.v2.json"
    ))
    .expect("valid PI output fixture");

    assert_json_equivalent(&actual, &expected, "$");
}

#[test]
fn idle_target_factory_remains_planned_demand() {
    let report =
        build_planetary_shortage_report(&fixture(), Some(2870), "2026-08-28T12:30:00.000Z");
    assert_eq!(report.scope.configured_target_factories, 1);
    assert_eq!(report.scope.configured_target_output_per_day, 24.0);
    let coolant = report
        .commodities
        .iter()
        .find(|row| row.name == "Coolant")
        .expect("Coolant row");
    assert_eq!(coolant.additional_processors_to_balance, Some(3));
    assert_eq!(coolant.base_components.len(), 2);
}

#[test]
fn target_catalog_is_deterministic() {
    let targets = available_planetary_shortage_targets(&fixture());
    assert_eq!(
        targets
            .iter()
            .map(|target| target.name.as_str())
            .collect::<Vec<_>>(),
        vec!["Bacteria", "Coolant", "Organic Mortar Applicators"]
    );
}

#[test]
fn inventory_extends_runway_and_final_output_is_surplus() {
    let mut data = fixture();
    data.hangar_stock.insert(9832, 720.0);
    let report = build_planetary_shortage_report(&data, Some(2870), &data.as_of);
    let row = report.commodities.iter().find(|r| r.type_id == 9832).unwrap();
    assert_eq!(row.net_shortfall_per_day, 360.0);
    assert_eq!(row.total_inventory, row.projected_inventory + 720.0);
    assert_eq!(row.runway_days_at_net_shortfall, Some(2.666667));
    let output = report.commodities.iter().find(|r| r.type_id == 2870).unwrap();
    assert_eq!(output.net_surplus_per_day, 24.0);
    assert_eq!(output.coverage, None);
}
