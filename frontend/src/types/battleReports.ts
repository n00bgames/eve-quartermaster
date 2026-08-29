export type BattleReportPilot = {
  character_id: number;
  name: string;
  corporation_id?: number | null;
};

export type BattleReportContext = {
  enabled: boolean;
  pilots: BattleReportPilot[];
  can_sync: boolean;
  default_gap_minutes: number;
  coverage_notice: string;
};

export type BattleReportHistoryEntry = {
  seed_killmail_id: number;
  start_time: string;
  end_time: string;
  pilot_killmail_count: number;
  systems: { system_id: number; system_name: string }[];
};

export type BattleReportHistoryPayload = {
  pilot: Pick<BattleReportPilot, "character_id" | "name">;
  reports: BattleReportHistoryEntry[];
  total_reports: number;
  coverage: { warning: string; grouping_gap_minutes: number };
};

export type BattleReportTeam = {
  side: number;
  label: string;
  pilot_count: number;
  corporation_count: number;
  alliance_count: number;
  ships_lost: number;
  isk_lost: number;
  unknown_value_losses: number;
  damage_inflicted: number;
  efficiency?: number | null;
  organizations: { organization_type?: "corporation" | "alliance"; organization_id?: number; name: string; pilot_count: number }[];
};

export type BattleReportParticipant = {
  character_id: number;
  character_name: string;
  corporation_id?: number | null;
  corporation_name?: string | null;
  alliance_id?: number | null;
  alliance_name?: string | null;
  side: number;
  ship_type_names: string[];
  ships?: { type_id: number; type_name: string; ship_group_id?: number | null; ship_group_name?: string | null }[];
  damage_done: number;
  damage_taken: number;
  killmail_participations: number;
  final_blows: number;
  losses: number;
  loss_value: number;
};

export type BattleReportTimelineEntry = {
  killmail_id: number;
  killmail_time: string;
  system_id: number;
  system_name: string;
  victim_name: string;
  victim_character_id?: number | null;
  victim_corporation_id?: number | null;
  victim_corporation_name?: string | null;
  victim_alliance_id?: number | null;
  victim_alliance_name?: string | null;
  victim_ship_type_id?: number | null;
  victim_ship_type_name: string;
  victim_side: number;
  damage_taken: number;
  estimated_total_value?: number | null;
  attacker_count: number;
  zkill_url: string;
};

export type BattleReportComposition = {
  side: number;
  ship_type_id: number;
  ship_type_name: string;
  ship_group_id?: number | null;
  ship_group_name?: string | null;
  pilots: number;
  involved: number;
  lost: number;
  loss_value: number;
};

export type BattleReport = {
  seed_killmail_id: number;
  side_overrides: Record<string, number>;
  organization_overrides: { organization_type: "alliance" | "corporation"; organization_id: number; side: number }[];
  start_time: string;
  end_time: string;
  duration_seconds: number;
  gap_minutes: number;
  systems: { system_id: number; system_name: string; security_status?: number | null; region_name?: string | null }[];
  regions: string[];
  killmail_count: number;
  pilot_count: number;
  estimated_total_value: number;
  unknown_value_killmails: number;
  teams: BattleReportTeam[];
  participants: BattleReportParticipant[];
  timeline: BattleReportTimelineEntry[];
  composition: BattleReportComposition[];
};

export type BattleReportPayload = {
  pilot: Pick<BattleReportPilot, "character_id" | "name">;
  report: BattleReport | null;
  coverage: {
    warning: string;
    canonical_source: string;
    discovery_source: string;
    grouping_rule?: string;
    generated_at_utc?: string;
  };
  engine_requested?: string;
  engine_used?: string;
  engine_shadow_match?: boolean | null;
  engine_fallback_reason?: string | null;
};

export type BattleReportShare = {
  id: number;
  share_token: string;
  share_url: string;
  selected_character_id: number;
  selected_character_name: string;
  view_count: number;
  created_at?: string | null;
  last_viewed_at?: string | null;
  revoked_at?: string | null;
};

export type PublicBattleReportPayload = BattleReportPayload & {
  share: {
    selected_character_name: string;
    created_at?: string | null;
    view_count: number;
  };
};
