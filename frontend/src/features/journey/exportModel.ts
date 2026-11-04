import type {JourneyHistory,Context,ShipSegment,Visit} from './types.ts';
import {projectSystems} from './replay.ts';

export const EXPORT_WIDTH=1920, EXPORT_HEIGHT=1080, MAX_EXPORT_VISITS=500, MAX_EXPORT_SECONDS=600, MAX_EXPORT_BYTES=128*1024*1024;
export const EXPORT_OVERHEAD=4.5;
export const ENGAGEMENT_PAGE_SIZE=6, ENGAGEMENT_HOLD=3;
export type CombatRow=Context['combat']['rows'][number];
export type ExportCombat={available:boolean;notice?:string;rows:CombatRow[];total:number;truncated:boolean;limit:number};
export type ExportPhase={kind:'overview'|'zoom'|'visit'|'engagement'|'outro'|'end';start:number;duration:number;index:number;page?:number};
export type Camera={x:number;y:number;scale:number};
export type ExportPlan={history:JourneyHistory;visits:Visit[];engagements:CombatRow[][];phases:ExportPhase[];duration:number;exportedAt:string;unmatched:number;combatAvailable:boolean;points:ReturnType<typeof projectSystems>;partNumber?:number;visitNumbers?:number[];continued?:boolean;clipStartAt?:string;clipEndAt?:string};
export type TimelineUnit={kind:'visit'|'engagement';visitIndex:number;page?:number};
export type ExportTimeline={history:JourneyHistory;combat:ExportCombat;engagements:CombatRow[][];units:TimelineUnit[];unmatched:number};
export const utcStamp=(s:string)=>new Date(s).toISOString().replace('T',' ').slice(0,19)+' UTC';

// Continuous observations extend until the next system sample. Across pauses or
// gaps only the confirmed span is eligible; never attach a gap kill to a revisit.
export function matchEngagements(history:JourneyHistory,rows:CombatRow[]):CombatRow[][]{
 const groups=history.visits.map(()=>[] as CombatRow[]),seen=new Set<number>();
 const from=Date.parse(history.from_at),to=Date.parse(history.to_at);
 for(const row of rows.slice().sort((a,b)=>Date.parse(a.time)-Date.parse(b.time)||a.id-b.id)){
  if(seen.has(row.id))continue;seen.add(row.id);
  const at=Date.parse(row.time);if(!Number.isFinite(at)||at<from||at>=to)continue;
  const index=history.visits.findIndex((v,i)=>{
   const next=history.visits[i+1]??(history as JourneyHistory&{next_visit?:Visit|null}).next_visit,continuous=next&&!next.gap_before;
   return v.system_id===row.system_id&&at>=Date.parse(v.first_seen_at)&&(continuous?at<Date.parse(next.first_seen_at):at<=Date.parse(v.last_seen_at));
  });
  if(index>=0)groups[index].push(row);
 }
 return groups;
}

