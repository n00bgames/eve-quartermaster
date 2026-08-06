import { ArrowDownRight, ArrowUpRight, TrendingUp, WalletCards } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { iskFormatter } from "../../lib/market";
import type { CorporationWalletAnalytics, FinancialAnalytics, PersonalWalletAnalytics, WalletPoint, WalletStatistics } from "../../types/financialAnalytics";
import "./financialDashboard.css";

type View = { key: string; kind: "personal"; row: PersonalWalletAnalytics } | { key: string; kind: "corporation"; row: CorporationWalletAnalytics };

const signedIsk = (value: number) => `${value > 0 ? "+" : ""}${iskFormatter.format(value)} ISK`;
const percent = (value?: number | null) => value == null ? "Baseline needed" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;

export function FinancialDashboard({ data, canManageCorporations, onToggleCorporationTotals }: {
  data: FinancialAnalytics;
  canManageCorporations: boolean;
  onToggleCorporationTotals: (corporationId: number, visible: boolean) => Promise<void>;
}) {
  const views = useMemo<View[]>(() => [
    ...data.personal.map((row) => ({ key: `personal-${row.character_id}`, kind: "personal" as const, row })),
    ...data.corporations.map((row) => ({ key: `corporation-${row.corporation_id}`, kind: "corporation" as const, row })),
  ], [data]);
  const [selectedKey, setSelectedKey] = useState(views[0]?.key ?? "");
  useEffect(() => { if (!views.some((view) => view.key === selectedKey)) setSelectedKey(views[0]?.key ?? ""); }, [views, selectedKey]);
  const selected = views.find((view) => view.key === selectedKey) ?? views[0];

  return <section className="financial-dashboard" aria-labelledby="financial-dashboard-title">
    <div className="section-heading">
      <div><h3 id="financial-dashboard-title"><WalletCards size={22} /> Financial Analytics</h3><p>Historical wallet movement, growth, spending velocity, and the events behind major changes.</p></div>
      {views.length > 0 && <select aria-label="Financial analytics scope" value={selected?.key ?? ""} onChange={(event) => setSelectedKey(event.target.value)}>{data.personal.length > 0 && <optgroup label="My characters">{data.personal.map((row) => <option key={row.character_id} value={`personal-${row.character_id}`}>{row.character_name}</option>)}</optgroup>}{data.corporations.length > 0 && <optgroup label="Corporations">{data.corporations.map((row) => <option key={row.corporation_id} value={`corporation-${row.corporation_id}`}>{row.corporation_name}</option>)}</optgroup>}</select>}
    </div>
    <div className="privacy-placard">{data.privacy.message}</div>
    {!selected && <p className="empty">No wallet history is available yet. Run Character Sync after linking the character-wallet ESI scope.</p>}
    {selected?.kind === "personal" && <PersonalFinancialView row={selected.row} />}
    {selected?.kind === "corporation" && <CorporationFinancialView row={selected.row} canManage={canManageCorporations} onToggle={onToggleCorporationTotals} />}
  </section>;
}

function FinancialKpis({ stats, currentLabel = "Current wallet", currentHidden = false, extra }: { stats: WalletStatistics; currentLabel?: string; currentHidden?: boolean; extra?: ReactNode }) {
  const cards = [
    [currentLabel, currentHidden || stats.current == null ? "Hidden" : `${iskFormatter.format(stats.current)} ISK`],
    ["Net change", signedIsk(stats.net_change)],
    ["Growth", percent(stats.percentage_growth)],
    ["Average / day", signedIsk(stats.average_daily_growth)],
    ["Largest gain", signedIsk(stats.largest_gain)],
    ["Largest loss", signedIsk(stats.largest_loss)],
  ];
  return <div className="financial-kpi-grid">{cards.map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}{extra}</div>;
}

function PersonalFinancialView({ row }: { row: PersonalWalletAnalytics }) {
  return <div className="financial-view">
    <div className="financial-scope-heading"><div><strong>{row.character_name}</strong><span>{row.corporation_name ?? "No corporation"} · Wallet synced {row.wallet_synced_at ? new Date(row.wallet_synced_at).toLocaleString() : "never"}</span></div></div>
    <FinancialKpis stats={row.stats} extra={<><article><span>Income</span><strong className="positive">{signedIsk(row.stats.income ?? 0)}</strong></article><article><span>Spending</span><strong className="negative">-{iskFormatter.format(row.stats.spending ?? 0)} ISK</strong></article></>} />
    <div className="financial-content-grid"><WalletLineChart points={row.points} title={`${row.character_name} wallet history`} /><article className="financial-timeline"><h4>Financial Timeline</h4><p>Largest wallet journal events in the selected period.</p><div>{row.timeline.map((event) => <div className="financial-event" key={event.id}>{event.amount >= 0 ? <ArrowUpRight className="positive" size={18} /> : <ArrowDownRight className="negative" size={18} />}<span><strong>{event.label}</strong><small>{event.occurred_at ? new Date(event.occurred_at).toLocaleString() : "Unknown time"}{event.description ? ` · ${event.description}` : ""}</small></span><b className={event.amount >= 0 ? "positive" : "negative"}>{signedIsk(event.amount)}</b></div>)}{row.timeline.length === 0 && <p className="empty">No notable wallet journal events have been collected yet.</p>}</div></article></div>
  </div>;
}

