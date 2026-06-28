import { Activity, Boxes, Building2, Database, Factory, KeyRound, PackagePlus, Plus, RefreshCw, ScrollText, Sparkles, UserRoundCheck } from "lucide-react";
import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Health = { status: string; app: string };
type UserAccount = { id: number; email: string; display_name: string; role: string; created_at?: string };
type AuthResponse = { access_token: string; user: UserAccount };
type BootstrapStatus = { needs_admin: boolean; roles: string[] };
type InviteInfo = { email: string; role: string; expires_at?: string | null };
type UserInvite = { id: number; email: string; role: string; status?: string; created_by_display_name?: string | null; created_at?: string | null; expires_at?: string | null; accepted_at?: string | null; revoked_at?: string | null; invite_url?: string };
type Summary = { owners: number; locations: number; types: number; asset_stacks: number; asset_units: number; blueprints: number; industry_activities: number };
type Owner = { id: number; owner_kind: string; display_name: string; notes?: string };
type EveType = { type_id: number; name: string; group_id?: number; volume?: number };
type Location = { id: number; location_kind: string; name: string; notes?: string };
type Asset = { id: number; ownership_entity_id: number; owner_name: string; owner_kind?: string; type_id: number; type_name: string; quantity: number; location_name?: string; location_flag?: string; source: string; parent_asset_item_id?: number; parent_asset_type_name?: string };
type Blueprint = { id: number; owner_name: string; blueprint_type_id: number; blueprint_type_name: string; product_type_name?: string; material_efficiency: number; time_efficiency: number; runs_remaining?: number; is_copy: boolean; location_name?: string };
type ActivityInput = { id: number; input_type_name: string; quantity: number; consume_type: string };
type IndustryActivity = { id: number; activity_kind: string; blueprint_type_name: string; product_type_name?: string; product_quantity: number; time_seconds?: number; inputs: ActivityInput[] };
type EsiAuthInfo = { ready: boolean; message?: string; url?: string; required_scopes: string[] };
type LinkedCharacter = { token_id: number; character_id: number; character_name: string; scopes: string; access_token_expires_at?: string; linked_at?: string; last_sync_at?: string; last_sync_type?: string; last_sync_status?: string; missing_public_scopes: string[]; missing_standing_scopes: string[] };
type EqmCharacter = { id: number; character_id?: number; name: string; can_view_detail: boolean; owner_user_id?: number | null; owner_display_name?: string | null; owner_role?: string | null; corporation_name?: string | null; alliance_name?: string | null; public_assets_visible?: boolean; last_synced_at?: string | null; can_manage?: boolean; can_assign?: boolean };
type CorporationToken = { token_id: number; character_name: string; user_display_name: string; has_corporation_asset_scope: boolean; can_sync: boolean; has_corporation_blueprint_scope: boolean; can_sync_blueprints: boolean };
type EqmCorporation = { id: number; corporation_id: number; name: string; ticker?: string | null; alliance_name?: string | null; ceo_character_eve_id?: number | null; ceo_character_name?: string | null; member_count?: number | null; last_synced_at?: string | null; asset_rows: number; blueprint_rows: number; last_asset_sync_at?: string | null; last_asset_sync_status?: string | null; last_asset_sync_message?: string | null; asset_sync_stale?: boolean; last_blueprint_sync_at?: string | null; last_blueprint_sync_status?: string | null; last_blueprint_sync_message?: string | null; blueprint_sync_stale?: boolean; eligible_tokens: CorporationToken[] };
type ContactSample = { contact_id: number; name: string; contact_type?: string; standing: number; is_watched: boolean };
type ContactPreviewTarget = { token_id: number; character_id: number; character_name: string; create_count: number; update_count: number; skip_count: number; create_sample: ContactSample[]; update_sample: ContactSample[] };
type ContactSyncPreview = { source_character_name: string; source_contact_count: number; overwrite_existing: boolean; totals: { create: number; update: number; skip: number }; targets: ContactPreviewTarget[] };
type ContactApplyResult = { status: string; source_character_name: string; created: number; updated: number; targets: { character_name: string; created: number; updated: number; skipped: number }[] };

type AppData = {
  health: Health | null;
  summary: Summary | null;
  owners: Owner[];
  types: EveType[];
  locations: Location[];
  assets: Asset[];
  blueprints: Blueprint[];
  activities: IndustryActivity[];
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const APP_VERSION = "0.0.2-alpha";
const emptyData: AppData = { health: null, summary: null, owners: [], types: [], locations: [], assets: [], blueprints: [], activities: [] };
const numberFormatter = new Intl.NumberFormat();

function formatApiError(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const maybeMessage = (detail as { message?: unknown }).message;
    if (typeof maybeMessage === "string") return maybeMessage;
    const nestedDetail = (detail as { detail?: unknown }).detail;
    if (typeof nestedDetail === "string") return nestedDetail;
    return JSON.stringify(detail);
  }
  return "Request failed";
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("eq_access_token");
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...options,
  });
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    if (typeof payload === "string") {
      const detail = payload.trim() || response.statusText || "Request failed";
      throw new Error(`${response.status} ${detail}`);
    }
    throw new Error(formatApiError(payload.detail ?? payload.message ?? "Request failed"));
  }
  if (typeof payload === "string") throw new Error(`Unexpected non-JSON response from ${path}: ${payload.slice(0, 120)}`);
  return payload;
}

type AssetSortKey = "item" | "owner" | "quantity" | "location" | "flag";
type AssetFilterKey = Exclude<AssetSortKey, "quantity">;
type OwnerKindFilter = "character" | "corporation" | "alliance" | "manual_group";
type AssetFilter = { key: AssetFilterKey; value: string; label: string; mode: "exact" | "contains" };
type SortDirection = "asc" | "desc";

function asNumber(value: FormDataEntryValue | null) {
  if (value === null || value === "") return undefined;
  return Number(value);
}

