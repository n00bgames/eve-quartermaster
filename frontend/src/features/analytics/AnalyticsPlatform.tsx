import { Activity, Building2, Database, GraduationCap, ScrollText } from "lucide-react";
import React, { useEffect, useState } from "react";

import { iskFormatter } from "../../lib/market";
import type { AnalyticsPoint, AnalyticsSummary, DuplicateBlueprint, MetricCatalogItem } from "../../types/analytics";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type MetricComponent = (props: { icon: React.ReactNode; label: string; value: string | number; delta?: string }) => React.ReactElement;

type AnalyticsPlatformProps = {
  currentUser: { role: string };
  api: ApiClient;
  Metric: MetricComponent;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const numberFormatter = new Intl.NumberFormat();

export function AnalyticsPlatform({ currentUser, api, Metric }: AnalyticsPlatformProps) {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [catalog, setCatalog] = useState<MetricCatalogItem[]>([]);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadAnalytics(selectedDays = days) {
    setAnalyticsError(null);
    const [nextSummary, nextCatalog] = await Promise.all([api<AnalyticsSummary>(`/analytics/summary?days=${selectedDays}`), api<MetricCatalogItem[]>("/analytics/metrics")]);
    setSummary(nextSummary);
    setCatalog(nextCatalog);
  }

  async function downloadExport(format: "csv" | "json") {
    const token = localStorage.getItem("eq_access_token");
    const response = await fetch(`${API_BASE}/analytics/exports/metrics.${format}?days=${days}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!response.ok) throw new Error(`Export failed: ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `eqm-metrics-${days}d.${format}`;
    link.click();
    URL.revokeObjectURL(url);
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
      setMessage(`Snapshot ${result.snapshot_run_id} captured.`);
      await loadAnalytics();
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Snapshot failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadAnalytics().catch((err) => setAnalyticsError(err instanceof Error ? err.message : "Unable to load analytics")); }, []);

  return <section className="panel stacked analytics-platform"><div className="section-heading"><div><h3>Analytics Platform</h3><p>Historical snapshot engine, metric providers, report exports, and composable widgets. First observations establish baselines; deltas start after a later snapshot.</p></div><div className="button-row compact"><select value={days} onChange={(event) => { const next = Number(event.target.value); setDays(next); void loadAnalytics(next); }}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>1 year</option></select><button type="button" disabled={busy} onClick={() => void captureSnapshot()}>{busy ? "Capturing" : "Capture snapshot"}</button>{currentUser.role === "admin" && <button type="button" className="danger" disabled={busy} onClick={() => void clearSnapshots()}>Clear snapshots</button>}</div></div>{message && <div className="notice inline">{message}</div>}{analyticsError && <div className="mini-alert">{analyticsError}</div>}{summary ? <><div className="status-grid wide"><Metric icon={<Database size={18} />} label="Snapshots" value={summary.snapshot_count} delta={summary.latest_snapshot_at ? `latest ${new Date(summary.latest_snapshot_at).toLocaleString()}` : "none yet"} /><Metric icon={<GraduationCap size={18} />} label="Characters" value={summary.cards.character_count} /><Metric icon={<Building2 size={18} />} label="Members" value={summary.cards.member_total} /><Metric icon={<ScrollText size={18} />} label="Blueprints" value={summary.cards.blueprint_total} /><Metric icon={<Activity size={18} />} label="Corp wallets" value={`${iskFormatter.format(summary.cards.wallet_total)} ISK`} /></div><div className="analytics-export-row"><button type="button" onClick={() => void downloadExport("csv")}>Export metrics CSV</button><button type="button" onClick={() => void downloadExport("json")}>Export metrics JSON</button><button type="button" onClick={() => void navigator.clipboard.writeText(discordAnalyticsSummary(summary))}>Copy Discord summary</button></div><MetricCatalogWidget rows={catalog} /><div className="widget-grid"><AnalyticsWidget title="SP Gain" rows={summary.top_sp_gainers} unit="SP" /><AnalyticsWidget title="Skill Point History" rows={summary.top_sp_losses} unit="SP extracted" loss /><AnalyticsWidget title="Skill Category Gain" rows={summary.top_skill_category_gainers} unit="SP" /><AnalyticsWidget title="Category Extraction" rows={summary.top_skill_category_losses} unit="SP extracted" loss /><AnalyticsWidget title="Wallet Growth" rows={summary.wallet_growth} unit="ISK" isk /><AnalyticsWidget title="Corporation Growth" rows={summary.member_growth} unit="members" /><AnalyticsWidget title="Blueprint Growth" rows={summary.blueprint_growth} unit="BPs" /><DuplicateBlueprintWidget rows={summary.duplicate_blueprints} /><TrendWidget title="Wallet Trend" points={summary.series.wallet_totals} isk /><TrendWidget title="Blueprint Trend" points={summary.series.blueprint_counts} /></div></> : <p className="empty">No analytics snapshots yet. Capture one manually or run a sync to start building history.</p>}</section>;
}

function discordAnalyticsSummary(summary: AnalyticsSummary): string {
  const topSp = summary.top_sp_gainers[0];
  const wallet = summary.wallet_growth[0];
  return [`EQM ${summary.days}-day report`, `Snapshots: ${summary.snapshot_count}`, `Top SP: ${topSp ? `${topSp.name} +${numberFormatter.format(topSp.delta)} SP` : "none"}`, `Top wallet: ${wallet ? `${wallet.name} ${iskFormatter.format(wallet.delta)} ISK` : "none"}`, `Blueprints: ${numberFormatter.format(summary.cards.blueprint_total)}`].join("\n");
}

function AnalyticsWidget({ title, rows, unit, isk = false, loss = false }: { title: string; rows: { name: string; delta: number }[]; unit: string; isk?: boolean; loss?: boolean }) {
  const max = Math.max(...rows.map((row) => Math.abs(row.delta)), 1);
  return <article className="analytics-widget"><h4>{title}</h4><div className="widget-list">{rows.slice(0, 8).map((row) => <div key={`${title}-${row.name}`} className={loss ? "widget-row loss-row" : "widget-row"}><span>{row.name}</span><strong>{loss ? formatLoss(row.delta, unit, isk) : formatDelta(row.delta, unit, isk)}</strong><i style={{ width: `${Math.max(4, Math.abs(row.delta) / max * 100)}%` }} /></div>)}{rows.length === 0 && <p className="empty">No movement yet.</p>}</div></article>;
}

function MetricCatalogWidget({ rows }: { rows: MetricCatalogItem[] }) {
  return <article className="analytics-widget metric-catalog"><h4>Metric Catalog</h4><div className="metric-chip-row">{rows.map((row) => <span key={row.metric} className={row.hasData ? "metric-chip has-data" : "metric-chip"}>{row.label}<small>v{row.version} · {row.unit} · {row.chartTypes.join(", ")}{row.deprecated ? " · deprecated" : ""}</small></span>)}</div></article>;
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

  return <article className="analytics-widget"><h4>Duplicate BPs</h4><div className="metric-chip-row duplicate-filter-row">{kindOptions.map((option) => <button key={option.key} type="button" className={kindFilter === option.key ? "metric-chip active" : "metric-chip"} onClick={() => setKindFilter(option.key)}>{option.label}<small>{countForKind(option.key).toLocaleString()}</small></button>)}</div><div className="metric-chip-row duplicate-filter-row duplicate-owner-row"><button type="button" className={ownerFilter === "all" ? "metric-chip active" : "metric-chip"} onClick={() => setOwnerFilter("all")}>All Corps<small>{countForOwner("all").toLocaleString()}</small></button>{ownerNames.map((ownerName) => <button key={ownerName} type="button" className={ownerFilter === ownerName ? "metric-chip active" : "metric-chip"} onClick={() => setOwnerFilter(ownerName)}>{ownerName}<small>{countForOwner(ownerName).toLocaleString()}</small></button>)}</div><div className="widget-list">{filteredRows.slice(0, 8).map((row) => <div key={`${row.owner_name}-${row.blueprint_type_name}-${row.is_copy}`} className="widget-row"><span>{row.blueprint_type_name}</span><strong>{row.quantity.toLocaleString()} {row.is_copy ? "BPC" : "BPO"}</strong><small>{row.owner_name}</small><i style={{ width: `${Math.max(5, row.quantity / maxQuantity * 100)}%` }} /></div>)}{filteredRows.length === 0 && <p className="empty">No duplicate blueprint stacks match this filter.</p>}</div></article>;
}

function TrendWidget({ title, points, isk = false }: { title: string; points: AnalyticsPoint[]; isk?: boolean }) {
  const compact = points.slice(-24);
  const max = Math.max(...compact.map((point) => point.value), 1);
  return <article className="analytics-widget"><h4>{title}</h4><div className="trend-strip">{compact.map((point, index) => <i key={`${title}-${point.date}-${point.corporation_name}-${index}`} style={{ height: `${Math.max(6, point.value / max * 100)}%` }} title={`${point.corporation_name ?? "value"}: ${isk ? iskFormatter.format(point.value) : numberFormatter.format(point.value)}`} />)}</div>{compact.length === 0 && <p className="empty">No trend data yet.</p>}</article>;
}

function formatDelta(value: number, unit: string, isk = false) {
  const sign = value > 0 ? "+" : "";
  const formatted = isk ? iskFormatter.format(value) : numberFormatter.format(Math.round(value));
  return `${sign}${formatted} ${unit}`;
}

function formatLoss(value: number, unit: string, isk = false) {
  const formatted = isk ? iskFormatter.format(Math.abs(value)) : numberFormatter.format(Math.round(Math.abs(value)));
  return `-${formatted} ${unit}`;
}