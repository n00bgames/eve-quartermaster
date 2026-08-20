import { Beaker, Clock3, Copy, Factory, FlaskConical, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { BlueprintHoverCard } from "../../components/BlueprintHoverCard";
import { ModuleFinder } from "../../components/ModuleFinder";
import { isCharacterSyncPollingAborted, resumeCharacterSyncJob, trackCharacterSyncJob } from "../../lib/characterSyncPolling";
import { matchesSearchTerms } from "../../lib/search";

import { ResearchQueuePlanner } from "./ResearchQueuePlanner";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type Project = {
  id: number; job_id: number; activity_id: number; activity_name: string; status: string;
  character_id?: number | null; installer_character_id?: number | null; character_name: string; character_portrait_url?: string | null;
  source_type: "character" | "corporation"; corporation_id?: number | null; corporation_name?: string | null;
  blueprint_type_id?: number | null; blueprint_name: string; product_name?: string | null; material_efficiency?: number | null; time_efficiency?: number | null; runs_remaining?: number | null; is_copy?: boolean | null; blueprint_location_name?: string | null;
  facility_id?: number | null; facility_name?: string | null; runs: number; licensed_runs?: number | null;
  successful_runs?: number | null; probability?: number | null; cost?: number | null; duration?: number | null;
  start_date?: string | null; end_date?: string | null; completed_date?: string | null; last_synced_at: string;
};
type Payload = {
  as_of: string;
  summary: { active: number; manufacturing: number; material_efficiency: number; time_efficiency: number; copying: number; invention: number; history: number };
  sync_tokens: { token_id: number; character_id: number; character_name: string; has_scope: boolean; has_corporation_scope: boolean; has_corporation_role_scope: boolean; can_sync: boolean }[];
  projects: Project[];
};
type SyncJob = {
  job_id: string; status: "queued" | "running" | "complete" | "failed"; total_count: number; processed_count: number;
  success_count: number; failed_count: number; skipped_count: number; current_character_name?: string | null; errors: string[];
};
type SortKey = "blueprint" | "activity" | "installer" | "owner" | "status" | "runs" | "facility" | "cost" | "timing";
type SortDirection = "asc" | "desc";

const activeStatuses = new Set(["active", "paused", "ready"]);
const isk = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

function projectSortValue(project: Project, key: SortKey): string | number {
  switch (key) {
    case "blueprint": return `${project.blueprint_name} ${project.product_name ?? ""}`;
    case "activity": return project.activity_name;
    case "installer": return project.character_name;
    case "owner": return project.corporation_name ?? project.character_name;
    case "status": return project.status;
    case "runs": return project.runs;
    case "facility": return project.facility_name ?? project.facility_id ?? "";
    case "cost": return project.cost ?? 0;
    case "timing": return Date.parse(project.end_date ?? project.completed_date ?? project.start_date ?? "") || 0;
  }
}

export function ResearchProjectsPage({ api, formatDateTime }: { api: ApiClient; formatDateTime: (value?: string | null) => string }) {
  const [data, setData] = useState<Payload | null>(null);
  const [view, setView] = useState<"active" | "history">("active");
  const [activity, setActivity] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("timing");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [syncJob, setSyncJob] = useState<SyncJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const syncPollAbortRef = useRef<AbortController | null>(null);


  async function load() {
    setError(null);
    setData(await api<Payload>("/research-projects?include_history=true"));
  }

  async function syncAll() {
    setBusy(true);
    setError(null);
    try {
      const initialJob = await api<SyncJob>("/esi/sync/characters/all?sync_kind=research", { method: "POST", body: "{}" });
      setSyncJob(initialJob);
      const job = await trackCharacterSyncJob({
        scope: "research-all",
        initialJob,
        fetchLatest: (current) => api<SyncJob>(`/esi/sync/characters/all/${current.job_id}`),
        onUpdate: setSyncJob,
        signal: syncPollAbortRef.current?.signal,
      });
      await load();
      if (job.failed_count) setError(job.errors.join(" · "));
    } catch (err) {
      if (!isCharacterSyncPollingAborted(err)) setError(err instanceof Error ? err.message : "Research sync failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    syncPollAbortRef.current = controller;
    void load().catch((err) => setError(err instanceof Error ? err.message : "Unable to load research projects"));
    void resumeCharacterSyncJob<SyncJob>({
      scope: "research-all",
      fetchById: (jobId) => api<SyncJob>(`/esi/sync/characters/all/${jobId}`),
      onUpdate: (job) => { setSyncJob(job); setBusy(true); },
      signal: controller.signal,
    }).then(async (job) => {
      if (!job) return;
      await load();
      if (job.failed_count) setError(job.errors.join(" · "));
    }).catch((err) => {
      if (!isCharacterSyncPollingAborted(err)) setError(err instanceof Error ? err.message : "Unable to resume research sync");
    }).finally(() => setBusy(false));
    return () => controller.abort();
  }, []);

  const projects = useMemo(() => {
    return (data?.projects ?? []).filter((project) => {
      const statusMatches = view === "active" ? activeStatuses.has(project.status) : !activeStatuses.has(project.status);
      return statusMatches
        && (activity === "all" || String(project.activity_id) === activity)
        && matchesSearchTerms(query, [
          project.blueprint_name,
          project.product_name,
          project.activity_name,
          project.character_name,
          project.corporation_name,
          project.facility_name,
          project.blueprint_location_name,
          project.status,
          project.source_type,
          project.job_id,
          project.blueprint_type_id,
          project.facility_id,
        ]);
    }).sort((left, right) => {
      const leftValue = projectSortValue(left, sortKey);
      const rightValue = projectSortValue(right, sortKey);
      const result = typeof leftValue === "number" && typeof rightValue === "number"
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: "base" });
      return sortDirection === "asc" ? result : -result;
    });
  }, [data, view, activity, query, sortKey, sortDirection]);

  const unsearchedProjectCount = useMemo(() => (data?.projects ?? []).filter((project) => {
    const statusMatches = view === "active" ? activeStatuses.has(project.status) : !activeStatuses.has(project.status);
    return statusMatches && (activity === "all" || String(project.activity_id) === activity);
  }).length, [activity, data, view]);

  const eligible = data?.sync_tokens.filter((token) => token.can_sync && (token.has_scope || (token.has_corporation_scope && token.has_corporation_role_scope))).length ?? 0;
  const syncPercent = syncJob && syncJob.total_count ? Math.round(syncJob.processed_count / syncJob.total_count * 100) : 0;

  function toggleSort(nextKey: SortKey) {
    if (nextKey === sortKey) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "cost" || nextKey === "runs" ? "desc" : "asc");
  }

  function sortHeader(key: SortKey, label: string) {
    const mark = sortKey === key ? (sortDirection === "asc" ? "^" : "v") : "";
    return <button className="sort-header" type="button" onClick={() => toggleSort(key)}>{label}<span>{mark}</span></button>;
  }


  return <section className="panel stacked research-projects-page">
    <div className="section-heading">
      <div><h3>Research Projects</h3><p>Current character and corporation manufacturing, research, copying, and invention queues with retained history for analytics.</p></div>
      <div className="button-row compact"><button type="button" disabled={busy || eligible === 0} onClick={() => void syncAll()}><RefreshCw size={16} />{busy ? "Syncing" : "Sync all projects"}</button><button type="button" disabled={busy} onClick={() => void load()}><RefreshCw size={16} />Refresh</button></div>
    </div>
    {error && <div className="mini-alert">{error}</div>}
    {syncJob && <div className={`research-sync-status ${syncJob.failed_count ? "has-errors" : ""}`}><div><strong>{syncJob.processed_count} / {syncJob.total_count}</strong><span>{syncJob.current_character_name ? `Syncing ${syncJob.current_character_name}` : syncJob.status === "complete" ? "Industry-project sync complete" : syncJob.status === "failed" ? "Industry-project sync needs review" : "Industry-project sync queued"}</span></div><progress max={100} value={syncPercent} /><small>{syncJob.success_count} synced · {syncJob.failed_count} failed · {syncJob.skipped_count} skipped</small></div>}
    <div className="status-grid research-summary-grid">
      <article><Beaker size={19} /><span>Active</span><strong>{data?.summary.active ?? 0}</strong></article>
      <article><Factory size={19} /><span>Manufacturing</span><strong>{data?.summary.manufacturing ?? 0}</strong></article>
      <article><FlaskConical size={19} /><span>ME / TE</span><strong>{(data?.summary.material_efficiency ?? 0) + (data?.summary.time_efficiency ?? 0)}</strong></article>
      <article><Copy size={19} /><span>Copying</span><strong>{data?.summary.copying ?? 0}</strong></article>
      <article><Beaker size={19} /><span>Invention</span><strong>{data?.summary.invention ?? 0}</strong></article>
      <article><Clock3 size={19} /><span>Recorded history</span><strong>{data?.summary.history ?? 0}</strong></article>
    </div>
    <div className="research-controls">
      <div className="owner-kind-chips"><button type="button" className={view === "active" ? "active" : ""} onClick={() => setView("active")}>In progress</button><button type="button" className={view === "history" ? "active" : ""} onClick={() => setView("history")}>History</button></div>
      <ModuleFinder query={query} onQueryChange={setQuery} label="Search industry projects" placeholder="Blueprint, product, pilot, owner, facility…" resultCount={projects.length} totalCount={unsearchedProjectCount} />
      <label>Activity<select value={activity} onChange={(event) => setActivity(event.target.value)}><option value="all">All activities</option><option value="1">Manufacturing</option><option value="4">Material Efficiency</option><option value="3">Time Efficiency</option><option value="5">Copying</option><option value="8">Invention</option></select></label>
    </div>
    <div className="table-wrap research-table-wrap">
      <table className="research-table">
        <thead><tr><th>{sortHeader("blueprint", "Blueprint")}</th><th>{sortHeader("activity", "Activity")}</th><th>{sortHeader("installer", "Installed by")}</th><th>{sortHeader("owner", "Owner")}</th><th>{sortHeader("status", "Status")}</th><th>{sortHeader("runs", "Runs")}</th><th>{sortHeader("facility", "Facility")}</th><th>{sortHeader("cost", "Cost")}</th><th>{sortHeader("timing", "Timeline")}</th></tr></thead>
        <tbody>
          {projects.map((project) => <ResearchProjectRow key={project.id} project={project} formatDateTime={formatDateTime} />)}
          {data && projects.length === 0 && <tr><td colSpan={9}>No {view === "active" ? "active" : "historical"} industry projects match this filter.</td></tr>}
          {!data && !error && <tr><td colSpan={9}>Loading industry projects...</td></tr>}
        </tbody>
      </table>
    </div>
    <ResearchQueuePlanner api={api} formatDateTime={formatDateTime} />
  </section>;
}

