import {useEffect,useState} from "react";
import type {StructuresApi} from "./ManualPosPanel";

type Setting={id:number;source:string;source_id:string;token_key:number;enabled:boolean;roles:string[];minutes:number[];version:number;status:string;events:{kind:string;deadline:string;event_id:number}[]};
type Meta={can_manage:boolean;roles:{name:string;label:string}[];rows:Setting[]};

export function StructureTimerSettings({api,source,sourceId,tokenKey=0,revision}:{api:StructuresApi;source:string;sourceId:string;tokenKey?:number;revision:string}){
  const [meta,setMeta]=useState<Meta|null>(null),[setting,setSetting]=useState<Setting|null>(null);
  const [enabled,setEnabled]=useState(false),[roles,setRoles]=useState<string[]>(["officer","director"]),[minutes,setMinutes]=useState("1440, 60");
  const [error,setError]=useState(""),[busy,setBusy]=useState(false),[saved,setSaved]=useState(false);
  useEffect(()=>{const controller=new AbortController();setError("");void api<Meta>("/structure-timers",{signal:controller.signal}).then(data=>{
    if(controller.signal.aborted)return;setMeta(data);const row=data.rows.find(r=>r.source===source&&r.source_id===sourceId&&r.token_key===tokenKey)??null;
    setSetting(row);setEnabled(row?.enabled??false);setRoles(row?.roles??["officer","director"]);setMinutes((row?.minutes??[1440,60]).join(", "));setSaved(false);
  }).catch(err=>{if(!controller.signal.aborted)setError(err instanceof Error?err.message:"Unable to load timer settings");});return ()=>controller.abort();},[api,source,sourceId,tokenKey,revision]);
  async function save(){setBusy(true);setError("");setSaved(false);try{
    const leads=minutes.split(",").map(v=>Number(v.trim()));
    if(!roles.length||!leads.length||leads.length>8||leads.some(v=>!Number.isInteger(v)||v<1||v>43200))throw Error("Choose at least one role and up to eight reminders, 1–43200 minutes each.");
    const row=await api<Setting>("/structure-timers",{method:"PUT",body:JSON.stringify({source,source_id:sourceId,token_key:tokenKey,enabled,roles,minutes:leads,version:setting?.version??0})});setSetting(row);setSaved(true);
  }catch(err){setError(err instanceof Error?err.message:"Unable to save timer settings");}finally{setBusy(false);}}
  if(meta&&!meta.can_manage)return null;
  return <details className="structure-reminder-settings"><summary>Calendar timers & reminders{setting?.enabled?" · enabled":""}</summary>
    {!meta?<p role={error?"alert":"status"}>{error||"Loading timer settings…"}</p>:<div className="stacked">
      <label className="structures-check"><input type="checkbox" checked={enabled} disabled={busy} onChange={e=>{setEnabled(e.target.checked);setSaved(false);}}/>Create calendar timers and send reminders</label>
      <p className="muted">Shares the structure name, location and fuel/reinforcement deadlines with selected eligible roles. Private POS notes and quantities stay private. Reminders appear in EQM Messages and a flashing banner.</p>
      <fieldset disabled={busy}><legend>Recipient roles</legend><div className="structure-reminder-roles">{meta.roles.filter(r=>r.name!=="applicant").map(r=><label className="structures-check" key={r.name}><input type="checkbox" checked={roles.includes(r.name)} onChange={e=>{setRoles(current=>e.target.checked?[...current,r.name]:current.filter(v=>v!==r.name));setSaved(false);}}/>{r.label}</label>)}</div></fieldset>
      <label>Remind before deadline (minutes, separated by commas)<input value={minutes} disabled={busy} onChange={e=>{setMinutes(e.target.value);setSaved(false);}} placeholder="1440, 60"/></label>
      <small>60 = 1 hour · 1440 = 1 day · up to 8 reminders, maximum 30 days. Recipients must have Structures and Calendar access. Runs while you are offline.</small>
      <p className="muted">Fuel timers require an online manual POS fuel reading or ESI fuel expiry. Reinforcement requires an active reinforcement deadline; manual stront estimates are supported. No attack detection.</p>
      <div className="button-row"><button disabled={busy} onClick={()=>void save()}>{busy?"Saving…":"Save timer settings"}</button></div>
      {error&&<p role="alert" className="mini-alert">{error}</p>}{saved&&<p role="status">Timer settings saved.</p>}
      {setting&&<><p className="muted">{setting.status}{setting.enabled&&!setting.events.length?" · no active deadlines; waiting for a reading/state change":""}</p>{setting.events.map(event=><a key={event.kind} href={`#events/${event.event_id}`}>{event.kind==="fuel"?"Fuel depletion":"Reinforcement ends"} · {new Date(event.deadline).toLocaleString()}</a>)}</>}
    </div>}
  </details>;
}
