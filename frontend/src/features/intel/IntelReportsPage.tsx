import { useEffect, useRef, useState } from "react";
import { Activity, BookOpen, ChevronRight, Clock, Crosshair, Database, ExternalLink, Globe2, Network, Plus, RefreshCw, Search, ShieldCheck } from "lucide-react";
import type { ApiClient, Association, Candidate, Collection, IntelReport, Note, PrivateData, Ranking, Resolution, Subject } from "./types";
import {IntelNotes} from "./IntelNotes";
import {IntelSightingFields,emptySighting,type SightingDraft} from "./IntelSightingFields";
import {IntelSightingTimeline} from "./IntelSightingTimeline";
import "./intel.css";
const base="/intel";
const number=new Intl.NumberFormat(undefined,{maximumFractionDigits:1});
const stamp=(value:string|null|undefined)=>value?new Date(value).toLocaleString():"Unavailable";
const dateUTC=(value:Date)=>value.toISOString().slice(0,10);
const request=(method:string,body?:unknown):RequestInit=>({method,...(body===undefined?{}:{body:JSON.stringify(body)})});
const isActive=(job:Collection|null|undefined)=>!!job&&["queued","running"].includes(job.status);
const zkill=(kind:string,id:number)=>`https://zkillboard.com/${kind}/${id}/`;
const killLink=(id:number)=>`https://zkillboard.com/kill/${id}/`;
const initialId=()=>Number(window.location.hash.match(/^#intel\/(\d+)$/)?.[1]??0);
const tabs=["Overview","Geography","Timeline","Associates","Evidence","History","Authorized ESI","Notes"] as const;
type Tab=typeof tabs[number];

export function IntelReportsPage({api}:{api:ApiClient}) {
 const [subjects,setSubjects]=useState<Subject[]>([]),[report,setReport]=useState<IntelReport|null>(null);
 const [selectedId,setSelectedId]=useState(initialId),[tab,setTab]=useState<Tab>("Overview");
 const [paste,setPaste]=useState(""),[resolved,setResolved]=useState<Resolution[]>([]),[search,setSearch]=useState("");
 const [busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
 const [from,setFrom]=useState(dateUTC(new Date(Date.now()-90*86400000))),[to,setTo]=useState(dateUTC(new Date())),[pages,setPages]=useState(10);
 const [associateKind,setAssociateKind]=useState("character"),[evidenceIds,setEvidenceIds]=useState<number[]|null>(null),[evidenceTitle,setEvidenceTitle]=useState("");
 const [privateData,setPrivateData]=useState<PrivateData|null>(null),[notes,setNotes]=useState<Note[]>([]);
 const [sighting,setSighting]=useState<SightingDraft>({...emptySighting});
 const pendingSighting=useRef<{signature:string;request_id:string}|null>(null);
 const sequence=useRef(0),currentSubject=useRef(selectedId);currentSubject.current=selectedId;
 const latest=report?.latest_collection;
 function fail(err:unknown){setError(err instanceof Error?err.message:"Request failed");}
 async function lists(){setSubjects(await api<Subject[]>(`${base}/subjects?q=${encodeURIComponent(search)}`));}
 function windowQuery(){return new URLSearchParams({from_at:`${from}T00:00:00Z`,to_at:new Date(new Date(`${to}T00:00:00Z`).getTime()+86400000).toISOString()});}
 async function loadReport(id=selectedId){
  if(!id)return;const seq=++sequence.current;setLoading(true);
  try{const data=await api<IntelReport>(`${base}/subjects/${id}/report?${windowQuery()}`);if(seq===sequence.current&&currentSubject.current===id)setReport(data);}
  finally{if(seq===sequence.current)setLoading(false);}
 }
 async function run(action:()=>Promise<void>){setBusy(true);setError("");setMessage("");try{await action();}catch(err){fail(err);}finally{setBusy(false);}}
 useEffect(()=>{const timer=window.setTimeout(()=>void lists().catch(fail),200);return()=>clearTimeout(timer);},[search]);
 useEffect(()=>{setReport(null);setPrivateData(null);setNotes([]);setEvidenceIds(null);setTab("Overview");if(selectedId)void loadReport(selectedId).catch(fail);},[selectedId]);
 useEffect(()=>{if(selectedId)void loadReport(selectedId).catch(fail);},[from,to]);
 useEffect(()=>{
  if(!latest||!isActive(latest))return;
  let stopped=false;
  const timer=window.setInterval(()=>{void api<Collection>(`${base}/collections/${latest.id}`).then(async job=>{
    if(stopped||currentSubject.current!==job.subject_id)return;
    setReport(old=>old&&old.subject.id===job.subject_id?{...old,latest_collection:job}:old);
    if(!isActive(job)){await loadReport(job.subject_id);await lists();}
  }).catch(err=>{if(!stopped)fail(err);});},3000);
  return()=>{stopped=true;clearInterval(timer);};
 },[latest?.id,latest?.status]);
 useEffect(()=>{
  if(!selectedId)return;
  if(tab==="Authorized ESI"){setPrivateData(null);void api<PrivateData>(`${base}/subjects/${selectedId}/authorized`).then(data=>{if(currentSubject.current===selectedId)setPrivateData(data);}).catch(fail);}
  if(tab==="Notes")void api<Note[]>(`${base}/subjects/${selectedId}/notes`).then(data=>{if(currentSubject.current===selectedId)setNotes(data);}).catch(fail);
 },[tab,selectedId]);
 function open(id:number){sequence.current++;setSelectedId(id);window.history.replaceState({},"",`${window.location.pathname}#intel/${id}`);}
 function sightingPayload(candidate:Candidate){
  if(candidate.kind!=="character"||!sighting.systemText.trim()||!sighting.shipText.trim())return undefined;
  if(!sighting.system||!sighting.ship)throw new Error("Select a matching system and ship type from the search results before recording a sighting.");
  const signature=`${candidate.eve_id}:${sighting.system.id}:${sighting.ship.id}:${sighting.timeText}`;
  if(pendingSighting.current?.signature!==signature)pendingSighting.current={signature,request_id:crypto.randomUUID()};
  return {system_id:sighting.system.id,ship_type_id:sighting.ship.id,request_id:pendingSighting.current.request_id,...(sighting.timeText?{observed_at:new Date(sighting.timeText+"Z").toISOString()}:{})};
 }
 function sightingMessage(candidate:Candidate,saved:boolean){return saved?`Sighting recorded for ${candidate.name}: ${sighting.ship?.name} in ${sighting.system?.name}, at ${sighting.timeText?`${sighting.timeText.replace("T"," ")} UTC`:"the server’s UTC report-run time"}. Kills/losses unchanged.`:`Dossier opened for ${candidate.name}. No sighting recorded.`;}
 async function track(candidate:Candidate){await run(async()=>{
  const seen=sightingPayload(candidate);
  const subject=await api<Subject>(`${base}/subjects`,request("POST",{kind:candidate.kind,eve_id:candidate.eve_id,...(seen?{sighting:seen}:{})}));
  pendingSighting.current=null;
  if(selectedId===subject.id)await loadReport(subject.id);else open(subject.id);
  await lists();setMessage(sightingMessage(subject,!!seen));
 });}
 async function runReport(subject:Candidate&{id:number}){await run(async()=>{
  const seen=sightingPayload(subject);
  if(seen){await api(`${base}/subjects/${subject.id}/sightings`,request("POST",seen));pendingSighting.current=null;}
  if(selectedId===subject.id)await loadReport(subject.id);else open(subject.id);
  await lists();setMessage(sightingMessage(subject,!!seen));
 });}
 async function collect(){if(!selectedId)return;await run(async()=>{
  const job=await api<Collection>(`${base}/subjects/${selectedId}/collect`,request("POST",{days:Math.min(20000,Math.max(1,Math.ceil((Date.now()-new Date(`${from}T00:00:00Z`).getTime())/86400000))),max_pages:pages}));
  setReport(old=>old?{...old,latest_collection:job}:old);await lists();setMessage("Public collection queued. You can leave this page; progress is retained in the database.");
 });}
 function drill(ids:number[]|undefined,title:string){setEvidenceIds(ids??[]);setEvidenceTitle(title);setTab("Evidence");}
 const data=report?.subject.public_data,profile=data?.esi?.data,badges=data?.zkill?.data?.badges??[],summary=report?.summary;
 const evidence=(summary?.evidence??[]).filter(row=>!evidenceIds||evidenceIds.includes(row.id));
 return <section className="intel-page">
  <header className="panel intel-header"><div><span className="intel-eyebrow">INTELLIGENCE / EVIDENCE</span><h2><Search size={25}/> Intel Reports</h2><p>Investigate combat history, recurring associates, and operating patterns.</p></div><span className="intel-access"><ShieldCheck size={16}/> Restricted staff workspace</span></header>
  {error&&<div className="mini-alert" role="alert">{error}</div>}{message&&<div className="notice inline" role="status">{message}</div>}
  <div className="intel-layout"><aside className="intel-sidebar">
   <section className="panel stacked"><div><h3>Open a dossier</h3><p className="muted">Characters, corporations, alliances. Subjects do not need to be synced to EQM.</p></div>
    <label>Paste names or zKill entity URLs<textarea rows={3} maxLength={30000} value={paste} onChange={event=>setPaste(event.target.value)} placeholder={"Pilot Name\nCorporation Name\nhttps://zkillboard.com/alliance/…/"}/></label>
    <IntelSightingFields api={api} value={sighting} onChange={setSighting} disabled={busy}/>
    <button className="intel-primary" disabled={busy||!paste.trim()} onClick={()=>void run(async()=>{const result=await api<{rows:Resolution[];warnings:string[]}>(`${base}/resolve`,request("POST",{text:paste}));setResolved(result.rows);setMessage(result.warnings.join(" "));})}><Search size={15}/> Resolve names</button>
    <div className="intel-resolutions">{resolved.map((row,index)=><article key={index}><strong>{row.input}</strong>{row.state==="unresolved"?<small>No exact match. Check spelling or use a zKill entity URL.</small>:<>{row.state==="ambiguous"&&<small>Choose the intended entity:</small>}{row.candidates.map(candidate=><button key={`${candidate.kind}:${candidate.eve_id}`} disabled={busy} onClick={()=>void track(candidate)}><span>{candidate.name}<small>{candidate.kind}</small></span><ChevronRight size={16}/></button>)}</>}</article>)}</div>
   </section>
   <section className="panel stacked"><h3>Saved subjects</h3><label>Search dossiers<input value={search} onChange={event=>setSearch(event.target.value)} placeholder="Name"/></label><div className="intel-subjects">{subjects.map(subject=><button className={selectedId===subject.id?"selected":""} key={subject.id} disabled={busy} onClick={()=>void runReport(subject)}><span className={`intel-kind kind-${subject.kind}`}>{subject.kind}</span><strong>{subject.name}</strong><small>{subject.latest_collection?`${subject.latest_collection.status} · ${stamp(subject.latest_collection.updated_at)}`:"No collection yet"}</small></button>)}{!subjects.length&&<p className="muted">Resolve an entity to start a dossier.</p>}</div></section>
  </aside>
  <div className="intel-main">{report?<>
   <section className="panel stacked"><div className="intel-identity"><img alt="" src={report.subject.kind==="character"?`https://images.evetech.net/characters/${report.subject.eve_id}/portrait?size=128`:`https://images.evetech.net/${report.subject.kind==="corporation"?"corporations":"alliances"}/${report.subject.eve_id}/logo?size=128`}/><div><span className="intel-kind">{report.subject.kind} · {report.subject.eve_id}</span><h2>{report.subject.name}</h2><div className="intel-badges">{badges.map(badge=><span key={badge.label} title={`${badge.meaning}. ${badge.source==="zkill-rule"?"EQM applies the documented zKill rule; ":""}zKill rolling ${badge.window_days}-day window; fetched ${stamp(data?.zkill?.fetched_at)}`}><ShieldCheck size={13}/>{badge.label}{badge.level?` ${badge.level}`:""} {badge.count!==undefined?` (${number.format(badge.count)})`:""}</span>)}{summary?.smartbomb.frequent&&<span title={report.definitions.smartbomb} className="intel-local-tag">EQM · FREQUENT SMARTBOMBER</span>}</div></div><a className="intel-source-link" href={zkill(report.subject.kind,report.subject.eve_id)} target="_blank" rel="noreferrer">zKill <ExternalLink size={14}/></a></div>
    <div className="intel-controls"><label>From (UTC)<input type="date" value={from} onChange={event=>{if(event.target.value)setFrom(event.target.value);}}/></label><label>Through (UTC)<input type="date" value={to} onChange={event=>{if(event.target.value)setTo(event.target.value);}}/></label><div className="intel-presets">{[7,30,90,365].map(days=><button key={days} onClick={()=>{setFrom(dateUTC(new Date(Date.now()-days*86400000)));setTo(dateUTC(new Date()));}}>{days}d</button>)}<button onClick={()=>{setFrom("2003-05-06");setTo(dateUTC(new Date()));}}>All retained</button></div><button disabled={busy||loading} onClick={()=>void runReport(report.subject)}><RefreshCw size={15}/> {sighting.system&&sighting.ship&&report.subject.kind==="character"?"Record sighting / refresh report":"Refresh report"}</button></div>
    <div className="intel-collection-controls"><label>Collection depth: pages per kills/losses feed<input type="number" min={1} max={100} value={pages} onChange={event=>setPages(Number(event.target.value))}/></label><button className="intel-primary" disabled={busy||isActive(latest)||pages<1||pages>100||!Number.isInteger(pages)} onClick={()=>void collect()}><Database size={15}/> Collect public history</button><small>Collects from the selected start date through now; up to 200 entries per page. Report dates filter retained evidence independently.</small></div>
    {latest&&<div className={`intel-job job-${latest.status}`} role="status"><div><strong>{latest.status.toUpperCase()} · {latest.stage}</strong><span>Page {latest.page}/{latest.max_pages} · {latest.imported_count} new · {latest.reused_count} reused · {latest.failed_count} failed attempts</span>{latest.available_at&&latest.status==="queued"&&<small>Next attempt: {stamp(latest.available_at)}</small>}</div>{isActive(latest)?<button disabled={busy} onClick={()=>void run(async()=>{const job=await api<Collection>(`${base}/collections/${latest.id}/cancel`,request("POST"));setReport(old=>old?{...old,latest_collection:job}:old);await lists();})}>Cancel collection</button>:latest.stage!=="finished"&&["failed","partial","cancelled"].includes(latest.status)?<button disabled={busy} onClick={()=>void run(async()=>{const job=await api<Collection>(`${base}/collections/${latest.id}/retry`,request("POST"));setReport(old=>old?{...old,latest_collection:job}:old);})}>Resume collection</button>:null}</div>}
    <div className={`intel-coverage ${report.coverage.analysis_limited||latest?.status==="partial"?"limited":""}`}><BookOpen size={17}/><div><strong>{report.coverage.loaded_killmails?`${number.format(report.coverage.loaded_killmails)} retained killmails in this window`:"No retained evidence in this window"}</strong><span>Observed {stamp(report.coverage.observed_from)} — {stamp(report.coverage.observed_to)}.</span><span>{report.coverage.analysis_limited?`Analysis is capped at ${report.coverage.analysis_limit} killmails or the participant budget. `:""}{report.coverage.notice}</span>{latest&&<span>Latest collection coverage: {Object.entries(latest.coverage).filter(([key])=>key==="kills"||key==="losses").map(([key,value])=>`${key}: ${value.status??"pending"} (${value.pages??0} pages)`).join(" · ")||"not collected yet"}</span>}</div></div>
    {data?.esi?.state==="unavailable"&&<div className="mini-alert">Public ESI unavailable. Retained identity/history may be stale.</div>}{data?.zkill?.state==="unavailable"&&<div className="mini-alert">zKill statistics unavailable. Retained badges may be stale.</div>}
    {!!latest?.errors.length&&<p className="muted">Last collection issue: {latest.errors[latest.errors.length-1].message} ({latest.errors[latest.errors.length-1].stage}, page {latest.errors[latest.errors.length-1].page}).</p>}
    <nav className="intel-tabs" aria-label="Intel report sections">{tabs.map(name=><button key={name} className={tab===name?"active":""} onClick={()=>setTab(name)}>{name}</button>)}</nav>
   </section>
   {loading&&<p role="status" className="muted">Updating retained evidence…</p>}
   {tab==="Timeline"&&<IntelSightingTimeline report={report}/>}
   {tab==="Overview"&&summary&&<>
    <section className="panel intel-sighting-summary"><strong>{summary.sightings} analyst-reported sightings</strong><p className="muted">Separate from killmail evidence; each sighting adds 0 kills and 0 losses.</p><button onClick={()=>setTab("Timeline")}>View sighting timeline</button></section>
    <section className="intel-metrics"><Metric title="Observed PvP kills" value={number.format(summary.kills)} detail="Unique killmails as attacker"/><Metric title="Observed PvP losses" value={number.format(summary.losses)} detail="Unique killmails as victim"/><Metric title="Smartbomb evidence" value={`${summary.smartbomb.confirmed_kills} / ${summary.smartbomb.observed_kills}`} detail={`${summary.smartbomb.confirmed_percent??"—"}% confirmed · weapon metadata on ${summary.smartbomb.weapon_known_kills} kills`}/><Metric title="Recorded attacker count" value={summary.average_recorded_attacker_count===null?"—":number.format(summary.average_recorded_attacker_count)} detail="Average on subject's kills; not fleet size"/></section>
    <section className="panel stacked"><h3>Public identity and affiliations</h3><div className="intel-profile-grid">{Object.entries(profile??{}).filter(([key,value])=>!['history','description','name','source_errors','corporation_ids','corporations'].includes(key)&&value!==null).map(([key,value])=><div key={key}><small>{key.replace(/_/g," ")}</small><strong>{String(value)}</strong></div>)}</div>{profile?.description&&<p className="intel-plain">{profile.description}</p>}{profile?.corporation_ids&&<p>{profile.corporation_ids.length} public member corporations currently listed for this alliance.</p>}{profile?.source_errors?.map((text,index)=><p className="mini-alert" key={index}>{text}</p>)}<p className="muted">Public ESI: {stamp(data?.esi?.fetched_at)} · zKill badges/statistics: {stamp(data?.zkill?.fetched_at)}. Badges retain their own rolling windows.</p></section>
    <div className="intel-two"><RankingTable title="Observed ships" rows={summary.ships.slice(0,12)} onEvidence={drill}/><RankingTable title="Observed systems" rows={summary.systems.slice(0,12)} onEvidence={drill}/></div>
    <section className="panel stacked"><h3><Clock size={17}/> Recorded UTC activity</h3><HourBars rows={summary.utc_hours}/><p className="muted">Combat appearances, not online time. Times are UTC.</p></section>
   </>}
   {tab==="Geography"&&summary&&<><div className="intel-two"><RankingTable title="Systems: combat and sightings" rows={summary.systems} onEvidence={drill}/><RankingTable title="Regions" rows={summary.regions} onEvidence={drill}/></div><section className="panel stacked"><h3>Activity timeline</h3><div className="intel-table-wrap"><table><thead><tr><th>UTC date</th><th>Kills</th><th>Losses</th><th>Sightings</th></tr></thead><tbody>{summary.timeline.map(day=><tr key={day.date}><td>{day.date}</td><td>{day.kills}</td><td>{day.losses}</td><td>{day.sightings??0}</td></tr>)}</tbody></table></div><p className="muted">These are recorded combat locations. Home systems, travel paths, and current location are not established by these records.</p></section></>}
   {tab==="Associates"&&summary&&<section className="panel stacked"><div className="section-heading"><h3><Network size={17}/> Recurring co-attackers</h3><label>Entity type<select value={associateKind} onChange={event=>setAssociateKind(event.target.value)}><option value="character">Characters</option><option value="corporation">Corporations</option><option value="alliance">Alliances</option></select></label></div><p className="muted">{report.definitions.associates} Affiliations are those recorded at the time of each kill.</p><div className="intel-table-wrap"><table><thead><tr><th>Entity</th><th>Shared kills</th><th>Est. engagements</th><th>Days</th><th>Subject's kills</th><th>Evidence</th></tr></thead><tbody>{summary.associates.filter(row=>row.kind===associateKind).map(row=><tr key={`${row.kind}:${row.id}`}><td><button className="intel-text-button" disabled={busy} onClick={()=>void track({kind:row.kind,eve_id:row.id,name:row.name})}>{row.name}</button></td><td>{row.kills}</td><td>{row.estimated_engagements}</td><td>{row.distinct_days}</td><td>{row.share_of_subject_kills_percent}%</td><td><button onClick={()=>drill(row.evidence,`Co-attacker: ${row.name}`)}>Inspect</button></td></tr>)}</tbody></table></div><p className="muted">Top 50 per entity type. {report.total_associates} associations found in the loaded sample. An association is not a spy verdict or proof of a coalition agreement.</p></section>}
   {tab==="Evidence"&&<section className="panel stacked"><div className="section-heading"><h3>Evidence ledger</h3>{evidenceIds&&<button onClick={()=>{setEvidenceIds(null);setEvidenceTitle("");}}>Clear sample filter</button>}</div>{evidenceIds&&<p className="muted">{evidenceTitle} · showing available sample IDs from the report's 200 most recent evidence records.</p>}<div className="intel-table-wrap"><table><thead><tr><th>Killmail</th><th>Time</th><th>System</th><th>Subject's side</th></tr></thead><tbody>{evidence.map(row=><tr key={row.id}><td><a href={killLink(row.id)} target="_blank" rel="noreferrer">{row.id} <ExternalLink size={11}/></a></td><td>{stamp(row.time)}</td><td>{summary?.systems.find(system=>system.id===row.system_id)?.name??row.system_id}</td><td>{row.side}{row.npc_only?" · NPC-only":""}</td></tr>)}</tbody></table></div>{evidenceIds&&<div className="intel-samples">{evidenceIds.map(id=><a key={id} href={killLink(id)} target="_blank" rel="noreferrer">Kill {id} <ExternalLink size={11}/></a>)}</div>}<p className="muted">{report.definitions.evidence}</p></section>}
   {tab==="History"&&<>
    {!!profile?.corporations?.length&&<section className="panel stacked"><h3>Current public member corporations</h3>{profile.corporations.map(corp=><button disabled={busy} key={corp.id} onClick={()=>void track({kind:"corporation",eve_id:corp.id,name:corp.name})}>{corp.name} <ChevronRight size={14}/></button>)}</section>}
    <section className="panel stacked"><h3>Public employment / alliance history</h3><div className="intel-table-wrap"><table><thead><tr><th>Started</th><th>Entity</th><th>Record</th></tr></thead><tbody>{profile?.history?.map((row,index)=><tr key={index}><td>{stamp(row.start_date)}</td><td><a href={zkill(row.corporation_id?"corporation":"alliance",row.corporation_id??row.alliance_id??0)} target="_blank" rel="noreferrer">{row.corporation_id?(row.corporation_name??`Corporation ${row.corporation_id}`):(row.alliance_name??`Alliance ${row.alliance_id??"None"}`)}</a></td><td>{row.is_deleted?"Deleted":"Public ESI"}</td></tr>)}</tbody></table></div>{!profile?.history?.length&&<p className="muted">No public history currently available.</p>}</section>
    <section className="panel stacked"><h3>Collection history</h3><p className="muted">Latest 20 collection attempts. A completed fetch covers its requested range and feed response; zKill itself can have missing killmails.</p><div className="intel-table-wrap"><table><thead><tr><th>Requested window</th><th>Status</th><th>New / reused</th><th>Coverage</th></tr></thead><tbody>{report.coverage.collections.map(job=><tr key={job.id}><td>{stamp(job.from_at)} — {stamp(job.to_at)}</td><td>{job.status}</td><td>{job.imported_count} / {job.reused_count}</td><td>{Object.entries(job.coverage).filter(([key])=>key==="kills"||key==="losses").map(([key,value])=>`${key}: ${value.status??"pending"}`).join(" · ")||"Pending"}{job.errors.map((issue,index)=><small key={index}>{issue.stage}, page {issue.page}: {issue.message}</small>)}</td></tr>)}</tbody></table></div></section>
    <section className="panel stacked"><h3>Recorded profile and badge changes</h3><p className="muted">Saved only when public content changes. Observation dates show when EQM saw a change, not necessarily when it happened.</p>{report.observations.map((row,index)=><details key={index}><summary>{stamp(row.observed_at)} · {row.source.toUpperCase()}</summary><pre>{JSON.stringify(row.payload,null,2)}</pre></details>)}</section>
   </>}
   {tab==="Authorized ESI"&&<section className="panel stacked"><h3><ShieldCheck size={17}/> Authorized ESI enrichment</h3><p className="muted">Fetched for this viewer on demand. Private information is never stored in shared public intel snapshots.</p>{privateData?privateData.state!=="authorized"?<p>{privateData.notice}</p>:<>
    <div className="button-row">{privateData.refresh_datasets?.map(dataset=><button key={dataset} disabled={busy} onClick={()=>void run(async()=>{setPrivateData(await api<PrivateData>(`${base}/subjects/${selectedId}/authorized/refresh`,request("POST",{dataset})));setMessage(`Authorized ${dataset} refresh finished.`);})}><RefreshCw size={14}/> Refresh {dataset}</button>)}</div>
    {privateData.applicant&&<div className="intel-coverage"><strong>Applicant verification: {privateData.applicant.verification_status}</strong><span>Token: {privateData.applicant.token_health} · last successful sync {stamp(privateData.applicant.last_successful_sync_at)}</span></div>}
    <h4>Skills · {privateData.datasets?.skills?.state??"not authorized"}</h4>{privateData.datasets?.skills?.state==="available"&&<><strong>{privateData.datasets.skills.total_sp==null?"Unknown":number.format(privateData.datasets.skills.total_sp)} total SP</strong><p className="muted">Cached {stamp(privateData.datasets.skills.synced_at)}</p><div className="intel-table-wrap"><table><thead><tr><th>Skill</th><th>Trained</th><th>Active</th></tr></thead><tbody>{privateData.datasets.skills.top_skills?.map(skill=><tr key={skill.id}><td>{skill.name}</td><td>{skill.trained_level}</td><td>{skill.active_level}</td></tr>)}</tbody></table></div></>}
    {privateData.datasets?.queue&&<><h4>Training queue · {privateData.datasets.queue.state}</h4>{privateData.datasets.queue.entries.map((entry,index)=><p key={index}>{entry.name} {entry.level} · {stamp(entry.finish)}</p>)}</>}
    {privateData.datasets?.fittings&&<><h4>Saved fitting templates · {privateData.datasets.fittings.state}</h4><p className="muted">{privateData.datasets.fittings.notice}</p>{privateData.datasets.fittings.rows.map(fit=><p key={fit.id}>{fit.name} · {fit.ship} · {stamp(fit.synced_at)}</p>)}</>}
   </>:<p role="status">Checking viewer permissions and available scopes…</p>}</section>}
   {tab==="Notes"&&<IntelNotes key={selectedId} api={api} subjectId={selectedId} notes={notes} setNotes={setNotes}/>}
  </>:<section className="panel intel-empty"><Crosshair size={38}/><h3>{loading?"Opening dossier…":"Start with a name"}</h3><p>Paste an external pilot, corporation, or alliance to begin. Public killmail history supplies the core evidence.</p><div><Globe2 size={18}/> Public ESI identity <ChevronRight size={15}/><Activity size={18}/> zKill history <ChevronRight size={15}/><Network size={18}/> Patterns over time</div></section>}</div>
  </div>
 </section>;
}
function Metric({title,value,detail}:{title:string;value:string;detail:string}){return <article className="panel intel-metric"><small>{title}</small><strong>{value}</strong><span>{detail}</span></article>;}
function RankingTable({title,rows,onEvidence}:{title:string;rows:Ranking[];onEvidence:(ids:number[]|undefined,title:string)=>void}){return <section className="panel stacked"><h3>{title}</h3><div className="intel-table-wrap"><table><thead><tr><th>Name</th><th>Kills</th><th>Losses</th><th>Sightings</th><th>Evidence</th></tr></thead><tbody>{rows.map(row=><tr key={row.id}><td><strong>{row.name}</strong>{row.region_name&&<small>{row.region_name}</small>}{row.last_seen&&<small>Last combat {stamp(row.last_seen)}</small>}{row.last_sighting_at&&<small>Last sighting {stamp(row.last_sighting_at)}</small>}</td><td>{row.kills}</td><td>{row.losses}</td><td>{row.sightings??0}</td><td>{!!row.evidence?.length&&<button onClick={()=>onEvidence(row.evidence,title+": "+row.name)}>Inspect</button>}</td></tr>)}</tbody></table></div>{!rows.length&&<p className="muted">No observations in the retained sample.</p>}</section>;}
function HourBars({rows}:{rows:{hour:number;appearances:number}[]}){const max=Math.max(1,...rows.map(row=>row.appearances));return <div className="intel-hours">{rows.map(row=><div key={row.hour} title={`${String(row.hour).padStart(2,"0")}:00 UTC · ${row.appearances} appearances`}><span style={{height:`${Math.max(2,row.appearances/max*90)}px`}}/><small>{row.hour}</small></div>)}</div>;}
