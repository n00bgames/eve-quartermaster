import type { JumpFreighterKillSummary, NavigationKillmailSample } from "./killmails";

export type NavigationSystem = { system_id: number; name: string; security_status?: number | null; security_class?: string | null; security_band?: string; constellation_name?: string | null; region_name?: string | null; x?: number | null; y?: number | null; z?: number | null };

export type NavigationRouteSystem = NavigationSystem & { jump_index: number; recent_kill_count?: number | null; recent_destroyed_value?: number | null; latest_killmail_time?: string | null; risk_score?: number | null; risk_label?: string | null; sample_killmails?: NavigationKillmailSample[]; jump_activity?: JumpActivity };

export type NavigationGatecheck = { hours: number; industrial_only: boolean; total_recent_kills: number; total_destroyed_value: number; checked_systems: number; error_count: number; errors: string[] };

export type NavigationRoute = { origin: NavigationSystem; destination: NavigationSystem; jump_count: number; systems: NavigationRouteSystem[]; highsec_count: number; lowsec_count: number; nullsec_count: number; shortest_known: boolean; prefer_safer?: boolean; routing_preference?: string; avoided_system_ids?: number[]; map_context?: OperationalMapContext; gatecheck?: NavigationGatecheck; jump_activity?: { hours: number; cache?: { refreshed?: boolean; observed_at?: string | null; system_count?: number } } };

export type NavigationGatecheckRoute = NavigationRoute & { gatecheck: NavigationGatecheck };

export type JumpFreighterStation = { station_id: number; name: string; type_id?: number | null; type_name?: string | null; operation_name?: string | null; location_kind?: "station" | "structure"; cyno_guidance: { risk: string; range_km?: number | null; note: string; reference_links?: { label: string; url: string }[] } };

export type JumpActivity = { hours: number; total_jumps: number; jumps_last_hour: number; ship_kills_last_hour: number; pod_kills_last_hour: number; jumps_per_hour: number; observations: number; confidence: "none" | "low" | "medium" | "high" | string; activity_label: "quiet" | "moderate" | "active" | "very active" | string; latest_observed_at?: string | null };

export type JumpFreighterAlternate = { system: NavigationSystem; distance_ly: number; fuel_units: number; distance_to_planned_ly: number; rejoin_distance_ly?: number | null; can_rejoin: boolean; station_status: "station_available" | "red_only" | "no_station"; station_count: number; kills_24h: JumpFreighterKillSummary; jump_activity?: JumpActivity };

export type JumpFreighterJump = { jump_index: number; from_system: NavigationSystem; to_system: NavigationSystem; distance_ly: number; fuel_units: number; cyno_eligible: boolean; required_waypoint?: boolean; station_status?: "station_available" | "red_only" | "no_station"; station_count?: number; stations: JumpFreighterStation[]; industrial_kills_24h: JumpFreighterKillSummary; kills_24h?: JumpFreighterKillSummary; jump_activity?: JumpActivity; alternates: JumpFreighterAlternate[] };

export type OperationalMapSystem = NavigationSystem & { on_route?: boolean };

export type OperationalMapGate = { from_system_id: number; to_system_id: number };

export type OperationalMapContext = { gate_hops: number; truncated?: boolean; systems: OperationalMapSystem[]; stargates: OperationalMapGate[] };

export type OperationalMapRouteNode = NavigationSystem & { map_index: number; label: string; meta?: string; selected_key?: string | null; segment_label?: string | null };

export type OperationalMapAlternateNode = NavigationSystem & { alternate_key: string; from_system_id: number; label: string; meta?: string; selected?: boolean; segment_label?: string | null };

