import type {JourneyHistory,FleetTrace,ShipSegment} from './types.ts';
import {matchEngagements,type ExportCombat} from './exportModel.ts';
import {pilotColor} from './fleetGeometry.ts';

export const FLEET_MAP_LIMIT=2000;
export function mergeFleet(histories:JourneyHistory[],combat=new Map<number,ExportCombat>(),limit=FLEET_MAP_LIMIT):JourneyHistory{
 if(!histories.length)throw new Error('No tracked pilot histories are available.');
 const sorted=histories.slice().sort((a,b)=>a.character.character_id-b.character.character_id);
 const entries=sorted.flatMap(h=>h.visits.map((visit,i)=>({history:h,visit,combat:combat.get(h.character.character_id)?.available?matchCache(h,combat.get(h.character.character_id)!)[i]:[]})));
 entries.sort((a,b)=>Date.parse(a.visit.first_seen_at)-Date.parse(b.visit.first_seen_at)||a.history.character.character_id-b.history.character.character_id||a.visit.id-b.visit.id);
 const loaded=entries.slice(0,limit),fleet:FleetTrace={pilots:sorted.map(h=>({...h.character,color:pilotColor(h.character.character_id)})),owners:{},seeds:[],engagements:{},visitNumbers:{}};
 const ships:ShipSegment[]=[],systems=new Map<number,JourneyHistory['systems'][number]>();
 for(const h of sorted)for(const system of h.systems)if(!systems.has(system.system_id))systems.set(system.system_id,system);
 const visits=loaded.map(({history:h,visit,combat:rows},i)=>{
  const id=i+1;fleet.owners[id]=h.character.character_id;fleet.visitNumbers[id]=id;fleet.engagements[id]=rows;
  for(const s of h.ship_segments)if(s.visit_id===visit.id)ships.push({...s,id:ships.length+1,visit_id:id});
  return {...visit,id};
 });
 fleet.unmatched=sorted.reduce((n,h)=>{const c=combat.get(h.character.character_id);if(!c?.available)return n;const matched=new Set(matchCache(h,c).flat().map(r=>r.id));return n+new Set(c.rows.filter(r=>!matched.has(r.id)).map(r=>r.id)).size;},0);
 const first=sorted[0],window_visits=sorted.reduce((n,h)=>n+h.window_visits,0);
 return {...first,character:{character_id:0,eve_id:0,name:'My Fleet'},tracking:{...first.tracking,state:'fleet_recorded_positions'},
  visits,systems:[...systems.values()],ship_segments:ships,ship_segment_count:ships.length,
  ship_segments_truncated:sorted.some(h=>h.ship_segments_truncated),
  window_visits,total_visits:sorted.reduce((n,h)=>n+h.total_visits,0),unique_systems:systems.size,
  truncated:sorted.some(h=>h.truncated)||loaded.length<entries.length,limit,fleet};
}
// One match pass per source history, rather than one pass for every visit.
const cache=new WeakMap<JourneyHistory,{combat:ExportCombat;groups:ReturnType<typeof matchEngagements>}>();
function matchCache(h:JourneyHistory,c:ExportCombat){let value=cache.get(h);if(!value||value.combat!==c){value={combat:c,groups:matchEngagements(h,c.rows)};cache.set(h,value);}return value.groups;}

export async function mapConcurrent<T,R>(items:T[],work:(item:T)=>Promise<R>,concurrency=3):Promise<R[]>{
 const results:R[]=new Array(items.length);let next=0,failed=false;
 await Promise.all(Array.from({length:Math.min(concurrency,items.length)},async()=>{while(!failed&&next<items.length){const index=next++;try{results[index]=await work(items[index]);}catch(error){failed=true;throw error;}}}));
 return results;
}
