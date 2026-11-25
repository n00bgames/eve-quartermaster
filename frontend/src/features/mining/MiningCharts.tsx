import type { MiningHourlyAnalytics, MiningRollupRow } from "../../types/mining";

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

export function MiningTimeline({ rows, hourly, selectedDay, onDayClick, onBack, loading = false }: {
  rows: MiningRollupRow[];
  hourly?: MiningHourlyAnalytics;
  selectedDay?: string | null;
  onDayClick?: (day: string) => void;
  onBack?: () => void;
  loading?: boolean;
}) {
  const displayed = selectedDay ? hourly?.by_hour ?? [] : rows.slice(-31);
  const maximum = Math.max(1, ...displayed.map((row) => row.gross_volume));
  return <article className="mining-chart mining-timeline-chart" aria-label="Mining activity timeline" aria-busy={loading}>
    <header><div><h4>{selectedDay ? `Hourly activity · ${selectedDay}` : "Yield over time"}</h4><span>{selectedDay ? "Imported ledger record times · UTC" : "Select a day to view its hours and analytics · UTC dates"}</span></div>{selectedDay && onBack && <div className="button-row compact"><button type="button" disabled={loading} onClick={onBack}>Back to date range</button></div>}</header>
    <div className="mining-timeline" aria-label={selectedDay ? "Hourly ledger record volume in UTC" : "Daily mining volume"}>
      {displayed.map((row) => {
        const recoveredHeight = row.volume / maximum * 100;
        const residueHeight = row.residue_volume / maximum * 100;
        const title = `${row.name}${selectedDay ? " UTC" : ""}: ${decimal.format(row.volume)} m3 recovered, ${decimal.format(row.residue_volume)} m3 residue`;
        const content = <><span className="mining-timeline-stack"><span className="residue" style={{ height: `${residueHeight}%`, minHeight: row.residue_volume > 0 ? "1px" : "0" }} /><span className="recovered" style={{ height: `${recoveredHeight}%`, minHeight: row.volume > 0 ? "1px" : "0" }} /></span><small>{selectedDay ? row.name : row.name.slice(5)}</small></>;
        return !selectedDay && onDayClick ? <button type="button" className="mining-timeline-column mining-timeline-day" key={String(row.id)} title={title} aria-label={`View hourly mining for ${row.name}`} disabled={loading} onClick={() => onDayClick(row.name)}>{content}</button>
          : <div className="mining-timeline-column" key={String(row.id)} title={title}>{content}</div>;
      })}
      {displayed.length === 0 && <p className="empty">{selectedDay ? "Hourly record times are unavailable for this selection." : "No historical yield to graph yet."}</p>}
    </div>
    {selectedDay && <div className="mining-hourly-note"><p>ESI provides daily totals. Bars group imported ledger totals by their recorded timestamps, rather than measuring mining rates. Empty hours do not establish zero mining.</p>{hourly && hourly.untimed_rows > 0 && <p><strong>Hour not recorded:</strong> {decimal.format(hourly.untimed.volume)} m3 recovered · {decimal.format(hourly.untimed.residue_volume)} m3 residue across {hourly.untimed_rows} rows. Included in all of this day’s analytics.</p>}</div>}
  </article>;
}
