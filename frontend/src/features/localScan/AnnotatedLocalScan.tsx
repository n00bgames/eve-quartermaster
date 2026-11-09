import {useEffect,useRef,useState,type ComponentProps} from "react";
import {LocalScanResults} from "./LocalScanResults";
import type {ScanNotes} from "../intel/noteLinks";
import "../intel/noteSearch.css";

type Props=ComponentProps<typeof LocalScanResults>&{canViewNotes:boolean;canNote:boolean};
type BatchResult={character_count:number;created:number;replayed:boolean;is_private:boolean};

export function AnnotatedLocalScan({canViewNotes,canNote,...props}:Props) {
  const {report,api}=props;
  const [notes,setNotes]=useState<ScanNotes>({}),[draft,setDraft]=useState(""),[isPrivate,setPrivate]=useState(true);
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState(""),[revision,setRevision]=useState(0);
  const pending=useRef<{signature:string;id:string}|null>(null),mounted=useRef(true);
  const path=`/local-scans/reports/${encodeURIComponent(report.token)}/notes`;
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{if(!canViewNotes){setNotes({});return;}const controller=new AbortController();
    void api<{characters:ScanNotes}>(path,{signal:controller.signal}).then(result=>{if(!controller.signal.aborted)setNotes(result.characters);})
      .catch(err=>{if(!controller.signal.aborted)setError(err instanceof Error?err.message:"Character notes could not be loaded.");});
    return()=>controller.abort();
  },[api,path,canViewNotes,revision]);
  async function save(){if(!draft.trim()||busy)return;setBusy(true);setError("");setMessage("");
    const signature=JSON.stringify([report.token,draft.trim(),isPrivate]);
    if(pending.current?.signature!==signature)pending.current={signature,id:crypto.randomUUID()};
    try{
      const result=await api<BatchResult>(path,{method:"POST",body:JSON.stringify({body:draft.trim(),is_private:isPrivate,request_id:pending.current.id})});
      if(!mounted.current)return;
      setMessage(`${result.is_private?"Private":"Public"} note ${result.replayed?"already saved for":"added to"} ${result.character_count.toLocaleString()} resolved characters. Unresolved names were not tagged.`);
      pending.current=null;setDraft("");setRevision(n=>n+1);
      window.dispatchEvent(new Event("eqm-character-notes"));
    }catch(err){if(mounted.current)setError(err instanceof Error?err.message:"Note could not be saved. Retry to check the same request.");}
    finally{if(mounted.current)setBusy(false);}
  }
  return <>
    {canNote&&<div className="scan-note-composer stacked"><h4>Tag every character in this scan</h4><p className="muted">Add the same note to all {report.character_count.toLocaleString()} resolved pilots, even when the result list is filtered. Notes remain on their Intel dossiers after this scan expires or is deleted.</p>
      <label>Character note<textarea aria-label="Note for all scanned characters" rows={2} maxLength={5000} value={draft} disabled={busy} onChange={event=>setDraft(event.target.value)} placeholder="e.g. Suspected multiboxer · Arifsdald mining crew"/></label>
      <label>Note visibility<select aria-label="Scan note visibility" value={isPrivate?"private":"public"} disabled={busy} onChange={event=>setPrivate(event.target.value==="private")}><option value="private">Private Note — only me</option><option value="public">Public Note — EQM intel users</option></select></label>
      <p className="muted">{isPrivate?"Only you can read or search this note.":"Shared with signed-in users who have Intel Reports access."} Notes are excluded from public scan links and PDFs.</p>
      <div className="scan-report-actions"><button type="button" disabled={busy||!draft.trim()} onClick={()=>void save()}>{busy?"Saving character notes…":`Add note to all ${report.character_count.toLocaleString()} pilots`}</button></div>
    </div>}
    {error&&<div className="mini-alert scan-note-notice" role="alert">{error} <button onClick={()=>{setError("");setRevision(n=>n+1);}}>Reload notes</button></div>}
    {message&&<p className="notice scan-note-notice" role="status">{message}</p>}
    <LocalScanResults {...props} characterNotes={canViewNotes?notes:undefined}/>
  </>;
}
