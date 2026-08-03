import { CalendarClock, MapPin, ShieldCheck, Users } from "lucide-react";

import { formatCountdown, formatDateTime, formatEveTime } from "../../lib/time";
import type { EventSummary } from "../../types/events";

export function UpcomingEventsPane({
  events,
  timeZone,
  onSelect,
}: {
  events: EventSummary[];
  timeZone: string;
  onSelect: (event: EventSummary) => void;
}) {
  const upcoming = events
    .filter((event) => !["cancelled", "completed"].includes(event.lifecycle_status))
    .sort((a, b) => new Date(a.formup_at || a.start_at).getTime() - new Date(b.formup_at || b.start_at).getTime());

  return (
    <section className="panel event-upcoming-panel">
      <div className="event-pane-heading"><div><span className="eyebrow">Operations board</span><h3>Upcoming Events</h3></div><span className="event-count-chip">{upcoming.length}</span></div>
      {upcoming.length === 0 ? <div className="event-empty"><CalendarClock size={30} /><strong>No scheduled operations</strong><span>New events will appear here once published.</span></div> : (
        <div className="event-upcoming-list">
          {upcoming.map((event) => (
            <button type="button" key={event.id} className="event-upcoming-card" onClick={() => onSelect(event)}>
              <div className={`event-type-mark event-type-${event.event_type}`}><span>{event.event_type.slice(0, 3).toUpperCase()}</span></div>
              <div className="event-upcoming-main">
                <span className="event-card-kicker"><CalendarClock size={14} /> {formatCountdown(event.formup_at || event.start_at)}</span>
                <strong>{event.title}</strong>
                <small>{formatDateTime(event.formup_at || event.start_at, timeZone)} · {formatEveTime(event.formup_at || event.start_at)}</small>
              </div>
              <div className="event-upcoming-facts">
                <span><MapPin size={15} /> {event.formup_location?.system_name ?? event.operational_area ?? "Formup pending"}</span>
                <span><ShieldCheck size={15} /> {event.doctrine.name ?? event.doctrine_mode}</span>
                <span><Users size={15} /> {event.registration_counts.registered ?? 0} registered</span>
              </div>
              <span className={`event-rsvp-chip event-rsvp-${event.my_registrations.length > 0 ? "going" : event.my_rsvp?.status ?? "none"}`}>{event.my_registrations.length > 0 ? `${event.my_registrations.length} pilot${event.my_registrations.length === 1 ? "" : "s"} RSVP'd` : event.my_rsvp ? `Account: ${event.my_rsvp.status}` : "Open to RSVP"}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
