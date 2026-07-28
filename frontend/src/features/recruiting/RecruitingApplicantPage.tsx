import { CheckCircle2, Clock3, Link2, MessageSquare, RefreshCw, Save, Send, ShieldCheck, Star, Trash2, XCircle } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import type { RecruitingApplication, RecruitingContext, RecruitingQuestion } from "../../types/recruiting";
import { startRecruitmentSso } from "./recruitingSso";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type Props = { api: ApiClient; context: RecruitingContext; onRefresh: () => Promise<void> };

const acknowledgementLabels: Record<string, string> = {
  adult: "I confirm I am at least 18 years old.",
  english: "I can communicate in written and spoken English.",
  discord: "I can use Discord for corporation communications.",
  voice: "I understand voice communications may be required for fleets.",
  esi: "I consent to the limited EVE SSO verification described below.",
  doctrine: "I understand doctrine training may be part of onboarding.",
  defense: "I understand members may be asked to help defend shared space when available.",
};

export function RecruitingApplicantPage({ api, context, onRefresh }: Props) {
  const application = context.application;
  const [draft, setDraft] = useState(() => applicationDraft(application));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => setDraft(applicationDraft(application)), [application?.updated_at]);
  useEffect(() => {
    function receiveSsoResult(event: MessageEvent) {
      if (event.origin !== window.location.origin) return;
      const payload = event.data as { type?: string; characterName?: string; error?: string };
      if (payload?.type !== "eqm:recruitment-sso-complete") return;
      setBusy(false);
      if (payload.error) {
        setError(payload.error);
        return;
      }
      setNotice(`${payload.characterName || "Character"} linked through EVE SSO.`);
      void onRefresh().catch((reason) => setError(reason instanceof Error ? reason.message : "Application could not be refreshed."));
    }

    window.addEventListener("message", receiveSsoResult);
    return () => window.removeEventListener("message", receiveSsoResult);
  }, [onRefresh]);
  const groupedQuestions = useMemo(() => groupQuestions(context.application_questions ?? []), [context.application_questions]);
  const editable = !application || ["Draft", "Additional Information Requested", "ESI Verification Required"].includes(application.status);

  async function save() {
    setBusy(true); setError(null);
    try {
      await api("/recruiting/applications/me", { method: "PATCH", body: JSON.stringify(draft) });
      setNotice("Application draft saved.");
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Application could not be saved.");
    } finally { setBusy(false); }
  }

  async function submit() {
    setBusy(true); setError(null);
    try {
      await api("/recruiting/applications/me/submit", { method: "POST", body: "{}" });
      setNotice("Application submitted for review.");
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Application could not be submitted.");
    } finally { setBusy(false); }
  }

  async function withdraw() {
    if (!application || !window.confirm("Withdraw this application? The recruiting team will retain the record according to its configured privacy policy.")) return;
    const reason = window.prompt("Optional reason for withdrawing:", "") ?? "";
    setBusy(true); setError(null);
    try {
      await api("/recruiting/applications/me/withdraw", { method: "POST", body: JSON.stringify({ reason }) });
      setNotice("Application withdrawn.");
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Application could not be withdrawn.");
    } finally { setBusy(false); }
  }
  async function startEsi() {
    setBusy(true); setError(null);
    try {
      await startRecruitmentSso({
        openWindow: () => window.open("about:blank", "_blank"),
        saveDraft: () => api("/recruiting/applications/me", { method: "PATCH", body: JSON.stringify(draft) }),
        loadAuthUrl: () => api<{ ready: boolean; url?: string; message?: string }>("/esi/auth-url?scope_group=recruitment"),
      });
      setNotice("Application draft saved. Complete EVE SSO in the new tab.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "EVE SSO could not be started.");
    } finally { setBusy(false); }
  }

  async function characterAction(characterId: number, action: "main" | "sync" | "unlink") {
    setBusy(true); setError(null);
    try {
      const path = `/recruiting/applications/me/characters/${characterId}${action === "main" ? "/main" : action === "sync" ? "/sync" : ""}`;
      await api(path, { method: action === "unlink" ? "DELETE" : "POST", body: action === "unlink" ? undefined : "{}" });
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Character could not be updated.");
    } finally { setBusy(false); }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!message.trim()) return;
    setBusy(true); setError(null);
    try {
      await api("/recruiting/applications/me/messages", { method: "POST", body: JSON.stringify({ body: message }) });
      setMessage("");
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Message could not be sent.");
    } finally { setBusy(false); }
  }

  async function acknowledgeInterview(interviewId: number) {
    setBusy(true); setError(null);
    try {
      await api(`/recruiting/applications/me/interviews/${interviewId}`, { method: "PATCH", body: JSON.stringify({ acknowledged: true }) });
      setNotice("Interview schedule acknowledged.");
      await onRefresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Interview could not be acknowledged.");
    } finally { setBusy(false); }
  }

  const progress = application?.progress_percent ?? 0;
  const canWithdraw = Boolean(application && !["Accepted", "Accepted with Onboarding Plan", "Declined", "Closed", "Applicant Withdrew"].includes(application.status));
  return (
    <div className="recruiting-applicant">
      <section className="panel recruiting-application-status">
        <div><div className="recruiting-status-summary"><span className="status-badge">{application?.status ?? "Draft"}</span><strong>{progress}% complete</strong></div>{canWithdraw && <button type="button" className="recruiting-withdraw" onClick={withdraw} disabled={busy}><XCircle size={17} /> Withdraw</button>}</div>
        <progress value={progress} max={100} />
        {!!application?.missing_requirements.length && <p className="muted">Still needed: {application.missing_requirements.join(", ")}</p>}
      </section>
      {error && <div className="alert error">{error}</div>}
      {notice && <div className="alert success">{notice}</div>}

      <section className="panel recruiting-form-section">
        <div className="section-heading"><div><span>1</span><h3>Contact and availability</h3></div></div>
        <div className="recruiting-form-grid">
          <label>Current Discord username<input disabled={!editable} value={draft.discord_username} onChange={(event) => setDraft({ ...draft, discord_username: event.target.value })} /></label>
          <label>Discord display name<input disabled={!editable} value={draft.discord_display_name} onChange={(event) => setDraft({ ...draft, discord_display_name: event.target.value })} /></label>
          <label>Preferred name<input disabled={!editable} value={draft.preferred_name} onChange={(event) => setDraft({ ...draft, preferred_name: event.target.value })} /></label>
          <label>Pronouns (optional)<input disabled={!editable} value={draft.pronouns} onChange={(event) => setDraft({ ...draft, pronouns: event.target.value })} /></label>
          <label>Timezone<input disabled={!editable} value={draft.timezone} placeholder="America/Chicago" onChange={(event) => setDraft({ ...draft, timezone: event.target.value })} /></label>
          <label>Primary interest<select disabled={!editable} value={draft.primary_interest} onChange={(event) => setDraft({ ...draft, primary_interest: event.target.value })}><option value="">Choose one</option>{(context.form_options?.primary_interests ?? []).map((value) => <option key={value}>{value}</option>)}</select></label>
          <label>Usually online from<input disabled={!editable} type="time" value={String(draft.activity_preferences.active_start ?? "")} onChange={(event) => setDraft({ ...draft, activity_preferences: { ...draft.activity_preferences, active_start: event.target.value } })} /></label>
          <label>Usually online until<input disabled={!editable} type="time" value={String(draft.activity_preferences.active_end ?? "")} onChange={(event) => setDraft({ ...draft, activity_preferences: { ...draft.activity_preferences, active_end: event.target.value } })} /></label>
        </div>
        {application?.overlap_hours != null && <p className="recruiting-overlap"><Clock3 size={17} /> Estimated overlap with the corporation window: <strong>{application.overlap_hours} hours</strong></p>}
      </section>

      {Object.entries(groupedQuestions).map(([section, questions], index) => (
        <section className="panel recruiting-form-section" key={section}>
          <div className="section-heading"><div><span>{index + 2}</span><h3>{section}</h3></div></div>
          <div className="recruiting-question-list">{questions.map((question) => <QuestionField key={question.key} question={question} disabled={!editable} value={draft.answers[question.key]} onChange={(value) => setDraft({ ...draft, answers: { ...draft.answers, [question.key]: value } })} />)}</div>
        </section>
      ))}

      <section className="panel recruiting-form-section">
        <div className="section-heading"><div><span>{Object.keys(groupedQuestions).length + 2}</span><h3>EVE character verification</h3></div><button type="button" onClick={startEsi} disabled={busy || !editable}><Link2 size={17} /> Link character</button></div>
        <div className="recruiting-scope-note"><ShieldCheck size={18} /><span>Requested scopes: {(context.public.required_scopes ?? ["publicData", "esi-skills.read_skills.v1"]).join(", ")}. No assets, wallet, mail, location, contacts, or fitting scopes are requested.</span></div>
        <div className="recruiting-character-grid">
          {(application?.characters ?? []).map((character) => (
            <article key={character.id} className={character.is_main ? "main" : ""}>
              <img src={character.portrait_url ?? `https://images.evetech.net/characters/${character.character_id}/portrait?size=128`} alt="" />
              <div><strong>{character.name}</strong><span>{character.total_skill_points?.toLocaleString() ?? 0} SP</span><small>{character.verification_status} · {character.token_health}</small></div>
              <div className="button-row">
                {!character.is_main && <button type="button" title="Set as main" onClick={() => characterAction(character.id, "main")}><Star size={16} /></button>}
                <button type="button" title="Refresh ESI snapshot" onClick={() => characterAction(character.id, "sync")}><RefreshCw size={16} /></button>
                {editable && <button type="button" className="danger" title="Unlink" onClick={() => characterAction(character.id, "unlink")}><Trash2 size={16} /></button>}
              </div>
            </article>
          ))}
          {!application?.characters.length && <p className="muted">No EVE characters linked yet.</p>}
        </div>
      </section>

      <section className="panel recruiting-form-section">
        <div className="section-heading"><div><span>{Object.keys(groupedQuestions).length + 3}</span><h3>Confirmations</h3></div></div>
        <div className="recruiting-check-list">{Object.entries(acknowledgementLabels).map(([key, label]) => <label key={key}><input disabled={!editable} type="checkbox" checked={Boolean(draft.acknowledgements[key])} onChange={(event) => setDraft({ ...draft, acknowledgements: { ...draft.acknowledgements, [key]: event.target.checked } })} /><span>{label}</span></label>)}</div>
        {editable && <div className="button-row"><button type="button" onClick={save} disabled={busy}><Save size={17} /> Save draft</button><button type="button" onClick={submit} disabled={busy || Boolean(application?.missing_requirements.length)}><CheckCircle2 size={17} /> Submit application</button></div>}
      </section>

      <section className="panel recruiting-communications">
        <div className="section-heading"><h3>Recruiter communication</h3><MessageSquare size={20} /></div>
        <div className="recruiting-message-list">{(application?.messages ?? []).map((row) => <article key={row.id} className={row.from_applicant ? "applicant" : "recruiter"}><strong>{row.author}</strong><p>{row.body}</p><small>{new Date(row.created_at).toLocaleString()}</small></article>)}{!application?.messages.length && <p className="muted">No messages yet.</p>}</div>
        <form className="recruiting-message-form" onSubmit={sendMessage}><textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Message the recruiting team" /><button type="submit" disabled={busy || !message.trim()}><Send size={17} /> Send</button></form>
        {!!application?.interviews.length && <div className="recruiting-interviews"><h4>Interviews</h4>{application.interviews.map((row) => <article key={row.id}><strong>{row.scheduled_at ? new Date(row.scheduled_at).toLocaleString() : "Scheduling requested"}</strong><span>{row.attendance_status}</span>{row.visible_follow_up && <p>{row.visible_follow_up}</p>}{row.scheduled_at && !row.applicant_acknowledged_at && <button type="button" className="icon-text-button" onClick={() => acknowledgeInterview(row.id)} disabled={busy}><CheckCircle2 size={16} /> Acknowledge schedule</button>}{row.applicant_acknowledged_at && <small>Acknowledged {new Date(row.applicant_acknowledged_at).toLocaleString()}</small>}</article>)}</div>}
      </section>
    </div>
  );
}

