import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ClipboardList, Copy, GripVertical, Plus, RefreshCw, Search, ShieldCheck, Users } from "lucide-react";
import type { ApiClient, FleetOperation, FleetPilot, FleetPreset, FleetSlot, FleetSources, FleetSummary, PersonalFleet } from "./types";
import { dropTargets } from "./types";
import "./fleetAssignments.css";

const base = "/fleet-assignments";
const json = (method: string, payload: unknown): RequestInit => ({ method, body: JSON.stringify(payload) });
const personalId = () => window.location.hash.match(/^#fleet-assignments\/my\/(\d+)$/)?.[1];

export function FleetAssignmentsPage({ api }: { api: ApiClient }) {
  const [canManage, setCanManage] = useState(false);
  const [ready, setReady] = useState(false);
  const [personal, setPersonal] = useState(window.location.hash.includes("/my"));
  const [mine, setMine] = useState<PersonalFleet[]>([]);
  const [fleets, setFleets] = useState<FleetSummary[]>([]);
  const [presets, setPresets] = useState<FleetPreset[]>([]);
  const [sources, setSources] = useState<FleetSources>({ fittings: [], doctrines: [], sync_tokens: [] });
  const [operation, setOperation] = useState<FleetOperation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [newName, setNewName] = useState("");
  const [presetId, setPresetId] = useState("");
  const [presetName, setPresetName] = useState("");
  const [name, setName] = useState("");
  const [briefing, setBriefing] = useState("");
  const [roster, setRoster] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [slotKey, setSlotKey] = useState("");
  const [dragOverPilot, setDragOverPilot] = useState<number | null>(null);
  const [pilotSearch, setPilotSearch] = useState("");
  const [onlyUnassigned, setOnlyUnassigned] = useState(false);
  const [fitSearch, setFitSearch] = useState("");
  const [character, setCharacter] = useState("");
  const [doctrine, setDoctrine] = useState("");
  const [fitId, setFitId] = useState("");
  const [role, setRole] = useState("");
  const [target, setTarget] = useState(1);
  const [syncToken, setSyncToken] = useState("");

  function accept(next: FleetOperation) {
    setName((current) => !operation || operation.id !== next.id || current === operation.name ? next.name : current);
    setBriefing((current) => !operation || operation.id !== next.id || current === operation.briefing ? next.briefing : current);
    setOperation(next);
    setSelected((old) => old.filter((id) => next.pilots.some((pilot) => pilot.id === id && pilot.resolved)));
    setSlotKey((old) => next.slots.some((slot) => slot.key === old) ? old : "");
  }
  async function loadLists() {
    const [nextFleets, nextPresets, nextSources] = await Promise.all([
      api<FleetSummary[]>(`${base}/operations`), api<FleetPreset[]>(`${base}/presets`), api<FleetSources>(`${base}/sources`),
    ]);
    setFleets(nextFleets); setPresets(nextPresets); setSources(nextSources);
  }
  async function loadMine() { setMine(await api<PersonalFleet[]>(`${base}/my${personalId() ? `/${personalId()}` : ""}`)); }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); }
    catch (err) {
      setError(err instanceof Error ? err.message : "The request could not be completed.");
      if (operation && !personal) {
        try { accept(await api<FleetOperation>(`${base}/operations/${operation.id}`)); } catch { /* Keep last saved view if offline. */ }
      }
    } finally { setBusy(false); }
  }
  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const meta = await api<{ can_manage: boolean }>(`${base}/meta`);
        if (!live) return;
        setCanManage(meta.can_manage);
        const isPersonal = window.location.hash.includes("/my") || !meta.can_manage;
        setPersonal(isPersonal);
        if (isPersonal) await loadMine(); else await loadLists();
      } catch (err) { if (live) setError(err instanceof Error ? err.message : "Could not load Fleet Assignments"); }
      finally { if (live) setReady(true); }
    })();
    return () => { live = false; };
  }, []);

  async function openFleet(id: number) {
    await run(async () => { setSelected([]); accept(await api<FleetOperation>(`${base}/operations/${id}`)); setRoster(""); });
  }
  async function assign(key: string | null, ids: number[]) {
    if (!operation || !ids.length || busy || operation.status === "archived") return;
    await run(async () => {
      accept(await api<FleetOperation>(`${base}/operations/${operation.id}/assign`, json("POST", { revision: operation.revision, slot_key: key, pilot_ids: ids })));
      setMessage(`${ids.length} pilot assignment${ids.length === 1 ? "" : "s"} ${key ? "saved" : "cleared"}.`);
    });
  }
  async function changeStatus(status: FleetOperation["status"]) {
    if (!operation) return;
    await run(async () => {
      accept(await api<FleetOperation>(`${base}/operations/${operation.id}`, json("PATCH", { revision: operation.revision, status })));
      await loadLists(); setMessage(status === "published" ? "Assignments published. Members can now open their personal link." : `Fleet moved to ${status}.`);
    });
  }
  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); setMessage("Copied to clipboard."); }
    catch { setError("Clipboard access failed. Select and copy the displayed text instead."); }
  }
  const selectedDoctrine = sources.doctrines.find((row) => row.id === Number(doctrine));
  const fits = useMemo(() => sources.fittings.filter((fit) =>
    (!character || fit.character_id === Number(character)) &&
    (!doctrine || selectedDoctrine?.fitting_ids.includes(fit.id)) &&
    `${fit.name} ${fit.ship_name} ${fit.character_name}`.toLowerCase().includes(fitSearch.toLowerCase())),
  [sources, character, doctrine, selectedDoctrine, fitSearch]);
  const pilots = (operation?.pilots ?? []).filter((pilot) => pilot.name.toLowerCase().includes(pilotSearch.toLowerCase()) && (!onlyUnassigned || !pilot.slot_key));
  const editable = !!operation && operation.status !== "archived";
  const personalLink = operation ? new URL(window.location.pathname + operation.personal_path, window.location.origin).href : "";
  const assigned = operation?.pilots.filter((pilot) => pilot.slot_key).length ?? 0;
  const resolved = operation?.pilots.filter((pilot) => pilot.resolved).length ?? 0;

  return <section className="fa-page">
    <header className="panel fa-header"><div><span className="fa-eyebrow">FLEET OPERATIONS</span><h2><ClipboardList size={25}/> Fleet Assignments</h2><p className="muted">Build the composition. Assign the fit. Give every pilot a clear brief.</p></div><div className="button-row">
      {canManage && <button className={!personal ? "active" : ""} onClick={() => { window.location.hash = "fleet-assignments"; }}>Planning board</button>}
      <button className={personal ? "active" : ""} onClick={() => { window.location.hash = "fleet-assignments/my"; }}><ShieldCheck size={16}/> My assignments</button>
      <button disabled={busy || !ready} onClick={() => void run(async () => { if (personal) await loadMine(); else { await loadLists(); if (operation) accept(await api<FleetOperation>(`${base}/operations/${operation.id}`)); } })}><RefreshCw size={16}/> Refresh</button>
    </div></header>
    {error && <div className="mini-alert" role="alert">{error}</div>}{message && <div className="notice inline" role="status">{message}</div>}
    {!ready ? <p className="panel" role="status">Loading Fleet Assignments…</p> : personal ? <>
      <div className="fa-privacy"><ShieldCheck size={18}/><span>Only assignments for your currently linked, authorized characters appear here.</span></div>
      {mine.map((fleet) => <section className="panel stacked" key={fleet.id}><div className="section-heading"><h3>{fleet.name}</h3><span className="fa-badge">YOUR ASSIGNMENTS</span></div>{fleet.briefing && <p className="fa-briefing">{fleet.briefing}</p>}
        <div className="fa-personal-grid">{fleet.assignments.map((pilot) => <article className="fa-personal-card" key={pilot.id}><h3>{pilot.name}</h3>{pilot.fitting && <><div className="fa-ship"><img alt="" src={`https://images.evetech.net/types/${pilot.fitting.ship_type_id}/render?size=64`}/><div><strong>{pilot.fitting.name}</strong><p>{pilot.fitting.ship_name}{pilot.fitting.doctrine_name ? ` · ${pilot.fitting.doctrine_name}` : ""}</p></div></div><FitText fitting={pilot.fitting} onCopy={copy}/></>}</article>)}</div>
      </section>)}{!mine.length && !error && <div className="panel fa-empty"><ShieldCheck size={32}/><h3>No published assignments yet</h3><p>Your fleet commander needs to publish an assignment for one of your linked characters. Link the assigned character through EVE SSO if necessary.</p></div>}
    </> : canManage ? <>
      <section className="panel stacked"><div className="fa-launch-grid"><label>Open fleet<select aria-label="Open fleet" value={operation?.id ?? ""} disabled={busy} onChange={(event) => { if (event.target.value) void openFleet(Number(event.target.value)); }}><option value="">Choose an operation</option>{fleets.map((fleet) => <option key={fleet.id} value={fleet.id}>{fleet.name} · {fleet.status}</option>)}</select></label>
        <form className="fa-create" onSubmit={(event) => { event.preventDefault(); void run(async () => { const next = await api<FleetOperation>(`${base}/operations`, json("POST", { name: newName, preset_id: presetId ? Number(presetId) : null })); setSelected([]); accept(next); setNewName(""); await loadLists(); }); }}><label>New fleet name<input required maxLength={255} value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Friday armor roam"/></label><label>Start from preset<select value={presetId} onChange={(event) => setPresetId(event.target.value)}><option value="">Empty composition</option>{presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.name} · {preset.slot_count} fits</option>)}</select></label><button disabled={busy || !newName.trim()}><Plus size={16}/> Create fleet</button></form>
      </div></section>
      {operation ? <>
        <section className="panel stacked"><div className="section-heading"><div><span className={`fa-badge fa-${operation.status}`}>{operation.status.toUpperCase()}</span><h3>{operation.name}</h3></div><div className="button-row"><button disabled={busy || !editable || (!assigned && operation.status !== "published")} onClick={() => void changeStatus(operation.status === "published" ? "draft" : "published")}>{operation.status === "published" ? "Unpublish" : "Publish assignments"}</button><button disabled={busy} onClick={() => void changeStatus(operation.status === "archived" ? "draft" : "archived")}>{operation.status === "archived" ? "Restore to draft" : "Archive fleet"}</button></div></div>
          {operation.status === "published" && <div className="fa-link"><label>Member link — login required<input readOnly value={personalLink} onFocus={(event) => event.target.select()}/></label><button onClick={() => void copy(personalLink)}><Copy size={15}/> Copy personal-view link</button></div>}
          <details><summary>Fleet brief and preset</summary><div className="fa-edit-grid"><label>Fleet name<input maxLength={255} value={name} onChange={(event) => setName(event.target.value)} disabled={!editable}/></label><label>Briefing shown to assigned pilots<textarea maxLength={10000} value={briefing} onChange={(event) => setBriefing(event.target.value)} disabled={!editable}/></label><div className="button-row"><button disabled={busy || !editable || !name.trim()} onClick={() => void run(async () => { accept(await api<FleetOperation>(`${base}/operations/${operation.id}`, json("PATCH", { revision: operation.revision, name, briefing }))); await loadLists(); setMessage("Fleet brief saved."); })}>Save brief</button></div>
            <div className="fa-link"><label>Save current composition as preset<input maxLength={255} value={presetName} onChange={(event) => setPresetName(event.target.value)} placeholder="Armor roam / standard"/></label><button disabled={busy || !presetName.trim() || !operation.slots.length} onClick={() => void run(async () => { const result = await api<{ operation: FleetOperation }>(`${base}/operations/${operation.id}/preset`, json("POST", { revision: operation.revision, name: presetName })); accept(result.operation); setPresetName(""); await loadLists(); setMessage("Preset saved with fitting snapshots and target counts. Pilot names are excluded."); })}>Save preset</button></div>
            {presets.length > 0 && <label>Remove a preset<select value="" disabled={busy} onChange={(event) => { const id = Number(event.target.value); if (id && window.confirm("Remove this preset? Existing operations keep their own composition.")) void run(async () => { await api(`${base}/presets/${id}`, { method: "DELETE" }); if (presetId === String(id)) setPresetId(""); await loadLists(); }); }}><option value="">Choose preset to remove…</option>{presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.name}</option>)}</select></label>}
          </div></details>
        </section>
        <div className="fa-board">
          <aside className="panel stacked fa-library"><div><span className="fa-eyebrow">01 / FITTING LIBRARY</span><h3>Build your composition</h3><p className="muted">Add fittings, then drag their cards onto pilots. Adding a fit distributes a saved copy to assigned members.</p></div>
            <label>Doctrine<select value={doctrine} onChange={(event) => { setDoctrine(event.target.value); setFitId(""); }}><option value="">All available fittings</option>{sources.doctrines.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
            <label>Source character<select value={character} onChange={(event) => { setCharacter(event.target.value); setFitId(""); }}><option value="">All source characters</option>{Array.from(new Map(sources.fittings.map((fit) => [fit.character_id, fit.character_name])).entries()).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
            <label>Find a fit<input value={fitSearch} onChange={(event) => { setFitSearch(event.target.value); setFitId(""); }} placeholder="Ship or fitting name"/></label>
            <label>Fitting<select aria-label="Fitting" value={fitId} onChange={(event) => setFitId(event.target.value)}><option value="">Choose fitting ({fits.length})</option>{fits.map((fit) => <option key={fit.id} value={fit.id}>{fit.name} · {fit.ship_name} · {fit.character_name}</option>)}</select></label>
            <div className="fa-role-inputs"><label>Role<input value={role} maxLength={120} onChange={(event) => setRole(event.target.value)} placeholder="Damage / logistics"/></label><label>Target<input type="number" min={1} max={500} value={target} onChange={(event) => setTarget(Number(event.target.value))}/></label></div>
            <button disabled={busy || !editable || !fitId || target < 1 || target > 500} onClick={() => void run(async () => { accept(await api<FleetOperation>(`${base}/operations/${operation.id}/slots`, json("POST", { revision: operation.revision, fitting_id: Number(fitId), doctrine_id: doctrine ? Number(doctrine) : null, role, target_count: target }))); setMessage("Fitting snapshot added. Drag its card onto a pilot or select pilots and use Assign selected."); })}><Plus size={16}/> Add fitting role</button>
            <details><summary>Refresh saved fittings from EVE</summary><label>Your authorized character<select value={syncToken} onChange={(event) => setSyncToken(event.target.value)}><option value="">Choose character</option>{sources.sync_tokens.map((token) => <option key={token.id} value={token.id}>{token.name}</option>)}</select></label><button disabled={busy || !syncToken} onClick={() => void run(async () => { await api(`/esi/sync/character-fittings/${syncToken}`, json("POST", {})); await loadLists(); setMessage("Saved EVE fittings refreshed. Existing fleet snapshots stay as assigned."); })}><RefreshCw size={14}/> Sync character fittings</button></details>
            <div className="fa-slots">{operation.slots.map((slot) => <SlotCard key={slot.key} slot={slot} count={operation.pilots.filter((pilot) => pilot.slot_key === slot.key).length} active={slotKey === slot.key} disabled={busy || !editable} onSelect={() => setSlotKey(slot.key)} onCopy={copy} onHover={setDragOverPilot} onAssign={(pilotId) => void assign(slot.key, dropTargets(pilotId, selected))}
              onSave={(nextRole, count) => void run(async () => { accept(await api<FleetOperation>(`${base}/operations/${operation.id}/slots/${slot.key}`, json("PATCH", { revision: operation.revision, role: nextRole, target_count: count }))); })}
              onRemove={() => void run(async () => { accept(await api<FleetOperation>(`${base}/operations/${operation.id}/slots/${slot.key}?revision=${operation.revision}`, { method: "DELETE" })); })}/>)}</div>
            {!operation.slots.length && <p className="fa-empty">Add the first fitting role to begin assigning ships.</p>}
          </aside>
          <section className="panel stacked fa-roster"><div><span className="fa-eyebrow">02 / FLEET ROSTER</span><h3><Users size={18}/> Assign your pilots</h3></div>
            <details open={!operation.pilots.length}><summary>Paste fleet members</summary><label>Character names<textarea rows={6} maxLength={60000} value={roster} onChange={(event) => setRoster(event.target.value)} placeholder={"One character per line, or paste a tab-separated EVE fleet roster"}/></label><button disabled={busy || !editable || !roster.trim()} onClick={() => void run(async () => { const result = await api<{ operation: FleetOperation; report: { added: number; duplicates: string[]; unresolved: string[]; resolved: number; warning: string | null } }>(`${base}/operations/${operation.id}/roster`, json("POST", { revision: operation.revision, text: roster })); accept(result.operation); setRoster(""); setMessage(`${result.report.added} pilots added, ${result.report.duplicates.length} duplicates skipped, ${result.report.resolved} existing names resolved. ${result.report.unresolved.length} unresolved.${result.report.warning ? ` ${result.report.warning}` : ""}`); })}>Import roster</button><p className="muted">Duplicates are skipped. Unresolved names stay visible for correction; paste them again to retry lookup.</p></details>
            <label className="fa-search"><Search size={16}/><input aria-label="Search pilots" value={pilotSearch} onChange={(event) => setPilotSearch(event.target.value)} placeholder="Find pilot"/></label><label className="check"><input type="checkbox" checked={onlyUnassigned} onChange={(event) => setOnlyUnassigned(event.target.checked)}/> Unassigned only</label>
            <div className="fa-assignment-tools"><button disabled={busy || !editable} onClick={() => setSelected(pilots.filter((pilot) => pilot.resolved).map((pilot) => pilot.id))}>Select visible</button><button disabled={!selected.length || busy} onClick={() => setSelected([])}>Deselect</button><select aria-label="Fitting to assign" value={slotKey} onChange={(event) => setSlotKey(event.target.value)}><option value="">Choose fitting role</option>{operation.slots.map((slot) => <option key={slot.key} value={slot.key}>{slot.role ? `${slot.role} · ` : ""}{slot.fitting.name}</option>)}</select><button disabled={busy || !editable || !selected.length || !slotKey} onClick={() => void assign(slotKey, selected)}>Assign selected ({selected.length})</button><button disabled={busy || !editable || !selected.length} onClick={() => void assign(null, selected)}>Clear assignments</button></div>
            <div className="fa-pilot-list">{pilots.map((pilot) => <PilotRow key={pilot.id} pilot={pilot} selected={selected.includes(pilot.id)} dragOver={dragOverPilot === pilot.id} disabled={busy || !editable}
              onToggle={() => setSelected((old) => old.includes(pilot.id) ? old.filter((id) => id !== pilot.id) : [...old, pilot.id])}
              onRemove={() => { if (window.confirm(`Remove ${pilot.name} from this fleet?`)) void run(async () => { accept(await api<FleetOperation>(`${base}/operations/${operation.id}/pilots/${pilot.id}?revision=${operation.revision}`, { method: "DELETE" })); }); }}/>)}</div>
            {!pilots.length && <p className="fa-empty">{operation.pilots.length ? "No pilots match these filters." : "Paste a roster to get started."}</p>}
          </section>
          <aside className="panel stacked fa-composition"><span className="fa-eyebrow">03 / COMPOSITION</span><h3>Fleet readiness</h3><div className="fa-stat"><strong>{assigned}<small> / {operation.pilots.length}</small></strong><span>Pilots assigned</span></div><p className="muted">{resolved} resolved · {operation.pilots.length - resolved} need name correction</p>
            {operation.slots.map((slot) => { const count = operation.pilots.filter((pilot) => pilot.slot_key === slot.key).length; return <div className="fa-composition-row" key={slot.key}><div><strong>{slot.role || slot.fitting.ship_name}</strong><span>{slot.fitting.name}</span></div><b className={count >= slot.target_count ? "fa-full" : ""}>{count}/{slot.target_count}</b><progress aria-label={`${slot.fitting.name} assigned`} max={slot.target_count} value={count}/></div>; })}
            <p className="muted">Targets are planning guides; extra assignments are allowed.</p><div className="fa-privacy"><ShieldCheck size={17}/><span>{operation.status === "published" ? "Members see only their own assigned fits." : "This fleet is hidden from member views."}</span></div>
          </aside>
        </div>
      </> : <div className="panel fa-empty"><ClipboardList size={32}/><h3>Start with a fleet</h3><p>Create an empty operation or load a preset to build your composition.</p></div>}
    </> : null}
  </section>;
}

