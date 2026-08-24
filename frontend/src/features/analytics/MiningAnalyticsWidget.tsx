import { Gauge, Pickaxe } from "lucide-react";

import type { MiningAnalytics } from "../../types/analytics";

const number = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });

export function MiningAnalyticsWidget({ summary, days }: { summary: MiningAnalytics; days: number }) {
  const maxVolume = Math.max(1, ...summary.top_by_volume.map((row) => row.volume));
  return <>
    <article id="analytics-mining" className="analytics-widget mining-analytics-widget analytics-category-anchor">
      <header><Pickaxe size={18} /><div><h4>Mining Output</h4><small>{days}-day persistent ledger</small></div></header>
      <div className="manufacturing-kpi-grid">
        <div><span>Recovered</span><strong>{number.format(summary.recovered_volume)} m3</strong></div>
        <div><span>Gross extraction</span><strong>{number.format(summary.gross_volume)} m3</strong></div>
        <div><span>Residue loss</span><strong>{number.format(summary.residue_volume)} m3</strong></div>
        <div><span>Net value</span><strong>{number.format(summary.net_value)} ISK</strong></div>
      </div>
      <div className="widget-list">{summary.top_by_volume.map((row) => <div className="widget-row" key={row.name}><span>{row.name}</span><strong>{number.format(row.volume)} m3</strong><i style={{ width: `${Math.max(4, row.volume / maxVolume * 100)}%` }} /></div>)}{summary.top_by_volume.length === 0 && <p className="empty">Sync or import a mining ledger to begin mining analytics.</p>}</div>
    </article>
    <article className="analytics-widget mining-analytics-widget">
      <header><Gauge size={18} /><div><h4>Mining Efficiency</h4><small>Only residue-measured rows are ranked</small></div></header>
      <div className="manufacturing-kpi-grid"><div><span>Measured fleet efficiency</span><strong>{summary.efficiency == null ? "Not reported" : `${summary.efficiency}%`}</strong></div><div><span>Measured volume</span><strong>{number.format(summary.measured_volume)} m3</strong></div></div>
      <div className="widget-list">{summary.top_by_efficiency.map((row) => <div className="widget-row" key={row.name}><span>{row.name}</span><strong>{row.efficiency}%</strong><i style={{ width: `${Math.max(4, row.efficiency)}%` }} /></div>)}{summary.top_by_efficiency.length === 0 && <p className="empty">Detailed residue data is required for honest efficiency rankings.</p>}</div>
    </article>
  </>;
}
