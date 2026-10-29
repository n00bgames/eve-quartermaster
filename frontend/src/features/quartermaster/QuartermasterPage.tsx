import {LayoutRegion} from "../appearance/LayoutRegion";
import { useEffect, useMemo, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { ColonyRow } from "../industry/PlanetaryIndustryPage";
import type { PlanetaryColony } from "../../types/planetaryIndustry";
import "./quartermaster.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type Blueprint = { id: number; blueprint_type_name: string; owner_name: string; owner_type: string; location_name?: string; material_efficiency: number; time_efficiency: number; runs_remaining?: number; is_copy: boolean; quantity: number; last_synced_at?: string; research_shadow?: boolean; active_use?: { activity: string }; location_resolution?: { immediate_location_name?: string; location_flag_name?: string; location_resolution_status?: string } };
type Job = { id: number; character_name: string; corporation_name?: string; source_type: string; activity_name: string; blueprint_name: string; product_name?: string; facility_name?: string; status: string; runs: number; end_date?: string; last_synced_at?: string };
type SyncJob = { job_id: string; status: string; total_count: number; processed_count: number; success_count: number; failed_count: number; skipped_count: number; current?: string; errors: string[]; warnings: string[] };
type Payload = { as_of: string; notice: string; warnings: string[]; summary: { bpo: number; bpc: number; active_jobs: number; colonies: number }; blueprints: Blueprint[]; jobs: Job[]; colonies: PlanetaryColony[] };

export function QuartermasterPage({ api, formatDateTime }: { api: ApiClient; formatDateTime: (value?: string | null) => string }) {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState("Blueprints");
  const [search, setSearch] = useState("");
  const [owner, setOwner] = useState("");
  const [kind, setKind] = useState("");
  const [expanded, setExpanded] = useState<number[]>([]);
  const [sync, setSync] = useState<SyncJob | null>(null);
  const [starting, setStarting] = useState(false);
  const [syncAttempt, setSyncAttempt] = useState(0);
  const syncing = starting || !!sync && ["queued", "running"].includes(sync.status);
  async function startSync() {
    setStarting(true); setError("");
    try { setSync(await api<SyncJob>("/quartermaster-oversight/sync", { method: "POST", body: "{}" })); setSyncAttempt(value => value + 1); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not start Sync All"); }
    finally { setStarting(false); }
  }
  useEffect(() => { const abort = new AbortController(); void api<SyncJob | null>("/quartermaster-oversight/sync", { signal: abort.signal }).then(value => { if (!abort.signal.aborted) setSync(value); }).catch(() => undefined); return () => abort.abort(); }, [api]);
  useEffect(() => {
    if (!sync || !["queued", "running"].includes(sync.status)) return;
    const abort = new AbortController(); const jobId = sync.job_id;
    void (async () => {
      try {
        while (!abort.signal.aborted) {
          await new Promise(resolve => setTimeout(resolve, 1500));
          if (abort.signal.aborted) return;
          const next = await api<SyncJob>(`/quartermaster-oversight/sync/${jobId}`, { signal: abort.signal });
          if (abort.signal.aborted) return;
          setSync(next);
          if (!["queued", "running"].includes(next.status)) { await load(abort.signal); return; }
        }
      } catch (e) { if (!abort.signal.aborted) { setSync(old => old ? { ...old, status: "unavailable" } : old); setError(e instanceof Error ? e.message : "Sync progress is unavailable; refresh the view"); } }
    })();
    return () => abort.abort();
  }, [api, sync?.job_id, syncAttempt]);
  async function load(signal?: AbortSignal) {
    setBusy(true); setError(""); setData(null);
    try { const next = await api<Payload>("/quartermaster-oversight", { signal }); if (!signal?.aborted) setData(next); }
    catch (e) { if (!signal?.aborted) setError(e instanceof Error ? e.message : "Quartermaster data is unavailable"); }
    finally { if (!signal?.aborted) setBusy(false); }
  }
  useEffect(() => { const abort = new AbortController(); void load(abort.signal); return () => abort.abort(); }, [api]);
  const needle = search.trim().toLocaleLowerCase();
  const matches = (...values: (string | null | undefined)[]) => values.some(value => value?.toLocaleLowerCase().includes(needle));
  const blueprints = useMemo(() => (data?.blueprints ?? []).filter(row => (!owner || row.owner_name === owner) && (!kind || (row.is_copy ? "BPC" : "BPO") === kind) && matches(row.blueprint_type_name, row.owner_name, row.location_name, row.location_resolution?.immediate_location_name)), [data, owner, kind, needle]);
  const jobs = (data?.jobs ?? []).filter(row => matches(row.character_name, row.corporation_name, row.blueprint_name, row.product_name, row.facility_name));
  const colonies = (data?.colonies ?? []).filter(row => matches(row.character_name, row.planet_name, row.solar_system_name));
  const owners = [...new Set((data?.blueprints ?? []).map(row => row.owner_name))].sort();
  return <LayoutRegion region="quartermaster" className="qm-workspace">
    <section key="quartermaster-1" data-layout-id="quartermaster-1" data-layout-label="Section 1" className="panel"><div className="qm-heading"><div><h3><ShieldCheck size={21} /> View-only Quartermaster</h3><p>Blueprints, industry jobs, and planetary infrastructure across authenticated characters and authorized linked corporations.</p></div><div className="qm-tabs"><button type="button" disabled={syncing || busy} onClick={() => void startSync()}><RefreshCw size={16} />{syncing ? "Syncing…" : "Sync All"}</button><button type="button" disabled={busy || syncing} onClick={() => void load()}>{busy ? "Loading…" : "Refresh view"}</button></div></div>
      <p className="muted">Sync All refreshes blueprint inventories and locations, industry jobs, and PI for eligible linked owners. It respects ESI scopes, corporate roles, privacy opt-outs, and ESI cache timing. Other records remain view-only.</p>
      {error && <p role="alert" className="mini-alert">{error}</p>}
      {busy && <p role="status">Loading Quartermaster records…</p>}
      {sync && <div className="qm-sync" role="status"><strong>Sync All · {sync.status}</strong><p>{sync.processed_count} / {sync.total_count} tasks · {sync.success_count} refreshed · {sync.failed_count} failed · {sync.skipped_count} skipped</p>{sync.current && <p>{sync.current}</p>}<progress value={sync.processed_count} max={Math.max(1, sync.total_count)} />{sync.errors.map((message, index) => <p className="mini-alert" key={index}>{message}</p>)}{sync.warnings.map((message, index) => <p className="notice warning" key={index}>{message}</p>)}</div>}
      {data && <><div className="qm-metrics">{[["BPOs", data.summary.bpo], ["BPCs", data.summary.bpc], ["Running / ready jobs", data.summary.active_jobs], ["PI colonies", data.summary.colonies]].map(([label, value]) => <div key={label}><strong>{Number(value).toLocaleString()}</strong><span>{label}</span></div>)}</div><p className="muted">{data.notice}</p>{data.warnings.map(warning => <p className="notice warning" key={warning}>{warning}</p>)}<small>View generated {formatDateTime(data.as_of)}. Blueprint counts are items; BPC licensed runs are listed separately.</small></>}
    </section>
    <section key="quartermaster-2" data-layout-id="quartermaster-2" data-layout-label="Section 2" className="panel"><div className="qm-tabs" role="group" aria-label="Quartermaster views">{["Blueprints", "Industry jobs", "Planetary infrastructure"].map(value => <button key={value} type="button" aria-pressed={tab === value} onClick={() => { setTab(value); setSearch(""); }}>{value}</button>)}</div>
      <div className="qm-filters"><label>Search<input value={search} onChange={event => setSearch(event.target.value)} placeholder={tab === "Blueprints" ? "Blueprint, owner, or location" : "Pilot, product, planet, or location"} /></label>{tab === "Blueprints" && <><label>Owner<select aria-label="Owner" value={owner} onChange={event => setOwner(event.target.value)}><option value="">All owners</option>{owners.map(value => <option key={value}>{value}</option>)}</select></label><label>Blueprint kind<select aria-label="Blueprint kind" value={kind} onChange={event => setKind(event.target.value)}><option value="">BPOs and BPCs</option><option>BPO</option><option>BPC</option></select></label></>}</div>
      {data && tab === "Blueprints" && <><p>{blueprints.reduce((total, row) => total + row.quantity, 0)} blueprint items · {blueprints.filter(row => !row.is_copy).reduce((total, row) => total + row.quantity, 0)} BPOs · {blueprints.filter(row => row.is_copy).reduce((total, row) => total + row.quantity, 0)} BPCs in this view</p><div className="table-wrap"><table><thead><tr><th>Blueprint</th><th>Owner</th><th>Kind / count</th><th>Location / hangar</th><th>ME / TE</th><th>Licensed runs</th><th>Last synced</th></tr></thead><tbody>{blueprints.map(row => <tr key={row.id}><td>{row.blueprint_type_name}{row.active_use && <small>{row.active_use.activity}</small>}{row.research_shadow && <small>Located through active research</small>}</td><td>{row.owner_name}<small>{row.owner_type}</small></td><td>{row.is_copy ? "BPC" : "BPO"} × {row.quantity}</td><td>{row.location_name || "Unresolved location"}<small>{row.location_resolution?.immediate_location_name} {row.location_resolution?.location_flag_name}</small><small>{row.location_resolution?.location_resolution_status}</small></td><td>{row.material_efficiency} / {row.time_efficiency}</td><td>{row.is_copy ? row.runs_remaining ?? "Unknown" : "Unlimited"}</td><td>{formatDateTime(row.last_synced_at)}</td></tr>)}</tbody></table></div>{!blueprints.length && <p>No matching blueprint records. Authorizations or cached data may be missing.</p>}</>}
      {data && tab === "Industry jobs" && <><p>{jobs.length} active, paused, or ready jobs</p><div className="table-wrap"><table><thead><tr><th>Installer / owner</th><th>Activity</th><th>Blueprint / product</th><th>Facility</th><th>Status / runs</th><th>Ends</th><th>Last synced</th></tr></thead><tbody>{jobs.map(row => <tr key={row.id}><td>{row.character_name}<small>{row.source_type === "corporation" ? row.corporation_name : "Character job"}</small></td><td>{row.activity_name}</td><td>{row.blueprint_name}<small>{row.product_name}</small></td><td>{row.facility_name || "Unknown facility"}</td><td>{row.status} · {row.runs} runs</td><td>{formatDateTime(row.end_date)}</td><td>{formatDateTime(row.last_synced_at)}</td></tr>)}</tbody></table></div>{!jobs.length && <p>No matching running jobs in available cached records.</p>}</>}
      {data && tab === "Planetary infrastructure" && <div className="planetary-colony-list">{colonies.map(colony => <div key={colony.id}><ColonyRow colony={colony} expanded={expanded.includes(colony.id)} onToggle={() => setExpanded(old => old.includes(colony.id) ? old.filter(id => id !== colony.id) : [...old, colony.id])} formatDateTime={formatDateTime} />{expanded.includes(colony.id) && <details><summary>Routes ({colony.routes.length})</summary><div className="table-wrap"><table><thead><tr><th>From pin</th><th>To pin</th><th>Commodity</th><th>Quantity</th></tr></thead><tbody>{colony.routes.map(route => <tr key={route.route_id}><td>{route.source_pin_id}</td><td>{route.destination_pin_id}</td><td>{route.content_name}</td><td>{route.quantity}</td></tr>)}</tbody></table></div></details>}</div>)}{!colonies.length && <p>No matching colonies in available cached records.</p>}</div>}
    </section>
  </LayoutRegion>;
}
