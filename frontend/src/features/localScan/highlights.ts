import type { CSSProperties } from "react";
import type { Highlight, Pilot } from "./types";

export const SCAN_COLORS = {
  red: {label: "EVE Red", hex: "#ff7d86"},
  orange: {label: "EVE Orange", hex: "#ffba66"},
  blue: {label: "EVE Blue", hex: "#78aaff"},
  light_blue: {label: "EVE Light Blue", hex: "#7cdef5"},
  green: {label: "EVE Green", hex: "#86df9c"},
  purple: {label: "EVE Purple", hex: "#d5a0ff"},
  gray: {label: "EVE Gray", hex: "#bcc8d6"},
} as const;
export type ScanColor = keyof typeof SCAN_COLORS;
export type OrganizationTarget = {kind: "corporation" | "alliance"; eve_id?: number; name: string};
export type AutomaticRule = {kind:"corporation"|"alliance";eve_id:number;color:ScanColor};
export type SaveColor = (target: OrganizationTarget, color: ScanColor | null) => Promise<void>;
export function normalizeColor(value: unknown): ScanColor {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(SCAN_COLORS, value) ? value as ScanColor : "red";
}
export function colorStyle(color: ScanColor | null): CSSProperties | undefined {
  return color ? {"--scan-mark-color": SCAN_COLORS[color].hex} as CSSProperties : undefined;
}
export function pilotColor(pilot: Pilot, alliance = false): ScanColor | null {
  const color = alliance ? pilot.alliance_highlight_color : pilot.highlight_color;
  return color ? normalizeColor(color) : (alliance ? pilot.alliance_highlighted : pilot.highlighted) ? "red" : null;
}
// Current preferences affect only the private view, never the saved snapshot.
export function markPilots(pilots: Pilot[], highlights: Highlight[] | undefined, automaticRules: AutomaticRule[] = []): Pilot[] {
  if (highlights === undefined) return pilots;
  const targets = new Map(highlights.map(h => [`${h.kind}:${h.eve_id}`, normalizeColor(h.color)]));
  const automatic = new Map(automaticRules.map(r=>[`${r.kind}:${r.eve_id}`,normalizeColor(r.color)]));
  return pilots.map(p => {
    const manualAlliance = targets.get(`alliance:${p.alliance_id}`) ?? null;
    const corporation = targets.get(`corporation:${p.corporation_id}`) ?? null;
    const alliance = manualAlliance ?? automatic.get(`alliance:${p.alliance_id}`) ?? null;
    const effective = corporation ?? manualAlliance ?? automatic.get(`corporation:${p.corporation_id}`) ?? alliance;
    return {...p, alliance_highlight_color: alliance, corporation_highlight_color: corporation,
      highlight_color: effective, alliance_highlighted: Boolean(alliance), highlighted: Boolean(effective)};
  });
}
