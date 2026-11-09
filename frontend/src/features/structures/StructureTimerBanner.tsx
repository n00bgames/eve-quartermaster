import {useEffect,useState} from "react";
import type {StructuresApi} from "./ManualPosPanel";
import "./structures.css";
type Alert={id:number;title:string;body:string;deadline:string;event_id:number};

export function StructureTimerBanner({api,onOpenEvent}:{api:StructuresApi;onOpenEvent:(id:number)=>void}){
  const [rows,setRows]=useState<Alert[]>([]),[error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();async function load(){try{const result=await api<{rows:Alert[]}>("/structure-timers/alerts",{signal:controller.signal});if(!controller.signal.aborted)setRows(result.rows);}catch{if(!controller.signal.aborted)setRows([]);}}
    void load();const timer=window.setInterval(()=>{if(!document.hidden)void load();},30000);const visible=()=>{if(!document.hidden)void load();};document.addEventListener("visibilitychange",visible);
    return ()=>{controller.abort();clearInterval(timer);document.removeEventListener("visibilitychange",visible);};},[api]);
  async function dismiss(id:number){setError("");try{await api(`/structure-timers/alerts/${id}/dismiss`,{method:"POST"});setRows(current=>current.filter(r=>r.id!==id));}catch{setError("Could not dismiss reminder. Please retry.");}}
  if(!rows.length)return null;
  return <aside className="structure-timer-banner" aria-label="Structure timer reminders" role="status"><strong>Structure timer reminder{rows.length>1?"s":""}</strong>{rows.map(row=><div key={row.id}><p><strong>{row.title}</strong> · {new Date(row.deadline).toLocaleString()}</p><div className="button-row"><button onClick={()=>onOpenEvent(row.event_id)}>View calendar timer</button><button onClick={()=>void dismiss(row.id)}>Dismiss reminder</button></div></div>)}{error&&<p role="alert">{error}</p>}</aside>;
}
