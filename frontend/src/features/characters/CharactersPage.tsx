import { Activity, Boxes, ClipboardList, GraduationCap, PackagePlus, ScrollText, ShoppingCart } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";

import { ImplantDogmaChip } from "./ImplantDogmaChip";
import { PilotSecurityStatus } from "./PilotSecurityStatus";
import type { CharacterDossier, CharacterDossierToken, CharacterFocus, EqmCharacter } from "../../types/characters";
import type { JumpClonePayload, JumpCloneRecord } from "../../types/jumpClones";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type UserAccount = { id: number; email: string; display_name: string; role: string };
type EveEntityKind = "character" | "corporation" | "alliance";
type EveIconSize = "tiny" | "sm" | "md" | "lg";
type SyncKind = "assets" | "skills" | "fittings" | "contracts" | "implants";
type CharacterSyncAllJob = { job_id: string; status: "queued" | "running" | "complete" | "failed" | "cancelled"; created_at: string; updated_at?: string | null; completed_at?: string | null; total_count: number; processed_count: number; success_count: number; failed_count: number; skipped_count: number; current_character_name?: string | null; current_sync_kind?: SyncKind | null; results: { character_name: string; sync_kind: SyncKind; status: string }[]; errors: string[] };

type MetricComponent = (props: { icon: ReactNode; label: string; value: number | string; delta?: string }) => ReactElement;
type EveEntityIconComponent = (props: { kind: EveEntityKind; id?: number | null; name?: string | null; size?: EveIconSize }) => ReactElement;
type CharacterHoverNameComponent = (props: { characterId?: number | null; name: string; className?: string; href?: string }) => ReactElement;
type AssetTableComponent = (props: { assets: any[] }) => ReactElement;
type BlueprintListComponent = (props: { blueprints: any[]; assets?: any[] }) => ReactElement;

function cloneLocationText(clone: JumpCloneRecord): string {
  if (clone.clone_kind === "active_clone") return "Active clone";
  if (clone.location_name && clone.system_name && clone.location_name !== clone.system_name) return `${clone.location_name} · ${clone.system_name}`;
  if (clone.location_name) return clone.location_name;
  if (clone.location_id) return `${clone.location_type ?? "Location"} ${clone.location_id}`;
  return "Jump clone";
}

type CharactersPageProps = {
  currentUser: UserAccount;
  focus?: CharacterFocus | null;
  api: ApiClient;
  Metric: MetricComponent;
  EveEntityIcon: EveEntityIconComponent;
  CharacterHoverName: CharacterHoverNameComponent;
  AssetTable: AssetTableComponent;
  BlueprintList: BlueprintListComponent;
  formatDateTime: (value?: string | null) => string;
  numberFormatter: Intl.NumberFormat;
  accountLabel: (user: UserAccount) => string;
};

