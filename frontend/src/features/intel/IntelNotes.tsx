import {useEffect,useRef,useState} from "react";
import type {Dispatch,SetStateAction} from "react";
import type {ApiClient,Note} from "./types";
import {noteSearchLink} from "./noteLinks";

export function IntelNotes({api,subjectId,notes,setNotes}:{api:ApiClient;subjectId:number;notes:Note[];setNotes:Dispatch<SetStateAction<Note[]>>}){
 const [draft,setDraft]=useState(""),[editing,setEditing]=useState<number|null>(null),[editBody,setEditBody]=useState(""),[original,setOriginal]=useState("");
 const [isPrivate,setPrivate]=useState(true),[editPrivate,setEditPrivate]=useState(false),[originalPrivate,setOriginalPrivate]=useState(false);
 const [deleting,setDeleting]=useState<number|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const path=`/intel/subjects/${subjectId}/notes`;
 async function run(action:()=>Promise<void>){setBusy(true);setError("");try{await action();}catch(err){if(mounted.current)setError(err instanceof Error?err.message:"Unable to save note changes.");}finally{if(mounted.current)setBusy(false);}}
 async function reload(){await run(async()=>{const rows=await api<Note[]>(path);if(mounted.current){setNotes(rows);setEditing(null);setDeleting(null);}});}
 return <section className="panel stacked"><h3>Character notes</h3><p className="muted">Public notes are shared with signed-in EQM intel users. Private notes are author-only. Authors can edit/delete their notes; Admins and Hosts can moderate public notes. Notes never appear on public scan links or PDFs. Record evidence and hypotheses separately.</p>
 {error&&<div role="alert" className="mini-alert">{error} <button disabled={busy} onClick={()=>void reload()}>Reload notes</button></div>}
 <label>New note<textarea rows={4} maxLength={5000} value={draft} onChange={e=>setDraft(e.target.value)}/></label>
 <label>Note visibility<select aria-label="New Intel note visibility" value={isPrivate?"private":"public"} onChange={e=>setPrivate(e.target.value==="private")}><option value="private">Private Note — only me</option><option value="public">Public Note — EQM intel users</option></select></label>
 <button disabled={busy||!draft.trim()} onClick={()=>void run(async()=>{const row=await api<Note>(path,{method:"POST",body:JSON.stringify({body:draft,is_private:isPrivate})});if(mounted.current){setNotes(old=>[row,...old]);setDraft("");window.dispatchEvent(new Event("eqm-character-notes"));}})}>Add note</button>
 <button disabled={busy} onClick={()=>void reload()}>Reload notes</button>
 {notes.map(row=><article className="intel-note" key={row.id}>
 <div className="intel-note-header"><strong>{row.author} · {new Date(row.created_at).toLocaleString()} · {row.is_private?"Private Note":"Public Note"}</strong><div className="intel-note-actions">
 {row.can_edit&&<button disabled={busy||editing===row.id} onClick={()=>{setEditing(row.id);setOriginal(row.body);setOriginalPrivate(Boolean(row.is_private));setEditPrivate(Boolean(row.is_private));setEditBody(row.body);setDeleting(null);setError("");}}>Edit note</button>}
 {row.can_delete&&<button disabled={busy} onClick={()=>{setDeleting(row.id);setEditing(null);setError("");}}>Delete note</button>}</div></div>
 {editing===row.id?<><label>Edit note<textarea aria-label="Edit note text" autoFocus rows={4} maxLength={5000} value={editBody} onChange={e=>setEditBody(e.target.value)}/></label><label>Note visibility<select aria-label="Edit Intel note visibility" disabled={!row.can_change_visibility} value={editPrivate?"private":"public"} onChange={e=>setEditPrivate(e.target.value==="private")}><option value="private">Private Note — author only</option><option value="public">Public Note — EQM intel users</option></select></label><div className="intel-note-actions"><button disabled={busy||!editBody.trim()} onClick={()=>void run(async()=>{const next=await api<Note>(`${path}/${row.id}`,{method:"PATCH",body:JSON.stringify({body:editBody,is_private:editPrivate,expected_body:original,expected_is_private:originalPrivate})});if(mounted.current){setNotes(old=>old.map(n=>n.id===next.id?next:n));setEditing(null);window.dispatchEvent(new Event("eqm-character-notes"));}})}>Save changes</button><button disabled={busy} onClick={()=>setEditing(null)}>Cancel edit</button></div></>:<p>{row.body}</p>}
 <a href={noteSearchLink(row.body)}>Find characters with matching note text</a>
 {deleting===row.id&&<div className="intel-note-delete" role="group" aria-label="Confirm note deletion"><p>Delete this note permanently?</p><div className="intel-note-actions"><button disabled={busy} onClick={()=>void run(async()=>{await api(`${path}/${row.id}`,{method:"DELETE",body:JSON.stringify({expected_body:row.body,expected_is_private:Boolean(row.is_private)})});if(mounted.current){setNotes(old=>old.filter(n=>n.id!==row.id));setDeleting(null);window.dispatchEvent(new Event("eqm-character-notes"));}})}>Confirm delete</button><button disabled={busy} onClick={()=>setDeleting(null)}>Keep note</button></div></div>}
 </article>)}
 </section>;
}
