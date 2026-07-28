import { Building2, CheckCircle2, RefreshCw, Save, Search, ShieldCheck, UserCog } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

import type { RecruitingCapabilities, RecruitingCeo, RecruitingOrganization, RecruitingSettings } from "../../types/recruiting";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type Props = { api: ApiClient; onRefresh: () => Promise<void> };
type ResolvedOrganization = RecruitingOrganization & { ceo?: RecruitingCeo; alliance?: RecruitingOrganization };

export function RecruitingSetup({ api, onRefresh }: Props) {
  const [settings, setSettings] = useState<RecruitingSettings | null>(null);
  const [capabilities, setCapabilities] = useState<RecruitingCapabilities | null>(null);
  const [corporationQuery, setCorporationQuery] = useState("");
  const [allianceQuery, setAllianceQuery] = useState("");
  const [ceoQuery, setCeoQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [settingRows, capabilityRows] = await Promise.all([
      api<RecruitingSettings>("/recruiting/settings"),
      api<RecruitingCapabilities>("/recruiting/capabilities"),
    ]);
    setSettings(settingRows); setCapabilities(capabilityRows);
  }, [api]);
  useEffect(() => { load().catch((reason) => setError(reason instanceof Error ? reason.message : "Recruiting setup could not be loaded.")); }, []);

  async function execute(action: () => Promise<void>, success?: string) {
    setBusy(true); setError(null);
    try { await action(); if (success) setNotice(success); } catch (reason) { setError(reason instanceof Error ? reason.message : "Recruiting setup update failed."); } finally { setBusy(false); }
  }

  async function resolve(kind: "corporation" | "alliance" | "character", name: string) {
    if (!name.trim() || !settings) return;
    await execute(async () => {
      const result = await api<ResolvedOrganization>(`/recruiting/resolve-organization?kind=${kind}&name=${encodeURIComponent(name.trim())}`);
      if (kind === "corporation") {
        setSettings({ ...settings, corporation: result, ceo: result.ceo ?? settings.ceo, alliance: result.alliance?.id ? result.alliance : settings.alliance, ceo_manual_override: false });
      } else if (kind === "alliance") setSettings({ ...settings, alliance: result });
      else setSettings({ ...settings, ceo: { ...result, manual_override: true }, ceo_manual_override: true });
    });
  }

  async function save(complete = false) {
    if (!settings) return;
    await execute(async () => {
      const payload: Record<string, unknown> = {
        corporation_eve_id: settings.corporation?.id,
        alliance_eve_id: settings.alliance?.id, alliance_name: settings.alliance?.name, alliance_ticker: settings.alliance?.ticker, alliance_logo_url: settings.alliance?.logo_url,
        ceo_manual_override: settings.ceo_manual_override,
        primary_timezone: settings.primary_timezone, activity_window_start: settings.activity_window_start, activity_window_end: settings.activity_window_end,
        public_headline: settings.public_headline, public_subheading: settings.public_subheading,
        public_summary: settings.public_summary, public_body: settings.public_body,
        offers: settings.offers, expectations: settings.expectations, priorities: settings.priorities, privacy_notice: settings.privacy_notice,
        statuses: settings.statuses, tags: settings.tags, form_options: settings.form_options,
        application_questions: settings.application_questions, interview_questions: settings.interview_questions, parameter_definitions: settings.parameter_definitions,
        declined_retention_days: settings.declined_retention_days, withdrawn_retention_days: settings.withdrawn_retention_days,
        abandoned_retention_days: settings.abandoned_retention_days, auto_refresh_hours: settings.auto_refresh_hours,
        setup_complete: complete || settings.setup_complete,
      };
      if (settings.ceo_manual_override) Object.assign(payload, { ceo_character_eve_id: settings.ceo?.id, ceo_character_name: settings.ceo?.name, ceo_portrait_url: settings.ceo?.portrait_url });
      const updated = await api<RecruitingSettings>("/recruiting/settings", { method: "PATCH", body: JSON.stringify(payload) });
      setSettings(updated); await onRefresh();
    }, complete ? "Recruiting setup completed." : "Recruiting settings saved.");
  }

  async function updateCapability(userId: number, capability: string, enabled: boolean) {
    if (!capabilities) return;
    const user = capabilities.users.find((row) => row.id === userId);
    if (!user) return;
    const values = enabled ? [...new Set([...user.capabilities, capability])] : user.capabilities.filter((value) => value !== capability);
    await execute(async () => {
      await api(`/recruiting/capabilities/${userId}`, { method: "PUT", body: JSON.stringify({ capabilities: values }) });
      setCapabilities({ ...capabilities, users: capabilities.users.map((row) => row.id === userId ? { ...row, capabilities: values } : row) });
    });
  }

  if (!settings) return <section className="panel"><p className="muted">Loading Recruiting Initial Setup...</p>{error && <div className="alert error">{error}</div>}</section>;
  return (
    <div className="recruiting-setup">
      {!settings.setup_complete && <section className="recruiting-setup-banner"><Building2 size={26} /><div><h3>Recruiting Initial Setup</h3><p>Choose your corporation and customize the public application before applicants can register.</p></div></section>}
      {error && <div className="alert error">{error}</div>}{notice && <div className="alert success">{notice}</div>}

      <section className="panel recruiting-setup-section">
        <div className="section-heading"><div><span>1</span><h3>Corporation, alliance, and CEO</h3></div></div>
        <p className="muted">Selecting a corporation resolves its current CEO automatically from ESI. A manual override is available only for exceptional cases and is recorded in the recruiting audit log.</p>
        <OrganizationSearch label="Corporation" value={corporationQuery} onChange={setCorporationQuery} onSearch={() => resolve("corporation", corporationQuery)} busy={busy} />
        <IdentityCard organization={settings.corporation} />
        <OrganizationSearch label="Alliance" value={allianceQuery} onChange={setAllianceQuery} onSearch={() => resolve("alliance", allianceQuery)} busy={busy} />
        <IdentityCard organization={settings.alliance} />
        <div className="recruiting-ceo-setup">
          {settings.ceo?.portrait_url && <img src={settings.ceo.portrait_url} alt="CEO portrait" />}
          <div><span>Corporation CEO</span><strong>{settings.ceo?.name || "Resolve a corporation"}</strong><small>{settings.ceo_manual_override ? "Manual override · audited" : "Automatically resolved from ESI"}</small></div>
          <label className="check"><input type="checkbox" checked={settings.ceo_manual_override} onChange={(event) => setSettings({ ...settings, ceo_manual_override: event.target.checked })} /><span>Allow manual CEO override</span></label>
        </div>
        {settings.ceo_manual_override && <OrganizationSearch label="Override CEO character" value={ceoQuery} onChange={setCeoQuery} onSearch={() => resolve("character", ceoQuery)} busy={busy} />}
      </section>

      <section className="panel recruiting-setup-section">
        <div className="section-heading"><div><span>2</span><h3>Public recruiting page</h3></div></div>
        <div className="recruiting-form-grid">
          <label>Headline<input value={settings.public_headline ?? ""} onChange={(event) => setSettings({ ...settings, public_headline: event.target.value })} /></label>
          <label>Subheading<input value={settings.public_subheading ?? ""} onChange={(event) => setSettings({ ...settings, public_subheading: event.target.value })} /></label>
          <label>Primary timezone<input value={settings.primary_timezone} onChange={(event) => setSettings({ ...settings, primary_timezone: event.target.value })} placeholder="America/Chicago" /></label>
          <label>Activity starts<input type="time" value={settings.activity_window_start ?? ""} onChange={(event) => setSettings({ ...settings, activity_window_start: event.target.value })} /></label>
          <label>Activity ends<input type="time" value={settings.activity_window_end ?? ""} onChange={(event) => setSettings({ ...settings, activity_window_end: event.target.value })} /></label>
        </div>
        <label>Short summary<textarea value={settings.public_summary ?? ""} onChange={(event) => setSettings({ ...settings, public_summary: event.target.value })} /></label>
        <label>Full public description<textarea placeholder="## Who We Are" value={settings.public_body ?? ""} onChange={(event) => setSettings({ ...settings, public_body: event.target.value })} /></label>
        <div className="recruiting-three-columns">
          <LineList label="What we offer" values={settings.offers ?? []} onChange={(offers) => setSettings({ ...settings, offers })} />
          <LineList label="What we expect" values={settings.expectations ?? []} onChange={(expectations) => setSettings({ ...settings, expectations })} />
          <LineList label="Current priorities" values={settings.priorities ?? []} onChange={(priorities) => setSettings({ ...settings, priorities })} />
        </div>
        <label>Privacy notice<textarea value={settings.privacy_notice ?? ""} onChange={(event) => setSettings({ ...settings, privacy_notice: event.target.value })} /></label>
      </section>

      <section className="panel recruiting-setup-section">
        <div className="section-heading"><div><span>3</span><h3>Recruiting capabilities</h3></div><UserCog size={21} /></div>
        <p className="muted">Recruiter and Recruitment Administrator are assignable capabilities, not account roles. Existing member permissions remain unchanged.</p>
        <div className="recruiting-capability-table">
          {(capabilities?.users ?? []).map((user) => <article key={user.id}><div><strong>{user.display_name}</strong><span>{user.email} · {user.role}</span></div>{(capabilities?.capabilities ?? []).map((capability) => <label className="check" key={capability}><input type="checkbox" checked={user.capabilities.includes(capability)} onChange={(event) => updateCapability(user.id, capability, event.target.checked)} /><span>{capability === "recruitment_admin" ? "Recruitment Administrator" : "Recruiter"}</span></label>)}</article>)}
        </div>
      </section>

      <section className="panel recruiting-setup-section">
        <details><summary>Advanced workflow configuration</summary>
          <div className="recruiting-two-columns">
            <LineList label="Statuses" values={settings.statuses} onChange={(statuses) => setSettings({ ...settings, statuses })} />
            <LineList label="Tags" values={settings.tags} onChange={(tags) => setSettings({ ...settings, tags })} />
          </div>
          <JsonEditor label="Application questions" value={settings.application_questions} onChange={(application_questions) => setSettings({ ...settings, application_questions })} />
          <JsonEditor label="Interview questions" value={settings.interview_questions} onChange={(interview_questions) => setSettings({ ...settings, interview_questions })} />
          <JsonEditor label="Assessment parameters" value={settings.parameter_definitions} onChange={(parameter_definitions) => setSettings({ ...settings, parameter_definitions })} />
          <div className="recruiting-form-grid"><label>Declined retention days<input type="number" value={settings.declined_retention_days} onChange={(event) => setSettings({ ...settings, declined_retention_days: Number(event.target.value) })} /></label><label>Withdrawn retention days<input type="number" value={settings.withdrawn_retention_days} onChange={(event) => setSettings({ ...settings, withdrawn_retention_days: Number(event.target.value) })} /></label><label>Abandoned retention days<input type="number" value={settings.abandoned_retention_days} onChange={(event) => setSettings({ ...settings, abandoned_retention_days: Number(event.target.value) })} /></label><label>ESI refresh hours<input type="number" value={settings.auto_refresh_hours} onChange={(event) => setSettings({ ...settings, auto_refresh_hours: Number(event.target.value) })} /></label></div>
        </details>
      </section>

      <div className="recruiting-setup-actions"><button type="button" onClick={() => load()} disabled={busy}><RefreshCw size={17} /> Reset unsaved</button><button type="button" onClick={() => save(false)} disabled={busy}><Save size={17} /> Save settings</button>{!settings.setup_complete && <button type="button" onClick={() => save(true)} disabled={busy}><CheckCircle2 size={17} /> Complete Initial Setup</button>}</div>
    </div>
  );
}

