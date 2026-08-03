export type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export type HyperNetStatus = "draft" | "active" | "awaiting_reconciliation" | "completed" | "expired" | "cancelled" | "invalid";

export type HyperNetFinancials = {
  node_price: number;
  gross_offer_value: number;
  completion_fee: number;
  payout_after_fee: number;
  hypercore_cost: number;
  net_proceeds: number;
  profit: number;
  return_on_cost_percent: number | null;
  break_even_offer_price: number;
  break_even_node_price: number;
  minimum_offer_for_target_profit: number;
  minimum_node_price_for_target_profit: number;
  maximum_hypercore_unit_cost: number | null;
  premium_over_jita_percent: number | null;
  premium_over_local_percent: number | null;
};

export type HyperNetScenario = {
  seller_win_probability_percent: number;
  external_win_probability_percent: number;
  seller_node_spend: number;
  cash_result_if_external_wins: number;
  cash_result_if_seller_wins: number;
  seller_wins_item_retained: boolean;
  seller_win_mark_to_cost_result: number;
  seller_win_mark_to_jita_result: number | null;
  expected_monetary_result: number;
  maximum_possible_loss: number;
  capital_tied_up: number;
  genuinely_profitable: boolean;
};

export type HyperNetSnapshot = {
  id: number;
  captured_at: string;
  nodes_sold: number;
  seller_owned_nodes: number;
  organic_nodes_sold: number;
  unique_participants: number;
  jita_buy?: number | null;
  jita_sell?: number | null;
  local_buy?: number | null;
  local_sell?: number | null;
  hypercore_buy?: number | null;
  hypercore_sell?: number | null;
  note?: string | null;
  source: string;
};

export type HyperNetOffer = {
  id: number;
  status: HyperNetStatus;
  visibility: string;
  seller: { id: number; character_id?: number | null; name: string };
  item: { type_id: number; name: string; group?: string | null; category?: string | null };
  quantity: number;
  location: { id?: number | null; name: string; eve_location_id?: number | null };
  created_offer_at: string;
  expires_at: string;
  completed_at?: string | null;
  reconciled_at?: string | null;
  remaining_seconds: number;
  total_offer_price: number;
  total_nodes: number;
  nodes_sold: number;
  nodes_remaining: number;
  seller_owned_nodes: number;
  organic_nodes_sold: number;
  filled_percent: number;
  unique_participants: number;
  hypercores_required: number;
  hypercore_unit_cost: number;
  acquisition_cost: number;
  desired_profit: number;
  completion_fee?: number | null;
  payout?: number | null;
  actual_hypercore_cost?: number | null;
  final_market_value?: number | null;
  final_profit?: number | null;
  winner?: string | null;
  item_outcome: string;
  notes?: string | null;
  source: string;
  source_reference?: string | null;
  calculations: {
    financials: HyperNetFinancials;
    seeded_scenario: HyperNetScenario;
    progress: {
      first_organic_node_at?: string | null;
      hours_to_first_organic_node?: number | null;
      organic_nodes_per_hour?: number | null;
      estimated_hours_to_completion?: number | null;
    };
  };
  snapshots?: HyperNetSnapshot[];
  participants?: Array<{ id: number; character_id?: number | null; participant_name: string; nodes_owned: number; is_seller: boolean; first_seen_at: string; last_seen_at: string }>;
  updated_at: string;
};

export type HyperNetSummary = {
  active_offers: number;
  nearing_expiration: number;
  nodes_sold: number;
  total_nodes: number;
  gross_offer_value: number;
  expected_payout: number;
  hypercore_cost: number;
  estimated_net_proceeds: number;
  estimated_profit: number;
  completed_offers: number;
  expired_offers: number;
  lifetime_profit: number;
  average_profit_per_completed_offer: number | null;
  completion_rate_percent: number | null;
  average_hours_to_first_node: number | null;
  average_hours_to_completion: number | null;
  capital_tied_up: number;
  next_expiring_offer?: HyperNetOffer | null;
};

export type HyperNetMeta = {
  statuses: HyperNetStatus[];
  data_sources: Array<{ key: string; label: string; available: boolean }>;
  seller_characters: Array<{ id: number; character_id: number; name: string; portrait_url?: string | null }>;
  fee_rate: number;
  manual_only: boolean;
};

export type HyperNetTypeCandidate = { type_id: number; name: string; group?: string | null; category?: string | null };
export type HyperNetLocationCandidate = { id?: number | null; eve_location_id?: number | null; name: string; source: string };
