import { Activity, Building2, Database, GraduationCap, ScrollText } from "lucide-react";
import React, { useEffect, useState } from "react";

import { BlueprintHoverCard } from "../../components/BlueprintHoverCard";
import { TimeSeriesChart } from "../../components/TimeSeriesChart";
import { iskFormatter } from "../../lib/market";
import type { AnalyticsCorporationScopeResponse, AnalyticsMaintenancePreview, AnalyticsPoint, AnalyticsRetentionMode, AnalyticsRetentionSettings, AnalyticsSummary, DuplicateBlueprint, MetricCatalogItem, PlanetaryAnalytics } from "../../types/analytics";
import type { FinancialAnalytics } from "../../types/financialAnalytics";
import { FinancialDashboard } from "./FinancialDashboard";
import { ManufacturingAnalyticsWidgets } from "./ManufacturingAnalyticsWidgets";
import { MiningAnalyticsWidget } from "./MiningAnalyticsWidget";
import { PlanetaryAnalyticsWidget } from "./PlanetaryAnalyticsWidget";
import { ResearchAnalyticsWidget } from "./ResearchAnalyticsWidget";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type MetricComponent = (props: { icon: React.ReactNode; label: string; value: string | number; delta?: string }) => React.ReactElement;

type AnalyticsPlatformProps = {
  currentUser: { id: number; role: string };
  api: ApiClient;
  Metric: MetricComponent;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const numberFormatter = new Intl.NumberFormat();
const trendColors = ["#55c7d8", "#e8b84d", "#79e0a7", "#e87575", "#9a8cff", "#ff9f68", "#d97ad9", "#7eb6ff"];

function coverageLabel(seconds: number): string {
  const hours = Math.max(0, Math.floor(seconds / 3600));
  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return days > 0 ? `${days}d ${remainingHours}h` : `${remainingHours}h`;
}

export function AnalyticsPlatform({ currentUser, api, Metric }: AnalyticsPlatformProps) {
  const [days, setDays] = useState(30);
  const canViewAllPilots = ["host", "admin"].includes(currentUser.role);
  const [analyticsScope, setAnalyticsScope] = useState(canViewAllPilots ? "all" : "mine");
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [planetary, setPlanetary] = useState<PlanetaryAnalytics | null>(null);
  const [financial, setFinancial] = useState<FinancialAnalytics | null>(null);
  const [catalog, setCatalog] = useState<MetricCatalogItem[]>([]);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [maintenancePreview, setMaintenancePreview] = useState<AnalyticsMaintenancePreview | null>(null);
  const [retention, setRetention] = useState<AnalyticsRetentionSettings | null>(null);
  const [retentionDraft, setRetentionDraft] = useState<AnalyticsRetentionMode>("full");
  const [corporationScope, setCorporationScope] = useState<AnalyticsCorporationScopeResponse>({ can_manage: false, corporations: [] });
  const [showCorporationScope, setShowCorporationScope] = useState(false);
  const [busyCorporationId, setBusyCorporationId] = useState<number | null>(null);

  async function loadAnalytics(selectedDays = days, selectedScope = analyticsScope) {
    setAnalyticsError(null);
    setLoading(true);
    try {
      const [scopeMode, scopeEntityId] = selectedScope.includes(":") ? selectedScope.split(":", 2) : [selectedScope, null];
      const entityQuery = scopeMode === "corporation" && scopeEntityId ? `&corporation_id=${encodeURIComponent(scopeEntityId)}` : scopeMode === "alliance" && scopeEntityId ? `&alliance_id=${encodeURIComponent(scopeEntityId)}` : "";
      const scopeQuery = `scope=${encodeURIComponent(scopeMode)}${entityQuery}`;
      const [nextSummary, nextCatalog, nextCorporationScope, nextPlanetary, nextFinancial, nextRetention] = await Promise.all([api<AnalyticsSummary>(`/analytics/summary?days=${selectedDays}&${scopeQuery}`), api<MetricCatalogItem[]>("/analytics/metrics"), api<AnalyticsCorporationScopeResponse>("/analytics/corporations"), api<PlanetaryAnalytics>(`/analytics/planetary-industry?days=${selectedDays}&${scopeQuery}`), api<FinancialAnalytics>(`/analytics/financial?days=${selectedDays}`), api<AnalyticsRetentionSettings>("/analytics/retention")]);
      setSummary(nextSummary);
      setCatalog(nextCatalog);
      setCorporationScope(nextCorporationScope);
      setPlanetary(nextPlanetary);
      setFinancial(nextFinancial);
      setRetention(nextRetention);
      setRetentionDraft(nextRetention.mode);
    } finally {
      setLoading(false);
    }
  }

  async function toggleCorporationScope(corporationId: number, excluded: boolean) {
    setBusyCorporationId(corporationId);
    setAnalyticsError(null);
    try {
      await api(`/analytics/corporations/${corporationId}`, { method: "PATCH", body: JSON.stringify({ excluded }) });
      setMessage(`Corporation ${excluded ? "excluded from" : "included in"} analytics.`);
      await loadAnalytics();
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Corporation analytics setting failed");
    } finally {
      setBusyCorporationId(null);
    }
  }
  async function toggleCorporationWalletTotals(corporationId: number, visible: boolean) {
    setBusyCorporationId(corporationId);
    setAnalyticsError(null);
    try {
      await api(`/analytics/corporations/${corporationId}`, { method: "PATCH", body: JSON.stringify({ wallet_totals_visible: visible }) });
      setMessage(`Corporation wallet totals ${visible ? "enabled" : "returned to trend-only mode"}.`);
      await loadAnalytics();
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Corporation wallet privacy setting failed");
    } finally {
      setBusyCorporationId(null);
    }
  }

  async function downloadExport(format: "csv" | "json") {
    const token = localStorage.getItem("eq_access_token");
    const response = await fetch(`${API_BASE}/analytics/exports/metrics.${format}?days=${days}`, { credentials: "include", headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!response.ok) throw new Error(`Export failed: ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `eqm-metrics-${days}d.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function inspectLegacySnapshots() {
    setBusy(true);
    setAnalyticsError(null);
    try {
      setMaintenancePreview(await api<AnalyticsMaintenancePreview>("/analytics/maintenance/legacy-snapshots"));
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Unable to inspect legacy analytics history");
    } finally {
      setBusy(false);
    }
  }

  async function compactLegacySnapshots() {
    if (!maintenancePreview) return;
    const rows = maintenancePreview.candidate_rows;
    if (!window.confirm(`Compact ${rows.snapshot_runs.toLocaleString()} redundant legacy snapshot runs? Manual snapshots and the latest complete automatic snapshot for every UTC day will be preserved.`)) return;
    setBusy(true);
    setAnalyticsError(null);
    try {
      const result = await api<{ status: string; deleted: AnalyticsMaintenancePreview["candidate_rows"]; maintenance_note: string }>("/analytics/maintenance/legacy-snapshots/compact", { method: "POST", body: "{}" });
      setMessage(`Compacted ${result.deleted.snapshot_runs.toLocaleString()} legacy runs and ${result.deleted.blueprint_rows.toLocaleString()} duplicate blueprint rows. ${result.maintenance_note}`);
      setMaintenancePreview(null);
      await loadAnalytics();
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Legacy analytics compaction failed");
    } finally {
      setBusy(false);
    }
  }
  async function clearSnapshots() {
    if (!window.confirm("Clear all analytics snapshot history? Current synced assets, skills, wallets, and corporation records will stay intact.")) return;
    setBusy(true);
    setAnalyticsError(null);
    try {
      const result = await api<{ status: string; deleted_snapshot_runs: number }>("/analytics/snapshots", { method: "DELETE" });
      setMessage(`Cleared ${result.deleted_snapshot_runs.toLocaleString()} analytics snapshot run${result.deleted_snapshot_runs === 1 ? "" : "s"}.`);
      await loadAnalytics();
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Snapshot cleanup failed");
    } finally {
      setBusy(false);
    }
  }

  async function captureSnapshot() {
    setBusy(true);
    setAnalyticsError(null);
    try {
      const result = await api<{ status: string; snapshot_run_id: number }>("/analytics/snapshot", { method: "POST", body: "{}" });
      setMessage(result.status === "unchanged" ? `Observation ${result.snapshot_run_id} checked; no values changed.` : `Snapshot ${result.snapshot_run_id} captured.`);
      await loadAnalytics();
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Snapshot failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveRetentionMode() {
    if (!retention || retentionDraft === retention.mode) return;
    setBusy(true);
    setAnalyticsError(null);
    try {
      const next = await api<AnalyticsRetentionSettings>("/analytics/retention", { method: "PATCH", body: JSON.stringify({ mode: retentionDraft }) });
      setRetention(next);
      setRetentionDraft(next.mode);
      setMessage(`Analytics storage set to ${next.modes.find((mode) => mode.key === next.mode)?.label ?? next.mode}. Existing history was preserved.`);
      await loadAnalytics();
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Analytics retention setting failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadAnalytics().catch((err) => setAnalyticsError(err instanceof Error ? err.message : "Unable to load analytics")); }, []);

  return <section className="panel stacked analytics-platform"><div className="section-heading"><div><h3>Analytics Platform</h3><p>Historical snapshot engine, metric providers, report exports, and composable widgets. First observations establish baselines; deltas start after a later snapshot.</p></div><div className="button-row compact"><select aria-label="Analytics pilot scope" value={analyticsScope} onChange={(event) => { const next = event.target.value; setAnalyticsScope(next); void loadAnalytics(days, next); }}>{canViewAllPilots && <option value="all">All Pilots</option>}<option value="mine">My Pilots</option>{(summary?.scope.corporations ?? []).length > 0 && <optgroup label="Corporations">{summary?.scope.corporations.map((corporation) => <option key={corporation.id} value={`corporation:${corporation.id}`}>{corporation.name}{corporation.ticker ? ` [${corporation.ticker}]` : ""}</option>)}</optgroup>}{(summary?.scope.alliances ?? []).length > 0 && <optgroup label="Alliances">{summary?.scope.alliances.map((alliance) => <option key={alliance.id} value={`alliance:${alliance.id}`}>{alliance.name}{alliance.ticker ? ` [${alliance.ticker}]` : ""}</option>)}</optgroup>}</select><select aria-label="Analytics reporting period" value={days} onChange={(event) => { const next = Number(event.target.value); setDays(next); void loadAnalytics(next, analyticsScope); }}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>1 year</option></select><button type="button" onClick={() => setShowCorporationScope((value) => !value)}>{showCorporationScope ? "Hide corporation scope" : "Corporation scope"}</button><button type="button" disabled={busy} onClick={() => void captureSnapshot()}>{busy ? "Working" : "Capture snapshot"}</button>{currentUser.role === "host" && <button type="button" disabled={busy} onClick={() => void inspectLegacySnapshots()}>Inspect storage</button>}{["host", "admin"].includes(currentUser.role) && <button type="button" className="danger" disabled={busy} onClick={() => void clearSnapshots()}>Clear snapshots</button>}</div></div>{message && <div className="notice inline">{message}</div>}{analyticsError && <div className="mini-alert">{analyticsError}</div>}{loading && <div className="analytics-loading-placard" role="status" aria-live="polite"><Activity className="spin" size={22} /><div><strong>Analytics loading.</strong><span>This may take some time. Do not refresh the page.</span></div></div>}{retention && <article className="analytics-retention-panel"><div><strong>Analytics storage · {retention.modes.find((mode) => mode.key === retention.mode)?.label}</strong><span>{retention.note}</span></div>{retention.can_manage && <div className="analytics-retention-controls">{retention.modes.map((mode) => <label key={mode.key} className={retentionDraft === mode.key ? "active" : ""}><input type="radio" name="analytics-retention" value={mode.key} checked={retentionDraft === mode.key} onChange={() => setRetentionDraft(mode.key)} /><span><b>{mode.label}</b><small>{mode.description}</small></span></label>)}<button type="button" disabled={busy || retentionDraft === retention.mode} onClick={() => void saveRetentionMode()}>Save storage mode</button></div>}</article>}{summary && <div className={summary.coverage.complete ? "analytics-coverage-placard" : "analytics-coverage-placard partial"}><strong>{summary.coverage.complete ? `Full ${summary.days}-day platform coverage` : `${coverageLabel(summary.coverage.available_seconds)} of the requested ${summary.days}-day range is available`}</strong><span>{summary.coverage.available_from && summary.coverage.available_to ? `${new Date(summary.coverage.available_from).toLocaleString()} through ${new Date(summary.coverage.available_to).toLocaleString()}. ` : ""}Pilot-derived widgets use the selected analytics scope. Financial Analytics retains its stricter owner/corporation privacy controls. Each metric series follows its own observation timestamps; a run ID does not imply every metric was collected.</span></div>}{maintenancePreview && <div className="analytics-maintenance-placard"><div><strong>Legacy analytics compaction available</strong><span>{maintenancePreview.strategy}</span><small>{maintenancePreview.candidate_rows.snapshot_runs.toLocaleString()} redundant runs · {maintenancePreview.candidate_rows.blueprint_rows.toLocaleString()} blueprint rows · {maintenancePreview.candidate_rows.metric_rows.toLocaleString()} metric rows</small></div><div className="button-row compact"><button type="button" disabled={busy || maintenancePreview.candidate_rows.snapshot_runs === 0} onClick={() => void compactLegacySnapshots()}>Compact legacy history</button><button type="button" disabled={busy} onClick={() => setMaintenancePreview(null)}>Dismiss</button></div></div>}{showCorporationScope && <article className="analytics-widget metric-catalog"><h4>Corporation Scope</h4><p>Only corporations with a successful corporation-level ESI sync can contribute to analytics. Hidden and manually excluded corporations remain omitted.</p><div className="metric-chip-row">{corporationScope.corporations.map((corporation) => { const source = corporation.managed ? "Managed" : corporation.affiliation ? "Affiliation" : "Historical"; return <button key={corporation.id} type="button" className={corporation.excluded ? "metric-chip" : "metric-chip active"} disabled={!corporationScope.can_manage || busyCorporationId === corporation.id || corporation.hidden || !corporation.managed} title={!corporation.managed ? "Corporation-level ESI access is required" : corporation.hidden ? "Hidden corporations remain excluded" : corporation.excluded ? "Include this corporation in analytics" : "Exclude this corporation from analytics"} onClick={() => void toggleCorporationScope(corporation.id, !corporation.excluded)}>{corporation.name}{corporation.ticker ? ` [${corporation.ticker}]` : ""}<small>{!corporation.managed ? "Excluded · No corporate access" : corporation.hidden ? "Excluded while hidden" : corporation.excluded ? `Excluded · ${source}` : `Included · ${source}`}</small></button>; })}</div>{corporationScope.corporations.length === 0 && <p className="empty">No corporation analytics records yet.</p>}</article>}<nav className="analytics-jump-nav" aria-label="Analytics categories"><span>Jump to</span><a href="#analytics-overview">Overview</a><a href="#analytics-financial">Financial</a><a href="#analytics-manufacturing">Manufacturing</a><a href="#analytics-planetary">Planetary</a><a href="#analytics-mining">Mining</a><a href="#analytics-research">Research</a><a href="#analytics-skills">Skills & standings</a><a href="#analytics-corporate">Corporate trends</a></nav>{summary ? <><div id="analytics-overview" className="status-grid wide analytics-category-anchor"><Metric icon={<Database size={18} />} label="Retained snapshots" value={summary.snapshot_count} delta={`${summary.observation_count.toLocaleString()} checks · ${summary.latest_snapshot_at ? `latest ${new Date(summary.latest_snapshot_at).toLocaleString()}` : "none yet"}`} /><Metric icon={<GraduationCap size={18} />} label="Characters" value={summary.cards.character_count} /><Metric icon={<Building2 size={18} />} label="Members" value={summary.cards.member_total} /><Metric icon={<ScrollText size={18} />} label="Blueprints" value={summary.cards.blueprint_total} /><Metric icon={<Activity size={18} />} label="Corp wallets" value={`${iskFormatter.format(summary.cards.wallet_total)} ISK`} /></div><div className="analytics-export-row"><button type="button" onClick={() => void downloadExport("csv")}>Export metrics CSV</button><button type="button" onClick={() => void downloadExport("json")}>Export metrics JSON</button><button type="button" onClick={() => void navigator.clipboard.writeText(discordAnalyticsSummary(summary))}>Copy Discord summary</button></div>{financial && <FinancialDashboard data={financial} canManageCorporations={corporationScope.can_manage} onToggleCorporationTotals={toggleCorporationWalletTotals} />}<MetricCatalogWidget rows={catalog} /><div className="widget-grid"><ChangeCompositionWidget summary={summary} /><ManufacturingAnalyticsWidgets summary={summary.manufacturing} days={summary.days} />{planetary && <PlanetaryAnalyticsWidget summary={planetary} />}<MiningAnalyticsWidget summary={summary.mining} days={summary.days} /><ResearchAnalyticsWidget summary={summary.research_projects} days={summary.days} /><span id="analytics-skills" className="analytics-scroll-anchor" aria-hidden="true" /><AnalyticsWidget title="SP Gain" rows={summary.top_sp_gainers} unit="SP" /><AnalyticsWidget title="Skill Point History" rows={summary.top_sp_losses} unit="SP extracted" loss /><AnalyticsWidget title="Skill Category Gain" rows={summary.top_skill_category_gainers} unit="SP" /><AnalyticsWidget title="Category Extraction" rows={summary.top_skill_category_losses} unit="SP extracted" loss /><AnalyticsWidget title="NPC Corporation Standing Gains" rows={summary.standings_movement.corporations.gains} unit="standing" limit={10} decimals={2} subtitle={`Net base-standing movement across selected pilots · ${summary.days}d`} /><AnalyticsWidget title="NPC Corporation Standing Losses" rows={summary.standings_movement.corporations.losses} unit="standing" limit={10} decimals={2} subtitle={`Net base-standing movement across selected pilots · ${summary.days}d`} loss /><AnalyticsWidget title="Faction Standing Gains" rows={summary.standings_movement.factions.gains} unit="standing" limit={10} decimals={2} subtitle={`Net base-standing movement across selected pilots · ${summary.days}d`} /><AnalyticsWidget title="Faction Standing Losses" rows={summary.standings_movement.factions.losses} unit="standing" limit={10} decimals={2} subtitle={`Net base-standing movement across selected pilots · ${summary.days}d`} loss /><span id="analytics-corporate" className="analytics-scroll-anchor" aria-hidden="true" /><AnalyticsWidget title="Wallet Growth" rows={summary.wallet_growth} unit="ISK" isk /><AnalyticsWidget title="Corporation Growth" rows={summary.member_growth} unit="members" /><AnalyticsWidget title="Blueprint Growth" rows={summary.blueprint_growth} unit="BPs" /><DuplicateBlueprintWidget rows={summary.duplicate_blueprints} /><TrendWidget title="Wallet Trend" points={summary.series.wallet_totals} days={summary.days} isk /><TrendWidget title="Blueprint Trend" points={summary.series.blueprint_counts} days={summary.days} /></div></> : !loading && <p className="empty">No analytics snapshots yet. Capture one manually or run a sync to start building history.</p>}</section>;
}

function discordAnalyticsSummary(summary: AnalyticsSummary): string {
  const topSp = summary.top_sp_gainers[0];
  const wallet = summary.wallet_growth[0];
  const sp = summary.change_composition.skill_points;
  return [`EQM ${summary.days}-day report`, `Snapshots: ${summary.snapshot_count}`, `SP change: ${formatDelta(sp.organic_delta, "SP")} organic / ${formatDelta(sp.coverage_delta, "SP")} newly tracked`, `Top SP: ${topSp ? `${topSp.name} +${numberFormatter.format(topSp.delta)} SP` : "none"}`, `Top wallet: ${wallet ? `${wallet.name} ${iskFormatter.format(wallet.delta)} ISK` : "none"}`, `Blueprints: ${numberFormatter.format(summary.cards.blueprint_total)}`].join("\n");
}

function ChangeCompositionWidget({ summary }: { summary: AnalyticsSummary }) {
  const rows = [
    { label: "Skill points", data: summary.change_composition.skill_points, unit: "SP", isk: false },
    { label: "Corporation wallets", data: summary.change_composition.corporation_wallets, unit: "ISK", isk: true },
    { label: "Members", data: summary.change_composition.members, unit: "members", isk: false },
    { label: "Blueprints", data: summary.change_composition.blueprints, unit: "BPs", isk: false },
  ];
  const value = (amount: number, unit: string, isk: boolean) => `${isk ? iskFormatter.format(amount) : numberFormatter.format(Math.round(amount))} ${unit}`;
  return <article className="analytics-widget change-composition-widget"><h4>Change Composition</h4><p><strong>Net change = Organic change + Coverage change.</strong> First observations are coverage, not growth.</p><div className="change-composition-list">{rows.map((row) => <section key={row.label}><div><span>{row.label}</span><strong>{value(row.data.current, row.unit, row.isk)}</strong></div><b>{formatDelta(row.data.total_delta, row.unit, row.isk)} net change</b><small>{formatDelta(row.data.organic_delta, row.unit, row.isk)} organic · {formatDelta(row.data.coverage_delta, row.unit, row.isk)} coverage{row.data.newly_tracked_count ? ` · ${row.data.newly_tracked_count} newly tracked owner${row.data.newly_tracked_count === 1 ? "" : "s"}` : ""}</small></section>)}</div></article>;
}

function AnalyticsWidget({ title, rows, unit, isk = false, loss = false, limit = 8, decimals = 0, subtitle }: { title: string; rows: { name: string; delta: number }[]; unit: string; isk?: boolean; loss?: boolean; limit?: number; decimals?: number; subtitle?: string }) {
  const max = Math.max(...rows.map((row) => Math.abs(row.delta)), 1);
  return <article className="analytics-widget"><h4>{title}</h4>{subtitle && <p>{subtitle}</p>}<div className="widget-list">{rows.slice(0, limit).map((row) => <div key={`${title}-${row.name}`} className={loss ? "widget-row loss-row" : "widget-row"}><span>{row.name}</span><strong>{loss ? formatLoss(row.delta, unit, isk, decimals) : formatDelta(row.delta, unit, isk, decimals)}</strong><i style={{ width: `${Math.max(4, Math.abs(row.delta) / max * 100)}%` }} /></div>)}{rows.length === 0 && <p className="empty">No baseline-backed movement yet.</p>}</div></article>;
}

function MetricCatalogWidget({ rows }: { rows: MetricCatalogItem[] }) {
  return <article className="analytics-widget metric-catalog"><h4>Metric Catalog</h4><p>Every registered metric declares how values roll up across entities and time. Charts can consume this contract instead of hard-coding metric behavior.</p><div className="metric-chip-row">{rows.map((row) => <span key={row.metric} className={row.hasData ? "metric-chip has-data" : "metric-chip"} title={row.description}>{row.label}<small>v{row.version} · {row.unit} · {row.valueKind}</small><small>Entities: {row.entityAggregation} · Time: {row.timeAggregation}</small><small>{row.supportedAggregations.length ? row.supportedAggregations.join(", ") : "No aggregation contract"}{row.supportedTransforms.length ? ` · ${row.supportedTransforms.join(", ")}` : ""}{!row.registered ? " · unregistered" : row.deprecated ? " · deprecated" : ""}</small>{row.derivedMetrics.length > 0 && <small>Virtual: {row.derivedMetrics.map((derived) => derived.metric).join(", ")}</small>}</span>)}</div></article>;
}

function DuplicateBlueprintWidget({ rows }: { rows: DuplicateBlueprint[] }) {
  const [kindFilter, setKindFilter] = useState<"all" | "bpo" | "bpc">("all");
  const [ownerFilter, setOwnerFilter] = useState("all");
  const ownerNames = Array.from(new Set(rows.map((row) => row.owner_name))).sort((left, right) => left.localeCompare(right));
  const kindMatches = (row: DuplicateBlueprint) => kindFilter === "all" || (kindFilter === "bpc" ? row.is_copy : !row.is_copy);
  const ownerMatches = (row: DuplicateBlueprint) => ownerFilter === "all" || row.owner_name === ownerFilter;
  const kindOptions: { key: "all" | "bpo" | "bpc"; label: string }[] = [
    { key: "all", label: "All" },
    { key: "bpo", label: "BPO" },
    { key: "bpc", label: "BPC" },
  ];
  const filteredRows = rows.filter((row) => kindMatches(row) && ownerMatches(row));
  const maxQuantity = Math.max(...filteredRows.map((row) => row.quantity), 1);
  const countForKind = (kind: "all" | "bpo" | "bpc") => rows.filter((row) => kind === "all" || (kind === "bpc" ? row.is_copy : !row.is_copy)).length;
  const countForOwner = (ownerName: string) => rows.filter((row) => kindMatches(row) && (ownerName === "all" || row.owner_name === ownerName)).length;

  return <article className="analytics-widget"><h4>Duplicate BPs</h4><div className="metric-chip-row duplicate-filter-row">{kindOptions.map((option) => <button key={option.key} type="button" className={kindFilter === option.key ? "metric-chip active" : "metric-chip"} onClick={() => setKindFilter(option.key)}>{option.label}<small>{countForKind(option.key).toLocaleString()}</small></button>)}</div><div className="metric-chip-row duplicate-filter-row duplicate-owner-row"><button type="button" className={ownerFilter === "all" ? "metric-chip active" : "metric-chip"} onClick={() => setOwnerFilter("all")}>All Corps<small>{countForOwner("all").toLocaleString()}</small></button>{ownerNames.map((ownerName) => <button key={ownerName} type="button" className={ownerFilter === ownerName ? "metric-chip active" : "metric-chip"} onClick={() => setOwnerFilter(ownerName)}>{ownerName}<small>{countForOwner(ownerName).toLocaleString()}</small></button>)}</div><div className="widget-list">{filteredRows.slice(0, 8).map((row) => <div key={`${row.owner_name}-${row.blueprint_type_name}-${row.is_copy}`} className="widget-row"><BlueprintHoverCard details={{ name: row.blueprint_type_name, owner: row.owner_name, kind: row.is_copy ? "BPC" : "BPO", materialEfficiencyLabel: row.material_efficiency_levels.join(", "), timeEfficiencyLabel: row.time_efficiency_levels.join(", "), location: "Multiple synced locations", use: row.in_use > 0 ? { active: true, activity: `${row.in_use.toLocaleString()} currently in use` } : null, note: `${row.quantity.toLocaleString()} synced instances in this aggregate.` }}><span>{row.blueprint_type_name}</span></BlueprintHoverCard><strong>{row.quantity.toLocaleString()} {row.is_copy ? "BPC" : "BPO"}</strong><small>{row.owner_name}</small><i style={{ width: `${Math.max(5, row.quantity / maxQuantity * 100)}%` }} /></div>)}{filteredRows.length === 0 && <p className="empty">No duplicate blueprint stacks match this filter.</p>}</div></article>;
}

function TrendWidget({ title, points, days, isk = false }: { title: string; points: AnalyticsPoint[]; days: number; isk?: boolean }) {
  const datedPoints = points
    .filter((point): point is AnalyticsPoint & { date: string } => Boolean(point.date) && Number.isFinite(Date.parse(point.date as string)))
    .sort((left, right) => Date.parse(left.date) - Date.parse(right.date));
  const grouped = new Map<string, (AnalyticsPoint & { date: string })[]>();
  for (const point of datedPoints) {
    const key = point.corporation_id == null ? point.corporation_name ?? "Corporation" : String(point.corporation_id);
    grouped.set(key, [...(grouped.get(key) ?? []), point]);
  }
  const series = Array.from(grouped.entries())
    .map(([key, values]) => ({ key, name: values[0]?.corporation_name ?? "Corporation", values }))
    .sort((left, right) => left.name.localeCompare(right.name));
  if (series.length === 0) return <article className="analytics-widget"><h4>{title}</h4><p className="empty">No trend data yet.</p></article>;

  const formatValue = (value: number) => isk ? `${iskFormatter.format(value)} ISK` : numberFormatter.format(Math.round(value));
  const uniqueDays = new Set(datedPoints.map((point) => point.date.slice(0, 10))).size;
  const chartSeries = series.map((item, index) => ({
    key: item.key,
    name: item.name,
    color: trendColors[index % trendColors.length],
    points: item.values.map((point) => ({ date: point.date, value: point.value })),
  }));

  return <article className="analytics-widget trend-widget"><h4>{title}</h4><p className="trend-summary">Daily closing snapshots · {series.length} corporation{series.length === 1 ? "" : "s"} · {uniqueDays} day{uniqueDays === 1 ? "" : "s"}</p><TimeSeriesChart ariaLabel={`${title} by corporation`} selectedDays={days} series={chartSeries} formatValue={formatValue} /><div className="trend-legend">{series.map((item, index) => { const latest = item.values[item.values.length - 1]; return <div key={item.key}><i style={{ backgroundColor: trendColors[index % trendColors.length] }} /><span>{item.name}</span><strong>{formatValue(latest.value)}</strong></div>; })}</div></article>;
}
function formatDelta(value: number, unit: string, isk = false, decimals = 0) {
  const sign = value > 0 ? "+" : "";
  const formatted = isk ? iskFormatter.format(value) : decimals > 0 ? value.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : numberFormatter.format(Math.round(value));
  return `${sign}${formatted} ${unit}`;
}

function formatLoss(value: number, unit: string, isk = false, decimals = 0) {
  const absolute = Math.abs(value);
  const formatted = isk ? iskFormatter.format(absolute) : decimals > 0 ? absolute.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : numberFormatter.format(Math.round(absolute));
  return `-${formatted} ${unit}`;
}
