import type {FleetPosition,JourneyHistory,Visit} from './types.ts';

export function fleetPositions(history:JourneyHistory,at=Infinity):FleetPosition[]{
 const fleet=history.fleet;if(!fleet)return [];
 const positions=new Map(fleet.seeds.filter(p=>Date.parse(p.visit.first_seen_at)<=at).map(p=>[p.pilot_id,p]));
 for(const visit of history.visits){
  const pilot_id=fleet.owners[visit.id];
  if(pilot_id===undefined||Date.parse(visit.first_seen_at)>at)continue;
  const old=positions.get(pilot_id);
  if(old&&Date.parse(old.visit.first_seen_at)>Date.parse(visit.first_seen_at))continue;
  const sample=Math.min(at,Date.parse(visit.last_seen_at));
  const ship=history.ship_segments.find(s=>s.visit_id===visit.id&&s.system_id===visit.system_id&&Date.parse(s.first_seen_at)<=sample&&Date.parse(s.last_seen_at)>=sample)??null;
  positions.set(pilot_id,{pilot_id,visit,ship});
 }
 return [...positions.values()].sort((a,b)=>a.pilot_id-b.pilot_id);
}

export function fleetLinks(visits:Visit[],owners:Record<number,number>,seeds:FleetPosition[]=[]){
 const previous=new Map(seeds.map(p=>[p.pilot_id,p.visit]));
 const links:{a:number;b:number;gap:boolean;pilot_id:number}[]=[];
 for(const v of visits){const pilot_id=owners[v.id];if(pilot_id===undefined)continue;
  const prior=previous.get(pilot_id);
  if(prior&&prior.system_id!==v.system_id)links.push({a:prior.system_id,b:v.system_id,gap:v.gap_before,pilot_id});
  previous.set(pilot_id,v);
 }
 return links;
}

export const pilotColor=(id:number)=>['#65d9ef','#f5bd6b','#b29bff','#87df9d','#fa91b1','#e8dc7b','#88baff','#e4a5f0'][Math.abs(id)%8];
