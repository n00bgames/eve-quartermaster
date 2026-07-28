import { CalendarPlus, Eye, MessageSquare, RefreshCw, Save, Search, ShieldAlert, UserRoundCheck } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import type { RecruitingApplication, RecruitingContext, RecruitingDashboard } from "../../types/recruiting";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type Props = { api: ApiClient; context: RecruitingContext };

export function RecruitingDashboardPage({ api, context }: Props) {
  const [dashboard, setDashboard] = useState<RecruitingDashboard | null>(null);
  const [selected, setSelected] = useState<RecruitingApplication | null>(null);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (preferredId?: number) => {
    const query = new URLSearchParams();
    if (status) query.set("status", status);
    if (search.trim()) query.set("search", search.trim());
    const result = await api<RecruitingDashboard>(`/recruiting/dashboard?${query.toString()}`);
    setDashboard(result);
    const target = result.applications.find((row) => row.id === (preferredId ?? selected?.id)) ?? result.applications[0] ?? null;
    if (target) setSelected(await api<RecruitingApplication>(`/recruiting/applications/${target.id}`));
    else setSelected(null);
  }, [api, search, selected?.id, status]);

  useEffect(() => { load().catch((reason) => setError(reason instanceof Error ? reason.message : "Recruiting dashboard could not be loaded.")); }, []);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(null);
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Recruiting update failed."); } finally { setBusy(false); }
  }

  async function patchApplication(payload: Record<string, unknown>) {
    if (!selected) return;
    await api(`/recruiting/applications/${selected.id}`, { method: "PATCH", body: JSON.stringify(payload) });
    await load(selected.id);
  }

  const columns = useMemo(() => dashboard?.applications ?? [], [dashboard]);
  return (
    <div className="recruiting-dashboard">
      <section className="recruiting-summary-strip">
        {Object.entries(dashboard?.counts ?? {}).map(([label, count]) => <article key={label}><span>{label}</span><strong>{count}</strong></article>)}
        {!Object.keys(dashboard?.counts ?? {}).length && <article><span>Applications</span><strong>0</strong></article>}
      </section>
      <section className="panel recruiting-dashboard-toolbar">
        <label><span>Search</span><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Applicant, Discord, or character" /></label>
        <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All active statuses</option>{(dashboard?.statuses ?? []).map((value) => <option key={value}>{value}</option>)}</select></label>
        <button type="button" onClick={() => run(() => load())} disabled={busy}><RefreshCw size={17} /> Apply</button>
      </section>
      {error && <div className="alert error">{error}</div>}

      <section className="recruiting-review-layout">
        <aside className="panel recruiting-application-queue">
          <h3>Application queue</h3>
          {columns.map((application) => (
            <button type="button" key={application.id} className={selected?.id === application.id ? "active" : ""} onClick={() => run(async () => setSelected(await api<RecruitingApplication>(`/recruiting/applications/${application.id}`)))}>
              <span><strong>{application.preferred_name || application.applicant_name || application.discord_username}</strong><small>{application.status}</small></span>
              <span><b>{application.progress_percent}%</b><small>{application.characters.map((row) => row.name).join(", ") || "No characters"}</small></span>
            </button>
          ))}
          {!columns.length && <p className="muted">No submitted applications match this filter.</p>}
        </aside>

        {selected ? <ApplicantDossier application={selected} dashboard={dashboard} context={context} busy={busy} run={run} patch={patchApplication} api={api} reload={() => load(selected.id)} /> : <section className="panel recruiting-empty"><Eye size={28} /><p>Select an application to review.</p></section>}
      </section>
    </div>
  );
}

