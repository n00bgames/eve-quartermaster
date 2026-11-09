import {useEffect,useState} from "react";
import type {ApiClient} from "./types";
import {noteQueryFromHash,noteSearchLink,type NotePreview} from "./noteLinks";
import "./noteSearch.css";

type Matches={query:string;total:number;offset:number;limit:number;rows:{subject_id:number;character_id:number;name:string;notes:NotePreview[];matching_note_count:number}[]};

export function NoteSearch({api}:{api:ApiClient}) {
  const [query,setQuery]=useState(()=>noteQueryFromHash(window.location.hash)??""),[offset,setOffset]=useState(0);
  const [data,setData]=useState<Matches|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[revision,setRevision]=useState(0);
  useEffect(()=>{const change=()=>setRevision(n=>n+1);window.addEventListener("eqm-character-notes",change);return()=>window.removeEventListener("eqm-character-notes",change);},[]);
  useEffect(()=>{const change=()=>{const text=noteQueryFromHash(window.location.hash);if(text!==null){setQuery(text);setOffset(0);}};window.addEventListener("hashchange",change);return()=>window.removeEventListener("hashchange",change);},[]);
  useEffect(()=>{setData(null);setError("");if(!query.trim()){setBusy(false);return;}const controller=new AbortController();setBusy(true);
    const timer=window.setTimeout(()=>{void api<Matches>(`/intel/notes/search?q=${encodeURIComponent(query.trim())}&offset=${offset}&limit=50`,{signal:controller.signal})
      .then(result=>{if(!controller.signal.aborted)setData(result);})
      .catch(err=>{if(!controller.signal.aborted)setError(err instanceof Error?err.message:"Note search failed.");})
      .finally(()=>{if(!controller.signal.aborted)setBusy(false);});},250);
    return()=>{clearTimeout(timer);controller.abort();};
  },[api,query,offset,revision]);
  return <section className="panel stacked intel-note-search" aria-label="Search character notes">
    <div className="scan-report-header"><h3>Search character notes</h3>{query.trim()&&<a href={noteSearchLink(query.trim())}>Link to this search</a>}</div>
    <p className="muted">Find characters by text in their Public or Private notes. Public notes are shared with signed-in EQM intel users; private notes are visible only to you.</p>
    <label>Note text<input aria-label="Search note text" maxLength={5000} value={query} onChange={event=>{setQuery(event.target.value);setOffset(0);}} placeholder="e.g. suspected multiboxer · mining crew A"/></label>
    {busy&&<p role="status">Searching notes…</p>}{error&&<p role="alert" className="mini-alert">{error}</p>}
    {data&&<><p role="status">{data.total.toLocaleString()} characters match “{data.query}”.</p><div className="intel-note-matches">{data.rows.map(row=><article key={row.character_id}><div><a href={`#intel/${row.subject_id}`} className="intel-note-character">{row.name}</a><a href={`https://zkillboard.com/character/${row.character_id}/`} target="_blank" rel="noopener noreferrer">zKillboard ↗</a></div>{row.notes.map(note=><p key={note.id}><span className="intel-note-visibility">{note.is_private?"Private Note":"Public Note"}</span> {note.body}{note.truncated?"…":""}<small> {note.author} · {new Date(note.created_at).toLocaleString()}</small></p>)}{row.matching_note_count>row.notes.length&&<small>{row.matching_note_count} matching notes · open the character for more</small>}</article>)}</div>{data.total>50&&<div className="scan-report-actions"><button disabled={busy||offset===0} onClick={()=>setOffset(n=>Math.max(0,n-50))}>Previous matches</button><span>{offset+1}–{Math.min(offset+50,data.total)} of {data.total}</span><button disabled={busy||offset+50>=data.total} onClick={()=>setOffset(n=>n+50)}>Next matches</button></div>}</>}
  </section>;
}
