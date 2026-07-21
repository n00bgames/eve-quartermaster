import { ArrowDown, ArrowUp, CheckCheck, ClipboardCopy, PackageSearch, Search, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { EveTypeCandidate, NoteAssetScope, NoteDetail, NoteItemStatus, NoteLocationResult, NoteSystemResult } from "../../types/notes";
import { NotesPricingPane } from "./NotesPricingPane";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

type Props = {
  api: ApiClient;
  note: NoteDetail;
  assetScope: NoteAssetScope;
  ownerIds: number[];
  onAssetScopeChange: (scope: NoteAssetScope, ownerIds: number[]) => void;
  onReload: () => Promise<void>;
  onPatchNote: (payload: Record<string, unknown>) => Promise<void>;
};

const statusOptions: { value: NoteItemStatus; label: string }[] = [
  { value: "needed", label: "Needed" },
  { value: "planned", label: "Planned" },
  { value: "purchased", label: "Purchased" },
  { value: "in_transit", label: "In transit" },
  { value: "delivered", label: "Delivered" },
  { value: "skipped", label: "Skipped" },
];

const number = new Intl.NumberFormat("en-US");

export function ItemListEditor({ api, note, assetScope, ownerIds, onAssetScopeChange, onReload, onPatchNote }: Props) {
  const [importText, setImportText] = useState("");
  const [mergeDuplicates, setMergeDuplicates] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [hideCompleted, setHideCompleted] = useState(false);
  const [sort, setSort] = useState<"manual" | "name" | "status" | "remaining">("manual");
  const [systemQuery, setSystemQuery] = useState(note.destination_system_name ?? "");
  const [systems, setSystems] = useState<NoteSystemResult[]>([]);
  const [locations, setLocations] = useState<NoteLocationResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setSystemQuery(note.destination_system_name ?? ""), [note.destination_system_name]);

  useEffect(() => {
    if (systemQuery.trim().length < 2 || systemQuery === note.destination_system_name) {
      setSystems([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void api<NoteSystemResult[]>("/notes/search/systems?q=" + encodeURIComponent(systemQuery.trim()))
        .then(setSystems)
        .catch(() => setSystems([]));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [api, note.destination_system_name, systemQuery]);

  useEffect(() => {
    if (!note.destination_system_id) {
      setLocations([]);
      return;
    }
    void api<NoteLocationResult[]>("/notes/search/locations?system_id=" + note.destination_system_id)
      .then(setLocations)
      .catch(() => setLocations([]));
  }, [api, note.destination_system_id]);

  const visibleItems = useMemo(() => {
    const needle = search.trim().toLowerCase();
    const rows = note.items.filter((item) => {
      if (hideCompleted && item.completed) return false;
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      return !needle || item.name.toLowerCase().includes(needle);
    });
    if (sort === "name") rows.sort((a, b) => a.name.localeCompare(b.name));
    if (sort === "status") rows.sort((a, b) => a.status.localeCompare(b.status));
    if (sort === "remaining") rows.sort((a, b) => b.asset_context.remaining - a.asset_context.remaining);
    return rows;
  }, [hideCompleted, note.items, search, sort, statusFilter]);

  async function request(path: string, method: string, payload?: unknown) {
    setBusy(true);
    setError(null);
    try {
      await api(path, { method, body: payload === undefined ? undefined : JSON.stringify(payload) });
      await onReload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The list could not be updated.");
      throw reason;
    } finally {
      setBusy(false);
    }
  }

  async function importRows() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api<{ duplicates: { name: string; quantity: number }[]; imported: unknown[] }>("/notes/" + note.id + "/items/parse", {
        method: "POST",
        body: JSON.stringify({ text: importText, merge_duplicates: mergeDuplicates }),
      });
      setImportText("");
      setMessage(result.duplicates.length ? "Imported " + result.imported.length + " rows. Duplicate names were " + (mergeDuplicates ? "merged by request." : "kept as separate rows.") : "Imported " + result.imported.length + " rows.");
      await onReload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Item import failed.");
    } finally {
      setBusy(false);
    }
  }

  async function chooseSystem(system: NoteSystemResult) {
    setSystemQuery(system.name);
    setSystems([]);
    await onPatchNote({ destination_system_id: system.system_id, destination_location_id: null });
  }

  async function chooseLocation(value: string) {
    if (!value) {
      await onPatchNote({ destination_location_id: null });
      return;
    }
    const location = locations.find((row) => String(row.id ?? "eve-" + row.eve_location_id) === value);
    if (!location) return;
    await onPatchNote(location.id ? { destination_location_id: location.id } : { destination_eve_location_id: location.eve_location_id });
  }

  async function patchItem(itemId: number, payload: Record<string, unknown>) {
    await request("/notes/" + note.id + "/items/" + itemId, "PATCH", payload);
  }

  async function bulkStatus(status: NoteItemStatus) {
    await request("/notes/" + note.id + "/items/bulk-status", "POST", { item_ids: [...selected], status });
    setSelected(new Set());
  }

  async function move(itemId: number, direction: -1 | 1) {
    const ids = [...note.items].sort((a, b) => a.sort_order - b.sort_order).map((item) => item.id);
    const index = ids.indexOf(itemId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    await request("/notes/" + note.id + "/items/reorder", "POST", { item_ids: ids });
  }

  async function copyShoppingList(copyAll = false) {
    const rows = [...note.items]
      .sort((a, b) => a.sort_order - b.sort_order)
      .filter((item) => copyAll || (!item.completed && item.asset_context.remaining > 0))
      .map((item) => `${item.name} ${copyAll ? item.requested_quantity : item.asset_context.remaining}`);
    if (!rows.length) {
      setMessage(copyAll ? "This shopping list has no items to copy." : "No remaining shopping-list items to copy.");
      setError(null);
      return;
    }
    try {
      await navigator.clipboard.writeText(rows.join("\n"));
      setMessage(`Copied ${rows.length} ${copyAll ? "full-list" : "remaining"} ${rows.length === 1 ? "item" : "items"}.`);
      setError(null);
    } catch {
      setError("The browser blocked clipboard access. Check its clipboard permission and try again.");
    }
  }

  const allVisibleSelected = visibleItems.length > 0 && visibleItems.every((item) => selected.has(item.id));

  return (
    <div className="notes-item-editor">
      <section className="notes-destination-grid">
        <label className="notes-system-search">
          Destination system
          <div className="input-with-icon"><Search size={15} /><input value={systemQuery} placeholder="Search imported SDE systems" onChange={(event) => setSystemQuery(event.target.value)} /></div>
          {systems.length > 0 && <div className="notes-search-results">{systems.map((system) => <button type="button" key={system.system_id} onClick={() => void chooseSystem(system)}><span>{system.name}</span><small>Security {system.security_status?.toFixed(1) ?? "?"}</small></button>)}</div>}
        </label>
        <label>
          Station or structure
          <select value={note.destination_location_id ? String(note.destination_location_id) : ""} disabled={!note.destination_system_id} onChange={(event) => void chooseLocation(event.target.value)}>
            <option value="">Whole solar system</option>
            {locations.map((location) => <option key={String(location.id ?? "eve-" + location.eve_location_id)} value={String(location.id ?? "eve-" + location.eve_location_id)}>{location.name}</option>)}
          </select>
        </label>
        <div className="notes-destination-readout">
          <span>Destination</span>
          <strong>{note.destination_location_name ?? note.destination_system_name ?? "Not selected"}</strong>
          {typeof note.destination_security_status === "number" && <small>Security {note.destination_security_status.toFixed(1)}</small>}
        </div>
      </section>

      <section className="notes-import-panel">
        <header><div><h4>Add item lines</h4><p>One item per line. Quantity may come before the name or after it with x.</p></div></header>
        <textarea value={importText} onChange={(event) => setImportText(event.target.value)} placeholder={"Tritanium x5000\n2000 Pyerite\nDamage Control II"} />
        <div className="button-row">
          <label className="inline-check"><input type="checkbox" checked={mergeDuplicates} onChange={(event) => setMergeDuplicates(event.target.checked)} /> Merge duplicate item names</label>
          <button type="button" disabled={busy || !importText.trim()} onClick={() => void importRows()}><PackageSearch size={16} /> Import rows</button>
        </div>
      </section>

      <section className="notes-asset-scope">
        <header className="section-heading"><div><h4>Asset cross-reference</h4><p>Visible synced assets only. Scope and freshness are explicit.</p></div></header>
        <div className="notes-scope-controls">
          <label>Scope<select value={assetScope} onChange={(event) => onAssetScopeChange(event.target.value as NoteAssetScope, [])}><option value="all">All visible assets</option><option value="character">Characters</option><option value="corporation">Corporations</option></select></label>
          <fieldset><legend>Owners</legend><div className="notes-owner-options">{note.asset_scope.owners.filter((owner) => assetScope === "all" || owner.kind === assetScope).map((owner) => <label key={owner.id}><input type="checkbox" checked={ownerIds.includes(owner.id)} onChange={(event) => onAssetScopeChange(assetScope, event.target.checked ? [...ownerIds, owner.id] : ownerIds.filter((id) => id !== owner.id))} />{owner.name}</label>)}</div></fieldset>
          <div className={"notes-freshness " + (note.asset_scope.freshness.stale ? "stale" : "fresh")}>
            <strong>{note.asset_scope.freshness.available ? (note.asset_scope.freshness.stale ? "Asset data may be stale" : "Asset data current") : "Asset data unavailable"}</strong>
            <span>{note.asset_scope.freshness.latest_synced_at ? "Latest sync " + new Date(note.asset_scope.freshness.latest_synced_at).toLocaleString() : "No sync timestamp"}</span>
            <small>{number.format(note.asset_scope.freshness.asset_stacks)} visible stacks · {note.asset_scope.freshness.scope_kinds.join(", ") || "no owner scope"}</small>
          </div>
        </div>
      </section>

      <section className="notes-list-tools">
        <div className="input-with-icon"><Search size={15} /><input value={search} placeholder="Search this list" onChange={(event) => setSearch(event.target.value)} /></div>
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option>{statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
        <select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="manual">Manual order</option><option value="name">Name</option><option value="status">Status</option><option value="remaining">Remaining need</option></select>
        <label className="inline-check"><input type="checkbox" checked={hideCompleted} onChange={(event) => setHideCompleted(event.target.checked)} /> Hide completed</label>
      </section>

      {message && <div className="notice compact">{message}</div>}
      {error && <div className="mini-alert">{error}</div>}

      <div className="notes-bulk-bar">
        <label className="inline-check"><input type="checkbox" checked={allVisibleSelected} onChange={(event) => setSelected(event.target.checked ? new Set(visibleItems.map((item) => item.id)) : new Set())} /> Select visible</label>
        <span>{selected.size} selected</span>
        <select disabled={!selected.size || busy} defaultValue="" onChange={(event) => { if (event.target.value) void bulkStatus(event.target.value as NoteItemStatus); event.currentTarget.value = ""; }}>
          <option value="">Set status...</option>{statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <button type="button" className="notes-copy-list" disabled={busy} onClick={() => void copyShoppingList()}><ClipboardCopy size={15} /> Copy remaining</button>
        <button type="button" className="notes-copy-list" disabled={busy} onClick={() => void copyShoppingList(true)}><ClipboardCopy size={15} /> Copy all items</button>
        <button type="button" className="danger" disabled={busy || note.summary.completed_items === 0} onClick={() => window.confirm("Remove all delivered and skipped rows?") && void request("/notes/" + note.id + "/items/completed", "DELETE")}><Trash2 size={15} /> Clear completed</button>
      </div>

      <div className="table-wrap notes-items-table">
        <table>
          <thead><tr><th aria-label="Select"></th><th>Item</th><th>Requested</th><th>At destination</th><th>Elsewhere</th><th>Remaining</th><th>Status</th><th aria-label="Actions"></th></tr></thead>
          <tbody>
            {visibleItems.map((item) => (
              <tr key={item.id} className={item.completed ? "completed" : ""}>
                <td><input type="checkbox" checked={selected.has(item.id)} onChange={(event) => setSelected((current) => { const next = new Set(current); event.target.checked ? next.add(item.id) : next.delete(item.id); return next; })} /></td>
                <td>
                  <div className="notes-item-name">
                    {item.type_id ? <img src={"https://images.evetech.net/types/" + item.type_id + "/icon?size=64"} alt="" /> : <span className="notes-unresolved-icon">?</span>}
                    <span><strong>{item.name}</strong><small>{item.group_name ?? (item.type_id ? "SDE item" : "Unresolved item")}</small></span>
                  </div>
                  {!item.type_id && <label className="notes-resolve-select">Resolve<select defaultValue="" onChange={(event) => event.target.value && void patchItem(item.id, { type_id: Number(event.target.value) })}><option value="">Choose SDE match...</option>{item.candidates.map((candidate: EveTypeCandidate) => <option key={candidate.type_id} value={candidate.type_id}>{candidate.name} · {candidate.group_name ?? "Unknown group"}</option>)}</select></label>}
                  {item.asset_context.locations.length > 0 && <details><summary>Asset locations</summary><div className="notes-location-list">{item.asset_context.locations.map((row, index) => <span key={row.owner_name + row.location_name + index}><b>{number.format(row.quantity)}</b> {row.owner_name} · {row.location_name}{row.at_destination ? " · destination" : ""}</span>)}</div></details>}
                </td>
                <td><input className="notes-quantity-input" type="number" min={1} defaultValue={item.requested_quantity} onBlur={(event) => Number(event.target.value) !== item.requested_quantity && void patchItem(item.id, { requested_quantity: Number(event.target.value) })} /></td>
                <td>{number.format(item.asset_context.at_destination)}</td>
                <td>{number.format(item.asset_context.elsewhere)}</td>
                <td className={item.asset_context.remaining ? "notes-remaining" : "notes-covered"}>{number.format(item.asset_context.remaining)}</td>
                <td><select value={item.status} onChange={(event) => void patchItem(item.id, { status: event.target.value })}>{statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></td>
                <td><div className="notes-row-actions">
                  {!item.completed && <button type="button" className="icon-button success" title="Mark delivered" onClick={() => void patchItem(item.id, { status: "delivered" })}><CheckCheck size={15} /></button>}
                  {sort === "manual" && <><button type="button" className="icon-button" title="Move up" onClick={() => void move(item.id, -1)}><ArrowUp size={15} /></button><button type="button" className="icon-button" title="Move down" onClick={() => void move(item.id, 1)}><ArrowDown size={15} /></button></>}
                  <button type="button" className="icon-button danger" title="Remove item" onClick={() => void request("/notes/" + note.id + "/items/" + item.id, "DELETE")}><X size={15} /></button>
                </div></td>
              </tr>
            ))}
            {!visibleItems.length && <tr><td colSpan={8} className="empty">No item rows match these filters.</td></tr>}
          </tbody>
        </table>
      </div>

      <NotesPricingPane api={api} noteId={note.id} selectedItemIds={[...selected]} assetScope={assetScope} ownerIds={ownerIds} sourceHubKey={note.source_market_hub_key} />
    </div>
  );
}