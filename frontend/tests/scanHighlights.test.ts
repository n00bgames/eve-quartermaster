import assert from "node:assert/strict";
import test from "node:test";
import {markPilots,pilotColor,normalizeColor} from "../src/features/localScan/highlights.ts";
const pilots=[{character_id:1,name:"Pilot",corporation_id:10,corporation_name:"Corp",alliance_id:20,alliance_name:"Alliance",affiliation_available:true,highlighted:false,alliance_highlighted:false}];
test("corporation overrides alliance and removal inherits alliance; snapshots stay immutable",()=>{
  const alliance={id:1,kind:"alliance" as const,eve_id:20,name:"Alliance",color:"blue" as const};
  const corp={id:2,kind:"corporation" as const,eve_id:10,name:"Corp",color:"orange" as const};
  const result=markPilots(pilots,[alliance,corp]);
  assert.equal(pilotColor(result[0]),"orange");assert.equal(pilotColor(result[0],true),"blue");
  assert.equal(pilotColor(markPilots(pilots,[alliance])[0]),"blue");
  assert.equal(pilots[0].highlighted,false);assert.equal(pilotColor(markPilots(pilots,[])[0]),null);
});
test("legacy public snapshots remain red; invalid palette values cannot become styles",()=>{
  const legacy=[{...pilots[0],highlighted:true,alliance_highlighted:true}];
  assert.equal(markPilots(legacy,undefined),legacy);assert.equal(pilotColor(legacy[0]),"red");
  assert.equal(normalizeColor("url(evil)"),"red");assert.equal(normalizeColor("__proto__"),"red");
});

test("manual rules outrank contacts; contact corporation outranks contact alliance",()=>{
  const automatic=[{kind:"alliance" as const,eve_id:20,color:"blue" as const},{kind:"corporation" as const,eve_id:10,color:"orange" as const}];
  assert.equal(pilotColor(markPilots(pilots,[],automatic)[0]),"orange");
  const manualAlliance={id:1,kind:"alliance" as const,eve_id:20,name:"Alliance",color:"green" as const};
  assert.equal(pilotColor(markPilots(pilots,[manualAlliance],automatic)[0]),"green");
  assert.equal(pilotColor(markPilots(pilots,[],[])[0]),null);
  assert.equal(pilotColor(markPilots(pilots,[],[{kind:"corporation",eve_id:10,color:"gray"}])[0]),"gray");
});
