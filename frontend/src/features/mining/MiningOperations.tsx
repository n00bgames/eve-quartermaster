import { Plus, Trash2, Users } from "lucide-react";
import { useState } from "react";

import type { MiningCharacter, MiningOperation } from "../../types/mining";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type ParticipantDraft = { selected: boolean; role: "miner" | "booster"; ship_name: string; crystal_name: string };

export function MiningOperations({ api, characters, systems, operations, onChanged }: {
  api: ApiClient;
  characters: MiningCharacter[];
  systems: [number, string][];
  operations: MiningOperation[];
  onChanged: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [participants, setParticipants] = useState<Record<number, ParticipantDraft>>({});

  function updateParticipant(characterId: number, patch: Partial<ParticipantDraft>) {
    setParticipants((current) => {
      const existing = current[characterId] ?? { selected: false, role: "miner", ship_name: "", crystal_name: "" };
      return { ...current, [characterId]: { ...existing, ...patch } };
    });
  }

  async function createOperation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const systemName = String(form.get("solar_system_name") || "").trim();
    const system = systems.find((row) => row[1].toLocaleLowerCase() === systemName.toLocaleLowerCase());
    const selected = characters.flatMap((character) => {
      const draft = participants[character.character_id];
      return draft?.selected ? [{ character_id: character.character_id, role: draft.role, ship_name: draft.ship_name, crystal_name: draft.crystal_name }] : [];
    });
    setBusy(true);
    setMessage(null);
    try {
      await api("/mining-ledger/operations", { method: "POST", body: JSON.stringify({
        name: form.get("name"), solar_system_id: system?.[0], solar_system_name: systemName,
        start_at: new Date(String(form.get("start_at"))).toISOString(), end_at: new Date(String(form.get("end_at"))).toISOString(),
        notes: form.get("notes"), participants: selected,
      }) });
      setMessage("Mining operation created and matching historical rows attached.");
      setParticipants({});
      formElement.reset();
      setOpen(false);
      await onChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to create mining operation");
    } finally {
      setBusy(false);
    }
  }

  async function removeOperation(operation: MiningOperation) {
    if (!window.confirm(`Delete ${operation.name}? Ledger history will remain.`)) return;
    setBusy(true);
    try {
      await api(`/mining-ledger/operations/${operation.id}`, { method: "DELETE" });
      await onChanged();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to delete mining operation");
    } finally {
      setBusy(false);
    }
  }

  return <section className="mining-operations">
    <div className="section-heading"><div><h4>Mining operations</h4><p>Group a system, selected characters, and a time window into a named operation.</p></div><button type="button" onClick={() => setOpen((value) => !value)}><Plus size={16} />{open ? "Close builder" : "New operation"}</button></div>
    {message && <div className="notice inline">{message}</div>}
    {open && <form className="mining-operation-form" onSubmit={(event) => void createOperation(event)}>
      <div className="form-grid mining-operation-basics">
        <label>Operation name<input name="name" required placeholder="Hahda Raven Replenishment Op" /></label>
        <label>Solar system<input name="solar_system_name" list="mining-system-options" required placeholder="Hahda" /></label>
        <label>Start<input name="start_at" type="datetime-local" required /></label>
        <label>End<input name="end_at" type="datetime-local" required /></label>
      </div>
      <datalist id="mining-system-options">{systems.map(([id, name]) => <option key={id} value={name} />)}</datalist>
      <label>Notes<textarea name="notes" rows={2} placeholder="Fleet, payout, belt, or objective notes" /></label>
      <div className="mining-participant-list">
        <strong><Users size={16} /> Participants</strong>
        {characters.filter((character) => !character.sync_opt_out).map((character) => {
          const draft = participants[character.character_id] ?? { selected: false, role: "miner", ship_name: "", crystal_name: "" };
          return <div className={draft.selected ? "mining-participant active" : "mining-participant"} key={character.character_id}>
            <label className="check-row"><input type="checkbox" checked={draft.selected} onChange={(event) => updateParticipant(character.character_id, { selected: event.target.checked })} />{character.name}</label>
            <select disabled={!draft.selected} value={draft.role} onChange={(event) => updateParticipant(character.character_id, { role: event.target.value as "miner" | "booster" })}><option value="miner">Miner</option><option value="booster">Booster</option></select>
            <input disabled={!draft.selected} value={draft.ship_name} onChange={(event) => updateParticipant(character.character_id, { ship_name: event.target.value })} placeholder="Ship (optional)" />
            <input disabled={!draft.selected} value={draft.crystal_name} onChange={(event) => updateParticipant(character.character_id, { crystal_name: event.target.value })} placeholder="Crystal (optional)" />
          </div>;
        })}
      </div>
      <div className="button-row compact"><button type="submit" disabled={busy}>{busy ? "Creating" : "Create operation"}</button></div>
    </form>}
    <div className="mining-operation-cards">
      {operations.map((operation) => <article key={operation.id}>
        <header><div><h5>{operation.name}</h5><span>{operation.solar_system_name} · {new Date(operation.start_at).toLocaleString()} to {new Date(operation.end_at).toLocaleString()}</span></div><button type="button" className="icon-button danger" title="Delete operation" disabled={busy} onClick={() => void removeOperation(operation)}><Trash2 size={16} /></button></header>
        <div className="mining-operation-stats"><strong>{operation.summary.volume.toLocaleString()} m3 recovered</strong><span>{operation.summary.residue_volume.toLocaleString()} m3 residue</span><span>{operation.summary.estimated_price.toLocaleString()} ISK net value</span><span>{operation.summary.efficiency == null ? "Efficiency not measured" : `${operation.summary.efficiency}% efficient`}</span></div>
        <p>{operation.participants.filter((row) => row.role === "miner").length} miners · {operation.participants.filter((row) => row.role === "booster").length} boosters · added by {operation.created_by}</p>
        <div className="participant-chips">{operation.participants.map((row) => <span key={row.character_id}>{row.character_name} · {row.role}{row.ship_name ? ` · ${row.ship_name}` : ""}{row.crystal_name ? ` · ${row.crystal_name}` : ""}</span>)}</div>
      </article>)}
      {operations.length === 0 && <p className="empty">No named mining operations yet.</p>}
    </div>
  </section>;
}
