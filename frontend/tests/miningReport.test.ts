import assert from "node:assert/strict";
import test from "node:test";
import { allMiningHistory, buildMiningReport, buildMiningReportExport, sameMiningScope } from "../src/features/mining/miningReport.ts";
import type { MiningLedgerPayload, MiningRollupRow } from "../src/types/mining.ts";

const stamp = new Date("2026-11-19T18:00:00Z");
const loadedAt = "2026-11-19T17:59:00Z";
function row(name: string, id: number | string = 1): MiningRollupRow {
  return { id, name, quantity: 120, residue_quantity: 7, volume: 123.4567, residue_volume: 8.75,
    gross_volume: 132.2067, estimated_price: 456789.12345, estimated_residue_price: 21.5,
    gross_value: 456810.62345, efficiency: 93.38 };
}
function fixture(): MiningLedgerPayload {
  return {
    characters: [{ character_id: 1001, name: "Demo Miner", can_sync: true, sync_opt_out: false },
      { character_id: 1002, name: "Other Roster Pilot", can_sync: false, sync_opt_out: false }],
    systems: [[30000142, "Demo System"]],
    operations: [{ id: 5, name: "Demo operation", notes: "DO NOT EXPORT OPERATION NOTES" }] as MiningLedgerPayload["operations"],
    analytics: { totals: { ...row("ignored"), gross_quantity: 127, measured_volume: 42.125 },
      by_day: Array.from({ length: 40 }, (_, i) => row(new Date(Date.UTC(2026, 9, 1+i)).toISOString().slice(0, 10), i)),
      by_ore: Array.from({ length: 14 }, (_, i) => row(`Demo Ore ${i}`, i)),
      by_character: [row("Demo Miner")], by_system: [row("Demo System", 30000142)] },
    entries: [{ private_data: "DO NOT EXPORT RAW ROW" }] as unknown as MiningLedgerPayload["entries"],
    entry_count: 700, page: 3, page_size: 100,
  };
}
function csv(text: string): string[][] {
  const rows: string[][] = []; let row: string[] = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') { if (quoted && text[i + 1] === '"') { cell += '"'; i++; } else quoted = !quoted; }
    else if (c === ',' && !quoted) { row.push(cell); cell = ""; }
    else if (c === '\r' && !quoted && text[i + 1] === '\n') { row.push(cell); rows.push(row); row = []; cell = ""; i++; }
    else cell += c;
  }
  return rows;
}

test("report retains the full filtered analytics beyond chart and page limits without rounding", () => {
  const data = fixture(), before = JSON.stringify(data);
  const report = buildMiningReport(data, allMiningHistory, loadedAt, stamp);
  assert.equal(report.schema_version, "eqm.mining-report.v1");
  assert.equal(report.coverage.matching_ledger_rows, 700);
  assert.equal(report.by_day.length, 40);
  assert.equal(report.by_ore.length, 14);
  assert.equal(report.totals.recovered_volume_m3, 123.4567);
  assert.equal(report.totals.estimated_recovered_isk, 456789.12345);
  assert.equal(report.totals.measured_gross_volume_m3, 42.125);
  assert.equal(report.loaded_from_eqm_at_utc, loadedAt);
  assert.equal(report.exported_at_utc, stamp.toISOString());
  assert.equal(JSON.stringify(data), before);
});

test("applied inclusive dates and composed character/system/operation filters retain labels", () => {
  const scope = { character_id: "1001", system_id: "30000142", operation_id: "5", date_from: "2026-11-17", date_to: "2026-11-19" };
  const report = buildMiningReport(fixture(), scope, loadedAt, stamp);
  assert.equal(report.scope.character_id, 1001);
  assert.equal(report.scope.character_name, "Demo Miner");
  assert.equal(report.scope.system_name, "Demo System");
  assert.equal(report.scope.operation_name, "Demo operation");
  assert.equal(report.scope.date_from, "2026-11-17");
  assert.match(report.scope.date_basis, /inclusive/);
  assert(sameMiningScope(scope, { ...scope }));
  for (const key of Object.keys(scope) as (keyof typeof scope)[]) {
    assert(!sameMiningScope(scope, { ...scope, [key]: "different" }));
  }
  assert.equal(buildMiningReportExport(report, "json").filename, "mining-report-2026-11-17_to_2026-11-19-2026-11-19T18-00-00Z.json");
});

