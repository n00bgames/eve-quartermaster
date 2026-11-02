import {useEffect, useRef, useState} from "react";
import type {BattleReportPayload, BattleWindow, BattleDiscoveryJob} from "../../types/battleReports";

type Api = <T>(path:string, options?:RequestInit)=>Promise<T>;
const running = (job:BattleDiscoveryJob|null) => Boolean(job && ["queued","running"].includes(job.status));
const utcInput = (value:string) => new Date(value).toISOString().slice(0,16);

export function BattleDiscoveryPanel({api,pilotId,seedId,gapMinutes,payload,onApply}: {
  api:Api;pilotId:number;seedId:number;gapMinutes:number;payload:BattleReportPayload;
  onApply:(window:BattleWindow, jobId:string|null)=>Promise<void>;
}) {
  const apply=useRef(onApply);
  useEffect(()=>{apply.current=onApply;},[onApply]);
  const suggested=payload.coverage.search_window;
  const [from,setFrom]=useState(suggested?utcInput(suggested.start_time):"");
  const [to,setTo]=useState(suggested?utcInput(suggested.end_time):"");
  const [systems,setSystems]=useState(payload.report?.systems??[]);
  const [selected,setSelected]=useState<number[]>(suggested?.system_ids??[]);
  const [query,setQuery]=useState("");
  const [choices,setChoices]=useState<{system_id:number;system_name:string}[]>([]);
  const [job,setJob]=useState<BattleDiscoveryJob|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  useEffect(()=>{
    let active=true;
    void api<BattleDiscoveryJob|null>(`/battle-reports/discovery/latest?character_id=${pilotId}&seed_killmail_id=${seedId}`)
      .then(value=>{if(active)setJob(current=>current??value);}).catch(()=>undefined);
    return ()=>{active=false;};
  },[pilotId,seedId]);
  useEffect(()=>{
    if(query.trim().length<2){setChoices([]);return;}
    let active=true;
    const timer=window.setTimeout(()=>{void api<{system_id:number;system_name:string}[]>(`/battle-reports/systems?q=${encodeURIComponent(query.trim())}`)
      .then(rows=>{if(active)setChoices(rows);}).catch(()=>{if(active)setChoices([]);});},300);
    return ()=>{active=false;window.clearTimeout(timer);};
  },[query]);
  useEffect(()=>{
    if(!job || !running(job))return;
    let active=true;
    const timer=window.setInterval(()=>{void api<BattleDiscoveryJob>(`/battle-reports/discovery/${job.job_id}`).then(async next=>{
      if(!active)return;setJob(next);
      if(["complete","partial"].includes(next.status))await apply.current(next.window,next.job_id);
    }).catch(e=>{if(active)setError(e instanceof Error?e.message:"Collection status unavailable");});},2500);
    return ()=>{active=false;window.clearInterval(timer);};
  },[job?.job_id,job?.status]);
  function chosenWindow():BattleWindow {
    if(!from || !to || !selected.length)throw new Error("Choose the UTC start, end and at least one system.");
    const start=new Date(from+"Z"),end=new Date(to+"Z");
    if(!(end.getTime()>start.getTime()) || end.getTime()-start.getTime()>12*3600000)throw new Error("Choose a positive window of at most 12 hours.");
    return {start_time:start.toISOString(),end_time:end.toISOString(),system_ids:selected};
  }
  async function collect() {
    setBusy(true);setError("");
    try {
      const window=chosenWindow();
      const next=await api<BattleDiscoveryJob>("/battle-reports/discovery",{method:"POST",body:JSON.stringify({
        character_id:pilotId,seed_killmail_id:seedId,gap_minutes:gapMinutes,battle_window:window})});
      setJob(next);
      await apply.current(next.window,next.job_id);
    } catch(e){setError(e instanceof Error?e.message:"Could not start battle collection");}
    finally{setBusy(false);}
  }
  async function control(action:"resume"|"cancel") {
    if(!job)return;setBusy(true);setError("");
    try{setJob(await api<BattleDiscoveryJob>(`/battle-reports/discovery/${job.job_id}/${action}`,{method:"POST"}));}
    catch(e){setError(e instanceof Error?e.message:"Collection action failed");}finally{setBusy(false);}
  }
  return <section className="panel battle-discovery" aria-label="Full battle discovery">
    <h3>Find all battle kills</h3>
    <p>Search zKillboard across the selected systems and UTC window, including kills your pilot was never on. All kills in this window enter the report; review teams and third parties before sharing.</p>
    <fieldset disabled={busy||running(job)}><legend>Battle boundaries</legend>
      <div className="battle-discovery-times"><label>Battle start (UTC)<input type="datetime-local" value={from} onChange={e=>setFrom(e.target.value)}/></label>
        <label>Battle end (UTC)<input type="datetime-local" value={to} onChange={e=>setTo(e.target.value)}/></label></div>
      <p className="muted">Starts from your pilot's activity window. Adjust it to include earlier, later or nearby parts of the fight. Up to 12 hours and 8 systems.</p>
      <div className="battle-discovery-systems">{systems.map(system=><label key={system.system_id}><input type="checkbox" checked={selected.includes(system.system_id)}
        onChange={e=>setSelected(ids=>e.target.checked?[...ids,system.system_id]:ids.filter(id=>id!==system.system_id))}/>{system.system_name}</label>)}</div>
      <label>Add battle system<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search system name" maxLength={100}/></label>
      {choices.length>0&&<ul>{choices.filter(s=>!systems.some(x=>x.system_id===s.system_id)).map(s=><li key={s.system_id}><button type="button" disabled={selected.length>=8} onClick={()=>{setSystems(rows=>[...rows,s]);setSelected(ids=>[...ids,s.system_id]);setQuery("");}}>{s.system_name}</button></li>)}</ul>}
      <button type="button" disabled={!selected.length||selected.length>8} onClick={()=>void collect()}>Find all battle kills</button>
    </fieldset>
    {error&&<div className="alert" role="alert">{error}</div>}
    {job&&<div className="battle-discovery-progress" role="status"><strong>Collection: {job.status}</strong>
      <p>{job.imported_count.toLocaleString()} imported · {job.cached_count.toLocaleString()} already cached / outside window · {job.failed_count.toLocaleString()} import issues · page {job.page}, source {Math.min(job.target_index+1,job.target_count)} of {job.target_count}</p>
      <p>{job.message}</p>
      <p className="muted">Collected window: {new Date(job.window.start_time).toISOString()} to {new Date(job.window.end_time).toISOString()}</p>
      {job.can_resume&&<button type="button" disabled={busy} onClick={()=>void control("resume")}>Resume collection</button>}
      {!["complete","partial","cancelled"].includes(job.status)&&<button type="button" disabled={busy} onClick={()=>void control("cancel")}>Cancel collection</button>}
      {!running(job)&&<button type="button" disabled={busy} onClick={()=>void onApply(job.window,job.job_id).catch(e=>setError(String(e)))}>Use collected kills</button>}
    </div>}
    <p className="muted">zKillboard withholds kills less than five minutes old and caches responses. Missing, delayed, failed or unreported kills cannot be guaranteed; refresh later for more coverage.</p>
  </section>;
}
