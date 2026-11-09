import {useEffect,useState} from "react";
import {Building2,RefreshCw,Shield,Timer} from "lucide-react";
import {activeTimer,label,needsAttention,remaining,type Overview,type PosDetail,type Structure,type Source} from "./model";
import "./structures.css";
import {StructureTimerSettings} from "./StructureTimerSettings";
import {ManualPosPanel} from "./ManualPosPanel";

type Api = <T>(path:string,options?:RequestInit)=>Promise<T>;
type Link = {token_id:number;character_name:string;corporation_name:string;upwell_authorized:boolean;pos_authorized:boolean};
type DateFormat = (value?:string|null)=>string;

export function StructuresPage({api,formatDateTime}:{api:Api;formatDateTime:DateFormat}) {
  const [links,setLinks]=useState<Link[]|null>(null),[token,setToken]=useState<number|null>(null),[error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();
    void api<{characters:Link[]}>("/structures/links",{signal:controller.signal}).then(data=>{
      if(controller.signal.aborted)return;setLinks(data.characters);
      setToken(data.characters.find(c=>c.upwell_authorized||c.pos_authorized)?.token_id??data.characters[0]?.token_id??null);
    }).catch(err=>{if(!controller.signal.aborted)setError(err instanceof Error?err.message:"Unable to load linked characters.");});
    return ()=>controller.abort();
  },[api]);
  const selected=links?.find(c=>c.token_id===token);
  return <section className="panel stacked structures-page" aria-label="Owned structures">
    <div className="section-heading"><div><h3><Building2 size={22}/> Structures</h3><p className="muted">Corporation structures and POS towers · ESI status and private manual tracking</p></div></div>
    <ManualPosPanel api={api} date={formatDateTime}/>
    <h4 className="structures-esi-heading">ESI corporation structures</h4>
    {error&&<p className="mini-alert" role="alert">{error}</p>}
    {links===null&&!error&&<p role="status">Loading your linked characters…</p>}
    {links?.length===0&&<div className="notice">Link a corporation character through EVE SSO in ESI Sync to get started. No structures are required yet.</div>}
    {!!links?.length&&<label className="structures-character">Corporation character<select value={token??""} onChange={event=>setToken(Number(event.target.value))}>{links.map(link=><option key={link.token_id} value={link.token_id}>{link.character_name} · {link.corporation_name}</option>)}</select></label>}
    {selected&&<StructureList key={selected.token_id} link={selected} api={api} date={formatDateTime}/>}
  </section>;
}

