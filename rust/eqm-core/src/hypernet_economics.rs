use chrono::DateTime;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

const SCHEMA_VERSION: &str = "eqm.hypernet-economics.v1";

#[derive(Debug, Deserialize)]
pub struct HyperNetEconomicsInput {
    pub schema_version: String,
    pub operation: String,
    #[serde(default)]
    pub offer: Option<OfferInput>,
    #[serde(default)]
    pub participation: Option<ParticipationInput>,
    #[serde(default)]
    pub reconciliation: Option<ReconciliationInput>,
}

#[derive(Debug, Deserialize)]
pub struct OfferInput {
    pub total_offer_price_cents: i64,
    pub total_nodes: i64,
    pub seller_owned_nodes: i64,
    pub hypercores_required: i64,
    pub hypercore_unit_cost_cents: i64,
    pub acquisition_cost_cents: i64,
    #[serde(default)]
    pub desired_profit_cents: i64,
    #[serde(default)]
    pub jita_sell_cents: Option<i64>,
    #[serde(default)]
    pub local_sell_cents: Option<i64>,
    #[serde(default)]
    pub created_at: Option<String>,
    #[serde(default)]
    pub snapshots: Vec<ProgressSnapshotInput>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ProgressSnapshotInput {
    #[serde(default)]
    pub id: i64,
    pub captured_at: String,
    #[serde(default)]
    pub nodes_sold: i64,
    #[serde(default)]
    pub seller_owned_nodes: i64,
}

#[derive(Debug, Deserialize)]
pub struct ParticipationInput {
    pub total_nodes: i64,
    pub nodes_purchased: i64,
    pub node_price_cents: i64,
    pub outcome: String,
    #[serde(default)]
    pub item_value_at_completion_cents: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub struct ReconciliationInput {
    pub status: String,
    pub winner: String,
    pub total_offer_price_cents: i64,
    pub total_nodes: i64,
    pub seller_owned_nodes: i64,
    pub hypercores_required: i64,
    pub hypercore_unit_cost_cents: i64,
    pub acquisition_cost_cents: i64,
    #[serde(default)]
    pub actual_hypercore_cost_cents: Option<i64>,
    #[serde(default)]
    pub payout_cents: Option<i64>,
    #[serde(default)]
    pub final_market_value_cents: Option<i64>,
    #[serde(default)]
    pub final_profit_cents: Option<i64>,
}

#[derive(Debug, Serialize)]
pub struct OfferOutput {
    pub schema_version: &'static str,
    pub financials: FinancialOutput,
    pub seeded_scenario: SeededScenarioOutput,
    pub progress: ProgressOutput,
}

#[derive(Debug, Serialize)]
pub struct FinancialOutput {
    pub node_price_cents: i64,
    pub gross_offer_value_cents: i64,
    pub completion_fee_cents: i64,
    pub payout_after_fee_cents: i64,
    pub hypercore_cost_cents: i64,
    pub net_proceeds_cents: i64,
    pub profit_cents: i64,
    pub return_on_cost_percent_cents: Option<i64>,
    pub break_even_offer_price_cents: i64,
    pub break_even_node_price_cents: i64,
    pub minimum_offer_for_target_profit_cents: i64,
    pub minimum_node_price_for_target_profit_cents: i64,
    pub maximum_hypercore_unit_cost_cents: Option<i64>,
    pub premium_over_jita_percent_cents: Option<i64>,
    pub premium_over_local_percent_cents: Option<i64>,
}

#[derive(Debug, Serialize)]
pub struct SeededScenarioOutput {
    pub seller_win_probability_percent_cents: i64,
    pub external_win_probability_percent_cents: i64,
    pub seller_node_spend_cents: i64,
    pub cash_result_if_external_wins_cents: i64,
    pub cash_result_if_seller_wins_cents: i64,
    pub seller_wins_item_retained: bool,
    pub seller_win_mark_to_cost_result_cents: i64,
    pub seller_win_mark_to_jita_result_cents: Option<i64>,
    pub expected_monetary_result_cents: i64,
    pub maximum_possible_loss_cents: i64,
    pub capital_tied_up_cents: i64,
    pub genuinely_profitable: bool,
}

#[derive(Debug, Serialize)]
pub struct ProgressOutput {
    pub first_organic_node_at: Option<String>,
    pub hours_to_first_organic_node: Option<f64>,
    pub organic_nodes_per_hour: Option<f64>,
    pub estimated_hours_to_completion: Option<f64>,
}

fn checked_i64(value: i128, label: &str) -> Result<i64, String> {
    i64::try_from(value).map_err(|_| format!("{label} exceeds the supported range"))
}

fn round_ratio(numerator: i128, denominator: i128) -> Result<i128, String> {
    if denominator <= 0 {
        return Err("rounding denominator must be positive".to_string());
    }
    if numerator >= 0 {
        Ok((numerator + denominator / 2) / denominator)
    } else {
        Ok(-((-numerator + denominator / 2) / denominator))
    }
}

fn rounded_i64(numerator: i128, denominator: i128, label: &str) -> Result<i64, String> {
    checked_i64(round_ratio(numerator, denominator)?, label)
}

fn percent_cents(numerator: i64, denominator: i64, label: &str) -> Result<Option<i64>, String> {
    if denominator == 0 {
        return Ok(None);
    }
    rounded_i64(i128::from(numerator) * 10_000, i128::from(denominator), label).map(Some)
}

fn offer_financials(input: &OfferInput) -> Result<FinancialOutput, String> {
    if input.total_nodes <= 0 {
        return Err("total_nodes must be greater than zero".to_string());
    }
    if input.hypercores_required < 0 {
        return Err("hypercores_required cannot be negative".to_string());
    }
    let gross = input.total_offer_price_cents;
    let cores = checked_i64(
        i128::from(input.hypercores_required) * i128::from(input.hypercore_unit_cost_cents),
        "hypercore cost",
    )?;
    let node_price = rounded_i64(i128::from(gross), i128::from(input.total_nodes), "node price")?;
    let completion_fee = rounded_i64(i128::from(gross) * 5, 100, "completion fee")?;
    let payout = gross - completion_fee;
    let net = payout - cores;
    let profit = net - input.acquisition_cost_cents;
    let break_even = rounded_i64(
        (i128::from(input.acquisition_cost_cents) + i128::from(cores)) * 100,
        95,
        "break-even offer",
    )?;
    let minimum_target = rounded_i64(
        (i128::from(input.acquisition_cost_cents)
            + i128::from(input.desired_profit_cents)
            + i128::from(cores)) * 100,
        95,
        "target offer",
    )?;
    let maximum_core = if input.hypercores_required == 0 {
        None
    } else {
        Some(rounded_i64(
            i128::from(gross) * 95
                - i128::from(input.acquisition_cost_cents) * 100
                - i128::from(input.desired_profit_cents) * 100,
            i128::from(input.hypercores_required) * 100,
            "maximum hypercore unit cost",
        )?)
    };
    let premium = |value: Option<i64>, label: &str| -> Result<Option<i64>, String> {
        match value {
            Some(value) if value != 0 => percent_cents(gross - value, value, label),
            _ => Ok(None),
        }
    };
    Ok(FinancialOutput {
        node_price_cents: node_price,
        gross_offer_value_cents: gross,
        completion_fee_cents: completion_fee,
        payout_after_fee_cents: payout,
        hypercore_cost_cents: cores,
        net_proceeds_cents: net,
        profit_cents: profit,
        return_on_cost_percent_cents: percent_cents(profit, input.acquisition_cost_cents, "return on cost")?,
        break_even_offer_price_cents: break_even,
        break_even_node_price_cents: rounded_i64(i128::from(break_even), i128::from(input.total_nodes), "break-even node price")?,
        minimum_offer_for_target_profit_cents: minimum_target,
        minimum_node_price_for_target_profit_cents: rounded_i64(i128::from(minimum_target), i128::from(input.total_nodes), "target node price")?,
        maximum_hypercore_unit_cost_cents: maximum_core,
        premium_over_jita_percent_cents: premium(input.jita_sell_cents, "Jita premium")?,
        premium_over_local_percent_cents: premium(input.local_sell_cents, "local premium")?,
    })
}

fn seeded_scenario(input: &OfferInput, financials: &FinancialOutput) -> Result<SeededScenarioOutput, String> {
    if input.seller_owned_nodes < 0 || input.seller_owned_nodes > input.total_nodes {
        return Err("seller_owned_nodes must be between zero and total_nodes".to_string());
    }
    let seeded_spend = checked_i64(
        i128::from(input.seller_owned_nodes) * i128::from(financials.node_price_cents),
        "seller node spend",
    )?;
    let external_result = financials.payout_after_fee_cents
        - financials.hypercore_cost_cents
        - seeded_spend
        - input.acquisition_cost_cents;
    let seller_cash = financials.payout_after_fee_cents - financials.hypercore_cost_cents - seeded_spend;
    let mark_to_cost = seller_cash;
    let mark_to_jita = input
        .jita_sell_cents
        .map(|jita| seller_cash + jita - input.acquisition_cost_cents);
    let retained_result = mark_to_jita.unwrap_or(mark_to_cost);
    let expected = rounded_i64(
        i128::from(input.total_nodes - input.seller_owned_nodes) * i128::from(external_result)
            + i128::from(input.seller_owned_nodes) * i128::from(retained_result),
        i128::from(input.total_nodes),
        "expected result",
    )?;
    let worst = external_result.min(retained_result);
    Ok(SeededScenarioOutput {
        seller_win_probability_percent_cents: rounded_i64(
            i128::from(input.seller_owned_nodes) * 10_000,
            i128::from(input.total_nodes),
            "seller probability",
        )?,
        external_win_probability_percent_cents: rounded_i64(
            i128::from(input.total_nodes - input.seller_owned_nodes) * 10_000,
            i128::from(input.total_nodes),
            "external probability",
        )?,
        seller_node_spend_cents: seeded_spend,
        cash_result_if_external_wins_cents: external_result,
        cash_result_if_seller_wins_cents: seller_cash,
        seller_wins_item_retained: true,
        seller_win_mark_to_cost_result_cents: mark_to_cost,
        seller_win_mark_to_jita_result_cents: mark_to_jita,
        expected_monetary_result_cents: expected,
        maximum_possible_loss_cents: (-worst).max(0),
        capital_tied_up_cents: input.acquisition_cost_cents + financials.hypercore_cost_cents + seeded_spend,
        genuinely_profitable: expected > 0,
    })
}

fn progress(input: &OfferInput) -> Result<ProgressOutput, String> {
    let Some(created_text) = input.created_at.as_ref() else {
        return Ok(ProgressOutput {
            first_organic_node_at: None,
            hours_to_first_organic_node: None,
            organic_nodes_per_hour: None,
            estimated_hours_to_completion: None,
        });
    };
    let created = DateTime::parse_from_rfc3339(created_text)
        .map_err(|error| format!("invalid created_at: {error}"))?;
    let mut rows: Vec<(DateTime<chrono::FixedOffset>, &ProgressSnapshotInput)> = input
        .snapshots
        .iter()
        .map(|row| {
            DateTime::parse_from_rfc3339(&row.captured_at)
                .map(|stamp| (stamp, row))
                .map_err(|error| format!("invalid snapshot captured_at: {error}"))
        })
        .collect::<Result<_, _>>()?;
    rows.sort_by_key(|(stamp, row)| (*stamp, row.id));
    let first = rows
        .iter()
        .find(|(_, row)| row.nodes_sold - row.seller_owned_nodes > 0);
    let hours_to_first = first.map(|(stamp, _)| (*stamp - created).num_milliseconds() as f64 / 3_600_000.0);
    let latest = rows.last();
    let (organic_per_hour, trajectory) = if let Some((stamp, row)) = latest {
        let elapsed = (*stamp - created).num_milliseconds() as f64 / 3_600_000.0;
        if elapsed > 0.0 {
            let organic = (row.nodes_sold - row.seller_owned_nodes).max(0) as f64;
            let rate = organic / elapsed;
            let remaining = (input.total_nodes - row.nodes_sold).max(0) as f64;
            (Some(rate), if rate > 0.0 { Some(remaining / rate) } else { None })
        } else {
            (None, None)
        }
    } else {
        (None, None)
    };
    Ok(ProgressOutput {
        first_organic_node_at: first.map(|(_, row)| row.captured_at.clone()),
        hours_to_first_organic_node: hours_to_first,
        organic_nodes_per_hour: organic_per_hour,
        estimated_hours_to_completion: trajectory,
    })
}

fn evaluate_offer(input: OfferInput) -> Result<Value, String> {
    let financials = offer_financials(&input)?;
    let scenario = seeded_scenario(&input, &financials)?;
    let progress = progress(&input)?;
    serde_json::to_value(OfferOutput {
        schema_version: SCHEMA_VERSION,
        financials,
        seeded_scenario: scenario,
        progress,
    })
    .map_err(|error| error.to_string())
}

fn evaluate_participation(input: ParticipationInput) -> Result<Value, String> {
    if input.total_nodes <= 0 || input.nodes_purchased < 0 || input.nodes_purchased > input.total_nodes {
        return Err("participation nodes must be within the total node count".to_string());
    }
    let spent = checked_i64(
        i128::from(input.nodes_purchased) * i128::from(input.node_price_cents),
        "participation spend",
    )?;
    let (item_value, profit_loss) = match input.outcome.as_str() {
        "pending" => (None, None),
        "won" => {
            let value = input.item_value_at_completion_cents.ok_or_else(|| "won participation requires item value".to_string())?;
            (Some(value), Some(value - spent))
        }
        "lost" => (None, Some(-spent)),
        "cancelled" => (None, Some(0)),
        _ => return Err("unsupported participation outcome".to_string()),
    };
    Ok(json!({
        "schema_version": SCHEMA_VERSION,
        "win_probability_percent_ten_thousandths": rounded_i64(i128::from(input.nodes_purchased) * 1_000_000, i128::from(input.total_nodes), "win probability")?,
        "total_spent_cents": spent,
        "item_value_at_completion_cents": item_value,
        "profit_loss_cents": profit_loss,
    }))
}

fn evaluate_reconciliation(input: ReconciliationInput) -> Result<Value, String> {
    if input.total_nodes <= 0 || input.seller_owned_nodes < 0 || input.seller_owned_nodes > input.total_nodes {
        return Err("reconciliation node counts are invalid".to_string());
    }
    let cores = input.actual_hypercore_cost_cents.unwrap_or(checked_i64(
        i128::from(input.hypercores_required) * i128::from(input.hypercore_unit_cost_cents),
        "actual hypercore cost",
    )?);
    let seeded_spend = rounded_i64(
        i128::from(input.seller_owned_nodes) * i128::from(input.total_offer_price_cents),
        i128::from(input.total_nodes),
        "seeded spend",
    )?;
    let (profit, item_outcome) = if let Some(profit) = input.final_profit_cents {
        (Some(profit), if input.status == "completed" { if input.winner == "external" { "transferred" } else { "retained" } } else if input.status == "expired" { "retained" } else { "unresolved" })
    } else if input.status == "completed" {
        let payout = input.payout_cents.unwrap_or(0);
        let result = if input.winner == "external" {
            payout - cores - seeded_spend - input.acquisition_cost_cents
        } else {
            payout - cores - seeded_spend + input.final_market_value_cents.unwrap_or(input.acquisition_cost_cents) - input.acquisition_cost_cents
        };
        (Some(result), if input.winner == "external" { "transferred" } else { "retained" })
    } else if input.status == "expired" {
        (Some(-cores), "retained")
    } else {
        (None, "unresolved")
    };
    Ok(json!({
        "schema_version": SCHEMA_VERSION,
        "actual_hypercore_cost_cents": cores,
        "seeded_spend_cents": seeded_spend,
        "final_profit_cents": profit,
        "item_outcome": item_outcome,
    }))
}

pub fn evaluate_hypernet_economics(input: HyperNetEconomicsInput) -> Result<Value, String> {
    if input.schema_version != SCHEMA_VERSION {
        return Err(format!("unsupported HyperNet economics schema: {}", input.schema_version));
    }
    match input.operation.as_str() {
        "offer" => evaluate_offer(input.offer.ok_or_else(|| "offer payload is required".to_string())?),
        "participation" => evaluate_participation(input.participation.ok_or_else(|| "participation payload is required".to_string())?),
        "reconciliation" => evaluate_reconciliation(input.reconciliation.ok_or_else(|| "reconciliation payload is required".to_string())?),
        _ => Err(format!("unsupported HyperNet economics operation: {}", input.operation)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn marshal_offer() -> OfferInput {
        OfferInput {
            total_offer_price_cents: 1_200_000_000_000,
            total_nodes: 8,
            seller_owned_nodes: 2,
            hypercores_required: 16,
            hypercore_unit_cost_cents: 500_000_000,
            acquisition_cost_cents: 900_000_000_000,
            desired_profit_cents: 100_000_000_000,
            jita_sell_cents: Some(950_000_000_000),
            local_sell_cents: None,
            created_at: Some("2026-08-03T12:00:00+00:00".to_string()),
            snapshots: vec![
                ProgressSnapshotInput { id: 1, captured_at: "2026-08-03T12:00:00+00:00".to_string(), nodes_sold: 0, seller_owned_nodes: 0 },
                ProgressSnapshotInput { id: 2, captured_at: "2026-08-03T14:00:00+00:00".to_string(), nodes_sold: 1, seller_owned_nodes: 1 },
                ProgressSnapshotInput { id: 3, captured_at: "2026-08-03T16:00:00+00:00".to_string(), nodes_sold: 2, seller_owned_nodes: 1 },
            ],
        }
    }

    #[test]
    fn offer_matches_existing_marshal_economics() {
        let input = marshal_offer();
        let financials = offer_financials(&input).unwrap();
        assert_eq!(financials.node_price_cents, 150_000_000_000);
        assert_eq!(financials.completion_fee_cents, 60_000_000_000);
        assert_eq!(financials.hypercore_cost_cents, 8_000_000_000);
        assert_eq!(financials.profit_cents, 232_000_000_000);
        assert_eq!(financials.break_even_offer_price_cents, 955_789_473_684);
        assert_eq!(financials.minimum_offer_for_target_profit_cents, 1_061_052_631_579);
        let scenario = seeded_scenario(&input, &financials).unwrap();
        assert_eq!(scenario.seller_win_probability_percent_cents, 2_500);
        assert_eq!(scenario.cash_result_if_external_wins_cents, -68_000_000_000);
        assert_eq!(scenario.seller_win_mark_to_jita_result_cents, Some(882_000_000_000));
        let progress = progress(&input).unwrap();
        assert_eq!(progress.hours_to_first_organic_node, Some(4.0));
        assert_eq!(progress.organic_nodes_per_hour, Some(0.25));
        assert_eq!(progress.estimated_hours_to_completion, Some(24.0));
    }

    #[test]
    fn participation_and_reconciliation_are_exact() {
        let participation = evaluate_participation(ParticipationInput {
            total_nodes: 8,
            nodes_purchased: 2,
            node_price_cents: 5_000_000_000,
            outcome: "won".to_string(),
            item_value_at_completion_cents: Some(150_000_000_000),
        }).unwrap();
        assert_eq!(participation["total_spent_cents"], 10_000_000_000_i64);
        assert_eq!(participation["profit_loss_cents"], 140_000_000_000_i64);

        let reconciliation = evaluate_reconciliation(ReconciliationInput {
            status: "completed".to_string(), winner: "external".to_string(),
            total_offer_price_cents: 1_200_000_000_000, total_nodes: 8, seller_owned_nodes: 2,
            hypercores_required: 16, hypercore_unit_cost_cents: 500_000_000,
            acquisition_cost_cents: 900_000_000_000, actual_hypercore_cost_cents: None,
            payout_cents: Some(1_140_000_000_000), final_market_value_cents: None,
            final_profit_cents: None,
        }).unwrap();
        assert_eq!(reconciliation["seeded_spend_cents"], 300_000_000_000_i64);
        assert_eq!(reconciliation["final_profit_cents"], -68_000_000_000_i64);
    }
}
