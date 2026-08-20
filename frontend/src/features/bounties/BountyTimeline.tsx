import { useMemo, useState, type PointerEvent } from "react";

import type { BountyTimelinePoint } from "../../types/bountyAnalytics";

const WIDTH = 1000;
const HEIGHT = 300;
const LEFT = 82;
const RIGHT = 980;
const TOP = 20;
const BOTTOM = 242;

const compact = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });

export function BountyTimeline({ points, timeZone, formatDateTime }: { points: BountyTimelinePoint[]; timeZone: string; formatDateTime: (value: string) => string }) {
  const rows = useMemo(() => points.map((point) => ({ ...point, time: Date.parse(point.bucket_start) })).filter((point) => Number.isFinite(point.time)), [points]);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  if (!rows.length) return <p className="empty">No bounty ticks match this range.</p>;
  const minTime = Math.min(...rows.map((row) => row.time));
  const maxTime = Math.max(...rows.map((row) => row.time));
  const maxValue = Math.max(1, ...rows.flatMap((row) => [row.net_isk, row.known_gross_isk, row.known_corporate_tax_isk]));
  const high = maxValue * 1.1;
  const x = (value: number) => minTime === maxTime ? (LEFT + RIGHT) / 2 : LEFT + (value - minTime) / (maxTime - minTime) * (RIGHT - LEFT);
  const y = (value: number) => BOTTOM - value / high * (BOTTOM - TOP);
  const ticks = Array.from({ length: Math.min(5, rows.length) }, (_, index) => minTime + (maxTime - minTime) * index / Math.max(1, Math.min(5, rows.length) - 1));
  const lines = [
    { key: "net", label: "Net bounty", color: "#55c4da", value: (row: BountyTimelinePoint) => row.net_isk },
    { key: "gross", label: "Known gross", color: "#efbf4a", value: (row: BountyTimelinePoint) => row.known_gross_isk },
    { key: "tax", label: "Known corporate tax", color: "#ef7b62", value: (row: BountyTimelinePoint) => row.known_corporate_tax_isk },
  ];

  function move(event: PointerEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const viewX = (event.clientX - bounds.left) / Math.max(bounds.width, 1) * WIDTH;
    const target = minTime + Math.max(0, Math.min(1, (viewX - LEFT) / (RIGHT - LEFT))) * (maxTime - minTime);
    let nearest = 0;
    rows.forEach((row, index) => { if (Math.abs(row.time - target) < Math.abs(rows[nearest].time - target)) nearest = index; });
    setHoverIndex(nearest);
  }

  const hover = hoverIndex == null ? null : rows[hoverIndex];
  return <div className="bounty-chart-shell">
    <div className="bounty-chart-legend">{lines.map((line) => <span key={line.key}><i style={{ background: line.color }} />{line.label}</span>)}</div>
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Bounty income, gross bounty, and corporate tax over time" onPointerMove={move} onPointerLeave={() => setHoverIndex(null)}>
      {[0, high / 2, high].map((value) => <g key={value}><line className="bounty-grid-line" x1={LEFT} x2={RIGHT} y1={y(value)} y2={y(value)} /><text x={LEFT - 12} y={y(value) + 5} textAnchor="end">{compact.format(value)}</text></g>)}
      {ticks.map((value) => <text key={value} x={x(value)} y={BOTTOM + 30} textAnchor="middle">{new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: rows.length < 60 ? "numeric" : undefined, timeZone }).format(value)}</text>)}
      {lines.map((line) => <g key={line.key}>
        {rows.length > 1 && <polyline points={rows.map((row) => `${x(row.time)},${y(line.value(row))}`).join(" ")} fill="none" stroke={line.color} strokeWidth="3" />}
        {rows.map((row, index) => <circle key={`${line.key}-${row.bucket_start}`} cx={x(row.time)} cy={y(line.value(row))} r={index === hoverIndex ? 6 : 3.5} fill={line.color} />)}
      </g>)}
      {hover && <line className="bounty-crosshair" x1={x(hover.time)} x2={x(hover.time)} y1={TOP} y2={BOTTOM} />}
    </svg>
    {hover && <div className="bounty-chart-tooltip" style={{ left: `${x(hover.time) / WIDTH * 100}%` }} role="status"><strong>{formatDateTime(hover.bucket_start)}</strong><span>Net <b>{compact.format(hover.net_isk)} ISK</b></span><span>Known gross <b>{compact.format(hover.known_gross_isk)} ISK</b></span><span>Known tax <b>{compact.format(hover.known_corporate_tax_isk)} ISK</b></span><small>{hover.tick_count} tick{hover.tick_count === 1 ? "" : "s"}{hover.tax_unknown_ticks ? ` · ${hover.tax_unknown_ticks} tax unknown` : ""}</small></div>}
  </div>;
}

