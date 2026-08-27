import { Activity, Database, MapIcon, RefreshCw, ScrollText, UserRoundCheck } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { PilotSecurityStatus } from "../characters/PilotSecurityStatus";
import { formatDateTime, formatDurationMs, formatTimeOnly, localizeUtcHourLabel, preferredTimeZone } from "../../lib/time";
import { iskFormatter } from "../../lib/market";
import type { IndustrialThreatAnalysis, IndustrialThreatRank, LocalThreatAnalysis, LocalThreatJob, LocalThreatPilot, NavigationSystem, PvpIntelAnalysis } from "../../types/navigation";
import { SystemSearchField } from "./RouteChecker";

type ThreatIntelUser = { timezone?: string };
type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type EveEntityKind = "character" | "corporation" | "alliance";
type EveIconSize = "tiny" | "sm" | "md" | "lg";

type ThreatMetric = (props: { icon: ReactNode; label: string; value: string | number; delta?: string }) => ReactElement;

type ThreatWidgetProps = {
  currentUser: ThreatIntelUser;
  api: ApiClient;
  Metric: ThreatMetric;
};

type LocalThreatWidgetProps = ThreatWidgetProps & {
  EveEntityIcon: (props: { kind: EveEntityKind; id?: number | null; name?: string | null; size?: EveIconSize }) => ReactElement;
  CharacterHoverName: (props: { characterId?: number | null; name: string; className?: string; href?: string }) => ReactElement;
};

function parseLocalThreatInput(raw: string, maxPilots = 2000): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const part of raw.split(/[\r\n,;]+/)) {
    const cleaned = part.replace(/^\[[0-9:. ]+\]\s*/, "").replace(/\s+/g, " ").trim();
    const key = cleaned.toLocaleLowerCase();
    if (cleaned.length < 3 || seen.has(key)) continue;
    seen.add(key);
    names.push(cleaned);
    if (names.length >= maxPilots) break;
  }
  return names;
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
function IndustrialThreatRankList({ title, rows, valueLabel = "ISK", formatName }: { title: string; rows: IndustrialThreatRank[]; valueLabel?: string; formatName?: (name: string) => ReactNode }) {

  return <section className="threat-card"><h4>{title}</h4>{rows.length > 0 ? <div className="threat-rank-list">{rows.map((row) => <div key={row.name}><span>{formatName ? formatName(row.name) : row.name}</span><strong>{row.count.toLocaleString()}</strong>{typeof row.total_value === "number" && row.total_value > 0 && <small>{iskFormatter.format(row.total_value)} {valueLabel}</small>}</div>)}</div> : <p className="empty">No cached observations yet.</p>}</section>;

}



