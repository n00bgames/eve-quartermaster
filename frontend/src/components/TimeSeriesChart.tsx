import { useMemo, useState, type PointerEvent } from "react";

import { adaptiveDateTicks, chartDomain, compactChartValue } from "../lib/chartScale";

import "./timeSeriesChart.css";

export type TimeSeriesPoint = { date: string; value: number };
export type TimeSeries = { key: string; name: string; color: string; points: TimeSeriesPoint[] };

type DatedPoint = TimeSeriesPoint & { time: number };
type DatedSeries = Omit<TimeSeries, "points"> & { points: DatedPoint[] };

const WIDTH = 1000;
const HEIGHT = 280;
const LEFT = 92;
const RIGHT = 976;
const TOP = 18;
const BOTTOM = 228;

export function TimeSeriesChart({ series, ariaLabel, selectedDays, includeZero = false, formatValue, formatAxisValue = compactChartValue }: {
  series: TimeSeries[];
  ariaLabel: string;
  selectedDays?: number;
  includeZero?: boolean;
  formatValue: (value: number) => string;
  formatAxisValue?: (value: number) => string;
}) {
  const datedSeries = useMemo<DatedSeries[]>(() => series.map((item) => ({
    ...item,
    points: item.points
      .map((point) => ({ ...point, time: Date.parse(`${point.date.slice(0, 10)}T00:00:00Z`) }))
      .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.value))
      .sort((left, right) => left.time - right.time),
  })).filter((item) => item.points.length > 0), [series]);
  const allPoints = datedSeries.flatMap((item) => item.points);
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  if (allPoints.length === 0) return <p className="empty">No chartable observations yet.</p>;

  const minTime = Math.min(...allPoints.map((point) => point.time));
  const maxTime = Math.max(...allPoints.map((point) => point.time));
  const domain = chartDomain(allPoints.map((point) => point.value), includeZero);
  const xFor = (time: number) => minTime === maxTime ? (LEFT + RIGHT) / 2 : LEFT + (time - minTime) / (maxTime - minTime) * (RIGHT - LEFT);
  const yFor = (value: number) => BOTTOM - (value - domain.low) / Math.max(domain.high - domain.low, 1) * (BOTTOM - TOP);
  const dateTicks = adaptiveDateTicks(minTime, maxTime, selectedDays);
  const exactHoverRows = hoverTime == null ? [] : datedSeries.flatMap((item) => {
    const point = item.points.find((candidate) => candidate.time === hoverTime);
    return point ? [{ ...item, point }] : [];
  });
  const hoverX = hoverTime == null ? null : xFor(hoverTime);
  const hoverY = exactHoverRows.length === 1 ? yFor(exactHoverRows[0].point.value) : null;

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const viewX = (event.clientX - bounds.left) / Math.max(bounds.width, 1) * WIDTH;
    const targetTime = minTime + Math.max(0, Math.min(1, (viewX - LEFT) / (RIGHT - LEFT))) * (maxTime - minTime);
    const nearest = allPoints.reduce((best, point) => Math.abs(point.time - targetTime) < Math.abs(best.time - targetTime) ? point : best);
    setHoverTime(nearest.time);
  }

  return <div className="time-series-chart-shell">
    <svg className="time-series-chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={ariaLabel} onPointerMove={handlePointerMove} onPointerLeave={() => setHoverTime(null)}>
      {domain.ticks.map((tick) => <g key={`y-${tick}`}><line className="time-series-grid" x1={LEFT} y1={yFor(tick)} x2={RIGHT} y2={yFor(tick)} /><text className="time-series-y-label" x={LEFT - 12} y={yFor(tick) + 4} textAnchor="end">{formatAxisValue(tick)}</text></g>)}
      {dateTicks.map((tick) => <g key={`x-${tick.time}`}><line className="time-series-date-mark" x1={xFor(tick.time)} y1={TOP} x2={xFor(tick.time)} y2={BOTTOM} /><text className="time-series-x-label" x={xFor(tick.time)} y={BOTTOM + 28} textAnchor="middle">{tick.label}</text></g>)}
      {datedSeries.map((item) => <g key={item.key}>
        {item.points.length > 1 && <polyline className="time-series-line" points={item.points.map((point) => `${xFor(point.time)},${yFor(point.value)}`).join(" ")} stroke={item.color} />}
        {item.points.map((point) => <circle key={`${item.key}-${point.time}`} className={point.time === hoverTime ? "time-series-point active" : "time-series-point"} cx={xFor(point.time)} cy={yFor(point.value)} r={point.time === hoverTime ? 6 : 4} fill={item.color}><title>{item.name} · {new Date(point.time).toLocaleDateString()} · {formatValue(point.value)}</title></circle>)}
      </g>)}
      {hoverX != null && <line className="time-series-crosshair" x1={hoverX} y1={TOP} x2={hoverX} y2={BOTTOM} />}
      {hoverY != null && <line className="time-series-crosshair horizontal" x1={LEFT} y1={hoverY} x2={RIGHT} y2={hoverY} />}
    </svg>
    {hoverTime != null && <div className={`time-series-tooltip ${hoverX != null && hoverX > WIDTH * 0.72 ? "align-right" : ""}`} style={{ left: `${(hoverX ?? LEFT) / WIDTH * 100}%` }} role="status" aria-live="polite"><strong>{new Date(hoverTime).toLocaleDateString(undefined, { dateStyle: "medium", timeZone: "UTC" })}</strong>{exactHoverRows.map((item) => <span key={item.key}><i style={{ backgroundColor: item.color }} />{item.name}<b>{formatValue(item.point.value)}</b></span>)}</div>}
  </div>;
}
