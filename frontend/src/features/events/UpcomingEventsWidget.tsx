import { CalendarClock, ChevronRight, MapPin } from "lucide-react";
import { useEffect, useState } from "react";

import { formatCountdown, formatDateTime } from "../../lib/time";
import type { EventSummary } from "../../types/events";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export function UpcomingEventsWidget({ api, timeZone, onOpen }: { api: ApiClient; timeZone: string; onOpen: (eventId?: number) => void }) {
  const [events, setEvents] = useState<EventSummary[]>([]);
  useEffect(() => {
    const from = new Date().toISOString();
    const to = new Date(Date.now() + 90 * 86400000).toISOString();
    void api<EventSummary[]>(`/events?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=10`).then((rows) => setEvents(rows.slice(0, 3))).catch(() => setEvents([]));
  }, [api]);
  return <section className="panel overview-events-widget"><div className="event-pane-heading"><div><span className="eyebrow">Community operations</span><h3>Upcoming Events</h3></div><button type="button" className="event-secondary-button" onClick={() => onOpen()}>Open calendar <ChevronRight size={16} /></button></div>{events.length === 0 ? <p className="muted">No scheduled events in the next 90 days.</p> : <div className="overview-event-list">{events.map((event) => <button type="button" key={event.id} onClick={() => onOpen(event.id)}><CalendarClock size={18} /><span><strong>{event.title}</strong><small>{formatDateTime(event.formup_at || event.start_at, timeZone)} · {formatCountdown(event.formup_at || event.start_at)}</small></span><em><MapPin size={13} /> {event.formup_location?.system_name || "Formup pending"}</em><span className={`event-rsvp-chip event-rsvp-${event.my_rsvp?.status ?? "none"}`}>{event.my_rsvp?.status ?? "No RSVP"}</span></button>)}</div>}</section>;
}
