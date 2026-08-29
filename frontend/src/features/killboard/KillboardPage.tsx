import { AlertTriangle, ExternalLink, RefreshCw, Settings2, Skull, Swords } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { KillboardAnalytics, KillboardContext, KillboardScope, KillboardSettings, KillboardSync, RankedKillboardValue } from "../../types/killboard";
import "./killboard.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

const activeStatuses = new Set(["queued", "running"]);

function isk(value?: number | null): string {
  if (value === null || value === undefined) return "Unknown";
  const absolute = Math.abs(value);
  const divisor = absolute >= 1e12 ? 1e12 : absolute >= 1e9 ? 1e9 : absolute >= 1e6 ? 1e6 : 1;
  const suffix = divisor === 1e12 ? "T" : divisor === 1e9 ? "B" : divisor === 1e6 ? "M" : "";
  return `${(value / divisor).toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix} ISK`;
}

function RankedList({ title, rows }: { title: string; rows: RankedKillboardValue[] }) {
  return <article className="killboard-card"><h3>{title}</h3>{rows.length ? <ol className="killboard-ranked">{rows.map((row) => <li key={row.name}><span>{row.name}</span><strong>{row.count.toLocaleString()}</strong></li>)}</ol> : <p className="empty">No matching activity yet.</p>}</article>;
}

function Timeline({ rows }: { rows: KillboardAnalytics["timeline"] }) {
  const max = Math.max(1, ...rows.map((row) => row.kills + row.losses));
  return <article className="killboard-card killboard-timeline"><h3>Violence over time</h3>{rows.length ? <div className="killboard-bars" role="img" aria-label="Daily kills and losses"><div className="killboard-bar-legend"><span className="kill-dot" />Kills <span className="loss-dot" />Losses</div>{rows.map((row) => <div className="killboard-bar-day" key={row.date} title={`${row.date}: ${row.kills} kills, ${row.losses} losses`}><div className="killboard-bar-stack"><i className="kills" style={{ height: `${Math.max(row.kills ? 6 : 0, row.kills / max * 100)}%` }} /><i className="losses" style={{ height: `${Math.max(row.losses ? 6 : 0, row.losses / max * 100)}%` }} /></div><small>{row.date.slice(5)}</small></div>)}</div> : <p className="empty">The ledger is suspiciously quiet.</p>}</article>;
}

