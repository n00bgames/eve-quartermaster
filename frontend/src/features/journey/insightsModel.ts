const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export type InsightRow={id?:number|null;name:string;visits:number;segments:number;systems:number;seconds:number;kills:number|null;losses:number|null;first_at?:string;last_at?:string};
export type InsightRank={rows:InsightRow[];total:number;offset:number;limit:number;truncated:boolean};
export type InsightReport={scope:{from_at:string;to_at:string;metric:string;cohort?:string};checked_at:string;combat_available:boolean;
 summary:{visits:number;systems:number;segments:number;seconds:number;kills:number|null;losses:number|null};
 hulls:InsightRank;systems?:InsightRank;pilots?:InsightRank;cohort?:{id:number;name:string;eve_id:number}[];first_at?:string;last_at?:string;notices:string[]};
export type InsightScope={cohort:'account'|'fleet'|'selected';character_ids:number[];period:'all'|'range';from_at?:string;to_at?:string;
 ship_type_id:number|null;system_id:number|null;metric:'visits'|'seconds'|'kills'|'losses';limit:number;offset:number;
 exclude_types:number[];exclude_groups:number[];exclude_capitals:boolean;exclude_supercapitals:boolean;show_systems:boolean;show_pilots:boolean};
export type ViewMeta={id:number;title:string;is_public:boolean;created_at:string;expires_at:string;share_path:string|null};
export type SavedView=ViewMeta&{report:InsightReport;preview_hash:string};
export type InsightOptions={groups:{id:number;name:string}[];types:{type_id:number;name:string}[];pilots:{id:number;name:string;eve_id:number}[];enabled_ids:number[]};

export function insightScope(query:string,fleet=false):InsightScope{
 const dates=new URLSearchParams(query);
 return {cohort:fleet?'fleet':'account',character_ids:[],period:'all',from_at:dates.get('from_at')??undefined,to_at:dates.get('to_at')??undefined,
  ship_type_id:null,system_id:null,metric:'visits',limit:10,offset:0,exclude_types:[],exclude_groups:[],exclude_capitals:false,exclude_supercapitals:false,show_systems:false,show_pilots:false};
}

/** Private downloads send scope in the body, with the normal account auth. */
export async function exportInsights(scope:InsightScope,format:'json'|'csv'){
 const token=localStorage.getItem('eq_access_token'),abort=new AbortController(),timer=window.setTimeout(()=>abort.abort(),120000);
 try{
  const response=await fetch(`${API_BASE}/journey/insights/export/${format}`,{method:'POST',credentials:'include',signal:abort.signal,
   headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify(scope)});
  if(!response.ok)throw new Error(`Export failed (${response.status}).`);
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');link.href=url;link.download=`eqm-journey-insights.${format}`;link.click();window.setTimeout(()=>URL.revokeObjectURL(url),30000);
 }finally{window.clearTimeout(timer);}
}

export const viewUrl=(path:string)=>`${window.location.origin}${window.location.pathname}${path}`;
