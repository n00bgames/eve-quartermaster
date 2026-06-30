import { Activity, Boxes, Building2, Database, Factory, GraduationCap, KeyRound, MessageCircle, PackagePlus, Plus, RefreshCw, ScrollText, Settings, Sparkles, UserRoundCheck } from "lucide-react";
import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Health = { status: string; app: string };
type UserAccount = { id: number; email: string; display_name: string; role: string; created_at?: string };
type SectionPermission = { key: string; label: string; default_roles: string[] };
type EffectivePermissions = { sections: SectionPermission[]; permissions: Record<string, boolean> };
type RoleDefinition = { name: string; display_name: string; base_role: string; is_system: boolean; sort_order?: number; rank?: number };
type PermissionMatrix = { sections: SectionPermission[]; roles: string[]; role_permissions: { id: number; role: string; section: string; can_view: boolean }[]; user_permissions: { id: number; user_id: number; section: string; can_view: boolean }[] };
type AuthResponse = { access_token: string; user: UserAccount };
type BootstrapStatus = { needs_admin: boolean; roles: string[] };
type InviteInfo = { email: string; role: string; expires_at?: string | null };
type UserInvite = { id: number; email: string; role: string; status?: string; created_by_display_name?: string | null; created_at?: string | null; expires_at?: string | null; accepted_at?: string | null; revoked_at?: string | null; invite_url?: string };
type Summary = { owners: number; locations: number; types: number; asset_stacks: number; asset_units: number; blueprints: number; industry_activities: number };
type SdeStatus = { default_source_path: string; categories: number; groups: number; types: number; blueprint_activities: number; activity_inputs: number };
type SdeImportResult = SdeStatus & { source_path: string; skipped_activities: number };
type Owner = { id: number; owner_kind: string; display_name: string; notes?: string };
type EveType = { type_id: number; name: string; group_id?: number; volume?: number };
type Location = { id: number; location_kind: string; name: string; notes?: string };
type Asset = { id: number; ownership_entity_id: number; owner_name: string; owner_kind?: string; type_id: number; type_name: string; quantity: number; location_name?: string; location_flag?: string; source: string; last_synced_at?: string | null; parent_asset_item_id?: number; parent_asset_type_name?: string };
type Blueprint = { id: number; owner_name: string; blueprint_type_id: number; blueprint_type_name: string; product_type_name?: string; material_efficiency: number; time_efficiency: number; runs_remaining?: number; is_copy: boolean; location_name?: string; last_synced_at?: string | null };
type ActivityInput = { id: number; input_type_name: string; quantity: number; consume_type: string };
type IndustryActivity = { id: number; activity_kind: string; blueprint_type_name: string; product_type_name?: string; product_quantity: number; time_seconds?: number; inputs: ActivityInput[] };
type EsiAuthInfo = { ready: boolean; message?: string; url?: string; required_scopes: string[] };
type LinkedCharacter = { token_id: number; character_id: number; character_name: string; linked_user_id: number; linked_user_display_name: string; can_sync_assets: boolean; can_unlink: boolean; scopes: string; access_token_expires_at?: string; linked_at?: string; last_sync_at?: string; last_sync_type?: string; last_sync_status?: string; missing_public_scopes: string[]; missing_standing_scopes: string[] };
type EqmCharacter = { id: number; character_id?: number; name: string; can_view_detail: boolean; owner_user_id?: number | null; owner_display_name?: string | null; owner_role?: string | null; corporation_name?: string | null; alliance_name?: string | null; public_assets_visible?: boolean; sync_opt_out?: boolean; last_synced_at?: string | null; can_manage?: boolean; can_assign?: boolean };
type RosterCharacter = { character_id: number; name: string; portrait_url?: string | null };
type RosterCorporation = { corporation_id?: number | null; corporation_name: string; ticker?: string | null; alliance_name?: string | null; member_count?: number | null; characters: RosterCharacter[] };
type CorporationToken = { token_id: number; character_name: string; user_display_name: string; has_corporation_asset_scope: boolean; can_sync: boolean; has_corporation_blueprint_scope: boolean; can_sync_blueprints: boolean; has_corporation_wallet_scope?: boolean; can_sync_wallets?: boolean };
type CorporationWalletDivision = { division: number; balance: number; last_synced_at?: string | null };
type EqmCorporation = { id: number; corporation_id: number; name: string; ticker?: string | null; alliance_name?: string | null; ceo_character_eve_id?: number | null; ceo_character_name?: string | null; member_count?: number | null; last_synced_at?: string | null; asset_rows: number; blueprint_rows: number; last_asset_sync_at?: string | null; last_asset_sync_status?: string | null; last_asset_sync_message?: string | null; asset_sync_stale?: boolean; last_blueprint_sync_at?: string | null; last_blueprint_sync_status?: string | null; last_blueprint_sync_message?: string | null; blueprint_sync_stale?: boolean; last_wallet_sync_at?: string | null; last_wallet_sync_status?: string | null; last_wallet_sync_message?: string | null; wallet_sync_stale?: boolean; wallet_divisions: CorporationWalletDivision[]; eligible_tokens: CorporationToken[] };
type ContactSample = { contact_id: number; name: string; contact_type?: string; standing: number; is_watched: boolean };
type ContactPreviewTarget = { token_id: number; character_id: number; character_name: string; create_count: number; update_count: number; skip_count: number; create_sample: ContactSample[]; update_sample: ContactSample[] };
type ContactSyncPreview = { source_character_name: string; source_contact_count: number; overwrite_existing: boolean; totals: { create: number; update: number; skip: number }; targets: ContactPreviewTarget[] };
type ContactApplyResult = { status: string; source_character_name: string; created: number; updated: number; targets: { character_name: string; created: number; updated: number; skipped: number }[] };
type SkillRecord = { id: number; skill_type_id: number; skill_name: string; skill_group_name: string; skill_category_name: string; trained_skill_level: number; active_skill_level: number; skillpoints_in_skill: number; last_synced_at?: string | null };
type SkillQueueEntry = { id: number; queue_position: number; skill_type_id: number; skill_name: string; finished_level: number; training_start_sp?: number | null; level_start_sp?: number | null; level_end_sp?: number | null; start_date?: string | null; finish_date?: string | null };
type CharacterSkillProfile = { token_id: number; character_id: number; character_name: string; owner_user_id: number; sync_opt_out: boolean; admin_override_visible: boolean; can_sync?: boolean; total_skill_points?: number | null; unallocated_skill_points?: number | null; skills_synced_at?: string | null; skill_queue_synced_at?: string | null; missing_skill_scopes: string[]; skill_count: number; queue_count: number; skills: SkillRecord[]; queue: SkillQueueEntry[] };
type AuditEvent = { id: number; event_kind: string; title: string; body?: string | null; actor_display_name?: string | null; recipient_display_name?: string | null; character_name?: string | null; is_read: boolean; created_at?: string | null };
type PrivateMessage = { id: number; sender_user_id: number; sender_display_name?: string | null; recipient_user_id: number; recipient_display_name?: string | null; subject: string; body: string; is_read: boolean; created_at?: string | null };
type NotificationInbox = { unread_count: number; events: AuditEvent[]; messages: PrivateMessage[]; sent_messages?: PrivateMessage[]; users: UserAccount[] };
type ProfileFocus = { section: "messages"; replyTo?: PrivateMessage; nonce: number };
type AnalyticsPoint = { date?: string | null; corporation_name?: string; value: number };
type AnalyticsGrowth = { id?: number; name: string; value?: number; delta: number };
type DuplicateBlueprint = { owner_name: string; blueprint_type_name: string; is_copy: boolean; quantity: number };
type MetricCatalogItem = { metric: string; version: number; label: string; unit: string; aggregation: string; category: string; supportsCharacter: boolean; supportsCorporation: boolean; chartTypes: string[]; deprecated: boolean; hasData?: boolean };
type AnalyticsSummary = {
  days: number;
  latest_snapshot_at?: string | null;
  latest_snapshot_status?: string | null;
  snapshot_count: number;
  cards: { wallet_total: number; blueprint_total: number; member_total: number; character_count: number };
  top_sp_gainers: AnalyticsGrowth[];
  top_skill_category_gainers: { name: string; delta: number }[];
  wallet_growth: AnalyticsGrowth[];
  member_growth: AnalyticsGrowth[];
  blueprint_growth: AnalyticsGrowth[];
  duplicate_blueprints: DuplicateBlueprint[];
  series: { wallet_totals: AnalyticsPoint[]; member_counts: AnalyticsPoint[]; blueprint_counts: AnalyticsPoint[] };
};

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
const APP_VERSION = "0.0.6-alpha";

function accountLabel(user: UserAccount): string {
  const name = user.display_name?.trim();
  if (name && !name.includes("@")) return name;
  const localPart = user.email.split("@")[0]?.trim();
  return localPart || name || `User ${user.id}`;
}
const emptyData: AppData = { health: null, summary: null, owners: [], types: [], locations: [], assets: [], blueprints: [], activities: [] };
const numberFormatter = new Intl.NumberFormat();
const iskFormatter = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 });

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

function requestTimeoutMs(path: string): number {
  if (path.startsWith("/esi/sync/")) return 300000;
  if (path.startsWith("/sde/import")) return 900000;
  return 20000;
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem("eq_access_token");
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), requestTimeoutMs(path));
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: options?.signal ?? controller.signal,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options?.headers },
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
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw new Error(`Request timed out while calling ${path}.`);
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
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

function isToday(value?: string | null) {
  if (!value) return false;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return date >= today;
}

function syncedTodayLabel(value: number, unit: string) {
  return value > 0 ? `+${numberFormatter.format(value)} ${unit} synced today` : "No sync today";
}