export function KillboardPage({ api }: { api: ApiClient }) {
  const [context, setContext] = useState<KillboardContext | null>(null);
  const [analytics, setAnalytics] = useState<KillboardAnalytics | null>(null);
  const [scope, setScope] = useState<KillboardScope | null>(null);
  const [days, setDays] = useState(30);
  const [sync, setSync] = useState<KillboardSync | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<KillboardSettings | null>(null);

  async function loadContext(ensure = false) {
    const next = await api<KillboardContext>("/killboard/context");
    setContext(next); setSettings(next.settings); setSync(next.latest_sync);
    setScope((current) => current && next.scopes.some((item) => item.scope_type === current.scope_type && item.scope_id === current.scope_id) ? current : next.scopes[0] ?? null);
    if (ensure && next.enabled && (next.sync_due || (next.latest_sync && activeStatuses.has(next.latest_sync.status)))) {
      const ensured = await api<{ sync: KillboardSync }>("/killboard/sync/ensure", { method: "POST", body: "{}" });
      setSync(ensured.sync);
    }
  }

  async function loadAnalytics(selected = scope, period = days) {
    if (!selected) return;
    const query = new URLSearchParams({ scope_type: selected.scope_type, scope_id: String(selected.scope_id), days: String(period) });
    setAnalytics(await api<KillboardAnalytics>(`/killboard/analytics?${query}`));
  }

  useEffect(() => {
    setLoading(true); setError(null);
    void loadContext(true).catch((err) => setError(err instanceof Error ? err.message : "Killboard context failed")).finally(() => setLoading(false));
  }, []);

  useEffect(() => { if (scope) void loadAnalytics().catch((err) => setError(err instanceof Error ? err.message : "Killboard analytics failed")); }, [scope, days]);

  useEffect(() => {
    if (!sync || !activeStatuses.has(sync.status)) return;
    const timer = window.setInterval(() => {
      void api<KillboardSync>(`/killboard/sync/${sync.job_id}`).then((next) => {
        setSync(next);
        if (!activeStatuses.has(next.status)) void loadAnalytics();
      }).catch((err) => setError(err instanceof Error ? err.message : "Sync polling failed"));
    }, 2500);
    return () => window.clearInterval(timer);
  }, [sync?.job_id, sync?.status, scope, days]);

  async function startSync() {
    setError(null);
    try {
      setSync(await api<KillboardSync>("/killboard/sync", { method: "POST", body: JSON.stringify({ scope: "account", lookback_days: context?.settings.lookback_days }) }));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not start sync"); }
  }

  async function resumeSync() {
    if (!sync) return;
    try { setSync(await api<KillboardSync>(`/killboard/sync/${sync.job_id}/resume`, { method: "POST", body: "{}" })); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not resume sync"); }
  }

  async function saveSettings() {
    if (!settings) return;
    try {
      const saved = await api<KillboardSettings>("/killboard/settings", { method: "PATCH", body: JSON.stringify(settings) });
      setSettings(saved); setContext((value) => value ? { ...value, enabled: saved.enabled, settings: saved } : value); setSettingsOpen(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save settings"); }
  }

  const syncProgress = useMemo(() => sync?.target_count ? Math.min(100, Math.round(sync.target_index / sync.target_count * 100)) : 0, [sync]);
  if (loading && !context) return <section className="panel"><p>Opening EQM Violence Ledger…</p></section>;
  if (!context) return <section className="panel"><div className="alert">{error ?? "Killboard is unavailable."}</div></section>;

  return <div className="killboard-page">
    <section className="killboard-command panel">
      <div><span className="eyebrow">Canonical ESI records · zKill discovery</span><h2 style={{ fontSize: "clamp(1.45rem, 3cqi, 2rem)", lineHeight: 1.1 }}><Skull size={24} /> EQM Violence Ledger</h2><p>Ships converted into content, cached locally for useful historical analysis.</p></div>
      <div className="killboard-controls">
        <label>Scope<select value={scope ? `${scope.scope_type}:${scope.scope_id}` : ""} onChange={(event) => setScope(context.scopes.find((item) => `${item.scope_type}:${item.scope_id}` === event.target.value) ?? null)}>{context.scopes.map((item) => <option key={`${item.scope_type}:${item.scope_id}`} value={`${item.scope_type}:${item.scope_id}`}>{item.label}</option>)}</select></label>
        <div className="button-row">{[7, 30, 90].map((value) => <button key={value} type="button" className={days === value ? "active" : ""} onClick={() => setDays(value)}>{value}D</button>)}</div>
        <button type="button" onClick={() => void startSync()} disabled={!context.enabled || Boolean(sync && activeStatuses.has(sync.status))}><RefreshCw size={17} /> Sync now</button>
        {context.can_manage && <button type="button" className="secondary-action" onClick={() => setSettingsOpen((value) => !value)}><Settings2 size={17} /> Configure</button>}
      </div>
    </section>
    <div className="killboard-placard"><AlertTriangle size={18} /><span>{context.coverage_notice} Do not interpret discovery coverage as a complete combat record.{analytics?.engine_used ? ` Analytics: ${analytics.engine_used === "rust" ? "Rust" : analytics.engine_used.replace(/-/g, " ")}.` : ""}</span></div>
    {error && <div className="alert">{error}</div>}
    {settingsOpen && settings && <section className="panel killboard-settings"><h3>Killboard synchronization</h3><label><input type="checkbox" checked={settings.enabled} onChange={(event) => setSettings({ ...settings, enabled: event.target.checked })} /> Module enabled</label><label>Refresh period (hours)<input type="number" min="1" max="168" value={settings.sync_period_hours} onChange={(event) => setSettings({ ...settings, sync_period_hours: Number(event.target.value) })} /></label><label>Lookback (days)<input type="number" min="1" max="3650" value={settings.lookback_days} onChange={(event) => setSettings({ ...settings, lookback_days: Number(event.target.value) })} /></label><label>Delay between zKill requests (seconds)<input type="number" min="0.2" max="30" step="0.1" value={settings.request_delay_seconds} onChange={(event) => setSettings({ ...settings, request_delay_seconds: Number(event.target.value) })} /></label><label>Maximum pages per feed<input type="number" min="1" max="100" value={settings.max_pages} onChange={(event) => setSettings({ ...settings, max_pages: Number(event.target.value) })} /></label><button type="button" onClick={() => void saveSettings()}>Save settings</button></section>}
    {sync && <section className={`killboard-sync panel status-${sync.status}`}><div><strong>{activeStatuses.has(sync.status) ? "Sync in progress" : `Last sync: ${sync.status.replace(/_/g, " ")}`}</strong><span>{sync.message}</span>{sync.current_target && <span>{sync.current_target.owner_name} · {sync.feed} · page {sync.page}</span>}</div><div className="killboard-sync-counts"><span>{sync.imported_count} new</span><span>{sync.updated_count} refreshed</span><span>{sync.skipped_count} cached</span><span>{sync.failed_count} failed</span></div>{activeStatuses.has(sync.status) && <progress value={syncProgress} max="100" />}{sync.status === "failed" && <button type="button" onClick={() => void resumeSync()}>Resume from saved cursor</button>}</section>}
    {!context.enabled && <div className="alert">The Killboard module is disabled. An administrator can re-enable it in Configure.</div>}
    {analytics && <>
      <section className="killboard-kpis">
        <article><span>Kills</span><strong>{analytics.summary.kills.toLocaleString()}</strong><small>{analytics.summary.solo_kills} solo · {analytics.summary.fleet_kills} fleet</small></article>
        <article><span>Losses</span><strong>{analytics.summary.losses.toLocaleString()}</strong><small>{analytics.summary.inactivity_days ?? "—"} days since activity</small></article>
        <article><span>ISK destroyed</span><strong>{isk(analytics.summary.isk_destroyed)}</strong><small>zKill estimate</small></article>
        <article><span>ISK lost</span><strong>{isk(analytics.summary.isk_lost)}</strong><small>{analytics.coverage.unknown_value_records} unknown values</small></article>
        <article><span>Efficiency</span><strong>{analytics.summary.efficiency === null || analytics.summary.efficiency === undefined ? "—" : `${analytics.summary.efficiency.toFixed(1)}%`}</strong><small>Creative accounting included</small></article>
        <article><span>Final blows</span><strong>{analytics.summary.final_blows.toLocaleString()}</strong><small>{analytics.summary.damage_contribution_percent?.toFixed(1) ?? "—"}% damage contribution</small></article>
      </section>
      <Timeline rows={analytics.timeline} />
      <section className="killboard-grid"><RankedList title="Most-used hulls" rows={analytics.hulls.most_used} /><RankedList title="Ships converted into content" rows={analytics.hulls.most_killed} /><RankedList title="Most-lost hulls" rows={analytics.hulls.most_lost} /><RankedList title="Dangerous acquaintances" rows={analytics.opponents} /><RankedList title="Busy systems" rows={analytics.geography.systems} /><RankedList title="Regions" rows={analytics.geography.regions} /></section>
      <section className="killboard-grid two"><article className="killboard-card"><h3>Streaks</h3><p className="killboard-big">{analytics.streaks.current || 0} {analytics.streaks.current_kind ?? "activity"}</p><p>Longest kill streak: <strong>{analytics.streaks.longest_kill}</strong></p><p>Longest loss streak: <strong>{analytics.streaks.longest_loss}</strong></p></article><article className="killboard-card"><h3>Frequent wingmates</h3>{analytics.wingmates.length ? analytics.wingmates.map((row) => <p key={row.characters.join(":")}><strong>{row.characters.join(" + ")}</strong> · {row.shared_kills} shared kills</p>) : <p className="empty">No recurring character pairs in this scope.</p>}</article></section>
      <section className="killboard-card"><div className="section-heading"><h3><Swords size={18} /> Recent kills and losses</h3><span className="muted">{analytics.coverage.record_count} locally cached records in this view</span></div><div className="killboard-recent">{analytics.recent.map((row) => <a key={row.killmail_id} href={row.zkill_url} target="_blank" rel="noreferrer" className={`killmail-row ${row.result}`}><span className="killmail-result">{row.result.replace("_", " ")}</span><span><strong>{row.victim.ship_type_name}</strong><small>{row.victim.character_name ?? row.victim.corporation_name ?? "Unknown or NPC victim"}</small></span><span><strong>{row.system_name}</strong><small>{new Date(row.killmail_time).toLocaleString()}</small></span><span><strong>{isk(row.estimated_total_value)}</strong><small>{row.attacker_count} attacker{row.attacker_count === 1 ? "" : "s"}{row.solo ? " · solo" : ""}</small></span><ExternalLink size={16} /></a>)}{analytics.recent.length === 0 && <p className="empty">No discovered canonical killmails match this view yet.</p>}</div></section>
    </>}
  </div>;
}