function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [data, setData] = useState<AppData>(emptyData);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState<UserAccount | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapStatus | null>(null);
  const [authReady, setAuthReady] = useState(false);

  async function refreshAuth() {
    try {
      const boot = await api<BootstrapStatus>("/auth/bootstrap");
      setBootstrap(boot);
      const token = localStorage.getItem("eq_access_token");
      if (token && !boot.needs_admin) {
        setUser(await api<UserAccount>("/auth/me"));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication check failed.");
    } finally {
      setAuthReady(true);
    }
  }

  async function completeAuth(path: string, body: Record<string, unknown>) {
    const result = await api<AuthResponse>(path, { method: "POST", body: JSON.stringify(body) });
    localStorage.setItem("eq_access_token", result.access_token);
    setUser(result.user);
    setNotice(`Signed in as ${result.user.display_name}.`);
    if (new URLSearchParams(window.location.search).has("invite")) window.history.replaceState({}, "", window.location.pathname);
    await load();
  }

  function signOut() {
    localStorage.removeItem("eq_access_token");
    setUser(null);
    setData(emptyData);
    setActiveTab("overview");
  }

  async function load() {
    if (!localStorage.getItem("eq_access_token")) return;
    setLoading(true);
    setError(null);
    try {
      const [health, summary, owners, types, locations, assets, blueprints, activities] = await Promise.all([
        api<Health>("/health"),
        api<Summary>("/quartermaster/summary"),
        api<Owner[]>("/quartermaster/owners"),
        api<EveType[]>("/quartermaster/types"),
        api<Location[]>("/quartermaster/locations"),
        api<Asset[]>("/quartermaster/assets"),
        api<Blueprint[]>("/quartermaster/blueprints"),
        api<IndustryActivity[]>("/quartermaster/industry-activities"),
      ]);
      setData({ health, summary, owners, types, locations, assets, blueprints, activities });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend API is offline.");
    } finally {
      setLoading(false);
    }
  }

  async function seed() {
    const result = await api<{ status: string }>("/quartermaster/dev/seed", { method: "POST", body: "{}" });
    setNotice(result.status === "seeded" ? "Seed data added." : "Seed data was already present.");
    await load();
  }

  async function submit(path: string, body: Record<string, unknown>, success: string) {
    await api(path, { method: "POST", body: JSON.stringify(body) });
    setNotice(success);
    await load();
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (window.location.hash === "#esi" || params.get("esi_status")) setActiveTab("esi");
    if (params.get("esi_status")) {
      const characterName = params.get("character_name") ?? "Character";
      const status = params.get("esi_status") === "updated" ? "updated" : "linked";
      const addedScopes = (params.get("added_scopes") ?? "").split(",").filter(Boolean);
      const removedScopes = (params.get("removed_scopes") ?? "").split(",").filter(Boolean);
      const scopeNote = addedScopes.length > 0 ? ` Added ${addedScopes.length} scope${addedScopes.length === 1 ? "" : "s"}.` : removedScopes.length > 0 ? ` Removed ${removedScopes.length} scope${removedScopes.length === 1 ? "" : "s"}.` : "";
      setNotice(`${characterName} ${status} through EVE SSO.${scopeNote}`);
      window.history.replaceState({}, "", "/#esi");
    }
    void refreshAuth().then(() => {
      if (localStorage.getItem("eq_access_token")) void load();
    });
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 3000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const typeOptions = useMemo(() => data.types.map((type) => <option key={type.type_id} value={type.type_id}>{type.name}</option>), [data.types]);
  const ownerOptions = useMemo(() => data.owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.display_name}</option>), [data.owners]);
  const locationOptions = useMemo(() => data.locations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>), [data.locations]);
  const activityOptions = useMemo(() => data.activities.map((activity) => <option key={activity.id} value={activity.id}>{activity.blueprint_type_name} - {activity.activity_kind}</option>), [data.activities]);

  const inviteToken = new URLSearchParams(window.location.search).get("invite");
  if (!authReady) return <main className="auth-shell"><section className="panel"><img className="auth-logo" src="/eqm-logo.png" alt="EVE Quartermaster" /><p className="muted">Checking account session...</p></section></main>;
  if (!user && inviteToken) return <InviteScreen token={inviteToken} onAuth={completeAuth} />;
  if (!user) return <AuthScreen bootstrap={bootstrap} onAuth={completeAuth} />;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <img className="brand-logo" src="/eqm-logo.png" alt="EVE Quartermaster" />
        <div>
          <h1>eve-quartermaster</h1>
          <p>Inventory, ownership, and industry planning for EVE Online.</p>
        </div>
        <nav>
          <button className={activeTab === "overview" ? "active" : ""} onClick={() => setActiveTab("overview")}><Database size={18} /> Overview</button>
          <button className={activeTab === "ownership" ? "active" : ""} onClick={() => setActiveTab("ownership")}><Boxes size={18} /> Ownership</button>
          <button className={activeTab === "characters" ? "active" : ""} onClick={() => setActiveTab("characters")}><UserRoundCheck size={18} /> Characters</button>
          {!["member", "view_only"].includes(user.role) && <button className={activeTab === "corporations" ? "active" : ""} onClick={() => setActiveTab("corporations")}><Building2 size={18} /> Corporations</button>}
          <button className={activeTab === "assets" ? "active" : ""} onClick={() => setActiveTab("assets")}><PackagePlus size={18} /> Assets</button>
          <button className={activeTab === "industry" ? "active" : ""} onClick={() => setActiveTab("industry")}><Factory size={18} /> Industry</button>
          <button className={activeTab === "esi" ? "active" : ""} onClick={() => setActiveTab("esi")}><KeyRound size={18} /> ESI Sync</button>
          {user.role === "admin" && <button className={activeTab === "users" ? "active" : ""} onClick={() => setActiveTab("users")}><UserRoundCheck size={18} /> Users</button>}
        </nav>
      </aside>

      <section className="content">
        <header className="hero compact">
          <div>
            <span className="eyebrow">Quartermaster Console</span>
            <h2>{titleFor(activeTab)}</h2>
            <p>{subtitleFor(activeTab)}</p>
          </div>
          <div className="toolbar">
            <span className="status-badge version-badge">v{APP_VERSION}</span>
            <span className="status-badge">{user.display_name}</span>
            <span className="status-badge rank-badge">{user.role}</span>
            <button onClick={() => void seed()}><Sparkles size={18} /> Seed</button>
            <button onClick={() => void load()}><RefreshCw size={18} /> {loading ? "Refreshing" : "Refresh"}</button>
            <button onClick={signOut}>Sign out</button>
          </div>
        </header>

        {error && <div className="alert">{error}</div>}
        {notice && <div className="notice">{notice}</div>}

        {activeTab === "overview" && <Overview data={data} />}
        {activeTab === "ownership" && <Ownership data={data} submit={submit} />}
        {activeTab === "characters" && <Characters currentUser={user} />}
        {activeTab === "corporations" && <Corporations loadAssets={load} />}
        {activeTab === "assets" && <Assets data={data} submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} />}
        {activeTab === "industry" && <Industry data={data} submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} activityOptions={activityOptions} />}
        {activeTab === "esi" && <Esi load={load} />}
        {activeTab === "users" && user.role === "admin" && <UsersAdmin currentUser={user} />}
      </section>
    </main>
  );
}

function AuthScreen({ bootstrap, onAuth }: { bootstrap: BootstrapStatus | null; onAuth: (path: string, body: Record<string, unknown>) => Promise<void> }) {
  const needsAdmin = bootstrap?.needs_admin ?? false;
  return (
    <main className="auth-shell">
      <section className="panel auth-panel">
        <img className="auth-logo" src="/eqm-logo.png" alt="EVE Quartermaster" />
        <span className="status-badge version-badge auth-version">v{APP_VERSION}</span>
        <h2>{needsAdmin ? "Create Admin Account" : "Sign In"}</h2>
        <p className="muted">{needsAdmin ? "Set up the first Quartermaster administrator." : "Use your Quartermaster account before linking EVE characters."}</p>
        <ManagedForm submitLabel={needsAdmin ? "Create admin" : "Sign in"} onSubmit={(form) => onAuth(needsAdmin ? "/auth/bootstrap" : "/auth/login", { email: form.get("email"), password: form.get("password"), display_name: form.get("display_name") })}>
          {needsAdmin && <label>Display name<input name="display_name" required placeholder="Quartermaster" /></label>}
          <label>Email<input name="email" type="email" required placeholder="you@example.com" /></label>
          <label>Password<input name="password" type="password" minLength={8} required /></label>
        </ManagedForm>
      </section>
    </main>
  );
}


