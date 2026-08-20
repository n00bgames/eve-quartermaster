import { AlertTriangle, CircleCheck, Clock3, Plus, RefreshCw, ShieldOff, Trash2, UserRoundCheck } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";

import { isCharacterSyncPollingAborted, resumeCharacterSyncJob, trackCharacterSyncJob } from "../../lib/characterSyncPolling";
import type { ContactSyncJob, ContactSyncPreview, EsiAuthInfo, LinkedCharacter, SyncDatasetFreshness, SyncFreshnessPayload } from "../../types/esi";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type UserAccount = { id: number; email: string; display_name: string; role: string; timezone?: string; created_at?: string };
type ManagedFormComponent = (props: { children: ReactNode; onSubmit: (form: FormData) => Promise<void>; submitLabel?: string }) => ReactElement;
type MetricComponent = (props: { icon: ReactNode; label: string; value: number | string; delta?: string }) => ReactElement;
type CharacterHoverNameComponent = (props: { characterId?: number | null; name: string; className?: string; href?: string }) => ReactElement;

type EsiSyncPageProps = {
  currentUser: UserAccount;
  load: () => Promise<void>;
  api: ApiClient;
  ManagedForm: ManagedFormComponent;
  Metric: MetricComponent;
  CharacterHoverName: CharacterHoverNameComponent;
};

