import {useEffect,useState} from "react";
import type {ApiClient} from "./types";
import type {AutomaticRule} from "./highlights";
type Character = {token_id:number;character_id:number;name:string;can_read:boolean};
type Settings = {characters:Character[];selected_token_id:number|null;source_name:string|null;source_unavailable:boolean;enabled:boolean;synced_at:string|null;automatic_rules:AutomaticRule[]};
export function StandingsColors({api,basePath,onRules,disabled}:{api:ApiClient;basePath:string;onRules:(rules:AutomaticRule[])=>void;disabled:boolean}) {
  const [settings,setSettings]=useState<Settings|null>(null);
  const [selected,setSelected]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  useEffect(()=>{let active=true;void api<Settings>(`${basePath}/color-settings`).then(value=>{if(active){setSettings(value);onRules(value.automatic_rules);const remembered=sessionStorage.getItem("eqm-scan-standings-selection");setSelected(String(value.selected_token_id??value.characters.find(c=>String(c.token_id)===remembered)?.token_id??""));}}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Could not load standings source.");});return()=>{active=false;};},[api,basePath,onRules]);
  const character=settings?.characters.find(c=>String(c.token_id)===selected);
  async function save(tokenId:number|null) {
    setBusy(true);setError("");
    try {const value=await api<Settings>(`${basePath}/color-settings`,{method:"POST",body:JSON.stringify({token_id:tokenId})});setSettings(value);onRules(value.automatic_rules);setSelected(String(value.selected_token_id??""));}
    catch(e){setError(e instanceof Error?e.message:"Could not refresh standings.");}finally{setBusy(false);}
  }
  async function authorize() {
    if(!character)return;setBusy(true);setError("");
    try {const value=await api<{auth_url:string}>(`${basePath}/color-settings/${character.token_id}/auth-url`);sessionStorage.setItem("eqm-scan-standings-selection",selected);window.location.assign(value.auth_url);}
    catch(e){setError(e instanceof Error?e.message:"Could not enable contact access.");setBusy(false);}
  }
  return <section className="scan-standings"><h4>Automatic standings colors</h4><p className="muted">Use one of your linked characters’ corporation/alliance contacts. Manual colors take priority. This reads contacts only; it never changes in-game standings.</p><div className="scan-highlight-form"><label>Standings character<select aria-label="Standings character" value={selected} disabled={busy||disabled||!settings} onChange={e=>setSelected(e.target.value)}><option value="">Choose your character</option>{settings?.characters.map(c=><option key={c.token_id} value={c.token_id}>{c.name}{c.can_read?"":" · contact access needed"}</option>)}</select></label>{character&&!character.can_read?<button type="button" disabled={busy||disabled} onClick={()=>void authorize()}>Enable read-only contacts</button>:<button type="button" disabled={busy||disabled||!character} onClick={()=>void save(Number(selected))}>{busy?"Refreshing contacts…":settings?.selected_token_id===Number(selected)?"Refresh standings":"Use this character"}</button>}{(settings?.enabled||settings?.source_unavailable)&&<button type="button" disabled={busy||disabled} onClick={()=>void save(null)}>Use manual colors only</button>}</div>
    <p className="muted">{settings?.enabled?`${settings.source_name} · ${settings.automatic_rules.length} organization contacts · Last refreshed ${settings.synced_at?new Date(settings.synced_at).toLocaleString():"unknown"}.`:settings?.source_unavailable?"The selected source needs an active linked character and contact authorization. Automatic colors are disabled.":"Manual colors only until you choose and load a character."} Refresh after changing contacts in EVE. Unlisted organizations stay unmarked.</p>
    <p className="scan-standings-legend"><span>Terrible: EVE Red</span><span>Bad: EVE Orange</span><span>Neutral: EVE Gray</span><span>Good: EVE Light Blue</span><span>Excellent: EVE Blue</span></p>{error&&<p role="alert" className="alert">{error}</p>}
  </section>;
}
