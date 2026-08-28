import type {
  PlanetaryIndustryPayload,
  PlanetaryPin,
  PlanetarySchematic,
} from "../../types/planetaryIndustry";

export const PLANETARY_SHORTAGE_REPORT_SCHEMA = "eqm.planetary-shortage-report.v1" as const;

export type PlanetaryShortageSeverity = "critical" | "short" | "watch" | "covered";

export type PlanetaryShortageTarget = {
  type_id: number;
  name: string;
  configured_factories: number;
  configured_output_per_day: number;
};

export type PlanetaryShortageRow = {
  type_id: number;
  name: string;
  projected_inventory: number;
  configured_supply_per_day: number;
  configured_demand_per_day: number;
  net_shortfall_per_day: number;
  coverage: number | null;
  inventory_days_at_demand: number | null;
  runway_days_at_net_shortfall: number | null;
  configured_producers: number;
  configured_consumers: number;
  running_producers: number;
  starved_producers: number;
  producer_output_per_day: number | null;
  additional_processors_to_balance: number | null;
  base_components: {
    type_id: number;
    name: string;
    quantity_per_day: number;
    planet_types: string[];
  }[];
  severity: PlanetaryShortageSeverity;
};

export type PlanetaryShortageReport = {
  schema_version: typeof PLANETARY_SHORTAGE_REPORT_SCHEMA;
  generated_at: string;
  source_as_of: string;
  methodology: "configured-throughput-with-projected-inventory";
  scope: {
    target_type_id: number | null;
    target_name: string | null;
    configured_target_factories: number;
    configured_target_output_per_day: number;
    commodity_count: number;
  };
  summary: {
    critical_shortages: number;
    shortages: number;
    watch_items: number;
    covered_items: number;
  };
  commodities: PlanetaryShortageRow[];
  caveats: string[];
};

type Aggregate = {
  typeId: number;
  name: string;
  inventory: number;
  supplyPerDay: number;
  demandPerDay: number;
  producers: number;
  consumers: number;
  runningProducers: number;
  starvedProducers: number;
  producerOutputPerDay: number | null;
};

const SEVERITY_ORDER: Record<PlanetaryShortageSeverity, number> = {
  critical: 0,
  short: 1,
  watch: 2,
  covered: 3,
};

// Resource distribution matrix: https://wiki.eveuniversity.org/Planets
const PLANET_TYPES_BY_RESOURCE: Record<string, string[]> = {
  aqueousliquids: ["Barren", "Gas", "Ice", "Oceanic", "Storm", "Temperate"],
  autotrophs: ["Temperate"],
  basemetals: ["Barren", "Gas", "Lava", "Plasma", "Storm"],
  carboncompounds: ["Barren", "Oceanic", "Temperate"],
  complexorganisms: ["Oceanic", "Temperate"],
  felsicmagma: ["Lava"],
  heavymetals: ["Ice", "Lava", "Plasma"],
  ionicsolutions: ["Gas", "Storm"],
  microorganisms: ["Barren", "Ice", "Oceanic", "Temperate"],
  noblegas: ["Gas", "Ice", "Storm"],
  noblemetals: ["Barren", "Plasma"],
  noncscrystals: ["Lava", "Plasma"],
  plankticcolonies: ["Ice", "Oceanic"],
  reactivegas: ["Gas"],
  suspendedplasma: ["Lava", "Plasma", "Storm"],
};

function perDay(quantity: number, cycleTime: number) {
  return cycleTime > 0 ? quantity * 86_400 / cycleTime : 0;
}

function rounded(value: number) {
  return Math.round((value + Number.EPSILON) * 1_000_000) / 1_000_000;
}

function planetTypesFor(resourceName: string) {
  const key = resourceName.toLowerCase().replace(/[^a-z0-9]/g, "");
  return PLANET_TYPES_BY_RESOURCE[key] ?? [];
}

function rowFor(map: Map<number, Aggregate>, typeId: number, name: string) {
  const current = map.get(typeId);
  if (current) {
    if (!current.name && name) current.name = name;
    return current;
  }
  const created: Aggregate = {
    typeId,
    name,
    inventory: 0,
    supplyPerDay: 0,
    demandPerDay: 0,
    producers: 0,
    consumers: 0,
    runningProducers: 0,
    starvedProducers: 0,
    producerOutputPerDay: null,
  };
  map.set(typeId, created);
  return created;
}

function factoryStatus(pin: PlanetaryPin) {
  return pin.projected_status === "running"
    ? "running"
    : pin.projected_status === "starved"
      ? "starved"
      : null;
}