export type JumpFreighterRoute = { origin: NavigationSystem; destination: NavigationSystem; route_mode?: "automatic" | "waypoint_assisted"; requested_waypoints?: NavigationSystem[]; ship: { name: string; fuel_type_name: string; base_fuel_per_light_year: number; base_range_ly?: number; ship_class?: string }; skills: { jump_drive_calibration: number; jump_fuel_conservation: number }; max_range_ly: number; jump_count: number; total_distance_ly: number; total_fuel_units: number; station_safety?: { mode: string; label: string; applied?: boolean }; kill_filter?: { mode: string; label: string }; jump_activity?: { hours: number; cache?: { refreshed?: boolean; observed_at?: string | null; system_count?: number } }; avoided_systems?: NavigationSystem[]; jumps: JumpFreighterJump[]; map_context?: OperationalMapContext; station_cyno_guide: { station_type: string; range_km?: number | null; risk: string; note: string }[]; notes: string[] };

export type UedamaScoutStatus = { channel: string; url: string; is_live: boolean; checked: boolean; error?: string | null; source?: string | null };

export type IndustrialThreatRank = { name: string; count: number; total_value?: number };

export type IndustrialThreatAnalysis = { system: NavigationSystem; days: number; retention_days: number; refresh_hours: number; cache: { live_fetch_performed: boolean; fetched_at?: string | null; expires_at?: string | null; ttl_minutes: number }; total_industrial_kills: number; total_destroyed_value: number; latest_killmail_time?: string | null; risk_score: number; risk_label: string; top_victim_hulls: IndustrialThreatRank[]; top_time_periods: IndustrialThreatRank[]; top_attacker_corporations: IndustrialThreatRank[]; top_attacker_alliances: IndustrialThreatRank[]; most_dangerous_locations: IndustrialThreatRank[]; top_final_blow_hulls: IndustrialThreatRank[]; top_attacker_group_sizes: IndustrialThreatRank[] };

export type PvpIntelAnalysis = { system: NavigationSystem; system_jump_activity?: JumpActivity; days: number; retention_days: number; refresh_hours: number; cache: { live_fetch_performed: boolean; fetched_at?: string | null; expires_at?: string | null; ttl_minutes: number }; total_kills: number; total_destroyed_value: number; latest_killmail_time?: string | null; risk_score: number; risk_label: string; top_victim_hulls: IndustrialThreatRank[]; top_time_periods: IndustrialThreatRank[]; top_attacker_corporations: IndustrialThreatRank[]; top_attacker_alliances: IndustrialThreatRank[]; top_victim_corporations: IndustrialThreatRank[]; top_victim_alliances: IndustrialThreatRank[]; most_dangerous_locations: IndustrialThreatRank[]; top_final_blow_hulls: IndustrialThreatRank[]; top_attacker_group_sizes: IndustrialThreatRank[] };

export type LocalThreatPilot = { input_name: string; name: string; resolved: boolean; character_id?: number; security_status?: number | null; corporation_id?: number | null; corporation_name?: string | null; alliance_id?: number | null; alliance_name?: string | null; danger_score: number; danger_label: string; period_danger_score?: number; period_danger_label?: string; recent_kills: number; recent_losses: number; group_kills?: number; group_kill_percent?: number; ships_destroyed?: number; ships_lost?: number; isk_destroyed?: number; isk_lost?: number; danger_ratio?: number; gang_ratio?: number; solo_kills?: number; last_activity_at?: string | null; zkb_url?: string | null; top_loss_hulls?: IndustrialThreatRank[]; notes: string[] };

export type LocalThreatAnalysis = { generated_at: string; days: number; input_count: number; resolved_count: number; zkill_analyzed_count: number; max_pilots: number; zkill_detail_limit: number; errors: string[]; pilots: LocalThreatPilot[] };

export type LocalThreatJob = { job_id: string; status: "queued" | "running" | "cancelling" | "cancelled" | "complete" | "failed"; created_at: string; updated_at?: string | null; completed_at?: string | null; total_count: number; processed_count: number; batch: number; total_batches: number; visible_limit: number; analysis: LocalThreatAnalysis };