function CorporationFinancialView({ row, canManage, onToggle }: { row: CorporationWalletAnalytics; canManage: boolean; onToggle: (corporationId: number, visible: boolean) => Promise<void> }) {
  return <div className="financial-view">
    <div className="financial-scope-heading"><div><strong>{row.corporation_name}{row.ticker ? ` [${row.ticker}]` : ""}</strong><span>{row.tracked_characters.toLocaleString()} opted-in character{row.tracked_characters === 1 ? "" : "s"} + {row.corporation_wallet_divisions.toLocaleString()} corporation wallet division{row.corporation_wallet_divisions === 1 ? "" : "s"} · {row.series_mode === "absolute" ? "absolute totals permitted" : "trend-only privacy mode"}</span></div>{canManage && <label className="check"><input type="checkbox" checked={row.raw_totals_visible} onChange={(event) => void onToggle(row.corporation_id, event.target.checked)} /> Show corporation wallet totals to authorized officers</label>}</div>
    {!row.raw_totals_visible && <div className="privacy-placard">Raw combined wealth, corporation wallet divisions, and opted-in pilot totals are hidden. The graph is rebased to zero and shows only corporation-level movement.</div>}
    <FinancialKpis stats={row.stats} currentLabel="Combined wealth" currentHidden={!row.raw_totals_visible} extra={<><article><span>Corporation wallets</span><strong>{row.corporation_wallet_total == null ? "Hidden" : `${iskFormatter.format(row.corporation_wallet_total)} ISK`}</strong></article><article><span>Opted-in pilot wallets</span><strong>{row.character_wallet_total == null ? "Hidden" : `${iskFormatter.format(row.character_wallet_total)} ISK`}</strong></article><article><span>Median opted-in wallet</span><strong>{row.stats.median == null ? "Hidden" : `${iskFormatter.format(row.stats.median)} ISK`}</strong></article><article><span>Average opted-in wallet</span><strong>{row.stats.average == null ? "Hidden" : `${iskFormatter.format(row.stats.average)} ISK`}</strong></article></>} />
    <WalletLineChart points={row.points} title={`${row.corporation_name} ${row.series_mode === "absolute" ? "tracked wallet total" : "wallet movement"}`} changeMode={row.series_mode === "change"} />
  </div>;
}

function WalletLineChart({ points, title, changeMode = false }: { points: WalletPoint[]; title: string; changeMode?: boolean }) {
  if (points.length === 0) return <article className="financial-chart"><h4>{title}</h4><p className="empty">A second wallet snapshot is needed to establish a trend.</p></article>;
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = min === max ? Math.max(Math.abs(max) * 0.02, 1) : (max - min) * 0.08;
  const low = min - padding;
  const high = max + padding;
  const x = (index: number) => points.length === 1 ? 500 : 28 + index / (points.length - 1) * 944;
  const y = (value: number) => 202 - (value - low) / Math.max(high - low, 1) * 180;
  const coordinates = points.map((point, index) => `${x(index)},${y(point.value)}`).join(" ");
  return <article className="financial-chart"><h4><TrendingUp size={18} /> {title}</h4><p>{changeMode ? "Change from first observation" : "Daily closing balance"} · {points.length} day{points.length === 1 ? "" : "s"}</p><svg viewBox="0 0 1000 225" role="img" aria-label={title}><line x1="28" y1="22" x2="972" y2="22" /><line x1="28" y1="112" x2="972" y2="112" /><line x1="28" y1="202" x2="972" y2="202" /><polyline points={coordinates} /><g>{points.map((point, index) => <circle key={point.date} cx={x(index)} cy={y(point.value)} r="5"><title>{new Date(`${point.date}T00:00:00Z`).toLocaleDateString()} · {signedIsk(point.value)}</title></circle>)}</g></svg><div className="financial-chart-axis"><span>{new Date(`${points[0].date}T00:00:00Z`).toLocaleDateString()}</span><b>{changeMode ? signedIsk(points[points.length - 1].value) : `${iskFormatter.format(points[points.length - 1].value)} ISK`}</b><span>{new Date(`${points[points.length - 1].date}T00:00:00Z`).toLocaleDateString()}</span></div></article>;
}
