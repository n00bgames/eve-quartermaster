import test from 'node:test';
import assert from 'node:assert/strict';
import {journeySteps} from '../src/features/journey/shipTimeline.ts';
import {replayFrame,visitCounts} from '../src/features/journey/replay.ts';
const at=(n:number)=>`2026-11-01T12:00:${String(n).padStart(2,'0')}Z`;
const visit=(id:number,first:number,last:number)=>({id,system_id:30000142,first_seen_at:at(first),last_seen_at:at(last),samples:3,gap_before:id===1,observed_span_seconds:last-first});
const ship=(id:number,visit_id:number,tid:number,first:number,last:number)=>({id,visit_id,system_id:30000142,ship_type_id:tid,ship_name:'Example hull',first_seen_at:at(first),last_seen_at:at(last),samples:2,gap_before:id===1});
test('hull switches add replay steps without adding system visits',()=>{
 const visits=[visit(1,0,30)];const steps=journeySteps(visits,[ship(1,1,11178,0,15),ship(2,1,12023,30,30)]);
 assert.deepEqual(steps.map(s=>s.ship?.ship_type_id),[11178,12023]);assert.deepEqual(steps.map(s=>s.visitIndex),[0,0]);
 assert.equal(visitCounts(replayFrame(visits,steps[1].visitIndex)).get(30000142),1);
});
test('old visits and recording gaps remain unknown without carrying a hull forward',()=>{
 const visits=[visit(1,0,30),visit(2,40,50)];const steps=journeySteps(visits,[ship(1,1,11178,10,15)]);
 assert.deepEqual(steps.map(s=>s.ship?.ship_type_id??null),[null,11178,null,null]);
 assert.deepEqual(steps.map(s=>s.at),[at(0),at(10),at(30),at(40)]);
 assert.equal(new Set(steps.map(s=>s.key)).size,steps.length);
 assert.deepEqual(journeySteps([],[]),[]);
});

test('location-only visits retain their last observed time without inventing a hull',()=>{
 const steps=journeySteps([visit(1,0,30)],[]);
 assert.equal(steps.length,1);assert.equal(steps[0].at,at(0));assert.equal(steps[0].last_at,at(30));assert.equal(steps[0].ship,null);
});
