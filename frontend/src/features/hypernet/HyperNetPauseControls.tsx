import { useEffect, useRef, useState } from "react";
import type { ApiClient, HyperNetPause } from "../../types/hypernet";

export function HyperNetPauseControls({ api, value, onChanged, disabled = false }: {
  api: ApiClient; value?: HyperNetPause; onChanged: (value: HyperNetPause) => void; disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function save(paused: boolean, characterId?: number) {
    if (saving || disabled || !value) return;
    setSaving(true); setError("");
    try {
      const next = await api<HyperNetPause>("/hypernet/pause", { method: "PATCH", body: JSON.stringify({ paused, ...(characterId == null ? {} : { character_id: characterId }) }) });
      if (mounted.current) onChanged(next);
    } catch (err) { if (mounted.current) setError(err instanceof Error ? err.message : "Unable to change HyperNet pause."); }
    finally { if (mounted.current) setSaving(false); }
  }
  return <div className="hypernet-pause-controls">
    <button type="button" onClick={() => setOpen(old => !old)} aria-expanded={open}>HyperNet pause controls</button>
    {open && <section className="panel stacked" aria-label="HyperNet pause controls">
      <h4>Temporarily pause HyperNet in EQM</h4>
      <p>Pausing prevents new bid and offer records, including drafts. Existing records, corrections, outcome updates, and opted-in analytics remain available. You can resume at any time.</p>
      <p className="muted">These switches affect EQM only. They do not block HyperNet purchases in EVE or request an in-game self-exclusion.</p>
      {!value ? <p>Refresh HyperNet to load your pause settings.</p> : <>
        <label><input type="checkbox" checked={value.account_paused} disabled={saving || disabled} onChange={event => void save(event.target.checked)} />Pause HyperNet for my EQM account</label>
        <p className="muted">The account pause covers every character, including newly linked ones. Individual switches are preserved when the account resumes.</p>
        {value.characters.length > 0 && <div className="hypernet-pause-characters">{value.characters.map(row => <label key={row.id}>
          <input type="checkbox" aria-label={`Pause HyperNet for ${row.name}`} checked={row.paused} disabled={saving || disabled || value.account_paused} onChange={event => void save(event.target.checked, row.id)} />Pause HyperNet for {row.name}{value.account_paused && <small>Paused by account switch</small>}
        </label>)}</div>}
      </>}
      {saving && <p role="status">Saving HyperNet pause…</p>}
      {error && <div role="alert" className="mini-alert">{error}</div>}
    </section>}
  </div>;
}