function ResearchProjectRow({ project, formatDateTime }: { project: Project; formatDateTime: (value?: string | null) => string }) {
  const start = project.start_date ? new Date(project.start_date).getTime() : 0;
  const end = project.end_date ? new Date(project.end_date).getTime() : 0;
  const now = Date.now();
  const progress = start && end > start ? Math.max(0, Math.min(100, (now - start) / (end - start) * 100)) : project.status === "delivered" ? 100 : 0;
  const remaining = end ? durationLabel(end - now) : "No due time";
  const portraitId = project.character_id ?? project.installer_character_id;
  const portrait = project.character_portrait_url || (portraitId ? `https://images.evetech.net/characters/${portraitId}/portrait?size=64` : "");

  return <tr className="research-project-row">
    <td><BlueprintHoverCard details={{ name: project.blueprint_name, owner: project.corporation_name ?? project.character_name, kind: project.is_copy == null ? null : project.is_copy ? "BPC" : "BPO", materialEfficiency: project.material_efficiency, timeEfficiency: project.time_efficiency, runsRemaining: project.runs_remaining, location: project.blueprint_location_name ?? project.facility_name, use: { active: activeStatuses.has(project.status), activity: project.activity_name, status: project.status, job_id: project.job_id, runs: project.runs, facility: project.facility_name, installer: project.character_name, start_date: project.start_date, end_date: project.end_date } }}><strong>{project.blueprint_name}</strong></BlueprintHoverCard>{project.product_name && <span>Output: {project.product_name}</span>}</td>
    <td><strong>{project.activity_name}</strong>{project.probability != null && <span>{Math.round(project.probability * 100)}% chance</span>}</td>
    <td><span className="research-installer">{portrait && <img src={portrait} alt="" />}<span>{project.character_name}</span></span></td>
    <td><span className="manufacturing-status-badge">{project.source_type}</span><span>{project.corporation_name ?? project.character_name}</span></td>
    <td><span className="manufacturing-status-badge">{project.status}</span></td>
    <td>{project.runs.toLocaleString()}</td>
    <td>{project.facility_name ?? `Location ${project.facility_id ?? "unknown"}`}</td>
    <td>{project.cost != null ? `${isk.format(project.cost)} ISK` : "Not reported"}</td>
    <td><div className="research-table-timeline"><strong>{activeStatuses.has(project.status) ? remaining : `Completed ${formatDateTime(project.completed_date ?? project.end_date)}`}</strong><span>{formatDateTime(project.start_date)} to {formatDateTime(project.end_date)}</span><progress max={100} value={progress} /></div></td>
  </tr>;
}

function durationLabel(milliseconds: number) {
  if (milliseconds <= 0) return "Ready for delivery";
  const minutes = Math.ceil(milliseconds / 60_000);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor(minutes % 1440 / 60);
  const mins = minutes % 60;
  return `${days ? `${days}d ` : ""}${hours ? `${hours}h ` : ""}${mins}m remaining`;
}
