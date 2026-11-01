import type {Visit,ShipSegment} from './types';
export type JourneyStep={key:string;visitIndex:number;system_id:number;at:string;last_at:string;ship:ShipSegment|null;gap_before:boolean};

// A hull change is a replay step, but retains its original visit identity. Never
// propagate a known hull through a location-only sample or backfill old visits.
export function journeySteps(visits:Visit[],segments:ShipSegment[]):JourneyStep[]{
 const byVisit=new Map<number,ShipSegment[]>();
 for(const s of segments){const group=byVisit.get(s.visit_id)??[];group.push(s);byVisit.set(s.visit_id,group);}
 return visits.flatMap((v,index)=>{
  const shipRows=(byVisit.get(v.id)??[]).slice().sort((a,b)=>Date.parse(a.first_seen_at)-Date.parse(b.first_seen_at)||a.id-b.id);
  const steps:JourneyStep[]=[];
  const unknown=(key:string,at:string,gap:boolean)=>steps.push({key,visitIndex:index,system_id:v.system_id,at,last_at:at,ship:null,gap_before:gap});
  if(!shipRows.length||Date.parse(shipRows[0].first_seen_at)>Date.parse(v.first_seen_at))unknown(`visit-${v.id}`,v.first_seen_at,v.gap_before);
  if(!shipRows.length)steps[0].last_at=v.last_seen_at;
  for(const s of shipRows)steps.push({key:`ship-${s.id}`,visitIndex:index,system_id:v.system_id,at:s.first_seen_at,last_at:s.last_seen_at,ship:s,gap_before:s.gap_before});
  if(shipRows.length&&Date.parse(shipRows[shipRows.length-1].last_seen_at)<Date.parse(v.last_seen_at))unknown(`end-${v.id}`,v.last_seen_at,true);
  return steps;
 });
}