function InviteScreen({ token, onAuth }: { token: string; onAuth: (path: string, body: Record<string, unknown>) => Promise<void> }) {
  const [invite, setInvite] = useState<InviteInfo | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);

  useEffect(() => {
    void api<InviteInfo>(`/auth/invites/${token}`)
      .then(setInvite)
      .catch((err) => setInviteError(err instanceof Error ? err.message : "Invite could not be loaded"));
  }, [token]);

  return (
    <main className="auth-shell">
      <section className="panel auth-panel">
        <img className="auth-logo" src="/eqm-logo.png" alt="EVE Quartermaster" />
        <span className="status-badge version-badge auth-version">v{APP_VERSION}</span>
        <h2>Accept Invite</h2>
        {inviteError && <div className="mini-alert">{inviteError}</div>}
        {invite ? <>
          <p className="muted">Create your Quartermaster account for {invite.email}.</p>
          <div className="invite-summary"><span>Assigned role</span><strong>{invite.role}</strong></div>
          <ManagedForm submitLabel="Create account" onSubmit={(form) => onAuth(`/auth/invites/${token}/accept`, { display_name: form.get("display_name"), password: form.get("password") })}>
            <label>Display name<input name="display_name" required placeholder="Quartermaster" /></label>
            <label>Password<input name="password" type="password" minLength={8} required /></label>
          </ManagedForm>
        </> : !inviteError ? <p className="muted">Checking invite...</p> : null}
      </section>
    </main>
  );
}
function UsersAdmin({ currentUser }: { currentUser: UserAccount }) {
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [invites, setInvites] = useState<UserInvite[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [latestInviteUrl, setLatestInviteUrl] = useState<string | null>(null);
  const [userError, setUserError] = useState<string | null>(null);
  const roles = ["admin", "director", "officer", "member", "view_only"];

  async function runUserAction(action: () => Promise<string>, refreshInvites = false) {
    setUserError(null);
    try {
      const nextMessage = await action();
      setMessage(nextMessage);
      await loadUsers();
      if (refreshInvites) await loadInvites();
    } catch (err) {
      setUserError(err instanceof Error ? err.message : "User action failed");
    }
  }

  async function loadUsers() {
    setUsers(await api<UserAccount[]>("/auth/users"));
  }

  async function loadInvites() {
    setInvites(await api<UserInvite[]>("/auth/invites"));
  }

  async function createAccount(form: FormData) {
    await runUserAction(async () => {
      const user = await api<UserAccount>("/auth/users", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), display_name: form.get("display_name"), password: form.get("password"), role: form.get("role") }),
      });
      return `${user.display_name} created.`;
    });
  }

  async function createInvite(form: FormData) {
    await runUserAction(async () => {
      const invite = await api<UserInvite>("/auth/invites", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), role: form.get("role") }),
      });
      if (invite.invite_url) {
        setLatestInviteUrl(invite.invite_url);
        await navigator.clipboard.writeText(invite.invite_url).catch(() => undefined);
      }
      return `Invite generated for ${invite.email}.`;
    }, true);
  }

  async function updateRole(userId: number, role: string) {
    await runUserAction(async () => {
      const user = await api<UserAccount>(`/auth/users/${userId}`, { method: "PATCH", body: JSON.stringify({ role }) });
      return `${user.display_name} is now ${user.role}.`;
    });
  }

  async function resetPassword(userId: number, form: FormData) {
    await runUserAction(async () => {
      const user = await api<UserAccount>(`/auth/users/${userId}`, { method: "PATCH", body: JSON.stringify({ password: form.get("password") }) });
      return `${user.display_name}'s password was reset.`;
    });
  }

  async function deleteAccount(user: UserAccount) {
    if (!window.confirm(`Delete ${user.display_name}? This unlinks their ESI tokens and cannot be undone.`)) return;
    await runUserAction(async () => {
      await api<{ status: string }>(`/auth/users/${user.id}`, { method: "DELETE" });
      return `${user.display_name} deleted.`;
    });
  }

  async function revokeInvite(invite: UserInvite) {
    if (!window.confirm(`Revoke invite for ${invite.email}?`)) return;
    await runUserAction(async () => {
      await api<UserInvite>(`/auth/invites/${invite.id}`, { method: "DELETE" });
      return `Invite for ${invite.email} revoked.`;
    }, true);
  }

  useEffect(() => {
    void Promise.all([loadUsers(), loadInvites()]).catch((err) => setUserError(err instanceof Error ? err.message : "Unable to load users"));
  }, []);

  return (
    <div className="two-column">
      <section className="panel stacked">
        <h3>Accounts</h3>
        {message && <div className="notice inline">{message}</div>}
        {latestInviteUrl && <div className="invite-link"><code>{latestInviteUrl}</code><button type="button" onClick={() => void navigator.clipboard.writeText(latestInviteUrl)}>Copy link</button></div>}
        {userError && <div className="mini-alert">{userError}</div>}
        <div className="card-list">{users.map((user) => <article key={user.id}>
          <strong>{user.display_name}</strong>
          <span>{user.email}</span>
          <label>Role<select value={user.role} onChange={(event) => void updateRole(user.id, event.target.value)}>{roles.map((role) => <option key={role} value={role}>{role}</option>)}</select></label>
          <ManagedForm submitLabel="Reset password" onSubmit={(form) => resetPassword(user.id, form)}>
            <label>New password<input name="password" type="password" minLength={8} required /></label>
          </ManagedForm>
          <div className="card-actions">
            <button className="danger" type="button" disabled={user.id === currentUser.id} onClick={() => void deleteAccount(user)}>{user.id === currentUser.id ? "Signed in" : "Delete user"}</button>
          </div>
        </article>)}</div>
      </section>
      <section className="panel stacked">
        <h3>Create Invite</h3>
        <ManagedForm submitLabel="Generate invite" onSubmit={createInvite}>
          <label>Email<input name="email" type="email" required /></label>
          <label>Role<select name="role" defaultValue="member">{roles.map((role) => <option key={role} value={role}>{role}</option>)}</select></label>
        </ManagedForm>
        <h3>Pending Invites</h3>
        <div className="card-list invite-list">{invites.map((invite) => <article key={invite.id}>
          <strong>{invite.email}</strong>
          <span>{invite.role} · {invite.status ?? "pending"}</span>
          <span>Created {invite.created_at ? new Date(invite.created_at).toLocaleString() : "recently"}{invite.created_by_display_name ? ` by ${invite.created_by_display_name}` : ""}</span>
          {invite.accepted_at && <span>Accepted {new Date(invite.accepted_at).toLocaleString()}</span>}
          {invite.revoked_at && <span>Revoked {new Date(invite.revoked_at).toLocaleString()}</span>}
          <div className="card-actions"><button className="danger" type="button" disabled={invite.status !== "pending"} onClick={() => void revokeInvite(invite)}>Revoke</button></div>
        </article>)}{invites.length === 0 && <p className="empty">No invites yet.</p>}</div>
        <h3>Create Account Manually</h3>
        <ManagedForm submitLabel="Create account" onSubmit={createAccount}>
          <label>Display name<input name="display_name" required /></label>
          <label>Email<input name="email" type="email" required /></label>
          <label>Role<select name="role" defaultValue="member">{roles.map((role) => <option key={role} value={role}>{role}</option>)}</select></label>
          <label>Temporary password<input name="password" type="password" minLength={8} required /></label>
        </ManagedForm>
      </section>
    </div>
  );
}function Overview({ data }: { data: AppData }) {
  const summary = data.summary;
  return (
    <>
      <div className="status-grid wide">
        <Metric icon={<Activity size={22} />} label="API status" value={data.health?.status ?? "checking"} />
        <Metric icon={<Database size={22} />} label="Backend app" value={data.health?.app ?? "pending"} />
        <Metric icon={<Boxes size={22} />} label="Owners" value={summary?.owners ?? 0} />
        <Metric icon={<PackagePlus size={22} />} label="Asset units" value={summary?.asset_units ?? 0} />
        <Metric icon={<ScrollText size={22} />} label="Blueprints" value={summary?.blueprints ?? 0} />
        <Metric icon={<Factory size={22} />} label="Recipes" value={summary?.industry_activities ?? 0} />
      </div>
      <div className="two-column">
        <section className="panel"><h3>Recent Assets</h3><AssetTable assets={data.assets.slice(0, 6)} /></section>
        <section className="panel"><h3>Blueprint Library</h3><BlueprintList blueprints={data.blueprints} /></section>
      </div>
    </>
  );
}

