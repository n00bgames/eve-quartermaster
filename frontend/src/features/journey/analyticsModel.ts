export type RankRow = {name:string;system_id?:number;ship_type_id?:number|null;character_id?:number;eve_id?:number;
  visits?:number;systems?:number;segments?:number;observed_seconds?:number;jumps?:number;kills?:number|null;losses?:number|null};
export type Ranking = {rows:RankRow[];total:number;limit:number;truncated:boolean};
export type JourneyAnalyticsData = {
  scope:{character_id:number|null;name:string;period:"range"|"all";from_at:string;to_at:string;ship_order:"visits"|"span"};
  checked_at:string;combat_available:boolean;
  summary:{pilots:number;visits:number;systems:number;jumps:number;observed_seconds:number;visits_without_hull:number;kills:number|null;losses:number|null};
  systems:Ranking;ships:Ranking;combat_ships:Ranking;kill_systems:Ranking;lost_ships:Ranking;pilots:Ranking;notices:string[];
};

export function analyticsQuery(scope:"account"|"character",character:number,period:"all"|"range",journeyQuery:string,order:"visits"|"span",limit:number):string|null {
  if(scope==="character"&&!character)return null;
  const query=new URLSearchParams(period==="range"?journeyQuery:undefined);
  query.set("period",period);query.set("ship_order",order);query.set("limit",String(limit));
  if(scope==="character")query.set("character_id",String(character));
  else query.delete("character_id");
  return query.toString();
}

export function observedSpan(seconds:number):string {
  if(seconds<60)return `${Math.floor(Math.max(0,seconds))}s`;
  const minutes=Math.floor(seconds/60),hours=Math.floor(minutes/60),days=Math.floor(hours/24);
  return days?`${days}d ${hours%24}h`:hours?`${hours}h ${minutes%60}m`:`${minutes}m`;
}

export function rankPercent(value:number,max:number):number {return max>0?Math.min(100,Math.max(0,value/max*100)):0;}
