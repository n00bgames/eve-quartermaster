import assert from "node:assert/strict";
import test from "node:test";
import { addPlanets, buildSheet, defaultRequest, dependencyIds, hypotheticalPlanet, importScenario, removePlanet } from "../src/features/industry/piPlannerState.ts";
import type { Catalog, PlannerContext, Plan } from "../src/features/industry/piPlannerTypes.ts";

const catalog = {
  1: {type_id:1,name:"Raw",tier:0,volume:1,planet_types:["Storm"],tax_base:5,recipe:null},
  2: {type_id:2,name:"Product",tier:1,volume:1,planet_types:[],tax_base:400,recipe:{id:1,name:"Product",cycle_time:1800,output:{type_id:2,name:"Product",quantity:20,volume:1},inputs:[{type_id:1,name:"Raw",quantity:3000,volume:1}]}},
} satisfies Catalog;
const context = {as_of:"2026-09-09",catalog,pilots:[{character_id:1,name:"Pilot",ccu:null,ic:4,cce:null,skills_synced_at:null,colonies:[{id:7,planet_id:100,planet_name:"Current",planet_type:"Storm",upgrade_level:4,last_synced_at:"2026-09-09"}]}],planets:[],baseline:{colonies:1,configured_weekly_output:{},observed_inventory:{},note:"Observed"}} satisfies PlannerContext;

test("default scenario preserves colonies and does not invent skill levels",()=>{
  const r=defaultRequest(context);
  assert.deepEqual(r.pilots[0].release_colony_ids,[]);
  assert.equal(r.pilots[0].planned_ccu,null);
  assert.equal(r.sale_mode,"immediate");
});
test("scouting additions deduplicate and removing a planet removes all pilot references",()=>{
  const p=hypotheticalPlanet("Storm","p");
  const r=addPlanets(addPlanets(defaultRequest(context),[p]),[p]);
  assert.equal(r.planets.length,1);
  assert.deepEqual(r.pilots[0].planet_keys,["p"]);
  assert.deepEqual(removePlanet(r,"p").pilots[0].planet_keys,[]);
});
test("dependency graph and imported snapshots use scenario data only",()=>{
  assert.deepEqual(dependencyIds(catalog,[2,2]),[2,1]);
  const r=defaultRequest(context);
  assert.deepEqual(importScenario(JSON.stringify({schema_version:"eqm.pi-planning-snapshot.v1",request:r,snapshot:{prices:"untrusted"}})),r);
  assert.throws(()=>importScenario('{"schema_version":"future"}'));
  assert.throws(()=>importScenario("x".repeat(250001)));
});
test("CSV build sheet protects spreadsheet formulas in pilot and planet names",()=>{
  const plan={colonies:[{character_name:"=HYPERLINK(bad)",planet:{name:"+bad"},facilities:[{name:'Water "factory"',count:2}],cpu:500,power:1000,setup_isk:100,external_inputs:{1:200},outputs:{2:20}}],shopping:[]} as unknown as Plan;
  const csv=buildSheet(plan,catalog);
  assert.ok(csv.includes('"\'=HYPERLINK(bad)"'));
  assert.ok(csv.includes('"\'+bad"'));
  assert.ok(csv.includes('"Water ""factory"""'));
});