export function exportTimeline(history:JourneyHistory,combat:ExportCombat,first=1,last=history.visits.length):ExportTimeline{
 if(!Number.isInteger(first)||!Number.isInteger(last)||first<1||last<first||last>history.visits.length)throw new Error('Choose a valid visit range.');
 if(combat.truncated)throw new Error('Combat records exceed the export limit. Narrow the journey dates before exporting.');
 const rows=combat.available?combat.rows:[],engagements=matchEngagements(history,rows),units:TimelineUnit[]=[];
 for(let i=first-1;i<last;i++){units.push({kind:'visit',visitIndex:i});for(let page=0;page<Math.ceil(engagements[i].length/ENGAGEMENT_PAGE_SIZE);page++)units.push({kind:'engagement',visitIndex:i,page});}
 const matched=new Set(engagements.flat().map(r=>r.id));
 return {history,combat,engagements,units,unmatched:new Set(rows.filter(r=>!matched.has(r.id)).map(r=>r.id)).size};
}
export const unitSeconds=(unit:TimelineUnit)=>unit.kind==='visit'?1:ENGAGEMENT_HOLD;
export function segmentTimeline(units:TimelineUnit[]):TimelineUnit[][]{
 const clips:TimelineUnit[][]=[];let clip:TimelineUnit[]=[],seconds=EXPORT_OVERHEAD,visits=new Set<number>();
 for(const unit of units){
  if(clip.length&&(seconds+unitSeconds(unit)>MAX_EXPORT_SECONDS||(!visits.has(unit.visitIndex)&&visits.size>=MAX_EXPORT_VISITS))){clips.push(clip);clip=[];seconds=EXPORT_OVERHEAD;visits=new Set();}
  clip.push(unit);seconds+=unitSeconds(unit);visits.add(unit.visitIndex);
 }
 if(clip.length)clips.push(clip);return clips;
}
export function splitTimeline(units:TimelineUnit[]):[TimelineUnit[],TimelineUnit[]]{
 if(units.length<2)throw new Error('One timeline event exceeds the file-size limit. Try MP4 instead of GIF. Saved clips are preserved.');
 const half=units.reduce((sum,u)=>sum+unitSeconds(u),0)/2;let sum=0,index=0;
 while(index<units.length-1&&sum<half){sum+=unitSeconds(units[index]);index++;}
 return [units.slice(0,index),units.slice(index)];
}
export function planTimelineClip(timeline:ExportTimeline,units:TimelineUnit[],exportedAt=new Date().toISOString(),partNumber?:number):ExportPlan{
 if(!units.length)throw new Error('No timeline events selected.');
 const {history,combat}=timeline,indices=[...new Set(units.map(u=>u.visitIndex))];
 if(indices.length>MAX_EXPORT_VISITS)throw new Error(`Choose at most ${MAX_EXPORT_VISITS} visits per clip.`);
 const visits=indices.map(i=>history.visits[i]).map(v=>{const first=Math.max(Date.parse(v.first_seen_at),Date.parse(history.from_at)),last=Math.max(first,Math.min(Date.parse(v.last_seen_at),Date.parse(history.to_at)-1));return {...v,first_seen_at:new Date(first).toISOString(),last_seen_at:new Date(last).toISOString(),observed_span_seconds:(last-first)/1000};});
 const engagements=indices.map(i=>timeline.engagements[i]),ids=new Set(visits.map(v=>v.system_id)),points=projectSystems(history.systems.filter(s=>ids.has(s.system_id)),1220,650);
 const phases:ExportPhase[]=[];let duration=0;
 const add=(kind:ExportPhase['kind'],seconds:number,index:number,page?:number)=>{phases.push({kind,start:duration,duration:seconds,index,page});duration+=seconds;};
 add('overview',1,0);add('zoom',1,0);
 units.forEach(u=>add(u.kind,unitSeconds(u),indices.indexOf(u.visitIndex),u.page));
 add('outro',1.5,visits.length-1);add('end',1,visits.length-1);
 if(duration>MAX_EXPORT_SECONDS)throw new Error('This clip exceeds ten minutes including engagement pauses. Choose fewer visits.');
 const eventStamp=(unit:TimelineUnit,end:boolean)=>{const index=indices.indexOf(unit.visitIndex);if(unit.kind==='visit')return end?visits[index].last_seen_at:visits[index].first_seen_at;const rows=engagements[index].slice(unit.page!*ENGAGEMENT_PAGE_SIZE,(unit.page!+1)*ENGAGEMENT_PAGE_SIZE);return rows[end?rows.length-1:0].time;};
 return {history,visits,engagements,phases,duration,exportedAt,unmatched:timeline.unmatched,combatAvailable:combat.available,points,partNumber,
  visitNumbers:indices.map(i=>((history as JourneyHistory&{visit_offset?:number}).visit_offset??0)+i+1),continued:units[0].kind==='engagement',
  clipStartAt:eventStamp(units[0],false),clipEndAt:eventStamp(units[units.length-1],true)};
}
export function makeExportPlan(history:JourneyHistory,combat:ExportCombat,first:number,last:number,exportedAt=new Date().toISOString()):ExportPlan{
 if(last-first+1>MAX_EXPORT_VISITS)throw new Error(`Choose at most ${MAX_EXPORT_VISITS} visits per clip.`);
 const timeline=exportTimeline(history,combat,first,last);return planTimelineClip(timeline,timeline.units,exportedAt);
}
const smooth=(p:number)=>{const t=Math.max(0,Math.min(1,p));return t*t*(3-2*t);};
const fit:Camera={x:610,y:325,scale:1};
const mix=(a:Camera,b:Camera,p:number):Camera=>{const t=smooth(p);return {x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t,scale:Math.exp(Math.log(a.scale)+(Math.log(b.scale)-Math.log(a.scale))*t)};};
export function focusCamera(plan:ExportPlan,index:number):Camera{
 for(let i=index;i>=0;i--){const point=plan.points.find(p=>p.system.system_id===plan.visits[i].system_id);if(point)return {x:point.x,y:point.y,scale:4};}
 return fit;
}
export function exportFrame(plan:ExportPlan,time:number){
 const at=Math.max(0,Math.min(plan.duration,time)),phase=plan.phases.find(p=>at<p.start+p.duration)??plan.phases[plan.phases.length-1];
 const progress=(at-phase.start)/phase.duration,target=focusCamera(plan,phase.index);
 let camera=target;
 if(phase.kind==='overview'||phase.kind==='end')camera=fit;
 if(phase.kind==='zoom')camera=mix(fit,target,progress);
 if(phase.kind==='outro')camera=mix(target,fit,progress);
 if(phase.kind==='visit'&&phase.index>0)camera=mix(focusCamera(plan,phase.index-1),target,progress/.55);
 return {phase,progress:Math.max(0,Math.min(1,progress)),camera};
}
export function hullAt(plan:ExportPlan,index:number,time:string):ShipSegment|null{
 const visit=plan.visits[index],at=Date.parse(time);
 return plan.history.ship_segments.find(s=>s.visit_id===visit.id&&s.system_id===visit.system_id&&at>=Date.parse(s.first_seen_at)&&at<=Date.parse(s.last_seen_at))??null;
}
export type ExportRequest={format:'gif'|'mp4';plan:ExportPlan;logo:ImageBitmap;version:string};
export type ExportMessage={type:'progress';progress:number}|{type:'done';buffer:ArrayBuffer;mime:string}|{type:'error';message:string;code?:'size_limit'};