function StructureList({link,api,date}:{link:Link;api:Api;date:DateFormat}) {
  const [data,setData]=useState<Overview|null>(null),[error,setError]=useState(""),[loading,setLoading]=useState(false),[reload,setReload]=useState(0);
  const [search,setSearch]=useState(""),[kind,setKind]=useState("all"),[attention,setAttention]=useState(false),[now,setNow]=useState(Date.now());
  const [authBusy,setAuthBusy]=useState(false),[authError,setAuthError]=useState("");
  const authorized=link.upwell_authorized||link.pos_authorized;
  useEffect(()=>{const clock=window.setInterval(()=>setNow(Date.now()),30000);return ()=>clearInterval(clock);},[]);
  useEffect(()=>{const poll=window.setInterval(()=>{if(!document.hidden)setReload(n=>n+1);},300000);return ()=>clearInterval(poll);},[]);
  useEffect(()=>{if(!authorized)return;const controller=new AbortController();setLoading(true);setError("");
    void api<Overview>(`/structures/tokens/${link.token_id}`,{signal:controller.signal}).then(result=>{if(!controller.signal.aborted)setData(result);})
      .catch(err=>{if(!controller.signal.aborted)setError(err instanceof Error?err.message:"Unable to read structures.");})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});return ()=>controller.abort();
  },[api,link.token_id,authorized,reload]);
  async function authorize(){setAuthBusy(true);setAuthError("");try{
    const result=await api<{ready:boolean;url?:string;message?:string}>(`/structures/tokens/${link.token_id}/auth-url`);
    if(result.ready&&result.url)window.location.assign(result.url);else setAuthError(result.message??"EVE SSO must be configured in Settings first.");
  }catch(err){setAuthError(err instanceof Error?err.message:"Unable to start EVE authorization.");}finally{setAuthBusy(false);}}
  const rows=(data?.rows??[]).filter(row=>(kind==="all"||row.kind===kind)&&(!attention||needsAttention(row,now))&&[row.name,row.type_name,row.system_name,row.moon_name??"",row.state,String(row.id)].some(value=>value.toLowerCase().includes(search.toLowerCase())));
  return <>
    <div className="structures-actions"><p className="muted">Use your Station Manager character for Upwell structures, or a Director for both lists and POS fuel.</p><div className="button-row"><button onClick={()=>void authorize()} disabled={authBusy}>{authBusy?"Opening EVE SSO…":"Authorize Structures"}</button><button onClick={()=>setReload(n=>n+1)} disabled={loading||!authorized}><RefreshCw size={14}/>{loading?"Checking ESI…":"Refresh"}</button></div></div>
    {authError&&<p role="alert" className="mini-alert">{authError}</p>}
    {!authorized&&<div className="notice">Authorize Structures for {link.character_name} to read owned Upwell structures and POS towers. Enable <code>esi-corporations.read_structures.v1</code> and <code>esi-corporations.read_starbases.v1</code> on your EVE developer application first.</div>}
    {error&&<div className="mini-alert" role="alert">{error}{data&&" Previous results remain below; they have not been refreshed."}</div>}
    {data&&<>
      <div className="structures-summary"><div><strong>{data.corporation.name}</strong><span>{data.rows.length} structures reported{!data.complete?" · partial coverage":""}</span></div><div><strong>{data.rows.filter(row=>row.kind==="upwell").length}</strong><span>Upwell</span></div><div><strong>{data.rows.filter(row=>row.kind==="pos").length}</strong><span>POS towers</span></div><div><strong>{data.rows.filter(row=>needsAttention(row,now)).length}</strong><span>Need attention</span></div></div>
      <div className="structures-sources">{data.sources.map(source=><SourceStatus key={source.kind} source={source} date={date}/>)}<p className="muted">Checked {date(data.checked_at)}. ESI can cache these readings for up to one hour. This view checks every five minutes while visible.</p></div>
      <div className="structures-filters"><label>Find a structure<input value={search} onChange={event=>setSearch(event.target.value)} placeholder="Name, type, system or ID"/></label><label>Show<select aria-label="Structure type" value={kind} onChange={event=>setKind(event.target.value)}><option value="all">All structures</option><option value="upwell">Upwell</option><option value="pos">POS towers</option></select></label><label className="structures-check"><input type="checkbox" checked={attention} onChange={event=>setAttention(event.target.checked)}/>Needs attention</label></div>
      {!rows.length&&<div className="notice">{data.rows.length?"No structures match these filters.":data.complete?"No owned structures reported yet. Once your tower appears in ESI, it will show here.":"No structures returned from the available sources. Resolve the access messages above to check the missing lists."}</div>}
      <div className="structures-grid">{rows.map(row=><StructureCard key={`${row.kind}-${row.id}`} row={row} tokenId={link.token_id} api={api} date={date} now={now} revision={data.checked_at}/>)}</div>
    </>}
  </>;
}

function SourceStatus({source,date}:{source:Source;date:DateFormat}) {
  const dates=source.pages.map(page=>page.response_date).filter((at):at is string=>Boolean(at));
  const oldest=dates.sort((a,b)=>Date.parse(a)-Date.parse(b))[0];
  return <p className={source.status==="ok"?"muted":"scope-warn"}><strong>{source.kind==="pos"?"POS towers":"Upwell"}:</strong> {source.status==="ok"?`Available${oldest?` · ESI response ${date(oldest)}`:" · ESI response time not reported"}`:source.message??label(source.status)}{source.required_scope&&<> <code>{source.required_scope}</code></>}</p>;
}

function Time({name,at,date,now}:{name:string;at?:string|null;date:DateFormat;now:number}) {
  return <div className="structures-time"><span>{name}</span><strong>{remaining(at,now)}</strong>{at&&<time dateTime={at}>{date(at)} · <span title="EVE time">{new Date(at).toISOString().replace("T"," ").replace(".000Z"," UTC")}</span></time>}</div>;
}

