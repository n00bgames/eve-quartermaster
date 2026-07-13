import { Boxes, Database, Factory, KeyRound, MapIcon, PackagePlus, RefreshCw, ScrollText } from "lucide-react";
import { Fragment, useEffect, useState, type ReactElement, type ReactNode } from "react";

import type { EqmCharacter } from "../../types/characters";
import type { PermissionMatrix, RoleDefinition, SectionSettings, SdeImportProgress, SdeStatus } from "../../types/settings";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type UserAccount = { id: number; email: string; display_name: string; role: string; timezone?: string; created_at?: string };
type MetricComponent = (props: { icon: ReactNode; label: string; value: number | string; delta?: string }) => ReactElement;
type ManagedFormComponent = (props: { children: ReactNode; onSubmit: (form: FormData) => Promise<void>; submitLabel?: string }) => ReactElement;

type SettingsPageProps = {
  currentUser: UserAccount;
  api: ApiClient;
  Metric: MetricComponent;
  ManagedForm: ManagedFormComponent;
  accountLabel: (user: UserAccount) => string;
};

export function SettingsPage({ currentUser, api, Metric, ManagedForm, accountLabel }: SettingsPageProps) {
  const [characters, setCharacters] = useState<EqmCharacter[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [suppressPeekNotifications, setSuppressPeekNotifications] = useState(false);
  const [sdeStatus, setSdeStatus] = useState<SdeStatus | null>(null);
  const [sdePath, setSdePath] = useState("/sde");
  const [sdeBusy, setSdeBusy] = useState(false);
  const [sdeImportState, setSdeImportState] = useState<SdeImportProgress | null>(null);

  async function loadCharacters() {
    setCharacters(await api<EqmCharacter[]>("/characters"));
  }

  async function loadSdeStatus() {
    if (currentUser.role !== "admin") return;

    const status = await api<SdeStatus>("/sde/status");
    setSdeStatus(status);
    setSdePath((current) => current || status.default_source_path || "/sde");
  }

  async function loadSdeImportState() {
    if (currentUser.role !== "admin") return;

    const previousCompletedAt = sdeImportState?.completed_at;
    const state = await api<SdeImportProgress>("/sde/import-status");
    setSdeImportState(state);
    setSdeBusy(Boolean(state.running));
    if (state.status === "success" && state.completed_at && state.completed_at !== previousCompletedAt) {
      await loadSdeStatus();
      setMessage("SDE import complete. Static data counts refreshed.");
    }
  }

  async function patchNotificationSuppression(value: boolean) {
    setSettingsError(null);
    try {
      const settings = await api<{ suppress_peek_notifications: boolean }>("/notifications/settings", { method: "PATCH", body: JSON.stringify({ suppress_peek_notifications: value }) });
      setSuppressPeekNotifications(settings.suppress_peek_notifications);
      setMessage("Notification suppression updated.");
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : "Settings update failed");
    }
  }

  async function patchCharacter(character: EqmCharacter, body: Record<string, unknown>, success: string) {
    setSettingsError(null);
    try {
      const updated = await api<EqmCharacter>(`/characters/${character.id}`, { method: "PATCH", body: JSON.stringify(body) });
      setCharacters((current) => current.map((item) => item.id === updated.id ? updated : item));
      setMessage(success);
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : "Settings update failed");
    }
  }

  async function importSde() {
    setSdeBusy(true);
    setSettingsError(null);
    setMessage("Starting SDE import. Progress will update here while EQM keeps working...");
    try {
      const state = await api<SdeImportProgress>("/sde/import", { method: "POST", body: JSON.stringify({ source_path: sdePath }) });
      setSdeImportState(state);
      setSdeBusy(Boolean(state.running));
      setMessage("SDE import started. You can leave this page open and watch the progress badge.");
    } catch (err) {
      setMessage(null);
      setSdeBusy(false);
      setSettingsError(err instanceof Error ? err.message : "SDE import failed");
    }
  }

  useEffect(() => {
    void loadCharacters().catch((err) => setSettingsError(err instanceof Error ? err.message : "Unable to load settings"));
    void loadSdeStatus().catch((err) => currentUser.role === "admin" && setSettingsError(err instanceof Error ? err.message : "Unable to load SDE status"));
    void loadSdeImportState().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (currentUser.role !== "admin") return;
    const timer = window.setInterval(() => { void loadSdeImportState().catch(() => undefined); }, sdeBusy ? 3000 : 15000);
    return () => window.clearInterval(timer);
  }, [currentUser.role, sdeBusy]);

  const manageable = characters.filter((character) => character.can_manage || currentUser.role === "admin");
  const sdeProgressStats = sdeImportState?.stats;
  const sdeProgressLabel = sdeImportState?.running
    ? `${sdeImportState.stage ?? "working"}${sdeProgressStats?.type_dogma_attributes ? ` · ${sdeProgressStats.type_dogma_attributes.toLocaleString()} type dogma attrs` : ""}${sdeProgressStats?.type_dogma_effects ? ` · ${sdeProgressStats.type_dogma_effects.toLocaleString()} type effects` : ""}${sdeProgressStats?.blueprint_activities ? ` · ${sdeProgressStats.blueprint_activities.toLocaleString()} recipes` : ""}`
    : sdeImportState?.status === "success"
      ? `Last import complete${sdeImportState.completed_at ? ` at ${new Date(sdeImportState.completed_at).toLocaleString()}` : ""}`
      : sdeImportState?.status === "failed"
        ? sdeImportState.error ?? "Last import failed"
        : "No SDE import running";

  return (
    <div className="stacked">
      <section className="panel stacked">
        <h3>Character Privacy</h3>
        {message && <div className="notice inline">{message}</div>}
        {settingsError && <div className="mini-alert">{settingsError}</div>}
        {currentUser.role === "admin" && (
          <div className="privacy-placard">
            <label className="check"><input type="checkbox" checked={suppressPeekNotifications} onChange={(event) => void patchNotificationSuppression(event.target.checked)} /> Suppress sync peek notifications for development or mandatory-public ESI corporations</label>
          </div>
        )}
        <div className="card-list">
          {manageable.map((character) => (
            <article key={character.id}>
              <strong>{character.name}</strong>
              <span>{character.corporation_name ?? "Unknown corporation"}{character.owner_display_name ? ` · ${character.owner_display_name}` : ""}</span>
              <label className="check"><input type="checkbox" checked={Boolean(character.public_assets_visible)} onChange={(event) => void patchCharacter(character, { public_assets_visible: event.target.checked }, `${character.name} public asset visibility updated.`)} /> Public assets visible to members</label>
              <label className="check"><input type="checkbox" checked={Boolean(character.sync_opt_out)} onChange={(event) => void patchCharacter(character, { sync_opt_out: event.target.checked }, `${character.name} sync preference updated.`)} /> Keep this character private from shared Quartermaster sync</label>
              {character.sync_opt_out && <div className="privacy-placard">This character does not wish to be synced. Admins can override temporarily for administrative review, but this preference remains visible.</div>}
            </article>
          ))}
          {manageable.length === 0 && <p className="empty">No manageable characters found.</p>}
        </div>
      </section>
      {currentUser.role === "admin" && (
        <section className="panel stacked">
          <div className="section-heading">
            <div><h3>SDE Import</h3><p>Load EVE static data from a mounted SDE folder or zip inside the backend container.</p></div>
            <button type="button" onClick={() => { void loadSdeStatus(); void loadSdeImportState(); }}>Refresh</button>
          </div>
          <div className="status-grid compact">
            <Metric icon={<Database size={18} />} label="Categories" value={sdeStatus?.categories ?? 0} />
            <Metric icon={<Boxes size={18} />} label="Groups" value={sdeStatus?.groups ?? 0} />
            <Metric icon={<PackagePlus size={18} />} label="Types" value={sdeStatus?.types ?? 0} />
            <Metric icon={<MapIcon size={18} />} label="Systems" value={sdeStatus?.systems ?? 0} />
            <Metric icon={<MapIcon size={18} />} label="Stargates" value={sdeStatus?.stargates ?? 0} />
            <Metric icon={<Factory size={18} />} label="Recipes" value={sdeStatus?.blueprint_activities ?? 0} />
            <Metric icon={<ScrollText size={18} />} label="Inputs" value={sdeStatus?.activity_inputs ?? 0} />
            <Metric icon={<KeyRound size={18} />} label="Dogma attrs" value={sdeStatus?.dogma_attributes ?? sdeProgressStats?.dogma_attributes ?? 0} />
            <Metric icon={<KeyRound size={18} />} label="Dogma effects" value={sdeStatus?.dogma_effects ?? sdeProgressStats?.dogma_effects ?? 0} />
            <Metric icon={<KeyRound size={18} />} label="Type dogma" value={sdeStatus?.type_dogma_attributes ?? sdeProgressStats?.type_dogma_attributes ?? 0} />
            <Metric icon={<KeyRound size={18} />} label="Type effects" value={sdeStatus?.type_dogma_effects ?? sdeProgressStats?.type_dogma_effects ?? 0} />
          </div>
          {sdeImportState && <div className={sdeImportState.status === "failed" ? "mini-alert" : "notice inline"}>{sdeProgressLabel}</div>}
          <label>SDE path<input value={sdePath} onChange={(event) => setSdePath(event.target.value)} placeholder="/sde or /sde/sde.zip" /></label>
          <button type="button" disabled={sdeBusy} onClick={() => void importSde()}><RefreshCw size={18} /> {sdeBusy ? "Importing" : "Import SDE"}</button>
        </section>
      )}
      {currentUser.role === "admin" && <SectionModuleSettings api={api} />}
      {currentUser.role === "admin" && <PermissionsAdmin api={api} ManagedForm={ManagedForm} accountLabel={accountLabel} />}
    </div>
  );
}

