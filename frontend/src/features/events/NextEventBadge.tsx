import { CalendarClock, MapPin, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";

import { formatCountdown, formatDateTime, formatEveTime } from "../../lib/time";
import type { EventSummary } from "../../types/events";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export function NextEventBadge({ api, onOpen }: { api: ApiClient; onOpen: (eventId: number) => void }) {
  const [event, setEvent] = useState<EventSummary | null>(null);
  const [, setTick] = useState(0);

  useEffect(() => {
    let active = true;
    const load = () => void api<EventSummary | null>("/events/next").then((row) => { if (active) setEvent(row); }).catch(() => undefined);
    load();
    const refresh = window.setInterval(load, 60000);
    const tick = window.setInterval(() => setTick((value) => value + 1), 30000);
    return () => { active = false; window.clearInterval(refresh); window.clearInterval(tick); };
  }, [api]);

  if (!event) return null;
  const time = event.formup_at || event.start_at;
  const location = event.formup_location;
  const systemName = location?.system_name || "Formup pending";
  const locationName = location?.location_name_snapshot || location?.location_name;
  const registrations = Object.values(event.registration_counts).reduce((total, count) => total + count, 0);
  const detailsId = `next-event-details-${event.id}`;

  return (
    <div className="next-event-shell">
      <button
        type="button"
        className="next-event-badge"
        aria-describedby={detailsId}
        onClick={() => onOpen(event.id)}
      >
        <CalendarClock className="next-event-icon" size={18} />
        <span className="next-event-copy">
          <small>Next event · {formatCountdown(time)}</small>
          <strong title={event.title}>{event.title}</strong>
        </span>
        <span className="next-event-location" title={systemName}>
          <MapPin size={15} />
          <span>{systemName}</span>
        </span>
      </button>

      <aside id={detailsId} role="tooltip" className="next-event-popover">
        <span className="eyebrow">Next event · {formatCountdown(time)}</span>
        <strong className="next-event-popover-title">{event.title}</strong>
        <div className="next-event-popover-facts">
          <div>
            <CalendarClock size={17} />
            <span><small>Formup</small><b>{formatDateTime(time)}</b><em>{formatEveTime(time)}</em></span>
          </div>
          <div>
            <MapPin size={17} />
            <span><small>Location</small><b>{systemName}</b>{locationName && <em>{locationName}</em>}</span>
          </div>
          <div>
            <UsersRound size={17} />
            <span><small>Registered</small><b>{registrations}</b><em>{event.event_type}</em></span>
          </div>
        </div>
        <small className="next-event-popover-hint">Click to open the full event briefing.</small>
      </aside>
    </div>
  );
}
