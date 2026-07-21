import { Copy, FileText, ListChecks, Plus, RefreshCw, RotateCcw, Save, Search, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { MarketHub, NoteAssetScope, NoteDetail, NoteKind, NoteListRow } from "../../types/notes";
import { ItemListEditor } from "./ItemListEditor";
import "./notes.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

type Props = {
  api: ApiClient;
};

type Draft = {
  title: string;
  body: string;
  tags: string;
  source_market_hub_key: string;
};

function toDraft(note: NoteDetail): Draft {
  return {
    title: note.title,
    body: note.body ?? "",
    tags: note.tags.join(", "),
    source_market_hub_key: note.source_market_hub_key ?? "",
  };
}

export function NotesListsPage({ api }: Props) {
  const [notes, setNotes] = useState<NoteListRow[]>([]);
  const [selected, setSelected] = useState<NoteDetail | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [assetScope, setAssetScope] = useState<NoteAssetScope>("all");
  const [ownerIds, setOwnerIds] = useState<number[]>([]);
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"all" | NoteKind>("all");
  const [tag, setTag] = useState("");
  const [sortNotes, setSortNotes] = useState<"updated" | "created">("updated");
  const [hubs, setHubs] = useState<MarketHub[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastDeleted, setLastDeleted] = useState<{ id: number; title: string } | null>(null);

  const loadNotes = useCallback(async (preferredId?: number) => {
    const rows = await api<NoteListRow[]>("/notes");
    setNotes(rows);
    const requestedId = preferredId ?? selected?.id;
    const targetId = requestedId && rows.some((row) => row.id === requestedId) ? requestedId : rows[0]?.id;
    if (targetId && rows.some((row) => row.id === targetId)) {
      const query = new URLSearchParams({ asset_scope: assetScope });
      if (ownerIds.length) query.set("owner_ids", ownerIds.join(","));
      const detail = await api<NoteDetail>("/notes/" + targetId + "?" + query.toString());
      setSelected(detail);
      setDraft(toDraft(detail));
    } else {
      setSelected(null);
      setDraft(null);
    }
  }, [api, assetScope, ownerIds, selected?.id]);

  const loadDetail = useCallback(async (noteId = selected?.id, scope = assetScope, owners = ownerIds) => {
    if (!noteId) return;
    const query = new URLSearchParams({ asset_scope: scope });
    if (owners.length) query.set("owner_ids", owners.join(","));
    const detail = await api<NoteDetail>("/notes/" + noteId + "?" + query.toString());
    setSelected(detail);
    setDraft((current) => current && selected?.id === detail.id ? current : toDraft(detail));
  }, [api, assetScope, ownerIds, selected?.id]);

  useEffect(() => {
    setBusy(true);
    Promise.all([loadNotes(), api<MarketHub[]>("/notes/market-hubs").then(setHubs)])
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Notes could not be loaded."))
      .finally(() => setBusy(false));
  }, []);

  const visibleNotes = useMemo(() => notes.filter((note) => {
    if (kind !== "all" && note.note_type !== kind) return false;
    if (tag && !note.tags.some((value) => value.toLowerCase().includes(tag.toLowerCase()))) return false;
    const needle = search.trim().toLowerCase();
    return !needle || note.title.toLowerCase().includes(needle) || (note.body ?? "").toLowerCase().includes(needle) || note.item_names.some((name) => name.toLowerCase().includes(needle));
  }).sort((a, b) => {
    const left = new Date(sortNotes === "created" ? a.created_at ?? 0 : a.updated_at ?? 0).getTime();
    const right = new Date(sortNotes === "created" ? b.created_at ?? 0 : b.updated_at ?? 0).getTime();
    return right - left;
  }), [kind, notes, search, sortNotes, tag]);

  async function create(kindToCreate: NoteKind) {
    setBusy(true);
    setError(null);
    try {
      const detail = await api<NoteDetail>("/notes", {
        method: "POST",
        body: JSON.stringify({ note_type: kindToCreate, title: kindToCreate === "freeform" ? "Untitled note" : "Untitled resupply list" }),
      });
      setAssetScope("all");
      setOwnerIds([]);
      await loadNotes(detail.id);
      setNotice(kindToCreate === "freeform" ? "New note created." : "New item list created.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Note could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function selectNote(noteId: number) {
    setBusy(true);
    setError(null);
    try {
      setAssetScope("all");
      setOwnerIds([]);
      const detail = await api<NoteDetail>("/notes/" + noteId);
      setSelected(detail);
      setDraft(toDraft(detail));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Note could not be opened.");
    } finally {
      setBusy(false);
    }
  }

  async function patchNote(payload: Record<string, unknown>) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await api("/notes/" + selected.id, { method: "PATCH", body: JSON.stringify(payload) });
      await loadDetail();
      const rows = await api<NoteListRow[]>("/notes");
      setNotes(rows);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Note could not be saved.");
      throw reason;
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!draft) return;
    await patchNote({
      title: draft.title,
      body: draft.body,
      tags: draft.tags,
      source_market_hub_key: draft.source_market_hub_key || null,
    });
    setNotice("Note saved.");
  }

  async function duplicate() {
    if (!selected) return;
    setBusy(true);
    try {
      const copy = await api<NoteDetail>("/notes/" + selected.id + "/duplicate", { method: "POST" });
      await loadNotes(copy.id);
      setNotice("A private copy was created.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Note could not be duplicated.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!selected || !window.confirm("Move this note to the deleted list?")) return;
    const removed = { id: selected.id, title: selected.title };
    setBusy(true);
    try {
      await api("/notes/" + selected.id, { method: "DELETE" });
      setLastDeleted(removed);
      setNotice(removed.title + " was deleted. Undo is available until you leave this page.");
      await loadNotes();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Note could not be deleted.");
    } finally {
      setBusy(false);
    }
  }

  async function undoDelete() {
    if (!lastDeleted) return;
    setBusy(true);
    try {
      await api("/notes/" + lastDeleted.id + "/restore", { method: "POST" });
      const restoredId = lastDeleted.id;
      setLastDeleted(null);
      await loadNotes(restoredId);
      setNotice("Deleted note restored.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Note could not be restored.");
    } finally {
      setBusy(false);
    }
  }

  function changeAssetScope(scope: NoteAssetScope, owners: number[]) {
    setAssetScope(scope);
    setOwnerIds(owners);
    void loadDetail(selected?.id, scope, owners).catch((reason) => setError(reason instanceof Error ? reason.message : "Asset scope could not be loaded."));
  }

  return (
    <section className="notes-page panel">
      <header className="section-heading notes-page-heading">
        <div>
          <h3>Notes & Lists</h3>
          <p>Private working notes and destination-aware resupply lists.</p>
        </div>
        <div className="button-row">
          <button type="button" onClick={() => void create("freeform")}><FileText size={16} /> New note</button>
          <button type="button" onClick={() => void create("item_list")}><ListChecks size={16} /> New item list</button>
          <button type="button" disabled={busy} onClick={() => void loadNotes()}><RefreshCw size={16} /> Refresh</button>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}
      {notice && <div className="notice compact"><span>{notice}</span>{lastDeleted && <button type="button" onClick={() => void undoDelete()}><RotateCcw size={15} /> Undo</button>}</div>}

      <div className="notes-layout">
        <aside className="notes-browser">
          <div className="input-with-icon"><Search size={15} /><input value={search} placeholder="Search notes" onChange={(event) => setSearch(event.target.value)} /></div>
          <div className="notes-browser-filters">
            <select value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}><option value="all">All types</option><option value="freeform">Notes</option><option value="item_list">Item lists</option></select>
            <select value={sortNotes} onChange={(event) => setSortNotes(event.target.value as typeof sortNotes)}><option value="updated">Recently updated</option><option value="created">Recently created</option></select>
            <input value={tag} placeholder="Filter tag" onChange={(event) => setTag(event.target.value)} />
          </div>
          <div className="notes-card-list">
            {visibleNotes.map((note) => (
              <button type="button" key={note.id} className={selected?.id === note.id ? "active" : ""} onClick={() => void selectNote(note.id)}>
                <span>{note.note_type === "freeform" ? <FileText size={17} /> : <ListChecks size={17} />}<strong>{note.title}</strong></span>
                <small>{note.note_type === "item_list" ? note.item_count + " item rows" : (note.body?.slice(0, 90) || "Empty note")}</small>
                <span className="notes-tags">{note.tags.map((value) => <em key={value}>{value}</em>)}</span>
                <time>{note.updated_at ? new Date(note.updated_at).toLocaleString() : ""}</time>
              </button>
            ))}
            {!visibleNotes.length && <p className="empty">No notes match these filters.</p>}
          </div>
        </aside>

        <main className="notes-editor">
          {selected && draft ? (
            <>
              <header className="notes-editor-heading">
                <div><span>{selected.note_type === "freeform" ? "Freeform note" : "Item / resupply list"}</span><small>Created {selected.created_at ? new Date(selected.created_at).toLocaleString() : "recently"} · Updated {selected.updated_at ? new Date(selected.updated_at).toLocaleString() : "recently"}</small></div>
                <div className="button-row">
                  <button type="button" disabled={busy} onClick={() => void save()}><Save size={16} /> Save</button>
                  <button type="button" disabled={busy} onClick={() => void duplicate()}><Copy size={16} /> Duplicate</button>
                  <button type="button" className="danger" disabled={busy} onClick={() => void remove()}><Trash2 size={16} /> Delete</button>
                </div>
              </header>

              <div className="notes-metadata">
                <label>Title<input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
                <label>Tags<input value={draft.tags} placeholder="doctrine, market, deployment" onChange={(event) => setDraft({ ...draft, tags: event.target.value })} /></label>
                {selected.note_type === "item_list" && <label>Preferred market hub<select value={draft.source_market_hub_key} onChange={(event) => setDraft({ ...draft, source_market_hub_key: event.target.value })}><option value="">No preference</option>{hubs.filter((hub) => hub.available).map((hub) => <option key={hub.key} value={hub.key}>{hub.label}</option>)}</select></label>}
              </div>

              {selected.note_type === "freeform" ? (
                <label className="notes-freeform-body">Note<textarea value={draft.body} placeholder="Write anything useful here..." onChange={(event) => setDraft({ ...draft, body: event.target.value })} /></label>
              ) : (
                <>
                  <label className="notes-description">Description<textarea value={draft.body} placeholder="Purpose, route, doctrine, or handoff notes..." onChange={(event) => setDraft({ ...draft, body: event.target.value })} /></label>
                  <div className="notes-summary-grid">
                    <article><span>Item rows</span><strong>{selected.summary.item_count}</strong></article>
                    <article><span>Requested units</span><strong>{selected.summary.requested_units.toLocaleString()}</strong></article>
                    <article><span>Remaining units</span><strong>{selected.summary.remaining_units.toLocaleString()}</strong></article>
                    <article><span>Completed</span><strong>{selected.summary.completed_items}</strong></article>
                    <article className={selected.summary.unresolved_items ? "warning" : ""}><span>Unresolved</span><strong>{selected.summary.unresolved_items}</strong></article>
                  </div>
                  <ItemListEditor
                    api={api}
                    note={selected}
                    assetScope={assetScope}
                    ownerIds={ownerIds}
                    onAssetScopeChange={changeAssetScope}
                    onReload={() => loadDetail()}
                    onPatchNote={patchNote}
                  />
                </>
              )}
            </>
          ) : (
            <div className="notes-empty-state"><ListChecks size={38} /><h4>Select a note or create a new one</h4><p>Your notes are private to your EQM account.</p><button type="button" onClick={() => void create("item_list")}><Plus size={16} /> Create item list</button></div>
          )}
        </main>
      </div>
    </section>
  );
}