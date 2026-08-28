use eqm_core::fitting_stats::{evaluate_fitting_stats, FittingStatsInput};

fn close(actual: f64, expected: f64) {
    assert!(
        (actual - expected).abs() <= 0.000000001,
        "{actual} != {expected}"
    );
}

#[test]
fn normalized_fitting_stats_contract_evaluates_foundational_sections() {
    let payload: FittingStatsInput = serde_json::from_str(include_str!(
        "../../../backend/tests/fixtures/fitting-stats-input.v1.json"
    ))
    .expect("valid normalized fitting stats fixture");
    let result = evaluate_fitting_stats(payload).expect("evaluation succeeds");

    close(result.defense.shield_hp, 1584.0);
    close(result.defense.armor_hp, 1000.0);
    close(result.defense.structure_hp, 575.0);
    close(result.defense.shield_ehp, 1584.0 / 0.65);
    close(result.defense.armor_ehp, 2500.0);
    close(result.defense.structure_ehp, 575.0 / 0.6);
    close(result.mobility.max_velocity.unwrap(), 125.0 * (1.0 + 1_000_000.0 / 1_100_000.0));
    close(result.mobility.align_time.unwrap(), 0.762461898616);
    close(result.mobility.signature_radius.unwrap(), 120.0);
    close(result.mobility.mass.unwrap(), 1_100_000.0);
    close(result.capacitor.capacity.unwrap(), 1200.0);
    close(result.capacitor.recharge_time.unwrap(), 75.0);
    close(result.capacitor.peak_recharge.unwrap(), 40.0);
    close(result.capacitor.draw_per_second, 3.25);
    assert!(result.capacitor.stable);
    assert!(result.capacitor.stable_percent.unwrap() < 100.0);
    close(result.defense.armor_repair_hps, 10.0);
    close(result.defense.active_tank_hps, 10.0);
    close(result.defense.armor_resists.em, 0.6);

    let cargo = result.cargo_bays.iter().find(|row| row.key == "Cargo").unwrap();
    close(cargo.used, 20.0);
    close(cargo.capacity.unwrap(), 120.0);
    close(cargo.percent.unwrap(), 100.0 / 6.0);
    let drones = result.cargo_bays.iter().find(|row| row.key == "DroneBay").unwrap();
    close(drones.used, 15.0);
    close(drones.capacity.unwrap(), 50.0);
    close(drones.percent.unwrap(), 30.0);

    close(result.targeting.targeting_range.unwrap(), 120000.0);
    close(result.targeting.scan_resolution.unwrap(), 250.0);
    close(result.targeting.sensor_strength.unwrap(), 12.0);
    close(result.offense.turret_dps, 14.375);
    close(result.offense.drone_dps, 22.5);
    close(result.offense.total_dps, 36.875);
    close(result.offense.volley, 91.0);
    close(result.offense.damage_types.em, 68.0);
    close(result.offense.damage_types.thermal, 23.0);
    close(result.offense.max_range_m.unwrap(), 22_500.0);
    assert_eq!(result.offense.weapon_count, 2);
    assert_eq!(result.offense.weapons[0]["name"], "Test Drone");
}
