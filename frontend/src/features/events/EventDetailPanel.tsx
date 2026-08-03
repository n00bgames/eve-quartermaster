import { ArrowLeft, CalendarClock, CheckCircle2, ExternalLink, Headphones, Lock, MapPin, Pencil, Route, ShieldCheck, Users } from "lucide-react";
import { useState } from "react";

import { formatDateTime, formatEveTime } from "../../lib/time";
import type { EventDetail } from "../../types/events";
import { EventRegistrationPanel } from "./EventRegistrationPanel";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export function EventDetailPanel({
  api,
  event,
  timeZone,
  onBack,
  onEdit,
  onOpenComposition,
  onOpenAttendance,
  onRefresh,
}: {
  api: ApiClient;
  event: EventDetail;
  timeZone: string;
  onBack: () => void;
  onEdit: () => void;
  onOpenComposition: () => void;
  onOpenAttendance: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formup = event.locations.find((location) => location.location_role === "formup");
  const destination = event.locations.find((location) => location.location_role === "destination");

  async function transition(lifecycle?: string, registration?: string) {
    setBusy(true); setError(null);
    try {
      await api(`/events/${event.id}/transition`, { method: "POST", body: JSON.stringify({ lifecycle_status: lifecycle || null, registration_status: registration || null }) });
      await onRefresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to update event"); }
    finally { setBusy(false); }
  }

  return (
    <div className="event-detail-shell">
      <section className="panel event-detail-hero">
        <div className="event-detail-actions">
          <button type="button" className="event-secondary-button" onClick={onBack}><ArrowLeft size={17} /> All events</button>
          <span className={`event-lifecycle event-lifecycle-${event.lifecycle_status}`}>{event.lifecycle_status.replace(/_/g, " ")}</span>
          <span className={`event-rsvp-chip event-rsvp-${event.registration_status}`}><Lock size={13} /> {event.registration_status}</span>
        </div>
        <div className="event-detail-title">
          <div className={`event-type-mark large event-type-${event.event_type}`}><span>{event.event_type.slice(0, 3).toUpperCase()}</span></div>
          <div><span className="eyebrow">{event.event_type} operation</span><h3>{event.title}</h3><p>{event.operational_area || "Operational area not specified"}</p></div>
          {event.permissions.can_manage && <button type="button" onClick={onEdit}><Pencil size={17} /> Edit</button>}
        </div>
        {error && <div className="mini-alert">{error}</div>}
        <div className="event-detail-facts">
          <div><CalendarClock size={19} /><span><small>Formup · local</small><strong>{formatDateTime(event.formup_at || event.start_at, timeZone)}</strong><em>{formatEveTime(event.formup_at || event.start_at)}</em></span></div>
          <div><MapPin size={19} /><span><small>Formup</small><strong>{formup?.system_name || "Pending"}</strong><em>{formup?.location_name || "System formup"}</em></span></div>
          <div><Route size={19} /><span><small>Destination</small><strong>{destination?.system_name || "Not specified"}</strong><em>{destination?.location_name || event.route_notes || "No route notes"}</em></span></div>
          <div><ShieldCheck size={19} /><span><small>Doctrine</small><strong>{event.doctrine.name || event.doctrine_mode}</strong><em>{event.doctrine_mode}</em></span></div>
          <div><Users size={19} /><span><small>Lead</small><strong>{event.lead.name || "Unassigned"}</strong><em>{event.created_by.name ? `Created by ${event.created_by.name}` : ""}</em></span></div>
          <div><Headphones size={19} /><span><small>Voice</small><strong>{event.discord_voice_label || "Not specified"}</strong>{event.discord_voice_url && <a href={event.discord_voice_url} target="_blank" rel="noreferrer">Open voice <ExternalLink size={13} /></a>}</span></div>
        </div>
        {(event.instructions || event.doctrine_notes || event.related_url) && <div className="event-briefing">
          {event.instructions && <div><h4>Instructions</h4><p>{event.instructions}</p></div>}
          {event.doctrine_notes && <div><h4>Doctrine notes</h4><p>{event.doctrine_notes}</p></div>}
          {event.related_url && <a href={event.related_url} target="_blank" rel="noreferrer">Open related resource <ExternalLink size={14} /></a>}
        </div>}
        <div className="event-detail-toolbar">
          {event.permissions.can_view_composition && <button type="button" className="event-secondary-button" onClick={onOpenComposition}><Users size={17} /> Fleet composition</button>}
          {event.permissions.can_record_attendance && <button type="button" className="event-secondary-button" onClick={onOpenAttendance}><CheckCircle2 size={17} /> Record attendance</button>}
          {event.permissions.can_manage && event.lifecycle_status === "draft" && <button disabled={busy} type="button" onClick={() => void transition("scheduled")}>Publish event</button>}
          {event.permissions.can_manage && event.lifecycle_status === "scheduled" && <button disabled={busy} type="button" onClick={() => void transition("in_progress")}>Mark in progress</button>}
          {event.permissions.can_manage && ["scheduled", "in_progress"].includes(event.lifecycle_status) && <button disabled={busy} type="button" onClick={() => void transition("completed")}>Complete event</button>}
          {event.permissions.can_manage && ["draft", "scheduled", "in_progress"].includes(event.lifecycle_status) && <button disabled={busy} type="button" className="event-danger-button" onClick={() => window.confirm("Cancel this event?") && void transition("cancelled")}>Cancel event</button>}
          {event.permissions.can_manage && event.registration_status !== "open" && !["completed", "cancelled"].includes(event.lifecycle_status) && <button disabled={busy} type="button" onClick={() => void transition(undefined, "open")}>Open registration</button>}
          {event.permissions.can_manage && event.registration_status === "open" && <button disabled={busy} type="button" onClick={() => void transition(undefined, "closed")}>Close registration</button>}
          {event.permissions.can_manage && event.registration_status !== "locked" && <button disabled={busy} type="button" onClick={() => void transition(undefined, "locked")}>Lock roster</button>}
        </div>
      </section>
      <div className="event-detail-columns">
        <section className="panel"><EventRegistrationPanel api={api} event={event} onChanged={onRefresh} /></section>
        <section className="panel event-requirements-panel">
          <div className="event-pane-heading"><div><span className="eyebrow">Fleet needs</span><h3>Composition Plan</h3></div></div>
          {event.role_requirements.length === 0 && event.doctrine_requirements.length === 0 ? <p className="muted">No requested roles or doctrine buckets have been defined.</p> : <>
            {event.role_requirements.map((role) => <article key={`role:${role.id ?? role.sort_order}`}><span><strong>{role.custom_label || role.role_key.replace(/_/g, " ")}</strong><small>{role.notes || "Requested fleet role"}</small></span><b>{role.requested_quantity}</b></article>)}
            {event.doctrine_requirements.map((requirement) => <article key={`doctrine:${requirement.id ?? requirement.sort_order}`}><span><strong>{requirement.label}</strong><small>{requirement.options.map((option) => option.ship_name || option.manual_name_snapshot).filter(Boolean).join(" · ") || "Accepted hulls pending"}</small></span><b>{requirement.requested_quantity}</b></article>)}
          </>}
        </section>
      </div>
    </div>
  );
}
