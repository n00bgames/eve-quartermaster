import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { buildPlanetaryFacilitiesExport, buildPlanetaryFacilitiesReport } from "../src/features/industry/planetaryFacilitiesExport.ts";
import type { PlanetaryIndustryPayload } from "../src/types/planetaryIndustry.ts";

const stamp = new Date("2026-11-10T15:00:00Z");
function fixture(): PlanetaryIndustryPayload {
  return JSON.parse(readFileSync(new URL("./fixtures/planetary-facilities-input.v1.json", import.meta.url), "utf8"));
}
function csv(text: string): string[][] {
  const rows: string[][] = []; let row: string[] = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') { if (quoted && text[i + 1] === '"') { cell += '"'; i++; } else quoted = !quoted; }
    else if (c === ',' && !quoted) { row.push(cell); cell = ""; }
    else if (c === '\n' && !quoted) { row.push(cell.replace(/\r$/, "")); rows.push(row); row = []; cell = ""; }
    else cell += c;
  }
  return rows;
}

test("facilities JSON retains all buildings and topology, with independent observed/projected values", () => {
  const data = fixture(), before = JSON.stringify(data);
  const report = buildPlanetaryFacilitiesReport(data, {character:"mine",system:"Demo Pocket",planet_type:"all"}, stamp);
  assert.equal(report.schema_version, "eqm.planetary-facilities.v1");
  assert.deepEqual(report.summary, {character_count:1,colony_count:1,facility_count:6,extractor_count:1,factory_count:2,unconfigured_factory_count:1,route_count:1});
  assert.deepEqual(report.colonies[0].facilities.map(p=>p.facility_role), ["command_center","launchpad","storage","factory","factory","extractor"]);
  const factory=report.colonies[0].facilities[3];
  assert.equal(factory.observed_contents[0].amount,0);
  assert.equal(factory.contents[0].amount,20);
  assert.equal(factory.projected_status,"starved");
  assert.equal(factory.latitude,0);
  assert.equal(report.colonies[0].facilities[5].extractor?.head_count,6);
  assert.equal(report.colonies[0].facilities[5].expiry_time,"2026-11-11T12:00:00Z");
  assert.deepEqual(report.colonies[0].facilities[1].inbound_route_ids,[700]);
  assert.deepEqual(report.colonies[0].routes[0].waypoints,[102]);
  assert.match(report.colonies[0].projection.warning!,/checkpoint/);
  assert.equal(JSON.stringify(data),before);
  assert(!("sync_tokens" in report));
  assert(!JSON.stringify(report).includes("Other Pilot Planet"));
});

test("CSV emits exactly one row per facility despite multiple contents and empty processors", () => {
  const data=fixture(); data.colonies[0].planet_name='Demo, "Barren"\nI'; data.colonies[0].character_name='=HYPERLINK("example")';
  const result=buildPlanetaryFacilitiesExport(data,"csv",{character:"mine",system:"Demo Pocket",planet_type:"all"},stamp);
  assert.equal(result.filename,"planetary-facilities-2026-11-10T15-00-00Z.csv");
  assert(result.text.startsWith("\uFEFF"));
  const [header,...rows]=csv(result.text.slice(1));
  assert.equal(rows.length,6);
  assert(rows.every(row=>row.length===header.length));
  const cell=(row:string[],name:string)=>row[header.indexOf(name)];
  assert.equal(cell(rows[0],"planet_name"),'Demo, "Barren"\nI');
  assert.equal(cell(rows[0],"character_name"),'\'=HYPERLINK("example")');
  assert.equal(cell(rows[3],"configured_output_per_day"),"960");
  assert.equal(cell(rows[3],"projected_status"),"starved");
  assert.equal(JSON.parse(cell(rows[3],"projected_contents_json")).length,2);
  assert.equal(JSON.parse(cell(rows[3],"observed_contents_json"))[0].amount,0);
  assert.equal(cell(rows[4],"configured_output_per_day"),"");
  assert.equal(cell(rows[4],"recipe_inputs_json"),"[]");
  assert.equal(JSON.parse(cell(rows[5],"outbound_routes_json"))[0].route_id,700);
});

test("character/group, system and type scopes compose and unknown scopes never broaden access", () => {
  const data=fixture();
  assert.equal(buildPlanetaryFacilitiesReport(data).summary.facility_count,7);
  assert.equal(buildPlanetaryFacilitiesReport(data,{character:"corp",system:"Demo Pocket",planet_type:"barren"}).summary.facility_count,7);
  assert.equal(buildPlanetaryFacilitiesReport(data,{character:"8",system:"all",planet_type:"all"}).summary.facility_count,1);
  assert.equal(buildPlanetaryFacilitiesReport(data,{character:"mine",system:"Demo Pocket",planet_type:"lava"}).summary.facility_count,0);
  assert.equal(buildPlanetaryFacilitiesReport(data,{character:"missing",system:"all",planet_type:"all"}).summary.facility_count,0);
  const legacy=fixture(); delete legacy.character_scopes;
  assert.equal(buildPlanetaryFacilitiesReport(legacy).summary.facility_count,0);
  assert.equal(buildPlanetaryFacilitiesReport(legacy,{character:"7",system:"all",planet_type:"all"}).summary.facility_count,7);
});

test("empty exports retain CSV headers and JSON metadata without synthetic rows", () => {
  const scope={character:"mine",system:"missing",planet_type:"all"};
  const result=buildPlanetaryFacilitiesExport(fixture(),"csv",scope,stamp);
  const full=buildPlanetaryFacilitiesExport(fixture(),"csv",undefined,stamp);
  assert.equal(csv(result.text.slice(1)).length,1);
  assert.deepEqual(csv(result.text.slice(1))[0],csv(full.text.slice(1))[0]);
  const report=JSON.parse(buildPlanetaryFacilitiesExport(fixture(),"json",scope,stamp).text);
  assert.equal(report.summary.facility_count,0); assert.deepEqual(report.colonies,[]);
  assert.deepEqual(report.scope,scope); assert.equal(report.source_as_of,"2026-11-10T12:00:00Z");
});

test("catalog fallback resolves configured recipes and unavailable recipes stay unknown", () => {
  const data=fixture(); delete data.colonies[0].pins[3].schematic;
  let report=buildPlanetaryFacilitiesReport(data);
  assert.equal(report.colonies[0].facilities[3].schematic?.name,"Water");
  data.colonies[0].pins[3].schematic_id=9999;
  report=buildPlanetaryFacilitiesReport(data);
  assert.equal(report.colonies[0].facilities[3].schematic,null);
  assert.equal(report.colonies[0].facilities[3].schematic_id,9999);
});
