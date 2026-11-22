import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeFleet,mapConcurrent} from '../src/features/journey/fleetModel.ts';
import {fleetPositions,fleetLinks} from '../src/features/journey/fleetGeometry.ts';
import {fleetExportPages} from '../src/features/journey/fleetExportHistory.ts';
import {exportTimeline,planTimelineClip,segmentTimeline,type ExportCombat} from '../src/features/journey/exportModel.ts';
import type {JourneyHistory,TrackedCharacter} from '../src/features/journey/types.ts';
const at=(s:number)=>new Date(Date.UTC(2026,10,22,0,0,s)).toISOString();
const pilot=(id:number)=>({character_id:id,eve_id:90000+id,name:`Demo ${id}`,enabled:true,authorized:true,ship_authorized:true,track_ship:true,interval_seconds:15,state:'ok',checked_at:null,last_seen_at:null}) satisfies TrackedCharacter;
function history(id:number,times:number[],systems=times.map((_,i)=>i+1)):JourneyHistory{
 return {character:{character_id:id,eve_id:90000+id,name:`Demo ${id}`},tracking:pilot(id),from_at:at(0),to_at:at(10000),
  total_visits:times.length,window_visits:times.length,unique_systems:new Set(systems).size,limit:2000,truncated:false,ship_segment_count:0,ship_segment_limit:5000,ship_segments_truncated:false,ship_segments:[],
  visits:times.map((t,i)=>({id:i+1,system_id:systems[i],first_seen_at:at(t),last_seen_at:at(t+2),samples:2,gap_before:i===0,observed_span_seconds:2})),
  systems:[...new Set(systems)].map(system_id=>({system_id,name:`System ${system_id}`,region:'Demo region',security:.5,x:system_id*100,z:system_id*20,visits:1,first_seen_at:at(0),last_seen_at:at(9999)}))};
}
const combat=(rows:ExportCombat['rows']=[],available=true):ExportCombat=>({available,rows,total:rows.length,truncated:false,limit:5000});
const kill=(id:number,time:number,system_id=1)=>({id,system_id,time:at(time),side:'kill',ship_type_id:10,ship:'Demo hull'});
function fetcher(histories:JourneyHistory[],combats=new Map<number,ExportCombat>()){
 const calls:string[]=[];
 const fetch=async <T,>(path:string):Promise<T>=>{
  calls.push(path);const url=new URL(path,'http://fixture'),id=Number(path.match(/characters\/(\d+)/)?.[1]),h=histories.find(h=>h.character.character_id===id)!;
  assert.ok(h,'Only selected pilots may be fetched');
  const offset=Number(url.searchParams.get('cursor')??0),visits=h.visits.slice(offset,offset+500),next=h.visits[offset+500];
  const c=combats.get(id)??combat();
  return {kind:'visits',snapshot_at:at(9999),history:{...h,visits,visit_offset:offset,next_visit:next??null,ship_segments:h.ship_segments.filter(s=>visits.some(v=>v.id===s.visit_id)),ship_segment_count:h.ship_segments.filter(s=>visits.some(v=>v.id===s.visit_id)).length},
   combat:{...c,rows:c.rows.filter(r=>Date.parse(r.time)>=Date.parse(visits[0]?.first_seen_at??at(9999))&&(!next||Date.parse(r.time)<Date.parse(next.first_seen_at))),total:0},ship_cursor:null,combat_cursor:null,next_cursor:next?String(offset+500):null} as T;
 };
 // Recalculate attachment totals after page filtering, just as the server does.
 const counted=async <T,>(path:string,options?:RequestInit):Promise<T>=>{assert.ok(!options?.method||options.method==='GET');const p=await fetch<any>(path);p.combat.total=p.combat.rows.length;return p;};
 return {fetch:counted,calls};
}

