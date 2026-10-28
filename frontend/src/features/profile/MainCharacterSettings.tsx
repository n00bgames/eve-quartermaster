import {useEffect,useState} from "react";
import type {ApiClient} from "../localScan/types";
type Choices={main_character_id:number|null;characters:{character_id:number;name:string}[]};
export function MainCharacterSettings({api,linkedCharacterId,onSaved}:{api:ApiClient;linkedCharacterId?:number;onSaved?:()=>void}) {
  const [data,setData]=useState<Choices|null>(null),[selected,setSelected]=useState(""),[busy,setBusy]=useState(false),[notice,setNotice]=useState("");
  useEffect(()=>{let active=true;void api<Choices>("/auth/me/characters").then(d=>{if(active){setData(d);setSelected(String(d.main_character_id??""));}}).catch(e=>{if(active)setNotice(e.message);});return()=>{active=false;};},[api]);
  useEffect(()=>{const sync=(e:Event)=>{const id=(e as CustomEvent<number|null>).detail;setData(d=>d?{...d,main_character_id:id}:d);setSelected(String(id??""));};window.addEventListener("eqm-main-character",sync);return()=>window.removeEventListener("eqm-main-character",sync);},[]);
  async function save(id:number|null){setBusy(true);setNotice("");try{await api("/auth/me/main-character",{method:"PUT",body:JSON.stringify({main_character_id:id})});setData(d=>d?{...d,main_character_id:id}:d);setSelected(String(id??""));window.dispatchEvent(new CustomEvent("eqm-main-character",{detail:id}));setNotice("Main character saved. Named reports now use this identity, including existing reports.");onSaved?.();}catch(e){setNotice(e instanceof Error?e.message:"Unable to save main character.");}finally{setBusy(false);}}
  const linked=data?.characters.find(c=>c.character_id===linkedCharacterId);
  if(linkedCharacterId && !linked)return null;
  return <section className="panel stacked main-character-settings"><h3>{linked?`${linked.name} linked` : "Main character"}</h3>
    <p className="muted">Named reports use your main character, including existing reports. Account names are never used; without a main, attribution is Anonymous.</p>
    {linked?<label className="check"><input type="checkbox" checked={data?.main_character_id===linked.character_id} disabled={busy} onChange={e=>void save(e.target.checked?linked.character_id:null)}/>Set {linked.name} as my main character</label>:<form onSubmit={e=>{e.preventDefault();void save(selected?Number(selected):null);}}><label>Main character<select aria-label="Main character" value={selected} disabled={!data||busy} onChange={e=>setSelected(e.target.value)}><option value="">No main selected (Anonymous)</option>{data?.characters.map(c=><option key={c.character_id} value={c.character_id}>{c.name}</option>)}</select></label><button type="submit" disabled={!data||busy}>{busy?"Saving…":"Save main character"}</button></form>}
    {notice&&<p role="status">{notice}</p>}
  </section>;
}
