use std::cmp::Ordering;

use serde::{Deserialize, Serialize};

const STACKING_PENALTIES: [f64; 7] = [
    1.0, 0.8708869, 0.5705831, 0.2829552, 0.1059926, 0.0299912, 0.0064102,
];

#[derive(Clone, Debug, Deserialize)]
pub struct FittingMathInput {
    pub schema_version: String,
    #[serde(default)]
    pub stacking_cases: Vec<StackingCaseInput>,
    #[serde(default)]
    pub capacitor_cases: Vec<CapacitorCaseInput>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct StackingCaseInput {
    pub name: String,
    #[serde(default)]
    pub raw_multipliers: Vec<f64>,
    #[serde(default)]
    pub unpenalized_multipliers: Vec<f64>,
    #[serde(default)]
    pub dogma_values: Vec<f64>,
    #[serde(default)]
    pub percent_bonuses: Vec<f64>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct CapacitorCaseInput {
    pub name: String,
    pub capacity: f64,
    pub recharge_seconds: f64,
    pub sample_percent: f64,
    pub drain_per_second: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct FittingMathOutput {
    pub schema_version: &'static str,
    pub stacking_cases: Vec<StackingCaseOutput>,
    pub capacitor_cases: Vec<CapacitorCaseOutput>,
}

#[derive(Clone, Debug, Serialize)]
pub struct StackingCaseOutput {
    pub name: String,
    pub raw_multiplier: f64,
    pub unpenalized_multiplier: f64,
    pub dogma_multiplier: f64,
    pub percent_bonus_multiplier: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct CapacitorCaseOutput {
    pub name: String,
    pub recharge_at_sample: f64,
    pub stable_percent: Option<f64>,
    pub depletion_seconds: Option<f64>,
}

pub fn dogma_multiplier(value: Option<f64>) -> Option<f64> {
    let number = value?;
    if number == 0.0 {
        None
    } else if number.abs() > 2.0 {
        Some(1.0 + number / 100.0)
    } else {
        Some(number)
    }
}

pub fn stacking_raw_multiplier(values: &[f64]) -> f64 {
    let mut useful = values
        .iter()
        .copied()
        .filter(|value| *value != 0.0 && *value > 0.0 && (*value - 1.0).abs() > 0.0001)
        .collect::<Vec<_>>();
    useful.sort_by(|left, right| {
        (right - 1.0)
            .abs()
            .partial_cmp(&(left - 1.0).abs())
            .unwrap_or(Ordering::Equal)
    });
    useful
        .iter()
        .enumerate()
        .fold(1.0, |result, (index, value)| {
            let penalty = STACKING_PENALTIES.get(index).copied().unwrap_or(0.0);
            result * (1.0 + (value - 1.0) * penalty)
        })
}

pub fn unpenalized_multiplier(values: &[f64]) -> f64 {
    values
        .iter()
        .copied()
        .filter(|value| *value > 0.0)
        .product()
}

pub fn stacking_multiplier(values: &[f64]) -> f64 {
    stacking_raw_multiplier(
        &values
            .iter()
            .filter_map(|value| dogma_multiplier(Some(*value)))
            .collect::<Vec<_>>(),
    )
}

pub fn percent_bonus_multiplier(values: &[f64]) -> f64 {
    stacking_raw_multiplier(
        &values
            .iter()
            .copied()
            .filter(|value| *value != 0.0)
            .map(|value| 1.0 + value / 100.0)
            .collect::<Vec<_>>(),
    )
}

pub fn capacitor_recharge_at_percent(capacity: f64, recharge_seconds: f64, percent: f64) -> f64 {
    let fraction = (percent / 100.0).clamp(0.0, 1.0);
    if capacity <= 0.0 || recharge_seconds <= 0.0 || fraction <= 0.0 {
        return 0.0;
    }
    (10.0 * capacity / recharge_seconds) * (fraction.sqrt() - fraction)
}

pub fn capacitor_stable_percent(
    capacity: f64,
    recharge_seconds: f64,
    drain_per_second: f64,
) -> Option<f64> {
    if drain_per_second <= 0.0 {
        return Some(100.0);
    }
    let peak = if capacity > 0.0 && recharge_seconds > 0.0 {
        capacity / recharge_seconds * 2.5
    } else {
        0.0
    };
    if peak <= 0.0 || drain_per_second > peak {
        return None;
    }
    let mut low = 25.0;
    let mut high = 100.0;
    for _ in 0..40 {
        let mid = (low + high) / 2.0;
        if capacitor_recharge_at_percent(capacity, recharge_seconds, mid) >= drain_per_second {
            low = mid;
        } else {
            high = mid;
        }
    }
    Some(low.clamp(0.0, 100.0))
}

pub fn capacitor_depletion_seconds(
    capacity: f64,
    recharge_seconds: f64,
    drain_per_second: f64,
) -> Option<f64> {
    if capacity <= 0.0 || drain_per_second <= 0.0 {
        return None;
    }
    let mut capacitor = capacity;
    let mut elapsed = 0.0;
    while capacitor > 0.0 && elapsed < 28_800.0 {
        let percent = capacitor / capacity * 100.0;
        let recharge = if recharge_seconds > 0.0 {
            capacitor_recharge_at_percent(capacity, recharge_seconds, percent)
        } else {
            0.0
        };
        capacitor += recharge - drain_per_second;
        elapsed += 1.0;
    }
    (capacitor <= 0.0).then_some(elapsed)
}

pub fn evaluate_fitting_math(input: FittingMathInput) -> Result<FittingMathOutput, String> {
    if input.schema_version != "eqm.fitting-math-input.v1" {
        return Err(format!(
            "unsupported fitting math schema: {}",
            input.schema_version
        ));
    }
    Ok(FittingMathOutput {
        schema_version: "eqm.fitting-math-output.v1",
        stacking_cases: input
            .stacking_cases
            .into_iter()
            .map(|case| StackingCaseOutput {
                name: case.name,
                raw_multiplier: stacking_raw_multiplier(&case.raw_multipliers),
                unpenalized_multiplier: unpenalized_multiplier(&case.unpenalized_multipliers),
                dogma_multiplier: stacking_multiplier(&case.dogma_values),
                percent_bonus_multiplier: percent_bonus_multiplier(&case.percent_bonuses),
            })
            .collect(),
        capacitor_cases: input
            .capacitor_cases
            .into_iter()
            .map(|case| CapacitorCaseOutput {
                name: case.name,
                recharge_at_sample: capacitor_recharge_at_percent(
                    case.capacity,
                    case.recharge_seconds,
                    case.sample_percent,
                ),
                stable_percent: capacitor_stable_percent(
                    case.capacity,
                    case.recharge_seconds,
                    case.drain_per_second,
                ),
                depletion_seconds: capacitor_depletion_seconds(
                    case.capacity,
                    case.recharge_seconds,
                    case.drain_per_second,
                ),
            })
            .collect(),
    })
}
