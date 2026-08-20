export type BountySummary = {
  net_isk: number;
  tick_count: number;
  average_tick_isk: number;
  highest_tick_isk: number | null;
  highest_tick_id: string | null;
  highest_tick_pilot: string | null;
  most_recent_at: string | null;
  active_pilots: number;
  corporate_tax_isk: number | null;
  known_corporate_tax_isk: number;
  gross_isk: number | null;
  known_gross_isk: number;
  effective_tax_rate: number | null;
  tax_coverage_complete: boolean;
  tax_known_ticks: number;
  tax_unknown_ticks: number;
};

export type BountyTick = {
  tick_id: string;
  occurred_at: string;
  character_id: number;
  character_eve_id: number;
  character_name: string;
  corporation_eve_id: number | null;
  corporation_name: string | null;
  reference_ids: number[];
  source_entry_count: number;
  net_isk: number;
  corporate_tax_isk: number | null;
  gross_isk: number | null;
  tax_status: "known" | "unknown";
  effective_tax_rate: number | null;
  tax_receiver_ids: number[];
  tax_receiver_names: string[];
  system_ids: number[];
  descriptions: string[];
};

export type BountyTimelinePoint = BountySummary & { bucket_start: string };
export type BountyLeaderboardRow = BountySummary & {
  rank: number;
  character_eve_id: number;
  character_name: string;
  corporation_eve_id: number | null;
  corporation_name: string | null;
  tick_ids: string[];
  reference_ids: number[];
};

export type BountyCharacter = {
  character_eve_id: number;
  character_name: string;
  corporation_eve_id: number | null;
  corporation_name: string | null;
  wallet_synced_at: string | null;
  authorization_status: "authorized" | "missing" | "revoked" | "missing_scope";
};

export type BountyAnalyticsPayload = {
  schema_version: string;
  generated_at_utc: string;
  period: string;
  date_from_utc: string | null;
  date_to_exclusive_utc: string | null;
  grouping: "tick" | "hourly" | "daily";
  reporting_timezone: string;
  scope: string;
  summary: BountySummary;
  timeline: BountyTimelinePoint[];
  leaderboard: BountyLeaderboardRow[];
  ledger: BountyTick[];
  tick_count: number;
  page: number;
  page_size: number;
  characters: BountyCharacter[];
  corporations: { corporation_eve_id: number; corporation_name: string }[];
  definitions: { tick: string; net: string; corporate_tax: string; gross: string; isk_per_hour: string };
};

