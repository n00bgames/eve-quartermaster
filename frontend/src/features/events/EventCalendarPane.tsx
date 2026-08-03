import { ChevronLeft, ChevronRight } from "lucide-react";

import { formatTimeOnly } from "../../lib/time";
import type { EventSummary } from "../../types/events";

function monthCells(month: Date): Date[] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = new Date(first);
  start.setDate(first.getDate() - first.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    return date;
  });
}

function sameDay(value: string, date: Date, timeZone: string): boolean {
  const formatter = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone });
  return formatter.format(new Date(value)) === formatter.format(date);
}

export function EventCalendarPane({
  events,
  month,
  timeZone,
  onMonthChange,
  onSelect,
}: {
  events: EventSummary[];
  month: Date;
  timeZone: string;
  onMonthChange: (date: Date) => void;
  onSelect: (event: EventSummary) => void;
}) {
  const cells = monthCells(month);
  const today = new Date();
  const monthLabel = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(month);

  return (
    <section className="panel event-calendar-panel">
      <div className="event-pane-heading">
        <div><span className="eyebrow">Calendar</span><h3>{monthLabel}</h3></div>
        <div className="event-icon-actions">
          <button type="button" aria-label="Previous month" onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft size={18} /></button>
          <button type="button" onClick={() => onMonthChange(new Date(today.getFullYear(), today.getMonth(), 1))}>Today</button>
          <button type="button" aria-label="Next month" onClick={() => onMonthChange(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight size={18} /></button>
        </div>
      </div>
      <div className="event-calendar-weekdays">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <span key={day}>{day}</span>)}</div>
      <div className="event-calendar-grid">
        {cells.map((date) => {
          const dayEvents = events.filter((event) => sameDay(event.formup_at || event.start_at, date, timeZone));
          const muted = date.getMonth() !== month.getMonth();
          const isToday = date.toDateString() === today.toDateString();
          return (
            <div key={date.toISOString()} className={`event-calendar-day${muted ? " muted-day" : ""}${isToday ? " today" : ""}`}>
              <span className="event-day-number">{date.getDate()}</span>
              <div className="event-calendar-items">
                {dayEvents.slice(0, 4).map((event) => (
                  <button type="button" key={event.id} className={`event-calendar-item event-type-${event.event_type}`} onClick={() => onSelect(event)}>
                    <time>{formatTimeOnly(event.formup_at || event.start_at, timeZone)}</time>
                    <strong>{event.title}</strong>
                  </button>
                ))}
                {dayEvents.length > 4 && <small>+{dayEvents.length - 4} more</small>}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
