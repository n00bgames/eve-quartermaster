import test from 'node:test';
import assert from 'node:assert/strict';
import {exportTimeline,segmentTimeline,planTimelineClip,splitTimeline,MAX_EXPORT_VISITS,type ExportCombat,type TimelineUnit} from '../src/features/journey/exportModel.ts';
import {journeyExportPages,type ExportHistoryPage} from '../src/features/journey/exportHistory.ts';
import type {JourneyHistory} from '../src/features/journey/types.ts';
const at=(n:number)=>new Date(Date.UTC(2026,10,1)+n*1000).toISOString();
const history=(count:number)=>({character:{character_id:1,eve_id:9001,name:'Demo'},systems:[],visits:Array.from({length:count},(_,i)=>({id:i+1,system_id:1,first_seen_at:at(i*60),last_seen_at:at(i*60+30),samples:2,gap_before:i===0,observed_span_seconds:30})),ship_segments:[],from_at:at(0),to_at:at((count+1)*60),visit_offset:0,ship_segment_count:0,ship_segments_truncated:false,window_visits:count} as JourneyHistory&{visit_offset:number});
const combat:ExportCombat={available:true,rows:[],total:0,truncated:false,limit:5000};

test('500 visits fit one clip; a whole journey continues at 501 with exact coverage',()=>{
 assert.equal(MAX_EXPORT_VISITS,500);
 const timeline=exportTimeline(history(1201),combat),clips=segmentTimeline(timeline.units);
 assert.deepEqual(clips.map(c=>c.length),[500,500,201]);assert.deepEqual(clips.flat(),timeline.units);
 assert.equal(planTimelineClip(timeline,clips[0]).duration,504.5);
 assert.equal(planTimelineClip(timeline,clips[1]).visitNumbers?.[0],501);
 assert.ok(clips.every(c=>planTimelineClip(timeline,c).duration<=600));
});
test('engagements crossing ten minutes continue at the next page without replaying a visit',()=>{
 const source=history(2),rows=Array.from({length:1200},(_,i)=>({id:i+1,system_id:1,time:at(10),ship_type_id:1,ship:'Rifter',side:i%2?'kill':'loss'}));
 const timeline=exportTimeline(source,{...combat,rows,total:rows.length}),clips=segmentTimeline(timeline.units);
 assert.deepEqual(clips.flat(),timeline.units);assert.equal(clips.length,2);
 assert.equal(clips[1][0].kind,'engagement');assert.equal(clips[1][0].page,198);
 const next=planTimelineClip(timeline,clips[1],at(100),2);assert.equal(next.continued,true);assert.equal(next.partNumber,2);
 assert.equal(next.phases.filter(p=>p.kind==='visit').length,1);assert.equal(clips.flat().filter(u=>u.kind==='visit').length,2);
 const ids=clips.flatMap(c=>c.filter(u=>u.kind==='engagement').flatMap(u=>timeline.engagements[u.visitIndex].slice(u.page!*6,(u.page!+1)*6).map(r=>r.id)));
 assert.equal(new Set(ids).size,1200);assert.equal(ids.length,1200);
});
test('adaptive file-size splitting preserves every timeline unit and stops at indivisible events',()=>{
 const timeline=exportTimeline(history(7),combat),queue=[timeline.units],result:TimelineUnit[][]=[];
 while(queue.length){const next=queue.shift()!;if(next.length>2)queue.unshift(...splitTimeline(next));else result.push(next);}
 assert.deepEqual(result.flat(),timeline.units);assert.ok(result.every(c=>c.length>0));assert.throws(()=>splitTimeline([timeline.units[0]]),/One timeline event/);
});
test('page lookahead assigns combat between last sample and next page exactly once',()=>{
 const source=history(1) as JourneyHistory&{next_visit?:unknown};source.to_at=at(180);source.next_visit={...history(2).visits[1]};
 const row={id:1,system_id:1,time:at(45),ship_type_id:1,ship:'Rifter',side:'kill'};
 assert.equal(exportTimeline(source,{...combat,rows:[row],total:1}).engagements[0].length,1);
});
test('paged loader includes all attachments and advances to the next history page',async()=>{
 const first={kind:'visits',history:history(1),combat:{...combat},ship_cursor:null,combat_cursor:'combat-2',next_cursor:'visits-2',snapshot_at:at(300)} as ExportHistoryPage;
 first.combat={...combat,total:1};
 const second={...first,history:{...history(1),visit_offset:1},combat:{...combat},combat_cursor:null,next_cursor:null};
 const paths:string[]=[];
 const fetcher=async<T>(path:string)=>{paths.push(path);return structuredClone(path.includes('combat-2')?{kind:'combat',rows:[{id:1,time:at(0),system_id:1,side:'kill',ship:null,ship_type_id:null}],next_cursor:null,available:true}:path.includes('visits-2')?second:first) as T;};
 const pages=[];for await(const p of journeyExportPages(fetcher,1,'all','ignored',new AbortController().signal))pages.push(p);
 assert.equal(pages.length,2);assert.equal(pages[0].combat.rows.length,1);assert.ok(paths[0].endsWith('scope=all'));assert.equal(paths.length,3);
});
test('incomplete or inconsistent pages stop rather than silently exporting missing records',async()=>{
 const page={kind:'visits',history:history(1),combat:{...combat,total:2},ship_cursor:null,combat_cursor:null,next_cursor:null,snapshot_at:at(300)} as ExportHistoryPage;
 const run=async()=>{for await(const _ of journeyExportPages(async<T>()=>page as T,1,'range','from_at=demo',new AbortController().signal)){};};
 await assert.rejects(run,/records changed/);
});
test('a snapshot at the current sample never creates a negative visit span after millisecond rounding',()=>{
 const source=history(1);source.to_at=source.visits[0].first_seen_at;source.visits[0].last_seen_at=source.to_at;
 const timeline=exportTimeline(source,combat),plan=planTimelineClip(timeline,timeline.units);
 assert.equal(plan.visits[0].first_seen_at,plan.visits[0].last_seen_at);assert.equal(plan.visits[0].observed_span_seconds,0);
});
test('attachment paging handles a very large engagement without overflowing a spread call',async()=>{
 const page={kind:'visits',history:history(1),combat:{...combat,rows:[],total:130000},ship_cursor:null,combat_cursor:'combat-0',next_cursor:null,snapshot_at:at(300)} as ExportHistoryPage;
 const fetcher=async<T>(path:string)=>{
  if(!path.includes('cursor='))return structuredClone(page) as T;
  const n=Number(path.split('combat-')[1]);return {kind:'combat',available:true,total:130000,rows:Array.from({length:5000},(_,i)=>({id:n*5000+i+1,system_id:1,time:at(10),ship_type_id:null,ship:null,side:'kill'})),next_cursor:n<25?'combat-'+(n+1):null} as T;
 };
 const pages=[];for await(const p of journeyExportPages(fetcher,1,'all','',new AbortController().signal))pages.push(p);
 assert.equal(pages[0].combat.rows.length,130000);assert.equal(pages[0].combat.rows[129999].id,130000);
});
