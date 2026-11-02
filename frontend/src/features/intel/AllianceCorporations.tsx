import {useEffect, useState} from "react";
import {ChevronDown, ChevronRight, ExternalLink, RefreshCw, Users} from "lucide-react";
import type {ApiClient, Candidate} from "./types";
import "./alliance-corporations.css";

type Corporation = {eve_id:number;name:string;ticker:string|null;member_count:number|null;ceo_id:number|null;ceo_name:string|null;description:string;state:string|null};
type Roster = {rows:Corporation[];total:number;page:number;page_size:number;fetched_at:string|null;stale:boolean;corporation_count:number;member_count:number|null;known_member_count:number|null;resolved_corporations:number};
type Profile = {name?:string;ticker?:string;member_count?:number;ceo_id?:number;creator_id?:number;alliance_id?:number;description?:string;date_founded?:string;tax_rate?:number;shares?:string;home_station_id?:number;faction_id?:number;url?:string;war_eligible?:boolean;source_errors?:string[];history?:{alliance_id?:number;start_date:string;is_deleted?:boolean}[]};
type Source<T> = {state:string;data:T;fetched_at?:string;last_attempt_at?:string;notice?:string;stale:boolean;ceo_name?:string;creator_name?:string;entity_names?:Record<string,string>};
type Details = {esi:Source<Profile>;zkill:Source<{totals?:Record<string,number>}>};
const number=new Intl.NumberFormat(undefined,{maximumFractionDigits:1});
const value=(n:number|null|undefined)=>n==null?"Unknown":number.format(n);
const stamp=(s:string|null|undefined)=>s?new Date(s).toLocaleString():"Not yet collected";
const zkill=(kind:string,id:number)=>`https://zkillboard.com/${kind}/${id}/`;
const image=(kind:string,id:number,size:number)=>`https://images.evetech.net/${kind}/${id}/${kind==="characters"?"portrait":"logo"}?size=${size}`;
function Person({id,name}:{id?:number|null;name?:string|null}) {
  return id?<a className="alliance-corp-person" href={zkill("character",id)} target="_blank" rel="noreferrer"><img src={image("characters",id,32)} alt="" width={24} height={24} loading="lazy"/>{name||`Character ${id}`}</a>:<>Unknown</>;
}
function Link({kind,id,name}:{kind:string;id:number;name?:string}) {return <a href={zkill(kind,id)} target="_blank" rel="noreferrer">{name||id} <ExternalLink size={12}/></a>;}
function Website({url}:{url?:string}) {
  try {const parsed=new URL(url||"");return ["https:","http:"].includes(parsed.protocol)?<a href={parsed.href} target="_blank" rel="noreferrer">{url} <ExternalLink size={12}/></a>:<>{url||"Not published"}</>;}catch{return <>{url||"Not published"}</>;}
}

