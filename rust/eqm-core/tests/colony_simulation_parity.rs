use eqm_core::colony_simulation::{known_pin_capacity_m3, simulate_colony, ColonySimulationInput};
use serde_json::Value;

fn fixture() -> ColonySimulationInput {
    serde_json::from_str(include_str!(
        "../../../backend/tests/fixtures/planetary-colony-simulation-input.v1.json"
    ))
    .expect("valid colony simulation input fixture")
}

#[test]
fn rust_simulation_matches_the_python_golden_contract() {
    let actual = serde_json::to_value(simulate_colony(fixture()).expect("simulation succeeds"))
        .expect("simulation serializes");
    let expected: Value = serde_json::from_str(include_str!(
        "../../../backend/tests/fixtures/planetary-colony-simulation-output.v1.json"
    ))
    .expect("valid colony simulation output fixture");
    assert_eq!(actual, expected);
}

#[test]
fn missing_checkpoint_preserves_observed_contents() {
    let mut payload = fixture();
    payload.checkpoint_at = None;
    payload.pins.truncate(1);
    payload.routes.clear();
    let result = simulate_colony(payload).expect("simulation succeeds");
    assert!(!result.is_projection);
    assert_eq!(result.events_processed, 0);
    assert_eq!(result.pins[&10].contents.get(&1), Some(&80));
}

#[test]
fn event_limit_sets_truncated_without_overrunning() {
    let mut payload = fixture();
    payload.max_events = 1;
    let result = simulate_colony(payload).expect("simulation succeeds");
    assert!(result.truncated);
    assert_eq!(result.events_processed, 1);
}

#[test]
fn known_storage_capacities_match_python() {
    assert_eq!(known_pin_capacity_m3("Temperate Launchpad"), Some(10_000.0));
    assert_eq!(known_pin_capacity_m3("Storage Facility"), Some(12_000.0));
    assert_eq!(known_pin_capacity_m3("Command Center"), Some(500.0));
    assert_eq!(known_pin_capacity_m3("High-Tech Production Plant"), None);
}
