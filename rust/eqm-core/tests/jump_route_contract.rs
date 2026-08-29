use eqm_core::jump_route::{
    evaluate_jump_route, JumpRouteInput, JumpSystem, INPUT_SCHEMA, OUTPUT_SCHEMA,
};

fn system(id: i64, x: f64, eligible: bool) -> JumpSystem {
    JumpSystem {
        system_id: id,
        name: format!("System {id}"),
        x_ly: x,
        y_ly: 0.0,
        z_ly: 0.0,
        eligible_midpoint: eligible,
    }
}

#[test]
fn fills_a_multi_jump_route_through_eligible_midpoints() {
    let output = evaluate_jump_route(JumpRouteInput {
        schema_version: INPUT_SCHEMA.to_string(),
        origin_system_id: 1,
        destination_system_id: 4,
        max_range_ly: 6.0,
        destination_allowed: true,
        avoid_system_ids: vec![],
        systems: vec![
            system(1, 0.0, false),
            system(2, 5.0, true),
            system(3, 10.0, true),
            system(4, 15.0, false),
        ],
    })
    .unwrap();

    assert_eq!(output.schema_version, OUTPUT_SCHEMA);
    assert_eq!(output.path_system_ids, vec![1, 2, 3, 4]);
    assert_eq!(output.total_distance_ly, 15.0);
}

#[test]
fn avoidance_and_midpoint_eligibility_are_enforced() {
    let result = evaluate_jump_route(JumpRouteInput {
        schema_version: INPUT_SCHEMA.to_string(),
        origin_system_id: 1,
        destination_system_id: 4,
        max_range_ly: 6.0,
        destination_allowed: true,
        avoid_system_ids: vec![2],
        systems: vec![
            system(1, 0.0, false),
            system(2, 5.0, true),
            system(3, 10.0, false),
            system(4, 15.0, false),
        ],
    });

    assert!(result.unwrap_err().contains("No jump route found"));
}