test('fleet merge is chronological, deterministic, and remaps colliding visit/ship IDs',()=>{
 const a=history(1,[0,20],[1,2]),b=history(2,[0,10],[1,3]);
 a.ship_segments=[{id:1,visit_id:1,system_id:1,ship_type_id:100,ship_name:'Alpha',first_seen_at:at(0),last_seen_at:at(2),samples:1,gap_before:true}];
 b.ship_segments=[{...a.ship_segments[0],ship_type_id:200,ship_name:'Beta'}];
 const merged=mergeFleet([b,a]);
 assert.deepEqual(merged.visits.map(v=>merged.fleet!.owners[v.id]),[1,2,2,1]);
 assert.equal(new Set(merged.visits.map(v=>v.id)).size,4);
 assert.deepEqual(merged.ship_segments.map(s=>[merged.fleet!.owners[s.visit_id],s.ship_name]),[[1,'Alpha'],[2,'Beta']]);
 assert.deepEqual(mergeFleet([a,b]).visits,merged.visits);
});
test('routes never connect different pilots, including co-located observations',()=>{
 const h=mergeFleet([history(1,[0,20],[1,2]),history(2,[10,30],[3,4])]);
 assert.deepEqual(fleetLinks(h.visits,h.fleet!.owners).map(r=>[r.pilot_id,r.a,r.b]),[[1,1,2],[2,3,4]]);
});
test('replay positions exclude unobserved pilots and future hull changes',()=>{
 const a=history(1,[0],[1]),b=history(2,[10],[2]);a.visits[0].last_seen_at=at(30);
 a.ship_segments=[{id:1,visit_id:1,system_id:1,ship_type_id:10,ship_name:'Later hull',first_seen_at:at(20),last_seen_at:at(30),samples:1,gap_before:true}];
 const h=mergeFleet([a,b]);
 assert.deepEqual(fleetPositions(h,-1),[]);
 assert.deepEqual(fleetPositions(h,Date.parse(at(5))).map(p=>[p.pilot_id,p.ship]),[[1,null]]);
 assert.equal(fleetPositions(h,Date.parse(at(25)))[0].ship?.ship_name,'Later hull');
});
test('loaded replay caps are explicit and per-pilot truncation survives aggregation',()=>{
 const a=history(1,[0,10,20]),b=history(2,[5,15,25]);b.truncated=true;b.window_visits=9;
 const h=mergeFleet([a,b],undefined,4);assert.equal(h.visits.length,4);assert.equal(h.window_visits,12);assert.equal(h.truncated,true);
});
test('the same kill ID can correctly appear for each involved fleet pilot',()=>{
 const a=history(1,[0],[1]),b=history(2,[0],[1]);
 const h=mergeFleet([a,b],new Map([[1,combat([kill(7,1)])],[2,combat([kill(7,1)])]]));
 const timeline=exportTimeline(h,combat());assert.deepEqual(timeline.engagements.map(r=>r.map(k=>k.id)),[[7],[7]]);
});
test('paged fleet merge crosses 500/2000 visits without omissions or duplicate visit events',async()=>{
 const a=history(1,Array.from({length:1200},(_,i)=>i*2)),b=history(2,Array.from({length:1200},(_,i)=>i*2+1));
 const f=fetcher([a,b]),all:number[]=[],owners:number[]=[];
 for await(const page of fleetExportPages(f.fetch,[pilot(2),pilot(1)],'all','',new AbortController().signal)){
  const timeline=exportTimeline(page.history,page.combat);
  for(const unit of timeline.units)if(unit.kind==='visit'){const v=page.history.visits[unit.visitIndex];all.push(page.history.fleet!.visitNumbers[v.id]);owners.push(page.history.fleet!.owners[v.id]);}
  assert.ok(page.history.visits.length<=500);assert.equal(page.history.window_visits,2400);
 }
 assert.deepEqual(all,Array.from({length:2400},(_,i)=>i+1));assert.deepEqual(owners.slice(0,6),[1,2,1,2,1,2]);
 assert.equal(f.calls.length,6);
});
test('late engagements interleave with other pilot moves across output chunk boundaries',async()=>{
 const a=history(1,[0,5000],[1,2]),b=history(2,Array.from({length:600},(_,i)=>i+1));
 const f=fetcher([a,b],new Map([[1,combat([kill(7,550)])]])),events:{at:number;kind:string;owner:number}[]=[];
 for await(const page of fleetExportPages(f.fetch,[pilot(1),pilot(2)],'range','from_at='+at(0),new AbortController().signal)){
  const timeline=exportTimeline(page.history,page.combat);
  for(const unit of timeline.units){const v=page.history.visits[unit.visitIndex];events.push({at:Date.parse(unit.kind==='visit'?v.first_seen_at:timeline.engagements[unit.visitIndex][unit.page!*6].time),kind:unit.kind,owner:page.history.fleet!.owners[v.id]});}
 }
 assert.ok(events.every((e,i)=>!i||e.at>=events[i-1].at));
 assert.equal(events.filter(e=>e.kind==='engagement').length,1);
 assert.ok(events.findIndex(e=>e.kind==='engagement')>500);
 assert.equal(events.filter(e=>e.kind==='visit').length,602);
});
test('segment plans retain global visit numbers, fleet seeds, and continue engagement pages',async()=>{
 const a=history(1,[0,100],[1,2]),b=history(2,[1,200],[3,4]);
 const f=fetcher([a,b],new Map([[1,combat(Array.from({length:1200},(_,i)=>kill(i+1,2+i*.05)))]]));
 let observed=0,engagementPages=0,parts=0;
 for await(const page of fleetExportPages(f.fetch,[pilot(1),pilot(2)],'all','',new AbortController().signal)){
  const t=exportTimeline(page.history,page.combat);
  for(const units of segmentTimeline(t.units)){const plan=planTimelineClip(t,units,at(9999),++parts);assert.ok(plan.duration<=600);assert.ok(plan.visitNumbers!.every(n=>n>=1&&n<=4));if(plan.continued)assert.ok(plan.points.some(p=>p.system.system_id===3),'A pilot holding position must remain mapped during engagement continuation');observed+=units.filter(u=>u.kind==='visit').length;engagementPages+=units.filter(u=>u.kind==='engagement').length;}
 }
 assert.equal(observed,4);assert.equal(engagementPages,200);assert.ok(parts>=2);
});
test('entire-fleet scope retains each pilot’s earlier oldest recorded date',async()=>{
 const a=history(1,[100]),b=history(2,[0]);a.from_at=at(100);
 const f=fetcher([a,b]);
 for await(const p of fleetExportPages(f.fetch,[pilot(1),pilot(2)],'all','',new AbortController().signal)){
  assert.equal(p.history.from_at,at(0));const t=exportTimeline(p.history,p.combat),plan=planTimelineClip(t,t.units);assert.equal(plan.visits[0].first_seen_at,at(0));
 }
});
test('unavailable combat on one pilot does not hide permitted combat on another',async()=>{
 const f=fetcher([history(1,[0]),history(2,[1])],new Map([[1,combat([kill(1,1)])],[2,combat([],false)]]));
 let records=0,unavailable=false;
 for await(const p of fleetExportPages(f.fetch,[pilot(1),pilot(2)],'all','',new AbortController().signal)){records+=exportTimeline(p.history,p.combat).engagements.flat().length;unavailable ||= !p.combat.available;}
 assert.equal(records,1);assert.equal(unavailable,true);
});
test('fleet export rejects duplicate pilots and aborts before issuing requests',async()=>{
 const f=fetcher([history(1,[0])]),controller=new AbortController();controller.abort();
 await assert.rejects(async()=>{for await(const _ of fleetExportPages(f.fetch,[pilot(1)],'all','',controller.signal)){}},/cancelled/);
 assert.equal(f.calls.length,0);
 await assert.rejects(async()=>{for await(const _ of fleetExportPages(f.fetch,[pilot(1),pilot(1)],'all','',new AbortController().signal)){}},/Duplicate/);
});
test('failed pilot history stops the fleet export rather than silently omitting a pilot',async()=>{
 const fetch=async <T,>():Promise<T>=>{throw new Error('permission removed');};
 await assert.rejects(async()=>{for await(const _ of fleetExportPages(fetch,[pilot(1)],'all','',new AbortController().signal)){}},/permission removed/);
});
test('bounded requests retain input order despite out-of-order completion',async()=>{
 let active=0,peak=0;
 const output=await mapConcurrent([1,2,3,4,5,6],async n=>{active++;peak=Math.max(peak,active);await new Promise(r=>setTimeout(r,7-n));active--;return n*2;});
 assert.deepEqual(output,[2,4,6,8,10,12]);assert.ok(peak<=3);
});
