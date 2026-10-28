import type { Highlight, Pilot } from "./types";

// Account preferences affect the private view without mutating the shared snapshot.
export function markPilots(pilots: Pilot[], highlights: Highlight[] | undefined): Pilot[] {
  if (highlights === undefined) return pilots;
  const alliances = new Set(highlights.filter(h => h.kind === "alliance").map(h => h.eve_id));
  const corporations = new Set(highlights.filter(h => h.kind === "corporation").map(h => h.eve_id));
  return pilots.map(p => {
    const alliance_highlighted = p.alliance_id !== null && alliances.has(p.alliance_id);
    return {...p, alliance_highlighted, highlighted: alliance_highlighted || (p.corporation_id !== null && corporations.has(p.corporation_id))};
  });
}