function StructureCard({row,tokenId,api,date,now,revision}:{row:Structure;tokenId:number;api:Api;date:DateFormat;now:number;revision:string}) {
  const timer=activeTimer(row),warn=needsAttention(row,now);
  return <article className={`structures-card${warn?" structures-attention":""}`}>
    <header><span className="structures-kind"><Shield size={14}/>{row.kind==="pos"?"POS tower":"Upwell"}</span><span className={warn?"scope-warn":"scope-ok"}>{label(row.state)}</span></header>
    <h4>{row.name}</h4><p className="muted">{row.type_name} · {row.system_name}{row.security_status!=null&&` (${row.security_status.toFixed(1)})`}</p><small className="muted">ID {row.id}{row.moon_id?` · ${row.moon_name??`Moon ${row.moon_id}`}`:""}</small>
    <div className="structures-timers">{row.kind==="upwell"?<Time name="Fuel expires" at={row.fuel_expires} date={date} now={now}/>:<div className="structures-time"><span>Fuel on hand</span><strong>See fuel & settings below</strong><small>ESI does not report POS fuel expiry.</small></div>}{timer&&<Time name={timer.name} at={timer.at} date={date} now={now}/>} {row.unanchors_at&&<Time name="Unanchors" at={row.unanchors_at} date={date} now={now}/>}</div>
    {row.kind==="upwell"&&<><div className="structures-services">{row.services?.length?row.services.map((service,index)=><span key={`${service.name}-${index}`} className={service.state==="online"?"scope-ok":"scope-warn"}>{service.name} · {label(service.state)}</span>):<span className="muted">No services reported.</span>}</div><details><summary>Reinforcement settings</summary><p>Configured reinforcement hour: {row.reinforce_hour==null?"Not reported":`${String(row.reinforce_hour).padStart(2,"0")}:00 UTC`}. This setting is separate from an active state timer.</p>{row.next_reinforce_hour!=null&&<p>Requested hour: {String(row.next_reinforce_hour).padStart(2,"0")}:00 UTC · applies {row.next_reinforce_apply?date(row.next_reinforce_apply):"at a time ESI did not report"}.</p>}{row.state_timer_start&&<p>Current state began {date(row.state_timer_start)}.</p>}</details></>}
    <StructureTimerSettings api={api} source={row.kind} sourceId={String(row.id)} tokenKey={tokenId} revision={revision}/>
    {row.kind==="pos"&&<>{row.onlined_since&&<p className="muted">Online since {date(row.onlined_since)}</p>}{row.unanchor_at&&<p className="scope-warn">Unanchoring started {date(row.unanchor_at)}. Completion time is not reported.</p>}<PosFuel key={revision} id={row.id} tokenId={tokenId} api={api} date={date}/></>}
  </article>;
}

function PosFuel({id,tokenId,api,date}:{id:number;tokenId:number;api:Api;date:DateFormat}) {
  const [open,setOpen]=useState(false),[attempt,setAttempt]=useState(0),[data,setData]=useState<PosDetail|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  useEffect(()=>{if(!open)return;const controller=new AbortController();setBusy(true);setError("");
    void api<PosDetail>(`/structures/tokens/${tokenId}/pos/${id}`,{signal:controller.signal}).then(result=>{if(!controller.signal.aborted)setData(result);})
      .catch(err=>{if(!controller.signal.aborted)setError(err instanceof Error?err.message:"Unable to read POS fuel.");})
      .finally(()=>{if(!controller.signal.aborted)setBusy(false);});return ()=>controller.abort();
  },[api,open,attempt,id,tokenId]);
  return <div className="structures-pos-fuel"><button aria-expanded={open} onClick={()=>setOpen(value=>!value)}><Timer size={14}/>{open?"Hide":"View"} fuel & settings</button>{open&&<div className="stacked">{busy&&<p role="status">Reading POS fuel…</p>}{error&&<p className="mini-alert" role="alert">{error} <button onClick={()=>setAttempt(n=>n+1)}>Retry</button></p>}{data&&<><p className="muted">ESI response {data.source.response_date?date(data.source.response_date):"time not reported"} · checked {date(data.checked_at)}</p>{data.fuels===null?<p>Fuel quantities not reported by ESI.</p>:data.fuels.length?<dl className="structures-fuels">{data.fuels.map(fuel=><div key={fuel.type_id}><dt>{fuel.name}</dt><dd>{fuel.quantity.toLocaleString()}</dd></div>)}</dl>:<p>No fuel entries reported by ESI.</p>}<details><summary>Access & defense settings</summary><dl className="structures-fuels">{Object.entries(data.settings).map(([key,value])=><div key={key}><dt>{label(key)}</dt><dd>{typeof value==="boolean"?(value?"Yes":"No"):typeof value==="string"?label(value):value}</dd></div>)}</dl></details></>}</div>}</div>;
}