function Characters({ currentUser }: { currentUser: UserAccount }) {
  const [characters, setCharacters] = useState<EqmCharacter[]>([]);
  const [accounts, setAccounts] = useState<UserAccount[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [characterError, setCharacterError] = useState<string | null>(null);
  const canAssign = ["admin", "director"].includes(currentUser.role);

  async function loadCharacters() {
    setCharacters(await api<EqmCharacter[]>("/characters"));
    if (canAssign) setAccounts(await api<UserAccount[]>("/characters/accounts"));
  }

  async function patchCharacter(characterId: number, body: Record<string, unknown>, success: string) {
    setCharacterError(null);
    try {
      const updated = await api<EqmCharacter>(`/characters/${characterId}`, { method: "PATCH", body: JSON.stringify(body) });
      setCharacters((current) => current.map((character) => character.id === updated.id ? updated : character));
      setMessage(success);
    } catch (err) {
      setCharacterError(err instanceof Error ? err.message : "Character update failed");
    }
  }

  useEffect(() => { void loadCharacters().catch((err) => setCharacterError(err instanceof Error ? err.message : "Unable to load characters")); }, []);

  return <section className="panel stacked"><h3>Characters</h3>{message && <div className="notice inline">{message}</div>}{characterError && <div className="mini-alert">{characterError}</div>}<div className="card-list character-list">{characters.map((character) => <article key={character.id}><strong>{character.name}</strong>{character.character_id && <span>Character ID {character.character_id}</span>}{character.can_view_detail ? <><span>{character.owner_display_name ?? "Unassigned"}{character.owner_role ? ` · ${character.owner_role}` : ""}</span><span>{character.corporation_name ?? "Unknown corporation"}{character.alliance_name ? ` · ${character.alliance_name}` : ""}</span><span>Last sync {character.last_synced_at ? new Date(character.last_synced_at).toLocaleString() : "never"}</span>{character.can_assign && <label>EQM Account<select value={character.owner_user_id ?? ""} onChange={(event) => void patchCharacter(character.id, { owner_user_id: event.target.value || null }, `${character.name} reassigned.`)}><option value="">Unassigned</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.display_name} ({account.role})</option>)}</select></label>}{character.can_manage && <label className="check"><input type="checkbox" checked={Boolean(character.public_assets_visible)} onChange={(event) => void patchCharacter(character.id, { public_assets_visible: event.target.checked }, `${character.name} visibility updated.`)} /> Public assets visible to members</label>}</> : <span className="muted">Details hidden by role policy.</span>}</article>)}</div>{characters.length === 0 && <p className="empty">No characters visible to this account yet.</p>}</section>;
}
function Corporations({ loadAssets }: { loadAssets: () => Promise<void> }) {
  const [corporations, setCorporations] = useState<EqmCorporation[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [corpError, setCorpError] = useState<string | null>(null);
  const [busyTokenId, setBusyTokenId] = useState<number | null>(null);
  const [busyAll, setBusyAll] = useState(false);

  async function loadCorporations() {
    setCorporations(await api<EqmCorporation[]>("/corporations"));
  }

  async function refreshCorporationLinks() {
    setCorpError(null);
    setMessage("Refreshing corporation links from enrolled characters...");
    try {
      const result = await api<{ characters_refreshed: number; skipped: number }>("/esi/sync/linked-corporations", { method: "POST", body: "{}" });
      setMessage(`Refreshed ${result.characters_refreshed.toLocaleString()} linked character corporation record${result.characters_refreshed === 1 ? "" : "s"}.`);
      await loadCorporations();
    } catch (err) {
      setCorpError(err instanceof Error ? err.message : "Corporation discovery failed");
    }
  }

  async function syncCorporationAssets(token: CorporationToken, corporation: EqmCorporation) {
    setBusyTokenId(token.token_id);
    setCorpError(null);
    setMessage(`Syncing ${corporation.name} assets with ${token.character_name}...`);
    try {
      const result = await api<{ corporation_name: string; asset_rows: number }>(`/esi/sync/corporation-assets/${token.token_id}`, { method: "POST", body: "{}" });
      setMessage(`Synced ${result.asset_rows.toLocaleString()} asset rows for ${result.corporation_name}.`);
      await Promise.all([loadCorporations(), loadAssets()]);
    } catch (err) {
      setCorpError(err instanceof Error ? err.message : "Corporation asset sync failed");
    } finally {
      setBusyTokenId(null);
    }
  }

  async function syncCorporationBlueprints(token: CorporationToken, corporation: EqmCorporation) {
    setBusyTokenId(token.token_id);
    setCorpError(null);
    setMessage(`Syncing ${corporation.name} blueprints with ${token.character_name}...`);
    try {
      const result = await api<{ corporation_name: string; blueprint_rows: number }>(`/esi/sync/corporation-blueprints/${token.token_id}`, { method: "POST", body: "{}" });
      setMessage(`Synced ${result.blueprint_rows.toLocaleString()} blueprint rows for ${result.corporation_name}.`);
      await loadCorporations();
    } catch (err) {
      setCorpError(err instanceof Error ? err.message : "Corporation blueprint sync failed");
    } finally {
      setBusyTokenId(null);
    }
  }

  async function syncAllEligible() {
    setBusyAll(true);
    setCorpError(null);
    let assetJobs = 0;
    let blueprintJobs = 0;
    try {
      for (const corporation of corporations) {
        const assetToken = corporation.eligible_tokens.find((token) => token.can_sync);
        if (assetToken) {
          await api(`/esi/sync/corporation-assets/${assetToken.token_id}`, { method: "POST", body: "{}" });
          assetJobs += 1;
        }
        const blueprintToken = corporation.eligible_tokens.find((token) => token.can_sync_blueprints);
        if (blueprintToken) {
          await api(`/esi/sync/corporation-blueprints/${blueprintToken.token_id}`, { method: "POST", body: "{}" });
          blueprintJobs += 1;
        }
      }
      setMessage(`Synced ${assetJobs} corporation asset ledger${assetJobs === 1 ? "" : "s"} and ${blueprintJobs} blueprint ledger${blueprintJobs === 1 ? "" : "s"}.`);
      await Promise.all([loadCorporations(), loadAssets()]);
    } catch (err) {
      setCorpError(err instanceof Error ? err.message : "Sync all failed");
    } finally {
      setBusyAll(false);
    }
  }

  useEffect(() => { void loadCorporations().catch((err) => setCorpError(err instanceof Error ? err.message : "Unable to load corporations")); }, []);

  return <section className="panel stacked"><div className="section-heading"><h3>Corporations</h3><div className="button-row compact"><button type="button" onClick={() => void refreshCorporationLinks()}>Refresh corporation links</button><button type="button" disabled={busyAll || corporations.length === 0} onClick={() => void syncAllEligible()}>{busyAll ? "Syncing all" : "Sync all eligible"}</button></div></div>{message && <div className="notice inline">{message}</div>}{corpError && <div className="mini-alert">{corpError}</div>}<div className="card-list corporation-list">{corporations.map((corporation) => <article key={corporation.id}><strong>{corporation.name}{corporation.ticker ? ` [${corporation.ticker}]` : ""}</strong><span>{corporation.alliance_name ?? "No alliance"} · Corp ID {corporation.corporation_id}</span><span>CEO {corporation.ceo_character_name ?? corporation.ceo_character_eve_id ?? "unknown"} · Members {corporation.member_count?.toLocaleString() ?? "unknown"}</span><span>{corporation.asset_rows.toLocaleString()} tracked asset rows · {corporation.blueprint_rows.toLocaleString()} blueprints</span><span className={corporation.asset_sync_stale ? "scope-warn" : "scope-ok"}>Assets {corporation.last_asset_sync_at ? `${new Date(corporation.last_asset_sync_at).toLocaleString()} (${corporation.last_asset_sync_status ?? "sync"})` : "never synced"}</span><span className={corporation.blueprint_sync_stale ? "scope-warn" : "scope-ok"}>Blueprints {corporation.last_blueprint_sync_at ? `${new Date(corporation.last_blueprint_sync_at).toLocaleString()} (${corporation.last_blueprint_sync_status ?? "sync"})` : "never synced"}</span>{corporation.last_asset_sync_message && <code>{corporation.last_asset_sync_message}</code>}{corporation.last_blueprint_sync_message && <code>{corporation.last_blueprint_sync_message}</code>}<div className="choice-list"><span>Corp sync tokens</span>{corporation.eligible_tokens.length > 0 ? corporation.eligible_tokens.map((token) => <div className="token-row" key={token.token_id}><span>{token.character_name} · {token.user_display_name}</span><div className="button-row compact">{token.has_corporation_asset_scope ? <button type="button" disabled={!token.can_sync || busyTokenId === token.token_id} onClick={() => void syncCorporationAssets(token, corporation)}>Assets</button> : <span className="scope-warn">Missing asset scope</span>}{token.has_corporation_blueprint_scope ? <button type="button" disabled={!token.can_sync_blueprints || busyTokenId === token.token_id} onClick={() => void syncCorporationBlueprints(token, corporation)}>Blueprints</button> : <span className="scope-warn">Missing blueprint scope</span>}</div></div>) : <p className="muted">No linked character tokens found for this corporation yet.</p>}</div></article>)}</div>{corporations.length === 0 && <p className="empty">No corporations imported or linked yet. Re-link a CEO/director through EVE SSO to populate this list.</p>}</section>;
}function Ownership({ data, submit }: { data: AppData; submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void> }) {
  return (
    <div className="two-column">
      <section className="panel">
        <h3>Owners</h3>
        <div className="card-list">{data.owners.map((owner) => <article key={owner.id}><strong>{owner.display_name}</strong><span>{owner.owner_kind.replace("_", " ")}</span></article>)}</div>
      </section>
      <section className="panel"><h3>Add Owner</h3><OwnerForm submit={submit} /></section>
      <section className="panel"><h3>Locations</h3><div className="card-list">{data.locations.map((location) => <article key={location.id}><strong>{location.name}</strong><span>{location.location_kind}</span></article>)}</div></section>
      <section className="panel"><h3>Add Location</h3><LocationForm submit={submit} /></section>
    </div>
  );
}

function Assets({ data, submit, ownerOptions, typeOptions, locationOptions }: { data: AppData; submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void>; ownerOptions: React.ReactNode; typeOptions: React.ReactNode; locationOptions: React.ReactNode }) {
  return <div className="two-column main-heavy"><section className="panel"><h3>Tracked Assets</h3><AssetTable assets={data.assets} /></section><section className="panel"><h3>Add Asset</h3><AssetForm submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} /></section></div>;
}

