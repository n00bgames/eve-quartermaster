import {useEffect,useRef,useState} from "react";
import type {Dispatch,SetStateAction} from "react";
import type {ApiClient,Note} from "./types";

export function IntelNotes({api,subjectId,notes,setNotes}:{api:ApiClient;subjectId:number;notes:Note[];setNotes:Dispatch<SetStateAction<Note[]>>}){
 const [draft,setDraft]=useState(""),[editing,setEditing]=useState<number|null>(null),[editBody,setEditBody]=useState(""),[original,setOriginal]=useState("");
 const [deleting,setDeleting]=useState<number|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const path=`/intel/subjects/${subjectId}/notes`;
 async function run(action:()=>Promise<void>){setBusy(true);setError("");try{await action();}catch(err){if(mounted.current)setError(err instanceof Error?err.message:"Unable to save note changes.");}finally{if(mounted.current)setBusy(false);}}
 async function reload(){await run(async()=>{const rows=await api<Note[]>(path);if(mounted.current){setNotes(rows);setEditing(null);setDeleting(null);}});}
 return <section className="panel stacked"><h3>Restricted analyst notes</h3><p className="muted">Visible to staff with Intel Reports access. Authors can edit/delete their own notes; Admins and Hosts can moderate any note. Record evidence and hypotheses separately.</p>
 {error&&<div role="alert" className="mini-alert">{error} <button disabled={busy} onClick={()=>void reload()}>Reload notes</button></div>}
 <label>New note<textarea rows={4} maxLength={5000} value={draft} onChange={e=>setDraft(e.target.value)}/></label>
 <button disabled={busy||!draft.trim()} onClick={()=>void run(async()=>{const row=await api<Note>(path,{method:"POST",body:JSON.stringify({body:draft})});if(mounted.current){setNotes(old=>[row,...old]);setDraft("");}})}>Add note</button>
 <button disabled={busy} onClick={()=>void reload()}>Reload notes</button>
 {notes.map(row=><article className="intel-note" key={row.id}>
 <div className="intel-note-header"><strong>{row.author} · {new Date(row.created_at).toLocaleString()}</strong><div className="intel-note-actions">
 {row.can_edit&&<button disabled={busy||editing===row.id} onClick={()=>{setEditing(row.id);setOriginal(row.body);setEditBody(row.body);setDeleting(null);setError("");}}>Edit note</button>}
 {row.can_delete&&<button disabled={busy} onClick={()=>{setDeleting(row.id);setEditing(null);setError("");}}>Delete note</button>}</div></div>
 {editing===row.id?<><label>Edit note<textarea autoFocus rows={4} maxLength={5000} value={editBody} onChange={e=>setEditBody(e.target.value)}/></label><div className="intel-note-actions"><button disabled={busy||!editBody.trim()} onClick={()=>void run(async()=>{const next=await api<Note>(`${path}/${row.id}`,{method:"PATCH",body:JSON.stringify({body:editBody,expected_body:original})});if(mounted.current){setNotes(old=>old.map(n=>n.id===next.id?next:n));setEditing(null);}})}>Save changes</button><button disabled={busy} onClick={()=>setEditing(null)}>Cancel edit</button></div></>:<p>{row.body}</p>}
 {deleting===row.id&&<div className="intel-note-delete" role="group" aria-label="Confirm note deletion"><p>Delete this note permanently?</p><div className="intel-note-actions"><button disabled={busy} onClick={()=>void run(async()=>{await api(`${path}/${row.id}`,{method:"DELETE",body:JSON.stringify({expected_body:row.body})});if(mounted.current){setNotes(old=>old.filter(n=>n.id!==row.id));setDeleting(null);}})}>Confirm delete</button><button disabled={busy} onClick={()=>setDeleting(null)}>Keep note</button></div></div>}
 </article>)}
 </section>;
}
