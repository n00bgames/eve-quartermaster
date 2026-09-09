import type { Catalog, PlannerContext, PlanningRequest, Plan, PlanetChoice, PlanetKind } from "./piPlannerTypes";

export function defaultRequest(context: PlannerContext): PlanningRequest {
  const product = Object.values(context.catalog).filter(x => x.recipe).sort((a, b) => a.tier - b.tier || a.name.localeCompare(b.name))[0];
  const planets = context.planets.slice(0, 60);
  return {
    schema_version: "eqm.pi-planning-input.v1", name: "My PI operation", objective: "profit",
    products: product ? [{ type_id: product.type_id, quantity: 1000 }] : [],
    pilots: context.pilots.slice(0, 12).map(p => ({ character_id: p.character_id, enabled: true, planned_ccu: null, planned_ic: null, release_colony_ids: [], planet_keys: planets.map(p => p.key) })),
    planets, sourcing: "auto", buy_type_ids: [], hub: "jita", sale_mode: "immediate",
    costs: { sales_tax_percent: 8, broker_fee_percent: 3, freight_isk_m3: 0, weekly_overhead: 0, per_colony_weekly: 0, setup_budget: 1e12, additional_setup_per_colony: 0, setup_amortization_weeks: 12 },
    schedule: { visits_per_week: 7, minutes_per_visit: 15, haul_capacity_m3: 60000, max_trips_per_visit: 4, program_hours: 24, restart_minutes: 5, link_length_km: 100 }, search_seconds: 8,
  };
}

export function hypotheticalPlanet(kind: PlanetKind, key: string): PlanetChoice {
  return { key, name: `${kind} proposal`, planet_type: kind, planet_id: null, system_id: null, diameter_km: 10000, security: .5, customs_percent: 10, npc_tax_percent: 10, yields: [] };
}

export function addPlanets(request: PlanningRequest, planets: PlanetChoice[]): PlanningRequest {
  const existing = new Set(request.planets.map(p => p.key));
  const added = planets.filter(p => !existing.has(p.key)).slice(0, 60 - request.planets.length);
  return { ...request, planets: [...request.planets, ...added], pilots: request.pilots.map(p => ({ ...p, planet_keys: [...p.planet_keys, ...added.map(p => p.key)] })) };
}

export function removePlanet(request: PlanningRequest, key: string): PlanningRequest {
  return { ...request, planets: request.planets.filter(p => p.key !== key), pilots: request.pilots.map(p => ({...p, planet_keys: p.planet_keys.filter(k => k !== key)})) };
}

export function dependencyIds(catalog: Catalog, targets: number[]): number[] {
  const ids = new Set<number>();
  const visit = (id: number) => {
    if (ids.has(id) || !catalog[id]) return;
    ids.add(id);
    catalog[id].recipe?.inputs.forEach(i => visit(i.type_id));
  };
  targets.forEach(visit);
  return [...ids];
}

export function importScenario(text: string): PlanningRequest {
  if (text.length > 250000) throw new Error("Scenario file is too large (250 KB maximum)");
  const parsed = JSON.parse(text);
  const request = parsed.schema_version === "eqm.pi-planning-snapshot.v1" ? parsed.request : parsed;
  if (request?.schema_version !== "eqm.pi-planning-input.v1" || !Array.isArray(request.products) || !Array.isArray(request.pilots) || !Array.isArray(request.planets) || !request.costs || !request.schedule) throw new Error("This is not an EQM PI scenario v1");
  // Server validation is authoritative. Check enough shape to safely render imported controls.
  if (request.products.length > 83 || request.pilots.length > 12 || request.planets.length > 60) throw new Error("Scenario exceeds planner limits");
  if (request.pilots.some((p: any) => !Number.isInteger(p.character_id) || !Array.isArray(p.planet_keys) || !Array.isArray(p.release_colony_ids)) || request.planets.some((p: any) => typeof p.key !== "string" || typeof p.planet_type !== "string" || !Array.isArray(p.yields))) throw new Error("Invalid pilot or planet records");
  return request as PlanningRequest;
}

function csv(value: string | number): string {
  const safe = typeof value === "string" && /^[=+@\-\t\r]/.test(value) ? `'${value}` : String(value);
  return `"${safe.replace(/"/g, '""')}"`;
}

export function buildSheet(plan: Plan, catalog: Catalog): string {
  const rows: (string | number)[][] = [["Pilot", "Planet", "Action", "Item", "Quantity", "CPU total", "Power total", "Setup ISK"]];
  for (const colony of plan.colonies) {
    for (const f of colony.facilities) rows.push([colony.character_name, colony.planet.name, colony.replaces_colony_id ? "Replace colony" : "Build", f.name, f.count, colony.cpu, colony.power, colony.setup_isk]);
    for (const [id, quantity] of Object.entries(colony.external_inputs)) rows.push([colony.character_name, colony.planet.name, "Inputs per week", catalog[id]?.name ?? id, quantity, "", "", ""]);
    for (const [id, quantity] of Object.entries(colony.outputs)) rows.push([colony.character_name, colony.planet.name, "Output per week", catalog[id]?.name ?? id, quantity, "", "", ""]);
  }
  for (const row of plan.shopping ?? []) rows.push(["", "Market", "Purchase per week", catalog[row.type_id]?.name ?? String(row.type_id), row.quantity, "", "", row.value]);
  return rows.map(row => row.map(csv).join(",")).join("\r\n");
}
