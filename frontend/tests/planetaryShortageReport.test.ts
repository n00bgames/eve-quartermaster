import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  availablePlanetaryShortageTargets,
  buildPlanetaryShortageReport,
} from "../src/features/industry/planetaryShortageReport.ts";
import type { PlanetaryIndustryPayload } from "../src/types/planetaryIndustry.ts";

const fixture = JSON.parse(fs.readFileSync(
  new URL("./fixtures/planetary-shortage-input.v1.json", import.meta.url),
  "utf8",
)) as PlanetaryIndustryPayload;
const expected = JSON.parse(fs.readFileSync(
  new URL("./fixtures/planetary-shortage-report.v1.json", import.meta.url),
  "utf8",
));

test("targeted report counts an idle target factory as planned demand", () => {
  const report = buildPlanetaryShortageReport(fixture, {
    targetTypeId: 2870,
    generatedAt: new Date("2026-08-28T12:30:00Z"),
  });

  assert.deepEqual(report, expected);
  assert.equal(report.scope.configured_target_output_per_day, 24);
  const coolant = report.commodities.find((row) => row.name === "Coolant");
  assert.equal(coolant?.additional_processors_to_balance, 3);
  assert.deepEqual(coolant?.base_components, [
    { type_id: 2268, name: "Aqueous Liquids", quantity_per_day: 432000, planet_types: ["Barren", "Gas", "Ice", "Oceanic", "Storm", "Temperate"] },
    { type_id: 2309, name: "Ionic Solutions", quantity_per_day: 432000, planet_types: ["Gas", "Storm"] },
  ]);
});

test("available report targets aggregate configured capacity by commodity", () => {
  const targets = availablePlanetaryShortageTargets(fixture);

  assert.deepEqual(targets, [
    { type_id: 2393, name: "Bacteria", configured_factories: 1, configured_output_per_day: 960 },
    { type_id: 9832, name: "Coolant", configured_factories: 1, configured_output_per_day: 120 },
    { type_id: 2870, name: "Organic Mortar Applicators", configured_factories: 1, configured_output_per_day: 24 },
  ]);
});

test("network report retains covered rows but ranks shortages first", () => {
  const report = buildPlanetaryShortageReport(fixture, {
    generatedAt: new Date("2026-08-28T12:30:00Z"),
  });

  assert.deepEqual(report.commodities.map((row) => [row.name, row.severity]), [
    ["Electrolytes", "critical"],
    ["Microorganisms", "critical"],
    ["Water", "critical"],
    ["Coolant", "critical"],
    ["Bacteria", "covered"],
  ]);
});
