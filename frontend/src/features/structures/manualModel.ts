export type ManualReading = {
  name:string; tower_type:string; corporation_name:string; location:string;
  state:"online"|"offline"|"reinforced"|"unknown";
  fuel_blocks:number|null; fuel_per_hour:number; stront_units:number|null; stront_per_hour:number;
  observed_at:string; reinforced_until:string|null; notes:string;
};
export type ManualPos = ManualReading & {id:string;version:number;created_at:string;updated_at:string;source:"manual"};

export const towerPresets = ["Caldari","Amarr","Gallente","Minmatar"].flatMap(race=>
  [{suffix:"",size:"large",fuel:40,stront:400},{suffix:" Medium",size:"medium",fuel:20,stront:200},{suffix:" Small",size:"small",fuel:10,stront:100}]
    .map(size=>({name:`${race} Control Tower${size.suffix}`,label:`${race} · ${size.size}`,fuel:size.fuel,stront:size.stront})));

export function durationHours(hours:number):string {
  if(!Number.isFinite(hours)||hours<0)return "Unknown";
  const minutes=Math.floor(hours*60),days=Math.floor(minutes/1440),h=Math.floor(minutes%1440/60),m=minutes%60;
  return days?`${days}d ${h}h ${m}m`:`${h}h ${m}m`;
}

export function fuelEstimate(row:ManualReading,now:number):{expiresAt:string;blocksLeft:number;hoursLeft:number}|null {
  return row.state==="online"?stockEstimate(row.fuel_blocks,row.fuel_per_hour,row.observed_at,now):null;
}

export function strontEstimate(row:ManualReading,now:number):{expiresAt:string;blocksLeft:number;hoursLeft:number}|null {
  return row.state==="reinforced"?stockEstimate(row.stront_units,row.stront_per_hour,row.observed_at,now):null;
}

function stockEstimate(quantity:number|null,rate:number,observedAt:string,now:number):{expiresAt:string;blocksLeft:number;hoursLeft:number}|null {
  const at=Date.parse(observedAt);
  if(quantity===null||!Number.isFinite(at)||!(rate>0))return null;
  const end=at+quantity/rate*3600000;
  if(!Number.isFinite(end)||Math.abs(end)>8.64e15)return null;
  const hoursLeft=Math.max(0,(end-now)/3600000);
  return {expiresAt:new Date(end).toISOString(),blocksLeft:Math.max(0,Math.floor(quantity-Math.max(0,now-at)/3600000*rate)),hoursLeft};
}

export function reinforcementTimer(row:ManualReading,now:number):{at:string;hoursLeft:number;source:"entered"|"stront estimate"}|null {
  if(row.state!=="reinforced")return null;
  if(row.reinforced_until&&Number.isFinite(Date.parse(row.reinforced_until)))
    return {at:row.reinforced_until,hoursLeft:Math.max(0,(Date.parse(row.reinforced_until)-now)/3600000),source:"entered"};
  const stront=strontEstimate(row,now);
  return stront?{at:stront.expiresAt,hoursLeft:stront.hoursLeft,source:"stront estimate"}:null;
}

export function manualAttention(row:ManualReading,now:number):boolean {
  const fuel=fuelEstimate(row,now);
  return row.state==="reinforced"||row.state==="offline"||Boolean(fuel&&fuel.hoursLeft<=72);
}

export function utcInput(value:string):string {return new Date(value).toISOString().slice(0,16);}
export function fromUtcInput(value:string):string {return new Date(`${value}:00Z`).toISOString();}
