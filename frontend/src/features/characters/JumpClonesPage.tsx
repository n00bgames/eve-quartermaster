import { useEffect, useMemo, useState, type ReactElement } from "react";
import { Copy } from "lucide-react";

import { ImplantDogmaChip } from "./ImplantDogmaChip";
import { buildImplantShoppingList } from "./implantShoppingList";
import type { ImplantSetRecord, JumpCloneImplant, JumpClonePayload, JumpCloneRecord, JumpCloneSyncToken } from "../../types/jumpClones";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type EveEntityKind = "character" | "corporation" | "alliance";
type EveIconSize = "tiny" | "sm" | "md" | "lg";
type EveEntityIconComponent = (props: { kind: EveEntityKind; id?: number | null; name?: string | null; size?: EveIconSize }) => ReactElement;

type JumpClonesPageProps = {
  api: ApiClient;
  EveEntityIcon: EveEntityIconComponent;
  formatDateTime: (value?: string | null) => string;
};

function implantSummary(implants: { name: string; slot?: number | null }[]): string {
  if (implants.length === 0) return "No implants recorded";
  return implants.map((implant) => `${implant.slot ? `Slot ${implant.slot}: ` : ""}${implant.name}`).join(", ");
}

function typeIdText(set: ImplantSetRecord): string {
  return set.implants.map((implant) => implant.type_id).join("\n");
}

function parseTypeIds(text: string): number[] {
  return Array.from(new Set(text.split(/[\s,;]+/).map((value) => Number(value.trim())).filter((value) => Number.isInteger(value) && value > 0))).slice(0, 20);
}

function cloneLocationText(clone: JumpCloneRecord): string {
  if (clone.clone_kind === "active_clone") return "Active clone";
  if (clone.location_name && clone.system_name && clone.location_name !== clone.system_name) return `${clone.location_name} · ${clone.system_name}`;
  if (clone.location_name) return clone.location_name;
  if (clone.location_id) return `${clone.location_type ?? "Location"} ${clone.location_id}`;
  return "Jump clone";
}


function CloneCard({ clone, formatDateTime, onCopy }: { clone: JumpCloneRecord; formatDateTime: (value?: string | null) => string; onCopy: (label: string, implants: JumpCloneImplant[]) => void }) {
  return (
    <article className="jump-clone-card">
      <div className="jump-clone-card-heading">
        <strong>{clone.name}</strong>
        <span>{cloneLocationText(clone)}</span>
        {clone.location_id && clone.location_name && <small>ID {clone.location_id}</small>}
        {clone.last_synced_at && <small>Synced {formatDateTime(clone.last_synced_at)}</small>}
      </div>
      <div className="implant-chip-list">
        {clone.implants.map((implant) => <ImplantDogmaChip key={`${clone.id}-${implant.type_id}`} implant={implant} />)}
        {clone.implants.length === 0 && <span className="implant-empty">No implants</span>}
      </div>
      <div className="button-row compact">
        <button type="button" disabled={clone.implants.length === 0} onClick={() => onCopy(clone.name, clone.implants)} title="Copy an item-and-quantity list for market appraisal or multibuy">
          <Copy size={15} /> Copy shopping list
        </button>
      </div>
    </article>
  );
}