function Industry({ data, submit, ownerOptions, typeOptions, locationOptions, activityOptions }: { data: AppData; submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void>; ownerOptions: React.ReactNode; typeOptions: React.ReactNode; locationOptions: React.ReactNode; activityOptions: React.ReactNode }) {
  return (
    <div className="two-column">
      <section className="panel"><h3>Blueprints</h3><BlueprintList blueprints={data.blueprints} /></section>
      <section className="panel"><h3>Add Blueprint</h3><BlueprintForm submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} /></section>
      <section className="panel"><h3>Recipes</h3><RecipeList activities={data.activities} /></section>
      <section className="panel stacked"><h3>Add Recipe</h3><RecipeForm submit={submit} typeOptions={typeOptions} /><h3>Add Recipe Input</h3><RecipeInputForm submit={submit} typeOptions={typeOptions} activityOptions={activityOptions} /></section>
    </div>
  );
}

function Esi({ load }: { load: () => Promise<void> }) {
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
    setTargetTokenIds((current) => current.filter((id) => id !== tokenId));
    setSourceTokenId((current) => current === tokenId ? "" : current);
    await loadEsiState();
  }

  function toggleTarget(tokenId: number) {
    setContactPreview(null);
    setTargetTokenIds((current) => current.includes(tokenId) ? current.filter((id) => id !== tokenId) : [...current, tokenId]);
  }

  async function previewContactSync() {
    if (sourceTokenId === "") return;
    setContactBusy(true);
    setMessage(null);
    try {
      const preview = await api<ContactSyncPreview>("/esi/standings/preview", {
        method: "POST",
        body: JSON.stringify({ source_token_id: sourceTokenId, target_token_ids: targetTokenIds, overwrite_existing: overwriteContacts }),
      });
      setContactPreview(preview);
      setMessage(`Preview ready: ${preview.totals.create.toLocaleString()} create, ${preview.totals.update.toLocaleString()} update.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Standing sync preview failed.");
    } finally {
      setContactBusy(false);
    }
  }

  async function applyContactSync() {
    if (sourceTokenId === "") return;
    setContactBusy(true);
    try {
      const result = await api<ContactApplyResult>("/esi/standings/apply", {
        method: "POST",
        body: JSON.stringify({ source_token_id: sourceTokenId, target_token_ids: targetTokenIds, overwrite_existing: overwriteContacts }),
      });
      setMessage(`Copied standings from ${result.source_character_name}: ${result.created.toLocaleString()} created, ${result.updated.toLocaleString()} updated.`);
      setContactPreview(null);
      await loadEsiState();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Standing sync failed.");
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
    return missing.length === 0 ? <span className="scope-ok">{kind === "public" ? "Core scopes current" : "Standing scopes current"}</span> : <span className="scope-warn">Missing {kind === "public" ? "core" : "standing"} scopes: {missing.join(", ")}</span>;
  }

  return (
    <div className="two-column">
      <section className="panel stacked">
        <h3>Linked Characters</h3>
        {linked.length > 0 ? <div className="card-list">{linked.map((character) => <article key={character.token_id}><strong>{character.character_name}</strong><span>Character ID {character.character_id}</span><span>Last sync {character.last_sync_at ? `${new Date(character.last_sync_at).toLocaleString()} (${character.last_sync_type ?? "sync"})` : "never"}</span><span>Linked {character.linked_at ? new Date(character.linked_at).toLocaleString() : "recently"}</span>{scopeStatus(character, "public")}{scopeStatus(character, "standing")}<div className="card-actions"><button type="button" onClick={() => void syncAssets(character.token_id, character.character_name)}>Sync assets</button>{character.missing_standing_scopes.length > 0 && standingAuthInfo?.ready ? <a className="mini-link" href={standingAuthInfo.url}>Authorize standing sync</a> : null}<button className="danger" type="button" onClick={() => void unlinkCharacter(character.token_id, character.character_name)}>Unlink</button></div></article>)}</div> : <p className="muted">No EVE characters linked yet.</p>}
        <h3>Authenticated Sync</h3>
        {authInfo?.ready ? <a className="auth-link" href={authInfo.url}>Start EVE SSO</a> : <p className="muted">{authInfo?.message ?? "Checking SSO setup..."}</p>}
        <div className="scope-list">{authInfo?.required_scopes.map((scope) => <code key={scope}>{scope}</code>)}</div>
      </section>

      <section className="panel stacked">
        <h3><UserRoundCheck size={20} /> Character Standing Sync</h3>
        {standingAuthInfo?.ready ? <a className="auth-link secondary" href={standingAuthInfo.url}>Authorize standing sync</a> : <p className="muted">{standingAuthInfo?.message ?? "Checking standing sync setup..."}</p>}
        <div className="scope-list compact">{standingAuthInfo?.required_scopes.map((scope) => <code key={scope}>{scope}</code>)}</div>
        <label>Copy standings from<select value={sourceTokenId} onChange={(event) => { setSourceTokenId(Number(event.target.value)); setTargetTokenIds([]); setContactPreview(null); }}><option value="">Choose source</option>{linked.map((character) => <option key={character.token_id} value={character.token_id}>{character.character_name}</option>)}</select></label>
        <div className="choice-list">
          <span>Copy to</span>
          {targetOptions.length > 0 ? targetOptions.map((character) => <label className="check" key={character.token_id}><input type="checkbox" checked={targetTokenIds.includes(character.token_id)} onChange={() => toggleTarget(character.token_id)} /> {character.character_name}</label>) : <p className="muted">Link at least one more character before syncing standings.</p>}
        </div>
        <label className="check"><input type="checkbox" checked={overwriteContacts} onChange={(event) => { setOverwriteContacts(event.target.checked); setContactPreview(null); }} /> Update existing target contacts when standings differ</label>
        <div className="button-row"><button type="button" disabled={sourceTokenId === "" || targetTokenIds.length === 0 || contactBusy} onClick={() => void previewContactSync()}>Preview</button><button type="button" disabled={!contactPreview || contactBusy} onClick={() => void applyContactSync()}>Apply sync</button></div>
        {contactPreview && <ContactPreview preview={contactPreview} />}
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

function ContactPreview({ preview }: { preview: ContactSyncPreview }) {
  return <div className="contact-preview"><strong>{preview.source_character_name}: {preview.source_contact_count.toLocaleString()} source standings</strong><div className="status-grid compact"><Metric icon={<Plus size={18} />} label="Creates" value={preview.totals.create} /><Metric icon={<RefreshCw size={18} />} label="Updates" value={preview.totals.update} /><Metric icon={<UserRoundCheck size={18} />} label="Skipped" value={preview.totals.skip} /></div>{preview.targets.map((target) => <article key={target.token_id}><strong>{target.character_name}</strong><span>{target.create_count.toLocaleString()} create · {target.update_count.toLocaleString()} update · {target.skip_count.toLocaleString()} skip</span>{[...target.create_sample, ...target.update_sample].slice(0, 8).map((contact) => <code key={`${target.token_id}-${contact.contact_id}`}>{contact.name}: {contact.standing}</code>)}</article>)}</div>;
}
function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return <article>{icon}<span>{label}</span><strong>{typeof value === "number" ? numberFormatter.format(value) : value}</strong></article>;
}

function AssetTable({ assets }: { assets: Asset[] }) {
  const [sortKey, setSortKey] = useState<AssetSortKey>("item");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [filter, setFilter] = useState<AssetFilter | null>(null);
  const [searchTerms, setSearchTerms] = useState<Record<AssetFilterKey, string>>({ item: "", owner: "", location: "", flag: "" });
  const [copyNotice, setCopyNotice] = useState<string | null>(null);
  const [ownerKindFilter, setOwnerKindFilter] = useState<OwnerKindFilter | "">("");
  const filterLabels: Record<AssetFilterKey, string> = { item: "Item", owner: "Owner", location: "Location", flag: "Flag" };

  function toggleSort(nextKey: AssetSortKey) {
    if (nextKey === sortKey) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "quantity" ? "desc" : "asc");
  }

  function sortValue(asset: Asset, key: AssetSortKey) {
    switch (key) {
      case "item": return asset.type_name ?? "";
      case "owner": return asset.owner_name ?? "";
      case "quantity": return asset.quantity ?? 0;
      case "location": return asset.location_name ?? "";
      case "flag": return asset.location_flag ?? "";
    }
  }

  function filterValue(asset: Asset, key: AssetFilterKey) {
    return String(sortValue(asset, key) || "-");
  }

  function applyFilter(key: AssetFilterKey, value: string, mode: AssetFilter["mode"] = "exact") {
    if (!value || value === "-") return;
    setFilter({ key, value, label: filterLabels[key], mode });
    setSearchTerms({ item: "", owner: "", location: "", flag: "", [key]: mode === "contains" ? value : "" });
    setCopyNotice(null);
  }

  function applySearch(key: AssetFilterKey, value: string) {
    setSearchTerms({ item: "", owner: "", location: "", flag: "", [key]: value });
    setCopyNotice(null);
    const trimmed = value.trim();
    if (!trimmed) {
      setFilter(null);
      return;
    }
    setFilter({ key, value: trimmed, label: filterLabels[key], mode: "contains" });
  }

  function clearFilter() {
    setFilter(null);
    setSearchTerms({ item: "", owner: "", location: "", flag: "" });
    setCopyNotice(null);
  }

  const filterOptions = useMemo(() => {
    const keys: AssetFilterKey[] = ["item", "owner", "location", "flag"];
    return Object.fromEntries(keys.map((key) => [key, [...new Set(assets.map((asset) => filterValue(asset, key)).filter((value) => value !== "-"))].sort((left, right) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }))])) as Record<AssetFilterKey, string[]>;
  }, [assets]);

  function matchesFilter(asset: Asset) {
    if (ownerKindFilter && asset.owner_kind !== ownerKindFilter) return false;
    if (!filter) return true;
    const value = filterValue(asset, filter.key);
    if (filter.mode === "contains") return value.toLowerCase().includes(filter.value.toLowerCase());
    return value === filter.value;
  }

  const visibleAssets = useMemo(() => {
    const filtered = assets.filter(matchesFilter);
    return [...filtered].sort((left, right) => {
      const leftValue = sortValue(left, sortKey);
      const rightValue = sortValue(right, sortKey);
      const result = typeof leftValue === "number" && typeof rightValue === "number"
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: "base" });
      return sortDirection === "asc" ? result : -result;
    });
  }, [assets, filter, ownerKindFilter, sortKey, sortDirection]);

  function csvValue(value: string | number | undefined) {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  function exportCsv() {
    const rows = [["Item", "Owner", "Quantity", "Location", "Flag"], ...visibleAssets.map((asset) => [
      asset.type_name,
      asset.owner_name,
      asset.quantity,
      asset.location_name ?? "",
      asset.location_flag ?? "",
    ])];
    const csv = rows.map((row) => row.map(csvValue).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const suffix = filter ? `${filter.key}-${filter.value}` : "all";
    link.href = url;
    link.download = `eve-quartermaster-assets-${suffix.replace(/[^a-z0-9_-]+/gi, "-")}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function copyJaniceList() {
    const totals = new Map<string, number>();
    for (const asset of visibleAssets) totals.set(asset.type_name, (totals.get(asset.type_name) ?? 0) + asset.quantity);
    const text = [...totals.entries()]
      .sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }))
      .map(([name, quantity]) => `${name}\t${quantity}`)
      .join("\n");
    await navigator.clipboard.writeText(text);
    setCopyNotice(`Copied ${totals.size} Janice line${totals.size === 1 ? "" : "s"}.`);
  }

  const sortMark = (key: AssetSortKey) => sortKey === key ? (sortDirection === "asc" ? "↑" : "↓") : "";
  const filterButton = (key: AssetFilterKey, value: string) => (
    <button className="cell-filter" type="button" onClick={() => applyFilter(key, value)}>{value || "-"}</button>
  );
  const matchingOptions = (key: AssetFilterKey) => {
    const term = searchTerms[key].trim().toLowerCase();
    return term ? filterOptions[key].filter((value) => value.toLowerCase().includes(term)) : filterOptions[key];
  };
  const filterSelect = (key: AssetFilterKey) => (
    <label>{filterLabels[key]}<select value={filter?.key === key && filter.mode === "exact" ? filter.value : ""} onChange={(event) => event.target.value ? applyFilter(key, event.target.value) : clearFilter()}><option value="">All {filterLabels[key].toLowerCase()}s</option>{filterOptions[key].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
  );
  const searchInput = (key: AssetFilterKey) => (
    <label>{filterLabels[key]} search<input value={searchTerms[key]} list={`asset-${key}-matches`} onChange={(event) => applySearch(key, event.target.value)} placeholder={`Search ${filterLabels[key].toLowerCase()}`} /><datalist id={`asset-${key}-matches`}>{matchingOptions(key).slice(0, 50).map((value) => <option key={value} value={value} />)}</datalist></label>
  );

  return (
    <div className="asset-ledger">
      <div className="owner-kind-chips"><button type="button" className={ownerKindFilter === "" ? "active" : ""} onClick={() => setOwnerKindFilter("")}>All owners</button><button type="button" className={ownerKindFilter === "character" ? "active" : ""} onClick={() => setOwnerKindFilter("character")}>Characters</button><button type="button" className={ownerKindFilter === "corporation" ? "active" : ""} onClick={() => setOwnerKindFilter("corporation")}>Corporations</button><button type="button" className={ownerKindFilter === "alliance" ? "active" : ""} onClick={() => setOwnerKindFilter("alliance")}>Alliances</button><button type="button" className={ownerKindFilter === "manual_group" ? "active" : ""} onClick={() => setOwnerKindFilter("manual_group")}>Manual</button></div>
      <div className="ledger-filter-grid">{filterSelect("item")}{filterSelect("owner")}{filterSelect("location")}{filterSelect("flag")}</div>
      <div className="ledger-filter-grid search-grid">{searchInput("item")}{searchInput("owner")}{searchInput("location")}{searchInput("flag")}</div>
      <div className="ledger-actions">
        {filter ? <div className="active-filter"><span>{filter.label} {filter.mode === "contains" ? "contains" : "is"}: {filter.value}</span><button type="button" onClick={clearFilter}>Clear filter</button></div> : <span className="muted">Showing all assets</span>}
        <div className="button-row compact"><button type="button" disabled={visibleAssets.length === 0} onClick={exportCsv}>Export CSV</button><button type="button" disabled={visibleAssets.length === 0} onClick={() => void copyJaniceList()}>Copy for Janice</button></div>
      </div>
      {copyNotice && <div className="notice inline">{copyNotice}</div>}
      <div className="table-wrap"><table><thead><tr>
        <th><button className="sort-header" type="button" onClick={() => toggleSort("item")}>Item <span>{sortMark("item")}</span></button></th>
        <th><button className="sort-header" type="button" onClick={() => toggleSort("owner")}>Owner <span>{sortMark("owner")}</span></button></th>
        <th><button className="sort-header" type="button" onClick={() => toggleSort("quantity")}>Qty <span>{sortMark("quantity")}</span></button></th>
        <th><button className="sort-header" type="button" onClick={() => toggleSort("location")}>Location <span>{sortMark("location")}</span></button></th>
        <th><button className="sort-header" type="button" onClick={() => toggleSort("flag")}>Flag <span>{sortMark("flag")}</span></button></th>
      </tr></thead><tbody>{visibleAssets.map((asset) => <tr key={asset.id}>
        <td>{filterButton("item", asset.type_name)}</td>
        <td>{filterButton("owner", asset.owner_name)}</td>
        <td>{numberFormatter.format(asset.quantity)}</td>
        <td>{filterButton("location", asset.location_name ?? "-")}</td>
        <td>{filterButton("flag", asset.location_flag ?? "-")}</td>
      </tr>)}</tbody></table>{assets.length === 0 && <p className="empty">No assets yet. Use Seed or add one.</p>}{assets.length > 0 && visibleAssets.length === 0 && <p className="empty">No assets match this filter.</p>}</div>
    </div>
  );
}
function BlueprintList({ blueprints }: { blueprints: Blueprint[] }) {
  return <div className="card-list">{blueprints.map((bp) => <article key={bp.id}><strong>{bp.blueprint_type_name}</strong><span>{bp.owner_name} · {bp.product_type_name ?? "No product"}</span><span>ME {bp.material_efficiency} · TE {bp.time_efficiency} · {bp.is_copy ? "BPC" : "BPO"}</span></article>)}{blueprints.length === 0 && <p className="empty">No blueprints yet.</p>}</div>;
}

