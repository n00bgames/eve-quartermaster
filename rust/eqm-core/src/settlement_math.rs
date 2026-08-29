use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

pub const INPUT_SCHEMA: &str = "eqm.settlement-math-input.v1";
pub const OUTPUT_SCHEMA: &str = "eqm.settlement-math-output.v1";
const RATE_SCALE: i128 = 10_000_000_000;

#[derive(Debug, Clone, Deserialize)]
pub struct SettlementMathInput {
    pub schema_version: String,
    pub settlement_mode: String,
    pub gross_cents: i64,
    pub reserve_cents: i64,
    pub deduction_cents: i64,
    pub distributable_cents: i64,
    #[serde(default)]
    pub participants: Vec<SettlementParticipantInput>,
    #[serde(default)]
    pub outputs: Vec<SettlementOutputInput>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SettlementParticipantInput {
    pub index: usize,
    pub compensation_method: String,
    pub fixed_rate_units: Option<i64>,
    pub share_weight_units: Option<i64>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SettlementOutputInput {
    pub index: usize,
    pub quantity: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MineralAllocation {
    pub output_index: usize,
    pub quantity: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SettlementParticipantOutput {
    pub index: usize,
    pub payout_cents: i64,
    pub payout_ratio_units: i64,
    pub mineral_payouts: Vec<MineralAllocation>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SettlementOutputResult {
    pub index: usize,
    pub distributed_quantity: i64,
    pub retained_quantity: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SettlementMathOutput {
    pub schema_version: String,
    pub fixed_payout_total_cents: i64,
    pub share_pool_cents: i64,
    pub participant_payout_total_cents: i64,
    pub unallocated_cents: i64,
    pub participants: Vec<SettlementParticipantOutput>,
    pub outputs: Vec<SettlementOutputResult>,
}

fn round_half_up(numerator: i128, denominator: i128) -> i128 {
    let quotient = numerator / denominator;
    let remainder = numerator % denominator;
    if remainder * 2 >= denominator {
        quotient + 1
    } else {
        quotient
    }
}

fn largest_remainder(total: i64, weights: &[(usize, i128)], zero_error: &str) -> Result<Vec<(usize, i64)>, String> {
    if total <= 0 {
        return Ok(weights.iter().map(|(index, _)| (*index, 0)).collect());
    }
    let positive = weights
        .iter()
        .filter(|(_, weight)| *weight > 0)
        .copied()
        .collect::<Vec<_>>();
    let weight_total = positive.iter().map(|(_, weight)| *weight).sum::<i128>();
    if positive.is_empty() || weight_total <= 0 {
        return Err(zero_error.to_string());
    }

    let mut floors = weights
        .iter()
        .map(|(index, _)| (*index, 0_i64))
        .collect::<BTreeMap<_, _>>();
    let mut fractions = Vec::new();
    let mut allocated = 0_i64;
    for (index, weight) in positive {
        let numerator = i128::from(total) * weight;
        let floor = (numerator / weight_total) as i64;
        allocated += floor;
        *floors
            .get_mut(&index)
            .ok_or_else(|| "allocation index is missing".to_string())? = floor;
        fractions.push((numerator % weight_total, index));
    }
    fractions.sort_by(|left, right| {
        right
            .0
            .cmp(&left.0)
            .then_with(|| left.1.cmp(&right.1))
    });
    for (_, index) in fractions.into_iter().take((total - allocated) as usize) {
        *floors
            .get_mut(&index)
            .ok_or_else(|| "allocation index is missing".to_string())? += 1;
    }
    Ok(weights
        .iter()
        .map(|(index, _)| (*index, *floors.get(index).unwrap_or(&0)))
        .collect())
}

fn parse_nonnegative_decimal(value: &str) -> Result<(i128, i128), String> {
    let cleaned = value.trim();
    if cleaned.is_empty()
        || cleaned.starts_with('-')
        || cleaned.contains('e')
        || cleaned.contains('E')
    {
        return Err(format!("invalid nonnegative decimal quantity: {value}"));
    }
    let cleaned = cleaned.strip_prefix('+').unwrap_or(cleaned);
    let mut pieces = cleaned.split('.');
    let whole = pieces.next().unwrap_or("0");
    let fraction = pieces.next().unwrap_or("");
    if pieces.next().is_some()
        || (!whole.is_empty() && !whole.chars().all(|value| value.is_ascii_digit()))
        || !fraction.chars().all(|value| value.is_ascii_digit())
    {
        return Err(format!("invalid decimal quantity: {value}"));
    }
    let scale = 10_i128
        .checked_pow(fraction.len() as u32)
        .ok_or_else(|| "quantity precision is too large".to_string())?;
    let whole_value = if whole.is_empty() {
        0
    } else {
        whole
            .parse::<i128>()
            .map_err(|_| format!("invalid decimal quantity: {value}"))?
    };
    let fraction_value = if fraction.is_empty() {
        0
    } else {
        fraction
            .parse::<i128>()
            .map_err(|_| format!("invalid decimal quantity: {value}"))?
    };
    Ok((whole_value * scale + fraction_value, scale))
}

fn compensation_weights(
    participants: &[SettlementParticipantInput],
) -> Result<(Vec<i64>, Vec<(usize, i128)>), String> {
    let fixed_total = participants
        .iter()
        .filter(|row| row.compensation_method == "fixed_percentage")
        .map(|row| i128::from(row.fixed_rate_units.unwrap_or(0)))
        .sum::<i128>();
    if fixed_total > RATE_SCALE {
        return Err("Participant fixed percentages cannot exceed 100% of the distributable pool.".to_string());
    }
    let remaining = RATE_SCALE - fixed_total;
    let share_total = participants
        .iter()
        .filter(|row| row.compensation_method == "shares")
        .map(|row| i128::from(row.share_weight_units.unwrap_or(0).max(0)))
        .sum::<i128>();
    if remaining > 0 && share_total <= 0 {
        return Err("Share-based funds remain, but total share weight is zero.".to_string());
    }

    let mut ratio_units = vec![0_i64; participants.len()];
    let mut effective_weights = Vec::with_capacity(participants.len());
    for row in participants {
        if row.compensation_method == "fixed_percentage" {
            let fixed = i128::from(row.fixed_rate_units.unwrap_or(0).max(0));
            ratio_units[row.index] = fixed as i64;
            effective_weights.push((row.index, if share_total > 0 { fixed * share_total } else { fixed }));
        } else {
            let share = i128::from(row.share_weight_units.unwrap_or(0).max(0));
            ratio_units[row.index] = if share > 0 && share_total > 0 {
                round_half_up(remaining * share, share_total) as i64
            } else {
                0
            };
            effective_weights.push((
                row.index,
                if remaining > 0 { remaining * share } else { 0 },
            ));
        }
    }
    Ok((ratio_units, effective_weights))
}

pub fn evaluate_settlement_math(input: SettlementMathInput) -> Result<SettlementMathOutput, String> {
    if input.schema_version != INPUT_SCHEMA {
        return Err(format!(
            "unsupported settlement math schema: {}",
            input.schema_version
        ));
    }
    if !matches!(input.settlement_mode.as_str(), "isk" | "minerals") {
        return Err("settlement_mode must be isk or minerals".to_string());
    }
    if [
        input.gross_cents,
        input.reserve_cents,
        input.deduction_cents,
        input.distributable_cents,
    ]
    .iter()
    .any(|value| *value < 0)
    {
        return Err("settlement monetary values cannot be negative".to_string());
    }
    if input
        .participants
        .iter()
        .enumerate()
        .any(|(index, row)| row.index != index)
        || input
            .outputs
            .iter()
            .enumerate()
            .any(|(index, row)| row.index != index)
    {
        return Err("settlement indexes must be contiguous and ordered".to_string());
    }
    for row in &input.participants {
        if !matches!(row.compensation_method.as_str(), "fixed_percentage" | "shares") {
            return Err(format!(
                "unsupported compensation method: {}",
                row.compensation_method
            ));
        }
        if row.fixed_rate_units.unwrap_or(0) < 0 || row.share_weight_units.unwrap_or(0) < 0 {
            return Err("participant rates and weights cannot be negative".to_string());
        }
    }

    let fixed_total_rate = input
        .participants
        .iter()
        .filter(|row| row.compensation_method == "fixed_percentage")
        .map(|row| i128::from(row.fixed_rate_units.unwrap_or(0)))
        .sum::<i128>();
    if fixed_total_rate > RATE_SCALE {
        return Err("Participant fixed percentages cannot exceed 100% of the distributable pool.".to_string());
    }

    let mut payout_cents = vec![0_i64; input.participants.len()];
    for row in &input.participants {
        if let Some(rate) = row.fixed_rate_units {
            payout_cents[row.index] = round_half_up(
                i128::from(input.distributable_cents) * i128::from(rate),
                RATE_SCALE,
            ) as i64;
        }
    }
    let fixed_payout_total_cents = payout_cents.iter().sum::<i64>();
    let share_pool_cents = input.distributable_cents - fixed_payout_total_cents;
    let share_weights = input
        .participants
        .iter()
        .filter(|row| row.compensation_method == "shares")
        .map(|row| (row.index, i128::from(row.share_weight_units.unwrap_or(0))))
        .collect::<Vec<_>>();
    if share_pool_cents > 0 {
        for (index, amount) in largest_remainder(
            share_pool_cents,
            &share_weights,
            "Share-based funds remain, but total share weight is zero.",
        )? {
            payout_cents[index] += amount;
        }
    }

    let participant_payout_total_cents = payout_cents.iter().sum::<i64>();
    let unallocated_cents = input.gross_cents
        - input.reserve_cents
        - input.deduction_cents
        - participant_payout_total_cents;
    let mut payout_ratio_units = payout_cents
        .iter()
        .map(|payout| {
            if input.distributable_cents > 0 {
                round_half_up(
                    i128::from(*payout) * RATE_SCALE,
                    i128::from(input.distributable_cents),
                ) as i64
            } else {
                0
            }
        })
        .collect::<Vec<_>>();
    let mut mineral_payouts = vec![Vec::new(); input.participants.len()];
    let mut output_results = Vec::with_capacity(input.outputs.len());

    if input.settlement_mode == "minerals" {
        let (mineral_ratios, effective_weights) = compensation_weights(&input.participants)?;
        payout_ratio_units = mineral_ratios;
        for output in &input.outputs {
            let (quantity, scale) = parse_nonnegative_decimal(&output.quantity)?;
            let quantity_floor = (quantity / scale) as i64;
            let distributed_quantity = if input.gross_cents > 0 {
                (quantity * i128::from(input.distributable_cents)
                    / (scale * i128::from(input.gross_cents))) as i64
            } else {
                quantity_floor
            };
            let allocations = largest_remainder(
                distributed_quantity,
                &effective_weights,
                "Mineral units remain, but total participant weight is zero.",
            )?;
            for (participant_index, quantity) in allocations {
                if quantity > 0 {
                    mineral_payouts[participant_index].push(MineralAllocation {
                        output_index: output.index,
                        quantity,
                    });
                }
            }
            output_results.push(SettlementOutputResult {
                index: output.index,
                distributed_quantity,
                retained_quantity: quantity_floor - distributed_quantity,
            });
        }
    } else {
        for output in &input.outputs {
            let (quantity, scale) = parse_nonnegative_decimal(&output.quantity)?;
            output_results.push(SettlementOutputResult {
                index: output.index,
                distributed_quantity: 0,
                retained_quantity: (quantity / scale) as i64,
            });
        }
    }

    let participants = input
        .participants
        .iter()
        .map(|row| SettlementParticipantOutput {
            index: row.index,
            payout_cents: payout_cents[row.index],
            payout_ratio_units: payout_ratio_units[row.index],
            mineral_payouts: mineral_payouts[row.index].clone(),
        })
        .collect();
    Ok(SettlementMathOutput {
        schema_version: OUTPUT_SCHEMA.to_string(),
        fixed_payout_total_cents,
        share_pool_cents,
        participant_payout_total_cents,
        unallocated_cents,
        participants,
        outputs: output_results,
    })
}