export function JumpClonesPage({ api, EveEntityIcon, formatDateTime }: JumpClonesPageProps) {
  const [payload, setPayload] = useState<JumpClonePayload>({ characters: [], clones: [], custom_sets: [], sync_tokens: [] });
  const [selectedCharacterId, setSelectedCharacterId] = useState<number | "">("");
  const [setName, setSetName] = useState("");
  const [setDescription, setSetDescription] = useState("");
  const [setTypeIds, setSetTypeIds] = useState("");
  const [setShared, setSetShared] = useState(false);
  const [editingSetId, setEditingSetId] = useState<number | null>(null);
  const [busyTokenId, setBusyTokenId] = useState<number | null>(null);
  const [savingSet, setSavingSet] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const next = await api<JumpClonePayload>("/jump-clones");
    setPayload(next);
    setSelectedCharacterId((current) => current === "" ? next.characters[0]?.id ?? "" : current);
  }

  async function syncToken(token: JumpCloneSyncToken) {
    setBusyTokenId(token.token_id);
    setError(null);
    setMessage(`Syncing clones and implants for ${token.character_name}...`);
    try {
      const result = await api<{ character_name: string; implant_count: number }>(`/jump-clones/sync/${token.token_id}`, { method: "POST", body: "{}" });
      setMessage(`Synced ${result.character_name}: ${result.implant_count.toLocaleString()} distinct implant type${result.implant_count === 1 ? "" : "s"} recorded.`);
      await load();
    } catch (err) {
      setMessage(null);
      setError(err instanceof Error ? err.message : "Jump clone sync failed");
    } finally {
      setBusyTokenId(null);
    }
  }

  function beginEdit(set: ImplantSetRecord) {
    setEditingSetId(set.id);
    setSetName(set.name);
    setSetDescription(set.description ?? "");
    setSetTypeIds(typeIdText(set));
    setSetShared(set.is_shared);
    setSelectedCharacterId(set.character_id ?? "");
  }

  function resetForm() {
    setEditingSetId(null);
    setSetName("");
    setSetDescription("");
    setSetTypeIds("");
    setSetShared(false);
  }

  async function saveSet() {
    const implantTypeIds = parseTypeIds(setTypeIds);
    if (!setName.trim()) {
      setError("Name the implant set before saving it.");
      return;
    }
    setSavingSet(true);
    setError(null);
    try {
      const body = JSON.stringify({
        name: setName,
        description: setDescription,
        character_id: selectedCharacterId || null,
        implant_type_ids: implantTypeIds,
        is_shared: setShared,
      });
      if (editingSetId) {
        await api<ImplantSetRecord>(`/jump-clones/sets/${editingSetId}`, { method: "PATCH", body });
        setMessage(`${setName} updated.`);
      } else {
        await api<ImplantSetRecord>("/jump-clones/sets", { method: "POST", body });
        setMessage(`${setName} created.`);
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save implant set");
    } finally {
      setSavingSet(false);
    }
  }

  async function deleteSet(set: ImplantSetRecord) {
    if (!window.confirm(`Delete implant set ${set.name}?`)) return;
    setError(null);
    try {
      await api(`/jump-clones/sets/${set.id}`, { method: "DELETE" });
      setMessage(`${set.name} deleted.`);
      if (editingSetId === set.id) resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete implant set");
    }
  }

  async function copyImplants(label: string, implants: JumpCloneImplant[]) {
    const list = buildImplantShoppingList(implants);
    if (!list.text) {
      setMessage(null);
      setError(`${label} has no implants to copy.`);
      return;
    }
    try {
      await navigator.clipboard.writeText(list.text);
      setError(null);
      setMessage(`Copied ${list.implantCount.toLocaleString()} implant${list.implantCount === 1 ? "" : "s"} across ${list.itemTypeCount.toLocaleString()} item type${list.itemTypeCount === 1 ? "" : "s"} from ${label}.`);
    } catch {
      setMessage(null);
      setError("The browser blocked clipboard access. Check its clipboard permission and try again.");
    }
  }

  useEffect(() => { void load().catch((err) => setError(err instanceof Error ? err.message : "Unable to load jump clones")); }, []);

  const clonesByCharacter = useMemo(() => {
    const rows = new Map<number, JumpCloneRecord[]>();
    for (const clone of payload.clones) rows.set(clone.character_id, [...(rows.get(clone.character_id) ?? []), clone]);
    return rows;
  }, [payload.clones]);

  const selectedCharacter = payload.characters.find((character) => character.id === selectedCharacterId) ?? null;
  const selectedClones = selectedCharacterId === "" ? [] : clonesByCharacter.get(selectedCharacterId) ?? [];
  const selectedImplants = selectedClones.flatMap((clone) => clone.implants);

  return (
    <section className="panel stacked jump-clones-page">
      <div className="section-heading">
        <div>
          <h3>Jump Clones</h3>
          <p>Sync clone implants from ESI and build custom implant sets for fitting experiments.</p>
        </div>
        <div className="button-row compact"><button type="button" onClick={() => void load()}>Refresh</button></div>
      </div>
      {message && <div className="notice inline">{message}</div>}
      {error && <div className="mini-alert">{error}</div>}

      <section className="character-sync-grid">
        {payload.sync_tokens.map((token) => (
          <article key={token.token_id}>
            <strong>{token.character_name}</strong>
            {token.can_sync ? <span className="scope-ok">Sync permitted</span> : <span className="scope-warn">Sync hidden by role policy</span>}
            {token.missing_scopes.length > 0 && <small>Missing scopes: {token.missing_scopes.join(", ")}</small>}
            <button type="button" disabled={!token.can_sync || !token.has_clone_scope || !token.has_implant_scope || busyTokenId !== null} onClick={() => void syncToken(token)}>
              {busyTokenId === token.token_id ? "Syncing..." : "Sync clones and implants"}
            </button>
          </article>
        ))}
        {payload.sync_tokens.length === 0 && <p className="empty">No linked clone-capable tokens are visible to this account.</p>}
      </section>

      <div className="two-column jump-clone-layout">
        <aside className="character-picker-list">
          {payload.characters.map((character) => (
            <button type="button" key={character.id} className={`character-picker-card ${selectedCharacterId === character.id ? "active" : ""}`} onClick={() => setSelectedCharacterId(character.id)}>
              <span className="entity-card-heading">
                <EveEntityIcon kind="character" id={character.character_id} name={character.name} size="sm" />
                <span className="jump-clone-character-text"><strong>{character.name}</strong><small>{character.owner_display_name ?? "Unassigned"}</small></span>
              </span>
              <small>{clonesByCharacter.get(character.id)?.length ?? 0} clone record{(clonesByCharacter.get(character.id)?.length ?? 0) === 1 ? "" : "s"}</small>
            </button>
          ))}
        </aside>
        <section className="jump-clone-detail">
          <div className="section-heading compact">
            <h4>{selectedCharacter ? selectedCharacter.name : "Select a character"}</h4>
            <button type="button" disabled={!selectedCharacter || selectedImplants.length === 0} onClick={() => void copyImplants(`${selectedCharacter?.name ?? "selected character"} clones`, selectedImplants)} title="Copy all implants from this character's active clone and jump clones">
              <Copy size={15} /> Copy all implants
            </button>
          </div>
          <div className="jump-clone-grid">
            {selectedClones.map((clone) => <CloneCard key={clone.id} clone={clone} formatDateTime={formatDateTime} onCopy={(label, implants) => void copyImplants(label, implants)} />)}
            {selectedCharacter && selectedClones.length === 0 && <p className="empty">No jump clone data synced for this character yet.</p>}
          </div>
        </section>
      </div>

      <section className="implant-set-workshop">
        <div className="section-heading compact">
          <div><h4>{editingSetId ? "Edit Implant Set" : "Custom Implant Set"}</h4><p>Paste implant type IDs to build an experimental set for fittings.</p></div>
          {editingSetId && <button type="button" onClick={resetForm}>New set</button>}
        </div>
        <div className="fitting-editor-controls implant-set-form">
          <label>Name<input value={setName} onChange={(event) => setSetName(event.target.value)} placeholder="Ascendancy haul set, Asklepian active tank..." /></label>
          <label>Character<select value={selectedCharacterId} onChange={(event) => setSelectedCharacterId(event.target.value ? Number(event.target.value) : "")}><option value="">No character lock</option>{payload.characters.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}</select></label>
          <label className="check"><input type="checkbox" checked={setShared} onChange={(event) => setSetShared(event.target.checked)} /> Shared</label>
          <label className="wide">Implant type IDs<textarea value={setTypeIds} onChange={(event) => setSetTypeIds(event.target.value)} placeholder={"10208\n10212\n10216"} /></label>
          <label className="wide">Notes<textarea value={setDescription} onChange={(event) => setSetDescription(event.target.value)} placeholder="Experiment notes" /></label>
          <button type="button" disabled={savingSet} onClick={() => void saveSet()}>{savingSet ? "Saving..." : editingSetId ? "Update set" : "Create set"}</button>
        </div>
        <div className="card-list implant-set-list">
          {payload.custom_sets.map((set) => (
            <article key={set.id}>
              <div className="section-heading compact">
                <div><strong>{set.name}</strong><span>{set.implants.length.toLocaleString()} implant{set.implants.length === 1 ? "" : "s"}{set.character_name ? ` · ${set.character_name}` : ""}{set.is_shared ? " · Shared" : ""}</span></div>
                <div className="button-row compact"><button type="button" disabled={set.implants.length === 0} onClick={() => void copyImplants(set.name, set.implants)} title="Copy an item-and-quantity list for market appraisal or multibuy"><Copy size={15} /> Copy shopping list</button>{set.can_manage && <button type="button" onClick={() => beginEdit(set)}>Edit</button>}{set.can_manage && <button type="button" className="danger-button" onClick={() => void deleteSet(set)}>Delete</button>}</div>
              </div>
              <span>{implantSummary(set.implants)}</span>
              {set.description && <small>{set.description}</small>}
            </article>
          ))}
          {payload.custom_sets.length === 0 && <p className="empty">No custom implant sets yet.</p>}
        </div>
      </section>
    </section>
  );
}
