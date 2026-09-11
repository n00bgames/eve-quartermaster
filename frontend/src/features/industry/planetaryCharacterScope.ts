import type { PlanetaryIndustryPayload } from "../../types/planetaryIndustry.ts";

export function scopePlanetaryCharacters(data: PlanetaryIndustryPayload, selection: string): PlanetaryIndustryPayload {
  const groups = data.character_scopes ?? [];
  const group = groups.find(row => row.id === selection);
  const allowed = new Set(group?.character_ids ?? (data.characters.some(row => String(row.id) === selection) ? [Number(selection)] : []));
  const colonies = data.colonies.filter(row => allowed.has(row.character_id));
  return { ...data,
    characters: data.characters.filter(row => allowed.has(row.id)),
    sync_tokens: data.sync_tokens.filter(row => allowed.has(row.character_id)),
    colonies,
    summary: {
      colonies: colonies.length, characters: new Set(colonies.map(row => row.character_id)).size,
      expired_extractors: colonies.reduce((sum, row) => sum + row.summary.expired_extractors, 0),
      expiring_extractors: colonies.reduce((sum, row) => sum + row.summary.expiring_extractors, 0),
      starved_factories: colonies.reduce((sum, row) => sum + row.summary.starved_factories, 0),
      stored_volume: colonies.reduce((sum, row) => sum + row.summary.stored_volume, 0),
    },
  };
}
