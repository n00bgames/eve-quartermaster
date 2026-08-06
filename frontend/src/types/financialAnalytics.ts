export type WalletPoint = { date: string; value: number };

export type WalletStatistics = {
  current: number | null;
  net_change: number;
  percentage_growth?: number | null;
  average_daily_growth: number;
  largest_gain: number;
  largest_loss: number;
  income?: number;
  spending?: number;
  spending_velocity?: number;
  median?: number | null;
  average?: number | null;
};

export type FinancialTimelineEvent = {
  id: number;
  occurred_at?: string | null;
  kind: string;
  label: string;
  amount: number;
  balance?: number | null;
  description?: string | null;
  context_id?: number | null;
  item_name?: string | null;
  quantity?: number | null;
  unit_price?: number | null;
  is_buy?: boolean | null;
};

export type PersonalWalletAnalytics = {
  character_id: number;
  character_eve_id: number;
  character_name: string;
  corporation_id?: number | null;
  corporation_name?: string | null;
  wallet_synced_at?: string | null;
  history_opt_out: boolean;
  stats: WalletStatistics;
  points: WalletPoint[];
  timeline: FinancialTimelineEvent[];
};

export type CorporationWalletAnalytics = {
  corporation_id: number;
  corporation_eve_id: number;
  corporation_name: string;
  ticker?: string | null;
  raw_totals_visible: boolean;
  tracked_characters: number;
  corporation_wallet_divisions: number;
  corporation_wallet_total: number | null;
  character_wallet_total: number | null;
  series_mode: "absolute" | "change";
  stats: WalletStatistics;
  points: WalletPoint[];
};

export type FinancialAnalytics = {
  days: number;
  personal: PersonalWalletAnalytics[];
  corporations: CorporationWalletAnalytics[];
  privacy: { individual_leaderboards_enabled: false; message: string };
};
