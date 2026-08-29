export type KillboardScope = { scope_type: "account" | "character" | "corporation" | "all"; scope_id: number; label: string };

export type KillboardSync = {
  job_id: string; status: string; target_count: number; target_index: number; current_target?: { owner_name?: string } | null;
  feed: string; page: number; lookback_days: number; discovered_count: number; imported_count: number; updated_count: number;
  skipped_count: number; failed_count: number; message?: string | null; created_at?: string | null; updated_at?: string | null; finished_at?: string | null;
};

export type KillboardSettings = { enabled: boolean; sync_period_hours: number; lookback_days: number; request_delay_seconds: number; max_pages: number };
export type KillboardContext = { enabled: boolean; settings: KillboardSettings; can_manage: boolean; scopes: KillboardScope[]; latest_sync: KillboardSync | null; sync_due: boolean; cached_killmail_count: number; coverage_notice: string };
export type RankedKillboardValue = { name: string; count: number };
export type KillboardRecent = {
  killmail_id: number; killmail_time: string; result: "kill" | "loss" | "friendly_fire"; system_name: string; region_name?: string | null;
  victim: { character_name?: string | null; corporation_name?: string | null; ship_type_name: string };
  final_blow?: { character_name?: string | null; corporation_name?: string | null; ship_type_name?: string | null } | null;
  attacker_count: number; estimated_total_value?: number | null; points?: number | null; solo?: boolean | null; npc?: boolean | null; awox?: boolean | null; zkill_url: string;
};
export type KillboardAnalytics = {
  days: number;
  engine_requested?: string | null; engine_used?: string | null; engine_shadow_match?: boolean | null; engine_fallback_reason?: string | null;
  coverage: { warning: string; record_count: number; earliest?: string | null; latest?: string | null; unknown_value_records: number };
  summary: { kills: number; losses: number; isk_destroyed: number; isk_lost: number; efficiency?: number | null; solo_kills: number; fleet_kills: number; final_blows: number; damage_done: number; damage_contribution_percent?: number | null; inactivity_days?: number | null };
  hulls: { most_used: RankedKillboardValue[]; most_killed: RankedKillboardValue[]; most_lost: RankedKillboardValue[] };
  geography: { systems: RankedKillboardValue[]; regions: RankedKillboardValue[]; security_classes: RankedKillboardValue[] };
  opponents: RankedKillboardValue[];
  streaks: { current_kind?: string | null; current: number; longest_kill: number; longest_loss: number };
  wingmates: { characters: string[]; shared_kills: number }[];
  timeline: { date: string; kills: number; losses: number; isk_destroyed: number; isk_lost: number }[];
  recent: KillboardRecent[];
};
