import assert from 'node:assert/strict';
import test from 'node:test';
import {activeTimer,label,needsAttention,remaining,type Structure} from '../src/features/structures/model.ts';

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
