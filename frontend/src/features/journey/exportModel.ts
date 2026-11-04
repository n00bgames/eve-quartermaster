import type {JourneyHistory,Context,ShipSegment,Visit} from './types.ts';
import {projectSystems} from './replay.ts';

export const EXPORT_WIDTH=1920, EXPORT_HEIGHT=1080, MAX_EXPORT_VISITS=300, MAX_EXPORT_SECONDS=600;
export const ENGAGEMENT_PAGE_SIZE=6, ENGAGEMENT_HOLD=3;
export type CombatRow=Context['combat']['rows'][number];
export type ExportCombat={available:boolean;notice?:string;rows:CombatRow[];total:number;truncated:boolean;limit:number};
export type ExportPhase={kind:'overview'|'zoom'|'visit'|'engagement'|'outro'|'end';start:number;duration:number;index:number;page?:number};
export type Camera={x:number;y:number;scale:number};
export type ExportPlan={history:JourneyHistory;visits:Visit[];engagements:CombatRow[][];phases:ExportPhase[];duration:number;exportedAt:string;unmatched:number;combatAvailable:boolean;points:ReturnType<typeof projectSystems>};
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
   const next=history.visits[i+1],continuous=next&&!next.gap_before;
   return v.system_id===row.system_id&&at>=Date.parse(v.first_seen_at)&&(continuous?at<Date.parse(next.first_seen_at):at<=Date.parse(v.last_seen_at));
  });
  if(index>=0)groups[index].push(row);
 }
 return groups;
}

export function makeExportPlan(history:JourneyHistory,combat:ExportCombat,first:number,last:number,exportedAt=new Date().toISOString()):ExportPlan{
 if(!Number.isInteger(first)||!Number.isInteger(last)||first<1||last<first||last>history.visits.length)throw new Error('Choose a valid visit range.');
 if(last-first+1>MAX_EXPORT_VISITS)throw new Error(`Choose at most ${MAX_EXPORT_VISITS} visits per clip.`);
 if(combat.truncated)throw new Error('Combat records exceed the export limit. Narrow the journey dates before exporting.');
 const rows=combat.available?combat.rows:[],all=matchEngagements(history,rows),engagements=all.slice(first-1,last);
 const visits=history.visits.slice(first-1,last).map(v=>({...v,first_seen_at:new Date(Math.max(Date.parse(v.first_seen_at),Date.parse(history.from_at))).toISOString(),last_seen_at:new Date(Math.min(Date.parse(v.last_seen_at),Date.parse(history.to_at)-1)).toISOString()}));
 const ids=new Set(visits.map(v=>v.system_id)),points=projectSystems(history.systems.filter(s=>ids.has(s.system_id)),1220,650);
 const phases:ExportPhase[]=[];let duration=0;
 const add=(kind:ExportPhase['kind'],seconds:number,index:number,page?:number)=>{phases.push({kind,start:duration,duration:seconds,index,page});duration+=seconds;};
 add('overview',1,0);add('zoom',1,0);
 visits.forEach((_,i)=>{add('visit',1,i);for(let page=0;page<Math.ceil(engagements[i].length/ENGAGEMENT_PAGE_SIZE);page++)add('engagement',ENGAGEMENT_HOLD,i,page);});
 add('outro',1.5,visits.length-1);add('end',1,visits.length-1);
 if(duration>MAX_EXPORT_SECONDS)throw new Error('This clip exceeds ten minutes including engagement pauses. Choose fewer visits.');
 const matched=new Set(all.flat().map(r=>r.id));
 const unmatched=new Set(rows.filter(r=>!matched.has(r.id)).map(r=>r.id)).size;
 return {history,visits,engagements,phases,duration,exportedAt,unmatched,combatAvailable:combat.available,points};
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
export type ExportMessage={type:'progress';progress:number}|{type:'done';buffer:ArrayBuffer;mime:string}|{type:'error';message:string};
