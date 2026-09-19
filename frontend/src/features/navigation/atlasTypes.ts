import type { NavigationSystem } from "../../types/navigation";
export type AtlasSystem = NavigationSystem & { region_id: number | null; station_count: number; agent_count: number };
export type AtlasCatalog = { systems: AtlasSystem[]; edges: [number, number][]; agent_count: number };
export type Agent = { agent_id: number; name: string; level: number; corporation_id: number; corporation_name: string;
  faction_id: number | null; division_id: number | null; division: string; agent_type_id: number | null; is_locator: boolean;
  system_id: number | null; system_name: string | null; security_status: number | null; station_name: string | null; jumps: number | null };
export type Station = { station_id: number; name: string | null; corporation_id?: number; corporation_name?: string; operation?: string };
export type AtlasDetail = { system: NavigationSystem; stations: Station[]; agents: Agent[]; links: { dotlan: string; zkill: string } };
export type Feed<T> = { data: Record<string,T> | null; observed_at: string | null; expires_at: string; stale: boolean; error: string | null };
export type Activity = { kills: Feed<{ ship_kills: number; pod_kills: number; npc_kills: number }>;
  jumps: Feed<{ ship_jumps: number }> };
export type RouteRequest = { origin: string; destination: string; requestId: number };
export type Corporation = { corporation_id: number; name: string };
export type Offer = { offer_id: number; type_id: number; name: string; quantity: number; lp_cost: number; isk_cost: number;
  ak_cost?: number; required_items: { type_id: number; name: string; quantity: number }[] };
export type Loyalty = { character_id: number; checked_at: string; observed_at: string | null;
  balances: { corporation_id: number; corporation_name: string; loyalty_points: number }[] };

export function securityColor(value?: number | null): string {
  return value == null ? "#8292a8" : value >= .45 ? "#50d5b4" : value > 0 ? "#ffb957" : "#f46c88";
}
export function activityValue(activity: Activity | null, id: number, field: "ship_kills" | "pod_kills" | "npc_kills" | "ship_jumps", wormhole = false): number | null {
  const feed = field === "ship_jumps" ? activity?.jumps : activity?.kills;
  if (!feed?.data || wormhole) return null;
  const row = feed.data[String(id)] as Record<string,number> | undefined;
  return row?.[field] ?? 0;
}
export function lpCovered(offer: Offer, balance: number | null): boolean | null {
  return balance === null ? null : balance >= offer.lp_cost;
}