export function AllianceCorporations({api,subjectId,revision,onOpen}:{api:ApiClient;subjectId:number;revision?:string;onOpen:(candidate:Candidate)=>void}) {
  const [data,setData]=useState<Roster|null>(null),[search,setSearch]=useState(""),[sort,setSort]=useState("members"),[page,setPage]=useState(1);
  const [expanded,setExpanded]=useState<number|null>(null),[reload,setReload]=useState(0),[error,setError]=useState("");
  useEffect(()=>{
    const abort=new AbortController();let stopped=false;
    setData(null);setError("");
    const timer=window.setTimeout(()=>{
      const params=new URLSearchParams({search,sort,page:String(page)});
      void api<Roster>(`/intel/subjects/${subjectId}/corporations?${params}`,{signal:abort.signal}).then(result=>{if(!stopped)setData(result);}).catch(err=>{if(!stopped)setError(err instanceof Error?err.message:"Member corporations could not be loaded.");});
    },200);
    return()=>{stopped=true;abort.abort();window.clearTimeout(timer);};
  },[api,subjectId,revision,search,sort,page,reload]);
  return <section className="panel stacked alliance-corporations" aria-label="Alliance member corporations">
    <div className="alliance-corp-heading"><div><h3>Alliance member corporations</h3><p className="muted">Public ESI census · {value(data?.corporation_count)} corporations · {value(data?.member_count)} pilots</p></div><button onClick={()=>setReload(n=>n+1)} title="Reload the saved census"><RefreshCw size={14}/> Reload roster</button></div>
    <p className="muted">Checked {stamp(data?.fetched_at)}{data?.stale?" · Refresh needed":""}. Use Collect public history or Refresh counts to fetch a new census. Corporation statistics load when expanded.</p>
    {data&&data.member_count===null&&<p role="status">{data.resolved_corporations} of {data.corporation_count} corporation counts resolved. Known subtotal: {value(data.known_member_count)}. The alliance total remains unknown until every count resolves.</p>}
    <div className="alliance-corp-controls"><label>Find a corporation<input value={search} onChange={e=>{setSearch(e.target.value);setPage(1);setExpanded(null);}} placeholder="Name, ticker or CEO"/></label><label>Sort corporations<select value={sort} onChange={e=>{setSort(e.target.value);setPage(1);setExpanded(null);}}><option value="members">Largest first</option><option value="name">Name</option></select></label></div>
    {error&&<p role="alert">{error}</p>}
    {!data&&!error&&<p role="status">Loading member corporations…</p>}
    {data&&!data.rows.length&&<p>{search?"No matching corporations.":"No member corporations collected. Run Collect public history or Refresh counts to check ESI."}</p>}
    {data?.rows.map(corp=><article key={corp.eve_id} className="alliance-corp-row">
      <button className="alliance-corp-summary" aria-expanded={expanded===corp.eve_id} aria-controls={`corp-details-${subjectId}-${corp.eve_id}`} onClick={()=>setExpanded(expanded===corp.eve_id?null:corp.eve_id)}>
        <img className="alliance-corp-logo" src={image("corporations",corp.eve_id,64)} alt="" width={48} height={48} loading="lazy"/>
        <span className="alliance-corp-synopsis"><strong>{corp.name} {corp.ticker&&<span className="muted">[{corp.ticker}]</span>}</strong><span className="alliance-corp-ceo">{corp.ceo_id&&<img src={image("characters",corp.ceo_id,32)} width={20} height={20} alt="" loading="lazy"/>}CEO · {corp.ceo_name||(corp.ceo_id?`Character ${corp.ceo_id}`:"Unknown")}</span><span className="muted">{corp.description||"No public description published."}</span>{corp.state&&corp.state!=="available"&&<span className="muted">{corp.state==="affiliation_changed"?"Affiliation changed; excluded from alliance total":"Count unavailable; refresh needed"}</span>}</span>
        <span className="alliance-corp-count"><Users size={16}/><strong>{value(corp.member_count)}</strong><span className="muted">members</span></span>{expanded===corp.eve_id?<ChevronDown size={18}/>:<ChevronRight size={18}/>}
      </button>
      {expanded===corp.eve_id&&<div id={`corp-details-${subjectId}-${corp.eve_id}`}><CorporationDetails key={`${subjectId}-${corp.eve_id}`} api={api} subjectId={subjectId} corp={corp} onOpen={onOpen}/></div>}
    </article>)}
    {data&&data.total>50&&<div className="alliance-corp-pagination"><button disabled={page<=1} onClick={()=>{setPage(n=>n-1);setExpanded(null);}}>Previous</button><span>Page {page} of {Math.ceil(data.total/50)} · {data.total} results</span><button disabled={page*50>=data.total} onClick={()=>{setPage(n=>n+1);setExpanded(null);}}>Next</button></div>}
    <p className="muted">Counts are public characters, including alts; they do not measure active or unique players. Current roster and zKill statistics are independent of the dossier’s selected combat-history dates.</p>
  </section>;
}

