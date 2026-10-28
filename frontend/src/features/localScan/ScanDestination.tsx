import { useState } from "react";
import type { ApiClient } from "./types";

type Character = {token_id: number; character_id: number; name: string};
export function ScanDestination({api, system}: {api: ApiClient; system: {id: number; name: string}}) {
  const [characters, setCharacters] = useState<Character[] | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [clear, setClear] = useState(false);
  async function connect() {
    setBusy(true); setMessage("");
    try {
      const auth = await api<{ready:boolean;url?:string;message?:string}>("/esi/auth-url?scope_group=waypoint");
      if (auth.ready && auth.url) window.location.assign(auth.url);
      else setMessage(auth.message ?? "EVE SSO is not configured.");
    } catch(e) {setMessage(e instanceof Error ? e.message : "Sign in to EQM before linking a character.");}
    finally {setBusy(false);}
  }
  async function open() {
    setBusy(true); setMessage("");
    try {setCharacters(await api<Character[]>("/local-scans/destination-characters"));}
    catch (e) {setMessage(e instanceof Error ? e.message : "Sign in to choose your linked characters.");}
    finally {setBusy(false);}
  }
  async function send() {
    setBusy(true); setMessage("");
    const results: string[] = [];
    for (const character of characters ?? []) {
      if (!selected.includes(character.token_id)) continue;
      try {await api("/esi/ui/waypoint",{method:"POST",body:JSON.stringify({token_id: character.token_id, destination_id:system.id, clear_other_waypoints:clear, add_to_beginning:false})}); results.push(`${character.name}: destination sent`);}
      catch (e) {results.push(`${character.name}: ${e instanceof Error ? e.message : "failed"}`);}
    }
    setMessage(results.join(" · ")); setBusy(false);
  }
  return <div className="scan-destination"><button type="button" disabled={busy} onClick={() => void open()}>Set Destination</button>{characters !== null && <fieldset><legend>Send {system.name} to your characters</legend>{characters.map(c => <label key={c.token_id}><input type="checkbox" checked={selected.includes(c.token_id)} onChange={e => setSelected(ids => e.target.checked ? [...ids,c.token_id] : ids.filter(id => id !== c.token_id))}/>{c.name}</label>)}{characters.length === 0 && <p className="muted">No linked characters have esi-ui.write_waypoint.v1. Enable that scope and re-link a character through EVE SSO.</p>}<button type="button" disabled={busy} onClick={() => void connect()}>Link a character for destinations</button><label><input type="checkbox" checked={clear} onChange={e => setClear(e.target.checked)}/>Replace existing waypoints (otherwise append)</label><div className="scan-report-actions"><button type="button" disabled={busy || selected.length === 0} onClick={() => void send()}>{busy ? "Sending…" : "Send to selected characters"}</button><button type="button" disabled={busy} onClick={() => {setCharacters(null); setSelected([]);}}>Close</button></div></fieldset>}{message && <p role="status">{message}</p>}</div>;
}
