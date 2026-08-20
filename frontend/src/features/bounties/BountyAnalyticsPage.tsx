import { Coins, Download, RefreshCw, ShieldCheck, TrendingUp, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { BountyAnalyticsPayload } from "../../types/bountyAnalytics";
import { BountyTimeline } from "./BountyTimeline";
import "./bountyAnalytics.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type Grouping = "tick" | "hourly" | "daily";

const isk = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 2 });
const exactIsk = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

function money(value: number | null) { return value == null ? "Unknown" : `${isk.format(value)} ISK`; }

export function BountyAnalyticsPage({ api, timeZone, formatDateTime }: { api: ApiClient; timeZone: string; formatDateTime: (value: string) => string }) {
  const [data, setData] = useState<BountyAnalyticsPayload | null>(null);
  const [period, setPeriod] = useState("7d");
  const [grouping, setGrouping] = useState<Grouping>("daily");
  const [characterId, setCharacterId] = useState("");
  const [corporationId, setCorporationId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [taxStatus, setTaxStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  function params(nextPage = page) {
    const query = new URLSearchParams({ period, grouping, page: String(nextPage), page_size: "100", tax_status: taxStatus });
    if (characterId) query.set("character_eve_id", characterId);
    if (corporationId) query.set("corporation_eve_id", corporationId);
    if (dateFrom) query.set("date_from", dateFrom);
    if (dateTo) query.set("date_to", dateTo);
    return query;
  }

  async function load(nextPage = page) {
    setLoading(true); setError(null);
    try { setData(await api<BountyAnalyticsPayload>(`/bounty-analytics?${params(nextPage)}`)); setPage(nextPage); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load bounty analytics"); }
    finally { setLoading(false); }
  }

  async function exportCsv() {
    setError(null); setMessage(null);
    try {
      const result = await api<{ filename: string; csv: string; row_count: number }>(`/bounty-analytics/export?${params(1)}`);
      const blob = new Blob([result.csv], { type: "text/csv;charset=utf-8" });
      const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = result.filename; link.click(); URL.revokeObjectURL(link.href);
      setMessage(`Exported ${result.row_count.toLocaleString()} traceable bounty ticks.`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Bounty export failed"); }
  }

  useEffect(() => { void load(1); }, [period, grouping, characterId, corporationId, taxStatus]);

  const summary = data?.summary;
  const pageCount = Math.max(1, Math.ceil((data?.tick_count ?? 0) / (data?.page_size ?? 100)));
  const authorizationWarnings = data?.characters.filter((row) => row.authorization_status !== "authorized") ?? [];
  const rangeLabel = dateFrom || dateTo ? "Custom dates" : period === "all" ? "All retained" : period.toUpperCase();
  const taxCoverage = summary ? `${summary.tax_known_ticks.toLocaleString()} of ${summary.tick_count.toLocaleString()} ticks have authoritative tax` : "";
  const sortedLeaderboard = useMemo(() => data?.leaderboard ?? [], [data?.leaderboard]);

  return <section className="panel stacked bounty-analytics-page">
    <div className="section-heading"><div><h3>Bounty Analytics</h3><p>Persistent NPC bounty ticks, pilot comparisons, and authoritative corporation-tax reconciliation from character wallet journals.</p></div><div className="button-row compact"><button type="button" disabled={loading} onClick={() => void exportCsv()}><Download size={16} />Export CSV</button><button type="button" disabled={loading} onClick={() => void load()}><RefreshCw size={16} />Refresh</button></div></div>
    <div className="bounty-privacy-note"><ShieldCheck size={19} /><div><strong>Private, account-scoped analytics</strong><span>This module includes only wallet-visible characters connected to your account. Administrators cannot use it to inspect another account's bounty income. Corporation filters use the corporation preserved with each historical journal row.</span></div></div>
    <div className="bounty-definition-note"><Coins size={19} /><div><strong>What EQM calls a tick</strong><span>{data?.definitions.tick ?? "One authoritative NPC bounty payout cycle from ESI wallet history."} ESS transfers, missions, bonuses, loot sales, and other income are excluded.</span></div></div>
    {loading && <div className="analytics-loading-placard" role="status"><TrendingUp className="spin" size={22} /><div><strong>Bounty analytics loading.</strong><span>Reading retained wallet-journal history. Do not refresh the page.</span></div></div>}
    {message && <div className="notice inline">{message}</div>}{error && <div className="mini-alert">{error}</div>}
    {authorizationWarnings.length > 0 && <div className="mini-alert neutral"><strong>{authorizationWarnings.length} pilot{authorizationWarnings.length === 1 ? " has" : "s have"} unavailable wallet authorization.</strong> Retained history remains visible, but new ticks will not arrive until the token and wallet scope are restored.</div>}

    <div className="bounty-period-row"><div className="button-row compact">{["1d", "7d", "30d", "90d", "all"].map((value) => <button type="button" key={value} className={period === value && !dateFrom && !dateTo ? "active" : ""} onClick={() => { setDateFrom(""); setDateTo(""); setPeriod(value); setPage(1); }}>{value === "all" ? "All retained" : value.toUpperCase()}</button>)}</div><span>{rangeLabel} · times shown in {timeZone}</span></div>
    <div className="bounty-filter-grid">
      <label>View<select value={corporationId} onChange={(event) => { setCorporationId(event.target.value); setCharacterId(""); }}><option value="">All my pilots</option>{data?.corporations.map((row) => <option key={row.corporation_eve_id} value={row.corporation_eve_id}>{row.corporation_name}</option>)}</select></label>
      <label>Pilot<select value={characterId} onChange={(event) => setCharacterId(event.target.value)}><option value="">All pilots in view</option>{data?.characters.filter((row) => !corporationId || String(row.corporation_eve_id) === corporationId).map((row) => <option key={row.character_eve_id} value={row.character_eve_id}>{row.character_name}{row.authorization_status === "authorized" ? "" : ` · ${row.authorization_status.replace("_", " ")}`}</option>)}</select></label>
      <label>Chart grouping<select value={grouping} onChange={(event) => setGrouping(event.target.value as Grouping)}><option value="tick">Each tick</option><option value="hourly">Hourly</option><option value="daily">Daily</option></select></label>
      <label>Tax evidence<select value={taxStatus} onChange={(event) => setTaxStatus(event.target.value)}><option value="all">Known and unknown</option><option value="known">Authoritative tax only</option><option value="unknown">Tax unknown only</option></select></label>
      <label>From<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
      <label>To<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label>
      <button type="button" onClick={() => void load(1)}>Apply dates</button>
    </div>

    <div className="status-grid bounty-summary-grid">
      <article><span>Total earned · net</span><strong>{money(summary?.net_isk ?? 0)}</strong><small>Original wallet movement</small></article>
      <article><span>Gross bounty</span><strong>{money(summary?.gross_isk ?? null)}</strong><small>{summary?.tax_coverage_complete ? "Net + authoritative tax" : `Known gross ${money(summary?.known_gross_isk ?? 0)}`}</small></article>
      <article className="tax-card"><span>Corporate tax</span><strong>{money(summary?.corporate_tax_isk ?? null)}</strong><small>{summary?.tax_coverage_complete ? `${summary.effective_tax_rate?.toFixed(2) ?? "0.00"}% effective rate` : `${money(summary?.known_corporate_tax_isk ?? 0)} known · ${taxCoverage}`}</small><button type="button" onClick={() => setTaxStatus("known")}>Drill into taxed ticks</button></article>
      <article><span>Average tick · net</span><strong>{money(summary?.average_tick_isk ?? 0)}</strong><small>{summary?.tick_count.toLocaleString() ?? 0} ticks</small></article>
      <article><span>Highest tick · net</span><strong>{money(summary?.highest_tick_isk ?? null)}</strong><small>{summary?.highest_tick_pilot ?? "No payout yet"}</small></article>
      <article><span>Most recent tick</span><strong>{summary?.most_recent_at ? formatDateTime(summary.most_recent_at) : "None"}</strong></article>
      <article><Users size={18} /><span>Active pilots</span><strong>{summary?.active_pilots ?? 0}</strong></article>
    </div>

    <article className="bounty-chart-card"><div className="section-heading compact"><div><h4>Bounty income and corporate tax</h4><p>Net always reflects the source journal. Gross and tax lines include authoritative values only; missing tax is never estimated from a current corporation rate.</p></div></div>{data && <BountyTimeline points={data.timeline} timeZone={timeZone} formatDateTime={formatDateTime} />}</article>

    <article className="bounty-leaderboard"><div className="section-heading compact"><div><h4>Bounty leaderboard</h4><p>Click a pilot to drill into every contributing ledger entry. ISK/hour is intentionally omitted because ESI does not provide reliable session boundaries.</p></div></div><div className="table-wrap"><table><thead><tr><th>#</th><th>Pilot</th><th>Net bounty</th><th>Corporate tax</th><th>Gross bounty</th><th>Effective tax</th><th>Ticks</th><th>Average tick</th><th>Largest tick</th></tr></thead><tbody>{sortedLeaderboard.map((row) => <tr key={row.character_eve_id} onClick={() => { setCharacterId(String(row.character_eve_id)); setPage(1); }} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") setCharacterId(String(row.character_eve_id)); }}><td>{row.rank}</td><td><strong>{row.character_name}</strong><span>{row.corporation_name ?? "No corporation recorded"}</span></td><td>{money(row.net_isk)}</td><td>{row.corporate_tax_isk == null ? <span title={`${row.tax_unknown_ticks} ticks lack authoritative tax`}>Unknown</span> : money(row.corporate_tax_isk)}<small>{row.corporate_tax_isk == null ? `${money(row.known_corporate_tax_isk)} known` : ""}</small></td><td>{row.gross_isk == null ? "Unknown" : money(row.gross_isk)}</td><td>{row.effective_tax_rate == null ? "Unknown" : `${row.effective_tax_rate.toFixed(2)}%`}</td><td>{row.tick_count.toLocaleString()}</td><td>{money(row.average_tick_isk)}</td><td>{money(row.highest_tick_isk)}</td></tr>)}{data && !sortedLeaderboard.length && <tr><td colSpan={9}>No NPC bounty ticks match the current filters.</td></tr>}</tbody></table></div></article>

    <div className="section-heading compact"><div><h4>Traceable bounty ledger</h4><p>{(data?.tick_count ?? 0).toLocaleString()} ticks · page {page} of {pageCount}. Expand a row to see its ESI reference IDs and source details.</p></div><div className="button-row compact"><button type="button" disabled={page <= 1 || loading} onClick={() => void load(page - 1)}>Previous</button><button type="button" disabled={page >= pageCount || loading} onClick={() => void load(page + 1)}>Next</button></div></div>
    <div className="table-wrap bounty-ledger-table"><table><thead><tr><th>Timestamp</th><th>Pilot</th><th>Net bounty</th><th>Corporate tax</th><th>Gross bounty</th><th>Effective tax</th><th>Evidence</th></tr></thead><tbody>{data?.ledger.map((row) => <tr key={row.tick_id}><td>{formatDateTime(row.occurred_at)}</td><td><strong>{row.character_name}</strong><span>{row.corporation_name ?? "Corporation unknown"}</span></td><td>{exactIsk.format(row.net_isk)} ISK</td><td>{row.corporate_tax_isk == null ? <span className="unknown-value">Unknown</span> : `${exactIsk.format(row.corporate_tax_isk)} ISK`}</td><td>{row.gross_isk == null ? <span className="unknown-value">Unknown</span> : `${exactIsk.format(row.gross_isk)} ISK`}</td><td>{row.effective_tax_rate == null ? "Unknown" : `${row.effective_tax_rate.toFixed(2)}%`}</td><td><details><summary>{row.reference_ids.length} journal row{row.reference_ids.length === 1 ? "" : "s"}</summary><div><b>ESI reference IDs</b><code>{row.reference_ids.join(", ")}</code>{row.tax_receiver_names.length > 0 && <span>Tax receiver: {row.tax_receiver_names.join(", ")}</span>}{row.system_ids.length > 0 && <span>System IDs: {row.system_ids.join(", ")}</span>}{row.descriptions.map((description) => <span key={description}>{description}</span>)}</div></details></td></tr>)}{data && !data.ledger.length && <tr><td colSpan={7}>No ledger rows match the current filters.</td></tr>}</tbody></table></div>
  </section>;
}