function SectionModuleSettings({ api }: { api: ApiClient }) {
  const [settings, setSettings] = useState<SectionSettings | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadSettings() {
    setSettings(await api<SectionSettings>("/auth/sections/enabled"));
  }

  async function toggleSection(sectionKey: string) {
    if (!settings) return;

    const disabled = new Set(settings.disabled_sections);
    if (disabled.has(sectionKey)) disabled.delete(sectionKey);
    else disabled.add(sectionKey);

    setError(null);
    try {
      const updated = await api<SectionSettings>("/auth/sections/enabled", { method: "PATCH", body: JSON.stringify({ disabled_sections: Array.from(disabled) }) });
      setSettings(updated);
      const label = settings.sections.find((section) => section.key === sectionKey)?.label ?? sectionKey;
      setMessage(`${label} ${disabled.has(sectionKey) ? "disabled" : "enabled"}. Refresh signed-in sessions to apply navigation changes.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update section switches.");
    }
  }

  useEffect(() => {
    void loadSettings().catch((err) => setError(err instanceof Error ? err.message : "Unable to load section switches."));
  }, []);

  const protectedSections = new Set(["overview", "settings", "profile"]);

  return (
    <section className="panel stacked">
      <div className="section-heading">
        <div><h3>Section Switches</h3><p>Globally enable or disable major EQM modules without changing role permission rules.</p></div>
        <button type="button" onClick={() => void loadSettings()}>Refresh</button>
      </div>
      {message && <div className="notice inline">{message}</div>}
      {error && <div className="mini-alert">{error}</div>}
      <div className="section-toggle-grid">
        {settings?.sections.map((section) => {
          const disabled = settings.disabled_sections.includes(section.key);
          const locked = protectedSections.has(section.key);
          return <label key={section.key} className={`section-toggle-card ${disabled ? "disabled" : "enabled"}`}><input type="checkbox" checked={!disabled} disabled={locked} onChange={() => void toggleSection(section.key)} /><strong>{section.label}</strong><span>{locked ? "Always available" : disabled ? "Hidden globally" : "Enabled"}</span></label>;
        })}
        {!settings && <p className="empty">Loading section switches...</p>}
      </div>
    </section>
  );
}

function PermissionsAdmin({ api, ManagedForm, accountLabel }: { api: ApiClient; ManagedForm: ManagedFormComponent; accountLabel: (user: UserAccount) => string }) {
  const [matrix, setMatrix] = useState<PermissionMatrix | null>(null);
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const roles = matrix?.roles.filter((role) => role !== "admin") ?? [];

  async function loadPermissions() {
    const [permissionPayload, userRows] = await Promise.all([
      api<PermissionMatrix>("/auth/permissions"),
      api<UserAccount[]>("/auth/users"),
    ]);
    setMatrix(permissionPayload);
    setUsers(userRows);
  }

  function roleValue(role: string, section: string) {
    return matrix?.role_permissions.find((row) => row.role === role && row.section === section)?.can_view;
  }

  function userValue(userId: number, section: string) {
    return matrix?.user_permissions.find((row) => row.user_id === userId && row.section === section)?.can_view;
  }

  async function createRole(form: FormData) {
    setError(null);
    try {
      const role = await api<RoleDefinition>("/auth/roles", { method: "POST", body: JSON.stringify({ display_name: form.get("display_name"), name: form.get("name"), base_role: form.get("base_role") }) });
      setMessage(`${role.display_name} role created.`);
      await loadPermissions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create role");
    }
  }

  async function patchRole(role: string, section: string, value: string) {
    setError(null);
    await api(`/auth/permissions/roles/${role}`, { method: "PATCH", body: JSON.stringify({ section, can_view: value === "default" ? null : value === "allow" }) });
    setMessage(`${role} ${section} permission updated.`);
    await loadPermissions();
  }

  async function patchUser(userId: number, section: string, value: string) {
    setError(null);
    await api(`/auth/permissions/users/${userId}`, { method: "PATCH", body: JSON.stringify({ section, can_view: value === "inherit" ? null : value === "allow" }) });
    setMessage("User permission updated.");
    await loadPermissions();
  }

  useEffect(() => {
    void loadPermissions().catch((err) => setError(err instanceof Error ? err.message : "Unable to load permissions"));
  }, []);

  return (
    <section className="panel stacked">
      <div className="section-heading">
        <div><h3>Section Permissions</h3><p>Choose what roles can see, then add individual account exceptions where needed.</p></div>
        <button type="button" onClick={() => void loadPermissions()}>Refresh</button>
      </div>
      {message && <div className="notice inline">{message}</div>}
      {error && <div className="mini-alert">{error}</div>}
      <h4>Create role</h4>
      <ManagedForm submitLabel="Create role" onSubmit={createRole}>
        <label>Display name<input name="display_name" placeholder="Logistics" required /></label>
        <label>Machine name<input name="name" placeholder="logistics" /></label>
        <label>Base role<select name="base_role" defaultValue="member"><option value="view_only">View Only</option><option value="member">Member</option><option value="officer">Officer</option><option value="director">Director</option></select></label>
      </ManagedForm>
      <h4>Role defaults</h4>
      <div className="permission-grid">
        <div className="permission-header">Section</div>
        {roles.map((role) => <div key={role} className="permission-header">{role}</div>)}
        {matrix?.sections.map((section) => (
          <Fragment key={section.key}>
            <div><strong>{section.label}</strong><span>Default: {section.default_roles.join(", ")}</span></div>
            {roles.map((role) => {
              const value = roleValue(role, section.key);
              return <label key={`${role}-${section.key}`}><select value={value === undefined ? "default" : value ? "allow" : "deny"} onChange={(event) => void patchRole(role, section.key, event.target.value)}><option value="default">Default</option><option value="allow">Allow</option><option value="deny">Deny</option></select></label>;
            })}
          </Fragment>
        ))}
      </div>
      <h4>User overrides</h4>
      <div className="card-list permission-user-list">
        {users.filter((user) => user.role !== "admin").map((user) => (
          <article key={user.id}>
            <strong>{accountLabel(user)} <span className="muted">({user.role})</span></strong>
            <div className="permission-user-grid">
              {matrix?.sections.map((section) => {
                const value = userValue(user.id, section.key);
                return <label key={`${user.id}-${section.key}`}>{section.label}<select value={value === undefined ? "inherit" : value ? "allow" : "deny"} onChange={(event) => void patchUser(user.id, section.key, event.target.value)}><option value="inherit">Inherit</option><option value="allow">Allow</option><option value="deny">Deny</option></select></label>;
              })}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