export function EsiSyncPage({ currentUser, load, api, ManagedForm, Metric, CharacterHoverName }: EsiSyncPageProps) {
  const [status, setStatus] = useState<string>("Not checked");
  const [authInfo, setAuthInfo] = useState<EsiAuthInfo | null>(null);
  const [standingAuthInfo, setStandingAuthInfo] = useState<EsiAuthInfo | null>(null);
  const [linked, setLinked] = useState<LinkedCharacter[]>([]);
  const [resolveResult, setResolveResult] = useState<string>("");
  const [message, setMessage] = useState<string | null>(null);
  const [sourceTokenId, setSourceTokenId] = useState<number | "">("");
  const [targetTokenIds, setTargetTokenIds] = useState<number[]>([]);
  const [overwriteContacts, setOverwriteContacts] = useState(false);
  const [exactMatchContacts, setExactMatchContacts] = useState(false);
  const [contactPreview, setContactPreview] = useState<ContactSyncPreview | null>(null);
  const [contactJob, setContactJob] = useState<ContactSyncJob | null>(null);
  const [contactBusy, setContactBusy] = useState(false);
  const [contactError, setContactError] = useState<string | null>(null);
  const [contactNotice, setContactNotice] = useState<string | null>(null);
  const [freshness, setFreshness] = useState<SyncFreshnessPayload | null>(null);
  const [freshnessBusy, setFreshnessBusy] = useState(false);
  const [freshnessError, setFreshnessError] = useState<string | null>(null);
  const contactPollingRef = useRef(false);
  const contactPollAbortRef = useRef<AbortController | null>(null);
  const contactResumeScope = `contact-sync-${currentUser.id}`;

  async function checkStatus() {
    const payload = await api<{ players?: number; server_version?: string }>("/esi/status");
    setStatus(`${payload.players?.toLocaleString() ?? "Unknown"} pilots online · ${payload.server_version ?? "version unknown"}`);
  }

  async function loadEsiState() {
    const [auth, standingAuth, linkedCharacters, freshnessPayload] = await Promise.all([
      api<EsiAuthInfo>("/esi/auth-url"),
      api<EsiAuthInfo>("/esi/auth-url/standing-sync"),
      api<LinkedCharacter[]>("/esi/linked-characters"),
      api<SyncFreshnessPayload>("/esi/sync-freshness"),
    ]);
    setAuthInfo(auth);
    setStandingAuthInfo(standingAuth);
    setLinked(linkedCharacters);
    setFreshness(freshnessPayload);
  }

  async function refreshFreshness() {
    setFreshnessBusy(true);
    setFreshnessError(null);
    try {
      setFreshness(await api<SyncFreshnessPayload>("/esi/sync-freshness"));
    } catch (err) {
      setFreshnessError(err instanceof Error ? err.message : "Sync status could not be refreshed.");
    } finally {
      setFreshnessBusy(false);
    }
  }

  async function resolveNames(form: FormData) {
    const payload = await api<Record<string, unknown>>("/esi/resolve", { method: "POST", body: JSON.stringify({ names: form.get("names") }) });
    setResolveResult(JSON.stringify(payload, null, 2));
  }

  async function importPublic(form: FormData) {
    const kind = form.get("kind");
    const id = form.get("id");

    await api(`/esi/import/${kind}/${id}`, { method: "POST", body: "{}" });
    setMessage(`${kind} ${id} imported from ESI.`);
    await load();
  }

  async function syncAssets(tokenId: number, characterName: string) {
    setMessage(`Syncing assets for ${characterName}...`);
    const result = await api<{ asset_rows: number; character_name: string }>(`/esi/sync/character-assets/${tokenId}`, { method: "POST", body: "{}" });
    setMessage(`Synced ${result.asset_rows.toLocaleString()} asset rows for ${result.character_name}.`);
    await Promise.all([load(), loadEsiState()]);
  }

  async function unlinkCharacter(tokenId: number, characterName: string) {
    if (!window.confirm(`Unlink ${characterName}? You can re-link through EVE SSO to refresh scopes.`)) return;

    const result = await api<{ character_name: string }>(`/esi/linked-characters/${tokenId}`, { method: "DELETE" });
    setMessage(`${result.character_name} unlinked. Re-authorize to pull fresh ESI scopes.`);
    setContactPreview(null);
    setContactError(null);
    setContactNotice(null);
    setTargetTokenIds((current) => current.filter((id) => id !== tokenId));
    setSourceTokenId((current) => current === tokenId ? "" : current);
    await loadEsiState();
  }

  function toggleTarget(tokenId: number) {
    setContactPreview(null);
    setContactError(null);
    setContactNotice(null);
    setTargetTokenIds((current) => current.includes(tokenId) ? current.filter((id) => id !== tokenId) : [...current, tokenId]);
  }

  async function previewContactSync() {
    if (sourceTokenId === "") return;

    setContactBusy(true);
    setMessage(null);
    setContactError(null);
    setContactNotice(null);
    try {
      const preview = await api<ContactSyncPreview>("/esi/standings/preview", {
        method: "POST",
        body: JSON.stringify({ source_token_id: sourceTokenId, target_token_ids: targetTokenIds, overwrite_existing: overwriteContacts, exact_match: exactMatchContacts }),
      });
      setContactPreview(preview);
      setContactNotice(`Preview ready: ${preview.totals.create.toLocaleString()} create, ${preview.totals.update.toLocaleString()} update, ${preview.totals.delete.toLocaleString()} delete.`);
    } catch (err) {
      setContactError(err instanceof Error ? err.message : "Standing sync preview failed.");
    } finally {
      setContactBusy(false);
    }
  }

  async function applyContactSync() {
    if (sourceTokenId === "") return;
    const deleteCount = contactPreview?.totals.delete ?? 0;
    if (exactMatchContacts && deleteCount > 0 && !window.confirm(
      `Exact Match will permanently delete ${deleteCount.toLocaleString()} destination-only EVE contact${deleteCount === 1 ? "" : "s"} across ${targetTokenIds.length.toLocaleString()} selected character${targetTokenIds.length === 1 ? "" : "s"}. Continue?`,
    )) return;

    setContactBusy(true);
    setContactError(null);
    setContactNotice(null);
    try {
      const initialJob = await api<ContactSyncJob>("/esi/standings/apply", {
        method: "POST",
        body: JSON.stringify({ source_token_id: sourceTokenId, target_token_ids: targetTokenIds, overwrite_existing: overwriteContacts, exact_match: exactMatchContacts }),
      });
      setContactJob(initialJob);
      setContactPreview(null);
      setContactNotice(`Queued contact sync from ${initialJob.source_character_name}. You can leave this page; EQM will continue working in the background.`);
      void monitorContactSyncJob(initialJob, contactPollAbortRef.current?.signal);
    } catch (err) {
      setContactError(err instanceof Error ? err.message : "Standing sync failed.");
    } finally {
      setContactBusy(false);
    }
  }

  async function monitorContactSyncJob(initialJob: ContactSyncJob, signal?: AbortSignal) {
    if (contactPollingRef.current) return;
    contactPollingRef.current = true;
    try {
      const job = await trackCharacterSyncJob({
        scope: contactResumeScope,
        initialJob,
        fetchLatest: (current) => api<ContactSyncJob>(`/esi/contact-sync/jobs/${current.job_id}`),
        onUpdate: setContactJob,
        signal,
      });
      setContactJob(job);
      await loadEsiState();
      if (job.status === "complete") {
        setContactNotice(`Copied contacts from ${job.source_character_name}: ${job.created.toLocaleString()} created, ${job.updated.toLocaleString()} updated, ${job.deleted.toLocaleString()} deleted.`);
      } else {
        setContactNotice(null);
        setContactError(job.errors[0] ?? "One or more contact sync targets failed.");
      }
    } catch (err) {
      if (!isCharacterSyncPollingAborted(err)) {
        setContactNotice(null);
        setContactError(err instanceof Error ? err.message : "Unable to monitor the queued contact sync.");
      }
    } finally {
      contactPollingRef.current = false;
    }
  }

  useEffect(() => { void loadEsiState(); }, []);

  useEffect(() => {
    const controller = new AbortController();
    contactPollAbortRef.current = controller;
    contactPollingRef.current = true;
    void resumeCharacterSyncJob<ContactSyncJob>({
      scope: contactResumeScope,
      fetchById: (jobId) => api<ContactSyncJob>(`/esi/contact-sync/jobs/${jobId}`),
      onUpdate: (job) => {
        setContactJob(job);
        setContactNotice("Resumed contact sync progress from the server...");
      },
      signal: controller.signal,
    }).then(async (job) => {
      if (!job) return;
      setContactJob(job);
      await loadEsiState();
      if (job.status === "complete") {
        setContactNotice(`Copied contacts from ${job.source_character_name}: ${job.created.toLocaleString()} created, ${job.updated.toLocaleString()} updated, ${job.deleted.toLocaleString()} deleted.`);
      } else {
        setContactNotice(null);
        setContactError(job.errors[0] ?? "One or more contact sync targets failed.");
      }
    }).catch((err) => {
      if (!isCharacterSyncPollingAborted(err)) setContactError(err instanceof Error ? err.message : "Unable to resume contact sync progress.");
    }).finally(() => {
      contactPollingRef.current = false;
    });
    return () => controller.abort();
  }, [currentUser.id]);

  useEffect(() => {
    if (!freshness?.active_batches.length) return;
    const timer = globalThis.setInterval(() => void refreshFreshness(), 2_000);
    return () => globalThis.clearInterval(timer);
  }, [freshness?.active_batches.length]);

  useEffect(() => {
    if (linked.length === 0) return;
    setSourceTokenId((current) => current === "" ? linked[0].token_id : current);
  }, [linked]);

  const targetOptions = linked.filter((character) => character.token_id !== sourceTokenId);
  const contactJobActive = contactJob?.status === "queued" || contactJob?.status === "running";
  const contactJobPercent = contactJob?.total_count ? Math.round((contactJob.processed_count / contactJob.total_count) * 100) : 0;

  function scopeStatus(character: LinkedCharacter, kind: "public" | "standing") {
    const missing = kind === "public" ? character.missing_public_scopes : character.missing_standing_scopes;
    return missing.length === 0 ? <span className="scope-ok">{kind === "public" ? "Core scopes current" : "Contact scopes current"}</span> : <span className="scope-warn">Missing {kind === "public" ? "core" : "contact"} scopes: {missing.join(", ")}</span>;
  }

  return (
    <div className="esi-sync-page">
      <SyncFreshnessCenter payload={freshness} busy={freshnessBusy} error={freshnessError} onRefresh={refreshFreshness} Metric={Metric} CharacterHoverName={CharacterHoverName} />
      <div className="two-column">
      <section className="panel stacked">
        <h3>Linked Characters</h3>
        {linked.length > 0 ? (
          <div className="card-list">
            {linked.map((character) => (
              <article key={character.token_id}>
                <strong><CharacterHoverName characterId={character.character_id} name={character.character_name} /></strong>
                <span>Character ID {character.character_id}</span>
                {["host", "admin"].includes(currentUser.role) && <span>SSO linked by {character.linked_user_display_name}</span>}
                <span>Last sync {character.last_sync_at ? `${new Date(character.last_sync_at).toLocaleString()} (${character.last_sync_type ?? "sync"})` : "never"}</span>
                <span>Linked {character.linked_at ? new Date(character.linked_at).toLocaleString() : "recently"}</span>
                {scopeStatus(character, "public")}
                {scopeStatus(character, "standing")}
                {(character.can_sync_assets || character.can_unlink || (character.linked_user_id === currentUser.id && character.missing_standing_scopes.length > 0 && standingAuthInfo?.ready)) && (
                  <div className="card-actions">
                    {character.can_sync_assets && <button type="button" onClick={() => void syncAssets(character.token_id, character.character_name)}>Sync assets</button>}
                    {character.linked_user_id === currentUser.id && character.missing_standing_scopes.length > 0 && standingAuthInfo?.ready ? <a className="mini-link" href={standingAuthInfo.url}>Authorize contact sync</a> : null}
                    {character.can_unlink && <button className="danger" type="button" onClick={() => void unlinkCharacter(character.token_id, character.character_name)}>Unlink</button>}
                  </div>
                )}
              </article>
            ))}
          </div>
        ) : <p className="muted">No EVE characters linked yet.</p>}
        <h3>Authenticated Sync</h3>
        {authInfo?.ready ? <a className="auth-link" href={authInfo.url}>Start EVE SSO</a> : <p className="muted">{authInfo?.message ?? "Checking SSO setup..."}</p>}
        <div className="scope-list">{authInfo?.required_scopes.map((scope) => <code key={scope}>{scope}</code>)}</div>
      </section>

      <section className="panel stacked">
        <h3><UserRoundCheck size={20} /> Character Contacts Sync</h3>
        {standingAuthInfo?.ready ? <a className="auth-link secondary" href={standingAuthInfo.url}>Authorize contact sync</a> : <p className="muted">{standingAuthInfo?.message ?? "Checking contact sync setup..."}</p>}
        <div className="scope-list compact">{standingAuthInfo?.required_scopes.map((scope) => <code key={scope}>{scope}</code>)}</div>
        <label>Copy contacts from<select value={sourceTokenId} onChange={(event) => { setSourceTokenId(Number(event.target.value)); setTargetTokenIds([]); setContactPreview(null); setContactError(null); setContactNotice(null); }}><option value="">Choose source</option>{linked.map((character) => <option key={character.token_id} value={character.token_id}>{character.character_name}</option>)}</select></label>
        <div className="choice-list">
          <span>Copy to</span>
          {targetOptions.length > 0 ? targetOptions.map((character) => <label className="check" key={character.token_id}><input type="checkbox" checked={targetTokenIds.includes(character.token_id)} onChange={() => toggleTarget(character.token_id)} /> {character.character_name}</label>) : <p className="muted">Link at least one more character before syncing contacts.</p>}
        </div>
        <label className="check"><input type="checkbox" checked={overwriteContacts} disabled={exactMatchContacts} onChange={(event) => { setOverwriteContacts(event.target.checked); setContactPreview(null); setContactError(null); setContactNotice(null); }} /> Update existing target contacts when contact standings differ</label>
        <label className="check"><input type="checkbox" checked={exactMatchContacts} onChange={(event) => { const checked = event.target.checked; setExactMatchContacts(checked); if (checked) setOverwriteContacts(true); setContactPreview(null); setContactError(null); setContactNotice(null); }} /> Exact Match: make each selected character's contacts identical to the source, including deleting destination-only contacts</label>
        {exactMatchContacts && <div className="scope-warn"><strong>Exact Match is destructive.</strong> Preview the deletions carefully. EQM creates missing contacts and updates changed standings first, then permanently deletes contacts that do not exist on the source character.</div>}
        <div className="button-row"><button type="button" disabled={sourceTokenId === "" || targetTokenIds.length === 0 || contactBusy || contactJobActive} onClick={() => void previewContactSync()}>Preview</button><button type="button" disabled={!contactPreview || contactBusy || contactJobActive} onClick={() => void applyContactSync()}>{contactJobActive ? "Sync queued" : exactMatchContacts ? "Apply exact match" : "Apply sync"}</button></div>
        {contactJob && <div className={`queue-badge queue-${contactJob.status}`} role="status" aria-live="polite"><strong>{contactJob.processed_count.toLocaleString()} / {contactJob.total_count.toLocaleString()}</strong><span>{contactJob.status === "complete" ? "Contact sync complete" : contactJob.status === "failed" ? "Contact sync needs review" : contactJob.current_character_name ? `Syncing contacts to ${contactJob.current_character_name}` : "Contact sync queued"} · {contactJob.created.toLocaleString()} created · {contactJob.updated.toLocaleString()} updated · {contactJob.deleted.toLocaleString()} deleted</span><i style={{ width: `${contactJobPercent}%` }} /></div>}
        {contactError && <div className="mini-alert">{contactError}</div>}
        {contactNotice && <div className="notice inline">{contactNotice}</div>}
        {contactPreview && <ContactPreview preview={contactPreview} Metric={Metric} />}
      </section>

      <section className="panel stacked">
        <h3>Public ESI</h3>
        <div className="esi-status-row"><button type="button" onClick={() => void checkStatus()}>Check server status</button><span>{status}</span></div>
        {message && <div className="notice inline">{message}</div>}
        <h3>Resolve Names</h3>
        <ManagedForm onSubmit={resolveNames} submitLabel="Resolve"><label>Names<textarea name="names" placeholder="Jita&#10;The Scare Bears&#10;Steihl Lianul" required /></label></ManagedForm>
        {resolveResult && <pre className="json-output">{resolveResult}</pre>}
        <h3>Import Public ID</h3>
        <ManagedForm onSubmit={importPublic} submitLabel="Import"><label>Kind<select name="kind"><option value="type">Item type</option><option value="character">Character</option><option value="corporation">Corporation</option><option value="alliance">Alliance</option><option value="system">System</option><option value="station">Station</option></select></label><label>ESI ID<input name="id" type="number" required placeholder="34" /></label></ManagedForm>
      </section>
      </div>
    </div>
  );
}

