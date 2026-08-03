import { ArrowLeft, Check, Plus, RotateCcw, UserPlus, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import type { AttendanceRoster, AttendanceStatus, EventDetail } from "../../types/events";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

export function EventAttendancePanel({ api, event, onBack }: { api: ApiClient; event: EventDetail; onBack: () => void }) {
  const [roster, setRoster] = useState<AttendanceRoster | null>(null);
  const [source, setSource] = useState<"external_character" | "public_guest">("external_character");
  const [eveId, setEveId] = useState("");
  const [name, setName] = useState("");
  const [corporation, setCorporation] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState<number | "manual" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setRoster(await api<AttendanceRoster>(`/events/${event.id}/attendance`));
  }

  useEffect(() => { setRoster(null); setError(null); void load().catch((err) => setError(err instanceof Error ? err.message : "Unable to load attendance")); }, [event.id]);

  async function mark(registrationId: number, attendanceStatus: AttendanceStatus) {
    setBusy(registrationId); setError(null);
    try {
      await api(`/events/${event.id}/attendance/registrations/${registrationId}`, { method: "PUT", body: JSON.stringify({ attendance_status: attendanceStatus }) });
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to mark attendance"); }
    finally { setBusy(null); }
  }

  async function reset(attendanceId: number) {
    setBusy(attendanceId); setError(null);
    try { await api(`/events/${event.id}/attendance/${attendanceId}`, { method: "DELETE" }); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to reset attendance"); }
    finally { setBusy(null); }
  }

  async function addManual(submitEvent: FormEvent) {
    submitEvent.preventDefault(); setBusy("manual"); setError(null);
    try {
      await api(`/events/${event.id}/attendance`, { method: "POST", body: JSON.stringify({ attendee_source: source, character_eve_id: source === "external_character" ? Number(eveId) : null, display_name: name, corporation_name: corporation.trim() || null, notes: notes.trim() || null }) });
      setEveId(""); setName(""); setCorporation(""); setNotes(""); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to add attendee"); }
    finally { setBusy(null); }
  }

  const counts = roster?.registrations.reduce<Record<string, number>>((result, row) => { result[row.derived_attendance_status] = (result[row.derived_attendance_status] || 0) + 1; return result; }, {}) ?? {};

  return <div className="event-attendance-shell">
    <section className="panel">
      <div className="event-pane-heading"><div><span className="eyebrow">After action</span><h3>Attendance · {event.title}</h3></div><button type="button" className="event-secondary-button" onClick={onBack}><ArrowLeft size={17} /> Event detail</button></div>
      {error && <div className="mini-alert">{error}</div>}
      <div className="event-attendance-summary">{["attended", "no_show", "excused", "unmarked"].map((status) => <article key={status}><span>{status.replace(/_/g, " ")}</span><strong>{counts[status] || 0}</strong></article>)}<article><span>Walk-ins</span><strong>{roster?.unregistered_attendees.length || 0}</strong></article></div>
      {!roster ? <p className="muted">Loading roster…</p> : <div className="event-attendance-list">{roster.registrations.map((registration) => <article key={registration.id}>
        <img src={`https://images.evetech.net/characters/${registration.character_eve_id}/portrait?size=64`} alt="" />
        <span><strong>{registration.character_name}</strong><small>{registration.ship_name || registration.freeform_ship_description || "Ship undecided"} · {registration.corporation_name || "No corporation snapshot"}</small></span>
        <b className={`event-attendance-state attendance-${registration.derived_attendance_status}`}>{registration.derived_attendance_status.replace(/_/g, " ")}</b>
        <div className="event-attendance-actions">
          <button disabled={busy === registration.id} type="button" title="Attended" onClick={() => void mark(registration.id, "attended")}><Check size={16} /></button>
          <button disabled={busy === registration.id} type="button" title="No show" onClick={() => void mark(registration.id, "no_show")}><X size={16} /></button>
          <button disabled={busy === registration.id} type="button" title="Excused" onClick={() => void mark(registration.id, "excused")}>EX</button>
          {registration.attendance && <button disabled={busy === registration.attendance.id} type="button" title="Reset to unmarked" onClick={() => void reset(registration.attendance!.id)}><RotateCcw size={15} /></button>}
        </div>
      </article>)}</div>}
    </section>
    <section className="panel event-walkin-panel">
      <div className="event-pane-heading"><div><span className="eyebrow">No EQM registration</span><h3>Add Attendee</h3></div><UserPlus size={22} /></div>
      <form onSubmit={(submitEvent) => void addManual(submitEvent)}>
        <label><span>Attendee type</span><select value={source} onChange={(changeEvent) => setSource(changeEvent.target.value as "external_character" | "public_guest")}><option value="external_character">External EVE character</option><option value="public_guest">Public guest / freeform</option></select></label>
        {source === "external_character" && <label><span>EVE character ID</span><input required type="number" min={1} value={eveId} onChange={(changeEvent) => setEveId(changeEvent.target.value)} /></label>}
        <label><span>Display name</span><input required maxLength={255} value={name} onChange={(changeEvent) => setName(changeEvent.target.value)} /></label>
        <label><span>Corporation</span><input maxLength={255} value={corporation} onChange={(changeEvent) => setCorporation(changeEvent.target.value)} /></label>
        <label><span>Notes</span><textarea rows={3} value={notes} onChange={(changeEvent) => setNotes(changeEvent.target.value)} /></label>
        <button type="submit" disabled={busy === "manual"}><Plus size={16} /> Add as attended</button>
      </form>
      {(roster?.unregistered_attendees.length ?? 0) > 0 && <div className="event-walkin-list"><h4>Recorded walk-ins</h4>{roster?.unregistered_attendees.map((entry) => <article key={entry.id}><strong>{entry.display_name}</strong><span>{entry.corporation_name || entry.attendee_source.replace(/_/g, " ")}</span><b>{entry.attendance_status}</b><button type="button" aria-label={`Remove ${entry.display_name}`} onClick={() => void reset(entry.id)}><TrashIcon /></button></article>)}</div>}
    </section>
  </div>;
}

function TrashIcon() { return <X size={15} />; }
