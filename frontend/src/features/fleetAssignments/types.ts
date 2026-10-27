export type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
export type FitSnapshot = { name: string; ship_name: string; ship_type_id: number; eft: string; doctrine_name: string | null; captured_at: string };
export type FleetSlot = { key: string; role: string; target_count: number; fitting: FitSnapshot };
export type FleetPilot = { id: number; name: string; character_id: number | null; resolved: boolean; slot_key: string | null; fitting: FitSnapshot | null };
export type FleetOperation = { id: number; name: string; briefing: string; status: "draft" | "published" | "archived"; revision: number; slots: FleetSlot[]; pilots: FleetPilot[]; personal_path: string };
export type FleetSummary = Pick<FleetOperation, "id" | "name" | "status">;
export type FleetPreset = { id: number; name: string; slot_count: number };
export type FleetSources = { fittings: { id: number; name: string; ship_name: string; ship_type_id: number; character_id: number; character_name: string }[]; doctrines: { id: number; name: string; fitting_ids: number[] }[]; sync_tokens: { id: number; name: string }[] };
export type PersonalFleet = { id: number; name: string; briefing: string; assignments: FleetPilot[] };
export function dropTargets(pilotId: number, selected: number[]): number[] {
  return selected.includes(pilotId) ? selected : [pilotId];
}