const HEALTH_LABELS: Record<SyncDatasetFreshness["health"], string> = {
  current: "Current",
  active: "In progress",
  stale: "Stale",
  failed: "Failed",
  never_synced: "Never synced",
  missing_scope: "Missing scope",
  disabled: "Disabled",
  skipped: "Skipped",
};

function freshnessAge(seconds?: number | null) {
  if (seconds == null) return "No successful observation yet";
  if (seconds < 60) return "less than a minute ago";
  const hours = Math.floor(seconds / 3600);
  if (hours < 1) return `${Math.floor(seconds / 60)}m ago`;
  if (hours < 48) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function SyncFreshnessCenter({ payload, busy, error, onRefresh, Metric, CharacterHoverName }: {
  payload: SyncFreshnessPayload | null;
  busy: boolean;
  error: string | null;
  onRefresh: () => Promise<void>;
  Metric: MetricComponent;
  CharacterHoverName: CharacterHoverNameComponent;
}) {
  return <section className="panel stacked sync-freshness-center">
    <div className="section-heading">
      <div><h3><Clock3 size={20} /> Sync &amp; Freshness Center</h3><p>Character Data Sync and module syncs are ESI workflows too; active bulk progress, durable jobs, dataset age, authorization, and privacy state appear here.</p></div>
      <button type="button" disabled={busy} onClick={() => void onRefresh()}><RefreshCw className={busy ? "spin" : ""} size={17} /> {busy ? "Refreshing" : "Refresh status"}</button>
    </div>
    {error && <div className="mini-alert">{error}</div>}
    {!payload ? <p className="muted">Loading sync history…</p> : <>
      <div className="status-grid wide sync-freshness-summary">
        <Metric icon={<UserRoundCheck size={18} />} label="Linked characters" value={payload.summary.linked_characters} />
        <Metric icon={<CircleCheck size={18} />} label="Current datasets" value={payload.summary.current} delta={`${payload.summary.datasets} tracked`} />
        <Metric icon={<AlertTriangle size={18} />} label="Needs attention" value={payload.summary.attention} delta="failed, stale, or never synced" />
        <Metric icon={<Clock3 size={18} />} label="Active jobs" value={payload.summary.active} />
        <Metric icon={<ShieldOff size={18} />} label="Missing scopes" value={payload.summary.missing_scope} />
        <Metric icon={<ShieldOff size={18} />} label="Privacy disabled" value={payload.summary.disabled} />
      </div>
      {payload.active_batches.map((job) => {
        const percent = job.total_count ? Math.round(job.processed_count / job.total_count * 100) : 0;
        return <div className="queue-badge queue-running" key={job.job_id} role="status" aria-live="polite"><strong>{job.processed_count.toLocaleString()} / {job.total_count.toLocaleString()}</strong><span>{job.current_character_name ? `${job.job_kind}: ${job.current_sync_label ?? job.current_sync_kind ?? "data"} for ${job.current_character_name}` : `${job.job_kind} sync ${job.status}`} · {job.success_count.toLocaleString()} synced · {job.failed_count.toLocaleString()} failed · {job.skipped_count.toLocaleString()} skipped</span><i style={{ width: `${percent}%` }} /></div>;
      })}
      <div className="sync-freshness-characters">
        {payload.characters.map((character) => {
          const attention = character.datasets.filter((dataset) => ["stale", "failed", "never_synced", "missing_scope"].includes(dataset.health)).length;
          return <details key={character.token_id} className="sync-freshness-character" open={payload.characters.length === 1}>
            <summary>
              <span><CharacterHoverName characterId={character.character_id} name={character.character_name} />{character.sync_opt_out && <small>Owner disabled shared sync</small>}</span>
              <span className={attention > 0 ? "freshness-count attention" : "freshness-count"}>{attention > 0 ? `${attention} need attention` : "All available data current"}</span>
            </summary>
            <div className="sync-dataset-grid">
              {character.datasets.map((dataset) => <article key={dataset.key} className={`sync-dataset-card health-${dataset.health}`}>
                <div><strong>{dataset.label}</strong><span>{HEALTH_LABELS[dataset.health]}</span></div>
                <small>{dataset.disabled_reason ?? (dataset.missing_scopes.length > 0 ? `Authorize: ${dataset.missing_scopes.join(", ")}` : freshnessAge(dataset.age_seconds))}</small>
                {dataset.message && dataset.health === "failed" && <p title={dataset.message}>{dataset.message}</p>}
              </article>)}
            </div>
          </details>;
        })}
        {payload.characters.length === 0 && <p className="empty">No EVE characters are linked for this account.</p>}
      </div>
      {payload.recent_jobs.length > 0 && <details className="sync-job-history"><summary>Recent durable jobs</summary><div>{payload.recent_jobs.map((job) => <article key={job.id}><strong>{job.character_name ?? "Linked entity"} · {job.sync_type.replace(/_/g, " ")}</strong><span className={`health-${job.status}`}>{job.status}</span><small>{job.finished_at || job.started_at ? new Date(job.finished_at ?? job.started_at ?? "").toLocaleString() : "Queued"}</small></article>)}</div></details>}
      <small className="muted">Checked {new Date(payload.generated_at).toLocaleString()}. “Stale” means the last durable job is more than 26 hours old; ESI cache timing may still delay newly changed game data.</small>
    </>}
  </section>;
}

function ContactPreview({ preview, Metric }: { preview: ContactSyncPreview; Metric: MetricComponent }) {
  return (
    <div className="contact-preview">
      <strong>{preview.source_character_name}: {preview.source_contact_count.toLocaleString()} source contacts</strong>
      <div className="status-grid compact" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}>
        <Metric icon={<Plus size={18} />} label="Creates" value={preview.totals.create} />
        <Metric icon={<RefreshCw size={18} />} label="Updates" value={preview.totals.update} />
        <Metric icon={<Trash2 size={18} />} label="Deletes" value={preview.totals.delete} />
        <Metric icon={<UserRoundCheck size={18} />} label="Skipped" value={preview.totals.skip} />
      </div>
      {preview.targets.map((target) => <article key={target.token_id}><strong>{target.character_name}</strong><span>{target.create_count.toLocaleString()} create · {target.update_count.toLocaleString()} update · {target.delete_count.toLocaleString()} delete · {target.skip_count.toLocaleString()} skip</span>{target.create_sample.slice(0, 4).map((contact) => <code key={`${target.token_id}-create-${contact.contact_id}`}>Create · {contact.name}: {contact.standing}</code>)}{target.update_sample.slice(0, 4).map((contact) => <code key={`${target.token_id}-update-${contact.contact_id}`}>Update · {contact.name}: {contact.standing}</code>)}{target.delete_sample.slice(0, 8).map((contact) => <code key={`${target.token_id}-delete-${contact.contact_id}`}>Delete · {contact.name}: {contact.standing}</code>)}</article>)}
    </div>
  );
}
