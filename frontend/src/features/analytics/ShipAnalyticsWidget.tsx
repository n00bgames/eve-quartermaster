import {useEffect,useState} from "react";
import {TimeSeriesChart} from "../../components/TimeSeriesChart";
import {ReportTable} from "../industryReports/IndustryReportPage";
type Api=<T>(path:string,options?:RequestInit)=>Promise<T>;
type Point={date:string;value:number;ship_types?:number};
type ShipHistory={capitals_visible:boolean;total_ships:number;ship_types:number;observed_at:string|null;notice:string;
 by_type:{type_id:number;item:string;ship_class:string;quantity:number}[];series:Point[];type_series:Point[];selected_type_id:number|null};

export function ShipAnalyticsWidget({api,days,scope,refreshKey}:{api:Api;days:number;scope:string;refreshKey:number}){
 const [data,setData]=useState<ShipHistory|null>(null),[error,setError]=useState(""),[typeId,setTypeId]=useState(""),[ownerScope,setOwnerScope]=useState("all"),[loading,setLoading]=useState(false);
 useEffect(()=>{let active=true;setLoading(true);setError("");const chosen=ownerScope==="all"?"all":scope;
  const [mode,id]=chosen.split(":",2),query=new URLSearchParams({days:String(days),scope:mode});
  if(mode==="corporation"&&id)query.set("corporation_id",id);if(mode==="alliance"&&id)query.set("alliance_id",id);if(typeId)query.set("type_id",typeId);
  void api<ShipHistory>(`/analytics/ships?${query}`).then(next=>{if(active)setData(next);}).catch(err=>{if(active){setData(null);setError(err instanceof Error?err.message:"Ship history unavailable.");}}).finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;};
 },[api,days,scope,refreshKey,typeId,ownerScope]);
 const number=(value:number)=>Math.round(value).toLocaleString();
 return <section className="panel stacked ship-analytics"><h3>Ship inventory Analytics</h3><label>Ship owner scope<select value={ownerScope} onChange={e=>setOwnerScope(e.target.value)}><option value="all">All accessible ship owners</option><option value="selected">Use selected Analytics pilot scope</option></select></label>
 {loading&&<p role="status">Loading ship history…</p>}{error&&<p className="muted" role="status">{error}</p>}
 {data&&<><p className="muted">{data.capitals_visible?"All ship hull sizes":"Subcapital hulls only"} · Capsules excluded · {data.observed_at?`Observed through ${new Date(data.observed_at).toLocaleString()}`:"Run an asset sync or capture an Analytics snapshot to begin history."}</p>
 <div className="status-grid"><article><strong>{number(data.total_ships)}</strong><span>{data.capitals_visible?"Ships":"Subcapital ships"}</span></article><article><strong>{number(data.ship_types)}</strong><span>Distinct ship types</span></article></div>
 <div className="widget-grid"><article className="analytics-widget"><h4>Ship total history</h4>{data.series.length?<TimeSeriesChart ariaLabel="Ship total history" selectedDays={days} formatValue={number} series={[{key:"ships",name:"Ship hulls",color:"#55c7d8",points:data.series}]}/>:<p className="empty">No ship observations yet.</p>}</article>
 <article className="analytics-widget"><h4>Distinct ship type history</h4>{data.series.length?<TimeSeriesChart ariaLabel="Distinct ship type history" selectedDays={days} formatValue={number} series={[{key:"types",name:"Distinct types",color:"#e8b84d",points:data.series.map(p=>({date:p.date,value:p.ship_types??0}))}]}/>:<p className="empty">No ship observations yet.</p>}</article></div>
 <label>Hull type history<select value={typeId} onChange={e=>setTypeId(e.target.value)}><option value="">Choose a hull type</option>{data.by_type.map(row=><option key={row.type_id} value={row.type_id}>{row.item} ({number(row.quantity)})</option>)}</select></label>
 {typeId&&data.selected_type_id===Number(typeId)&&data.type_series.length>0&&<TimeSeriesChart ariaLabel="Selected hull type history" selectedDays={days} formatValue={number} series={[{key:typeId,name:data.by_type.find(row=>String(row.type_id)===typeId)?.item??"Hull type",color:"#79e0a7",points:data.type_series}]}/>}
 <ReportTable title="Latest observed ships by type" rows={data.by_type} fields={["item","ship_class","quantity"]}/><p className="muted">{data.notice}</p></>}
 </section>;
}
