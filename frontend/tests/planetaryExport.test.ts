import assert from "node:assert/strict";
import test from "node:test";

import { buildPlanetaryExport } from "../src/features/industry/planetaryExport.ts";
import type { PlanetaryIndustryPayload, PlanetaryPin } from "../src/types/planetaryIndustry.ts";

function pin(overrides: Partial<PlanetaryPin> = {}): PlanetaryPin {
  return {
    pin_id: 101,
    type_id: 2256,
    type_name: "Temperate Command Center",
    status: "online",
    projected_status: "online",
    content_source: "projected",
    is_factory: false,
    is_extractor: false,
    has_inbound_route: false,
    stored_volume: 0,
    observed_stored_volume: 0,
    contents: [],
    observed_contents: [],
    projected_produced: [],
    projected_blocked: [],
    ...overrides,
  };
}

function payload(pins: PlanetaryPin[]): PlanetaryIndustryPayload {
  return {
    as_of: "2026-08-28T12:00:00+00:00",
    characters: [{ id: 7, name: "PI Pilot" }],
    sync_tokens: [],
    colonies: [{
      id: 3,
      character_id: 7,
      character_eve_id: 90000001,
      character_name: "PI Pilot",
      planet_id: 40000001,
      planet_name: "Example, Prime",
      planet_type: "temperate",
      solar_system_id: 30000001,
      solar_system_name: "Example System",
      security_status: 0.5,
      upgrade_level: 5,
      num_pins: pins.length,
      esi_last_update: "2026-08-28T11:55:00+00:00",
      last_synced_at: "2026-08-28T12:00:00+00:00",
      link_count: 0,
      route_count: 0,
      projection: {
        checkpoint_at: "2026-08-28T11:55:00+00:00",
        projected_at: "2026-08-28T12:00:00+00:00",
        is_projection: true,
        events_processed: 1,
        truncated: false,
      },
      summary: {
        extractors: 0,
        expired_extractors: 0,
        expiring_extractors: 0,
        factories: 0,
        starved_factories: 0,
        stored_volume: 0,
        observed_stored_volume: 0,
        projected_daily_output: 0,
      },
      pins,
      routes: [],
    }],
    summary: {
      colonies: 1,
      characters: 1,
      expired_extractors: 0,
      expiring_extractors: 0,
      starved_factories: 0,
      stored_volume: 0,
    },
  };
}

test("JSON export preserves complete colony and facility details", () => {
  const data = payload([pin({
    is_extractor: true,
    type_name: "Extractor Control Unit",
    extractor: {
      cycle_time: 1800,
      head_count: 10,
      product_type_id: 2268,
      product_name: "Aqueous Liquids",
      qty_per_cycle: 1200,
      cycle_count: 24,
      projected_program_output: 50_000,
      projected_daily_output: 48_000,
      projected_remaining_output: 25_000,
      projection_source: "dogma",
    },
  })]);
  const result = buildPlanetaryExport(data, "json", new Date("2026-08-28T12:34:56Z"));
  const exported = JSON.parse(result.text);

  assert.equal(result.filename, "planetary-industry-2026-08-28T12-34-56Z.json");
  assert.equal(exported.schema_version, "eqm.planetary-industry.v1");
  assert.deepEqual(exported.schematics, []);
  assert.equal(exported.summary.facility_count, 1);
  assert.equal(exported.colonies[0].pins[0].extractor.projected_remaining_output, 25_000);
});

test("CSV export keeps empty facilities and aligns projected and observed amounts", () => {
  const data = payload([
    pin(),
    pin({
      pin_id: 102,
      type_name: "Storage Facility",
      contents: [{ type_id: 2398, name: "Reactive Metals", amount: 120, volume: 0.38 }],
      observed_contents: [{ type_id: 2398, name: "Reactive Metals", amount: 100, volume: 0.38 }],
      stored_volume: 45.6,
      observed_stored_volume: 38,
    }),
  ]);
  const result = buildPlanetaryExport(data, "csv", new Date("2026-08-28T12:34:56Z"));

  assert.equal(result.facilityCount, 2);
  assert.equal(result.amountRowCount, 2);
  assert.match(result.text, /"Example, Prime"/);
  assert.match(result.text, /Reactive Metals,2398,120,100/);
  assert.match(result.text, /Temperate Command Center,2256,101,infrastructure/);
});
