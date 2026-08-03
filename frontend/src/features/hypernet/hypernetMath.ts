import type { HyperNetFinancials, HyperNetScenario } from "../../types/hypernet";

const round = (value: number) => Math.round((value + Number.EPSILON) * 100) / 100;

export type HyperNetCalculatorInput = {
  totalOfferPrice: number;
  totalNodes: number;
  hypercoresRequired: number;
  hypercoreUnitCost: number;
  acquisitionCost: number;
  desiredProfit: number;
  sellerOwnedNodes: number;
  jitaSell?: number;
  localSell?: number;
};

export function calculateHyperNet(input: HyperNetCalculatorInput): { financials: HyperNetFinancials; scenario: HyperNetScenario } {
  const nodes = Math.max(1, input.totalNodes || 1);
  const gross = Math.max(0, input.totalOfferPrice || 0);
  const coreCost = Math.max(0, input.hypercoresRequired || 0) * Math.max(0, input.hypercoreUnitCost || 0);
  const fee = gross * 0.05;
  const payout = gross - fee;
  const net = payout - coreCost;
  const profit = net - Math.max(0, input.acquisitionCost || 0);
  const breakEven = (Math.max(0, input.acquisitionCost || 0) + coreCost) / 0.95;
  const targetOffer = (Math.max(0, input.acquisitionCost || 0) + (input.desiredProfit || 0) + coreCost) / 0.95;
  const nodePrice = gross / nodes;
  const seeded = Math.min(nodes, Math.max(0, input.sellerOwnedNodes || 0));
  const sellerProbability = seeded / nodes;
  const seededSpend = seeded * nodePrice;
  const externalResult = payout - coreCost - seededSpend - Math.max(0, input.acquisitionCost || 0);
  const sellerCashResult = payout - coreCost - seededSpend;
  const markToCost = sellerCashResult;
  const markToJita = input.jitaSell == null ? null : sellerCashResult + input.jitaSell - Math.max(0, input.acquisitionCost || 0);
  const retainedValueResult = markToJita ?? markToCost;
  const expected = (1 - sellerProbability) * externalResult + sellerProbability * retainedValueResult;
  const premium = (value?: number) => value ? round(((gross - value) / value) * 100) : null;
  return {
    financials: {
      node_price: round(nodePrice), gross_offer_value: round(gross), completion_fee: round(fee), payout_after_fee: round(payout),
      hypercore_cost: round(coreCost), net_proceeds: round(net), profit: round(profit),
      return_on_cost_percent: input.acquisitionCost ? round(profit / input.acquisitionCost * 100) : null,
      break_even_offer_price: round(breakEven), break_even_node_price: round(breakEven / nodes),
      minimum_offer_for_target_profit: round(targetOffer), minimum_node_price_for_target_profit: round(targetOffer / nodes),
      maximum_hypercore_unit_cost: input.hypercoresRequired ? round((gross * 0.95 - input.acquisitionCost - input.desiredProfit) / input.hypercoresRequired) : null,
      premium_over_jita_percent: premium(input.jitaSell), premium_over_local_percent: premium(input.localSell),
    },
    scenario: {
      seller_win_probability_percent: round(sellerProbability * 100), external_win_probability_percent: round((1 - sellerProbability) * 100),
      seller_node_spend: round(seededSpend), cash_result_if_external_wins: round(externalResult), cash_result_if_seller_wins: round(sellerCashResult),
      seller_wins_item_retained: true, seller_win_mark_to_cost_result: round(markToCost), seller_win_mark_to_jita_result: markToJita == null ? null : round(markToJita),
      expected_monetary_result: round(expected), maximum_possible_loss: round(Math.max(0, -Math.min(externalResult, retainedValueResult))),
      capital_tied_up: round(input.acquisitionCost + coreCost + seededSpend), genuinely_profitable: expected > 0,
    },
  };
}
