import type { MiningRollupRow } from "../../types/mining";

const compact = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });
const decimal = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

type BarChartProps = {
  title: string;
  subtitle: string;
  rows: MiningRollupRow[];
  value: (row: MiningRollupRow) => number;
  format?: (value: number) => string;
  limit?: number;
  className?: string;
};

export function MiningBarChart({ title, subtitle, rows, value, format = compact.format, limit = 10, className = "" }: BarChartProps) {
  const selected = rows.slice(0, limit);
  const maximum = Math.max(1, ...selected.map(value));
  return <article className={`mining-chart ${className}`}>
    <header><h4>{title}</h4><span>{subtitle}</span></header>
    <div className="mining-bars">
      {selected.map((row) => <div className="mining-bar-row" key={String(row.id)}>
        <div><strong>{row.name}</strong><span>{format(value(row))}</span></div>
        <div className="mining-bar-track"><span style={{ width: `${Math.max(1, value(row) / maximum * 100)}%` }} /></div>
      </div>)}
      {selected.length === 0 && <p className="empty">No ledger history in this selection.</p>}
    </div>
  </article>;
}

export function MiningEfficiencyRanking({ rows }: { rows: MiningRollupRow[] }) {
  const ranked = rows.filter((row) => row.efficiency != null).sort((left, right) => (right.efficiency ?? 0) - (left.efficiency ?? 0));
  return <MiningBarChart
    title="Most efficient miners"
    subtitle="Recovered volume divided by measured gross extraction"
    rows={ranked}
    value={(row) => row.efficiency ?? 0}
    format={(value) => `${decimal.format(value)}%`}
  />;
}

export function MiningTimeline({ rows }: { rows: MiningRollupRow[] }) {
  const maximum = Math.max(1, ...rows.map((row) => row.gross_volume));
  return <article className="mining-chart mining-timeline-chart">
    <header><h4>Yield over time</h4><span>Recovered volume with residue loss shown separately</span></header>
    <div className="mining-timeline">
      {rows.slice(-31).map((row) => {
        const recoveredHeight = row.volume / maximum * 100;
        const residueHeight = row.residue_volume / maximum * 100;
        return <div className="mining-timeline-column" key={String(row.id)} title={`${row.name}: ${decimal.format(row.volume)} m3 recovered, ${decimal.format(row.residue_volume)} m3 residue`}>
          <div className="mining-timeline-stack"><span className="residue" style={{ height: `${residueHeight}%` }} /><span className="recovered" style={{ height: `${recoveredHeight}%` }} /></div>
          <small>{row.name.slice(5)}</small>
        </div>;
      })}
      {rows.length === 0 && <p className="empty">No historical yield to graph yet.</p>}
    </div>
  </article>;
}
