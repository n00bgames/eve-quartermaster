import {useEffect,useState,type FormEvent} from "react";
import {Plus,RefreshCw,Shield} from "lucide-react";
import {durationHours,fuelEstimate,manualAttention,reinforcementTimer,strontEstimate,type ManualPos} from "./manualModel";
import {StructureTimerSettings} from "./StructureTimerSettings";
import {ManualPosForm} from "./ManualPosForm";

export type StructuresApi = <T>(path:string,options?:RequestInit)=>Promise<T>;
export type StructuresDate = (value?:string|null)=>string;

export function ManualPosPanel({api,date}:{api:StructuresApi;date:StructuresDate}) {
  const [rows,setRows]=useState<ManualPos[]>([]),[loading,setLoading]=useState(true),[loaded,setLoaded]=useState(false);
  const [error,setError]=useState(""),[reload,setReload]=useState(0),[editor,setEditor]=useState<ManualPos|"new"|null>(null);
  const [search,setSearch]=useState(""),[attention,setAttention]=useState(false),[now,setNow]=useState(Date.now());
  useEffect(()=>{const clock=window.setInterval(()=>setNow(Date.now()),30000);return ()=>clearInterval(clock);},[]);
  useEffect(()=>{const controller=new AbortController();setLoading(true);setError("");
    void api<{rows:ManualPos[]}>("/structures/manual-pos",{signal:controller.signal}).then(data=>{
      if(!controller.signal.aborted){setRows(data.rows);setLoaded(true);}
    }).catch(err=>{if(!controller.signal.aborted)setError(err instanceof Error?err.message:"Unable to load manual POS records.");})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[api,reload]);
  const visible=rows.filter(row=>(!attention||manualAttention(row,now))&&
    [row.name,row.tower_type,row.location,row.corporation_name,row.notes,row.state].some(text=>text.toLowerCase().includes(search.trim().toLowerCase())));
  function saved(row:ManualPos){setRows(current=>[...current.filter(item=>item.id!==row.id),row].sort((a,b)=>a.name.localeCompare(b.name)));setEditor(null);setNow(Date.now());}
  return <section className="manual-pos-section stacked" aria-label="Manual POS tracking">
    <div className="structures-actions"><div><h4>Manual POS tracking</h4><p className="muted">Private to your EQM account · saved across devices · no Director or ESI connection needed.</p></div>
      <div className="button-row"><button onClick={()=>{setEditor(null);setReload(value=>value+1);}} disabled={loading||editor!==null}><RefreshCw size={14}/>{loading?"Loading records…":"Reload records"}</button>
        <button onClick={()=>setEditor("new")} disabled={editor!==null||!loaded}><Plus size={14}/>Add manual POS</button></div></div>
    {error&&<p className="mini-alert" role="alert">{error}{loaded&&" Previously loaded records remain below."}</p>}
    {editor!==null&&<ManualPosForm key={editor==="new"?"new":editor.id} row={editor==="new"?null:editor} api={api} onSave={saved} onCancel={()=>setEditor(null)}/>}
    <p className="notice">User-entered readings and estimates. This does not monitor EVE or send attack alerts. Update the reading after refueling, changing rates, or changing the tower’s state.</p>
    {loaded&&<><div className="structures-filters"><label>Find a manual POS<input value={search} onChange={event=>setSearch(event.target.value)} placeholder="Name, tower, location, corporation or notes"/></label>
      <label className="structures-check"><input type="checkbox" checked={attention} onChange={event=>setAttention(event.target.checked)}/>Manual POS needs attention</label></div>
      <p className="muted">{visible.length} of {rows.length} manual POS records · {rows.filter(row=>manualAttention(row,now)).length} need attention (reinforced, offline or estimated fuel within 72 hours).</p>
      {!visible.length&&<p>{rows.length?"No manual POS records match these filters.":"No manual POS records yet. Add your tower and its latest fuel reading to begin."}</p>}
      <div className="structures-grid">{visible.map(row=><ManualPosCard key={row.id} row={row} api={api} date={date} now={now} editing={editor!==null}
        onEdit={()=>setEditor(row)} onRemove={()=>setRows(current=>current.filter(item=>item.id!==row.id))}/>)}</div></>}
  </section>;
}

function ManualPosCard({row,api,date,now,editing,onEdit,onRemove}:{row:ManualPos;api:StructuresApi;date:StructuresDate;now:number;editing:boolean;onEdit:()=>void;onRemove:()=>void}) {
  const [confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const fuel=fuelEstimate(row,now),stront=strontEstimate(row,now),reinforced=reinforcementTimer(row,now);
  async function remove(event:FormEvent){event.preventDefault();setBusy(true);setError("");try{
    await api<void>(`/structures/manual-pos/${row.id}?version=${row.version}`,{method:"DELETE"});onRemove();
  }catch(err){setError(err instanceof Error?err.message:"Unable to remove this record.");}finally{setBusy(false);}}
  return <article className={`structures-card manual-pos-card${manualAttention(row,now)?" structures-attention":""}`}>
    <header><span className="structures-kind"><Shield size={14}/>Manual POS · Private</span><span className={manualAttention(row,now)?"scope-warn":"scope-ok"}>{row.state[0].toUpperCase()+row.state.slice(1)} · entered</span></header>
    <h4>{row.name}</h4><p className="muted">{row.tower_type}</p><p>{row.location||"Location not entered"}</p>{row.corporation_name&&<p className="muted">{row.corporation_name}</p>}
    <div className="structures-timers"><div className="structures-time"><span>Estimated fuel remaining</span><strong>{fuel?(fuel.hoursLeft>0?`~${durationHours(fuel.hoursLeft)}`:"Estimate exhausted · verify in game"):row.state==="online"?(row.fuel_blocks===null?"Fuel quantity unknown":"Estimate unavailable"):"No live estimate for this state"}</strong>
      {fuel&&<><small>~{fuel.blocksLeft.toLocaleString()} blocks remaining</small><time dateTime={fuel.expiresAt}>Estimated depletion {date(fuel.expiresAt)}<span>{utcStamp(fuel.expiresAt)}</span></time></>}
      <small>{row.fuel_blocks===null?"Quantity not entered":`${row.fuel_blocks.toLocaleString()} blocks recorded`} · {row.fuel_per_hour} blocks/hour</small></div>
      <div className="structures-time"><span>{row.state==="reinforced"?"Estimated strontium remaining":"Recorded strontium"}</span><strong>{row.state==="reinforced"?(stront?`~${stront.blocksLeft.toLocaleString()} units`:"Quantity unknown"):(row.stront_units===null?"Quantity unknown":`${row.stront_units.toLocaleString()} units`)}</strong>
        {stront&&<small>~{durationHours(stront.hoursLeft)} remaining at {row.stront_per_hour}/hour.</small>}
        {row.stront_units!==null&&<small>{row.stront_units.toLocaleString()} units recorded · capacity ~{durationHours(row.stront_units/row.stront_per_hour)} at {row.stront_per_hour}/hour{row.state!=="reinforced"?". Not an active timer.":"."}</small>}</div>
      {row.state==="reinforced"&&<div className="structures-time"><span>Reinforcement ends · {reinforced?.source??"manual"}</span><strong>{reinforced===null?"Enter stront quantity or an exact end":reinforced.hoursLeft<=0?"Elapsed · verify in game":durationHours(reinforced.hoursLeft)}</strong>
        {reinforced&&<time dateTime={reinforced.at}>{date(reinforced.at)}<span>{utcStamp(reinforced.at)}</span></time>}{reinforced?.source==="entered"&&<small>Entered end time overrides the strontium estimate.</small>}</div>}</div>
    <p className="muted">Reading {date(row.observed_at)} · {utcStamp(row.observed_at)}</p><p className="muted manual-pos-assumptions">Countdowns assume continuous operation in the recorded state at the entered rate: fuel while online, strontium while reinforced. Hourly ticks and bonuses can shift depletion. Quantities do not update from EVE.</p>
    <StructureTimerSettings api={api} source="manual" sourceId={row.id} revision={String(row.version)}/>
    {row.notes&&<p className="manual-pos-notes">{row.notes}</p>}
    <div className="button-row"><button disabled={editing||busy} onClick={onEdit}>Update reading / edit</button><button disabled={editing||busy} onClick={()=>setConfirm(true)}>Remove record</button></div>
    {confirm&&<form className="manual-pos-delete" onSubmit={event=>void remove(event)}><p>Remove “{row.name}” from your manual records? This only removes the EQM record.</p><div className="button-row"><button disabled={busy||editing} type="submit">{busy?"Removing…":"Confirm removal"}</button><button type="button" disabled={busy} onClick={()=>setConfirm(false)}>Keep record</button></div></form>}
    {error&&<p role="alert" className="mini-alert">{error}</p>}
  </article>;
}

function utcStamp(at:string){return new Date(at).toISOString().replace("T"," ").replace(".000Z"," UTC");}