function applicationDraft(application?: RecruitingApplication | null) {
  return {
    discord_username: application?.discord_username ?? "", discord_display_name: application?.discord_display_name ?? "",
    preferred_name: application?.preferred_name ?? "", pronouns: application?.pronouns ?? "", timezone: application?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
    primary_interest: application?.primary_interest ?? "", answers: application?.answers ?? {}, acknowledgements: application?.acknowledgements ?? {}, activity_preferences: application?.activity_preferences ?? {},
  };
}

function groupQuestions(questions: RecruitingQuestion[]) {
  return questions.reduce<Record<string, RecruitingQuestion[]>>((groups, question) => {
    (groups[question.section] ??= []).push(question); return groups;
  }, {});
}

function QuestionField({ question, value, onChange, disabled }: { question: RecruitingQuestion; value: unknown; onChange: (value: unknown) => void; disabled: boolean }) {
  if (question.type === "checkbox") return <label className="check"><input disabled={disabled} type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} /><span>{question.label}</span></label>;
  if (question.type === "select") return <label>{question.label}{question.required && " *"}<select disabled={disabled} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)}><option value="">Choose one</option>{(question.options ?? []).map((option) => <option key={option}>{option}</option>)}</select></label>;
  if (question.type === "textarea") return <label>{question.label}{question.required && " *"}<textarea disabled={disabled} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} /></label>;
  return <label>{question.label}{question.required && " *"}<input disabled={disabled} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} /></label>;
}