function FitText({ fitting, onCopy }: { fitting: FleetSlot["fitting"]; onCopy: (text: string) => Promise<void> }) {
  return <details className="fa-fit-text"><summary>View fitting / copy EFT</summary><button onClick={() => void onCopy(fitting.eft)}><Copy size={14}/> Copy fitting</button><pre tabIndex={0}>{fitting.eft}</pre><small className="muted">Saved {new Date(fitting.captured_at).toLocaleString()}</small></details>;
}
function SlotCard({ slot, count, active, disabled, onSelect, onSave, onRemove, onCopy, onHover, onAssign }: { slot: FleetSlot; count: number; active: boolean; disabled: boolean; onSelect: () => void; onSave: (role: string, count: number) => void; onRemove: () => void; onCopy: (text: string) => Promise<void>; onHover: (pilotId: number | null) => void; onAssign: (pilotId: number) => void }) {
  const [role, setRole] = useState(slot.role); const [target, setTarget] = useState(slot.target_count);
  useEffect(() => { setRole(slot.role); setTarget(slot.target_count); }, [slot.role, slot.target_count]);
  return <article className={`fa-fit-card ${active ? "fa-selected" : ""}`} >
    <FittingDragHandle slot={slot} active={active} disabled={disabled} onSelect={onSelect} onHover={onHover} onAssign={onAssign}/>
    <span className="fa-badge">{count}/{slot.target_count} assigned</span><FitText fitting={slot.fitting} onCopy={onCopy}/><details><summary>Edit role / target</summary><label>Role<input maxLength={120} value={role} disabled={disabled} onChange={(event) => setRole(event.target.value)}/></label><label>Target count<input type="number" min={1} max={500} value={target} disabled={disabled} onChange={(event) => setTarget(Number(event.target.value))}/></label><div className="button-row"><button disabled={disabled || target < 1 || target > 500} onClick={() => onSave(role, target)}>Save role</button><button className="danger" disabled={disabled || count > 0} onClick={onRemove}>Remove fit</button></div></details>
  </article>;
}
function PilotRow({ pilot, selected, dragOver, disabled, onToggle, onRemove }: { pilot: FleetPilot; selected: boolean; dragOver: boolean; disabled: boolean; onToggle: () => void; onRemove: () => void }) {
  return <article data-fleet-pilot={pilot.resolved && !disabled ? pilot.id : undefined} className={`fa-pilot ${selected ? "fa-selected" : ""} ${dragOver ? "fa-drag-over" : ""} ${!pilot.resolved ? "fa-unresolved" : ""}`}
    >
    <label className="fa-pilot-label"><input type="checkbox" aria-label={`Select ${pilot.name}`} checked={selected} disabled={disabled || !pilot.resolved} onChange={onToggle}/><span><strong>{pilot.name}</strong><small>{!pilot.resolved ? "Name unresolved — correct and paste again" : pilot.fitting ? `${pilot.fitting.name} · ${pilot.fitting.ship_name}` : "Unassigned · drop a fitting here"}</small></span></label><button className="fa-remove" aria-label={`Remove ${pilot.name}`} disabled={disabled} onClick={onRemove}>×</button>
  </article>;
}


