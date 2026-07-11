export type FittingSeed = { text: string; nonce: number };

export type FittingSimulationState = "offline" | "online" | "active" | "overheated";

export type FittingItem = { id: number; type_id: number; type_name: string; charge_type_id?: number | null; charge_type_name?: string | null; flag: string; quantity: number; simulation_state?: FittingSimulationState; slot_group: string };

export type FittingSearchType = { type_id: number; name: string; group_id?: number | null; group_name?: string | null; category_name?: string | null; volume?: number | null; published?: boolean; bucket?: FittingPickerTab };

export const FITTING_PICKER_TABS = ["Modules", "Rigs", "Ammo", "Drones", "Other"] as const;

export type FittingPickerTab = typeof FITTING_PICKER_TABS[number];

export function fittingPickerBucket(item: Pick<FittingSearchType, "name" | "group_name" | "category_name">): FittingPickerTab {
  const haystack = `${item.name} ${item.group_name ?? ""} ${item.category_name ?? ""}`.toLowerCase();
  if (haystack.includes("drone") || haystack.includes("fighter")) return "Drones";
  if (haystack.includes("rig")) return "Rigs";
  if (haystack.includes("launcher") || haystack.includes("turret") || haystack.includes("module") || haystack.includes("shield") || haystack.includes("armor") || haystack.includes("propulsion") || haystack.includes("ewar") || haystack.includes("electronic") || haystack.includes("weapon") || haystack.includes("mining laser") || haystack.includes("upgrade")) return "Modules";
  if (haystack.includes("charge") || haystack.includes("ammo") || haystack.includes("missile") || haystack.includes("frequency crystal") || haystack.includes("script") || haystack.includes("bomb")) return "Ammo";
  return "Other";
}

export type CharacterFittingRecord = { id: number; eve_fitting_id?: number | null; source_fitting_id?: number | null; source_fitting_name?: string | null; name: string; description?: string | null; ship_type_id: number; ship_type_name: string; character_id?: number | null; character_eve_id?: number | null; character_name: string; owner_user_id?: number | null; owner_display_name?: string | null; is_shared: boolean; is_draft: boolean; can_manage: boolean; last_synced_at?: string | null; updated_at?: string | null; summary: Record<string, number>; copy_text: string; items: FittingItem[] };

export type FittingSyncToken = { token_id: number; character_id: number; character_name: string; has_fitting_scope: boolean; can_sync: boolean };

export type FittingsPayload = { fittings: CharacterFittingRecord[]; sync_tokens: FittingSyncToken[]; editable_flags: string[] };

export type FittingImportResult = { fitting: CharacterFittingRecord; warnings: string[] };

export type FittingSimulationResource = { used: number; capacity?: number | null; ok: boolean; percent?: number | null };

export type FittingSimulationSlot = { key: string; label: string; used: number; capacity?: number | null; ok: boolean };

export type FittingSimulationRequirement = { source_type_id: number; source_name: string; source_kind: string; skill_type_id: number; skill_name: string; required_level: number; trained_level: number; met: boolean };

export type ResistanceProfile = { em: number; thermal: number; kinetic: number; explosive: number };

export type FittingWeaponEstimate = { item_id?: number | null; type_id?: number | null; slot_flag?: string | null; quantity?: number | null; name: string; group: string; dps: number; volley: number; charge_name?: string | null; damage_types?: ResistanceProfile; range_m?: number | null; optimal_m?: number | null; falloff_m?: number | null; missile_velocity_m_s?: number | null; missile_flight_time_s?: number | null; state?: FittingSimulationState; overheated?: boolean; velocity_m_s?: number | null; control_range_m?: number | null; repair_hps?: number | null; mining_yield?: number | null; salvage_bonus?: number | null; ecm_strength?: number | null; scramble_strength?: number | null };

export type FittingSimulationStats = {
  offense: { turret_dps: number; launcher_dps: number; drone_dps: number; total_dps: number; volley: number; damage_types?: ResistanceProfile; weapon_count: number; max_range_m?: number | null; weapons: FittingWeaponEstimate[] };
  defense: { shield_hp: number; armor_hp: number; structure_hp: number; ehp: number; shield_ehp: number; armor_ehp: number; structure_ehp: number; shield_resists: ResistanceProfile; armor_resists: ResistanceProfile; structure_resists: ResistanceProfile; shield_peak_recharge?: number | null; active_tank_hps?: number | null; shield_repair_hps?: number | null; armor_repair_hps?: number | null; structure_repair_hps?: number | null };
  mobility: { max_velocity?: number | null; warp_speed?: number | null; align_time?: number | null; signature_radius?: number | null; mass?: number | null };
  capacitor: { capacity?: number | null; recharge_time?: number | null; peak_recharge?: number | null; draw_per_second?: number | null; stable?: boolean; stable_percent?: number | null; depletion_seconds?: number | null; modules?: { name: string; gj_per_second: number; cycle_seconds: number; quantity: number }[] };
  targeting: { max_targets?: number | null; targeting_range?: number | null; scan_resolution?: number | null; sensor_strength?: number | null; drone_control_range_m?: number | null };
  notes: string[];
};

export type FittingSimulation = { fitting_id: number; character_id: number; character_name: string; dogma_loaded: boolean; dogma_effects_loaded?: boolean; heat?: boolean; status: "pass" | "warning" | "unknown"; summary: { missing_skills: number; slot_issues: number; resource_issues: number }; resources: { cpu: FittingSimulationResource; powergrid: FittingSimulationResource; calibration: FittingSimulationResource }; slots: FittingSimulationSlot[]; requirements: FittingSimulationRequirement[]; stats?: FittingSimulationStats | null; notes: string[] };