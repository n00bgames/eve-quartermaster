export type Source = {kind:"upwell"|"pos";status:string;message?:string;required_scope?:string;pages:{response_date:string|null;expires:string|null;last_modified:string|null;cache_control:string|null}[]};
export type Structure = {id:number;kind:"upwell"|"pos";name:string;type_id:number;type_name:string;system_id:number;system_name:string;security_status:number|null;state:string;moon_id?:number|null;moon_name:string|null;services:{name:string;state:string}[]|null;fuel_expires?:string|null;state_timer_start?:string|null;state_timer_end?:string|null;unanchors_at?:string|null;reinforced_until?:string|null;unanchor_at?:string|null;onlined_since?:string|null;reinforce_hour?:number|null;next_reinforce_hour?:number|null;next_reinforce_apply?:string|null;profile_id?:number|null};
export type Overview = {corporation:{id:number;name:string};checked_at:string;complete:boolean;sources:Source[];rows:Structure[]};
export type PosDetail = {id:number;checked_at:string;source:Source["pages"][number];fuels:{type_id:number;name:string;quantity:number}[]|null;settings:Record<string,string|number|boolean>};

export function label(value:string):string{return value.replace(/_/g," ").replace(/^./,letter=>letter.toUpperCase());}
export function remaining(value:string|null|undefined,now:number):string {
  if(!value)return "Not reported";
  const end=Date.parse(value);if(!Number.isFinite(end))return "Not reported";
  if(end<=now)return "Elapsed · awaiting ESI update";
  const minutes=Math.ceil((end-now)/60000),days=Math.floor(minutes/1440),hours=Math.floor(minutes%1440/60);
  return days?`${days}d ${hours}h`:hours?`${hours}h ${minutes%60}m`:`${minutes}m`;
}
export function needsAttention(row:Structure,now:number):boolean {
  const fuel=row.fuel_expires?Date.parse(row.fuel_expires):NaN;
  return new Set(["reinforced","armor_reinforce","hull_reinforce","armor_vulnerable","hull_vulnerable","offline","unanchored","unanchoring","anchoring","onlining","onlining_vulnerable","anchor_vulnerable","deploy_vulnerable"]).has(row.state)
    || Boolean(row.unanchors_at) || Number.isFinite(fuel)&&fuel-now<=7*86400000;
}
export function activeTimer(row:Structure):{name:string;at:string}|null {
  if(row.kind==="pos")return row.reinforced_until?{name:"Reinforcement ends",at:row.reinforced_until}:null;
  return row.state_timer_end?{name:"State changes",at:row.state_timer_end}:null;
}