function OrganizationSearch({ label, value, onChange, onSearch, busy }: { label: string; value: string; onChange: (value: string) => void; onSearch: () => void; busy: boolean }) { return <div className="recruiting-org-search"><label>{label}<input value={value} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); onSearch(); } }} /></label><button type="button" onClick={onSearch} disabled={busy || !value.trim()}><Search size={17} /> Resolve from ESI</button></div>; }
function IdentityCard({ organization }: { organization?: RecruitingOrganization }) { return organization?.id ? <div className="recruiting-identity-card">{organization.logo_url && <img src={organization.logo_url} alt="" />}<div><strong>{organization.name}</strong><span>{organization.ticker ? `[${organization.ticker}] · ` : ""}EVE ID {organization.id}</span></div><ShieldCheck size={20} /></div> : <p className="muted">Not selected.</p>; }
function LineList({ label, values, onChange }: { label: string; values: string[]; onChange: (values: string[]) => void }) { return <label>{label}<textarea value={values.join("\n")} onChange={(event) => onChange(event.target.value.split("\n").map((row) => row.trim()).filter(Boolean))} /></label>; }
function JsonEditor<T>({ label, value, onChange }: { label: string; value: T; onChange: (value: T) => void }) { const [text, setText] = useState(() => JSON.stringify(value, null, 2)); function parse(event: FormEvent<HTMLTextAreaElement>) { const next = event.currentTarget.value; setText(next); try { onChange(JSON.parse(next)); } catch { /* Keep editing until valid JSON. */ } } return <label>{label}<textarea className="recruiting-json-editor" value={text} onInput={parse} /></label>; }
