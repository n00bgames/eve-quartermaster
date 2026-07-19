import { Plus, RefreshCw, UserRoundCheck } from "lucide-react";
import { useEffect, useState, type ReactElement, type ReactNode } from "react";

import type { ContactApplyResult, ContactSyncPreview, EsiAuthInfo, LinkedCharacter } from "../../types/esi";

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
  const [contactPreview, setContactPreview] = useState<ContactSyncPreview | null>(null);
  const [contactBusy, setContactBusy] = useState(false);
  const [contactError, setContactError] = useState<string | null>(null);
  const [contactNotice, setContactNotice] = useState<string | null>(null);

  async function checkStatus() {
    const payload = await api<{ players?: number; server_version?: string }>("/esi/status");
    setStatus(`${payload.players?.toLocaleString() ?? "Unknown"} pilots online · ${payload.server_version ?? "version unknown"}`);
  }

  async function loadEsiState() {
    const [auth, standingAuth, linkedCharacters] = await Promise.all([
      api<EsiAuthInfo>("/esi/auth-url"),
      api<EsiAuthInfo>("/esi/auth-url/standing-sync"),
      api<LinkedCharacter[]>("/esi/linked-characters"),
    ]);
    setAuthInfo(auth);
    setStandingAuthInfo(standingAuth);
    setLinked(linkedCharacters);
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
        body: JSON.stringify({ source_token_id: sourceTokenId, target_token_ids: targetTokenIds, overwrite_existing: overwriteContacts }),
      });
      setContactPreview(preview);
      setContactNotice(`Preview ready: ${preview.totals.create.toLocaleString()} create, ${preview.totals.update.toLocaleString()} update.`);
    } catch (err) {
      setContactError(err instanceof Error ? err.message : "Standing sync preview failed.");
    } finally {
      setContactBusy(false);
    }
  }

  async function applyContactSync() {
    if (sourceTokenId === "") return;

    setContactBusy(true);
    setContactError(null);
    setContactNotice(null);
    try {
      const result = await api<ContactApplyResult>("/esi/standings/apply", {
        method: "POST",
        body: JSON.stringify({ source_token_id: sourceTokenId, target_token_ids: targetTokenIds, overwrite_existing: overwriteContacts }),
      });
      setContactNotice(`Copied contacts from ${result.source_character_name}: ${result.created.toLocaleString()} created, ${result.updated.toLocaleString()} updated.`);
      setContactPreview(null);
      await loadEsiState();
    } catch (err) {
      setContactError(err instanceof Error ? err.message : "Standing sync failed.");
    } finally {
      setContactBusy(false);
    }
  }

  useEffect(() => { void loadEsiState(); }, []);

  useEffect(() => {
    if (linked.length === 0) return;
    setSourceTokenId((current) => current === "" ? linked[0].token_id : current);
  }, [linked]);

  const targetOptions = linked.filter((character) => character.token_id !== sourceTokenId);

  function scopeStatus(character: LinkedCharacter, kind: "public" | "standing") {
    const missing = kind === "public" ? character.missing_public_scopes : character.missing_standing_scopes;
    return missing.length === 0 ? <span className="scope-ok">{kind === "public" ? "Core scopes current" : "Contact scopes current"}</span> : <span className="scope-warn">Missing {kind === "public" ? "core" : "contact"} scopes: {missing.join(", ")}</span>;
  }

  return (
    <div className="two-column">
      <section className="panel stacked">
        <h3>Linked Characters</h3>
        {linked.length > 0 ? (
          <div className="card-list">
            {linked.map((character) => (
              <article key={character.token_id}>
                <strong><CharacterHoverName characterId={character.character_id} name={character.character_name} /></strong>
                <span>Character ID {character.character_id}</span>
                {currentUser.role === "admin" && <span>SSO linked by {character.linked_user_display_name}</span>}
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
        <label className="check"><input type="checkbox" checked={overwriteContacts} onChange={(event) => { setOverwriteContacts(event.target.checked); setContactPreview(null); setContactError(null); setContactNotice(null); }} /> Update existing target contacts when contact standings differ</label>
        <div className="button-row"><button type="button" disabled={sourceTokenId === "" || targetTokenIds.length === 0 || contactBusy} onClick={() => void previewContactSync()}>Preview</button><button type="button" disabled={!contactPreview || contactBusy} onClick={() => void applyContactSync()}>Apply sync</button></div>
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
  );
}

function ContactPreview({ preview, Metric }: { preview: ContactSyncPreview; Metric: MetricComponent }) {
  return (
    <div className="contact-preview">
      <strong>{preview.source_character_name}: {preview.source_contact_count.toLocaleString()} source contacts</strong>
      <div className="status-grid compact">
        <Metric icon={<Plus size={18} />} label="Creates" value={preview.totals.create} />
        <Metric icon={<RefreshCw size={18} />} label="Updates" value={preview.totals.update} />
        <Metric icon={<UserRoundCheck size={18} />} label="Skipped" value={preview.totals.skip} />
      </div>
      {preview.targets.map((target) => <article key={target.token_id}><strong>{target.character_name}</strong><span>{target.create_count.toLocaleString()} create · {target.update_count.toLocaleString()} update · {target.skip_count.toLocaleString()} skip</span>{[...target.create_sample, ...target.update_sample].slice(0, 8).map((contact) => <code key={`${target.token_id}-${contact.contact_id}`}>{contact.name}: {contact.standing}</code>)}</article>)}
    </div>
  );
}
