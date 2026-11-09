import assert from 'node:assert/strict';
import test from 'node:test';
import {analyticsQuery,observedSpan,rankPercent} from '../src/features/journey/analyticsModel.ts';

const range='from_at=2026-11-01T00%3A00%3A00Z&to_at=2026-11-10T00%3A00%3A00Z';
test('account all-history analytics never silently inherits the selected pilot or replay dates',()=>{
  const q=new URLSearchParams(analyticsQuery('account',5,'all',range,'visits',10)!);
  assert.equal(q.get('period'),'all');assert.equal(q.get('ship_order'),'visits');
  assert.equal(q.has('character_id'),false);assert.equal(q.has('from_at'),false);assert.equal(q.has('to_at'),false);
});
test('selected pilot and date scope preserve the exact exclusive UTC window',()=>{
  const q=new URLSearchParams(analyticsQuery('character',5,'range',range,'span',25)!);
  assert.equal(q.get('character_id'),'5');assert.equal(q.get('from_at'),'2026-11-01T00:00:00Z');assert.equal(q.get('to_at'),'2026-11-10T00:00:00Z');
  assert.equal(q.get('ship_order'),'span');assert.equal(q.get('limit'),'25');assert.equal(analyticsQuery('character',0,'all',range,'visits',10),null);
});
test('confirmed-span labels retain single-observation zeroes and ranking bars stay bounded',()=>{
  assert.equal(observedSpan(0),'0s');assert.equal(observedSpan(59),'59s');assert.equal(observedSpan(60),'1m');assert.equal(observedSpan(3660),'1h 1m');assert.equal(observedSpan(90000),'1d 1h');
  assert.equal(rankPercent(0,0),0);assert.equal(rankPercent(5,10),50);assert.equal(rankPercent(15,10),100);assert.equal(rankPercent(-5,10),0);
});
