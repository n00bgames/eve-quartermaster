import { ArrowLeft, BarChart3, CalendarDays, CheckCircle2, UserRoundCheck, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { EventAnalytics } from "../../types/events";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export function EventAnalyticsPane({ api, onBack }: { api: ApiClient; onBack: () => void }) {
  const [days, setDays] = useState(30);
  const [bucket, setBucket] = useState<"day" | "week" | "month">("day");
  const [data, setData] = useState<EventAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const to = new Date();
    const from = new Date(to.getTime() - days * 86400000);
    setData(null); setError(null);
    void api<EventAnalytics>(`/events/analytics?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}&bucket=${bucket}`)
      .then(setData).catch((err) => setError(err instanceof Error ? err.message : "Unable to load event analytics"));
  }, [days, bucket]);

  const maxEvents = useMemo(() => Math.max(1, ...(data?.by_event_type.map((row) => row.event_count) ?? [1])), [data]);

  return <div className="event-analytics-shell">
    <section className="panel">
      <div className="event-pane-heading"><div><span className="eyebrow">Lightweight reporting</span><h3>Event Analytics</h3></div><div className="event-analytics-controls"><select value={days} onChange={(event) => setDays(Number(event.target.value))}>{[7, 30, 90, 365].map((value) => <option key={value} value={value}>{value} days</option>)}</select><select value={bucket} onChange={(event) => setBucket(event.target.value as "day" | "week" | "month")}><option value="day">Daily</option><option value="week">Weekly</option><option value="month">Monthly</option></select><button type="button" className="event-secondary-button" onClick={onBack}><ArrowLeft size={17} /> Events</button></div></div>
      {error && <div className="mini-alert">{error}</div>}
      {!data ? !error && <p className="muted">Calculating event activity…</p> : <>
        <div className="event-analytics-metrics">
          <article><CalendarDays size={21} /><span>Events</span><strong>{data.totals.event_count}</strong></article>
          <article><Users size={21} /><span>Going RSVPs</span><strong>{data.totals.rsvp_going}</strong></article>
          <article><UserRoundCheck size={21} /><span>Registered characters</span><strong>{data.totals.registered_characters}</strong></article>
          <article><CheckCircle2 size={21} /><span>Actual attendance</span><strong>{data.totals.attended_registered + data.totals.attended_unregistered}</strong></article>
          <article><BarChart3 size={21} /><span>Registration attendance</span><strong>{data.totals.attendance_rate.percent == null ? "N/A" : `${data.totals.attendance_rate.percent}%`}</strong><small>{data.totals.attendance_rate.numerator} of {data.totals.attendance_rate.denominator}</small></article>
        </div>
        <div className="event-analytics-columns">
          <section><h4>Events by type</h4><div className="event-bar-list">{data.by_event_type.length === 0 ? <p className="muted">No events in this period.</p> : data.by_event_type.map((row) => <article key={row.event_type}><span>{row.event_type}</span><div><i style={{ width: `${row.event_count / maxEvents * 100}%` }} /></div><b>{row.event_count}</b></article>)}</div></section>
          <section><h4>Registration versus attendance</h4><dl className="event-analytics-breakdown"><div><dt>Registered</dt><dd>{data.totals.registered_characters}</dd></div><div><dt>Attended (registered)</dt><dd>{data.totals.attended_registered}</dd></div><div><dt>Walk-ins / public</dt><dd>{data.totals.attended_unregistered}</dd></div><div><dt>No-show</dt><dd>{data.totals.no_show}</dd></div><div><dt>Excused</dt><dd>{data.totals.excused}</dd></div><div><dt>Unmarked</dt><dd>{data.totals.unmarked}</dd></div></dl></section>
        </div>
        <section className="event-trend-panel"><h4>Activity over time</h4><div className="event-trend-chart">{data.series.length === 0 ? <p className="muted">No activity to chart.</p> : data.series.map((row) => { const max = Math.max(1, ...data.series.map((item) => Math.max(item.registered_characters, item.attended_registered + item.attended_unregistered))); return <article key={row.period_start}><div><i className="registered" style={{ height: `${row.registered_characters / max * 100}%` }} /><i className="attended" style={{ height: `${(row.attended_registered + row.attended_unregistered) / max * 100}%` }} /></div><span>{new Date(row.period_start).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span></article>; })}</div><div className="event-chart-legend"><span><i className="registered" /> Registered</span><span><i className="attended" /> Attended</span></div></section>
      </>}
    </section>
  </div>;
}
