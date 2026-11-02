import {useEffect, useId, useState} from "react";
import {RefreshCw, TrendingDown, TrendingUp, Users} from "lucide-react";
import type {ApiClient} from "./types";
import "./membership.css";

type Change = {change:number;percent:number|null;baseline_count?:number;baseline_at:string;observed_at?:string;elapsed_days?:number};
type Point = {observed_at:string;member_count:number|null;corporation_count:number|null;source:string};
export type Membership = {
  monitor:{enabled:boolean;status:string;next_poll_at:string|null;last_attempt_at:string|null;last_success_at:string|null;notice:string|null};
  member_count:number|null;observed_at:string|null;stale:boolean;direction:string;previous:Change|null;
  corporation_count:number|null;windows:({days:number;state:string}&Partial<Change>)[];
  history:Point[];history_limited:boolean;notice:string;changes_limited:boolean;
  latest_attempt:{observed_at:string;member_count:number|null;corporation_count:number|null;resolved_corporations:number;known_member_count:number|null}|null;
  corporation_changes:{observed_at:string;previous_at:string;added:{eve_id:number;name:string}[];removed:{eve_id:number;name:string}[]}[];
};

const integer=new Intl.NumberFormat(undefined,{maximumFractionDigits:0});
const signed=(n:number)=>`${n>0?"+":""}${integer.format(n)}`;
const time=(s:string|null)=>s?new Date(s).toLocaleString():"Not yet observed";
const date=(s:string)=>new Date(s).toISOString().slice(0,10);
const changeClass=(n:number|undefined)=>n===undefined?"":n>0?"membership-gain":n<0?"membership-loss":"";

export function IntelMembership({api,subjectId,kind,fromAt,toAt}:{api:ApiClient;subjectId:number;kind:string;fromAt:string;toAt:string}) {
  const [data,setData]=useState<Membership|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [revision,setRevision]=useState(0);
  useEffect(()=>{
    let stopped=false;
    let timer:number|undefined;
    const abort=new AbortController();
    setData(null);setError("");
    async function load(){
      try {
        const params=new URLSearchParams({from_at:fromAt,to_at:toAt});
        const next=await api<Membership>(`/intel/subjects/${subjectId}/membership?${params}`,{signal:abort.signal});
        if(stopped)return;
        setData(next);
        if(["queued","running"].includes(next.monitor.status))timer=window.setTimeout(()=>void load(),3000);
      }catch(err){if(!stopped)setError(err instanceof Error?err.message:"Membership counts could not be loaded.");}
    }
    void load();
    return()=>{stopped=true;abort.abort();window.clearTimeout(timer);};
  },[api,subjectId,fromAt,toAt,revision]);

  async function update(enabled?:boolean){
    setBusy(true);setError("");
    try {
      await api(`/intel/subjects/${subjectId}/membership/${enabled===undefined?"refresh":"monitoring"}`,{
        method:enabled===undefined?"POST":"PUT",
        ...(enabled===undefined?{}:{body:JSON.stringify({enabled})}),
      });
      setRevision(n=>n+1);
    }catch(err){setError(err instanceof Error?err.message:"Membership request failed.");}
    finally{setBusy(false);}
  }

  const active=!!data&&["queued","running"].includes(data.monitor.status);
  return <section className="panel stacked intel-membership" aria-label="Organization membership trends">
    <div className="section-heading"><h3><Users size={18}/> Organization strength</h3>
      <button disabled={busy||active||!data} onClick={()=>void update()}><RefreshCw size={14}/>{active?"Checking counts…":"Refresh counts"}</button>
    </div>
    {error&&<p role="alert" className="mini-alert">{error}</p>}
    {!data&&!error&&<p role="status" className="muted">Loading membership history…</p>}
    {data&&<>
      <div className="membership-headline">
        <div><small>Public character count</small><strong className="membership-total">{data.member_count===null?"Unknown":integer.format(data.member_count)}</strong>
          <small>As observed {time(data.observed_at)}{data.stale?" · stale":""}</small>
        </div>
        <div className={`membership-direction ${changeClass(data.previous?.change)}`}>
          {data.direction==="gaining"?<TrendingUp size={24}/>:data.direction==="losing"?<TrendingDown size={24}/>:null}
          <strong>{data.direction==="insufficient_history"?"Building history":data.direction==="gaining"?"Gaining members":data.direction==="losing"?"Losing members":"Unchanged"}</strong>
          <small>{data.previous?`${signed(data.previous.change)} since ${time(data.previous.baseline_at)}`:"Two separate observed days are needed for a trend."}</small>
        </div>
        {kind==="alliance"&&<div><small>Member corporations</small><strong className="membership-total">{data.corporation_count===null?"Unknown":integer.format(data.corporation_count)}</strong><small>Latest observed corporation list</small></div>}
      </div>
      <div className="membership-windows">{data.windows.map(w=><div key={w.days}>
        <small>{w.days}-day net change</small><strong className={changeClass(w.change)}>{w.change===undefined||w.change===null?"—":signed(w.change)}</strong>
        <small>{w.state==="available"?`${w.percent===null?"Percentage unavailable":`${w.percent!>0?"+":""}${w.percent}%`} · baseline ${time(w.baseline_at??null)}`:"No suitable baseline yet"}</small>
      </div>)}</div>
      {data.monitor.notice&&<p className="mini-alert">{data.monitor.notice}</p>}
      {data.latest_attempt?.member_count===null&&kind==="alliance"&&<p className="muted">Latest census: {data.latest_attempt.resolved_corporations} of {data.latest_attempt.corporation_count} corporation counts resolved. {data.latest_attempt.known_member_count===null?"No pilot subtotal available.":`${integer.format(data.latest_attempt.known_member_count)} characters in the resolved corporations; this is not the alliance total.`}</p>}
      <MembershipChart points={data.history}/>
      <label className="membership-monitor"><input type="checkbox" checked={data.monitor.enabled} disabled={busy} onChange={e=>void update(e.target.checked)}/> Monitor daily</label>
      <p className="muted">Shared monitoring for this Intel workspace. Next check: {data.monitor.next_poll_at?time(data.monitor.next_poll_at):"Not scheduled"}. Pausing keeps recorded history. A manual refresh does not enable daily monitoring.</p>
      <p className="muted">{data.notice}</p>
      {data.history_limited&&<p className="mini-alert">History is capped. Narrow the report dates to inspect a complete interval.</p>}
      <details><summary>Observed counts ({data.history.length} days in the report window)</summary>
        <div className="intel-table-wrap"><table><thead><tr><th>Observed UTC</th><th>Characters</th>{kind==="alliance"&&<th>Corporations</th>}<th>Source</th></tr></thead><tbody>
          {[...data.history].reverse().map(p=><tr key={p.observed_at}><td>{new Date(p.observed_at).toISOString()}</td><td>{p.member_count===null?"Incomplete":integer.format(p.member_count)}</td>{kind==="alliance"&&<td>{p.corporation_count}</td>}<td>{p.source==="retained_public_profile"?"Retained public profile":"Public ESI census"}</td></tr>)}
        </tbody></table></div>
      </details>
      {kind==="alliance"&&<details><summary>Corporation movements ({data.corporation_changes.length} observations)</summary>
        {!data.corporation_changes.length&&<p className="muted">No observed corporation-list changes in this window.</p>}
        {data.corporation_changes.map(c=><div className="membership-movement" key={c.observed_at}><strong>{time(c.observed_at)}</strong><small>Compared with {time(c.previous_at)}; exact move times are unknown.</small>
          {[...c.added.map(org=>({...org,action:"Added"})),...c.removed.map(org=>({...org,action:"Removed"}))].map(org=><p key={`${org.action}:${org.eve_id}`}>{org.action}: <a href={`https://zkillboard.com/corporation/${org.eve_id}/`} target="_blank" rel="noreferrer">{org.name}</a></p>)}
        </div>)}{data.changes_limited&&<p className="muted">Comparing the latest 30 daily intervals in this report. Narrow the date range to inspect older corporation movements.</p>}
      </details>}
    </>}
  </section>;
}

