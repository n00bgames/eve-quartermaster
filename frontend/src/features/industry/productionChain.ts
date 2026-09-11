import type { PlanetarySchematic, PlanetarySchematicMaterial } from "../../types/planetaryIndustry.ts";

// Tier is recipe depth: raw resources have no producing schematic.
export function productionChain(recipes: PlanetarySchematic[], target: PlanetarySchematic | undefined, feedTier: number | null) {
  const byOutput = new Map(recipes.map(r => [r.output.type_id, r]));
  const tiers = new Map<number, number>();
  function tier(id: number, active = new Set<number>()): number {
    if (tiers.has(id)) return tiers.get(id)!;
    if (active.has(id) || active.size > 8) throw Error("The recipe catalog contains a cycle.");
    const next = new Set(active).add(id);
    const r = byOutput.get(id);
    const value = r ? 1 + Math.max(...r.inputs.map(i => tier(i.type_id, next))) : 0;
    tiers.set(id, value); return value;
  }
  if (!target) return { tier: 0, inputs: [] as PlanetarySchematicMaterial[], stages: [] as PlanetarySchematic[] };
  const targetTier = tier(target.output.type_id);
  if (feedTier === null) return { tier: targetTier, inputs: target.inputs, stages: [target] };
  const cutoff = feedTier;
  const inputs = new Map<number, PlanetarySchematicMaterial>();
  const stages = new Map<number, PlanetarySchematic>();
  function visit(material: PlanetarySchematicMaterial) {
    const r = byOutput.get(material.type_id);
    if (tier(material.type_id) <= cutoff || !r) { inputs.set(material.type_id, material); return; }
    if (stages.has(r.id)) return;
    stages.set(r.id, r); r.inputs.forEach(visit);
  }
  visit(target.output);
  return { tier: targetTier, inputs: [...inputs.values()].sort((a,b) => a.name.localeCompare(b.name)),
    stages: [...stages.values()].sort((a,b) => tier(a.output.type_id) - tier(b.output.type_id) || a.output.name.localeCompare(b.output.name)) };
}
