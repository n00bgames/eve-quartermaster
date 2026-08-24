import { ArrowDownRight, ArrowUpRight, TrendingUp, WalletCards } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { TimeSeriesChart } from "../../components/TimeSeriesChart";
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

  return <section id="analytics-financial" className="financial-dashboard analytics-category-anchor" aria-labelledby="financial-dashboard-title">
    <div className="section-heading">
      <div><h3 id="financial-dashboard-title"><WalletCards size={22} /> Financial Analytics</h3><p>Historical wallet movement, growth, spending velocity, and the events behind major changes.</p></div>
      {views.length > 0 && <select aria-label="Financial analytics scope" value={selected?.key ?? ""} onChange={(event) => setSelectedKey(event.target.value)}>{data.personal.length > 0 && <optgroup label="My characters">{data.personal.map((row) => <option key={row.character_id} value={`personal-${row.character_id}`}>{row.character_name}</option>)}</optgroup>}{data.corporations.length > 0 && <optgroup label="Corporations">{data.corporations.map((row) => <option key={row.corporation_id} value={`corporation-${row.corporation_id}`}>{row.corporation_name}</option>)}</optgroup>}</select>}
    </div>
    <div className="privacy-placard">{data.privacy.message}</div>
    {!selected && <p className="empty">No wallet history is available yet. Run Character Sync after linking the character-wallet ESI scope.</p>}
    {selected?.kind === "personal" && <PersonalFinancialView row={selected.row} days={data.days} />}
    {selected?.kind === "corporation" && <CorporationFinancialView row={selected.row} days={data.days} canManage={canManageCorporations} onToggle={onToggleCorporationTotals} />}
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

function PersonalFinancialView({ row, days }: { row: PersonalWalletAnalytics; days: number }) {
  return <div className="financial-view">
    <div className="financial-scope-heading"><div><strong>{row.character_name}</strong><span>{row.corporation_name ?? "No corporation"} · Wallet synced {row.wallet_synced_at ? new Date(row.wallet_synced_at).toLocaleString() : "never"}</span></div></div>
    <FinancialKpis stats={row.stats} extra={<><article><span>Income</span><strong className="positive">{signedIsk(row.stats.income ?? 0)}</strong></article><article><span>Spending</span><strong className="negative">-{iskFormatter.format(row.stats.spending ?? 0)} ISK</strong></article></>} />
    <div className="financial-content-grid"><WalletLineChart points={row.points} title={`${row.character_name} wallet history`} days={days} /><article className="financial-timeline"><h4>Financial Timeline</h4><p>Largest wallet journal events in the selected period.</p><div>{row.timeline.map((event) => <div className="financial-event" key={event.id}>{event.amount >= 0 ? <ArrowUpRight className="positive" size={18} /> : <ArrowDownRight className="negative" size={18} />}<span><strong>{event.label}</strong><small>{event.occurred_at ? new Date(event.occurred_at).toLocaleString() : "Unknown time"}{event.description ? ` · ${event.description}` : ""}</small></span><b className={event.amount >= 0 ? "positive" : "negative"}>{signedIsk(event.amount)}</b></div>)}{row.timeline.length === 0 && <p className="empty">No notable wallet journal events have been collected yet.</p>}</div></article></div>
  </div>;
}

function CorporationFinancialView({ row, days, canManage, onToggle }: { row: CorporationWalletAnalytics; days: number; canManage: boolean; onToggle: (corporationId: number, visible: boolean) => Promise<void> }) {
  return <div className="financial-view">
    <div className="financial-scope-heading"><div><strong>{row.corporation_name}{row.ticker ? ` [${row.ticker}]` : ""}</strong><span>{row.tracked_characters.toLocaleString()} opted-in character{row.tracked_characters === 1 ? "" : "s"} + {row.corporation_wallet_divisions.toLocaleString()} corporation wallet division{row.corporation_wallet_divisions === 1 ? "" : "s"} · {row.series_mode === "absolute" ? "absolute totals permitted" : "trend-only privacy mode"}</span></div>{canManage && <label className="check"><input type="checkbox" checked={row.raw_totals_visible} onChange={(event) => void onToggle(row.corporation_id, event.target.checked)} /> Show corporation wallet totals to authorized officers</label>}</div>
    {!row.raw_totals_visible && <div className="privacy-placard">Raw combined wealth, corporation wallet divisions, and opted-in pilot totals are hidden. The graph is rebased to zero and shows only corporation-level movement.</div>}
    <FinancialKpis stats={row.stats} currentLabel="Combined wealth" currentHidden={!row.raw_totals_visible} extra={<><article><span>Corporation wallets</span><strong>{row.corporation_wallet_total == null ? "Hidden" : `${iskFormatter.format(row.corporation_wallet_total)} ISK`}</strong></article><article><span>Opted-in pilot wallets</span><strong>{row.character_wallet_total == null ? "Hidden" : `${iskFormatter.format(row.character_wallet_total)} ISK`}</strong></article><article><span>Median opted-in wallet</span><strong>{row.stats.median == null ? "Hidden" : `${iskFormatter.format(row.stats.median)} ISK`}</strong></article><article><span>Average opted-in wallet</span><strong>{row.stats.average == null ? "Hidden" : `${iskFormatter.format(row.stats.average)} ISK`}</strong></article></>} />
    <WalletLineChart points={row.points} title={`${row.corporation_name} ${row.series_mode === "absolute" ? "tracked wallet total" : "wallet movement"}`} days={days} changeMode={row.series_mode === "change"} />
  </div>;
}

function WalletLineChart({ points, title, days, changeMode = false }: { points: WalletPoint[]; title: string; days: number; changeMode?: boolean }) {
  if (points.length === 0) return <article className="financial-chart"><h4>{title}</h4><p className="empty">A second wallet snapshot is needed to establish a trend.</p></article>;
  const latest = points[points.length - 1];
  return <article className="financial-chart"><h4><TrendingUp size={18} /> {title}</h4><p>{changeMode ? "Change from first observation" : "Daily closing balance"} · {points.length} day{points.length === 1 ? "" : "s"}</p><TimeSeriesChart ariaLabel={title} selectedDays={days} includeZero={changeMode} series={[{ key: "wallet", name: title, color: "#55c7d8", points }]} formatValue={(value) => changeMode ? signedIsk(value) : `${iskFormatter.format(value)} ISK`} /><div className="financial-chart-latest"><span>Latest</span><b>{changeMode ? signedIsk(latest.value) : `${iskFormatter.format(latest.value)} ISK`}</b></div></article>;
}