function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [profileFocus, setProfileFocus] = useState<ProfileFocus | null>(null);
  const [data, setData] = useState<AppData>(emptyData);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState<UserAccount | null>(null);
  const [bootstrap, setBootstrap] = useState<BootstrapStatus | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [permissions, setPermissions] = useState<Record<string, boolean>>({ overview: true, profile: true });

  async function refreshAuth() {
    try {
      const boot = await api<BootstrapStatus>("/auth/bootstrap");
      setBootstrap(boot);
      const token = localStorage.getItem("eq_access_token");
      if (token && !boot.needs_admin) {
        const currentUser = await api<UserAccount>("/auth/me");
        setUser(currentUser);
        const permissionPayload = await api<EffectivePermissions>("/auth/permissions/effective");
        setPermissions(permissionPayload.permissions);
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
    const permissionPayload = await api<EffectivePermissions>("/auth/permissions/effective");
    setPermissions(permissionPayload.permissions);
    setNotice(`Signed in as ${result.user.display_name}.`);
    if (new URLSearchParams(window.location.search).has("invite")) window.history.replaceState({}, "", window.location.pathname);
    await load();
  }

  function signOut() {
    localStorage.removeItem("eq_access_token");
    setUser(null);
    setData(emptyData);
    setPermissions({ overview: true, profile: true });
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
        api<IndustryActivity[]>("/quartermaster/industry-activities?limit=250"),
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

  function canView(section: string) { return user?.role === "admin" || permissions[section] !== false; }

  const inviteToken = new URLSearchParams(window.location.search).get("invite");
  if (!authReady) return <main className="auth-shell"><section className="panel"><img className="auth-logo" src="/eqm-logo.png" alt="EVE Quartermaster" /><p className="muted">Checking account session...</p></section></main>;
  if (!user && inviteToken) return <InviteScreen token={inviteToken} onAuth={completeAuth} />;
  if (!user) return <AuthScreen bootstrap={bootstrap} onAuth={completeAuth} />;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <img className="brand-logo" src="/eqm-logo.png" alt="EVE Quartermaster" />
        <div>
          <h1>EVE Quartmaster</h1>
          <p>Inventory, ownership, and industry planning for EVE Online.</p><p className="sidebar-tagline">EVE is Excel in a flight suit.</p>
        </div>
        <nav>
          {canView("overview") && <button className={activeTab === "overview" ? "active" : ""} onClick={() => setActiveTab("overview")}><Database size={18} /> Overview</button>}
          {canView("ownership") && <button className={activeTab === "ownership" ? "active" : ""} onClick={() => setActiveTab("ownership")}><Boxes size={18} /> Ownership</button>}
          {canView("characters") && <button className={activeTab === "characters" ? "active" : ""} onClick={() => setActiveTab("characters")}><UserRoundCheck size={18} /> Characters</button>}
          {canView("roster") && <button className={activeTab === "roster" ? "active" : ""} onClick={() => setActiveTab("roster")}><Building2 size={18} /> Roster</button>}
          {canView("analytics") && <button className={activeTab === "analytics" ? "active" : ""} onClick={() => setActiveTab("analytics")}><Activity size={18} /> Analytics</button>}
          {canView("skills") && <button className={activeTab === "skills" ? "active" : ""} onClick={() => setActiveTab("skills")}><GraduationCap size={18} /> Skills</button>}
          {canView("settings") && <button className={activeTab === "settings" ? "active" : ""} onClick={() => setActiveTab("settings")}><Settings size={18} /> Settings</button>}
          {canView("corporations") && <button className={activeTab === "corporations" ? "active" : ""} onClick={() => setActiveTab("corporations")}><Building2 size={18} /> Corporations</button>}
          {canView("assets") && <button className={activeTab === "assets" ? "active" : ""} onClick={() => setActiveTab("assets")}><PackagePlus size={18} /> Assets</button>}
          {canView("industry") && <button className={activeTab === "industry" ? "active" : ""} onClick={() => setActiveTab("industry")}><Factory size={18} /> Industry</button>}
          {canView("esi") && <button className={activeTab === "esi" ? "active" : ""} onClick={() => setActiveTab("esi")}><KeyRound size={18} /> ESI Sync</button>}
          {canView("profile") && <button className={activeTab === "profile" ? "active" : ""} onClick={() => setActiveTab("profile")}><UserRoundCheck size={18} /> Profile</button>}
          {canView("audit") && <button className={activeTab === "audit" ? "active" : ""} onClick={() => setActiveTab("audit")}><ScrollText size={18} /> Audit</button>}        </nav>
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
            <NotificationBubble currentUser={user} onOpenMessages={(message) => { setProfileFocus({ section: "messages", replyTo: message, nonce: Date.now() }); setActiveTab("profile"); }} />
            <span className="status-badge rank-badge">{user.role}</span>
            <button onClick={() => void seed()}><Sparkles size={18} /> Seed</button>
            <button onClick={() => void load()}><RefreshCw size={18} /> {loading ? "Refreshing" : "Refresh"}</button>
            <button onClick={signOut}>Sign out</button>
          </div>
        </header>

        {error && <div className="alert">{error}</div>}
        {notice && <div className="notice">{notice}</div>}

        {!canView(activeTab) && <section className="panel"><h3>Permission required</h3><p className="muted">This section is not enabled for your account.</p></section>}
        {activeTab === "overview" && canView("overview") && <Overview data={data} />}
        {activeTab === "ownership" && canView("ownership") && <Ownership data={data} submit={submit} />}
        {activeTab === "characters" && canView("characters") && <Characters currentUser={user} />}
        {activeTab === "roster" && canView("roster") && <Roster />}
        {activeTab === "analytics" && canView("analytics") && <AnalyticsPlatform currentUser={user} />}
        {activeTab === "skills" && canView("skills") && <CharacterSkills currentUser={user} />}
        {activeTab === "settings" && canView("settings") && <SettingsPage currentUser={user} />}
        {activeTab === "corporations" && canView("corporations") && <Corporations loadAssets={load} />}
        {activeTab === "assets" && canView("assets") && <Assets data={data} submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} />}
        {activeTab === "industry" && canView("industry") && <Industry data={data} submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} activityOptions={activityOptions} />}
        {activeTab === "esi" && canView("esi") && <Esi load={load} currentUser={user} />}
        {activeTab === "profile" && canView("profile") && <ProfilePage currentUser={user} onUserUpdated={setUser} focus={profileFocus} />}
        {activeTab === "audit" && canView("audit") && <AuditLog />}
      </section>
    </main>
  );
}

function NotificationBubble({ currentUser, onOpenMessages }: { currentUser: UserAccount; onOpenMessages: (message?: PrivateMessage) => void }) {
  const [open, setOpen] = useState(false);
  const [inbox, setInbox] = useState<NotificationInbox | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<string | null>(null);

  async function loadInbox() {
    setInbox(await api<NotificationInbox>("/notifications"));
  }

  async function markAllRead() {
    if (!inbox) return;
    await api<{ status: string }>("/notifications/read", { method: "POST", body: JSON.stringify({ event_ids: inbox.events.map((event) => event.id), message_ids: inbox.messages.map((message) => message.id) }) });
    await loadInbox();
  }

  async function sendMessage(form: FormData) {
    setError(null);
    try {
      await api<PrivateMessage>("/notifications/messages", { method: "POST", body: JSON.stringify({ recipient_user_id: form.get("recipient_user_id"), subject: form.get("subject"), body: form.get("body") }) });
      setSent("Message sent.");
      await loadInbox();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Message failed");
    }
  }

  useEffect(() => { void loadInbox().catch(() => undefined); }, []);
  const unread = inbox?.unread_count ?? 0;
  const recipients = (inbox?.users ?? []).filter((user) => user.id !== currentUser.id);

  return <div className="bubble-wrap"><button type="button" className="bubble-button" aria-label="Messages and notifications" onClick={() => { setOpen((value) => !value); if (!open) void loadInbox().catch((err) => setError(err instanceof Error ? err.message : "Unable to load inbox")); }}><MessageCircle size={18} />{unread > 0 && <span>{unread > 99 ? "99+" : unread}</span>}</button>{open && <div className="bubble-panel"><div className="section-heading compact"><h3>Inbox</h3><button type="button" onClick={() => void markAllRead()}>Mark read</button></div>{error && <div className="mini-alert">{error}</div>}{sent && <div className="notice inline">{sent}</div>}<h4>System notices</h4><div className="mini-list inbox-list">{inbox?.events.map((event) => <div key={event.id} className={event.is_read ? "" : "unread"}><strong>{event.title}</strong><span>{event.body ?? "Audit event"}</span><span>{event.created_at ? new Date(event.created_at).toLocaleString() : "recently"}</span></div>)}{inbox && inbox.events.length === 0 && <p className="empty">No system notices.</p>}</div><h4>Private messages</h4><div className="mini-list inbox-list">{inbox?.messages.map((message) => <button type="button" key={message.id} className={message.is_read ? "message-link" : "message-link unread"} onClick={() => { setOpen(false); onOpenMessages(message); }}><strong>{message.subject}</strong><span>From {message.sender_display_name ?? "Unknown"}</span><span>{message.body}</span><span>{message.created_at ? new Date(message.created_at).toLocaleString() : "recently"}</span></button>)}{inbox && inbox.messages.length === 0 && <p className="empty">No private messages.</p>}</div><div className="section-heading compact"><h4>Send message</h4><button type="button" onClick={() => { setOpen(false); onOpenMessages(); }}>Open mailbox</button></div><ManagedForm submitLabel="Send" onSubmit={sendMessage}><label>To<select name="recipient_user_id" required>{recipients.map((user) => <option key={user.id} value={user.id}>{accountLabel(user)} ({user.role})</option>)}</select></label><label>Subject<input name="subject" required /></label><label>Message<textarea name="body" required /></label></ManagedForm></div>}</div>;
}

