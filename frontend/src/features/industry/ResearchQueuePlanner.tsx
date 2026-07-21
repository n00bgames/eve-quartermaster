import { ArrowDown, ArrowUp, CheckCircle2, Plus, RotateCcw, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import "./researchQueue.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

type QueueBlueprint = {
  id: number;
  blueprint_type_id: number;
  name: string;
  kind: "BPO" | "BPC";
  is_copy: boolean;
  owner_name: string;
  material_efficiency: number;
  time_efficiency: number;
  runs_remaining?: number | null;
  source_location_name?: string | null;
  source_hangar?: string | null;
};

type QueueItem = {
  id: number;
  blueprint_id?: number | null;
  blueprint_type_id?: number | null;
  blueprint_name: string;
  blueprint_kind: "BPO" | "BPC";
  owner_name?: string | null;
  material_efficiency: number;
  time_efficiency: number;
  runs_remaining?: number | null;
  source_location_name?: string | null;
  source_hangar?: string | null;
  activity_id: number;
  activity_name: string;
  runs: number;
  status: "pending" | "completed";
  sort_order: number;
  created_at?: string | null;
  completed_at?: string | null;
};

type QueuePayload = {
  summary: { pending: number; completed: number };
  items: QueueItem[];
};

const activityOptions = [
  { id: 4, label: "Material Efficiency", kind: "BPO" },
  { id: 3, label: "Time Efficiency", kind: "BPO" },
  { id: 5, label: "Copying", kind: "BPO" },
  { id: 8, label: "Invention", kind: "BPC" },
] as const;

function activitiesFor(kind: "BPO" | "BPC") {
  return activityOptions.filter((option) => option.kind === kind);
}

export function ResearchQueuePlanner({ api, formatDateTime }: { api: ApiClient; formatDateTime: (value?: string | null) => string }) {
  const [data, setData] = useState<QueuePayload | null>(null);
  const [view, setView] = useState<"pending" | "completed" | "all">("pending");
  const [blueprintQuery, setBlueprintQuery] = useState("");
  const [blueprintOptions, setBlueprintOptions] = useState<QueueBlueprint[]>([]);
  const [selectedBlueprint, setSelectedBlueprint] = useState<QueueBlueprint | null>(null);
  const [activityId, setActivityId] = useState(4);
  const [runs, setRuns] = useState(1);
  const [sourceHangar, setSourceHangar] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadQueue() {
    setData(await api<QueuePayload>("/research-projects/queue"));
  }

  useEffect(() => {
    void loadQueue().catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load the research queue."));
  }, []);

  useEffect(() => {
    const query = blueprintQuery.trim();
    if (selectedBlueprint && query === selectedBlueprint.name) {
      setBlueprintOptions([]);
      return;
    }
    if (query.length < 2) {
      setBlueprintOptions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void api<QueueBlueprint[]>("/research-projects/queue/blueprints?q=" + encodeURIComponent(query) + "&limit=40")
        .then(setBlueprintOptions)
        .catch(() => setBlueprintOptions([]));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [api, blueprintQuery, selectedBlueprint]);

  const visibleItems = useMemo(() => {
    const items = data?.items ?? [];
    return items.filter((item) => view === "all" || item.status === view);
  }, [data, view]);

  function chooseBlueprint(blueprint: QueueBlueprint) {
    setSelectedBlueprint(blueprint);
    setBlueprintQuery(blueprint.name);
    setBlueprintOptions([]);
    setActivityId(blueprint.is_copy ? 8 : 4);
    setRuns(1);
    setSourceHangar(blueprint.source_hangar ?? "");
  }

  async function createItem() {
    if (!selectedBlueprint) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api("/research-projects/queue", {
        method: "POST",
        body: JSON.stringify({
          blueprint_id: selectedBlueprint.id,
          activity_id: activityId,
          runs,
          source_hangar: sourceHangar,
        }),
      });
      setMessage(selectedBlueprint.name + " added to the research queue.");
      setSelectedBlueprint(null);
      setBlueprintQuery("");
      setSourceHangar("");
      setRuns(1);
      await loadQueue();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to add the research queue entry.");
    } finally {
      setBusy(false);
    }
  }

  async function patchItem(item: QueueItem, payload: Record<string, unknown>) {
    setBusy(true);
    setError(null);
    try {
      await api("/research-projects/queue/" + item.id, { method: "PATCH", body: JSON.stringify(payload) });
      await loadQueue();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update the research queue entry.");
    } finally {
      setBusy(false);
    }
  }

  async function removeItem(item: QueueItem) {
    if (!window.confirm("Remove " + item.blueprint_name + " from the research queue?")) return;
    setBusy(true);
    setError(null);
    try {
      await api("/research-projects/queue/" + item.id, { method: "DELETE" });
      await loadQueue();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to remove the research queue entry.");
    } finally {
      setBusy(false);
    }
  }

  async function moveItem(item: QueueItem, direction: -1 | 1) {
    const ids = (data?.items ?? []).filter((row) => row.status === "pending").sort((a, b) => a.sort_order - b.sort_order).map((row) => row.id);
    const index = ids.indexOf(item.id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    setBusy(true);
    setError(null);
    try {
      await api("/research-projects/queue/reorder", { method: "POST", body: JSON.stringify({ item_ids: ids }) });
      await loadQueue();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reorder the research queue.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="research-queue-planner">
    <header className="section-heading">
      <div><h4>Next Research Queue</h4><p>Plan the BPO and BPC jobs that should be installed after the current queue clears.</p></div>
      <div className="research-queue-counts"><span>{data?.summary.pending ?? 0} pending</span><span>{data?.summary.completed ?? 0} completed</span></div>
    </header>

    <div className="research-queue-form">
      <label className="research-queue-blueprint-search">
        Owned BPO or BPC
        <div className="input-with-icon"><Search size={15} /><input value={blueprintQuery} placeholder="Search synced blueprints" onChange={(event) => { setBlueprintQuery(event.target.value); setSelectedBlueprint(null); }} /></div>
        {blueprintOptions.length > 0 && <div className="research-queue-search-results">{blueprintOptions.map((blueprint) => <button type="button" key={blueprint.id} onClick={() => chooseBlueprint(blueprint)}>
          <strong>{blueprint.name}</strong>
          <span>{blueprint.kind} · {blueprint.owner_name} · ME {blueprint.material_efficiency} / TE {blueprint.time_efficiency}{blueprint.runs_remaining != null ? " · " + blueprint.runs_remaining + " runs" : ""}</span>
          <small>{blueprint.source_location_name ?? "Location unavailable"}{blueprint.source_hangar ? " · " + blueprint.source_hangar : ""}</small>
        </button>)}</div>}
      </label>
      <label>Job type<select value={activityId} disabled={!selectedBlueprint} onChange={(event) => setActivityId(Number(event.target.value))}>{activitiesFor(selectedBlueprint?.kind ?? "BPO").map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
      <label>Runs<input type="number" min={1} max={1_000_000} value={runs} onChange={(event) => setRuns(Math.max(1, Number(event.target.value) || 1))} /></label>
      <label>Source hangar<input value={sourceHangar} placeholder="Example: Corp Hangar 3 / Research" onChange={(event) => setSourceHangar(event.target.value)} /></label>
      <button type="button" disabled={busy || !selectedBlueprint} onClick={() => void createItem()}><Plus size={16} /> Add to queue</button>
    </div>

    {selectedBlueprint && <div className="research-queue-selection"><strong>{selectedBlueprint.name}</strong><span>{selectedBlueprint.kind} · {selectedBlueprint.owner_name} · ME {selectedBlueprint.material_efficiency} / TE {selectedBlueprint.time_efficiency}</span><small>{selectedBlueprint.source_location_name ?? "Location unavailable"}</small></div>}
    {message && <div className="notice compact">{message}</div>}
    {error && <div className="mini-alert">{error}</div>}

    <div className="research-queue-toolbar">
      <div className="owner-kind-chips">
        <button type="button" className={view === "pending" ? "active" : ""} onClick={() => setView("pending")}>Pending</button>
        <button type="button" className={view === "completed" ? "active" : ""} onClick={() => setView("completed")}>Completed</button>
        <button type="button" className={view === "all" ? "active" : ""} onClick={() => setView("all")}>All</button>
      </div>
    </div>

    <div className="table-wrap research-queue-table-wrap">
      <table className="research-queue-table">
        <thead><tr><th>Order</th><th>Blueprint</th><th>Job</th><th>Runs</th><th>Source hangar</th><th>Status</th><th aria-label="Actions"></th></tr></thead>
        <tbody>
          {visibleItems.map((item) => <tr key={item.id} className={item.status === "completed" ? "completed" : ""}>
            <td>{item.status === "pending" ? item.sort_order + 1 : "-"}</td>
            <td><strong>{item.blueprint_name}</strong><span>{item.blueprint_kind} · {item.owner_name ?? "Unknown owner"} · ME {item.material_efficiency} / TE {item.time_efficiency}</span><small>{item.source_location_name ?? "Location unavailable"}</small></td>
            <td><select value={item.activity_id} disabled={busy || item.status === "completed"} onChange={(event) => void patchItem(item, { activity_id: Number(event.target.value) })}>{activitiesFor(item.blueprint_kind).map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></td>
            <td><input type="number" min={1} max={1_000_000} defaultValue={item.runs} disabled={busy || item.status === "completed"} onBlur={(event) => Number(event.target.value) !== item.runs && void patchItem(item, { runs: Number(event.target.value) })} /></td>
            <td><input defaultValue={item.source_hangar ?? ""} placeholder="Not recorded" disabled={busy || item.status === "completed"} onBlur={(event) => event.target.value !== (item.source_hangar ?? "") && void patchItem(item, { source_hangar: event.target.value })} /></td>
            <td><span className={"research-queue-status " + item.status}>{item.status}</span>{item.completed_at && <small>{formatDateTime(item.completed_at)}</small>}</td>
            <td><div className="research-queue-actions">
              {item.status === "pending" ? <>
                <button type="button" title="Move up" disabled={busy} onClick={() => void moveItem(item, -1)}><ArrowUp size={15} /></button>
                <button type="button" title="Move down" disabled={busy} onClick={() => void moveItem(item, 1)}><ArrowDown size={15} /></button>
                <button type="button" className="success" title="Mark complete" disabled={busy} onClick={() => void patchItem(item, { status: "completed" })}><CheckCircle2 size={15} /></button>
              </> : <button type="button" title="Restore to pending" disabled={busy} onClick={() => void patchItem(item, { status: "pending" })}><RotateCcw size={15} /></button>}
              <button type="button" className="danger" title="Remove entry" disabled={busy} onClick={() => void removeItem(item)}><Trash2 size={15} /></button>
            </div></td>
          </tr>)}
          {data && visibleItems.length === 0 && <tr><td colSpan={7} className="empty">No {view === "all" ? "" : view + " "}research queue entries.</td></tr>}
          {!data && !error && <tr><td colSpan={7} className="empty">Loading research queue...</td></tr>}
        </tbody>
      </table>
    </div>
  </section>;
}
