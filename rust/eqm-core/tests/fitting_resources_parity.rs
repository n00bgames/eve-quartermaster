use eqm_core::fitting_resources::{evaluate_fitting_resources, FittingResourcesInput};
use serde_json::Value;

fn assert_json_equivalent(actual: &Value, expected: &Value, path: &str) {
    match (actual, expected) {
        (Value::Number(left), Value::Number(right)) => {
            let left = left.as_f64().expect("actual number is finite");
            let right = right.as_f64().expect("expected number is finite");
            assert!(
                (left - right).abs() <= 0.000000001,
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

#[test]
fn rust_fitting_resources_match_the_python_golden_contract() {
    let payload: FittingResourcesInput = serde_json::from_str(include_str!(
        "../../../backend/tests/fixtures/fitting-resources-input.v1.json"
    ))
    .expect("valid fitting resources input fixture");
    let actual = serde_json::to_value(
        evaluate_fitting_resources(payload).expect("resource evaluation succeeds"),
    )
    .expect("resource evaluation serializes");
    let expected: Value = serde_json::from_str(include_str!(
        "../../../backend/tests/fixtures/fitting-resources-output.v1.json"
    ))
    .expect("valid fitting resources output fixture");
    assert_json_equivalent(&actual, &expected, "$");
}
