import {useEffect,useState} from "react";
import {BarChart3,RefreshCw} from "lucide-react";
import {api} from "../../lib/api";
import {analyticsQuery,observedSpan,rankPercent,type JourneyAnalyticsData,type Ranking,type RankRow} from "./analyticsModel";
import "./analytics.css";

const number=(value:number|null|undefined)=>value==null?"Unavailable":value.toLocaleString();

export function JourneyAnalytics({character,query,refresh,onSelectCharacter}:{character:number;query:string;refresh:number;onSelectCharacter:(id:number)=>void}) {
  const [open,setOpen]=useState(true),[scope,setScope]=useState<"account"|"character">("account"),[period,setPeriod]=useState<"all"|"range">("all");
  const [order,setOrder]=useState<"visits"|"span">("visits"),[limit,setLimit]=useState(10);
  const request=analyticsQuery(scope,character,period,query,order,limit);
  return <section className="journey-analytics stacked" aria-label="Journey analytics">
    <header className="section-heading"><div><h4><BarChart3 size={20}/> Journey analytics</h4><p className="muted">Stored travel and imported combat · private to your account</p></div><button type="button" aria-expanded={open} onClick={()=>setOpen(value=>!value)}>{open?"Hide analytics":"Show analytics"}</button></header>
    {open&&<><div className="journey-analytics-controls">
      <label>Pilot scope<select aria-label="Analytics pilot scope" value={scope} onChange={event=>setScope(event.target.value as typeof scope)}><option value="account">All my pilots</option><option value="character" disabled={!character}>Selected journey pilot</option></select></label>
      <label>History scope<select aria-label="Analytics history scope" value={period} onChange={event=>setPeriod(event.target.value as typeof period)}><option value="all">All stored history</option><option value="range">Selected journey dates (UTC)</option></select></label>
      <label>Rank flown hulls by<select aria-label="Rank flown hulls by" value={order} onChange={event=>setOrder(event.target.value as typeof order)}><option value="visits">Observed visits</option><option value="span">Confirmed observation span</option></select></label>
      <label>Rows per ranking<select aria-label="Rows per analytics ranking" value={limit} onChange={event=>setLimit(Number(event.target.value))}>{[10,25,50].map(value=><option key={value} value={value}>Top {value}</option>)}</select></label>
    </div>
    {request?<AnalyticsResults key={`${request}:${refresh}`} query={request} onChoose={id=>{setScope("character");onSelectCharacter(id);}}/>:<p>Select a linked journey pilot to view their analytics.</p>}
    </>}
  </section>;
}

