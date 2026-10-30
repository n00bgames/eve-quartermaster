import {useEffect,useRef,useState} from "react";
import type {Dispatch,SetStateAction} from "react";
import type {ApiClient} from "./types";
import {IntelShipLabel} from "./IntelShipLabel";
export type SightingChoice={id:number;name:string;detail?:string|null};
export type SightingDraft={systemText:string;shipText:string;timeText:string;system:SightingChoice|null;ship:SightingChoice|null};
export const emptySighting:SightingDraft={systemText:"",shipText:"",timeText:"",system:null,ship:null};
export function IntelSightingFields({api,value,onChange,disabled}:{api:ApiClient;value:SightingDraft;onChange:Dispatch<SetStateAction<SightingDraft>>;disabled:boolean}){
 return <fieldset className="intel-sighting-fields" disabled={disabled}><legend>Optional ship sighting</legend><Picker api={api} kind="system" label="Sighting system" text={value.systemText} selected={value.system} onChange={(text,selected)=>onChange(old=>({...old,systemText:text,system:selected}))}/><Picker api={api} kind="ship" label="Sighting ship type (optional)" text={value.shipText} selected={value.ship} onChange={(text,selected)=>onChange(old=>({...old,shipText:text,ship:selected}))}/>
 {value.system&&!value.shipText.trim()&&<IntelShipLabel typeId={null} name="Unknown Ship Type"/>}
 <label>Sighting time (UTC)<input type="datetime-local" onInput={e=>{const time=e.currentTarget.value;onChange(old=>({...old,timeText:time}));}} value={value.timeText} onChange={e=>{const time=e.currentTarget.value;onChange(old=>({...old,timeText:time}));}}/></label><small>Optional: enter an earlier sighting time in UTC. Leave blank to use the report-run time.</small>
 <small>{value.system?"Opening or refreshing a character report will record this system at the entered time, or current UTC time when blank. Leave ship blank for Unknown Ship Type. Kills and losses stay unchanged.":"Select a system to record a sighting when running a character report. Ship type and UTC time are optional. Without a system, open the report without a sighting."}</small>
 {(value.systemText||value.shipText||value.timeText)&&<button type="button" onClick={()=>onChange({...emptySighting})}>Clear sighting fields</button>}</fieldset>;
}
function Picker({api,kind,label,text,selected,onChange}:{api:ApiClient;kind:"system"|"ship";label:string;text:string;selected:SightingChoice|null;onChange:(text:string,selected:SightingChoice|null)=>void}){
 const [choices,setChoices]=useState<SightingChoice[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(false);
 const update=useRef(onChange);update.current=onChange;
 useEffect(()=>{setChoices([]);setError("");setLoading(false);if(!text.trim()||selected)return;
  const controller=new AbortController();let active=true;
  const timer=window.setTimeout(()=>{setLoading(true);void api<SightingChoice[]>(`/intel/sighting-lookups?kind=${kind}&q=${encodeURIComponent(text.trim())}`,{signal:controller.signal}).then(rows=>{
   if(!active)return;const exact=rows.find(r=>r.name.toLocaleLowerCase()===text.trim().toLocaleLowerCase());
   if(exact)update.current(exact.name,exact);else setChoices(rows);
  }).catch(err=>{if(active)setError(err instanceof Error?err.message:"Lookup unavailable.");}).finally(()=>{if(active)setLoading(false);});},200);
  return()=>{active=false;clearTimeout(timer);controller.abort();};
 },[api,kind,text,selected?.id]);
 return <div><label>{label}<input value={text} maxLength={120} autoComplete="off" onChange={e=>onChange(e.target.value,null)} placeholder={kind==="system"?"Search a solar system":"Search a ship hull"}/></label>
 {selected&&<small className="intel-sighting-selected">Selected: {selected.name}{selected.detail?` · ${selected.detail}`:""}</small>}{loading&&<small role="status">Searching…</small>}{error&&<small role="alert">{error}</small>}
 {!!choices.length&&<div className="intel-sighting-choices">{choices.map(row=><button type="button" key={row.id} onClick={()=>onChange(row.name,row)}><strong>{row.name}</strong><small>{row.detail}</small></button>)}</div>}
 </div>;
}