function collectDependencyTypeIds(
  targetTypeId: number,
  recipes: Map<number, PlanetarySchematic>,
) {
  const dependencyIds = new Set<number>();
  const visiting = new Set<number>();

  function visit(typeId: number) {
    if (visiting.has(typeId)) return;
    visiting.add(typeId);
    const recipe = recipes.get(typeId);
    for (const input of recipe?.inputs ?? []) {
      dependencyIds.add(input.type_id);
      visit(input.type_id);
    }
    visiting.delete(typeId);
  }

  visit(targetTypeId);
  return dependencyIds;
}

function baseComponentsFor(
  typeId: number,
  quantityPerDay: number,
  recipes: Map<number, PlanetarySchematic>,
  names: Map<number, string>,
) {
  const totals = new Map<number, { type_id: number; name: string; quantity_per_day: number; planet_types: string[] }>();

  function expand(currentTypeId: number, quantity: number, stack: Set<number>) {
    if (quantity <= 0 || stack.has(currentTypeId)) return;
    const recipe = recipes.get(currentTypeId);
    if (recipe?.inputs.length) {
      const nextStack = new Set(stack).add(currentTypeId);
      for (const input of recipe.inputs) {
        expand(
          input.type_id,
          quantity * input.quantity / recipe.output.quantity,
          nextStack,
        );
      }
      return;
    }

    const name = names.get(currentTypeId) ?? recipe?.output.name ?? `Type ${currentTypeId}`;
    const planetTypes = planetTypesFor(name);
    if (!planetTypes.length) return;
    const existing = totals.get(currentTypeId);
    if (existing) existing.quantity_per_day += quantity;
    else totals.set(currentTypeId, {
      type_id: currentTypeId,
      name,
      quantity_per_day: quantity,
      planet_types: planetTypes,
    });
  }

  expand(typeId, quantityPerDay, new Set());
  return [...totals.values()]
    .map((row) => ({ ...row, quantity_per_day: rounded(row.quantity_per_day) }))
    .sort((left, right) => left.name.localeCompare(right.name) || left.type_id - right.type_id);
}

function severityFor(coverage: number | null): PlanetaryShortageSeverity {
  if (coverage == null || coverage >= 1) return "covered";
  if (coverage < 0.5) return "critical";
  if (coverage < 0.75) return "short";
  return "watch";
}

export function availablePlanetaryShortageTargets(data: PlanetaryIndustryPayload) {
  const targets = new Map<number, PlanetaryShortageTarget>();
  for (const colony of data.colonies) {
    for (const pin of colony.pins) {
      const schematic = pin.schematic;
      if (!pin.is_factory || !schematic) continue;
      const outputPerDay = perDay(schematic.output.quantity, schematic.cycle_time);
      const existing = targets.get(schematic.output.type_id);
      if (existing) {
        existing.configured_factories += 1;
        existing.configured_output_per_day += outputPerDay;
      } else {
        targets.set(schematic.output.type_id, {
          type_id: schematic.output.type_id,
          name: schematic.output.name,
          configured_factories: 1,
          configured_output_per_day: outputPerDay,
        });
      }
    }
  }
  return [...targets.values()]
    .map((target) => ({ ...target, configured_output_per_day: rounded(target.configured_output_per_day) }))
    .sort((left, right) => left.name.localeCompare(right.name) || left.type_id - right.type_id);
}