function ApplicantDossier({ application, dashboard, context, busy, run, patch, api, reload }: {
  application: RecruitingApplication; dashboard: RecruitingDashboard | null; context: RecruitingContext; busy: boolean;
  run: (action: () => Promise<void>) => Promise<void>; patch: (payload: Record<string, unknown>) => Promise<void>;
  api: ApiClient; reload: () => Promise<void>;
}) {
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [interviewTime, setInterviewTime] = useState("");
  const [tags, setTags] = useState(application.tags ?? []);
  const [ratings, setRatings] = useState(application.recruiter_ratings ?? {});
  useEffect(() => { setTags(application.tags ?? []); setRatings(application.recruiter_ratings ?? {}); }, [application.id, application.updated_at]);

  async function addText(event: FormEvent, kind: "notes" | "messages") {
    event.preventDefault();
    const body = kind === "notes" ? note : message;
    if (!body.trim()) return;
    await run(async () => {
      await api(`/recruiting/applications/${application.id}/${kind}`, { method: "POST", body: JSON.stringify({ body }) });
      kind === "notes" ? setNote("") : setMessage("");
      await reload();
    });
  }

  async function scheduleInterview() {
    if (!interviewTime) return;
    await run(async () => {
      await api(`/recruiting/applications/${application.id}/interviews`, { method: "POST", body: JSON.stringify({ scheduled_at: new Date(interviewTime).toISOString() }) });
      setInterviewTime(""); await reload();
    });
  }

  return (
    <div className="recruiting-dossier">
      <section className="panel recruiting-dossier-header">
        <div><h3>{application.preferred_name || application.applicant_name}</h3><p>{application.applicant_email} · Discord: {application.discord_username || "not supplied"}</p></div>
        <span className="status-badge">{application.status}</span>
      </section>
      <section className="panel recruiting-review-controls">
        <label>Status<select value={application.status} onChange={(event) => run(() => patch({ status: event.target.value }))}>{(dashboard?.statuses ?? []).map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Assigned recruiter<select value={application.assigned_recruiter_user_id ?? ""} onChange={(event) => run(() => patch({ assigned_recruiter_user_id: event.target.value ? Number(event.target.value) : null }))}><option value="">Unassigned</option>{(dashboard?.recruiters ?? []).map((row) => <option key={row.id} value={row.id}>{row.display_name}</option>)}</select></label>
        <button type="button" onClick={() => run(() => patch({ tags, recruiter_ratings: ratings }))} disabled={busy}><Save size={17} /> Save review</button>
        {!context.is_recruitment_admin && <span className="muted"><ShieldAlert size={15} /> Final decisions require Recruitment Administrator.</span>}
      </section>

      <section className="panel"><h3>Verified characters</h3><div className="recruiting-review-characters">{application.characters.map((character) => <article key={character.id}><img src={character.portrait_url ?? `https://images.evetech.net/characters/${character.character_id}/portrait?size=128`} alt="" /><div><strong>{character.name}{character.is_main ? " · Main" : ""}</strong><span>{character.total_skill_points?.toLocaleString()} SP · Sec {character.security_status?.toFixed(1)}</span><small>{String(character.snapshot.corporation_name ?? "Unknown corporation")} · {character.verification_status}</small></div></article>)}</div></section>

      <section className="panel recruiting-review-grid">
        <div><h3>Application answers</h3>{Object.entries(application.answers).map(([key, value]) => <article key={key}><strong>{humanize(key)}</strong><p>{String(value || "Not answered")}</p></article>)}</div>
        <div><h3>Assessment</h3>{(dashboard?.parameter_definitions ?? []).filter((row) => row.active).map((row) => <label key={row.key}>{row.label}<select value={ratings[row.key] ?? "Not assessed"} onChange={(event) => setRatings({ ...ratings, [row.key]: event.target.value })}>{["Not assessed", "Very low", "Low", "Moderate", "High", "Very high"].map((value) => <option key={value}>{value}</option>)}</select></label>)}</div>
      </section>

      <section className="panel"><h3>Tags</h3><div className="recruiting-tag-grid">{(dashboard?.tags ?? []).map((tag) => <label key={tag} className="check"><input type="checkbox" checked={tags.includes(tag)} onChange={(event) => setTags(event.target.checked ? [...tags, tag] : tags.filter((value) => value !== tag))} /><span>{tag}</span></label>)}</div></section>

      <section className="recruiting-review-grid">
        <section className="panel"><h3>Internal notes</h3><div className="recruiting-note-list">{(application.notes ?? []).map((row) => <article key={row.id}><strong>{row.author}</strong><p>{row.redacted ? "[Redacted]" : row.body}</p><small>{new Date(row.created_at).toLocaleString()}</small></article>)}</div><form onSubmit={(event) => addText(event, "notes")}><textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Recruiter-only note" /><button disabled={busy || !note.trim()}><Save size={16} /> Add note</button></form></section>
        <section className="panel"><h3>Applicant messages</h3><div className="recruiting-note-list">{application.messages.map((row) => <article key={row.id}><strong>{row.author}</strong><p>{row.body}</p><small>{new Date(row.created_at).toLocaleString()}</small></article>)}</div><form onSubmit={(event) => addText(event, "messages")}><textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Applicant-visible message" /><button disabled={busy || !message.trim()}><MessageSquare size={16} /> Send</button></form></section>
      </section>

      <section className="panel recruiting-interview-workflow"><div><h3>Interview workflow</h3><label>Schedule in your local time<input type="datetime-local" value={interviewTime} onChange={(event) => setInterviewTime(event.target.value)} /></label><button type="button" onClick={scheduleInterview} disabled={!interviewTime || busy}><CalendarPlus size={17} /> Schedule</button></div><div>{application.interviews.map((row) => <article key={row.id}><UserRoundCheck size={18} /><strong>{row.scheduled_at ? new Date(row.scheduled_at).toLocaleString() : "Scheduling requested"}</strong><span>{row.attendance_status}{row.interviewer ? ` · ${row.interviewer}` : ""}</span></article>)}</div></section>

      <section className="panel"><h3>Status history</h3><div className="recruiting-timeline">{application.timeline.map((row) => <article key={row.id}><span>{new Date(row.created_at).toLocaleString()}</span><strong>{row.new_status}</strong><p>{row.reason}</p></article>)}</div></section>
    </div>
  );
}

function humanize(value: string) { return value.replace(/_/g, " ").replace(/^./, (char: string) => char.toUpperCase()); }
