import { ArrowLeft, CheckCircle2, CircleDashed, ShieldCheck, Ship, Users } from "lucide-react";
import { useEffect, useState } from "react";

import type { EventComposition, EventDetail } from "../../types/events";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

function ProgressRows({ rows }: { rows: EventComposition["role_requirements"] }) {
  if (rows.length === 0) return <p className="muted">No requirements defined.</p>;
  return <div className="event-progress-list">{rows.map((row) => {
    const percent = Math.min(100, Math.round(row.registered / Math.max(1, row.requested) * 100));
    return <article key={row.id}><div><strong>{row.label}</strong><span>{row.registered} / {row.requested}{row.remaining > 0 ? ` · ${row.remaining} needed` : " · filled"}</span></div><div className="event-progress-track"><i style={{ width: `${percent}%` }} /></div></article>;
  })}</div>;
}

export function FleetCompositionPanel({ api, event, onBack }: { api: ApiClient; event: EventDetail; onBack: () => void }) {
  const [composition, setComposition] = useState<EventComposition | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setComposition(null); setError(null);
    void api<EventComposition>(`/events/${event.id}/composition`).then(setComposition).catch((err) => setError(err instanceof Error ? err.message : "Unable to load composition"));
  }, [event.id]);

  return <div className="event-composition-shell">
    <section className="panel">
      <div className="event-pane-heading"><div><span className="eyebrow">Fleet composition</span><h3>{event.title}</h3></div><button type="button" className="event-secondary-button" onClick={onBack}><ArrowLeft size={17} /> Event detail</button></div>
      {error && <div className="mini-alert">{error}</div>}
      {!composition ? !error && <p className="muted">Loading composition…</p> : <>
        <div className="event-composition-metrics">
          <article><Users size={20} /><span>Registered</span><strong>{composition.totals.registration.registered ?? 0}</strong></article>
          <article><CheckCircle2 size={20} /><span>Attended</span><strong>{composition.totals.attendance.attended ?? 0}</strong></article>
          <article><CircleDashed size={20} /><span>Unmarked</span><strong>{composition.totals.attendance.unmarked ?? 0}</strong></article>
          <article><Ship size={20} /><span>No character</span><strong>{composition.users_without_characters}</strong></article>
        </div>
        <div className="event-composition-columns">
          <section><h4><Users size={17} /> Requested roles</h4><ProgressRows rows={composition.role_requirements} /></section>
          <section><h4><ShieldCheck size={17} /> Doctrine buckets</h4><ProgressRows rows={composition.doctrine_requirements} /></section>
        </div>
        <div className="event-composition-columns compact">
          <section><h4>Roles</h4><div className="event-chip-cloud">{composition.roles.map((row) => <span key={row.label}>{row.label.replace(/_/g, " ")} <b>{row.count}</b></span>)}</div></section>
          <section><h4>Ships</h4><div className="event-chip-cloud">{composition.hulls.map((row) => <span key={row.label}>{row.label} <b>{row.count}</b></span>)}</div></section>
        </div>
      </>}
    </section>
    {composition?.identity_visible && <section className="panel">
      <div className="event-pane-heading"><div><span className="eyebrow">Roster detail</span><h3>Registered Characters</h3></div></div>
      <div className="table-wrap"><table className="event-composition-table"><thead><tr><th>Character</th><th>Account</th><th>Ship / fit</th><th>Role</th><th>Status</th><th>Attendance</th></tr></thead><tbody>
        {composition.registrations?.map((registration) => <tr key={registration.id}><td><span className="event-character-cell"><img src={`https://images.evetech.net/characters/${registration.character_eve_id}/portrait?size=64`} alt="" /><span><strong>{registration.character_name}</strong><small>{registration.corporation_name}</small></span></span></td><td>{registration.user_name || `User ${registration.user_id}`}</td><td>{registration.fitting_name || registration.ship_name || registration.freeform_ship_description || "Undecided"}</td><td>{registration.custom_role || registration.role_key?.replace(/_/g, " ") || "Unassigned"}</td><td>{registration.registration_status}<br /><small>{registration.confirmation_status}</small></td><td>{registration.attendance?.attendance_status || "unmarked"}</td></tr>)}
      </tbody></table></div>
      {(composition.unregistered_attendees?.length ?? 0) > 0 && <div className="event-walkin-list"><h4>Unregistered attendees</h4>{composition.unregistered_attendees?.map((entry) => <article key={entry.id}><strong>{entry.display_name}</strong><span>{entry.corporation_name || "Public attendee"}</span><b>{entry.attendance_status}</b></article>)}</div>}
    </section>}
  </div>;
}
