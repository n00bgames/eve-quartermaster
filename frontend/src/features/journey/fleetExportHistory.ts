import {journeyExportPages,type ExportHistoryPage} from './exportHistory.ts';
import {exportTimeline,type ExportTimeline,type TimelineUnit} from './exportModel.ts';
import {mapConcurrent} from './fleetModel.ts';
import {pilotColor} from './fleetGeometry.ts';
import type {JourneyHistory,TrackedCharacter,FleetPosition,FleetTrace,ShipSegment} from './types.ts';

type Fetcher=<T>(path:string,options?:RequestInit)=>Promise<T>;
type Source={pilot:TrackedCharacter;iterator:AsyncGenerator<ExportHistoryPage>;page?:ExportHistoryPage;timeline?:ExportTimeline;index:number;numbers:Map<number,number>;done:boolean;unmatchedPending:number};
const check=(signal:AbortSignal)=>{if(signal.aborted)throw new DOMException('Export cancelled','AbortError');};
function eventTime(s:Source){
 const unit=s.timeline!.units[s.index],visit=s.page!.history.visits[unit.visitIndex];
 return unit.kind==='visit'?Math.max(Date.parse(visit.first_seen_at),Date.parse(s.page!.history.from_at)):Date.parse(s.timeline!.engagements[unit.visitIndex][(unit.page??0)*6].time);
}
async function advance(s:Source,signal:AbortSignal){
 check(signal);
 while(!s.timeline||s.index>=s.timeline.units.length){
  const result=await s.iterator.next();check(signal);
  if(result.done){s.done=true;return;}
  if(result.value.history.character.character_id!==s.pilot.character_id)throw new Error('A fleet page returned the wrong pilot. Export stopped.');
  s.page=result.value;s.timeline=exportTimeline(s.page.history,s.page.combat);s.index=0;s.numbers=new Map();
  s.unmatchedPending+=s.timeline.unmatched;
  if(s.timeline.units.length)return;
 }
}

/** Merge event streams, not whole pilot histories: late engagements cannot jump
 * ahead of another pilot's earlier movement, including across 500-visit pages. */
export async function* fleetExportPages(fetcher:Fetcher,pilots:TrackedCharacter[],scope:'all'|'range',query:string,signal:AbortSignal):AsyncGenerator<ExportHistoryPage>{
 if(!pilots.length)throw new Error('Choose at least one tracked pilot.');
 if(new Set(pilots.map(p=>p.character_id)).size!==pilots.length)throw new Error('Duplicate fleet pilot.');
 const abort=new AbortController(),forward=()=>abort.abort();
 signal.addEventListener('abort',forward,{once:true});if(signal.aborted)forward();
 const localSignal=abort.signal;
 const sources:Source[]=pilots.slice().sort((a,b)=>a.character_id-b.character_id).map(pilot=>({pilot,iterator:journeyExportPages(fetcher,pilot.character_id,scope,query,localSignal),index:0,numbers:new Map(),done:false,unmatchedPending:0}));
 try{
  await mapConcurrent(sources,s=>advance(s,localSignal));
  const initial=sources.find(s=>s.page)?.page;
  if(!initial)return;
  const total=sources.reduce((n,s)=>n+(s.page?.history.window_visits??0),0),snapshot=initial.snapshot_at;
  const from_at=new Date(Math.min(...sources.filter(s=>s.page).map(s=>Date.parse(s.page!.history.from_at)))).toISOString();
  const to_at=new Date(Math.max(...sources.filter(s=>s.page).map(s=>Date.parse(s.page!.history.to_at)))).toISOString();
  const latest=new Map<number,FleetPosition>(),systems=new Map<number,JourneyHistory['systems'][number]>();
  let number=0;
  while(sources.some(s=>!s.done)){
   const seeds=[...latest.values()].map(p=>({...p,visit:{...p.visit}})),visits:JourneyHistory['visits']=[],ships:ShipSegment[]=[],units:TimelineUnit[]=[];
   const trace:FleetTrace={pilots:pilots.map(p=>({character_id:p.character_id,eve_id:p.eve_id,name:p.name,color:pilotColor(p.character_id)})),owners:{},seeds,engagements:{},visitNumbers:{},unmatched:0};
   const indices=new Map<number,number>();let combatAvailable=true;
   while(units.length<500){
    const source=sources.filter(s=>!s.done).sort((a,b)=>eventTime(a)-eventTime(b)||a.pilot.character_id-b.pilot.character_id)[0];
    if(!source)break;
    const page=source.page!,timeline=source.timeline!,unit=timeline.units[source.index],original=page.history.visits[unit.visitIndex],at=eventTime(source);
    let id=source.numbers.get(unit.visitIndex);
    if(id===undefined){
     if(unit.kind!=='visit')throw new Error('A fleet engagement is missing its earlier visit.');
     id=++number;source.numbers.set(unit.visitIndex,id);
    }
    let visitIndex=indices.get(id);
    if(visitIndex===undefined){
     visitIndex=visits.length;indices.set(id,visitIndex);visits.push({...original,id});
     trace.owners[id]=source.pilot.character_id;trace.visitNumbers[id]=id;
     trace.engagements[id]=timeline.engagements[unit.visitIndex];
     for(const ship of page.history.ship_segments)if(ship.visit_id===original.id)ships.push({...ship,id:ships.length+1,visit_id:id});
    }
    units.push({...unit,visitIndex});
    trace.unmatched!+=source.unmatchedPending;source.unmatchedPending=0;
    combatAvailable&&=page.combat.available;
    for(const system of page.history.systems)systems.set(system.system_id,system);
    const sample=Math.min(at,Date.parse(original.last_seen_at));
    const ship=page.history.ship_segments.find(s=>s.visit_id===original.id&&Date.parse(s.first_seen_at)<=sample&&Date.parse(s.last_seen_at)>=sample)??null;
    latest.set(source.pilot.character_id,{pilot_id:source.pilot.character_id,visit:{...original,id,last_seen_at:new Date(sample).toISOString()},ship});
    source.index++;await advance(source,localSignal);
   }
   if(!units.length)break;
   trace.units=units;
   const ids=new Set([...visits.map(v=>v.system_id),...seeds.map(p=>p.visit.system_id)]);
   const h:JourneyHistory&{visit_offset:number}={...initial.history,from_at,to_at,character:{character_id:0,eve_id:0,name:'My Fleet'},
    visits,ship_segments:ships,ship_segment_count:ships.length,ship_segments_truncated:false,
    systems:[...systems.values()].filter(s=>ids.has(s.system_id)),window_visits:total,limit:500,truncated:false,
    fleet:trace,visit_offset:0};
   yield {kind:'visits',history:h,combat:{available:combatAvailable,rows:[],total:0,truncated:false,limit:5000},
    ship_cursor:null,combat_cursor:null,next_cursor:null,snapshot_at:snapshot};
  }
 }finally{
  // Each iterator holds at most its current page/attachments. No full-journey
  // accumulation and no requests survive the caller's abort signal.
  abort.abort();signal.removeEventListener('abort',forward);
  await Promise.all(sources.map(s=>s.iterator.return(undefined)));
 }
}
