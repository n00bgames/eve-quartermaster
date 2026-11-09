import {useEffect, useRef, useState} from "react";
import type {ApiClient, Candidate} from "./types";

type Entity=Candidate&{id:number|null;key:string;priority:boolean;pilot_count:number};
type Corporation=Entity;
type Alliance=Entity&{corporations:Corporation[]};
type Pilot=Candidate&{id:number;priority:boolean};
type Page={rows:Pilot[];total:number};

export function IntelSubjectBrowser({api,revision,selectedId,busy,onOpen,onPilot}:{api:ApiClient;revision:number;selectedId:number;busy:boolean;onOpen:(candidate:Candidate)=>void;onPilot:(pilot:Pilot)=>void}) {
 const [query,setQuery]=useState("");
 const [tree,setTree]=useState<Alliance[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true);
 useEffect(()=>{let stopped=false;const timer=setTimeout(()=>{setLoading(true);void api<Alliance[]>(`/intel/subject-tree?q=${encodeURIComponent(query)}`).then(rows=>{if(!stopped){setTree(rows);setError("");}}).catch(err=>{if(!stopped)setError(String(err));}).finally(()=>{if(!stopped)setLoading(false);});},200);return()=>{stopped=true;clearTimeout(timer);};},[api,query,revision]);
 function title(entity:Entity){return <>{entity.eve_id?<button type="button" disabled={busy} className={selectedId===entity.id?"selected":""} onClick={()=>onOpen(entity)}>{entity.priority&&<span title="Priority Target">★ </span>}{entity.name}</button>:<strong>{entity.name}</strong>}<small>{entity.pilot_count} pilots</small></>;}
 return <section className="panel stacked intel-subject-browser"><h3>Saved subjects</h3><label>Search dossiers<input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Pilot, corporation or alliance"/></label><small className="muted">Cached affiliations · priority targets first, then alphabetical. Click an entity name to open its report.</small>
  {error&&<div role="alert" className="mini-alert">{error}</div>}{loading&&<small role="status">Loading subjects…</small>}
  <div key={query} className="intel-subject-tree">{tree.map(alliance=><div className="intel-subject-branch" key={alliance.key}><div className="intel-branch-title">{title(alliance)}</div><details><summary aria-label={`Expand ${alliance.name}`}>{alliance.corporations.length} corporations</summary><div className="intel-corporation-branches">{alliance.corporations.map(corp=><div className="intel-subject-branch" key={corp.key}><div className="intel-branch-title">{title(corp)}</div><PilotBranch api={api} revision={revision} alliance={alliance.key} corporation={corp} query={query} busy={busy} selectedId={selectedId} onPilot={onPilot}/></div>)}</div></details></div>)}{!tree.length&&!loading&&<p className="muted">{query?"No matching saved subjects.":"Resolve an entity or generate a Local Scan to start a dossier."}</p>}</div>
 </section>;
}

function PilotBranch({api,revision,alliance,corporation,query,busy,selectedId,onPilot}:{api:ApiClient;revision:number;alliance:string;corporation:Corporation;query:string;busy:boolean;selectedId:number;onPilot:(pilot:Pilot)=>void}) {
 const [open,setOpen]=useState(false),[page,setPage]=useState<Page|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState("");
 const version=useRef(0);
 useEffect(()=>{version.current++;setPage(null);setError("");setLoading(false);return()=>{version.current++;};},[revision]);
 async function load(offset:number){const current=version.current;setLoading(true);setError("");try{const result=await api<Page>(`/intel/subject-tree/pilots?${new URLSearchParams({alliance,corporation:corporation.key,q:query,offset:String(offset)})}`);if(current===version.current)setPage(old=>({total:result.total,rows:offset&&old?[...old.rows,...result.rows]:result.rows}));}catch(err){if(current===version.current)setError(String(err));}finally{if(current===version.current)setLoading(false);}}
 useEffect(()=>{if(open&&!page&&!loading&&!error)void load(0);},[open,page,loading,error]);
 return <details open={open}><summary aria-label={`Expand ${corporation.name} pilots`} onClick={event=>{event.preventDefault();setOpen(value=>!value);}}>{corporation.pilot_count} pilots</summary>{open&&<div className="intel-subjects intel-pilot-leaves">{page?.rows.map(pilot=><button key={pilot.id} className={selectedId===pilot.id?"selected":""} disabled={busy} onClick={()=>onPilot(pilot)}><strong>{pilot.priority&&<span title="Priority Target">★ </span>}{pilot.name}</strong><small>Open pilot dossier</small></button>)}{loading&&<small role="status">Loading pilots…</small>}{error&&<div role="alert">{error}<button onClick={()=>void load(page?.rows.length??0)}>Retry pilots</button></div>}{page&&page.rows.length<page.total&&<button disabled={loading} onClick={()=>void load(page.rows.length)}>Load more pilots ({page.rows.length}/{page.total})</button>}</div>}</details>;
}