function AnalyticsPlatform({ currentUser }: { currentUser: UserAccount }) {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [catalog, setCatalog] = useState<MetricCatalogItem[]>([]);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadAnalytics(selectedDays = days) {
    setAnalyticsError(null);
    const [nextSummary, nextCatalog] = await Promise.all([api<AnalyticsSummary>(`/analytics/summary?days=${selectedDays}`), api<MetricCatalogItem[]>("/analytics/metrics")]);
    setSummary(nextSummary);
    setCatalog(nextCatalog);
  }

  async function downloadExport(format: "csv" | "json") {
    const token = localStorage.getItem("eq_access_token");
    const response = await fetch(`${API_BASE}/analytics/exports/metrics.${format}?days=${days}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!response.ok) throw new Error(`Export failed: ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `eqm-metrics-${days}d.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function clearSnapshots() {
    if (!window.confirm("Clear all analytics snapshot history? Current synced assets, skills, wallets, and corporation records will stay intact.")) return;
    setBusy(true);
    setAnalyticsError(null);
    try {
      const result = await api<{ status: string; deleted_snapshot_runs: number }>("/analytics/snapshots", { method: "DELETE" });
      setMessage(`Cleared ${result.deleted_snapshot_runs.toLocaleString()} analytics snapshot run${result.deleted_snapshot_runs === 1 ? "" : "s"}.`);
      await loadAnalytics();
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Snapshot cleanup failed");
    } finally {
      setBusy(false);
    }
  }

  async function captureSnapshot() {
    setBusy(true);
    setAnalyticsError(null);
    try {
      const result = await api<{ status: string; snapshot_run_id: number }>("/analytics/snapshot", { method: "POST", body: "{}" });
      setMessage(`Snapshot ${result.snapshot_run_id} captured.`);
      await loadAnalytics();
    } catch (err) {
      setAnalyticsError(err instanceof Error ? err.message : "Snapshot failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void loadAnalytics().catch((err) => setAnalyticsError(err instanceof Error ? err.message : "Unable to load analytics")); }, []);

  return <section className="panel stacked analytics-platform"><div className="section-heading"><div><h3>Analytics Platform</h3><p>Historical snapshot engine, metric providers, report exports, and composable widgets. First observations establish baselines; deltas start after a later snapshot.</p></div><div className="button-row compact"><select value={days} onChange={(event) => { const next = Number(event.target.value); setDays(next); void loadAnalytics(next); }}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>1 year</option></select><button type="button" disabled={busy} onClick={() => void captureSnapshot()}>{busy ? "Capturing" : "Capture snapshot"}</button>{currentUser.role === "admin" && <button type="button" className="danger" disabled={busy} onClick={() => void clearSnapshots()}>Clear snapshots</button>}</div></div>{message && <div className="notice inline">{message}</div>}{analyticsError && <div className="mini-alert">{analyticsError}</div>}{summary ? <><div className="status-grid wide"><Metric icon={<Database size={18} />} label="Snapshots" value={summary.snapshot_count} delta={summary.latest_snapshot_at ? `latest ${new Date(summary.latest_snapshot_at).toLocaleString()}` : "none yet"} /><Metric icon={<GraduationCap size={18} />} label="Characters" value={summary.cards.character_count} /><Metric icon={<Building2 size={18} />} label="Members" value={summary.cards.member_total} /><Metric icon={<ScrollText size={18} />} label="Blueprints" value={summary.cards.blueprint_total} /><Metric icon={<Activity size={18} />} label="Corp wallets" value={`${iskFormatter.format(summary.cards.wallet_total)} ISK`} /></div><div className="analytics-export-row"><button type="button" onClick={() => void downloadExport("csv")}>Export metrics CSV</button><button type="button" onClick={() => void downloadExport("json")}>Export metrics JSON</button><button type="button" onClick={() => void navigator.clipboard.writeText(discordAnalyticsSummary(summary))}>Copy Discord summary</button></div><MetricCatalogWidget rows={catalog} /><div className="widget-grid"><AnalyticsWidget title="SP Gain" rows={summary.top_sp_gainers} unit="SP" /><AnalyticsWidget title="Skill Category Gain" rows={summary.top_skill_category_gainers} unit="SP" /><AnalyticsWidget title="Wallet Growth" rows={summary.wallet_growth} unit="ISK" isk /><AnalyticsWidget title="Corporation Growth" rows={summary.member_growth} unit="members" /><AnalyticsWidget title="Blueprint Growth" rows={summary.blueprint_growth} unit="BPs" /><DuplicateBlueprintWidget rows={summary.duplicate_blueprints} /><TrendWidget title="Wallet Trend" points={summary.series.wallet_totals} isk /><TrendWidget title="Blueprint Trend" points={summary.series.blueprint_counts} /></div></> : <p className="empty">No analytics snapshots yet. Capture one manually or run a sync to start building history.</p>}</section>;
}

function discordAnalyticsSummary(summary: AnalyticsSummary): string {
  const topSp = summary.top_sp_gainers[0];
  const wallet = summary.wallet_growth[0];
  return [`EQM ${summary.days}-day report`, `Snapshots: ${summary.snapshot_count}`, `Top SP: ${topSp ? `${topSp.name} +${numberFormatter.format(topSp.delta)} SP` : "none"}`, `Top wallet: ${wallet ? `${wallet.name} ${iskFormatter.format(wallet.delta)} ISK` : "none"}`, `Blueprints: ${numberFormatter.format(summary.cards.blueprint_total)}`].join("\n");
}

function AnalyticsWidget({ title, rows, unit, isk = false }: { title: string; rows: { name: string; delta: number }[]; unit: string; isk?: boolean }) {
  const max = Math.max(...rows.map((row) => Math.abs(row.delta)), 1);
  return <article className="analytics-widget"><h4>{title}</h4><div className="widget-list">{rows.slice(0, 8).map((row) => <div key={`${title}-${row.name}`} className="widget-row"><span>{row.name}</span><strong>{formatDelta(row.delta, unit, isk)}</strong><i style={{ width: `${Math.max(4, Math.abs(row.delta) / max * 100)}%` }} /></div>)}{rows.length === 0 && <p className="empty">No movement yet.</p>}</div></article>;
}

function MetricCatalogWidget({ rows }: { rows: MetricCatalogItem[] }) {
  return <article className="analytics-widget metric-catalog"><h4>Metric Catalog</h4><div className="metric-chip-row">{rows.map((row) => <span key={row.metric} className={row.hasData ? "metric-chip has-data" : "metric-chip"}>{row.label}<small>v{row.version} · {row.unit} · {row.chartTypes.join(", ")}{row.deprecated ? " · deprecated" : ""}</small></span>)}</div></article>;
}
function DuplicateBlueprintWidget({ rows }: { rows: DuplicateBlueprint[] }) {
  return <article className="analytics-widget"><h4>Duplicate BPs</h4><div className="widget-list">{rows.slice(0, 8).map((row) => <div key={`${row.owner_name}-${row.blueprint_type_name}-${row.is_copy}`} className="widget-row"><span>{row.blueprint_type_name}</span><strong>{row.quantity.toLocaleString()} {row.is_copy ? "BPC" : "BPO"}</strong><small>{row.owner_name}</small><i style={{ width: `${Math.min(100, row.quantity * 12)}%` }} /></div>)}{rows.length === 0 && <p className="empty">No duplicate blueprint stacks in the latest snapshot.</p>}</div></article>;
}

function TrendWidget({ title, points, isk = false }: { title: string; points: AnalyticsPoint[]; isk?: boolean }) {
  const compact = points.slice(-24);
  const max = Math.max(...compact.map((point) => point.value), 1);
  return <article className="analytics-widget"><h4>{title}</h4><div className="trend-strip">{compact.map((point, index) => <i key={`${title}-${point.date}-${point.corporation_name}-${index}`} style={{ height: `${Math.max(6, point.value / max * 100)}%` }} title={`${point.corporation_name ?? "value"}: ${isk ? iskFormatter.format(point.value) : numberFormatter.format(point.value)}`} />)}</div>{compact.length === 0 && <p className="empty">No trend data yet.</p>}</article>;
}

function formatDelta(value: number, unit: string, isk = false) {
  const sign = value > 0 ? "+" : "";
  const formatted = isk ? iskFormatter.format(value) : numberFormatter.format(Math.round(value));
  return `${sign}${formatted} ${unit}`;
}

function AuditLog() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [auditError, setAuditError] = useState<string | null>(null);

  async function loadAudit() {
    setEvents(await api<AuditEvent[]>("/notifications/audit"));
  }

  useEffect(() => { void loadAudit().catch((err) => setAuditError(err instanceof Error ? err.message : "Unable to load audit log")); }, []);

  return <section className="panel stacked"><div className="section-heading"><h3>Audit Log</h3><button type="button" onClick={() => void loadAudit()}>Refresh</button></div>{auditError && <div className="mini-alert">{auditError}</div>}<div className="card-list audit-list">{events.map((event) => <article key={event.id}><strong>{event.title}</strong><span>{event.event_kind} · {event.created_at ? new Date(event.created_at).toLocaleString() : "recently"}</span><span>Actor {event.actor_display_name ?? "system"}{event.recipient_display_name ? ` · Recipient ${event.recipient_display_name}` : ""}{event.character_name ? ` · Character ${event.character_name}` : ""}</span>{event.body && <span>{event.body}</span>}</article>)}{events.length === 0 && <p className="empty">No audit events yet.</p>}</div></section>;
}
function AuthScreen({ bootstrap, onAuth }: { bootstrap: BootstrapStatus | null; onAuth: (path: string, body: Record<string, unknown>) => Promise<void> }) {
  const needsAdmin = bootstrap?.needs_admin ?? false;
  return (
    <main className="auth-shell">
      <section className="panel auth-panel">
        <img className="auth-logo" src="/eqm-logo.png" alt="EVE Quartermaster" />
        <span className="status-badge version-badge auth-version">v{APP_VERSION}</span>
        <h2>{needsAdmin ? "Create Admin Account" : "Sign In"}</h2>
        <p className="muted">{needsAdmin ? "Set up the first Quartermaster administrator." : "Use your Quartermaster account before linking EVE characters."}</p><p className="auth-tagline">EVE is Excel in a flight suit.</p>
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
          <p className="muted">Create your Quartermaster account for {invite.email}.</p><p className="auth-tagline">EVE is Excel in a flight suit.</p>
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
function ProfilePage({ currentUser, onUserUpdated, focus }: { currentUser: UserAccount; onUserUpdated: (user: UserAccount) => void; focus: ProfileFocus | null }) {
  const [inbox, setInbox] = useState<NotificationInbox | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [replyTo, setReplyTo] = useState<PrivateMessage | undefined>(undefined);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const recipients = (inbox?.users ?? []).filter((user) => user.id !== currentUser.id);

  async function loadInbox() {
    setInbox(await api<NotificationInbox>("/notifications"));
  }

  async function updateAccount(form: FormData) {
    setProfileError(null);
    try {
      const payload: Record<string, unknown> = {};
      const displayName = String(form.get("display_name") ?? "").trim();
      const email = String(form.get("email") ?? "").trim();
      const password = String(form.get("password") ?? "");
      const currentPassword = String(form.get("current_password") ?? "");
      if (displayName) payload.display_name = displayName;
      if (email && email !== currentUser.email) payload.email = email;
      if (password) payload.password = password;
      if (currentPassword) payload.current_password = currentPassword;
      const updated = await api<UserAccount>("/auth/me", { method: "PATCH", body: JSON.stringify(payload) });
      onUserUpdated(updated);
      setMessage("Profile updated.");
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Profile update failed");
    }
  }

  async function sendMessage(form: FormData) {
    setProfileError(null);
    try {
      await api<PrivateMessage>("/notifications/messages", { method: "POST", body: JSON.stringify({ recipient_user_id: form.get("recipient_user_id"), subject: form.get("subject"), body: form.get("body") }) });
      setReplyTo(undefined);
      setMessage("Message sent.");
      await loadInbox();
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Message failed");
    }
  }

  async function markMessageRead(messageId: number) {
    await api<{ status: string }>("/notifications/read", { method: "POST", body: JSON.stringify({ event_ids: [], message_ids: [messageId] }) });
    await loadInbox();
  }

  async function deleteMessage(messageId: number) {
    if (!window.confirm("Delete this private message from your mailbox?")) return;
    await api<{ status: string }>(`/notifications/messages/${messageId}`, { method: "DELETE" });
    if (replyTo?.id === messageId) setReplyTo(undefined);
    setMessage("Message deleted.");
    await loadInbox();
  }

  useEffect(() => { void loadInbox().catch((err) => setProfileError(err instanceof Error ? err.message : "Unable to load messages")); }, []);
  useEffect(() => {
    if (!focus || focus.section !== "messages") return;
    setReplyTo(focus.replyTo);
    window.setTimeout(() => messagesRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    if (focus.replyTo && !focus.replyTo.is_read) void markMessageRead(focus.replyTo.id).catch(() => undefined);
  }, [focus?.nonce]);

  const replySubject = replyTo?.subject?.toLowerCase().startsWith("re:") ? replyTo.subject : replyTo ? `Re: ${replyTo.subject}` : "";

  return <div className="profile-page"><section className="panel stacked"><h3>Profile</h3>{message && <div className="notice inline">{message}</div>}{profileError && <div className="mini-alert">{profileError}</div>}<ManagedForm submitLabel="Update profile" onSubmit={updateAccount}><label>Display name<input name="display_name" defaultValue={currentUser.display_name} required /></label><label>Email<input name="email" type="email" defaultValue={currentUser.email} required /></label><label>Current password<input name="current_password" type="password" placeholder="Required for email or password changes" /></label><label>New password<input name="password" type="password" minLength={8} placeholder="Leave blank to keep current password" /></label></ManagedForm></section><section className="panel stacked" ref={messagesRef}><div className="section-heading"><h3>Private Messages</h3><button type="button" onClick={() => void loadInbox()}>Refresh</button></div><div className="two-column"><div className="stacked"><h4>Inbox</h4><div className="card-list message-list">{inbox?.messages.map((item) => <article key={item.id} className={item.is_read ? "" : "unread-card"}><strong>{item.subject}</strong><span>From {item.sender_display_name ?? "Unknown"} · {item.created_at ? new Date(item.created_at).toLocaleString() : "recently"}</span><p>{item.body}</p><div className="card-actions"><button type="button" onClick={() => setReplyTo(item)}>Reply</button>{!item.is_read && <button type="button" onClick={() => void markMessageRead(item.id)}>Mark read</button>}<button className="danger" type="button" onClick={() => void deleteMessage(item.id)}>Delete</button></div></article>)}{inbox && inbox.messages.length === 0 && <p className="empty">No private messages.</p>}</div></div><div className="stacked"><h4>Sent</h4><div className="card-list message-list">{inbox?.sent_messages?.map((item) => <article key={item.id}><strong>{item.subject}</strong><span>To {item.recipient_display_name ?? "Unknown"} · {item.created_at ? new Date(item.created_at).toLocaleString() : "recently"}</span><p>{item.body}</p><div className="card-actions"><button className="danger" type="button" onClick={() => void deleteMessage(item.id)}>Delete</button></div></article>)}{inbox && (inbox.sent_messages ?? []).length === 0 && <p className="empty">No sent messages.</p>}</div></div></div><h4>{replyTo ? `Reply to ${replyTo.sender_display_name ?? "Unknown"}` : "Compose"}</h4><ManagedForm key={replyTo?.id ?? "compose"} submitLabel={replyTo ? "Send reply" : "Send message"} onSubmit={sendMessage}><label>To<select name="recipient_user_id" required defaultValue={replyTo?.sender_user_id ?? recipients[0]?.id ?? ""}>{recipients.map((user) => <option key={user.id} value={user.id}>{accountLabel(user)} ({user.role})</option>)}</select></label><label>Subject<input name="subject" required defaultValue={replySubject} /></label><label>Message<textarea name="body" required /></label></ManagedForm></section>{currentUser.role === "admin" && <UsersAdmin currentUser={currentUser} />}</div>;
}
function UsersAdmin({ currentUser }: { currentUser: UserAccount }) {
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [invites, setInvites] = useState<UserInvite[]>([]);
  const [characters, setCharacters] = useState<EqmCharacter[]>([]);
  const [accounts, setAccounts] = useState<UserAccount[]>([]);
  const [roleDefinitions, setRoleDefinitions] = useState<RoleDefinition[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [latestInviteUrl, setLatestInviteUrl] = useState<string | null>(null);
  const [userError, setUserError] = useState<string | null>(null);
  const roles = roleDefinitions.length ? roleDefinitions.map((role) => role.name) : ["admin", "director", "officer", "member", "view_only"];
  const roleLabel = (roleName: string) => roleDefinitions.find((role) => role.name === roleName)?.display_name ?? roleName;

  async function loadUsers() {
    setUsers(await api<UserAccount[]>("/auth/users"));
  }

  async function loadRoles() {
    setRoleDefinitions(await api<RoleDefinition[]>("/auth/roles"));
  }

  async function loadInvites() {
    setInvites(await api<UserInvite[]>("/auth/invites"));
  }

  async function loadCharacterAssignments() {
    const [visibleCharacters, assignableAccounts] = await Promise.all([api<EqmCharacter[]>("/characters"), api<UserAccount[]>("/characters/accounts")]);
    setCharacters(visibleCharacters);
    setAccounts(assignableAccounts);
  }

  async function runUserAction(action: () => Promise<string>, refreshInvites = false) {
    setUserError(null);
    try {
      const nextMessage = await action();
      setMessage(nextMessage);
      await Promise.all([loadUsers(), loadCharacterAssignments()]);
      if (refreshInvites) await loadInvites();
    } catch (err) {
      setUserError(err instanceof Error ? err.message : "User action failed");
    }
  }

  async function createAccount(form: FormData) {
    await runUserAction(async () => {
      const user = await api<UserAccount>("/auth/users", { method: "POST", body: JSON.stringify({ email: form.get("email"), display_name: form.get("display_name"), password: form.get("password"), role: form.get("role") }) });
      return `${user.display_name} created.`;
    });
  }

  async function createInvite(form: FormData) {
    await runUserAction(async () => {
      const invite = await api<UserInvite>("/auth/invites", { method: "POST", body: JSON.stringify({ email: form.get("email"), role: form.get("role") }) });
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

  async function updateDisplayName(userId: number, form: FormData) {
    await runUserAction(async () => {
      const user = await api<UserAccount>(`/auth/users/${userId}`, { method: "PATCH", body: JSON.stringify({ display_name: form.get("display_name") }) });
      return `${accountLabel(user)} renamed.`;
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

  async function assignCharacter(character: EqmCharacter, ownerUserId: string) {
    setUserError(null);
    try {
      const updated = await api<EqmCharacter>(`/characters/${character.id}`, { method: "PATCH", body: JSON.stringify({ owner_user_id: ownerUserId || null }) });
      setCharacters((current) => current.map((item) => item.id === updated.id ? updated : item));
      setMessage(`${updated.name} assigned to ${updated.owner_display_name ?? "Unassigned"}.`);
    } catch (err) {
      setUserError(err instanceof Error ? err.message : "Character assignment failed");
    }
  }

  useEffect(() => {
    void Promise.all([loadUsers(), loadInvites(), loadCharacterAssignments(), loadRoles()]).catch((err) => setUserError(err instanceof Error ? err.message : "Unable to load users"));
  }, []);

  return <div className="two-column"><section className="panel stacked"><h3>User Administration</h3><h4>Accounts</h4>{message && <div className="notice inline">{message}</div>}{latestInviteUrl && <div className="invite-link"><code>{latestInviteUrl}</code><button type="button" onClick={() => void navigator.clipboard.writeText(latestInviteUrl)}>Copy link</button></div>}{userError && <div className="mini-alert">{userError}</div>}<div className="card-list">{users.map((user) => <article key={user.id}><strong>{accountLabel(user)}</strong><span>{user.email}</span><ManagedForm submitLabel="Rename" onSubmit={(form) => updateDisplayName(user.id, form)}><label>Display name<input name="display_name" defaultValue={accountLabel(user)} required /></label></ManagedForm><label>Role<select value={user.role} onChange={(event) => void updateRole(user.id, event.target.value)}>{roles.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}</select></label><ManagedForm submitLabel="Reset password" onSubmit={(form) => resetPassword(user.id, form)}><label>New password<input name="password" type="password" minLength={8} required /></label></ManagedForm><div className="card-actions"><button className="danger" type="button" disabled={user.id === currentUser.id} onClick={() => void deleteAccount(user)}>{user.id === currentUser.id ? "Signed in" : "Delete user"}</button></div></article>)}</div></section><section className="panel stacked"><h3>Create Invite</h3><ManagedForm submitLabel="Generate invite" onSubmit={createInvite}><label>Email<input name="email" type="email" required /></label><label>Role<select name="role" defaultValue="member">{roles.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}</select></label></ManagedForm><h3>Pending Invites</h3><div className="card-list invite-list">{invites.map((invite) => <article key={invite.id}><strong>{invite.email}</strong><span>{invite.role} · {invite.status ?? "pending"}</span><span>Created {invite.created_at ? new Date(invite.created_at).toLocaleString() : "recently"}{invite.created_by_display_name ? ` by ${invite.created_by_display_name}` : ""}</span>{invite.accepted_at && <span>Accepted {new Date(invite.accepted_at).toLocaleString()}</span>}{invite.revoked_at && <span>Revoked {new Date(invite.revoked_at).toLocaleString()}</span>}<div className="card-actions"><button className="danger" type="button" disabled={invite.status !== "pending"} onClick={() => void revokeInvite(invite)}>Revoke</button></div></article>)}{invites.length === 0 && <p className="empty">No invites yet.</p>}</div><h3>Create Account Manually</h3><ManagedForm submitLabel="Create account" onSubmit={createAccount}><label>Display name<input name="display_name" required /></label><label>Email<input name="email" type="email" required /></label><label>Role<select name="role" defaultValue="member">{roles.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}</select></label><label>Temporary password<input name="password" type="password" minLength={8} required /></label></ManagedForm><h3>Character Assignment</h3><div className="card-list character-assignment-list">{characters.map((character) => <article key={character.id}><strong>{character.name}</strong>{character.character_id && <span>Character ID {character.character_id}</span>}<span>{character.owner_display_name ?? "Unassigned"}</span><span>{character.corporation_name ?? "Unknown corporation"}{character.alliance_name ? ` · ${character.alliance_name}` : ""}</span><label>EQM Account<select value={character.owner_user_id ?? ""} onChange={(event) => void assignCharacter(character, event.target.value)}><option value="">Unassigned</option>{accounts.map((account) => <option key={account.id} value={account.id}>{accountLabel(account)} ({account.role})</option>)}</select></label></article>)}{characters.length === 0 && <p className="empty">No characters available for assignment.</p>}</div></section></div>;
}
function Overview({ data }: { data: AppData }) {
  const summary = data.summary;
  const assetUnitsSyncedToday = data.assets.filter((asset) => isToday(asset.last_synced_at)).reduce((total, asset) => total + asset.quantity, 0);
  const blueprintsSyncedToday = data.blueprints.filter((blueprint) => isToday(blueprint.last_synced_at)).length;
  return (
    <>
      <div className="status-grid wide">
        <Metric icon={<Activity size={22} />} label="API status" value={data.health?.status ?? "checking"} />
        <Metric icon={<Database size={22} />} label="Backend app" value={data.health?.app ?? "pending"} />
        <Metric icon={<Boxes size={22} />} label="Owners" value={summary?.owners ?? 0} />
        <Metric icon={<PackagePlus size={22} />} label="Asset units" value={summary?.asset_units ?? 0} delta={syncedTodayLabel(assetUnitsSyncedToday, "units")} />
        <Metric icon={<ScrollText size={22} />} label="Blueprints" value={summary?.blueprints ?? 0} delta={syncedTodayLabel(blueprintsSyncedToday, "blueprints")} />
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
  const [roleDefinitions, setRoleDefinitions] = useState<RoleDefinition[]>([]);
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

  return <section className="panel stacked"><h3>Characters</h3>{message && <div className="notice inline">{message}</div>}{characterError && <div className="mini-alert">{characterError}</div>}<div className="card-list character-list">{characters.map((character) => <article key={character.id}><strong>{character.name}</strong>{character.character_id && <span>Character ID {character.character_id}</span>}{character.can_view_detail ? <><span>{character.owner_display_name ?? "Unassigned"}{character.owner_role ? ` · ${character.owner_role}` : ""}</span><span>{character.corporation_name ?? "Unknown corporation"}{character.alliance_name ? ` · ${character.alliance_name}` : ""}</span><span>Last sync {character.last_synced_at ? new Date(character.last_synced_at).toLocaleString() : "never"}</span>{character.can_assign && <label>EQM Account<select value={character.owner_user_id ?? ""} onChange={(event) => void patchCharacter(character.id, { owner_user_id: event.target.value || null }, `${character.name} reassigned.`)}><option value="">Unassigned</option>{accounts.map((account) => <option key={account.id} value={account.id}>{accountLabel(account)} ({account.role})</option>)}</select></label>}{character.can_manage && <label className="check"><input type="checkbox" checked={Boolean(character.public_assets_visible)} onChange={(event) => void patchCharacter(character.id, { public_assets_visible: event.target.checked }, `${character.name} visibility updated.`)} /> Public assets visible to members</label>}{currentUser.role === "admin" && !character.public_assets_visible && <div className="privacy-placard">This character has not made assets public to members. Admin asset sync is an override for administrative review.</div>}{currentUser.role === "admin" && character.sync_opt_out && <div className="privacy-placard">This character does not wish to be synced. Admins can override temporarily for administrative review, but this preference remains visible.</div>}</> : <span className="muted">Details hidden by role policy.</span>}</article>)}</div>{characters.length === 0 && <p className="empty">No characters visible to this account yet.</p>}</section>;
}
function Roster() {
  const [corporations, setCorporations] = useState<RosterCorporation[]>([]);
  const [rosterError, setRosterError] = useState<string | null>(null);

  async function loadRoster() {
    setRosterError(null);
    try {
      setCorporations(await api<RosterCorporation[]>("/characters/roster"));
    } catch (err) {
      setRosterError(err instanceof Error ? err.message : "Unable to load roster");
    }
  }

  useEffect(() => { void loadRoster(); }, []);

  const totalCharacters = corporations.reduce((total, corporation) => total + corporation.characters.length, 0);
  return <section className="panel stacked roster-page"><div className="section-heading"><div><h3>Roster</h3><p>{totalCharacters.toLocaleString()} character{totalCharacters === 1 ? "" : "s"} across {corporations.length.toLocaleString()} corporation{corporations.length === 1 ? "" : "s"}</p></div><button type="button" onClick={() => void loadRoster()}>Refresh</button></div>{rosterError && <div className="mini-alert">{rosterError}</div>}<div className="roster-corporations">{corporations.map((corporation) => <article key={corporation.corporation_id ?? corporation.corporation_name} className="roster-corp"><div className="roster-corp-heading"><div><strong>{corporation.corporation_name}{corporation.ticker ? ` [${corporation.ticker}]` : ""}</strong><span>{corporation.alliance_name ?? "No alliance"}{corporation.corporation_id ? ` · Corp ID ${corporation.corporation_id}` : ""}</span></div><span>{corporation.characters.length.toLocaleString()} listed · Members {corporation.member_count?.toLocaleString() ?? "unknown"}</span></div><div className="roster-character-grid">{corporation.characters.map((character) => <div key={character.character_id} className="roster-character"><span>{character.name}</span></div>)}</div></article>)}{corporations.length === 0 && <p className="empty">No roster characters assigned to Quartermaster accounts yet.</p>}</div></section>;
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
      const result = await api<{ characters_refreshed: number; skipped: number; failed?: number; errors?: string[] }>("/esi/sync/linked-corporations", { method: "POST", body: "{}" });
      const failNote = result.failed ? ` ${result.failed.toLocaleString()} failed; ${result.errors?.[0] ?? "check backend logs"}.` : "";
      setMessage(`Refreshed ${result.characters_refreshed.toLocaleString()} linked character corporation record${result.characters_refreshed === 1 ? "" : "s"}.${failNote}`);
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

  async function syncCorporationWallets(token: CorporationToken, corporation: EqmCorporation) {
    setBusyTokenId(token.token_id);
    setCorpError(null);
    setMessage(`Syncing ${corporation.name} wallet divisions with ${token.character_name}...`);
    try {
      const result = await api<{ corporation_name: string; wallet_divisions: number }>(`/esi/sync/corporation-wallets/${token.token_id}`, { method: "POST", body: "{}" });
      setMessage(`Synced ${result.wallet_divisions.toLocaleString()} wallet divisions for ${result.corporation_name}.`);
      await loadCorporations();
    } catch (err) {
      setMessage(null);
      setCorpError(err instanceof Error ? err.message : "Corporation wallet sync failed");
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
      for (const [index, corporation] of corporations.entries()) {
        const step = `${index + 1}/${corporations.length}`;
        const assetToken = corporation.eligible_tokens.find((token) => token.can_sync);
        if (assetToken) {
          setMessage(`${step}: syncing ${corporation.name} corporation assets with ${assetToken.character_name}...`);
          await api(`/esi/sync/corporation-assets/${assetToken.token_id}`, { method: "POST", body: "{}" });
          assetJobs += 1;
        }
        const blueprintToken = corporation.eligible_tokens.find((token) => token.can_sync_blueprints);
        if (blueprintToken) {
          setMessage(`${step}: syncing ${corporation.name} corporation blueprints with ${blueprintToken.character_name}...`);
          await api(`/esi/sync/corporation-blueprints/${blueprintToken.token_id}`, { method: "POST", body: "{}" });
          blueprintJobs += 1;
        }
        const walletToken = corporation.eligible_tokens.find((token) => token.can_sync_wallets);
        if (walletToken) {
          setMessage(`${step}: syncing ${corporation.name} wallet divisions with ${walletToken.character_name}...`);
          await api(`/esi/sync/corporation-wallets/${walletToken.token_id}`, { method: "POST", body: "{}" });
        }
      }
      setMessage(`Synced ${assetJobs} corporation asset ledger${assetJobs === 1 ? "" : "s"}, ${blueprintJobs} blueprint ledger${blueprintJobs === 1 ? "" : "s"}, and eligible wallet divisions.`);
      await Promise.all([loadCorporations(), loadAssets()]);
    } catch (err) {
      setCorpError(err instanceof Error ? err.message : "Sync all failed");
    } finally {
      setBusyAll(false);
    }
  }

  useEffect(() => { void loadCorporations().catch((err) => setCorpError(err instanceof Error ? err.message : "Unable to load corporations")); }, []);

  return <section className="panel stacked"><div className="section-heading"><h3>Corporations</h3><div className="button-row compact"><button type="button" onClick={() => void refreshCorporationLinks()}>Refresh corporation links</button><button type="button" disabled={busyAll || corporations.length === 0} onClick={() => void syncAllEligible()}>{busyAll ? "Syncing all" : "Sync all eligible"}</button></div></div>{message && <div className="notice inline">{message}</div>}{corpError && <div className="mini-alert">{corpError}</div>}<div className="card-list corporation-list">{corporations.map((corporation) => <article key={corporation.id}><strong>{corporation.name}{corporation.ticker ? ` [${corporation.ticker}]` : ""}</strong><span>{corporation.alliance_name ?? "No alliance"} · Corp ID {corporation.corporation_id}</span><span>CEO {corporation.ceo_character_name ?? corporation.ceo_character_eve_id ?? "unknown"}</span><span className="scope-ok">Members {corporation.member_count?.toLocaleString() ?? "unknown"}</span><span>{corporation.asset_rows.toLocaleString()} tracked asset rows · {corporation.blueprint_rows.toLocaleString()} blueprints</span><span className={corporation.asset_sync_stale ? "scope-warn" : "scope-ok"}>Assets {corporation.last_asset_sync_at ? `${new Date(corporation.last_asset_sync_at).toLocaleString()} (${corporation.last_asset_sync_status ?? "sync"})` : "never synced"}</span><span className={corporation.blueprint_sync_stale ? "scope-warn" : "scope-ok"}>Blueprints {corporation.last_blueprint_sync_at ? `${new Date(corporation.last_blueprint_sync_at).toLocaleString()} (${corporation.last_blueprint_sync_status ?? "sync"})` : "never synced"}</span><span className={corporation.wallet_sync_stale ? "scope-warn" : "scope-ok"}>Wallets {corporation.last_wallet_sync_at ? `${new Date(corporation.last_wallet_sync_at).toLocaleString()} (${corporation.last_wallet_sync_status ?? "sync"})` : "never synced"}</span>{corporation.last_asset_sync_message && <code>{corporation.last_asset_sync_message}</code>}{corporation.last_blueprint_sync_message && <code>{corporation.last_blueprint_sync_message}</code>}{corporation.last_wallet_sync_message && <code>{corporation.last_wallet_sync_message}</code>}<div className="wallet-grid"><span>Wallet divisions</span>{corporation.wallet_divisions.length > 0 ? corporation.wallet_divisions.map((wallet) => <div key={wallet.division}><strong>Division {wallet.division}</strong><span>{iskFormatter.format(wallet.balance)} ISK</span></div>) : <p className="muted">No wallet divisions synced yet.</p>}</div><div className="choice-list"><span>Corp sync tokens</span>{corporation.eligible_tokens.length > 0 ? corporation.eligible_tokens.map((token) => <div className="token-row" key={token.token_id}><span>{token.character_name} · {token.user_display_name}</span><div className="button-row compact">{token.has_corporation_asset_scope ? <button type="button" disabled={!token.can_sync || busyTokenId === token.token_id} onClick={() => void syncCorporationAssets(token, corporation)}>Assets</button> : <span className="scope-warn">Missing asset scope</span>}{token.has_corporation_blueprint_scope ? <button type="button" disabled={!token.can_sync_blueprints || busyTokenId === token.token_id} onClick={() => void syncCorporationBlueprints(token, corporation)}>Blueprints</button> : <span className="scope-warn">Missing blueprint scope</span>}{token.has_corporation_wallet_scope ? <button type="button" disabled={!token.can_sync_wallets || busyTokenId === token.token_id} onClick={() => void syncCorporationWallets(token, corporation)}>Wallets</button> : <span className="scope-warn">Missing wallet scope</span>}</div></div>) : <p className="muted">No linked character tokens found for this corporation yet.</p>}</div></article>)}</div>{corporations.length === 0 && <p className="empty">No corporations imported or linked yet. Re-link a CEO/director through EVE SSO to populate this list.</p>}</section>;
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
  const recipePageSize = 250;
  const [recipes, setRecipes] = useState<IndustryActivity[]>(data.activities);
  const [selectedRecipe, setSelectedRecipe] = useState<IndustryActivity | null>(null);
  const [recipeBusy, setRecipeBusy] = useState(false);
  const [recipeError, setRecipeError] = useState<string | null>(null);
  const [hasMoreRecipes, setHasMoreRecipes] = useState(data.activities.length >= recipePageSize);

  useEffect(() => {
    setRecipes(data.activities);
    setHasMoreRecipes(data.activities.length >= recipePageSize);
  }, [data.activities]);

  async function loadMoreRecipes() {
    if (recipeBusy || !hasMoreRecipes) return;
    setRecipeBusy(true);
    setRecipeError(null);
    try {
      const nextRecipes = await api<IndustryActivity[]>(`/quartermaster/industry-activities?limit=${recipePageSize}&offset=${recipes.length}`);
      setRecipes((current) => [...current, ...nextRecipes]);
      setHasMoreRecipes(nextRecipes.length === recipePageSize);
    } catch (err) {
      setRecipeError(err instanceof Error ? err.message : "Unable to load more recipes");
    } finally {
      setRecipeBusy(false);
    }
  }

  return (
    <div className="two-column">
      <section className="panel"><h3>Blueprints</h3><BlueprintList blueprints={data.blueprints} /></section>
      <section className="panel"><h3>Add Blueprint</h3><BlueprintForm submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} /></section>
      <section className="panel"><h3>Recipes</h3><p className="muted">Showing {recipes.length.toLocaleString()} loaded recipes. Scroll the list to load more.</p>{recipeError && <div className="mini-alert">{recipeError}</div>}<RecipeList activities={recipes} onSelect={setSelectedRecipe} onLoadMore={() => void loadMoreRecipes()} loadingMore={recipeBusy} hasMore={hasMoreRecipes} /></section>
      <section className="panel stacked"><h3>Add Recipe</h3><RecipeForm submit={submit} typeOptions={typeOptions} /><h3>Add Recipe Input</h3><RecipeInputForm submit={submit} typeOptions={typeOptions} activityOptions={activityOptions} /></section>
      {selectedRecipe && <RecipeDetailModal activity={selectedRecipe} onClose={() => setSelectedRecipe(null)} />}
    </div>
  );
}
function SettingsPage({ currentUser }: { currentUser: UserAccount }) {
  const [characters, setCharacters] = useState<EqmCharacter[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [suppressPeekNotifications, setSuppressPeekNotifications] = useState(false);
  const [sdeStatus, setSdeStatus] = useState<SdeStatus | null>(null);
  const [sdePath, setSdePath] = useState("/sde");
  const [sdeBusy, setSdeBusy] = useState(false);

  async function loadCharacters() {
    setCharacters(await api<EqmCharacter[]>("/characters"));
  }

  async function loadSdeStatus() {
    if (currentUser.role !== "admin") return;
    const status = await api<SdeStatus>("/sde/status");
    setSdeStatus(status);
    setSdePath((current) => current || status.default_source_path || "/sde");
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
    setMessage("Importing SDE. This can take a few minutes on the first run...");
    try {
      const result = await api<SdeImportResult>("/sde/import", { method: "POST", body: JSON.stringify({ source_path: sdePath }) });
      setSdeStatus({ default_source_path: sdePath, categories: result.categories, groups: result.groups, types: result.types, blueprint_activities: result.blueprint_activities, activity_inputs: result.activity_inputs });
      setMessage(`Imported SDE from ${result.source_path}: ${result.types.toLocaleString()} types and ${result.blueprint_activities.toLocaleString()} blueprint activities.`);
    } catch (err) {
      setMessage(null);
      setSettingsError(err instanceof Error ? err.message : "SDE import failed");
    } finally {
      setSdeBusy(false);
    }
  }

  useEffect(() => {
    void loadCharacters().catch((err) => setSettingsError(err instanceof Error ? err.message : "Unable to load settings"));
    void loadSdeStatus().catch((err) => currentUser.role === "admin" && setSettingsError(err instanceof Error ? err.message : "Unable to load SDE status"));
  }, []);

  const manageable = characters.filter((character) => character.can_manage || currentUser.role === "admin");
  return <div className="stacked"><section className="panel stacked"><h3>Character Privacy</h3>{message && <div className="notice inline">{message}</div>}{settingsError && <div className="mini-alert">{settingsError}</div>}{currentUser.role === "admin" && <div className="privacy-placard"><label className="check"><input type="checkbox" checked={suppressPeekNotifications} onChange={(event) => void patchNotificationSuppression(event.target.checked)} /> Suppress sync peek notifications for development or mandatory-public ESI corporations</label></div>}<div className="card-list">{manageable.map((character) => <article key={character.id}><strong>{character.name}</strong><span>{character.corporation_name ?? "Unknown corporation"}{character.owner_display_name ? ` · ${character.owner_display_name}` : ""}</span><label className="check"><input type="checkbox" checked={Boolean(character.public_assets_visible)} onChange={(event) => void patchCharacter(character, { public_assets_visible: event.target.checked }, `${character.name} public asset visibility updated.`)} /> Public assets visible to members</label><label className="check"><input type="checkbox" checked={Boolean(character.sync_opt_out)} onChange={(event) => void patchCharacter(character, { sync_opt_out: event.target.checked }, `${character.name} sync preference updated.`)} /> Keep this character private from shared Quartermaster sync</label>{character.sync_opt_out && <div className="privacy-placard">This character does not wish to be synced. Admins can override temporarily for administrative review, but this preference remains visible.</div>}</article>)}{manageable.length === 0 && <p className="empty">No manageable characters found.</p>}</div></section>{currentUser.role === "admin" && <section className="panel stacked"><div className="section-heading"><div><h3>SDE Import</h3><p>Load EVE static data from a mounted SDE folder or zip inside the backend container.</p></div><button type="button" onClick={() => void loadSdeStatus()}>Refresh</button></div><div className="status-grid compact"><Metric icon={<Database size={18} />} label="Categories" value={sdeStatus?.categories ?? 0} /><Metric icon={<Boxes size={18} />} label="Groups" value={sdeStatus?.groups ?? 0} /><Metric icon={<PackagePlus size={18} />} label="Types" value={sdeStatus?.types ?? 0} /><Metric icon={<Factory size={18} />} label="Recipes" value={sdeStatus?.blueprint_activities ?? 0} /><Metric icon={<ScrollText size={18} />} label="Inputs" value={sdeStatus?.activity_inputs ?? 0} /></div><label>SDE path<input value={sdePath} onChange={(event) => setSdePath(event.target.value)} placeholder="/sde or /sde/sde.zip" /></label><button type="button" disabled={sdeBusy} onClick={() => void importSde()}><RefreshCw size={18} /> {sdeBusy ? "Importing" : "Import SDE"}</button></section>}{currentUser.role === "admin" && <PermissionsAdmin />}</div>;
}
function PermissionsAdmin() {
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
    setMessage(`User permission updated.`);
    await loadPermissions();
  }

  useEffect(() => { void loadPermissions().catch((err) => setError(err instanceof Error ? err.message : "Unable to load permissions")); }, []);

  return <section className="panel stacked"><div className="section-heading"><div><h3>Section Permissions</h3><p>Choose what roles can see, then add individual account exceptions where needed.</p></div><button type="button" onClick={() => void loadPermissions()}>Refresh</button></div>{message && <div className="notice inline">{message}</div>}{error && <div className="mini-alert">{error}</div>}<h4>Create role</h4><ManagedForm submitLabel="Create role" onSubmit={createRole}><label>Display name<input name="display_name" placeholder="Logistics" required /></label><label>Machine name<input name="name" placeholder="logistics" /></label><label>Base role<select name="base_role" defaultValue="member"><option value="view_only">View Only</option><option value="member">Member</option><option value="officer">Officer</option><option value="director">Director</option></select></label></ManagedForm><h4>Role defaults</h4><div className="permission-grid"><div className="permission-header">Section</div>{roles.map((role) => <div key={role} className="permission-header">{role}</div>)}{matrix?.sections.map((section) => <React.Fragment key={section.key}><div><strong>{section.label}</strong><span>Default: {section.default_roles.join(", ")}</span></div>{roles.map((role) => { const value = roleValue(role, section.key); return <label key={`${role}-${section.key}`}><select value={value === undefined ? "default" : value ? "allow" : "deny"} onChange={(event) => void patchRole(role, section.key, event.target.value)}><option value="default">Default</option><option value="allow">Allow</option><option value="deny">Deny</option></select></label>; })}</React.Fragment>)}</div><h4>User overrides</h4><div className="card-list permission-user-list">{users.filter((user) => user.role !== "admin").map((user) => <article key={user.id}><strong>{accountLabel(user)} <span className="muted">({user.role})</span></strong><div className="permission-user-grid">{matrix?.sections.map((section) => { const value = userValue(user.id, section.key); return <label key={`${user.id}-${section.key}`}>{section.label}<select value={value === undefined ? "inherit" : value ? "allow" : "deny"} onChange={(event) => void patchUser(user.id, section.key, event.target.value)}><option value="inherit">Inherit</option><option value="allow">Allow</option><option value="deny">Deny</option></select></label>; })}</div></article>)}</div></section>;
}
function CharacterSkills({ currentUser }: { currentUser: UserAccount }) {
  const [profiles, setProfiles] = useState<CharacterSkillProfile[]>([]);
  const [expandedProfileIds, setExpandedProfileIds] = useState<Set<number>>(new Set());
  const [skillError, setSkillError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busyTokenId, setBusyTokenId] = useState<number | null>(null);
  const baseSkillSp = [0, 250, 1415, 8000, 45255, 256000];

  async function loadSkills() {
    setProfiles(await api<CharacterSkillProfile[]>("/esi/character-skills"));
  }

  async function syncSkills(profile: CharacterSkillProfile) {
    if (!profile.can_sync) return;
    if (profile.sync_opt_out && profile.owner_user_id !== currentUser.id && currentUser.role === "admin" && !window.confirm(`${profile.character_name} has opted out of normal sync. Temporarily override as admin?`)) return;
    setBusyTokenId(profile.token_id);
    setSkillError(null);
    setMessage(`Syncing skills for ${profile.character_name}...`);
    try {
      const result = await api<{ character_name: string; skill_count: number; queue_count: number; total_skill_points: number }>(`/esi/sync/character-skills/${profile.token_id}`, { method: "POST", body: "{}" });
      setMessage(`Synced ${result.skill_count.toLocaleString()} skills and ${result.queue_count.toLocaleString()} queued skills for ${result.character_name}.`);
      await loadSkills();
    } catch (err) {
      setMessage(null);
      setSkillError(err instanceof Error ? err.message : "Skill sync failed");
    } finally {
      setBusyTokenId(null);
    }
  }

  function toggleProfile(tokenId: number) {
    setExpandedProfileIds((current) => {
      const next = new Set(current);
      if (next.has(tokenId)) next.delete(tokenId);
      else next.add(tokenId);
      return next;
    });
  }

  function groupedSkills(profile: CharacterSkillProfile) {
    const groups = new Map<string, SkillRecord[]>();
    for (const skill of profile.skills) {
      const key = skill.skill_group_name || skill.skill_category_name || "Uncategorized";
      groups.set(key, [...(groups.get(key) ?? []), skill]);
    }
    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }));
  }

  function categorySkillPoints(skills: SkillRecord[]) {
    return skills.reduce((total, skill) => total + skill.skillpoints_in_skill, 0);
  }

  function skillProgress(skill: SkillRecord) {
    const currentSp = skill.skillpoints_in_skill;
    const currentLevel = Math.max(0, Math.min(5, skill.trained_skill_level || skill.active_skill_level || 0));
    const nextLevel = Math.min(5, currentLevel + (currentLevel < 5 ? 1 : 0));
    const baseForCurrent = baseSkillSp[currentLevel] || 250;
    const rankEstimate = currentLevel > 0 ? Math.max(1, Math.min(16, Math.floor(currentSp / baseForCurrent) || 1)) : 1;
    const targetSp = Math.max(baseSkillSp[nextLevel] * rankEstimate, currentSp || baseSkillSp[1]);
    return { targetSp, percent: Math.max(0, Math.min(100, (currentSp / targetSp) * 100)) };
  }

  useEffect(() => { void loadSkills().catch((err) => setSkillError(err instanceof Error ? err.message : "Unable to load character skills")); }, []);

  return <section className="panel stacked"><div className="section-heading"><h3>Character Skills</h3><div className="button-row compact"><button type="button" onClick={() => setExpandedProfileIds(new Set(profiles.map((profile) => profile.token_id)))}>Expand all</button><button type="button" onClick={() => setExpandedProfileIds(new Set())}>Collapse all</button><button type="button" onClick={() => void loadSkills()}>Refresh</button></div></div>{message && <div className="notice inline">{message}</div>}{skillError && <div className="mini-alert">{skillError}</div>}<div className="card-list skill-profiles">{profiles.map((profile) => { const expanded = expandedProfileIds.has(profile.token_id); return <article key={profile.token_id} className="skill-profile-card"><div className="section-heading compact skill-profile-heading"><button type="button" className="skill-profile-toggle" onClick={() => toggleProfile(profile.token_id)} aria-expanded={expanded}>{expanded ? "Collapse" : "Expand"}</button><div><strong>{profile.character_name}</strong><span>Character ID {profile.character_id}</span></div><div className="button-row compact">{profile.can_sync && <button type="button" disabled={profile.missing_skill_scopes.length > 0 || busyTokenId === profile.token_id} onClick={() => void syncSkills(profile)}>{busyTokenId === profile.token_id ? "Syncing" : profile.sync_opt_out && profile.owner_user_id !== currentUser.id && currentUser.role === "admin" ? "Admin override sync" : "Sync skills"}</button>}</div></div>{profile.sync_opt_out && <div className="privacy-placard">This character does not wish to be synced.{profile.admin_override_visible ? " Admin view is active for administrative review." : " This data stays private to the character owner unless an admin opens an override view."}</div>}{profile.can_sync && profile.missing_skill_scopes.length > 0 && <span className="scope-warn">Missing skill scopes: {profile.missing_skill_scopes.join(", ")}. Re-link through ESI Sync.</span>}<div className="status-grid compact"><Metric icon={<GraduationCap size={18} />} label="Total SP" value={profile.total_skill_points ?? 0} /><Metric icon={<Plus size={18} />} label="Unallocated SP" value={profile.unallocated_skill_points ?? 0} /><Metric icon={<ScrollText size={18} />} label="Skills" value={profile.skill_count} /></div><span>Skills synced {profile.skills_synced_at ? new Date(profile.skills_synced_at).toLocaleString() : "never"} · Queue synced {profile.skill_queue_synced_at ? new Date(profile.skill_queue_synced_at).toLocaleString() : "never"}</span>{expanded && <div className="two-column skill-columns"><section><h4>Trained Skills</h4><div className="skill-group-list">{groupedSkills(profile).map(([groupName, skills]) => <details key={groupName} className="skill-group" open><summary>{groupName}<span>{skills.length.toLocaleString()} skills · {categorySkillPoints(skills).toLocaleString()} SP</span></summary><div className="mini-list">{skills.map((skill) => { const progress = skillProgress(skill); return <div key={skill.id} className="skill-row"><strong>{skill.skill_name}</strong><span>Level {skill.trained_skill_level} · Active {skill.active_skill_level}</span><div className="skill-progress-line"><span>{skill.skillpoints_in_skill.toLocaleString()} / {progress.targetSp.toLocaleString()} SP</span><span>{Math.round(progress.percent)}%</span></div><div className="skill-progress-bar" title="Progress target is estimated until SDE dogma skill ranks are imported."><i style={{ width: `${progress.percent}%` }} /></div></div>; })}</div></details>)}{profile.skills.length === 0 && <p className="empty">No trained skills imported yet.</p>}</div></section><section><h4>Current Queue</h4><div className="mini-list">{profile.queue.map((entry) => <div key={entry.id}><strong>{entry.queue_position + 1}. {entry.skill_name}</strong><span>To level {entry.finished_level}{entry.finish_date ? ` · finishes ${new Date(entry.finish_date).toLocaleString()}` : ""}</span></div>)}{profile.queue.length === 0 && <p className="empty">No active queue imported.</p>}</div></section></div>}</article>; })}{profiles.length === 0 && <p className="empty">No linked characters visible. Link a character through ESI Sync first.</p>}</div></section>;
}
function Esi({ load, currentUser }: { load: () => Promise<void>; currentUser: UserAccount }) {
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
        {linked.length > 0 ? <div className="card-list">{linked.map((character) => <article key={character.token_id}><strong>{character.character_name}</strong><span>Character ID {character.character_id}</span>{currentUser.role === "admin" && <span>SSO linked by {character.linked_user_display_name}</span>}<span>Last sync {character.last_sync_at ? `${new Date(character.last_sync_at).toLocaleString()} (${character.last_sync_type ?? "sync"})` : "never"}</span><span>Linked {character.linked_at ? new Date(character.linked_at).toLocaleString() : "recently"}</span>{scopeStatus(character, "public")}{scopeStatus(character, "standing")}{(character.can_sync_assets || character.can_unlink || (character.linked_user_id === currentUser.id && character.missing_standing_scopes.length > 0 && standingAuthInfo?.ready)) && <div className="card-actions">{character.can_sync_assets && <button type="button" onClick={() => void syncAssets(character.token_id, character.character_name)}>Sync assets</button>}{character.linked_user_id === currentUser.id && character.missing_standing_scopes.length > 0 && standingAuthInfo?.ready ? <a className="mini-link" href={standingAuthInfo.url}>Authorize standing sync</a> : null}{character.can_unlink && <button className="danger" type="button" onClick={() => void unlinkCharacter(character.token_id, character.character_name)}>Unlink</button>}</div>}</article>)}</div> : <p className="muted">No EVE characters linked yet.</p>}
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
function Metric({ icon, label, value, delta }: { icon: React.ReactNode; label: string; value: string | number; delta?: string }) {
  const isEmptyDelta = delta?.startsWith("No ");
  return <article>{icon}<span>{label}</span><strong>{typeof value === "number" ? numberFormatter.format(value) : value}</strong>{delta && <small className={isEmptyDelta ? "metric-delta empty" : "metric-delta"}>{delta}</small>}</article>;
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
  const [kindFilter, setKindFilter] = useState<"all" | "bpo" | "bpc">("all");
  const [ownerFilter, setOwnerFilter] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<"name" | "me" | "te">("name");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const bpoCount = blueprints.filter((blueprint) => !blueprint.is_copy).length;
  const bpcCount = blueprints.filter((blueprint) => blueprint.is_copy).length;
  const ownerOptions = [...new Set(blueprints.map((blueprint) => blueprint.owner_name).filter(Boolean))].sort((left, right) => left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }));
  const ownerCounts = new Map<string, number>();
  for (const blueprint of blueprints) ownerCounts.set(blueprint.owner_name, (ownerCounts.get(blueprint.owner_name) ?? 0) + 1);
  const kindFilteredBlueprints = kindFilter === "all" ? blueprints : blueprints.filter((blueprint) => kindFilter === "bpc" ? blueprint.is_copy : !blueprint.is_copy);
  const filteredBlueprints = ownerFilter ? kindFilteredBlueprints.filter((blueprint) => blueprint.owner_name === ownerFilter) : kindFilteredBlueprints;
  const visibleBlueprints = [...filteredBlueprints].sort((left, right) => {
    const direction = sortDirection === "asc" ? 1 : -1;
    if (sortKey === "name") return left.blueprint_type_name.localeCompare(right.blueprint_type_name, undefined, { numeric: true, sensitivity: "base" }) * direction;
    const leftValue = sortKey === "me" ? left.material_efficiency : left.time_efficiency;
    const rightValue = sortKey === "me" ? right.material_efficiency : right.time_efficiency;
    return (leftValue - rightValue || left.blueprint_type_name.localeCompare(right.blueprint_type_name, undefined, { numeric: true, sensitivity: "base" })) * direction;
  });

  function chooseSort(nextSortKey: "name" | "me" | "te") {
    if (sortKey === nextSortKey) {
      setSortDirection((current) => current === "asc" ? "desc" : "asc");
      return;
    }
    setSortKey(nextSortKey);
    setSortDirection(nextSortKey === "name" ? "asc" : "desc");
  }

  function sortLabel(key: "name" | "me" | "te") {
    return sortKey === key ? (sortDirection === "asc" ? "up" : "down") : "";
  }

  return <div className="blueprint-browser"><div className="blueprint-controls"><div className="blueprint-filter"><button type="button" className={kindFilter === "all" ? "active" : ""} onClick={() => setKindFilter("all")}>All <span>{blueprints.length.toLocaleString()}</span></button><button type="button" className={kindFilter === "bpo" ? "active" : ""} onClick={() => setKindFilter("bpo")}>BPO <span>{bpoCount.toLocaleString()}</span></button><button type="button" className={kindFilter === "bpc" ? "active" : ""} onClick={() => setKindFilter("bpc")}>BPC <span>{bpcCount.toLocaleString()}</span></button></div><div className="blueprint-filter sort"><button type="button" className={sortKey === "name" ? "active" : ""} onClick={() => chooseSort("name")}>A-Z <span>{sortLabel("name")}</span></button><button type="button" className={sortKey === "me" ? "active" : ""} onClick={() => chooseSort("me")}>ME <span>{sortLabel("me")}</span></button><button type="button" className={sortKey === "te" ? "active" : ""} onClick={() => chooseSort("te")}>TE <span>{sortLabel("te")}</span></button></div></div><div className="blueprint-filter owners"><button type="button" className={ownerFilter === null ? "active" : ""} onClick={() => setOwnerFilter(null)}>All owners <span>{blueprints.length.toLocaleString()}</span></button>{ownerOptions.map((owner) => <button type="button" key={owner} className={ownerFilter === owner ? "active" : ""} onClick={() => setOwnerFilter(owner)}>{owner} <span>{(ownerCounts.get(owner) ?? 0).toLocaleString()}</span></button>)}</div><div className="card-list">{visibleBlueprints.map((bp) => <article key={bp.id}><strong>{bp.blueprint_type_name}</strong><span><button type="button" className="inline-filter" onClick={() => setOwnerFilter(bp.owner_name)}>{bp.owner_name}</button> · {bp.product_type_name ?? "No product"}</span><div className="badge-row"><button type="button" className="bp-badge" onClick={() => chooseSort("me")}>ME {bp.material_efficiency}</button><button type="button" className="bp-badge" onClick={() => chooseSort("te")}>TE {bp.time_efficiency}</button><button type="button" className={bp.is_copy ? "bp-badge copy" : "bp-badge original"} onClick={() => setKindFilter(bp.is_copy ? "bpc" : "bpo")}>{bp.is_copy ? "BPC" : "BPO"}</button></div></article>)}{blueprints.length === 0 && <p className="empty">No blueprints yet.</p>}{blueprints.length > 0 && visibleBlueprints.length === 0 && <p className="empty">No blueprints match this filter.</p>}</div></div>;
}

function RecipeList({ activities, onSelect, onLoadMore, loadingMore, hasMore }: { activities: IndustryActivity[]; onSelect: (activity: IndustryActivity) => void; onLoadMore: () => void; loadingMore: boolean; hasMore: boolean }) {
  function handleScroll(event: React.UIEvent<HTMLDivElement>) {
    const element = event.currentTarget;
    if (element.scrollHeight - element.scrollTop - element.clientHeight < 160) onLoadMore();
  }

  return <div className="card-list recipe-list" onScroll={handleScroll}>{activities.map((activity) => <article key={activity.id}><button type="button" className="recipe-card-button" onClick={() => onSelect(activity)}><strong>{activity.blueprint_type_name}</strong><span>{activity.activity_kind} · {activity.product_type_name ?? "No product"} x{activity.product_quantity}</span><span>{activity.inputs.length.toLocaleString()} inputs · {activity.time_seconds ? `${numberFormatter.format(activity.time_seconds)} sec` : "No time listed"}</span></button></article>)}{activities.length === 0 && <p className="empty">No recipes yet.</p>}{loadingMore && <p className="muted">Loading more recipes...</p>}{!loadingMore && !hasMore && activities.length > 0 && <p className="muted">All visible recipes loaded.</p>}</div>;
}

function RecipeDetailModal({ activity, onClose }: { activity: IndustryActivity; onClose: () => void }) {
  return <div className="modal-backdrop" role="presentation" onClick={onClose}><section className="modal-window recipe-detail" role="dialog" aria-modal="true" aria-label={`${activity.blueprint_type_name} recipe`} onClick={(event) => event.stopPropagation()}><div className="section-heading"><div><h3>{activity.blueprint_type_name}</h3><p>{activity.activity_kind} · {activity.product_type_name ?? "No product"} x{activity.product_quantity}</p></div><button type="button" onClick={onClose}>Close</button></div><div className="status-grid compact"><Metric icon={<Factory size={18} />} label="Activity" value={activity.activity_kind.replace("_", " ")} /><Metric icon={<PackagePlus size={18} />} label="Output" value={activity.product_quantity} /><Metric icon={<ScrollText size={18} />} label="Inputs" value={activity.inputs.length} /><Metric icon={<Activity size={18} />} label="Time" value={activity.time_seconds ? `${numberFormatter.format(activity.time_seconds)} sec` : "n/a"} /></div><h4>Material Inputs</h4><div className="mini-list recipe-inputs">{activity.inputs.map((input) => <div key={input.id}><strong>{input.input_type_name}</strong><span>{numberFormatter.format(input.quantity)} {input.consume_type}</span></div>)}{activity.inputs.length === 0 && <p className="empty">No material inputs listed for this activity.</p>}</div></section></div>;
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
  return ({ overview: "Quartermaster Overview", ownership: "Ownership and Locations", characters: "Characters", roster: "Alliance Roster", analytics: "Analytics Platform", skills: "Character Skills", settings: "Settings", corporations: "Corporations", assets: "Asset Ledger", industry: "Blueprints and Recipes", esi: "ESI Sync", profile: "Profile", users: "User Administration", audit: "Audit Log" } as Record<string, string>)[tab];
}

function subtitleFor(tab: string) {
  return ({ overview: "Live status and the first useful totals from the database.", ownership: "Define the characters, corporations, manual buckets, and places assets can belong to.", characters: "Assign EVE characters to Quartermaster accounts and control public asset visibility.", roster: "A corporation-grouped character roster suitable for diplomats and prospective members.", analytics: "Snapshot history, metric widgets, exports, and the foundation for custom dashboards.", skills: "Import trained skills, total skill points, and active skill queues from ESI.", settings: "Control character visibility and sync privacy.", corporations: "Review enrolled corporations and sync corporation asset ledgers through authorized CEO or director tokens.", assets: "Track item stacks by owner, type, location, and EVE-style location flag.", industry: "Store blueprints, recipe activities, and material inputs before wiring in SDE imports.", esi: "A holding area for the upcoming SSO and sync work.", profile: "Manage your account and private messages.", users: "Manage Quartermaster accounts and role levels.", audit: "Review sync peeks, system events, and administrative activity." } as Record<string, string>)[tab];
}

createRoot(document.getElementById("root")!).render(<App />);







