export function IndustrialSystemThreatWidget({ currentUser, api, Metric }: ThreatWidgetProps) {

  const [system, setSystem] = useState("Uedama");

  const [systemOptions, setSystemOptions] = useState<NavigationSystem[]>([]);

  const [refreshHours, setRefreshHours] = useState(24);

  const [analysis, setAnalysis] = useState<IndustrialThreatAnalysis | null>(null);

  const [busy, setBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const selectionRef = useRef(system);

  const timeZone = preferredTimeZone(currentUser);






  async function searchThreatSystems(query: string) {

    if (query.trim().length < 2) {

      setSystemOptions([]);

      return;

    }

    try {

      setSystemOptions(await api<NavigationSystem[]>(`/navigation/systems?q=${encodeURIComponent(query)}&limit=12`));

    } catch {

      setSystemOptions([]);

    }

  }



  function pickThreatSystem(nextSystem: NavigationSystem) {

    selectionRef.current = nextSystem.name;

    setSystem(nextSystem.name);

    setSystemOptions([]);

  }



  async function analyze(forceRefresh = false) {

    setBusy(true);

    setError(null);

    try {

      const params = new URLSearchParams({ system, refresh_hours: String(refreshHours), days: "90", force_refresh: String(forceRefresh) });

      setAnalysis(await api<IndustrialThreatAnalysis>(`/navigation/industrial-threat?${params.toString()}`));

    } catch (err) {

      setError(err instanceof Error ? err.message : "Industrial threat analysis failed");

    } finally {

      setBusy(false);

    }

  }



  useEffect(() => { if (system.trim() === selectionRef.current.trim()) { setSystemOptions([]); return; } const timer = window.setTimeout(() => void searchThreatSystems(system), 180); return () => window.clearTimeout(timer); }, [system]);



  return <section className="panel stacked industrial-threat-widget"><div className="section-heading"><div><h3>Industrial System Threat</h3><p>Cached zKill industrial-loss observations retained for 90 days. Live refresh is manual and throttled per system/window.</p></div>{analysis && <span className={`risk-badge risk-${analysis.risk_label}`}>{analysis.risk_label}</span>}</div><div className="route-form threat-form"><SystemSearchField label="System" value={system} options={systemOptions} placeholder="Uedama" onChange={(value) => { selectionRef.current = ""; setSystem(value); }} onPick={pickThreatSystem} /><label>Refresh window<select value={refreshHours} onChange={(event) => setRefreshHours(Number(event.target.value))}><option value={1}>1 hour</option><option value={6}>6 hours</option><option value={12}>12 hours</option><option value={24}>24 hours</option><option value={72}>3 days</option><option value={168}>7 days</option></select></label><button type="button" disabled={busy || !system.trim()} onClick={() => void analyze(false)}><Activity size={18} /> {busy ? "Analyzing" : "Analyze"}</button><button type="button" disabled={busy || !system.trim()} onClick={() => void analyze(true)}><RefreshCw size={18} /> Force refresh</button></div>{error && <div className="mini-alert">{error}</div>}{analysis ? <><div className="gatecheck-summary"><Metric icon={<Activity size={18} />} label="Industrial kills" value={analysis.total_industrial_kills} delta={`${analysis.days}d cached`} /><Metric icon={<Database size={18} />} label="Destroyed value" value={`${iskFormatter.format(analysis.total_destroyed_value)} ISK`} /><Metric icon={<MapIcon size={18} />} label="System" value={analysis.system.name} delta={analysis.latest_killmail_time ? `latest ${formatDateTime(analysis.latest_killmail_time, timeZone)}` : "no cached kills"} /><Metric icon={<ScrollText size={18} />} label="Cache" value={analysis.cache.live_fetch_performed ? "refreshed" : "reused"} delta={analysis.cache.expires_at ? `fresh until ${formatTimeOnly(analysis.cache.expires_at, timeZone)}` : `${analysis.cache.ttl_minutes}m TTL`} /></div><div className="threat-grid"><IndustrialThreatRankList title="Top Industrial Hulls Lost" rows={analysis.top_victim_hulls} /><IndustrialThreatRankList title="Hottest UTC Hours" rows={analysis.top_time_periods} formatName={(name) => localizeUtcHourLabel(name, timeZone)} /><IndustrialThreatRankList title="Ganking Corporations" rows={analysis.top_attacker_corporations} /><IndustrialThreatRankList title="Ganking Alliances" rows={analysis.top_attacker_alliances} /><IndustrialThreatRankList title="Dangerous Gates and Stations" rows={analysis.most_dangerous_locations} /><IndustrialThreatRankList title="Final Blow Hulls" rows={analysis.top_final_blow_hulls} /><IndustrialThreatRankList title="Attacker Group Sizes" rows={analysis.top_attacker_group_sizes} /></div></> : <p className="empty">Analyze a system to start collecting and reading its cached industrial threat profile.</p>}</section>;

}



export function PvpIntelWidget({ currentUser, api, Metric }: ThreatWidgetProps) {

  const [system, setSystem] = useState("Tama");

  const [systemOptions, setSystemOptions] = useState<NavigationSystem[]>([]);

  const [refreshHours, setRefreshHours] = useState(24);

  const [analysis, setAnalysis] = useState<PvpIntelAnalysis | null>(null);

  const [busy, setBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const selectionRef = useRef(system);

  const timeZone = preferredTimeZone(currentUser);






  async function searchIntelSystems(query: string) {

    if (query.trim().length < 2) {

      setSystemOptions([]);

      return;

    }

    try {

      setSystemOptions(await api<NavigationSystem[]>(`/navigation/systems?q=${encodeURIComponent(query)}&limit=12`));

    } catch {

      setSystemOptions([]);

    }

  }



  function pickIntelSystem(nextSystem: NavigationSystem) {

    selectionRef.current = nextSystem.name;

    setSystem(nextSystem.name);

    setSystemOptions([]);

  }



  async function analyze(forceRefresh = false) {

    setBusy(true);

    setError(null);

    try {

      const params = new URLSearchParams({ system, refresh_hours: String(refreshHours), days: "90", force_refresh: String(forceRefresh) });

      setAnalysis(await api<PvpIntelAnalysis>(`/navigation/pvp-intel?${params.toString()}`));

    } catch (err) {

      setError(err instanceof Error ? err.message : "PvP intel report failed");

    } finally {

      setBusy(false);

    }

  }



  useEffect(() => { if (system.trim() === selectionRef.current.trim()) { setSystemOptions([]); return; } const timer = window.setTimeout(() => void searchIntelSystems(system), 180); return () => window.clearTimeout(timer); }, [system]);



  return <section className="panel stacked industrial-threat-widget pvp-intel-widget"><div className="section-heading"><div><h3>PvP Intel Report</h3><p>All zKill losses for a system, cached for 90 days with the same controlled refresh windows.</p></div>{analysis && <span className={`risk-badge risk-${analysis.risk_label}`}>{analysis.risk_label}</span>}</div><div className="route-form threat-form"><SystemSearchField label="System" value={system} options={systemOptions} placeholder="Tama" onChange={(value) => { selectionRef.current = ""; setSystem(value); }} onPick={pickIntelSystem} /><label>Refresh window<select value={refreshHours} onChange={(event) => setRefreshHours(Number(event.target.value))}><option value={1}>1 hour</option><option value={6}>6 hours</option><option value={12}>12 hours</option><option value={24}>24 hours</option><option value={72}>3 days</option><option value={168}>7 days</option></select></label><button type="button" disabled={busy || !system.trim()} onClick={() => void analyze(false)}><Activity size={18} /> {busy ? "Analyzing" : "Analyze"}</button><button type="button" disabled={busy || !system.trim()} onClick={() => void analyze(true)}><RefreshCw size={18} /> Force refresh</button></div>{error && <div className="mini-alert">{error}</div>}{analysis ? <><div className="gatecheck-summary"><Metric icon={<Activity size={18} />} label="PvP kills" value={analysis.total_kills} delta={`${analysis.days}d cached`} />{analysis.system_jump_activity && <Metric icon={<MapIcon size={18} />} label="Last-hour traffic" value={analysis.system_jump_activity.observations > 0 ? `${analysis.system_jump_activity.jumps_last_hour.toLocaleString()} jumps` : "Unavailable"} delta={analysis.system_jump_activity.observations > 0 ? `${analysis.system_jump_activity.ship_kills_last_hour.toLocaleString()} ship · ${analysis.system_jump_activity.pod_kills_last_hour.toLocaleString()} pod kills` : "ESI sample unavailable"} />}<Metric icon={<Database size={18} />} label="Destroyed value" value={`${iskFormatter.format(analysis.total_destroyed_value)} ISK`} /><Metric icon={<MapIcon size={18} />} label="System" value={analysis.system.name} delta={analysis.latest_killmail_time ? `latest ${formatDateTime(analysis.latest_killmail_time, timeZone)}` : "no cached kills"} /><Metric icon={<ScrollText size={18} />} label="Cache" value={analysis.cache.live_fetch_performed ? "refreshed" : "reused"} delta={analysis.cache.expires_at ? `fresh until ${formatTimeOnly(analysis.cache.expires_at, timeZone)}` : `${analysis.cache.ttl_minutes}m TTL`} /></div><div className="threat-grid"><IndustrialThreatRankList title="Top Hulls Lost" rows={analysis.top_victim_hulls} /><IndustrialThreatRankList title="Hottest UTC Hours" rows={analysis.top_time_periods} formatName={(name) => localizeUtcHourLabel(name, timeZone)} /><IndustrialThreatRankList title="Attacking Corporations" rows={analysis.top_attacker_corporations} /><IndustrialThreatRankList title="Attacking Alliances" rows={analysis.top_attacker_alliances} /><IndustrialThreatRankList title="Victim Corporations" rows={analysis.top_victim_corporations} /><IndustrialThreatRankList title="Victim Alliances" rows={analysis.top_victim_alliances} /><IndustrialThreatRankList title="Dangerous Gates and Stations" rows={analysis.most_dangerous_locations} /><IndustrialThreatRankList title="Final Blow Hulls" rows={analysis.top_final_blow_hulls} /><IndustrialThreatRankList title="Attacker Group Sizes" rows={analysis.top_attacker_group_sizes} /></div></> : <p className="empty">Analyze a system to build a broader PvP heat profile from cached all-kill observations.</p>}</section>;

}

export function LocalThreatWidget({ currentUser, api, Metric, EveEntityIcon, CharacterHoverName }: LocalThreatWidgetProps) {

  const [localText, setLocalText] = useState("");

  const [days, setDays] = useState(30);

  const [analysis, setAnalysis] = useState<LocalThreatAnalysis | null>(null);

  const [job, setJob] = useState<LocalThreatJob | null>(null);

  const [busy, setBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const [sortKey, setSortKey] = useState<"danger" | "period" | "group" | "kills" | "losses" | "solo">("danger");

  const [sortDescending, setSortDescending] = useState(true);

  const [timerNow, setTimerNow] = useState(Date.now());

  const timeZone = preferredTimeZone(currentUser);






  async function analyze() {

    const names = parseLocalThreatInput(localText, 2000);

    if (names.length === 0) {

      setError("Paste at least one valid pilot name.");

      setAnalysis(null);

      setJob(null);

      return;

    }



    setBusy(true);

    setError(null);

    setJob(null);

    setAnalysis(null);

    try {

      let nextJob = await api<LocalThreatJob>(`/navigation/local-threat/jobs?days=${days}`, { method: "POST", body: JSON.stringify({ names }) });

      setJob(nextJob);

      setAnalysis(nextJob.analysis);



      while (nextJob.status === "queued" || nextJob.status === "running" || nextJob.status === "cancelling") {

        await delay(1200);

        nextJob = await api<LocalThreatJob>(`/navigation/local-threat/jobs/${nextJob.job_id}`);

        setJob(nextJob);

        setAnalysis(nextJob.analysis);

      }



      if (nextJob.status === "failed") {

        setError(nextJob.analysis.errors[0] ?? "Local threat job failed.");

      }

    } catch (err) {

      setError(err instanceof Error ? err.message : "Local threat analysis failed");

    } finally {

      setBusy(false);

    }

  }



  async function cancelJob() {

    if (!job || !jobIsActive) return;

    setError(null);

    try {

      const nextJob = await api<LocalThreatJob>(`/navigation/local-threat/jobs/${job.job_id}/cancel`, { method: "POST" });

      setJob(nextJob);

      setAnalysis(nextJob.analysis);

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to cancel local threat scan");

    }

  }



  function sortMetric(pilot: LocalThreatPilot): number {

    if (sortKey === "kills") return pilot.recent_kills;

    if (sortKey === "period") return pilot.period_danger_score ?? 0;

    if (sortKey === "losses") return pilot.recent_losses;

    if (sortKey === "group") return pilot.group_kill_percent ?? 0;

    if (sortKey === "solo") return pilot.solo_kills ?? 0;

    return pilot.danger_score;

  }



  function setSort(nextKey: typeof sortKey) {

    if (nextKey === sortKey) setSortDescending((value) => !value);

    else {

      setSortKey(nextKey);

      setSortDescending(true);

    }

  }



  function sortMark(key: typeof sortKey): string {

    if (key !== sortKey) return "";

    return sortDescending ? "v" : "^";

  }



  const sortedPilots = useMemo(() => {

    const rows = [...(analysis?.pilots ?? [])];

    rows.sort((left, right) => {

      const primary = sortMetric(right) - sortMetric(left);

      const fallback = (right.danger_score - left.danger_score) || (right.recent_kills - left.recent_kills);

      return (sortDescending ? 1 : -1) * (primary || fallback);

    });

    return rows;

  }, [analysis, sortKey, sortDescending]);



  const hottest = sortedPilots[0];

  const jobIsActive = job?.status === "queued" || job?.status === "running" || job?.status === "cancelling";

  const queueTotal = job?.total_count ?? analysis?.input_count ?? 0;

  const queueProcessed = job?.processed_count ?? (analysis ? analysis.input_count : 0);

  const queuePercent = queueTotal > 0 ? Math.min(100, Math.round((queueProcessed / queueTotal) * 100)) : 0;

  const jobStartedAt = job?.created_at ? new Date(job.created_at).getTime() : null;

  const jobFinishedAt = job?.completed_at ? new Date(job.completed_at).getTime() : null;

  const queueElapsed = jobStartedAt ? formatDurationMs((jobFinishedAt ?? timerNow) - jobStartedAt) : null;

  const jobStatusLabel = job?.status === "complete" ? "Completed" : job?.status === "cancelled" ? "Cancelled" : job?.status === "cancelling" ? "Cancelling" : job?.status === "running" ? "Running" : job?.status === "queued" ? "Queued" : job?.status === "failed" ? "Failed" : "Idle";



  useEffect(() => {

    if (!jobIsActive) return;

    const timer = window.setInterval(() => setTimerNow(Date.now()), 1000);

    return () => window.clearInterval(timer);

  }, [jobIsActive, job?.job_id]);



  return <section className="panel stacked local-threat-widget">

    <div className="section-heading">

      <div>

        <h3>Local Threat</h3>

        <p>Paste pilots from local to resolve public ESI identities and visible zKill activity. Large systems run in the background and keep the current top 250 threats visible.</p>

      </div>

      <div className="local-threat-heading-actions">

        {job && <span className={`queue-badge queue-${job.status}`} title={`${queueProcessed}/${queueTotal} pilots processed in ${queueElapsed ?? "0:00"}`}><strong>{queueProcessed.toLocaleString()} / {queueTotal.toLocaleString()}</strong><small>{jobStatusLabel} · {queueElapsed ?? "0:00"} · batch {job.batch}/{job.total_batches} · zKill {analysis?.zkill_analyzed_count ?? 0}</small><i style={{ width: `${queuePercent}%` }} /></span>}

        {hottest && <span className={`risk-badge risk-${hottest.danger_label}`}>{hottest.danger_label}</span>}

      </div>

    </div>

    <div className="route-form local-threat-form">

      <label>Pilots<textarea value={localText} onChange={(event) => setLocalText(event.target.value)} placeholder={"Paste local names, one per line\nCODE Crusher\nSteihl Lianul"} /></label>

      <label>Lookback<select value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={7}>7 days</option><option value={14}>14 days</option><option value={30}>30 days</option><option value={60}>60 days</option><option value={90}>90 days</option></select></label>

      <button type="button" disabled={busy || !localText.trim()} onClick={() => void analyze()}><UserRoundCheck size={18} /> {busy ? `Analyzing ${job?.processed_count ?? 0}/${job?.total_count ?? 0}` : "Analyze local"}</button>{jobIsActive && <button type="button" className="danger" disabled={job?.status === "cancelling"} onClick={() => void cancelJob()}>{job?.status === "cancelling" ? "Cancelling" : "Abort scan"}</button>}

    </div>

    {error && <div className="mini-alert">{error}</div>}

    {jobIsActive && <div className="notice inline">Background threat scan running: {queueElapsed ?? "0:00"} elapsed · batch {job?.batch ?? 0}/{job?.total_batches ?? 0} · {job?.processed_count ?? 0}/{job?.total_count ?? 0} pilots processed · showing the strongest {job?.visible_limit ?? 250} seen so far.</div>}

    {analysis ? <>

      <div className="gatecheck-summary">

        <Metric icon={<UserRoundCheck size={18} />} label="Pilots" value={`${analysis.resolved_count}/${analysis.input_count}`} delta={job ? `${job.processed_count}/${job.total_count} processed` : "resolved"} />

        <Metric icon={<Activity size={18} />} label="zKill detail" value={analysis.zkill_analyzed_count} delta={job ? `${job.status} · batch ${job.batch}/${job.total_batches} · top ${job.visible_limit}` : `top ${analysis.zkill_detail_limit}`} />

        <Metric icon={<ScrollText size={18} />} label="Lookback" value={`${analysis.days}d`} />

        <Metric icon={<Database size={18} />} label="Generated" value={formatTimeOnly(analysis.generated_at, timeZone)} delta={formatDateTime(analysis.generated_at, timeZone)} />

      </div>

      {analysis.errors.map((item) => <div key={item} className="mini-alert subtle">{item}</div>)}

      <div className="local-threat-list">

        <div className="local-threat-table-head"><span>Pilot / Org</span><button type="button" onClick={() => setSort("danger")}>Lifetime {sortMark("danger")}</button><button type="button" onClick={() => setSort("period")}>Current {sortMark("period")}</button><button type="button" onClick={() => setSort("kills")}>Kills {sortMark("kills")}</button><button type="button" onClick={() => setSort("group")}>Group % {sortMark("group")}</button><button type="button" onClick={() => setSort("losses")}>Losses {sortMark("losses")}</button><button type="button" onClick={() => setSort("solo")}>Solo Kills {sortMark("solo")}</button><span>Evidence</span></div>

        {sortedPilots.map((pilot) => <article key={`${pilot.name}-${pilot.character_id ?? pilot.input_name}`} className={`local-threat-pilot risk-${pilot.danger_label}`}>

          <div className="local-threat-identity"><span className="entity-inline"><EveEntityIcon kind="character" id={pilot.character_id} name={pilot.name} /><CharacterHoverName characterId={pilot.character_id} name={pilot.name} className="local-threat-name local-threat-character" href={pilot.character_id ? `https://zkillboard.com/character/${pilot.character_id}/` : undefined} /><PilotSecurityStatus securityStatus={pilot.security_status} compact /></span><span className="local-threat-orgs">{pilot.corporation_id && <EveEntityIcon kind="corporation" id={pilot.corporation_id} name={pilot.corporation_name} size="tiny" />}{pilot.corporation_id ? <a className="local-threat-corporation" href={`https://zkillboard.com/corporation/${pilot.corporation_id}/`} target="_blank" rel="noreferrer">{pilot.corporation_name ?? "Unknown corporation"}</a> : <span className="local-threat-corporation">{pilot.corporation_name ?? "Unknown corporation"}</span>}{pilot.alliance_id ? <> · <EveEntityIcon kind="alliance" id={pilot.alliance_id} name={pilot.alliance_name} size="tiny" /><a className="local-threat-alliance" href={`https://zkillboard.com/alliance/${pilot.alliance_id}/`} target="_blank" rel="noreferrer">{pilot.alliance_name ?? "Unknown alliance"}</a></> : (pilot.alliance_name ? <> · <span className="local-threat-alliance">{pilot.alliance_name}</span></> : "")}</span></div>

          <span className="local-threat-danger"><span className={`risk-badge risk-${pilot.danger_label}`}>{pilot.danger_score}%</span><i style={{ width: `${Math.max(2, Math.min(100, pilot.danger_score))}%` }} /></span>

          <span className="local-threat-danger"><span className={`risk-badge risk-${pilot.period_danger_label ?? "unknown"}`}>{pilot.period_danger_score ?? 0}%</span><i style={{ width: `${Math.max(2, Math.min(100, pilot.period_danger_score ?? 0))}%` }} /></span>

          <span>{pilot.recent_kills.toLocaleString()}<small>{typeof pilot.ships_destroyed === "number" ? `(${pilot.ships_destroyed.toLocaleString()} lifetime)` : "(lifetime unknown)"}</small><small>{typeof pilot.isk_destroyed === "number" ? `${iskFormatter.format(pilot.isk_destroyed)}z all time` : "unknown"}</small></span>

          <span>{(pilot.group_kill_percent ?? 0).toFixed(1)}%</span>

          <span>{pilot.recent_losses.toLocaleString()}<small>{typeof pilot.ships_lost === "number" ? `(${pilot.ships_lost.toLocaleString()} lifetime)` : "(lifetime unknown)"}</small><small>{typeof pilot.isk_lost === "number" ? `${iskFormatter.format(pilot.isk_lost)}z all time` : "unknown"}</small></span>

          <span>{(pilot.solo_kills ?? 0).toLocaleString()}</span>

          <div className="local-threat-evidence"><span>{pilot.last_activity_at ? `Last ${formatDateTime(pilot.last_activity_at, timeZone)}` : "No recent public activity"}</span>{pilot.top_loss_hulls && pilot.top_loss_hulls.length > 0 && <span>{pilot.top_loss_hulls.map((row) => `${row.name} x${row.count}`).join(" · ")}</span>}{pilot.notes.map((note) => <span key={note}>{note}</span>)}</div>

        </article>)}

      </div>

    </> : <p className="empty">Paste local chat pilot names and analyze when you need a fast read on who is in system.</p>}

  </section>;

}