function MembershipChart({points}:{points:Point[]}) {
  const id=useId();
  const good=points.filter(p=>p.member_count!==null);
  if(!good.length)return <p className="muted">No complete member counts in the selected report dates. Refresh counts to begin recording.</p>;
  const start=new Date(points[0].observed_at).getTime(),end=new Date(points[points.length-1].observed_at).getTime();
  const values=good.map(p=>p.member_count!);
  const minimum=Math.max(0,Math.floor(Math.min(...values)*0.95)),maximum=Math.max(minimum+1,Math.ceil(Math.max(...values)*1.05));
  const x=(p:Point)=>48+(new Date(p.observed_at).getTime()-start)/Math.max(86400000,end-start)*704;
  const y=(p:Point)=>160-(p.member_count!-minimum)/(maximum-minimum)*135;
  return <figure className="membership-chart"><svg viewBox="0 0 800 200" role="img" aria-labelledby={id}>
    <title id={id}>Observed character counts, {date(points[0].observed_at)} through {date(points[points.length-1].observed_at)}. Missing data and gaps over two days are not connected.</title>
    <line x1="48" y1="160" x2="752" y2="160"/><line x1="48" y1="25" x2="752" y2="25"/>
    <text x="0" y="30">{integer.format(maximum)}</text><text x="0" y="165">{integer.format(minimum)}</text>
    {points.map((p,i)=>{
      const prev=points[i-1];
      if(p.member_count===null)return <text key={p.observed_at} x={x(p)} y="185" textAnchor="middle"><title>Incomplete count on {date(p.observed_at)}</title>?</text>;
      const connect=prev?.member_count!==null&&prev&&new Date(p.observed_at).getTime()-new Date(prev.observed_at).getTime()<=2*86400000;
      return <g key={p.observed_at}>{connect&&<line className="membership-series" x1={x(prev)} y1={y(prev)} x2={x(p)} y2={y(p)}/>}<circle cx={x(p)} cy={y(p)} r="3.5"><title>{date(p.observed_at)}: {integer.format(p.member_count)} characters</title></circle></g>;
    })}
    <text x="48" y="198">{date(points[0].observed_at)}</text><text x="752" y="198" textAnchor="end">{date(points[points.length-1].observed_at)}</text>
  </svg><figcaption className="muted">Daily last complete observation; gaps stay visible. The chart uses the report date range. Counts include alts and inactive characters.</figcaption></figure>;
}