export function CharactersPage({
  currentUser,
  focus,
  api,
  Metric,
  EveEntityIcon,
  CharacterHoverName,
  AssetTable,
  BlueprintList,
  formatDateTime,
  numberFormatter,
  accountLabel,
}: CharactersPageProps) {
  const [characters, setCharacters] = useState<EqmCharacter[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<number | null>(null);
  const [dossier, setDossier] = useState<CharacterDossier | null>(null);
  const [accounts, setAccounts] = useState<UserAccount[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [characterError, setCharacterError] = useState<string | null>(null);
  const [loadingDossier, setLoadingDossier] = useState(false);
  const [busySync, setBusySync] = useState<string | null>(null);
  const [syncAllJob, setSyncAllJob] = useState<CharacterSyncAllJob | null>(null);
  const [jumpClonePayload, setJumpClonePayload] = useState<JumpClonePayload>({ characters: [], clones: [], custom_sets: [], sync_tokens: [] });
  const syncAllPollingRef = useRef(false);
  const canLoadAccounts = ["admin", "director"].includes(currentUser.role);
  const syncAllActive = syncAllJob?.status === "queued" || syncAllJob?.status === "running";
  const syncAllPercent = syncAllJob?.total_count ? Math.round((syncAllJob.processed_count / syncAllJob.total_count) * 100) : 0;
  const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

  async function loadCharacters(preferredId = selectedCharacterId, preferredEveId?: number | null) {
    const loaded = await api<EqmCharacter[]>("/characters");
    api<JumpClonePayload>("/jump-clones").then(setJumpClonePayload).catch(() => setJumpClonePayload({ characters: [], clones: [], custom_sets: [], sync_tokens: [] }));

    setCharacters(loaded);
    if (canLoadAccounts) setAccounts(await api<UserAccount[]>("/characters/accounts"));

    const byEveId = preferredEveId ? loaded.find((character) => character.character_id === preferredEveId)?.id ?? null : null;
    const byInternalId = preferredId && loaded.some((character) => character.id === preferredId) ? preferredId : null;

    if (preferredEveId && !byEveId) {
      setMessage("That pilot is not linked in Quartermaster yet, so their dossier is not available here.");
    }

    const nextId = byEveId ?? byInternalId ?? loaded[0]?.id ?? null;
    setSelectedCharacterId(nextId);
    return nextId;
  }

  async function loadDossier(characterId: number | null) {
    if (!characterId) {
      setDossier(null);
      return;
    }

    setLoadingDossier(true);
    setCharacterError(null);
    try {
      setDossier(await api<CharacterDossier>(`/characters/dossier/${characterId}`));
    } catch (err) {
      setDossier(null);
      const message = err instanceof Error ? err.message : "Unable to load character dossier";
      setCharacterError(message === "500 Internal Server Error" ? "Unable to load that character dossier. Pick another character or refresh the list." : message);
    } finally {
      setLoadingDossier(false);
    }
  }

  async function patchCharacter(characterId: number, body: Record<string, unknown>, success: string) {
    setCharacterError(null);
    try {
      const updated = await api<EqmCharacter>(`/characters/${characterId}`, { method: "PATCH", body: JSON.stringify(body) });

      setCharacters((current) => current.map((character) => character.id === updated.id ? updated : character));
      setMessage(success);
      if (selectedCharacterId === characterId) await loadDossier(characterId);
    } catch (err) {
      setCharacterError(err instanceof Error ? err.message : "Character update failed");
    }
  }

  async function runCharacterSync(kind: SyncKind, token: CharacterDossierToken) {
    const endpoints: Record<SyncKind, string> = {
      assets: `/esi/sync/character-assets/${token.token_id}`,
      skills: `/esi/sync/character-skills/${token.token_id}`,
      fittings: `/esi/sync/character-fittings/${token.token_id}`,
      contracts: `/contracts/sync/character/${token.token_id}`,
      implants: `/jump-clones/sync/${token.token_id}`,
    };

    setBusySync(`${token.token_id}-${kind}`);
    setCharacterError(null);
    try {
      await api(endpoints[kind], { method: "POST", body: "{}" });
      setMessage(`${dossier?.character.name ?? "Character"} ${kind} synced.`);
      const nextId = await loadCharacters(selectedCharacterId);
      await loadDossier(nextId);
    } catch (err) {
      setCharacterError(err instanceof Error ? err.message : `Unable to sync ${kind}`);
    } finally {
      setBusySync(null);
    }
  }


  async function syncAllCharacters() {
    if (syncAllPollingRef.current) return;
    syncAllPollingRef.current = true;
    setCharacterError(null);
    setMessage("Queued assets, skills, fittings, and contracts for every eligible character...");
    try {
      let job = await api<CharacterSyncAllJob>("/esi/sync/characters/all", { method: "POST", body: "{}" });
      setSyncAllJob(job);
      const startedAt = Date.now();
      while (job.status === "queued" || job.status === "running") {
        if (Date.now() - startedAt > 10 * 60 * 1000) {
          setMessage(null);
          setCharacterError("Character sync is still running after 10 minutes, so polling was stopped. Refresh Characters to check the latest status, or restart the backend worker if the count is not moving.");
          setSyncAllJob((current) => current ? { ...current, status: "failed", errors: ["Polling stopped after 10 minutes while the backend job was still running.", ...current.errors] } : current);
          return;
        }
        await wait(2000);
        job = await api<CharacterSyncAllJob>(`/esi/sync/characters/all/${job.job_id}`);
        setSyncAllJob(job);
      }
      const nextId = await loadCharacters(selectedCharacterId);
      await loadDossier(nextId);
      if (job.status === "complete") {
        setMessage(`Synced ${job.success_count.toLocaleString()} of ${job.total_count.toLocaleString()} queued character sync tasks. Skipped ${job.skipped_count.toLocaleString()} opted-out, hidden, duplicate, or missing-scope task${job.skipped_count === 1 ? "" : "s"}.`);
      } else {
        setMessage(null);
        setCharacterError(job.errors[0] ?? "One or more character sync tasks failed.");
      }
    } catch (err) {
      setMessage(null);
      setCharacterError(err instanceof Error ? err.message : "Sync all characters failed");
    } finally {
      syncAllPollingRef.current = false;
    }
  }

  useEffect(() => {
    void loadCharacters().then((nextId) => loadDossier(nextId)).catch((err) => setCharacterError(err instanceof Error ? err.message : "Unable to load characters"));
  }, []);

  useEffect(() => {
    void loadDossier(selectedCharacterId);
  }, [selectedCharacterId]);

  useEffect(() => {
    if (!focus?.characterId) return;
    void loadCharacters(selectedCharacterId, focus.characterId).then((nextId) => loadDossier(nextId)).catch((err) => setCharacterError(err instanceof Error ? err.message : "Unable to open character"));
  }, [focus?.nonce]);

  const selectedCharacter = characters.find((character) => character.id === selectedCharacterId) ?? null;
  const selectedJumpClones = jumpClonePayload.clones.filter((clone) => clone.character_id === selectedCharacterId);
  const syncAllStatus = syncAllJob?.status === "complete" ? "Character sync complete" : syncAllJob?.status === "failed" ? "Character sync needs review" : syncAllJob?.current_character_name ? `Syncing ${syncAllJob.current_sync_kind ?? "data"} for ${syncAllJob.current_character_name}` : "Character sync queued";
  const summary = dossier?.summary;
  const canManage = Boolean(dossier?.permissions.can_manage);
  const canAssign = Boolean(dossier?.permissions.can_assign);
  const syncButton = (token: CharacterDossierToken, kind: SyncKind, label: string, enabled: boolean) => (
    <button type="button" disabled={!token.can_sync || !enabled || busySync !== null || syncAllActive} onClick={() => void runCharacterSync(kind, token)}>
      {busySync === `${token.token_id}-${kind}` ? "Syncing..." : label}
    </button>
  );

  return (
    <section className="panel stacked">
      <div className="section-heading">
        <div>
          <h3>Characters</h3>
          <p>{characters.length.toLocaleString()} visible character{characters.length === 1 ? "" : "s"}</p>
        </div>
        <div className="button-row compact"><button type="button" disabled={syncAllActive || characters.length === 0} onClick={() => void syncAllCharacters()}>{syncAllActive ? "Syncing all" : "Sync all eligible"}</button><button type="button" disabled={syncAllActive} onClick={() => void loadCharacters(selectedCharacterId).then((nextId) => loadDossier(nextId))}>Refresh</button></div>
      </div>
      {syncAllJob && <div className={`queue-badge queue-${syncAllJob.status}`}><strong>{syncAllJob.processed_count.toLocaleString()} / {syncAllJob.total_count.toLocaleString()}</strong><span>{syncAllStatus} · {syncAllJob.success_count.toLocaleString()} synced · {syncAllJob.failed_count.toLocaleString()} failed · {syncAllJob.skipped_count.toLocaleString()} skipped</span><i style={{ width: `${syncAllPercent}%` }} /></div>}
      {message && <div className="notice inline">{message}</div>}
      {characterError && <div className="mini-alert">{characterError}</div>}
      <div className="character-dossier-layout">
        <aside className="character-picker-list">
          {characters.map((character) => (
            <button type="button" key={character.id} className={`character-picker-card ${selectedCharacterId === character.id ? "active" : ""}`} onClick={() => setSelectedCharacterId(character.id)}>
              <span className="entity-card-heading">
                <EveEntityIcon kind="character" id={character.character_id} name={character.name} size="sm" />
                <span>
                  <strong><CharacterHoverName characterId={character.character_id} name={character.name} /><PilotSecurityStatus securityStatus={character.security_status} compact /></strong>
                  <small>{character.owner_display_name ?? "Unassigned"}{character.owner_role ? ` · ${character.owner_role}` : ""}</small>
                </span>
              </span>
              <small>{character.corporation_name ?? "Unknown corporation"}</small>
            </button>
          ))}
          {characters.length === 0 && <p className="empty">No characters visible to this account yet.</p>}
        </aside>
        <div className="character-dossier-panel">
          {loadingDossier && <div className="notice inline">Loading character dossier...</div>}
          {!loadingDossier && !dossier && selectedCharacter && <div className="mini-alert">Details hidden by role policy.</div>}
          {dossier && summary && (
            <>
              <div className="character-dossier-header">
                <div className="entity-card-heading">
                  <EveEntityIcon kind="character" id={dossier.character.character_id} name={dossier.character.name} size="lg" />
                  <div>
                    <h3><CharacterHoverName characterId={dossier.character.character_id} name={dossier.character.name} /></h3>
                    <PilotSecurityStatus securityStatus={dossier.character.security_status} />
                    <span>{dossier.character.owner_display_name ?? "Unassigned"}{dossier.character.owner_role ? ` · ${dossier.character.owner_role}` : ""}</span>
                    <span>{dossier.character.corporation_name ?? "Unknown corporation"}{dossier.character.alliance_name ? ` · ${dossier.character.alliance_name}` : ""}</span>
                    <span>Last sync {dossier.character.last_synced_at ? formatDateTime(dossier.character.last_synced_at) : "never"}</span>
                  </div>
                </div>
              </div>
              <div className="character-summary-grid">
                <Metric icon={<GraduationCap size={18} />} label="Skill points" value={summary.total_skill_points} />
                <Metric icon={<Activity size={18} />} label="Queue" value={summary.queue_count} />
                <Metric icon={<Boxes size={18} />} label="Asset units" value={summary.asset_units} />
                <Metric icon={<PackagePlus size={18} />} label="Ships" value={summary.ship_units} />
                <Metric icon={<ScrollText size={18} />} label="Blueprints" value={`${summary.bpos.toLocaleString()} BPO / ${summary.bpcs.toLocaleString()} BPC`} />
                <Metric icon={<ClipboardList size={18} />} label="Contracts" value={summary.contracts} />
              </div>
              {canManage && (
                <div className="character-admin-strip">
                  <h4>Character Controls</h4>
                  {canAssign && (
                    <label>
                      EQM Account
                      <select value={dossier.character.owner_user_id ?? ""} onChange={(event) => void patchCharacter(dossier.character.id, { owner_user_id: event.target.value || null }, `${dossier.character.name} reassigned.`)}>
                        <option value="">Unassigned</option>
                        {accounts.map((account) => <option key={account.id} value={account.id}>{accountLabel(account)} ({account.role})</option>)}
                      </select>
                    </label>
                  )}
                  <label className="check"><input type="checkbox" checked={Boolean(dossier.permissions.public_assets_visible)} onChange={(event) => void patchCharacter(dossier.character.id, { public_assets_visible: event.target.checked }, `${dossier.character.name} visibility updated.`)} /> Public assets visible to members</label>
                  <label className="check"><input type="checkbox" checked={Boolean(dossier.permissions.sync_opt_out)} onChange={(event) => void patchCharacter(dossier.character.id, { sync_opt_out: event.target.checked }, `${dossier.character.name} sync preference updated.`)} /> Keep this character private from shared Quartermaster sync</label>
                  {!dossier.permissions.public_assets_visible && <div className="privacy-placard">This character has not made assets public to members. Admin asset sync is an override for administrative review.</div>}
                  {dossier.permissions.sync_opt_out && <div className="privacy-placard">This character does not wish to be synced. Admins can override temporarily for administrative review, but this preference remains visible.</div>}
                </div>
              )}
              <div className="character-sync-grid">
                {dossier.sync_tokens.map((token) => (
                  <article key={token.token_id}>
                    <strong>SSO linked by {token.linked_user_display_name}</strong>
                    <span>Linked {token.linked_at ? formatDateTime(token.linked_at) : "unknown"}</span>
                    {token.can_sync ? <span className="scope-ok">Sync permitted</span> : <span className="scope-warn">Sync hidden by role policy</span>}
                    {token.missing_scopes.length > 0 && <small>Missing scopes: {token.missing_scopes.join(", ")}</small>}
                    <div className="button-row compact">
                      {syncButton(token, "assets", "Sync assets", token.has_asset_scope)}
                      {syncButton(token, "skills", "Sync skills", token.has_skill_scope)}
                      {syncButton(token, "fittings", "Sync fittings", token.has_fitting_scope)}
                      {syncButton(token, "contracts", "Sync contracts", token.has_contract_scope)}
                      {syncButton(token, "implants", "Sync clones", token.has_clone_scope)}
                    </div>
                  </article>
                ))}
              </div>
              <details className="character-jump-clone-summary">
                <summary>Jump clones and implants <span>{selectedJumpClones.length.toLocaleString()}</span></summary>
                <div className="jump-clone-grid compact">
                  {selectedJumpClones.map((clone) => <article key={clone.id} className="jump-clone-card"><div className="jump-clone-card-heading"><strong>{clone.name}</strong><span>{cloneLocationText(clone)}</span>{clone.location_id && clone.location_name && <small>ID {clone.location_id}</small>}</div><div className="implant-chip-list">{clone.implants.map((implant) => <ImplantDogmaChip key={`${clone.id}-${implant.type_id}`} implant={implant} />)}{clone.implants.length === 0 && <span className="implant-empty">No implants</span>}</div></article>)}
                  {selectedJumpClones.length === 0 && <p className="empty">No clone implants synced for this character yet.</p>}
                </div>
              </details>
              <div className="two-column character-dossier-sections">
                <section>
                  <h4>Skill Categories</h4>
                  <div className="mini-list">
                    {dossier.skills.categories.map((category) => <div key={category.name}><strong>{category.name}</strong><span>{numberFormatter.format(category.skill_points)} SP · {category.skill_count.toLocaleString()} skills</span></div>)}
                    {dossier.skills.categories.length === 0 && <p className="empty">No skill snapshot yet.</p>}
                  </div>
                </section>
                <section>
                  <h4>Skill Queue</h4>
                  <div className="mini-list">
                    {dossier.skills.queue.map((entry) => <div key={entry.id}><strong>{entry.queue_position}. {entry.skill_name} {entry.finished_level}</strong><span>{entry.finish_date ? `Finishes ${formatDateTime(entry.finish_date)}` : "No finish time"}</span></div>)}
                    {dossier.skills.queue.length === 0 && <p className="empty">No queued skills stored.</p>}
                  </div>
                </section>
              </div>
                            <div className="two-column character-dossier-sections">
                <section><h4>Assets Snapshot</h4><AssetTable assets={dossier.assets} /></section>
                <section><h4>Blueprint Snapshot</h4><BlueprintList blueprints={dossier.blueprints} assets={dossier.assets} /></section>
              </div>
                            <div className="two-column character-dossier-sections">
                <section>
                  <h4>Fittings</h4>
                  <div className="mini-list">
                    {dossier.fittings.map((fitting) => <div key={fitting.id}><strong>{fitting.ship_type_name}</strong><span>{fitting.name}{fitting.is_draft ? " · Draft" : ""}{fitting.is_shared ? " · Shared" : " · Private"}</span></div>)}
                    {dossier.fittings.length === 0 && <p className="empty">No saved fittings stored.</p>}
                  </div>
                </section>
                <section>
                  <h4>Contracts</h4>
                  <div className="mini-list">
                    {dossier.contracts.map((contract) => <div key={contract.id}><strong>{contract.title || contract.contract_type || `Contract ${contract.contract_id}`}</strong><span>{contract.status ?? "unknown"}{contract.reward ? ` · ${Math.round(contract.reward).toLocaleString()} ISK reward` : ""}</span></div>)}
                    {dossier.contracts.length === 0 && <p className="empty">No contracts stored.</p>}
                  </div>
                </section>
              </div>
              <section>
                <h4>Kill / Loss History</h4>
                <div className="character-summary-grid">
                  <Metric icon={<Activity size={18} />} label="Kills" value={dossier.kill_history.kills_count} />
                  <Metric icon={<Activity size={18} />} label="Losses" value={dossier.kill_history.losses_count} />
                  <Metric icon={<ShoppingCart size={18} />} label="ISK destroyed" value={Math.round(dossier.kill_history.isk_destroyed).toLocaleString()} />
                  <Metric icon={<ShoppingCart size={18} />} label="ISK lost" value={Math.round(dossier.kill_history.isk_lost).toLocaleString()} />
                </div>
                <div className="mini-list character-kill-list">
                  {[...dossier.kill_history.kills, ...dossier.kill_history.losses].slice(0, 10).map((kill) => <div key={`${kill.killmail_id}-${kill.victim_character_name}`}><strong>{kill.victim_hull ?? "Unknown hull"}{kill.smartbomb_used ? " · Smartbombs" : ""}{kill.is_wardec ? " · Wardec" : ""}</strong><span>{kill.killmail_time ? formatDateTime(kill.killmail_time) : "Unknown time"} · {kill.location_name ?? "Unknown location"}{kill.zkb_url ? <a href={kill.zkb_url} target="_blank" rel="noreferrer"> zKill</a> : null}</span></div>)}
                  {dossier.kill_history.kills.length + dossier.kill_history.losses.length === 0 && <p className="empty">No killmail observations stored for this character.</p>}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