test("exports whitelist report content and omit unrelated operations, rosters, entries and unknown fields", () => {
  const data = fixture() as MiningLedgerPayload & { token: string };
  data.token = "DO NOT EXPORT TOKEN";
  Object.assign(data.analytics.by_ore[0], { private_note: "DO NOT EXPORT ROW NOTE" });
  const report = buildMiningReport(data, allMiningHistory, loadedAt, stamp);
  for (const format of ["csv", "json"] as const) {
    const text = buildMiningReportExport(report, format).text;
    assert(!text.includes("DO NOT EXPORT"));
    assert(!text.includes("Other Roster Pilot"));
    assert(!text.includes("Demo operation"));
  }
});

test("CSV has sectioned complete rollups, stable columns, numeric precision and safe text cells", () => {
  const data = fixture();
  data.analytics.by_ore[0].name = 'Ore, "Special"\nGrade';
  data.analytics.by_character[0].name = '  =HYPERLINK("example")';
  data.analytics.by_ore[1].efficiency = null;
  const report = buildMiningReport(data, allMiningHistory, loadedAt, stamp);
  const file = buildMiningReportExport(report, "csv");
  assert(file.text.startsWith("\uFEFF"));
  const [header, ...rows] = csv(file.text.slice(1));
  assert.equal(rows.length, 1+40+14+1+1);
  assert(rows.every((row) => row.length === header.length));
  const cell = (r: string[], name: string) => r[header.indexOf(name)];
  assert.equal(cell(rows[0], "section"), "totals");
  assert.equal(cell(rows[0], "estimated_recovered_isk"), "456789.12345");
  assert.equal(cell(rows[0], "measured_gross_volume_m3"), "42.125");
  assert.equal(cell(rows.find((r) => cell(r, "section") === "by_ore")!, "name"), 'Ore, "Special"\nGrade');
  assert.equal(cell(rows.find((r) => cell(r, "section") === "by_character")!, "name"), '\'  =HYPERLINK("example")');
  assert.equal(cell(rows.find((r) => cell(r, "name") === "Demo Ore 1")!, "measured_efficiency_percent"), "");
  assert.equal(cell(rows[1], "measured_gross_volume_m3"), "");
});

test("unknown efficiency is distinct from zero and empty periods retain truthful metadata", () => {
  const data = fixture();
  data.analytics.totals.efficiency = null;
  data.analytics.by_character[0].efficiency = 0;
  let report = buildMiningReport(data, allMiningHistory, loadedAt, stamp);
  assert.equal(report.totals.measured_efficiency_percent, null);
  assert.equal(report.by_character[0].measured_efficiency_percent, 0);
  data.entry_count = 0;
  for (const key of ["by_day", "by_ore", "by_character", "by_system"] as const) data.analytics[key] = [];
  for (const key of Object.keys(data.analytics.totals)) if (typeof data.analytics.totals[key as keyof typeof data.analytics.totals] === "number") Object.assign(data.analytics.totals, { [key]: 0 });
  report = buildMiningReport(data, allMiningHistory, loadedAt, stamp);
  assert.equal(report.coverage.first_recorded_day, null);
  assert.equal(report.coverage.last_recorded_day, null);
  assert.equal(report.scope.date_from, null);
  assert.equal(report.scope.date_to, null);
  assert.equal(csv(buildMiningReportExport(report, "csv").text.slice(1)).length, 2);
  assert.equal(JSON.parse(buildMiningReportExport(report, "json").text).coverage.matching_ledger_rows, 0);
});