function RecipeList({ activities }: { activities: IndustryActivity[] }) {
  return <div className="card-list">{activities.map((activity) => <article key={activity.id}><strong>{activity.blueprint_type_name}</strong><span>{activity.activity_kind} · {activity.product_type_name ?? "No product"} x{activity.product_quantity}</span>{activity.inputs.map((input) => <code key={input.id}>{input.input_type_name}: {numberFormatter.format(input.quantity)}</code>)}</article>)}{activities.length === 0 && <p className="empty">No recipes yet.</p>}</div>;
}

function OwnerForm({ submit }: { submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void> }) {
  return <ManagedForm onSubmit={(form) => submit("/quartermaster/owners", { display_name: form.get("display_name"), owner_kind: form.get("owner_kind"), notes: form.get("notes") }, "Owner added.")}><label>Name<input name="display_name" required /></label><label>Kind<select name="owner_kind"><option value="character">Character</option><option value="corporation">Corporation</option><option value="alliance">Alliance</option><option value="manual_group">Manual group</option></select></label><label>Notes<textarea name="notes" /></label></ManagedForm>;
}

function LocationForm({ submit }: { submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void> }) {
  return <ManagedForm onSubmit={(form) => submit("/quartermaster/locations", { name: form.get("name"), location_kind: form.get("location_kind"), notes: form.get("notes") }, "Location added.")}><label>Name<input name="name" required /></label><label>Kind<select name="location_kind"><option value="structure">Structure</option><option value="station">Station</option><option value="system">System</option><option value="container">Container</option><option value="unknown">Unknown</option></select></label><label>Notes<textarea name="notes" /></label></ManagedForm>;
}