function CorporationDetails({api,subjectId,corp,onOpen}:{api:ApiClient;subjectId:number;corp:Corporation;onOpen:(candidate:Candidate)=>void}) {
  const [data,setData]=useState<Details|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
  useEffect(()=>{
    let stopped=false;const abort=new AbortController();setBusy(true);setError("");
    void api<Details>(`/intel/subjects/${subjectId}/corporations/${corp.eve_id}${refresh?"/refresh":""}`,{method:refresh?"POST":"GET",signal:abort.signal}).then(result=>{if(!stopped)setData(result);}).catch(err=>{if(!stopped)setError(err instanceof Error?err.message:"Corporation details unavailable.");}).finally(()=>{if(!stopped)setBusy(false);});
    return()=>{stopped=true;abort.abort();};
  },[api,subjectId,corp.eve_id,refresh]);
  const profile=data?.esi.data;
  const totals=data?.zkill.data.totals||{};
  return <div className="alliance-corp-details">
    <div className="alliance-corp-actions"><button onClick={()=>onOpen({kind:"corporation",eve_id:corp.eve_id,name:profile?.name||corp.name})}>Open full Intel report <ChevronRight size={14}/></button><a href={zkill("corporation",corp.eve_id)} target="_blank" rel="noreferrer">Corporation on zKill <ExternalLink size={14}/></a><button disabled={busy} onClick={()=>setRefresh(n=>n+1)}><RefreshCw size={14}/> Refresh details</button></div>
    {busy&&<p role="status">Loading public profile and zKill statistics…</p>}{error&&<p role="alert">{error}</p>}
    {data&&<><div className="alliance-corp-detail-grid"><section><h4>Public corporation profile</h4><p className="muted">ESI · {stamp(data.esi.fetched_at)}{data.esi.stale?" · Stale / unavailable":""}</p>{data.esi.notice&&<p>{data.esi.notice}</p>}
      {profile&&<><dl>
        <dt>Corporation</dt><dd>{profile.name||corp.name} [{profile.ticker||corp.ticker||"Unknown"}] · <Link kind="corporation" id={corp.eve_id}/></dd>
        <dt>CEO</dt><dd><Person id={profile.ceo_id} name={data.esi.ceo_name||(profile.ceo_id===corp.ceo_id?corp.ceo_name:undefined)}/></dd>
        <dt>Founder</dt><dd><Person id={profile.creator_id} name={data.esi.creator_name}/></dd>
        <dt>Members</dt><dd>{value(profile.member_count)}</dd>
        <dt>Founded</dt><dd>{stamp(profile.date_founded)}</dd>
        <dt>Alliance</dt><dd>{profile.alliance_id?<Link kind="alliance" id={profile.alliance_id} name={data.esi.entity_names?.[profile.alliance_id]}/>:"None published"}</dd>
        <dt>Tax rate</dt><dd>{profile.tax_rate==null?"Unknown":`${number.format(profile.tax_rate*100)}%`}</dd>
        <dt>Shares</dt><dd>{profile.shares??"Not published"}</dd>
        <dt>Home station</dt><dd>{profile.home_station_id?(data.esi.entity_names?.[profile.home_station_id]||`Station ${profile.home_station_id}`):"Not published"}</dd>
        <dt>Faction</dt><dd>{profile.faction_id?(data.esi.entity_names?.[profile.faction_id]||`Faction ${profile.faction_id}`):"None published"}</dd>
        <dt>War eligible</dt><dd>{profile.war_eligible==null?"Unknown":profile.war_eligible?"Yes":"No"}</dd>
        <dt>Website</dt><dd><Website url={profile.url}/></dd>
      </dl><p className="alliance-corp-description">{profile.description||"No public description."}</p>{profile.source_errors?.map((s,i)=><p className="muted" key={i}>{s}</p>)}</>}
    </section><section><h4>Latest zKill statistics</h4><p className="muted">zKill · {stamp(data.zkill.fetched_at)}{data.zkill.stale?" · Stale / unavailable":""}</p>{data.zkill.notice&&<p>{data.zkill.notice}</p>}<dl>{[["shipsDestroyed","Ships destroyed"],["shipsLost","Ships lost"],["iskDestroyed","ISK destroyed"],["iskLost","ISK lost"],["dangerRatio","Danger ratio"],["soloRatio","Solo ratio"],["gangRatio","Gang ratio"],["avgGangSize","Average gang size"]].map(([key,label])=><span className="alliance-corp-stat" key={key}><dt>{label}</dt><dd>{value(totals[key])}{key.endsWith("Ratio")&&totals[key]!=null?"%":""}</dd></span>)}</dl><p className="muted">Public upstream aggregate counters, cached for 10 minutes. These are not restricted to the report’s date range. Missing data is unknown, never zero.</p></section></div>
    {!!profile?.history?.length&&<section><h4>Public alliance history</h4><div className="alliance-corp-history">{profile.history.slice(0,100).map((entry,i)=><p key={i}>{stamp(entry.start_date)} · {entry.alliance_id?<Link kind="alliance" id={entry.alliance_id} name={data.esi.entity_names?.[entry.alliance_id]}/>:"No alliance"}{entry.is_deleted?" · Deleted record":""}</p>)}</div>{profile.history.length>100&&<p className="muted">Showing the first 100 public history records. Open the full Intel report for further investigation.</p>}</section>}
    </>}
  </div>;
}
