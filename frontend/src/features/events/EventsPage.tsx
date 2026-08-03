import { BarChart3, CalendarDays, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { EventDetail, EventMeta, EventSummary } from "../../types/events";
import { EventAnalyticsPane } from "./EventAnalyticsPane";
import { EventAttendancePanel } from "./EventAttendancePanel";
import { EventCalendarPane } from "./EventCalendarPane";
import { EventDetailPanel } from "./EventDetailPanel";
import { EventEditor } from "./EventEditor";
import { FleetCompositionPanel } from "./FleetCompositionPanel";
import { UpcomingEventsPane } from "./UpcomingEventsPane";
import "./events.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type CurrentUser = { id: number; role: string; timezone?: string | null };

type EventRoute =
  | { view: "board" }
  | { view: "new" }
  | { view: "analytics" }
  | { view: "detail" | "edit" | "composition" | "attendance"; eventId: number };

function parseRoute(hash: string): EventRoute {
  const path = hash.replace(/^#/, "").split("?")[0].replace(/\/$/, "");
  if (path === "events/new") return { view: "new" };
  if (path === "events/analytics") return { view: "analytics" };
  const match = path.match(/^events\/(\d+)(?:\/(edit|composition|attendance))?$/);
  if (match) return { view: (match[2] || "detail") as "detail" | "edit" | "composition" | "attendance", eventId: Number(match[1]) };
  return { view: "board" };
}

export function EventsPage({ api, currentUser }: { api: ApiClient; currentUser: CurrentUser }) {
  const [hash, setHash] = useState(window.location.hash);
  const [meta, setMeta] = useState<EventMeta | null>(null);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [month, setMonth] = useState(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [typeFilter, setTypeFilter] = useState("all");
  const [lifecycleFilter, setLifecycleFilter] = useState("active");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const route = parseRoute(hash);
  const timeZone = currentUser.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

  const navigate = useCallback((path: string) => {
    const next = `#${path}`;
    if (window.location.hash === next) setHash(next);
    else window.location.hash = path;
  }, []);

  const loadBoard = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const from = new Date(month.getFullYear(), month.getMonth(), -7).toISOString();
      const to = new Date(month.getFullYear(), month.getMonth() + 2, 7).toISOString();
      setEvents(await api<EventSummary[]>(`/events?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=500`));
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load events"); }
    finally { setBusy(false); }
  }, [api, month]);

  const loadDetail = useCallback(async (eventId: number) => {
    setBusy(true); setError(null);
    try { setDetail(await api<EventDetail>(`/events/${eventId}`)); }
    catch (err) { setDetail(null); setError(err instanceof Error ? err.message : "Unable to load event"); }
    finally { setBusy(false); }
  }, [api]);

  useEffect(() => {
    const sync = () => setHash(window.location.hash);
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  useEffect(() => { void api<EventMeta>("/events/meta").then(setMeta).catch((err) => setError(err instanceof Error ? err.message : "Unable to load Events access")); }, [api]);
  useEffect(() => { if (route.view === "board") void loadBoard(); }, [route.view, month]);
  useEffect(() => { if ("eventId" in route) void loadDetail(route.eventId); else setDetail(null); }, [hash]);

  const filteredEvents = useMemo(() => events.filter((event) => {
    if (typeFilter !== "all" && event.event_type !== typeFilter) return false;
    if (lifecycleFilter === "active" && ["cancelled", "completed"].includes(event.lifecycle_status)) return false;
    if (lifecycleFilter !== "all" && lifecycleFilter !== "active" && event.lifecycle_status !== lifecycleFilter) return false;
    return true;
  }), [events, typeFilter, lifecycleFilter]);

  if (!meta) return <section className="panel"><p className="muted">Loading Calendar and Events…</p>{error && <div className="mini-alert">{error}</div>}</section>;
  if ("eventId" in route && detail?.id !== route.eventId) return <section className="panel">{error ? <div className="mini-alert">{error}</div> : <p className="muted">Loading event…</p>}</section>;

  if (route.view === "analytics") return <EventAnalyticsPane api={api} onBack={() => navigate("events")} />;
  if (route.view === "new") return meta.permissions.can_create ? <EventEditor api={api} meta={meta} onCancel={() => navigate("events")} onSaved={(saved) => navigate(`events/${saved.id}`)} /> : <section className="panel"><div className="mini-alert">Officer access is required to create events.</div></section>;
  if (route.view === "edit" && detail) return <EventEditor api={api} meta={meta} detail={detail} onCancel={() => navigate(`events/${detail.id}`)} onSaved={(saved) => { setDetail(saved); navigate(`events/${saved.id}`); }} />;
  if (route.view === "composition" && detail) return <FleetCompositionPanel api={api} event={detail} onBack={() => navigate(`events/${detail.id}`)} />;
  if (route.view === "attendance" && detail) return <EventAttendancePanel api={api} event={detail} onBack={() => navigate(`events/${detail.id}`)} />;
  if (route.view === "detail" && detail) return <EventDetailPanel api={api} event={detail} timeZone={timeZone} onBack={() => navigate("events")} onEdit={() => navigate(`events/${detail.id}/edit`)} onOpenComposition={() => navigate(`events/${detail.id}/composition`)} onOpenAttendance={() => navigate(`events/${detail.id}/attendance`)} onRefresh={() => loadDetail(detail.id)} />;
  if (route.view !== "board") return <section className="panel">{error ? <div className="mini-alert">{error}</div> : <p className="muted">Loading event…</p>}</section>;

  return <div className="events-page">
    <div className="event-board-toolbar">
      <div className="event-filter-row"><label><span>Type</span><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">All event types</option>{meta.constants.event_types.map((value) => <option key={value} value={value}>{value.replace(/_/g, " ")}</option>)}</select></label><label><span>Status</span><select value={lifecycleFilter} onChange={(event) => setLifecycleFilter(event.target.value)}><option value="active">Active</option><option value="all">All states</option>{meta.constants.lifecycle_statuses.map((value) => <option key={value} value={value}>{value.replace(/_/g, " ")}</option>)}</select></label></div>
      <div className="event-board-actions">{meta.permissions.can_view_analytics && <button type="button" className="event-secondary-button" onClick={() => navigate("events/analytics")}><BarChart3 size={17} /> Analytics</button>}<button type="button" className="event-secondary-button" onClick={() => void loadBoard()}><RefreshCw className={busy ? "spin" : ""} size={17} /> Refresh</button>{meta.permissions.can_create && <button type="button" onClick={() => navigate("events/new")}><Plus size={17} /> Create event</button>}</div>
    </div>
    {error && <div className="mini-alert">{error}</div>}
    <div className="event-board-layout">
      <EventCalendarPane events={filteredEvents} month={month} timeZone={timeZone} onMonthChange={setMonth} onSelect={(event) => navigate(`events/${event.id}`)} />
      <UpcomingEventsPane events={filteredEvents} timeZone={timeZone} onSelect={(event) => navigate(`events/${event.id}`)} />
    </div>
    <div className="event-board-placard"><CalendarDays size={18} /><span><strong>Times are shown twice where it matters.</strong> Calendar cards use your profile timezone; detail views also show UTC as EVE time.</span></div>
  </div>;
}