function AssetForm({ submit, ownerOptions, typeOptions, locationOptions }: { submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void>; ownerOptions: React.ReactNode; typeOptions: React.ReactNode; locationOptions: React.ReactNode }) {
  return <ManagedForm onSubmit={(form) => submit("/quartermaster/assets", { ownership_entity_id: asNumber(form.get("ownership_entity_id")), type_id: asNumber(form.get("type_id")), quantity: asNumber(form.get("quantity")), location_id: asNumber(form.get("location_id")), location_flag: form.get("location_flag"), source: "manual" }, "Asset added.")}><label>Owner<select name="ownership_entity_id" required>{ownerOptions}</select></label><label>Item<select name="type_id" required>{typeOptions}</select></label><label>Quantity<input name="quantity" type="number" min="1" defaultValue="1" required /></label><label>Location<select name="location_id"><option value="">None</option>{locationOptions}</select></label><label>Flag<input name="location_flag" placeholder="Hangar, Cargo, CorpSAG1" /></label></ManagedForm>;
}

function BlueprintForm({ submit, ownerOptions, typeOptions, locationOptions }: { submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void>; ownerOptions: React.ReactNode; typeOptions: React.ReactNode; locationOptions: React.ReactNode }) {
  return <ManagedForm onSubmit={(form) => submit("/quartermaster/blueprints", { ownership_entity_id: asNumber(form.get("ownership_entity_id")), blueprint_type_id: asNumber(form.get("blueprint_type_id")), product_type_id: asNumber(form.get("product_type_id")), location_id: asNumber(form.get("location_id")), material_efficiency: asNumber(form.get("material_efficiency")) ?? 0, time_efficiency: asNumber(form.get("time_efficiency")) ?? 0, runs_remaining: asNumber(form.get("runs_remaining")), is_copy: form.get("is_copy") === "on", source: "manual" }, "Blueprint added.")}><label>Owner<select name="ownership_entity_id" required>{ownerOptions}</select></label><label>Blueprint Type<select name="blueprint_type_id" required>{typeOptions}</select></label><label>Product Type<select name="product_type_id"><option value="">None</option>{typeOptions}</select></label><label>Location<select name="location_id"><option value="">None</option>{locationOptions}</select></label><div className="form-grid"><label>ME<input name="material_efficiency" type="number" defaultValue="0" /></label><label>TE<input name="time_efficiency" type="number" defaultValue="0" /></label><label>Runs<input name="runs_remaining" type="number" /></label></div><label className="check"><input name="is_copy" type="checkbox" /> Blueprint copy</label></ManagedForm>;
}

