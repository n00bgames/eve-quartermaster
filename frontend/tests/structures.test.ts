import assert from 'node:assert/strict';
import test from 'node:test';
import {activeTimer,label,needsAttention,remaining,type Structure} from '../src/features/structures/model.ts';
import {durationHours,fuelEstimate,manualAttention,reinforcementTimer,strontEstimate,towerPresets,utcInput,fromUtcInput,type ManualReading} from '../src/features/structures/manualModel.ts';

const now=Date.parse('2026-11-08T12:00:00Z');
const base:Structure={id:1000000000001,kind:'upwell',name:'Demo',type_id:1,type_name:'Astrahus',system_id:1,system_name:'Demo',security_status:null,state:'shield_vulnerable',moon_name:null,services:[]};
test('expired timestamps never imply a completed game state',()=>{
  assert.equal(remaining(null,now),'Not reported');assert.equal(remaining('invalid',now),'Not reported');
  assert.equal(remaining('2026-11-08T11:00:00Z',now),'Elapsed · awaiting ESI update');
  assert.equal(remaining('2026-11-09T13:00:00Z',now),'1d 1h');
});
test('configured reinforcement hour and POS unanchor start are not active countdowns',()=>{
  assert.equal(activeTimer({...base,reinforce_hour:0}),null);
  assert.equal(activeTimer({...base,kind:'pos',unanchor_at:'2026-11-08T11:00:00Z'}),null);
  assert.deepEqual(activeTimer({...base,kind:'pos',reinforced_until:'2026-11-09T12:00:00Z'}),{name:'Reinforcement ends',at:'2026-11-09T12:00:00Z'});
});
test('low fuel, vulnerable and reinforced states get attention while invulnerable remains neutral',()=>{
  assert.equal(needsAttention({...base,state:'fitting_invulnerable'},now),false);
  assert.equal(needsAttention(base,now),false);
  assert.equal(needsAttention({...base,state:'online_deprecated',fuel_expires:'2026-11-10T12:00:00Z'},now),true);
  assert.equal(needsAttention({...base,kind:'pos',state:'reinforced'},now),true);
  assert.equal(label('new_unknown_state'),'New unknown state');
});

const reading:ManualReading={name:'Demo',tower_type:'Caldari Control Tower',corporation_name:'',location:'',state:'online',fuel_blocks:22080,fuel_per_hour:40,stront_units:16666,stront_per_hour:400,observed_at:'2026-11-08T12:00:00Z',reinforced_until:null,notes:''};

test('manual large Caldari fuel covers 23 days and decrements from the recorded time',()=>{
  const start=fuelEstimate(reading,now)!;assert.equal(start.hoursLeft,23*24);assert.equal(start.blocksLeft,22080);
  assert.equal(start.expiresAt,'2026-12-01T12:00:00.000Z');
  assert.equal(fuelEstimate(reading,now+3600000)!.blocksLeft,22040);
  const end=fuelEstimate(reading,now+24*86400000)!;assert.equal(end.hoursLeft,0);assert.equal(end.blocksLeft,0);
  assert.equal(durationHours(16666/400),'1d 17h 39m');
});

test('reinforced mode counts strontium instead of fuel and preserves the recorded quantities',()=>{
  const reinforced={...reading,state:'reinforced' as const};
  assert.equal(fuelEstimate(reinforced,now+3600000),null);
  const stront=strontEstimate(reinforced,now+3600000)!;
  assert.equal(stront.blocksLeft,16266);assert.equal(stront.hoursLeft,16666/400-1);
  assert.equal(reinforcementTimer(reinforced,now+3600000)!.source,'stront estimate');
  assert.equal(reinforcementTimer(reinforced,now+3600000)!.at,'2026-11-10T05:39:54.000Z');
  assert.equal(reinforced.stront_units,16666);assert.equal(reinforced.fuel_blocks,22080);
  assert.equal(strontEstimate(reading,now),null);assert.equal(reinforcementTimer(reading,now),null);
});

test('an entered reinforcement end overrides the estimate without inventing quantities',()=>{
  const row={...reading,state:'reinforced' as const,reinforced_until:'2026-11-09T12:00:00Z'};
  assert.deepEqual(reinforcementTimer(row,now),{at:row.reinforced_until,hoursLeft:24,source:'entered'});
  assert.equal(strontEstimate(row,now)!.blocksLeft,16666);
  assert.equal(reinforcementTimer({...row,stront_units:null},now)!.source,'entered');
  assert.equal(reinforcementTimer(row,now+2*86400000)!.hoursLeft,0);
});

test('unknown quantities stay unknown while zero readings are exhausted estimates',()=>{
  assert.equal(fuelEstimate({...reading,fuel_blocks:null},now),null);
  assert.equal(fuelEstimate({...reading,fuel_blocks:0},now)!.hoursLeft,0);
  assert.equal(reinforcementTimer({...reading,state:'reinforced',stront_units:null},now),null);
  assert.equal(strontEstimate({...reading,state:'reinforced',stront_units:0},now)!.hoursLeft,0);
  for(const state of ['offline','unknown'] as const){assert.equal(fuelEstimate({...reading,state},now),null);assert.equal(strontEstimate({...reading,state},now),null);}
});

test('manual attention, custom rates and slightly future readings use explicit assumptions',()=>{
  assert.equal(manualAttention(reading,now),false);assert.equal(manualAttention({...reading,fuel_blocks:2880},now),true);
  assert.equal(manualAttention({...reading,state:'reinforced'},now),true);assert.equal(manualAttention({...reading,state:'offline'},now),true);
  assert.equal(manualAttention({...reading,state:'unknown'},now),false);
  assert.equal(fuelEstimate({...reading,fuel_per_hour:30},now)!.hoursLeft,736);
  assert.equal(fuelEstimate(reading,now-60000)!.blocksLeft,22080);
});

test('standard presets cover all races and sizes; EVE UTC input ignores browser timezone',()=>{
  assert.equal(towerPresets.length,12);
  for(const race of ['Caldari','Amarr','Gallente','Minmatar']){
    assert.equal(towerPresets.find(p=>p.name===`${race} Control Tower`)!.fuel,40);
    assert.equal(towerPresets.find(p=>p.name===`${race} Control Tower Medium`)!.stront,200);
    assert.equal(towerPresets.find(p=>p.name===`${race} Control Tower Small`)!.fuel,10);
  }
  assert.equal(utcInput('2026-11-08T12:00:00Z'),'2026-11-08T12:00');
  assert.equal(fromUtcInput('2026-11-08T12:00'),'2026-11-08T12:00:00.000Z');
});
