import test from 'node:test';
import assert from 'node:assert/strict';
import {projectSystems,replayFrame,visitCounts} from '../src/features/journey/replay.ts';

const visits=[1,2,1,3].map((system_id,i)=>({id:i+1,system_id,first_seen_at:`2026-10-31T12:0${i}:00Z`,last_seen_at:`2026-10-31T12:0${i}:30Z`,samples:3,gap_before:i===0||i===3,observed_span_seconds:30}));
test('replay reveals observations in their recorded order, including revisits and gaps',()=>{
 assert.deepEqual(replayFrame(visits,null),visits);
 assert.deepEqual(replayFrame(visits,1).map(v=>v.system_id),[1,2]);
 assert.deepEqual(replayFrame(visits,2).map(v=>v.system_id),[1,2,1]);
 assert.equal(replayFrame(visits,3)[3].gap_before,true);
 assert.equal(replayFrame([],null).length,0);
 assert.equal(replayFrame(visits,999).length,4);
 assert.equal(visitCounts(visits).get(1),2);
 assert.equal(visitCounts(replayFrame(visits,1)).get(1),1);
});
test('SDE X/Z projection preserves direction, excludes unavailable coordinates and handles one star',()=>{
 const system=(id:number,x:number|null,z:number|null)=>({system_id:id,name:`Demo ${id}`,x,z,region:null,security:1,visits:1,first_seen_at:'',last_seen_at:''});
 const rows=projectSystems([system(1,0,0),system(2,100,50),system(3,null,null)]);
 assert.equal(rows.length,2);assert.ok(rows[1].x>rows[0].x&&rows[1].y<rows[0].y);
 assert.ok(rows.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
 assert.deepEqual(projectSystems([system(1,10,20)]).map(p=>[p.x,p.y]),[[500,280]]);
 assert.deepEqual(projectSystems([]),[]);
});
