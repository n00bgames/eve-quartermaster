import assert from "node:assert/strict";
import test from "node:test";
import {combatDossierFilename,combatDossierMarkdown} from "../src/features/intel/combatDossier.ts";
import type {IntelReport} from "../src/features/intel/types.ts";

function report():IntelReport {return {
 subject:{kind:"character",eve_id:9001,name:"Demo | Pilot <b>",public_data:{esi:{state:"available",data:{description:"PRIVATE SENTINEL"}}}},
 window:{from_at:"2026-08-20T16:38:10Z",to_at:"2026-11-18T16:38:10Z"},
 association_filters:{max_attackers:20,min_days:2,sort:"days"},
 summary:{kills:5,losses:1,utc_hours:[{hour:3,appearances:6}],associates:[{kind:"character",id:9002,name:"Wing | Mate",kills:3,distinct_days:2,estimated_engagements:2}],evidence:[{id:123,time:"2026-11-17T03:00:00Z",side:"attacker",system_id:30000001}],systems:[{name:"PRIVATE SYSTEM"}],sightings:99},
 coverage:{loaded_killmails:6,analysis_limited:false,notice:"PRIVATE NOTICE",collections:[]},definitions:{evidence:"Recent links are capped."},observations:[{payload:{text:"PRIVATE OBSERVATION"}}],notes:[{body:"PRIVATE NOTE"}],privateData:{name:"PRIVATE ACCOUNT"}
 } as unknown as IntelReport;}

test("combat dossier preserves UTC, limits, filtered associations and evidence",()=>{
 const r=report(),text=combatDossierMarkdown(r);
 assert.equal(combatDossierFilename(r),"eqm-combat-character-9001-2026-11-18.md");
 for(const expected of ["not online hours","No records does not mean inactive","common ownership","20 named attackers","2 shared UTC day","Observed PvP kills: 5","2026-11-17 03:00:00 UTC","https://zkillboard.com/kill/123/","Demo \\| Pilot \\<b\\>"])assert(text.includes(expected),expected);
 assert(!text.includes("PRIVATE"));
});

test("empty and NPC-only evidence are explicit without copying private fields",()=>{
 const r=report();r.summary.associates=[];r.summary.evidence=[];
 assert.match(combatDossierMarkdown(r),/No matching recorded co-attackers/);
 assert.match(combatDossierMarkdown(r),/No retained records in this window/);
 r.summary.evidence=[{id:124,time:"2026-11-17T03:00:00Z",side:"victim",system_id:30000001,npc_only:true}];
 assert.match(combatDossierMarkdown(r),/victim; NPC-only/);
});