function RecipeForm({ submit, typeOptions }: { submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void>; typeOptions: React.ReactNode }) {
  return <ManagedForm onSubmit={(form) => submit("/quartermaster/industry-activities", { blueprint_type_id: asNumber(form.get("blueprint_type_id")), activity_kind: form.get("activity_kind"), product_type_id: asNumber(form.get("product_type_id")), product_quantity: asNumber(form.get("product_quantity")) ?? 1, time_seconds: asNumber(form.get("time_seconds")) }, "Recipe added.")}><label>Blueprint<select name="blueprint_type_id" required>{typeOptions}</select></label><label>Activity<select name="activity_kind"><option value="manufacturing">Manufacturing</option><option value="copying">Copying</option><option value="invention">Invention</option><option value="reaction">Reaction</option></select></label><label>Product<select name="product_type_id"><option value="">None</option>{typeOptions}</select></label><div className="form-grid"><label>Output qty<input name="product_quantity" type="number" defaultValue="1" /></label><label>Seconds<input name="time_seconds" type="number" /></label></div></ManagedForm>;
}

function RecipeInputForm({ submit, activityOptions, typeOptions }: { submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void>; activityOptions: React.ReactNode; typeOptions: React.ReactNode }) {
  return <ManagedForm onSubmit={(form) => submit("/quartermaster/industry-activity-inputs", { activity_id: asNumber(form.get("activity_id")), input_type_id: asNumber(form.get("input_type_id")), quantity: asNumber(form.get("quantity")), consume_type: "consumed" }, "Recipe input added.")}><label>Recipe<select name="activity_id" required>{activityOptions}</select></label><label>Input Type<select name="input_type_id" required>{typeOptions}</select></label><label>Quantity<input name="quantity" type="number" min="1" defaultValue="1" required /></label></ManagedForm>;
}

function ManagedForm({ children, onSubmit, submitLabel = "Save" }: { children: React.ReactNode; onSubmit: (form: FormData) => Promise<void>; submitLabel?: string }) {
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    const formElement = event.currentTarget;
    try {
      await onSubmit(new FormData(formElement));
      formElement.reset();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }
  return <form className="stacked-form" onSubmit={(event) => void handleSubmit(event)}>{children}{formError && <div className="mini-alert">{formError}</div>}<button type="submit"><Plus size={18} /> {busy ? "Saving" : submitLabel}</button></form>;
}

function titleFor(tab: string) {
  return ({ overview: "Quartermaster Overview", ownership: "Ownership and Locations", characters: "Characters", corporations: "Corporations", assets: "Asset Ledger", industry: "Blueprints and Recipes", esi: "ESI Sync", users: "User Management" } as Record<string, string>)[tab];
}

function subtitleFor(tab: string) {
  return ({ overview: "Live status and the first useful totals from the database.", ownership: "Define the characters, corporations, manual buckets, and places assets can belong to.", characters: "Assign EVE characters to Quartermaster accounts and control public asset visibility.", corporations: "Review enrolled corporations and sync corporation asset ledgers through authorized CEO or director tokens.", assets: "Track item stacks by owner, type, location, and EVE-style location flag.", industry: "Store blueprints, recipe activities, and material inputs before wiring in SDE imports.", esi: "A holding area for the upcoming SSO and sync work.", users: "Manage Quartermaster accounts and role levels." } as Record<string, string>)[tab];
}

createRoot(document.getElementById("root")!).render(<App />);






























