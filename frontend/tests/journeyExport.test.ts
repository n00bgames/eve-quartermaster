import test from 'node:test';
import assert from 'node:assert/strict';
import {makeExportPlan,matchEngagements,exportFrame,hullAt,MAX_EXPORT_VISITS,type ExportCombat} from '../src/features/journey/exportModel.ts';
import type {JourneyHistory} from '../src/features/journey/types.ts';

const at=(seconds:number)=>new Date(Date.UTC(2026,10,4,12,0,seconds)).toISOString();
const visits=[1,2,1,3].map((system_id,i)=>({id:i+1,system_id,first_seen_at:at(i*60),last_seen_at:at(i*60+30),samples:3,gap_before:i===0||i===3,observed_span_seconds:30}));
const history={character:{character_id:1,eve_id:90001,name:'Demo'},visits,systems:[1,2,3].map(system_id=>({system_id,name:`Demo ${system_id}`,x:system_id===3?null:system_id*100,z:system_id===3?null:system_id*50,region:null,security:1,visits:1,first_seen_at:at(0),last_seen_at:at(240)})),ship_segments:[{id:1,visit_id:1,system_id:1,ship_type_id:10,ship_name:'Rifter',first_seen_at:at(0),last_seen_at:at(15),samples:2,gap_before:true},{id:2,visit_id:1,system_id:1,ship_type_id:11,ship_name:'Stiletto',first_seen_at:at(20),last_seen_at:at(30),samples:2,gap_before:false}],from_at:at(0),to_at:at(240)} as JourneyHistory;
const row=(id:number,system_id:number,seconds:number,side='kill')=>({id,system_id,time:at(seconds),ship_type_id:10,ship:'Rifter',side});
const combat=(rows:ExportCombat['rows']=[]):ExportCombat=>({available:true,rows,total:rows.length,truncated:false,limit:5000});

test('combat attaches once to the correct visit, including revisits and continuous intervals',()=>{
 const rows=[row(1,1,20),row(2,1,50),row(3,1,130,'loss'),row(4,1,170),row(5,2,60),row(6,1,60),row(7,3,220),row(8,3,210),row(1,1,20)];
 assert.deepEqual(matchEngagements(history,rows).map(g=>g.map(r=>r.id)),[[1,2],[5],[3],[8]]);
 const plan=makeExportPlan(history,combat(rows),3,4,at(300));
 assert.deepEqual(plan.engagements.map(g=>g.map(r=>r.id)),[[3],[8]]);assert.equal(plan.unmatched,3);
});
test('one second per visit regardless of hull changes, with added engagement pages',()=>{
 const plain=makeExportPlan(history,combat(),1,4);assert.equal(plain.duration,8.5);
 assert.equal(plain.phases.filter(p=>p.kind==='visit').length,4);
 const rows=Array.from({length:7},(_,i)=>row(i+1,1,10+i));
 const plan=makeExportPlan(history,combat(rows),1,4);assert.equal(plan.duration,14.5);
 assert.deepEqual(plan.phases.filter(p=>p.kind==='engagement').map(p=>[p.index,p.duration,p.page]),[[0,3,0],[0,3,1]]);
});
test('camera begins and ends fitted, zooms and pans smoothly, holds during engagement',()=>{
 const plan=makeExportPlan(history,combat([row(1,1,20)]),1,4);
 assert.equal(exportFrame(plan,0).camera.scale,1);assert.equal(exportFrame(plan,plan.duration-.01).camera.scale,1);
 assert.ok(exportFrame(plan,1.5).camera.scale>1);assert.equal(exportFrame(plan,2.6).camera.scale,4);
 const engagement=plan.phases.find(p=>p.kind==='engagement')!;
 assert.deepEqual(exportFrame(plan,engagement.start).camera,exportFrame(plan,engagement.start+2.9).camera);
 const lastVisit=plan.phases.filter(p=>p.kind==='visit').at(-1)!;assert.ok(Object.values(exportFrame(plan,lastVisit.start+.9).camera).every(Number.isFinite));
});
test('hulls are observed only; gaps and old visits are never backfilled',()=>{
 const plan=makeExportPlan(history,combat(),1,4);
 assert.equal(hullAt(plan,0,at(10))?.ship_name,'Rifter');assert.equal(hullAt(plan,0,at(17)),null);
 assert.equal(hullAt(plan,0,at(25))?.ship_name,'Stiletto');assert.equal(hullAt(plan,2,at(130)),null);
});
test('rejects invalid selections, oversized clips and incomplete combat data',()=>{
 for(const [a,b] of [[0,2],[1,0],[1,5],[1.2,2]])assert.throws(()=>makeExportPlan(history,combat(),a,b));
 assert.throws(()=>makeExportPlan(history,{...combat(),truncated:true},1,4),/Combat records/);
 const large={...history,visits:Array.from({length:MAX_EXPORT_VISITS+1},(_,i)=>({...visits[0],id:i+1}))};
 assert.throws(()=>makeExportPlan(large,combat(),1,MAX_EXPORT_VISITS+1),/at most/);
 const many=Array.from({length:1200},(_,i)=>row(i+1,1,10));assert.throws(()=>makeExportPlan(history,combat(many),1,4),/ten minutes/);
});
test('combat outside the date window or with invalid timestamps is excluded',()=>{
 const rows=[row(1,1,-1),row(2,3,240),{...row(3,1,10),time:'invalid'}];
 assert.deepEqual(matchEngagements(history,rows).map(g=>g.length),[0,0,0,0]);
});
test('visits spanning selected dates show only timestamps inside that window',()=>{
 const clipped={...history,from_at:at(10),to_at:at(20)};
 const plan=makeExportPlan(clipped,combat(),1,1);
 assert.equal(plan.visits[0].first_seen_at,at(10));assert.equal(Date.parse(plan.visits[0].last_seen_at),Date.parse(at(20))-1);
});
test('unavailable combat produces a marked travel-only clip without exposing records',()=>{
 const plan=makeExportPlan(history,{...combat([row(1,1,10)]),available:false},1,4);
 assert.equal(plan.combatAvailable,false);assert.equal(plan.duration,8.5);assert.equal(plan.engagements.flat().length,0);
});
