import {useState,type FormEvent} from "react";
import {fromUtcInput,towerPresets,utcInput,type ManualPos,type ManualReading} from "./manualModel";
import type {StructuresApi} from "./ManualPosPanel";

type Draft = Omit<ManualReading,"fuel_blocks"|"stront_units"|"observed_at"|"reinforced_until"> & {
  fuel_blocks:string;stront_units:string;observed_at:string;reinforced_until:string;
};

export function ManualPosForm({row,api,onSave,onCancel}:{row:ManualPos|null;api:StructuresApi;onSave:(row:ManualPos)=>void;onCancel:()=>void}) {
  const [id]=useState(()=>row?.id??crypto.randomUUID());
  const [draft,setDraft]=useState<Draft>(()=>row?{...row,fuel_blocks:row.fuel_blocks===null?"":String(row.fuel_blocks),stront_units:row.stront_units===null?"":String(row.stront_units),observed_at:utcInput(row.observed_at),reinforced_until:row.reinforced_until?utcInput(row.reinforced_until):""}:
    {name:"",tower_type:towerPresets[0].name,corporation_name:"",location:"",state:"online",fuel_blocks:"",fuel_per_hour:40,stront_units:"",stront_per_hour:400,observed_at:utcInput(new Date().toISOString()),reinforced_until:"",notes:""});
  const [preset,setPreset]=useState(()=>towerPresets.find(item=>item.name===draft.tower_type)?.name??"custom");
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  function change<K extends keyof Draft>(key:K,value:Draft[K]){setDraft(current=>({...current,[key]:value}));}
  function choose(value:string){setPreset(value);const next=towerPresets.find(item=>item.name===value);if(next)setDraft(current=>({...current,tower_type:next.name,fuel_per_hour:next.fuel,stront_per_hour:next.stront}));}
  async function submit(event:FormEvent){event.preventDefault();setError("");setBusy(true);try{
    const body:ManualReading={name:draft.name,tower_type:draft.tower_type,corporation_name:draft.corporation_name,location:draft.location,state:draft.state,
      fuel_blocks:draft.fuel_blocks===""?null:Number(draft.fuel_blocks),fuel_per_hour:draft.fuel_per_hour,
      stront_units:draft.stront_units===""?null:Number(draft.stront_units),stront_per_hour:draft.stront_per_hour,
      observed_at:fromUtcInput(draft.observed_at),reinforced_until:draft.state==="reinforced"&&draft.reinforced_until?fromUtcInput(draft.reinforced_until):null,notes:draft.notes};
    const result=await api<ManualPos>(row?`/structures/manual-pos/${row.id}`:"/structures/manual-pos",{method:row?"PUT":"POST",body:JSON.stringify({...body,...(row?{version:row.version}:{id})})});onSave(result);
  }catch(err){setError(err instanceof Error?err.message:"Unable to save this POS reading.");}finally{setBusy(false);}}
  return <form className="manual-pos-form stacked" onSubmit={event=>void submit(event)} aria-label={row?"Edit manual POS":"Add manual POS"}>
    <h4>{row?"Update manual POS reading":"Add a manual POS"}</h4><p className="muted">Private to your account. Enter balances observed in game. Blank quantities mean unknown; zero means empty. All input times are EVE time (UTC).</p>
    <fieldset disabled={busy}><div className="manual-pos-fields">
      <label>POS name<input required maxLength={160} value={draft.name} onChange={event=>change("name",event.target.value)}/></label>
      <label>Tower preset<select aria-label="Tower preset" value={preset} onChange={event=>choose(event.target.value)}>{towerPresets.map(item=><option key={item.name} value={item.name}>{item.label}</option>)}<option value="custom">Faction / custom tower</option></select></label>
      {preset==="custom"&&<label>Tower type<input required maxLength={160} value={draft.tower_type} onChange={event=>change("tower_type",event.target.value)}/></label>}
      <label>Corporation (optional)<input maxLength={160} value={draft.corporation_name} onChange={event=>change("corporation_name",event.target.value)}/></label>
      <label>System / moon (optional)<input maxLength={240} value={draft.location} onChange={event=>change("location",event.target.value)}/></label>
      <label className="structures-check manual-pos-mode"><input type="checkbox" checked={draft.state==="reinforced"} onChange={event=>setDraft(current=>({...current,state:event.target.checked?"reinforced":"online",observed_at:utcInput(new Date().toISOString()),reinforced_until:""}))}/>Reinforced mode</label>
      <label>Recorded state<select aria-label="Recorded state" disabled={draft.state==="reinforced"} value={draft.state} onChange={event=>change("state",event.target.value as Draft["state"])}><option value="online">Online</option><option value="offline">Offline</option>{draft.state==="reinforced"&&<option value="reinforced">Reinforced</option>}<option value="unknown">Unknown</option></select></label>
      <label>Reading time (UTC)<input required type="datetime-local" value={draft.observed_at} onChange={event=>change("observed_at",event.target.value)}/></label>
      <label>Fuel blocks on hand<input type="number" min={0} max={2000000000} step={1} placeholder="Unknown" value={draft.fuel_blocks} onChange={event=>change("fuel_blocks",event.target.value)}/></label>
      <label>Fuel blocks per hour<input required type="number" min={0.01} max={100000} step="any" value={draft.fuel_per_hour} onChange={event=>change("fuel_per_hour",Number(event.target.value))}/></label>
      <label>Strontium units on hand<input type="number" min={0} max={2000000000} step={1} placeholder="Unknown" value={draft.stront_units} onChange={event=>change("stront_units",event.target.value)}/></label>
      <label>Strontium units per hour<input required type="number" min={0.01} max={100000} step="any" value={draft.stront_per_hour} onChange={event=>change("stront_per_hour",Number(event.target.value))}/></label>
      {draft.state==="reinforced"&&<label>Exact reinforcement end (UTC, optional override)<input type="datetime-local" value={draft.reinforced_until} onChange={event=>change("reinforced_until",event.target.value)}/></label>}
    </div><label className="manual-pos-note-field">Notes (optional)<textarea aria-label="Notes (optional)" rows={3} maxLength={4000} value={draft.notes} onChange={event=>change("notes",event.target.value)}/></label>
    <p className="muted">Presets use standard tower rates. Adjust for faction towers or bonuses. Changing a preset replaces both consumption rates. Reinforced mode counts down strontium from the reading time. Switching modes sets that time to now; verify the recorded quantities before saving. Changing state or rate needs a fresh reading.</p>
    <div className="button-row"><button type="button" onClick={()=>change("observed_at",utcInput(new Date().toISOString()))}>Use current UTC time</button><button type="submit">{busy?"Saving…":"Save POS reading"}</button><button type="button" onClick={onCancel}>Cancel</button></div></fieldset>
    {error&&<p className="mini-alert" role="alert">{error} If another tab changed this record, cancel and reload records before editing again.</p>}
  </form>;
}