function AnalyticsResults({query,onChoose}:{query:string;onChoose:(id:number)=>void}) {
  const [data,setData]=useState<JourneyAnalyticsData|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(true),[reload,setReload]=useState(0);
  useEffect(()=>{const timer=window.setInterval(()=>{if(!document.hidden)setReload(value=>value+1);},60000);return ()=>clearInterval(timer);},[]);
  useEffect(()=>{const controller=new AbortController();setLoading(true);setError("");
    void api<JourneyAnalyticsData>(`/journey/analytics?${query}`,{signal:controller.signal}).then(result=>{if(!controller.signal.aborted)setData(result);})
      .catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:"Unable to load journey analytics.");})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[query,reload]);
  const spanOrder=data?.scope.ship_order==="span";
  const flyMetric=spanOrder?"observed_seconds":"visits";
  return <>
    <div className="journey-analytics-refresh"><p className="muted">{data?`${data.scope.name} · ${data.scope.period==="all"?"All stored history":`${data.scope.from_at.slice(0,10)} → ${data.scope.to_at.slice(0,10)} (end exclusive), UTC`} · checked ${new Date(data.checked_at).toISOString().replace("T"," ").slice(0,19)} UTC`:"Loading full-history aggregates…"}</p><button type="button" disabled={loading} onClick={()=>setReload(value=>value+1)}><RefreshCw size={14}/>{loading?"Reading analytics…":"Refresh analytics"}</button></div>
    {error&&<p role="alert" className="mini-alert">{error}{data&&" Previous results remain below and have not refreshed."}</p>}
    {!data&&loading&&<p role="status">Reading stored journey analytics…</p>}
    {data&&<>
      <div className="journey-analytics-metrics">
        <Metric name="Observed visits" value={number(data.summary.visits)}/><Metric name="Unique systems" value={number(data.summary.systems)}/><Metric name="Observed jumps" value={number(data.summary.jumps)}/>
        <Metric name="Confirmed hull span" value={observedSpan(data.summary.observed_seconds)}/><Metric name="Imported kills" value={number(data.summary.kills)}/><Metric name="Imported losses" value={number(data.summary.losses)}/>
      </div>
      <p className="muted journey-analytics-coverage">{number(data.summary.pilots)} linked pilots in scope · {number(data.summary.visits_without_hull)} {data.summary.visits_without_hull===1?"visit has":"visits have"} no recorded hull. All stored rows in scope contribute; replay truncation does not trim these totals.</p>
      <div className="journey-analytics-grid">
        <RankCard title="Systems most visited" help="Observed visits overlapping the selected scope." ranking={data.systems} metric="visits" unit="visits" empty="No journey visits recorded in this scope."/>
        <RankCard title="Ship types most flown" help={`Ranked by ${spanOrder?"confirmed observation span":"observed visits"}; recorded hulls only.`} ranking={data.ships} metric={flyMetric} unit={spanOrder?"confirmed span":"visits"} span={spanOrder}
          detail={row=>`${number(row.visits)} visits · ${observedSpan(row.observed_seconds??0)} confirmed span · ${number(row.segments)} hull segments`} empty="No hull observations recorded in this scope. Enable optional ship recording for future samples."/>
        <RankCard title="Most-flown hulls with kills" help="Recorded hulls with at least one imported kill in this scope. Kill hull comes from the pilot’s attacker entry." ranking={data.combat_ships} metric={flyMetric} unit={spanOrder?"confirmed span":"visits"} span={spanOrder}
          available={data.combat_available} detail={row=>`${number(row.kills)} imported kills · ${number(row.visits)} visits · ${observedSpan(row.observed_seconds??0)} confirmed span`} empty="No recorded hull in this scope has an imported kill."/>
        <RankCard title="Systems with most kills" help="Distinct imported killmails involving the selected pilots, including combat outside recorded journeys." ranking={data.kill_systems} metric="kills" unit="kills" available={data.combat_available} empty="No imported kills in this scope."/>
        <RankCard title="Ship types most lost" help="Destroyed hull from the killmail victim, independently of recorded ship history." ranking={data.lost_ships} metric="losses" unit="losses" available={data.combat_available} empty="No imported losses in this scope."/>
        <RankCard title="Pilots with most jumps" help="Observed system changes without a recorded gap. Select a pilot to view their journey." ranking={data.pilots} metric="jumps" unit="observed jumps" onChoose={onChoose}
          detail={row=>`${number(row.visits)} visits · ${number(row.systems)} systems${data.combat_available?` · ${number(row.kills)} kills / ${number(row.losses)} losses`:""}`} empty="No linked pilots in scope."/>
      </div>
      <details className="journey-analytics-method"><summary>How these rankings are counted</summary><ul>{data.notices.map(notice=><li key={notice}>{notice}</li>)}</ul></details>
      {!data.combat_available&&<p className="notice">Combat rankings require access to Killboard, Battle Reports or Intel Reports. Travel rankings remain available.</p>}
    </>}
  </>;
}

function Metric({name,value}:{name:string;value:string}) {return <div><strong>{value}</strong><span>{name}</span></div>;}

function RankCard({title,help,ranking,metric,unit,span=false,available=true,detail,empty,onChoose}:{title:string;help:string;ranking:Ranking;metric:keyof RankRow;unit:string;span?:boolean;available?:boolean;detail?:(row:RankRow)=>string;empty:string;onChoose?:(id:number)=>void}) {
  const max=Math.max(0,...ranking.rows.map(row=>Number(row[metric])||0));
  return <section className="journey-analytics-card" aria-label={title}><header><h5>{title}</h5><small>{available?`Top ${ranking.rows.length} of ${number(ranking.total)}`:"Unavailable"}</small></header><p className="muted">{help}</p>
    {!available?<p>Combat permission required.</p>:!ranking.rows.length?<p className="journey-analytics-empty">{empty}</p>:<ol>{ranking.rows.map((row,index)=>{const value=Number(row[metric])||0;return <li key={row.character_id??row.system_id??row.ship_type_id??"unknown"}>
      <div className="journey-analytics-rank-heading"><span className="journey-analytics-rank-number">{index+1}</span>{onChoose&&row.character_id?<button type="button" onClick={()=>onChoose(row.character_id!)} title={`View ${row.name} journey`}>{row.name}</button>:<strong className="journey-analytics-rank-name">{row.name}</strong>}
        <span className="journey-analytics-rank-value"><strong>{span?observedSpan(value):number(value)}</strong><small>{unit}</small></span></div>
      {detail&&<p className="muted">{detail(row)}</p>}<div className="journey-analytics-bar" aria-hidden="true"><span style={{width:`${rankPercent(value,max)}%`}}/></div></li>;})}</ol>}
    {available&&ranking.truncated&&<p className="muted">Showing the top {ranking.limit} of {number(ranking.total)} groups. Increase rows above for more; totals include every group.</p>}
  </section>;
}