// Pointer capture avoids browser-specific HTML drag behavior and supports touch.
// The keyboard/click assignment controls remain available beside the roster.
function FittingDragHandle({ slot, active, disabled, onSelect, onHover, onAssign }: {
  slot: FleetSlot; active: boolean; disabled: boolean; onSelect: () => void;
  onHover: (pilotId: number | null) => void; onAssign: (pilotId: number) => void;
}) {
  const origin = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const ignoreClick = useRef(false);
  const [dragging, setDragging] = useState(false);
  function hit(x: number, y: number) {
    const row = document.elementFromPoint(x, y)?.closest<HTMLElement>("[data-fleet-pilot]");
    return row?.dataset.fleetPilot ? Number(row.dataset.fleetPilot) : null;
  }
  function reset() { origin.current = null; setDragging(false); onHover(null); }
  return <button className={`fa-fit-select ${dragging ? "fa-dragging" : ""}`} disabled={disabled}
    aria-pressed={active} aria-label={`Select or drag ${slot.fitting.name}`} draggable={false}
    onDragStart={(event) => event.preventDefault()}
    onPointerDown={(event) => {
      if (event.button !== 0 || disabled) return;
      origin.current = { x: event.clientX, y: event.clientY, moved: false };
      ignoreClick.current = false; event.currentTarget.setPointerCapture(event.pointerId);
    }}
    onPointerMove={(event) => {
      const start = origin.current; if (!start) return;
      if (Math.hypot(event.clientX - start.x, event.clientY - start.y) > 7) {
        start.moved = true; setDragging(true); onHover(hit(event.clientX, event.clientY));
        if (event.clientY < 55) window.scrollBy(0, -18);
        else if (event.clientY > window.innerHeight - 55) window.scrollBy(0, 18);
      }
    }}
    onPointerUp={(event) => {
      const moved = origin.current?.moved;
      const pilotId = moved ? hit(event.clientX, event.clientY) : null;
      reset(); ignoreClick.current = !!moved;
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      if (pilotId !== null && !disabled) onAssign(pilotId);
    }}
    onPointerCancel={reset}
    onClick={() => { if (ignoreClick.current) { ignoreClick.current = false; return; } onSelect(); }}>
      <GripVertical size={18}/><span><strong>{slot.fitting.name}</strong><small>{dragging ? "Drop onto a pilot to assign" : `${slot.fitting.ship_name}${slot.role ? ` · ${slot.role}` : ""}`}</small></span>{active && <Check size={16}/>}</button>;
}