export function buildPlanetaryShortageReport(
  data: PlanetaryIndustryPayload,
  options: { targetTypeId?: number | null; generatedAt?: Date } = {},
): PlanetaryShortageReport {
  const aggregates = new Map<number, Aggregate>();
  const recipes = new Map<number, PlanetarySchematic>();

  for (const schematic of data.schematics ?? []) {
    recipes.set(schematic.output.type_id, schematic);
  }

  for (const colony of data.colonies) {
    for (const pin of colony.pins) {
      for (const content of pin.contents) {
        rowFor(aggregates, content.type_id, content.name).inventory += content.amount;
      }

      if (pin.extractor?.product_type_id && pin.extractor.product_name) {
        const aggregate = rowFor(aggregates, pin.extractor.product_type_id, pin.extractor.product_name);
        aggregate.supplyPerDay += pin.extractor.projected_daily_output;
        aggregate.producers += 1;
        if (pin.projected_status === "active" || pin.projected_status === "running") aggregate.runningProducers += 1;
      }

      const schematic = pin.schematic;
      if (!pin.is_factory || !schematic) continue;
      if (!recipes.has(schematic.output.type_id)) recipes.set(schematic.output.type_id, schematic);
      const configuredSchematic = recipes.get(schematic.output.type_id) ?? schematic;
      const outputPerDay = perDay(configuredSchematic.output.quantity, configuredSchematic.cycle_time);
      const output = rowFor(aggregates, configuredSchematic.output.type_id, configuredSchematic.output.name);
      output.supplyPerDay += outputPerDay;
      output.producers += 1;
      output.producerOutputPerDay = outputPerDay;
      const status = factoryStatus(pin);
      if (status === "running") output.runningProducers += 1;
      if (status === "starved") output.starvedProducers += 1;

      for (const input of configuredSchematic.inputs) {
        const aggregate = rowFor(aggregates, input.type_id, input.name);
        aggregate.demandPerDay += perDay(input.quantity, configuredSchematic.cycle_time);
        aggregate.consumers += 1;
      }
    }
  }

  for (const schematic of recipes.values()) {
    const aggregate = aggregates.get(schematic.output.type_id);
    if (aggregate && aggregate.producerOutputPerDay == null) {
      aggregate.producerOutputPerDay = perDay(schematic.output.quantity, schematic.cycle_time);
    }
  }

  const targetTypeId = options.targetTypeId ?? null;
  const target = targetTypeId == null
    ? null
    : availablePlanetaryShortageTargets(data).find((row) => row.type_id === targetTypeId) ?? null;
  const includedTypeIds = targetTypeId == null
    ? new Set([...aggregates.values()].filter((row) => row.demandPerDay > 0).map((row) => row.typeId))
    : collectDependencyTypeIds(targetTypeId, recipes);
  const names = new Map([...aggregates.values()].map((row) => [row.typeId, row.name]));
  for (const schematic of recipes.values()) {
    names.set(schematic.output.type_id, schematic.output.name);
    for (const input of schematic.inputs) names.set(input.type_id, input.name);
  }

  const commodities = [...includedTypeIds]
    .map((typeId): PlanetaryShortageRow | null => {
      const aggregate = aggregates.get(typeId);
      if (!aggregate || aggregate.demandPerDay <= 0) return null;
      const coverage = aggregate.supplyPerDay / aggregate.demandPerDay;
      const netShortfall = Math.max(0, aggregate.demandPerDay - aggregate.supplyPerDay);
      const processorGap = netShortfall > 0 && aggregate.producerOutputPerDay
        ? Math.ceil(netShortfall / aggregate.producerOutputPerDay)
        : netShortfall > 0
          ? null
          : 0;
      return {
        type_id: aggregate.typeId,
        name: aggregate.name,
        projected_inventory: rounded(aggregate.inventory),
        configured_supply_per_day: rounded(aggregate.supplyPerDay),
        configured_demand_per_day: rounded(aggregate.demandPerDay),
        net_shortfall_per_day: rounded(netShortfall),
        coverage: rounded(coverage),
        inventory_days_at_demand: rounded(aggregate.inventory / aggregate.demandPerDay),
        runway_days_at_net_shortfall: netShortfall > 0
          ? rounded(aggregate.inventory / netShortfall)
          : null,
        configured_producers: aggregate.producers,
        configured_consumers: aggregate.consumers,
        running_producers: aggregate.runningProducers,
        starved_producers: aggregate.starvedProducers,
        producer_output_per_day: aggregate.producerOutputPerDay == null
          ? null
          : rounded(aggregate.producerOutputPerDay),
        additional_processors_to_balance: processorGap,
        base_components: baseComponentsFor(typeId, netShortfall, recipes, names),
        severity: severityFor(coverage),
      };
    })
    .filter((row): row is PlanetaryShortageRow => row != null)
    .sort((left, right) => (
      SEVERITY_ORDER[left.severity] - SEVERITY_ORDER[right.severity]
      || (left.coverage ?? Number.POSITIVE_INFINITY) - (right.coverage ?? Number.POSITIVE_INFINITY)
      || left.name.localeCompare(right.name)
      || left.type_id - right.type_id
    ));

  return {
    schema_version: PLANETARY_SHORTAGE_REPORT_SCHEMA,
    generated_at: (options.generatedAt ?? new Date()).toISOString(),
    source_as_of: data.as_of,
    methodology: "configured-throughput-with-projected-inventory",
    scope: {
      target_type_id: target?.type_id ?? null,
      target_name: target?.name ?? null,
      configured_target_factories: target?.configured_factories ?? 0,
      configured_target_output_per_day: target?.configured_output_per_day ?? 0,
      commodity_count: commodities.length,
    },
    summary: {
      critical_shortages: commodities.filter((row) => row.severity === "critical").length,
      shortages: commodities.filter((row) => row.severity === "short").length,
      watch_items: commodities.filter((row) => row.severity === "watch").length,
      covered_items: commodities.filter((row) => row.severity === "covered").length,
    },
    commodities,
    caveats: [
      "Configured throughput counts every configured factory at full-cycle capacity, including idle or not-yet-started factories.",
      "Projected inventory is network-wide and may be stranded on another character or planet until hauled.",
      "Manual transfers, expedited routes, and unsubmitted colony edits remain unknown until ESI publishes a newer checkpoint.",
      "Additional processor counts are throughput equivalents and do not validate a planet's CPU or powergrid fit.",
      "Planet types show where a raw resource can occur, not the density or quality of a specific planet.",
    ],
  };
}
