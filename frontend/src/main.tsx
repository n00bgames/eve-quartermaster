import { Activity, Boxes, Building2, CalendarDays, ClipboardList, Coins, Database, Factory, FlaskConical, GraduationCap, Globe2, KeyRound, MapIcon, MessageCircle, NotebookTabs, PackagePlus, Pickaxe, Plus, RefreshCw, ScrollText, Settings, ShoppingCart, Siren, Sparkles, Store, UserRoundCheck } from "lucide-react";

import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { createRoot } from "react-dom/client";

import "./styles.css";
import "./responsive.css";

import { api } from "./lib/api";
import { eveSecurityClass, eveSecurityLabel, isUedamaSystem } from "./lib/evePresentation";
import { BROWSER_TIMEZONE, formatDateTime, formatDurationMs, formatTimeOnly, localizeUtcHourLabel, preferredTimeZone, timezoneChoices } from "./lib/time";
import { assetFamily, assetSubtype, blueprintFamily, blueprintSubtype, inventoryFamilyLabels, looksCapitalRelated, matchesInventoryFamily, sortedUnique, visibleAssetLocations, visibleAssetQuantity } from "./lib/inventory";
import { BlueprintHoverCard, blueprintHoverDetails } from "./components/BlueprintHoverCard";
import { WardecBadge } from "./components/WardecBadge";
import { MarketAppraisalPage } from "./features/market/MarketAppraisalPage";
import { CorporateExchangePage } from "./features/exchange/CorporateExchangePage";
import { PublicExchangeListingPage } from "./features/exchange/PublicExchangeListingPage";
import { HyperNetTrackerPage } from "./features/hypernet/HyperNetTrackerPage";
import { ManufacturingPage } from "./features/manufacturing/ManufacturingPage";
import { NotesListsPage } from "./features/notes/NotesListsPage";
import { FittingsPage } from "./features/fittings/FittingsPage";
import { AnalyticsPlatform } from "./features/analytics/AnalyticsPlatform";
import { JumpFreighterPlanner } from "./features/navigation/JumpFreighterPlanner";
import { Roster } from "./features/characters/Roster";
import { CharacterSkills } from "./features/characters/CharacterSkills";
import { CharacterHoverName as CharacterHoverNameBase, type CharacterHoverNameProps } from "./features/characters/CharacterHoverName";
import { CharactersPage } from "./features/characters/CharactersPage";
import { JumpClonesPage } from "./features/characters/JumpClonesPage";
import { ProfilePage } from "./features/profile/ProfilePage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { EsiSyncPage } from "./features/esi/EsiSyncPage";
import { ContractsPage } from "./features/contracts/ContractsPage";
import { CorporationsPage } from "./features/corporations/CorporationsPage";
import { BlueprintPreview } from "./features/industry/BlueprintPreview";
import { ResearchProjectsPage } from "./features/industry/ResearchProjectsPage";
import { PlanetaryIndustryPage } from "./features/industry/PlanetaryIndustryPage";
import { MiningLedgerPage } from "./features/mining/MiningLedgerPage";
import { RecruitingPage } from "./features/recruiting/RecruitingPage";
import { RecruitingPublicPage } from "./features/recruiting/RecruitingPublicPage";
import { EventsPage } from "./features/events/EventsPage";
import { NextEventBadge } from "./features/events/NextEventBadge";
import { UpcomingEventsWidget } from "./features/events/UpcomingEventsWidget";
import { IndustrialSystemThreatWidget, LocalThreatWidget, PvpIntelWidget } from "./features/navigation/ThreatIntelWidgets";
import { RouteChecker } from "./features/navigation/RouteChecker";
import type { CharacterFocus } from "./types/characters";
import type { Asset, AssetFilter, AssetFilterKey, AssetPagePayload, AssetSortKey, AssetTableSeed, Blueprint, EveType, IndustryActivity, InventoryFamilyFilter, Location, MissingBlueprintCatalog, Owner, OwnerKindFilter, SortDirection, Summary } from "./types/inventory";
import type { AuditEvent, NotificationInbox, PrivateMessage, ProfileFocus } from "./types/profile";
import type { SectionPermission } from "./types/settings";
import type { FittingSeed } from "./types/fittings";
import type { JumpFreighterRoute, NavigationGatecheckRoute, NavigationRoute, NavigationSystem, UedamaScoutStatus } from "./types/navigation";
import { APP_VERSION } from "./version";



type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;

type Health = { status: string; app: string };

type UserAccount = { id: number; email: string; display_name: string; role: string; timezone?: string; created_at?: string };

type EffectivePermissions = { sections: SectionPermission[]; permissions: Record<string, boolean> };

type AuthResponse = { access_token?: string | null; remembered?: boolean; user: UserAccount };

type BootstrapStatus = { needs_admin: boolean; roles: string[] };

type InviteInfo = { email: string; role: string; expires_at?: string | null };


type MarketSeed = { text: string; nonce: number };





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






function accountLabel(user: UserAccount): string {

  const name = user.display_name?.trim();

  if (name && !name.includes("@")) return name;

  const localPart = user.email.split("@")[0]?.trim();

  return localPart || name || `User ${user.id}`;

}

const emptyData: AppData = { health: null, summary: null, owners: [], types: [], locations: [], assets: [], blueprints: [], activities: [] };

const numberFormatter = new Intl.NumberFormat();






async function sendDestinationToEve(destinationId?: number | null, destinationName = "this location") {
  if (!destinationId) {
    window.alert("No EVE destination ID is available for this location yet.");
    return;
  }
  if (!window.confirm(`Set ${destinationName} as your EVE destination?`)) return;
  try {
    await api("/esi/ui/waypoint", {
      method: "POST",
      body: JSON.stringify({ destination_id: destinationId, clear_other_waypoints: true, add_to_beginning: false }),
    });
    window.alert(`Destination sent to EVE: ${destinationName}`);
  } catch (error) {
    window.alert(error instanceof Error ? error.message : "Could not send destination to EVE.");
  }
}

function UedamaScoutLiveLink({ status }: { status: UedamaScoutStatus | null }) {
  if (!status?.is_live) return null;
  return <a className="twitch-live-link" href={status.url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>Uedama Scout live</a>;
}
type EveEntityKind = "character" | "corporation" | "alliance";

type EveIconSize = "tiny" | "sm" | "md" | "lg";



function eveImageUrl(kind: EveEntityKind, id: number, size = 64): string {

  const folder = kind === "character" ? "characters" : kind === "corporation" ? "corporations" : "alliances";

  const variant = kind === "character" ? "portrait" : "logo";

  return `https://images.evetech.net/${folder}/${id}/${variant}?size=${size}`;

}



function entityInitials(name?: string | null): string {

  const words = (name ?? "EQM").replace(/[^a-zA-Z0-9 ]/g, " ").trim().split(/\s+/).filter(Boolean);

  return (words.slice(0, 2).map((word) => word[0]).join("") || "EQ").toUpperCase();

}



function EveEntityIcon({ kind, id, name, size = "sm" }: { kind: EveEntityKind; id?: number | null; name?: string | null; size?: EveIconSize }) {

  const [failed, setFailed] = useState(false);

  const pixelSize = size === "lg" ? 128 : size === "md" ? 64 : 32;

  if (!id || failed) return <span className={`eve-icon eve-icon-${size} eve-icon-fallback eve-icon-${kind}`} aria-hidden="true">{entityInitials(name)}</span>;

  return <img className={`eve-icon eve-icon-${size} eve-icon-${kind}`} src={eveImageUrl(kind, id, pixelSize)} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />;

}

function CharacterHoverName(props: CharacterHoverNameProps) {
  return <CharacterHoverNameBase {...props} api={api} EveEntityIcon={EveEntityIcon} numberFormatter={numberFormatter} />;
}










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

  const [marketSeed, setMarketSeed] = useState<MarketSeed | null>(null);

  const [fittingSeed, setFittingSeed] = useState<FittingSeed | null>(null);

  const [assetSeed, setAssetSeed] = useState<AssetTableSeed | null>(null);

  const [characterFocus, setCharacterFocus] = useState<CharacterFocus | null>(null);

  const [data, setData] = useState<AppData>(emptyData);

  const [error, setError] = useState<string | null>(null);

  const [notice, setNotice] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);

  const [user, setUser] = useState<UserAccount | null>(null);

  const [bootstrap, setBootstrap] = useState<BootstrapStatus | null>(null);

  const [authReady, setAuthReady] = useState(false);

  const [locationHash, setLocationHash] = useState(window.location.hash);

  const [permissions, setPermissions] = useState<Record<string, boolean>>({ overview: true, profile: true });



  async function refreshAuth() {

    let authenticatedUser: UserAccount | null = null;

    try {

      const boot = await api<BootstrapStatus>("/auth/bootstrap");

      setBootstrap(boot);

      if (!boot.needs_admin) {

        try {

          const currentUser = await api<UserAccount>("/auth/me");

          setUser(currentUser);

          authenticatedUser = currentUser;

          const permissionPayload = await api<EffectivePermissions>("/auth/permissions/effective");

          setPermissions(permissionPayload.permissions);

        } catch {

          localStorage.removeItem("eq_access_token");

          setUser(null);

        }

      }

    } catch (err) {

      setError(err instanceof Error ? err.message : "Authentication check failed.");

    } finally {

      setAuthReady(true);

    }

    return authenticatedUser;

  }


  async function completeAuth(path: string, body: Record<string, unknown>) {

    const result = await api<AuthResponse>(path, { method: "POST", body: JSON.stringify(body) });

    if (result.access_token) localStorage.setItem("eq_access_token", result.access_token);
    else localStorage.removeItem("eq_access_token");

    setUser(result.user);

    const permissionPayload = await api<EffectivePermissions>("/auth/permissions/effective");

    setPermissions(permissionPayload.permissions);

    setNotice(`Signed in as ${result.user.display_name}.`);

    if (new URLSearchParams(window.location.search).has("invite")) window.history.replaceState({}, "", window.location.pathname);

    if (result.user.role === "applicant") {

      setActiveTab("recruiting");

      window.history.replaceState({}, "", "/#recruiting");

    }

    await load(result.user.role);

  }



  async function signOut() {

    try {

      await api("/auth/logout", { method: "POST", body: "{}" });

    } catch {

      // Local sign-out must still complete if the server is temporarily unreachable.

    } finally {

      localStorage.removeItem("eq_access_token");

      setUser(null);

      setData(emptyData);

      setPermissions({ overview: true, profile: true });

      setActiveTab("overview");

    }

  }


  async function load(role = user?.role) {

    if (role === "applicant") {
      setData(emptyData);
      return;
    }

    if (!role) return;

    setLoading(true);

    setError(null);

    try {

      const [health, summary, owners, types, locations, assets, blueprints, activities] = await Promise.all([

        api<Health>("/health"),

        api<Summary>("/quartermaster/summary"),

        api<Owner[]>("/quartermaster/owners"),

        api<EveType[]>("/quartermaster/types"),

        api<Location[]>("/quartermaster/locations"),

        api<Asset[]>("/quartermaster/assets?limit=250"),

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

    function syncLocationHash() {

      setLocationHash(window.location.hash);

    }

    window.addEventListener("hashchange", syncLocationHash);

    return () => window.removeEventListener("hashchange", syncLocationHash);

  }, []);

  useEffect(() => {

    const params = new URLSearchParams(window.location.search);

    const esiMode = params.get("esi_mode");
    const esiDestination = esiMode === "recruitment" || window.location.hash === "#recruiting"
      ? "recruiting"
      : ["planet", "planets", "planetary", "planetary_industry", "pi"].includes(esiMode ?? "") || window.location.hash === "#planetary_industry"
        ? "planetary_industry"
        : "esi";

    const esiError = params.get("esi_error");

    if (window.location.hash.startsWith("#events")) setActiveTab("calendar_events");
    else if (window.location.hash.startsWith("#hypernet")) setActiveTab("hypernet");
    else if (window.location.hash === "#esi" || window.location.hash === "#recruiting" || window.location.hash === "#planetary_industry" || params.get("esi_status") || esiError) setActiveTab(esiDestination);

    if (esiError) {
      if (esiDestination === "recruiting" && window.opener) {
        window.opener.postMessage({ type: "eqm:recruitment-sso-complete", error: esiError }, window.location.origin);
        window.close();
      } else {
        setError(esiError);
      }
      window.history.replaceState({}, "", "/#" + esiDestination);
    }

    if (params.get("esi_status")) {

      const characterName = params.get("character_name") ?? "Character";

      const status = params.get("esi_status") === "updated" ? "updated" : "linked";

      const addedScopes = (params.get("added_scopes") ?? "").split(",").filter(Boolean);

      const removedScopes = (params.get("removed_scopes") ?? "").split(",").filter(Boolean);

      const scopeNote = addedScopes.length > 0 ? ` Added ${addedScopes.length} scope${addedScopes.length === 1 ? "" : "s"}.` : removedScopes.length > 0 ? ` Removed ${removedScopes.length} scope${removedScopes.length === 1 ? "" : "s"}.` : "";

      if (esiDestination === "recruiting" && window.opener) {
        window.opener.postMessage({ type: "eqm:recruitment-sso-complete", characterName, status }, window.location.origin);
        window.close();
      } else {
        setNotice(`${characterName} ${status} through EVE SSO.${scopeNote}`);
      }

      window.history.replaceState({}, "", "/#" + esiDestination);

    }

    void refreshAuth().then((currentUser) => {

      if (currentUser && currentUser.role !== "applicant") void load(currentUser.role);

    });

  }, []);

  useEffect(() => {
    if (locationHash.startsWith("#events")) setActiveTab("calendar_events");
    else if (locationHash.startsWith("#exchange")) setActiveTab("exchange");
    else if (locationHash.startsWith("#hypernet")) setActiveTab("hypernet");
  }, [locationHash]);

  useEffect(() => {

    if (!notice) return;

    const timer = window.setTimeout(() => setNotice(null), 3000);

    return () => window.clearTimeout(timer);

  }, [notice]);



  useEffect(() => {

    function openCharacter(event: Event) {

      const detail = (event as CustomEvent<CharacterFocus>).detail;

      if (!detail?.characterId) return;

      setCharacterFocus({ characterId: detail.characterId, name: detail.name, nonce: Date.now() });

      setActiveTab("characters");

    }

    window.addEventListener("eqm:open-character", openCharacter as EventListener);

    return () => window.removeEventListener("eqm:open-character", openCharacter as EventListener);

  }, []);

  const typeOptions = useMemo(() => data.types.map((type) => <option key={type.type_id} value={type.type_id}>{type.name}</option>), [data.types]);

  const ownerOptions = useMemo(() => data.owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.display_name}</option>), [data.owners]);

  const locationOptions = useMemo(() => data.locations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>), [data.locations]);

  const activityOptions = useMemo(() => data.activities.map((activity) => <option key={activity.id} value={activity.id}>{activity.blueprint_type_name} - {activity.activity_kind}</option>), [data.activities]);



  function canView(section: string) { return permissions[section] !== false || ["overview", "settings", "profile"].includes(section); }

  function openThreatAnalyzer() {
    setActiveTab("navigation");
    window.setTimeout(() => {
      document.getElementById("local-threat-analyzer")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  }



  const inviteToken = new URLSearchParams(window.location.search).get("invite");

  const publicRecruiting = locationHash === "#recruiting" || locationHash === "#apply";
  const publicExchangeId = locationHash.startsWith("#exchange/") ? locationHash.slice("#exchange/".length) : null;

  if (!authReady) return <main className="auth-shell"><section className="panel"><img className="auth-logo" src="/eqm-logo.png" alt="EVE Quartermaster" /><p className="muted">Checking account session...</p></section></main>;

  if (!user && inviteToken) return <InviteScreen token={inviteToken} onAuth={completeAuth} />;

  if (!user && publicRecruiting) return <RecruitingPublicPage api={api} onRegister={completeAuth} onBack={() => { window.location.hash = ""; window.location.reload(); }} />;

  if (!user && publicExchangeId) return <PublicExchangeListingPage api={api} publicId={publicExchangeId} onBack={() => { window.location.hash = ""; window.location.reload(); }} />;

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

          {canView("navigation") && <button className={activeTab === "navigation" ? "active" : ""} onClick={() => setActiveTab("navigation")}><MapIcon size={18} /> Navigation</button>}

          {["characters", "skills", "fittings", "jump_clones", "roster", "esi"].some(canView) && <span className="nav-section-label">Character Functions</span>}

          {canView("characters") && <button className={activeTab === "characters" ? "active" : ""} onClick={() => setActiveTab("characters")}><UserRoundCheck size={18} /> Characters</button>}

          {canView("skills") && <button className={activeTab === "skills" ? "active" : ""} onClick={() => setActiveTab("skills")}><GraduationCap size={18} /> Skills</button>}

          {canView("fittings") && <button className={`fittings-wip${activeTab === "fittings" ? " active" : ""}`} onClick={() => setActiveTab("fittings")}><ClipboardList size={18} /> Fittings - WIP</button>}

          {canView("jump_clones") && <button className={activeTab === "jump_clones" ? "active" : ""} onClick={() => setActiveTab("jump_clones")}><UserRoundCheck size={18} /> Jump Clones</button>}

          {canView("roster") && <button className={activeTab === "roster" ? "active" : ""} onClick={() => setActiveTab("roster")}><Building2 size={18} /> Roster</button>}

          {canView("esi") && <button className={activeTab === "esi" ? "active" : ""} onClick={() => setActiveTab("esi")}><KeyRound size={18} /> ESI Sync</button>}

          {["market", "exchange", "hypernet"].some(canView) && <span className="nav-section-label">Finance & Trade</span>}

          {canView("market") && <button className={activeTab === "market" ? "active" : ""} onClick={() => setActiveTab("market")}><ShoppingCart size={18} /> Market</button>}

          {canView("exchange") && <button className={activeTab === "exchange" ? "active" : ""} onClick={() => { window.location.hash = "exchange"; setActiveTab("exchange"); }}><Store size={18} /> Corporate Exchange</button>}

          {canView("hypernet") && <button className={activeTab === "hypernet" ? "active" : ""} onClick={() => { window.location.hash = "hypernet"; setActiveTab("hypernet"); }}><Coins size={18} /> HyperNet Tracker</button>}

          {["notes", "manufacturing", "mining", "planetary_industry", "corporations", "ownership", "assets", "industry", "contracts", "analytics"].some(canView) && <span className="nav-section-label">Inventory & Industry</span>}

          {canView("notes") && <button className={activeTab === "notes" ? "active" : ""} onClick={() => setActiveTab("notes")}><NotebookTabs size={18} /> Notes & Lists</button>}

          {canView("manufacturing") && <button className={activeTab === "manufacturing" ? "active" : ""} onClick={() => setActiveTab("manufacturing")}><Factory size={18} /> Manufacturing</button>}

          {canView("industry") && <button className={activeTab === "research_projects" ? "active" : ""} onClick={() => setActiveTab("research_projects")}><FlaskConical size={18} /> Research Projects</button>}

          {canView("mining") && <button className={activeTab === "mining" ? "active" : ""} onClick={() => setActiveTab("mining" )}><Pickaxe size={18} /> Mining Ledger</button>}

          {canView("planetary_industry") && <button className={activeTab === "planetary_industry" ? "active" : ""} onClick={() => setActiveTab("planetary_industry")}><Globe2 size={18} /> Planetary Industry</button>}

          {canView("corporations") && <button className={activeTab === "corporations" ? "active" : ""} onClick={() => setActiveTab("corporations")}><Building2 size={18} /> Corporations</button>}

          {canView("ownership") && <button className={activeTab === "ownership" ? "active" : ""} onClick={() => setActiveTab("ownership")}><Boxes size={18} /> Ownership</button>}

          {canView("assets") && <button className={activeTab === "assets" ? "active" : ""} onClick={() => setActiveTab("assets")}><PackagePlus size={18} /> Assets</button>}

          {canView("industry") && <button className={activeTab === "industry" ? "active" : ""} onClick={() => setActiveTab("industry")}><Factory size={18} /> Industry</button>}

          {canView("contracts") && <button className={activeTab === "contracts" ? "active" : ""} onClick={() => setActiveTab("contracts")}><ScrollText size={18} /> Contracts</button>}

          {canView("analytics") && <button className={activeTab === "analytics" ? "active" : ""} onClick={() => setActiveTab("analytics")}><Activity size={18} /> Analytics</button>}

          {["calendar_events", "recruiting"].some(canView) && <span className="nav-section-label">Community</span>}

          {canView("calendar_events") && <button className={activeTab === "calendar_events" ? "active" : ""} onClick={() => { window.location.hash = "events"; setActiveTab("calendar_events"); }}><CalendarDays size={18} /> Calendar & Events</button>}

          {canView("recruiting") && <button className={activeTab === "recruiting" ? "active" : ""} onClick={() => setActiveTab("recruiting")}><UserRoundCheck size={18} /> Recruiting</button>}

          {["profile", "settings", "audit"].some(canView) && <span className="nav-section-label">Account & Admin</span>}

          {canView("profile") && <button className={activeTab === "profile" ? "active" : ""} onClick={() => setActiveTab("profile")}><UserRoundCheck size={18} /> Profile</button>}

          {canView("settings") && <button className={activeTab === "settings" ? "active" : ""} onClick={() => setActiveTab("settings")}><Settings size={18} /> Settings</button>}

          {canView("audit") && <button className={activeTab === "audit" ? "active" : ""} onClick={() => setActiveTab("audit")}><ScrollText size={18} /> Audit</button>}

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

            {canView("calendar_events") && <NextEventBadge api={api} onOpen={(eventId) => { window.location.hash = `events/${eventId}`; setActiveTab("calendar_events"); }} />}

            {canView("navigation") && <button type="button" className="threat-analyzer-button" onClick={openThreatAnalyzer}><Siren size={18} /> Threat Analyzer</button>}

            <span className="status-badge">{user.display_name}</span>

            <NotificationBubble currentUser={user} onOpenMessages={(message) => { setProfileFocus({ section: "messages", replyTo: message, nonce: Date.now() }); setActiveTab("profile"); }} />

            <span className="status-badge rank-badge">{user.role}</span>

            {["host", "admin"].includes(user.role) && <button onClick={() => void seed()}><Sparkles size={18} /> Seed</button>}

            <button onClick={() => void load()}><RefreshCw size={18} /> {loading ? "Refreshing" : "Refresh"}</button>

            <button onClick={signOut}>Sign out</button>

          </div>

        </header>



        {error && <div className="alert">{error}</div>}

        {notice && <div className="notice">{notice}</div>}



        {!canView(activeTab) && <section className="panel"><h3>Permission required</h3><p className="muted">This section is not enabled for your account.</p></section>}

        {activeTab === "overview" && canView("overview") && <Overview data={data} api={api} timeZone={preferredTimeZone(user)} onOpenIndustry={canView("industry") ? () => setActiveTab("industry") : undefined} onOpenEvents={(eventId) => { window.location.hash = eventId ? `events/${eventId}` : "events"; setActiveTab("calendar_events"); }} />}

        {activeTab === "ownership" && canView("ownership") && <Ownership data={data} submit={submit} />}

        {activeTab === "characters" && canView("characters") && <CharactersPage currentUser={user} focus={characterFocus} api={api} Metric={Metric} EveEntityIcon={EveEntityIcon} CharacterHoverName={CharacterHoverName} AssetTable={AssetTable} BlueprintList={BlueprintList} formatDateTime={formatDateTime} numberFormatter={numberFormatter} accountLabel={accountLabel} />}

        {activeTab === "roster" && canView("roster") && <Roster api={api} EveEntityIcon={EveEntityIcon} CharacterHoverName={CharacterHoverName} />}

        {activeTab === "navigation" && canView("navigation") && <NavigationPlanner currentUser={user} />}

        {activeTab === "market" && canView("market") && <MarketAppraisalPage currentUser={user} seed={marketSeed} assets={data.assets} onOpenAssets={(itemName) => { setAssetSeed({ key: "item", value: itemName, mode: "exact", nonce: Date.now() }); setActiveTab("assets"); }} onOpenFittings={(itemName) => { setFittingSeed({ text: itemName, nonce: Date.now() }); setActiveTab("fittings"); }} api={api} sendDestinationToEve={sendDestinationToEve} ItemContextPanel={ItemContextPanel} numberFormatter={numberFormatter} />}

        {activeTab === "exchange" && canView("exchange") && <CorporateExchangePage api={api} currentUserId={user.id} />}

        {activeTab === "hypernet" && canView("hypernet") && <HyperNetTrackerPage api={api} />}

        {activeTab === "calendar_events" && canView("calendar_events") && <EventsPage api={api} currentUser={user} />}

        {activeTab === "notes" && canView("notes") && <NotesListsPage api={api} />}

        {activeTab === "manufacturing" && canView("manufacturing") && <ManufacturingPage api={api} formatDateTime={(value) => formatDateTime(value, preferredTimeZone(user))} />}

        {activeTab === "research_projects" && canView("industry") && <ResearchProjectsPage api={api} formatDateTime={(value) => formatDateTime(value, preferredTimeZone(user))} />}

        {activeTab === "mining" && canView("mining") && <MiningLedgerPage api={api} />}

        {activeTab === "planetary_industry" && canView("planetary_industry") && <PlanetaryIndustryPage api={api} formatDateTime={(value) => formatDateTime(value, preferredTimeZone(user))} />}

        {activeTab === "contracts" && canView("contracts") && <ContractsPage currentUser={user} api={api} CharacterHoverName={CharacterHoverName} />}

        {activeTab === "analytics" && canView("analytics") && <AnalyticsPlatform currentUser={user} api={api} Metric={Metric} />}

        {activeTab === "recruiting" && canView("recruiting") && <RecruitingPage api={api} />}

        {activeTab === "skills" && canView("skills") && <CharacterSkills currentUser={user} api={api} Metric={Metric} CharacterHoverName={CharacterHoverName} />}

        {activeTab === "fittings" && canView("fittings") && <FittingsPage currentUser={user} assets={data.assets} seed={fittingSeed} api={api} onOpenAssets={(itemName) => { setAssetSeed(itemName ? { key: "item", value: itemName, mode: "exact", nonce: Date.now() } : { key: "item", value: "", mode: "contains", nonce: Date.now() }); setActiveTab("assets"); }} onOpenMarket={(text) => { setMarketSeed({ text, nonce: Date.now() }); setActiveTab("market"); }} />}

        {activeTab === "jump_clones" && canView("jump_clones") && <JumpClonesPage api={api} EveEntityIcon={EveEntityIcon} formatDateTime={(value) => formatDateTime(value, preferredTimeZone(user))} />}

        {activeTab === "settings" && canView("settings") && <SettingsPage currentUser={user} api={api} Metric={Metric} ManagedForm={ManagedForm} accountLabel={accountLabel} />}

        {activeTab === "corporations" && canView("corporations") && <CorporationsPage api={api} loadAssets={load} EveEntityIcon={EveEntityIcon} />}

        {activeTab === "assets" && canView("assets") && <Assets data={data} seed={assetSeed} submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} api={api} onOpenFittings={(itemName) => { setFittingSeed({ text: itemName, nonce: Date.now() }); setActiveTab("fittings"); }} onOpenMarket={(text) => { setMarketSeed({ text, nonce: Date.now() }); setActiveTab("market"); }} />}

        {activeTab === "industry" && canView("industry") && <Industry data={data} submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} activityOptions={activityOptions} onOpenMarket={(text) => { setMarketSeed({ text, nonce: Date.now() }); setActiveTab("market"); }} onOpenAssets={(itemName) => { setAssetSeed({ key: "item", value: itemName, mode: "exact", nonce: Date.now() }); setActiveTab("assets"); }} />}

        {activeTab === "esi" && canView("esi") && <EsiSyncPage load={load} currentUser={user} api={api} ManagedForm={ManagedForm} Metric={Metric} CharacterHoverName={CharacterHoverName} />}

        {activeTab === "profile" && canView("profile") && <ProfilePage currentUser={user} onUserUpdated={setUser} focus={profileFocus} api={api} ManagedForm={ManagedForm} accountLabel={accountLabel} />}

        {activeTab === "audit" && canView("audit") && <AuditLog currentUser={user} />}

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

  const timeZone = preferredTimeZone(currentUser);






  return <div className="bubble-wrap"><button type="button" className="bubble-button" aria-label="Messages and notifications" onClick={() => { setOpen((value) => !value); if (!open) void loadInbox().catch((err) => setError(err instanceof Error ? err.message : "Unable to load inbox")); }}><MessageCircle size={18} />{unread > 0 && <span>{unread > 99 ? "99+" : unread}</span>}</button>{open && <div className="bubble-panel"><div className="section-heading compact"><h3>Inbox</h3><button type="button" onClick={() => void markAllRead()}>Mark read</button></div>{error && <div className="mini-alert">{error}</div>}{sent && <div className="notice inline">{sent}</div>}<h4>System notices</h4><div className="mini-list inbox-list">{inbox?.events.map((event) => <div key={event.id} className={event.is_read ? "" : "unread"}><strong>{event.title}</strong><span>{event.body ?? "Audit event"}</span><span>{event.created_at ? formatDateTime(event.created_at, timeZone) : "recently"}</span></div>)}{inbox && inbox.events.length === 0 && <p className="empty">No system notices.</p>}</div><h4>Private messages</h4><div className="mini-list inbox-list">{inbox?.messages.map((message) => <button type="button" key={message.id} className={message.is_read ? "message-link" : "message-link unread"} onClick={() => { setOpen(false); onOpenMessages(message); }}><strong>{message.subject}</strong><span>From {message.sender_display_name ?? "Unknown"}</span><span>{message.body}</span><span>{message.created_at ? formatDateTime(message.created_at, timeZone) : "recently"}</span></button>)}{inbox && inbox.messages.length === 0 && <p className="empty">No private messages.</p>}</div><div className="section-heading compact"><h4>Send message</h4><button type="button" onClick={() => { setOpen(false); onOpenMessages(); }}>Open mailbox</button></div><ManagedForm submitLabel="Send" onSubmit={sendMessage}><label>To<select name="recipient_user_id" required>{recipients.map((user) => <option key={user.id} value={user.id}>{accountLabel(user)} ({user.role})</option>)}</select></label><label>Subject<input name="subject" required /></label><label>Message<textarea name="body" required /></label></ManagedForm></div>}</div>;

}



function NavigationPlanner({ currentUser }: { currentUser: UserAccount }) {
  return <>
    <RouteChecker
      currentUser={currentUser}
      api={api}
      numberFormatter={numberFormatter}
      Metric={Metric}
      EveEntityIcon={EveEntityIcon}
      CharacterHoverName={CharacterHoverName}
      UedamaScoutLiveLink={UedamaScoutLiveLink}
    />
    <JumpFreighterPlanner currentUser={currentUser} api={api} numberFormatter={numberFormatter} Metric={Metric} EveEntityIcon={EveEntityIcon} CharacterHoverName={CharacterHoverName} UedamaScoutLiveLink={UedamaScoutLiveLink} />
    <IndustrialSystemThreatWidget currentUser={currentUser} api={api} Metric={Metric} />
    <PvpIntelWidget currentUser={currentUser} api={api} Metric={Metric} />
    <div id="local-threat-analyzer" className="threat-analyzer-anchor">
      <LocalThreatWidget currentUser={currentUser} api={api} Metric={Metric} EveEntityIcon={EveEntityIcon} CharacterHoverName={CharacterHoverName} />
    </div>
  </>;
}
function AuditLog({ currentUser }: { currentUser: UserAccount }) {

  const [events, setEvents] = useState<AuditEvent[]>([]);

  const [auditError, setAuditError] = useState<string | null>(null);

  const timeZone = preferredTimeZone(currentUser);






  async function loadAudit() {

    setEvents(await api<AuditEvent[]>("/notifications/audit"));

  }



  useEffect(() => { void loadAudit().catch((err) => setAuditError(err instanceof Error ? err.message : "Unable to load audit log")); }, []);



  return <section className="panel stacked"><div className="section-heading"><h3>Audit Log</h3><button type="button" onClick={() => void loadAudit()}>Refresh</button></div>{auditError && <div className="mini-alert">{auditError}</div>}<div className="card-list audit-list">{events.map((event) => <article key={event.id}><strong>{event.title}</strong><span>{event.event_kind} · {event.created_at ? formatDateTime(event.created_at, timeZone) : "recently"}</span><span>Actor {event.actor_display_name ?? "system"}{event.recipient_display_name ? ` · Recipient ${event.recipient_display_name}` : ""}{event.character_name ? ` · Character ${event.character_name}` : ""}</span>{event.body && <span>{event.body}</span>}</article>)}{events.length === 0 && <p className="empty">No audit events yet.</p>}</div></section>;

}

function AuthScreen({ bootstrap, onAuth }: { bootstrap: BootstrapStatus | null; onAuth: (path: string, body: Record<string, unknown>) => Promise<void> }) {

  const needsAdmin = bootstrap?.needs_admin ?? false;

  return (

    <main className="auth-shell">

      <section className="panel auth-panel">

        <img className="auth-logo" src="/eqm-logo.png" alt="EVE Quartermaster" />

        <span className="status-badge version-badge auth-version">v{APP_VERSION}</span>

        <h2>{needsAdmin ? "Create Admin Account" : "Sign In"}</h2>

        <p className="muted">{needsAdmin ? "Set up the first Quartermaster host account." : "Use your Quartermaster account before linking EVE characters."}</p><p className="auth-tagline">EVE is Excel in a flight suit.</p>

        <ManagedForm submitLabel={needsAdmin ? "Create host" : "Sign in"} onSubmit={(form) => onAuth(needsAdmin ? "/auth/bootstrap" : "/auth/login", { email: form.get("email"), password: form.get("password"), display_name: form.get("display_name"), remember_me: !needsAdmin && form.get("remember_me") === "on" })}>

          {needsAdmin && <label>Display name<input name="display_name" required placeholder="Quartermaster" /></label>}

          <label>Email<input name="email" type="email" required placeholder="you@example.com" /></label>

          <label>Password<input name="password" type="password" minLength={8} required /></label>

          {!needsAdmin && <label className="check auth-remember"><input name="remember_me" type="checkbox" /><span><strong>Remember me</strong><small>Stay signed in on this device for 30 days.</small></span></label>}

        </ManagedForm>

        {!needsAdmin && <a className="auth-link auth-recruiting-link" href="/#recruiting"><UserRoundCheck size={18} /> Apply / Recruiting</a>}

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

function Overview({ data, api, timeZone, onOpenIndustry, onOpenEvents }: { data: AppData; api: ApiClient; timeZone: string; onOpenIndustry?: () => void; onOpenEvents: (eventId?: number) => void }) {

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

        <section className="panel"><h3>Recent Assets</h3><AssetTable assets={data.assets.slice(0, 6)} blueprints={data.blueprints} /></section>

        <section className="panel"><h3>Blueprint Library</h3><BlueprintPreview blueprints={data.blueprints} onOpenIndustry={onOpenIndustry} /></section>

      </div>

      <UpcomingEventsWidget api={api} timeZone={timeZone} onOpen={onOpenEvents} />

    </>

  );

}



function Ownership({ data, submit }: { data: AppData; submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void> }) {

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



function Assets({ data, seed, submit, ownerOptions, typeOptions, locationOptions, api, onOpenFittings, onOpenMarket }: { data: AppData; seed?: AssetTableSeed | null; submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void>; ownerOptions: React.ReactNode; typeOptions: React.ReactNode; locationOptions: React.ReactNode; api: ApiClient; onOpenFittings: (itemName: string) => void; onOpenMarket: (text: string) => void }) {

  return <div className="two-column main-heavy"><section className="panel"><h3>Tracked Assets</h3><AssetTable assets={data.assets} seed={seed} api={api} serverMode onOpenFittings={onOpenFittings} onOpenMarket={onOpenMarket} /></section><section className="panel"><h3>Add Asset</h3><AssetForm submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} /></section></div>;

}



function Industry({ data, submit, ownerOptions, typeOptions, locationOptions, activityOptions, onOpenMarket, onOpenAssets }: { data: AppData; submit: (path: string, body: Record<string, unknown>, success: string) => Promise<void>; ownerOptions: React.ReactNode; typeOptions: React.ReactNode; locationOptions: React.ReactNode; activityOptions: React.ReactNode; onOpenMarket: (text: string) => void; onOpenAssets: (itemName: string) => void }) {

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

      <section className="panel"><h3>Blueprints</h3><BlueprintList blueprints={data.blueprints} assets={data.assets} onOpenMarket={onOpenMarket} onOpenAssets={onOpenAssets} /></section>

      <section className="panel"><h3>Add Blueprint</h3><BlueprintForm submit={submit} ownerOptions={ownerOptions} typeOptions={typeOptions} locationOptions={locationOptions} /></section>

      <section className="panel"><h3>Recipes</h3><p className="muted">Showing {recipes.length.toLocaleString()} loaded recipes. Scroll the list to load more.</p>{recipeError && <div className="mini-alert">{recipeError}</div>}<RecipeList activities={recipes} blueprints={data.blueprints} onSelect={setSelectedRecipe} onLoadMore={() => void loadMoreRecipes()} loadingMore={recipeBusy} hasMore={hasMoreRecipes} /></section>

      <section className="panel stacked"><h3>Add Recipe</h3><RecipeForm submit={submit} typeOptions={typeOptions} /><h3>Add Recipe Input</h3><RecipeInputForm submit={submit} typeOptions={typeOptions} activityOptions={activityOptions} /></section>

      {selectedRecipe && <RecipeDetailModal activity={selectedRecipe} blueprints={data.blueprints} assets={data.assets} onOpenMarket={onOpenMarket} onOpenAssets={onOpenAssets} onClose={() => setSelectedRecipe(null)} />}

    </div>

  );

}

function Metric({ icon, label, value, delta }: { icon: React.ReactNode; label: string; value: string | number; delta?: string }) {

  const isEmptyDelta = delta?.startsWith("No ");

  return <article>{icon}<span>{label}</span><strong>{typeof value === "number" ? numberFormatter.format(value) : value}</strong>{delta && <small className={isEmptyDelta ? "metric-delta empty" : "metric-delta"}>{delta}</small>}</article>;

}



function AssetTable({ assets, blueprints = [], seed, api, serverMode = false, onOpenFittings, onOpenMarket }: { assets: Asset[]; blueprints?: Blueprint[]; seed?: AssetTableSeed | null; api?: ApiClient; serverMode?: boolean; onOpenFittings?: (itemName: string) => void; onOpenMarket?: (text: string) => void }) {

  const [sortKey, setSortKey] = useState<AssetSortKey>("item");

  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const [filter, setFilter] = useState<AssetFilter | null>(null);

  const [searchTerms, setSearchTerms] = useState<Record<AssetFilterKey, string>>({ item: "", owner: "", location: "", flag: "" });

  const [copyNotice, setCopyNotice] = useState<string | null>(null);

  const [ownerKindFilter, setOwnerKindFilter] = useState<OwnerKindFilter | "">("");

  const [categoryFilter, setCategoryFilter] = useState<InventoryFamilyFilter>("all");

  const [subtypeFilter, setSubtypeFilter] = useState<string>("");

  const [contextTypeId, setContextTypeId] = useState<number | null>(null);

  const [assetPage, setAssetPage] = useState(1);

  const [assetPageSize, setAssetPageSize] = useState(100);

  const [serverAssets, setServerAssets] = useState<Asset[]>([]);

  const [serverTotal, setServerTotal] = useState(0);

  const [serverBusy, setServerBusy] = useState(false);

  const [serverError, setServerError] = useState<string | null>(null);

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

      case "flag": return asset.location_flag_name ?? asset.location_flag ?? "";

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



  useEffect(() => {

    if (!seed) return;

    if (!seed.value) {

      setFilter(null);

      setSearchTerms({ item: "", owner: "", location: "", flag: "" });

      setCopyNotice(null);

      return;

    }

    setFilter({ key: seed.key, value: seed.value, label: filterLabels[seed.key], mode: seed.mode });

    setSearchTerms({ item: "", owner: "", location: "", flag: "", [seed.key]: seed.mode === "contains" ? seed.value : "" });

    setCopyNotice(null);

  }, [seed?.nonce]);
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

    const capitalRelated = looksCapitalRelated(asset.type_group_name, asset.type_category_name, asset.type_name);

    if (!matchesInventoryFamily(categoryFilter, assetFamily(asset), capitalRelated)) return false;

    if (subtypeFilter && assetSubtype(asset) !== subtypeFilter) return false;

    if (!filter) return true;

    const value = filterValue(asset, filter.key);

    if (filter.mode === "contains") return value.toLowerCase().includes(filter.value.toLowerCase());

    return value === filter.value;

  }



  const tableAssets = serverMode ? serverAssets : assets;

  const visibleAssets = useMemo(() => {

    if (serverMode) return tableAssets;

    const filtered = tableAssets.filter(matchesFilter);

    return [...filtered].sort((left, right) => {

      const leftValue = sortValue(left, sortKey);

      const rightValue = sortValue(right, sortKey);

      const result = typeof leftValue === "number" && typeof rightValue === "number"

        ? leftValue - rightValue

        : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: "base" });

      return sortDirection === "asc" ? result : -result;

    });

  }, [tableAssets, serverMode, filter, ownerKindFilter, categoryFilter, subtypeFilter, sortKey, sortDirection]);



  useEffect(() => {

    setAssetPage(1);

    setContextTypeId(null);

  }, [filter, ownerKindFilter, categoryFilter, subtypeFilter, sortKey, sortDirection, assetPageSize, assets.length]);



  const visibleAssetCount = serverMode ? serverTotal : visibleAssets.length;

  const assetPageCount = Math.max(1, Math.ceil(visibleAssetCount / assetPageSize));

  const safeAssetPage = Math.min(assetPage, assetPageCount);

  const assetPageStart = visibleAssetCount === 0 ? 0 : (safeAssetPage - 1) * assetPageSize + 1;

  const assetPageEnd = Math.min(visibleAssetCount, safeAssetPage * assetPageSize);

  const pagedAssets = serverMode ? visibleAssets : visibleAssets.slice((safeAssetPage - 1) * assetPageSize, safeAssetPage * assetPageSize);



  useEffect(() => {

    if (!serverMode || !api) return;

    const params = new URLSearchParams({ page: String(assetPage), page_size: String(assetPageSize), sort_key: sortKey, sort_direction: sortDirection, category: categoryFilter });

    if (ownerKindFilter) params.set("owner_kind", ownerKindFilter);

    if (subtypeFilter) params.set("subtype", subtypeFilter);

    if (filter) {

      params.set("filter_key", filter.key);

      params.set("filter_value", filter.value);

      params.set("filter_mode", filter.mode);

    }

    let cancelled = false;

    setServerBusy(true);

    setServerError(null);

    void api<AssetPagePayload>(`/quartermaster/assets-page?${params.toString()}`)

      .then((payload) => {

        if (cancelled) return;

        setServerAssets(payload.items);

        setServerTotal(payload.total);

      })

      .catch((err) => {

        if (!cancelled) setServerError(err instanceof Error ? err.message : "Unable to load assets");

      })

      .finally(() => {

        if (!cancelled) setServerBusy(false);

      });

    return () => { cancelled = true; };

  }, [api, serverMode, assetPage, assetPageSize, sortKey, sortDirection, ownerKindFilter, categoryFilter, subtypeFilter, filter]);



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

      asset.location_flag_name ?? asset.location_flag ?? "",

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



  const assetCategoryOptions: InventoryFamilyFilter[] = ["all", "ships", "ammunition", "drones", "rigs", "reactions", "ram", "blueprints", "capital-construction"];

  const assetSubtypeOptions = useMemo(() => sortedUnique(assets.filter((asset) => matchesInventoryFamily(categoryFilter, assetFamily(asset), looksCapitalRelated(asset.type_group_name, asset.type_category_name, asset.type_name))).map(assetSubtype)), [assets, categoryFilter]);

  const sortMark = (key: AssetSortKey) => sortKey === key ? (sortDirection === "asc" ? "^" : "v") : "";

  function overviewBlueprintDetails(asset: Asset) {
    const looksLikeBlueprint = asset.inventory_family === "blueprints" || asset.type_category_name?.toLowerCase() === "blueprint" || asset.is_blueprint_copy != null;
    if (!looksLikeBlueprint) return null;
    const exact = blueprints.find((blueprint) => blueprint.asset_id === asset.id);
    const fallback = exact ?? blueprints.find((blueprint) => blueprint.blueprint_type_id === asset.type_id && blueprint.owner_name === asset.owner_name && (!asset.location_name || blueprint.location_name === asset.location_name));
    return fallback ? blueprintHoverDetails(fallback) : { name: asset.type_name, owner: asset.owner_name, kind: asset.is_blueprint_copy == null ? null : asset.is_blueprint_copy ? "BPC" as const : "BPO" as const, location: asset.location_name, definitionOnly: true, note: "Blueprint instance details are awaiting a matching blueprint sync." };
  }

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

      <div className="blueprint-filter asset-category-filter">{assetCategoryOptions.map((family) => <button type="button" key={family} className={categoryFilter === family ? "active" : ""} onClick={() => { setCategoryFilter(family); setSubtypeFilter(""); }}>{inventoryFamilyLabels[family]}</button>)}</div>

      <label className="inventory-subtype-filter">Subtype<select value={subtypeFilter} onChange={(event) => setSubtypeFilter(event.target.value)}><option value="">All subtypes</option>{assetSubtypeOptions.map((subtype) => <option key={subtype} value={subtype}>{subtype}</option>)}</select></label>

      <div className="ledger-filter-grid">{filterSelect("item")}{filterSelect("owner")}{filterSelect("location")}{filterSelect("flag")}</div>

      <div className="ledger-filter-grid search-grid">{searchInput("item")}{searchInput("owner")}{searchInput("location")}{searchInput("flag")}</div>

      <div className="ledger-actions">

        {filter ? <div className="active-filter"><span>{filter.label} {filter.mode === "contains" ? "contains" : "is"}: {filter.value}</span><button type="button" onClick={clearFilter}>Clear filter</button></div> : <span className="muted">{serverMode ? "Showing paged assets" : "Showing all assets"}</span>}

        <div className="button-row compact"><button type="button" disabled={visibleAssets.length === 0} onClick={exportCsv}>{serverMode ? "Export page CSV" : "Export CSV"}</button><button type="button" disabled={visibleAssets.length === 0} onClick={() => void copyJaniceList()}>{serverMode ? "Copy page for Janice" : "Copy for Janice"}</button></div>

      </div>

      {serverBusy && <div className="notice inline">Loading asset page...</div>}

      {serverError && <div className="mini-alert">{serverError}</div>}

      {visibleAssetCount > assetPageSize && <div className="ledger-pagination"><span>Showing {assetPageStart.toLocaleString()}-{assetPageEnd.toLocaleString()} of {visibleAssetCount.toLocaleString()} rows</span><div className="button-row compact"><button type="button" disabled={safeAssetPage <= 1} onClick={() => setAssetPage(1)}>First</button><button type="button" disabled={safeAssetPage <= 1} onClick={() => setAssetPage((page) => Math.max(1, page - 1))}>Prev</button><label>Rows<select value={assetPageSize} onChange={(event) => setAssetPageSize(Number(event.target.value))}><option value={50}>50</option><option value={100}>100</option><option value={250}>250</option><option value={500}>500</option></select></label><button type="button" disabled={safeAssetPage >= assetPageCount} onClick={() => setAssetPage((page) => Math.min(assetPageCount, page + 1))}>Next</button><button type="button" disabled={safeAssetPage >= assetPageCount} onClick={() => setAssetPage(assetPageCount)}>Last</button></div></div>}

      {copyNotice && <div className="notice inline">{copyNotice}</div>}

      <div className="table-wrap"><table><thead><tr>

        <th><button className="sort-header" type="button" onClick={() => toggleSort("item")}>Item <span>{sortMark("item")}</span></button></th>

        <th><button className="sort-header" type="button" onClick={() => toggleSort("owner")}>Owner <span>{sortMark("owner")}</span></button></th>

        <th><button className="sort-header" type="button" onClick={() => toggleSort("quantity")}>Qty <span>{sortMark("quantity")}</span></button></th>

        <th><button className="sort-header" type="button" onClick={() => toggleSort("location")}>Location <span>{sortMark("location")}</span></button></th>

        <th><button className="sort-header" type="button" onClick={() => toggleSort("flag")}>Flag <span>{sortMark("flag")}</span></button></th>

      </tr></thead><tbody>{pagedAssets.map((asset) => <React.Fragment key={asset.id}>

        <tr>

        <td><div className="asset-item-context">{overviewBlueprintDetails(asset) ? <BlueprintHoverCard details={overviewBlueprintDetails(asset)!}>{filterButton("item", asset.type_name)}</BlueprintHoverCard> : filterButton("item", asset.type_name)}<div className="context-actions">{onOpenMarket && <button type="button" onClick={() => onOpenMarket(`${asset.quantity} ${asset.type_name}`)}>Price</button>}{onOpenFittings && <button type="button" onClick={() => onOpenFittings(asset.type_name)}>Fits</button>}<button type="button" onClick={() => setContextTypeId((current) => current === asset.type_id ? null : asset.type_id)}>{contextTypeId === asset.type_id ? "Hide" : "Context"}</button></div></div></td>

        <td>{filterButton("owner", asset.owner_name)}</td>

        <td>{numberFormatter.format(asset.quantity)}</td>

        <td><div className="cell-action-row">{filterButton("location", asset.location_name ?? "-")}{asset.location_id ? <button type="button" className="destination-link" onClick={() => void sendDestinationToEve(asset.location_id, asset.location_name ?? "asset location")}>Set dest</button> : null}</div></td>

        <td title={asset.location_flag ?? undefined}>{filterButton("flag", asset.location_flag_name ?? asset.location_flag ?? "-")}</td>

        </tr>

        {contextTypeId === asset.type_id && <tr className="asset-context-row"><td colSpan={5}><ItemContextPanel typeId={asset.type_id} itemName={asset.type_name} assets={assets} onOpenMarket={onOpenMarket} onOpenFittings={onOpenFittings} /></td></tr>}

      </React.Fragment>)}</tbody></table>{visibleAssetCount === 0 && !serverBusy && <p className="empty">{assets.length === 0 && !serverMode ? "No assets yet. Use Seed or add one." : "No assets match this filter."}</p>}</div>

    </div>

  );

}


type ItemContextOwner = { owner_name: string; owner_kind?: string | null; quantity: number; stacks: number };
type ItemContextLocation = { owner_name: string; location_name?: string | null; location_flag?: string | null; quantity: number; stacks: number };
type ItemContextFitting = { id: number; name: string; ship_type_name?: string | null; character_name?: string | null; quantity?: number; flags?: string[]; is_shared?: boolean; is_draft?: boolean };
type ItemContextBlueprint = { id: number; owner_name?: string | null; blueprint_type_name: string; product_type_name?: string | null; material_efficiency: number; time_efficiency: number; runs_remaining?: number | null; is_copy: boolean; location_name?: string | null; active_use?: Blueprint["active_use"] };
type ItemContextRecipe = { id: number; activity_kind: string; blueprint_type_id?: number | null; blueprint_type_name?: string | null; product_type_name?: string | null; product_quantity?: number; required_quantity?: number };
type ItemContextSummary = {
  item: { type_id: number; name: string; group_name?: string | null; category_name?: string | null; volume?: number | null; packaged_volume?: number | null; market_group_id?: number | null };
  owned: { quantity: number; stacks: number; owners: ItemContextOwner[]; locations: ItemContextLocation[] };
  fittings: { total_ship_fittings: number; total_used_by: number; ship_fittings: ItemContextFitting[]; used_by: ItemContextFitting[] };
  blueprints: { owned_blueprints: number; bpos: number; bpcs: number; products_owned: number; owned_blueprints_sample: ItemContextBlueprint[]; product_blueprints: ItemContextBlueprint[] };
  industry: { produced_by: ItemContextRecipe[]; used_by: ItemContextRecipe[] };
};

function ItemContextPanel({ typeId, itemName, assets = [], compact = false, onOpenAssets, onOpenMarket, onOpenFittings }: { typeId?: number | null; itemName?: string | null; assets?: Asset[]; compact?: boolean; onOpenAssets?: (itemName: string) => void; onOpenMarket?: (text: string) => void; onOpenFittings?: (itemName: string) => void }) {

  const [context, setContext] = useState<ItemContextSummary | null>(null);

  const [busy, setBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {

    if (!typeId) {

      setContext(null);

      setError(null);

      return;

    }

    let cancelled = false;

    setBusy(true);

    setError(null);

    api<ItemContextSummary>(`/context/item/${typeId}`).then((row) => {

      if (!cancelled) setContext(row);

    }).catch((err) => {

      if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load item context.");

    }).finally(() => {

      if (!cancelled) setBusy(false);

    });

    return () => { cancelled = true; };

  }, [typeId]);

  const displayName = context?.item.name ?? itemName ?? "Item";

  const ownedQuantity = context?.owned.quantity ?? visibleAssetQuantity(assets, itemName);

  const localLocations = visibleAssetLocations(assets, itemName);

  const hasFittingContext = Boolean(context && (context.fittings.total_ship_fittings > 0 || context.fittings.total_used_by > 0));

  const hasIndustryContext = Boolean(context && (context.industry.produced_by.length > 0 || context.industry.used_by.length > 0 || context.blueprints.owned_blueprints > 0 || context.blueprints.product_blueprints.length > 0));

  return <section className={`item-context-panel ${compact ? "compact" : ""}`}>
    <div className="item-context-heading">
      <div>
        <strong>{displayName}</strong>
        {context?.item.group_name && <span>{context.item.category_name ? `${context.item.category_name} / ` : ""}{context.item.group_name}</span>}
        {!typeId && <span>Visible asset context only</span>}
      </div>
      <div className="context-actions">
        {onOpenAssets && <button type="button" onClick={() => onOpenAssets(displayName)}>Assets</button>}
        {onOpenMarket && <button type="button" onClick={() => onOpenMarket(`${Math.max(ownedQuantity || 1, 1)} ${displayName}`)}>Market</button>}
        {onOpenFittings && <button type="button" onClick={() => onOpenFittings(displayName)}>Fittings</button>}
      </div>
    </div>
    {busy && <span className="muted">Loading context...</span>}
    {error && <div className="mini-alert">{error}</div>}
    <div className="item-context-grid">
      <article><span>Owned</span><strong>{numberFormatter.format(ownedQuantity)}</strong><small>{context ? `${numberFormatter.format(context.owned.stacks)} visible stack${context.owned.stacks === 1 ? "" : "s"}` : `${localLocations.length} visible location hint${localLocations.length === 1 ? "" : "s"}`}</small></article>
      <article><span>Fittings</span><strong>{context ? numberFormatter.format(context.fittings.total_ship_fittings + context.fittings.total_used_by) : "-"}</strong><small>ship fits and module usage</small></article>
      <article><span>Industry</span><strong>{context ? numberFormatter.format(context.industry.produced_by.length + context.industry.used_by.length + context.blueprints.product_blueprints.length) : "-"}</strong><small>recipes and blueprints</small></article>
    </div>
    <div className="item-context-columns">
      <div>
        <h4>Where it is</h4>
        <div className="item-context-list">
          {context ? context.owned.locations.map((location) => <div key={`${location.owner_name}-${location.location_name}-${location.location_flag ?? ""}`}><strong>{numberFormatter.format(location.quantity)}x</strong><span>{location.owner_name} @ {location.location_name ?? "Unknown"}{location.location_flag ? ` (${location.location_flag})` : ""}</span></div>) : localLocations.map((location) => <div key={location}><span>{location}</span></div>)}
          {ownedQuantity === 0 && <span className="muted">None visible to you.</span>}
        </div>
      </div>
      {hasFittingContext && context && <div>
        <h4>Fitting context</h4>
        <div className="item-context-list">
          {context.fittings.ship_fittings.map((fitting) => <div key={`ship-${fitting.id}`}><strong>{fitting.name}</strong><span>{fitting.character_name ?? "Unknown character"} flies this hull{fitting.is_draft ? " as a draft" : ""}</span></div>)}
          {context.fittings.used_by.map((fitting) => <div key={`use-${fitting.id}`}><strong>{fitting.name}</strong><span>{numberFormatter.format(fitting.quantity ?? 0)} used on {fitting.ship_type_name ?? "Unknown ship"}{fitting.flags?.length ? ` (${fitting.flags.join(", ")})` : ""}</span></div>)}
        </div>
      </div>}
      {hasIndustryContext && context && <div>
        <h4>Industry context</h4>
        <div className="item-context-list">
          {context.blueprints.product_blueprints.map((blueprint) => <div key={`product-bp-${blueprint.id}`}><BlueprintHoverCard details={blueprintHoverDetails(blueprint)}><strong>{blueprint.blueprint_type_name}</strong></BlueprintHoverCard><span>{blueprint.owner_name ?? "Unknown owner"} · ME {blueprint.material_efficiency} · TE {blueprint.time_efficiency} · {blueprint.is_copy ? "BPC" : "BPO"}</span></div>)}
          {context.industry.produced_by.map((recipe) => <div key={`produced-${recipe.id}`}><BlueprintHoverCard details={{ name: recipe.blueprint_type_name ?? "Blueprint", definitionOnly: true }}><strong>{recipe.blueprint_type_name ?? "Blueprint"}</strong></BlueprintHoverCard><span>Produces {numberFormatter.format(recipe.product_quantity ?? 1)} per run</span></div>)}
          {context.industry.used_by.map((recipe) => <div key={`input-${recipe.id}`}><strong>{recipe.product_type_name ?? recipe.blueprint_type_name ?? "Recipe"}</strong><span>Needs {numberFormatter.format(recipe.required_quantity ?? 0)} per run</span></div>)}
          {context.blueprints.owned_blueprints > 0 && <div><strong>{numberFormatter.format(context.blueprints.owned_blueprints)} owned blueprint{context.blueprints.owned_blueprints === 1 ? "" : "s"}</strong><span>{context.blueprints.bpos} BPO · {context.blueprints.bpcs} BPC</span></div>}
        </div>
      </div>}
    </div>
  </section>;

}
function blueprintReferenceDetails(blueprintTypeId: number | null | undefined, name: string, blueprints: Blueprint[]) {
  const matches = blueprints.filter((blueprint) => blueprintTypeId != null ? blueprint.blueprint_type_id === blueprintTypeId : blueprint.blueprint_type_name === name);
  if (matches.length === 0) return { name, definitionOnly: true };
  return { ...blueprintHoverDetails(matches[0]), note: matches.length > 1 ? `${matches.length.toLocaleString()} owned instances match this blueprint reference; showing the most recently loaded instance.` : null };
}

function BlueprintList({ blueprints, assets = [], onOpenMarket, onOpenAssets }: { blueprints: Blueprint[]; assets?: Asset[]; onOpenMarket?: (text: string) => void; onOpenAssets?: (itemName: string) => void }) {

  const [kindFilter, setKindFilter] = useState<"all" | "bpo" | "bpc">("all");

  const [ownerFilter, setOwnerFilter] = useState<string | null>(null);

  const [categoryFilter, setCategoryFilter] = useState<InventoryFamilyFilter>("all");

  const [subtypeFilter, setSubtypeFilter] = useState("");

  const [searchText, setSearchText] = useState("");

  const [sortKey, setSortKey] = useState<"name" | "me" | "te">("name");

  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const bpoCount = blueprints.filter((blueprint) => !blueprint.is_copy).length;

  const bpcCount = blueprints.filter((blueprint) => blueprint.is_copy).length;

  const ownerOptions = sortedUnique(blueprints.map((blueprint) => blueprint.owner_name));

  const ownerCounts = new Map<string, number>();

  for (const blueprint of blueprints) ownerCounts.set(blueprint.owner_name, (ownerCounts.get(blueprint.owner_name) ?? 0) + 1);

  const blueprintCategoryOptions: InventoryFamilyFilter[] = ["all", "ships", "ammunition", "drones", "rigs", "reactions", "ram", "capital-construction"];

  const kindFilteredBlueprints = kindFilter === "all" ? blueprints : blueprints.filter((blueprint) => kindFilter === "bpc" ? blueprint.is_copy : !blueprint.is_copy);

  const ownerFilteredBlueprints = ownerFilter ? kindFilteredBlueprints.filter((blueprint) => blueprint.owner_name === ownerFilter) : kindFilteredBlueprints;

  const categoryFilteredBlueprints = ownerFilteredBlueprints.filter((blueprint) => matchesInventoryFamily(categoryFilter, blueprintFamily(blueprint), Boolean(blueprint.capital_construction_related)));

  const subtypeOptions = sortedUnique(categoryFilteredBlueprints.map(blueprintSubtype));

  const subtypeFilteredBlueprints = subtypeFilter ? categoryFilteredBlueprints.filter((blueprint) => blueprintSubtype(blueprint) === subtypeFilter) : categoryFilteredBlueprints;

  const searchNeedle = searchText.trim().toLowerCase();

  const filteredBlueprints = searchNeedle ? subtypeFilteredBlueprints.filter((blueprint) => [blueprint.blueprint_type_name, blueprint.product_type_name, blueprint.owner_name, blueprint.location_name, blueprint.product_category_name, blueprint.product_group_name, blueprint.is_copy ? "BPC" : "BPO", `ME ${blueprint.material_efficiency}`, `TE ${blueprint.time_efficiency}`].filter(Boolean).join(" ").toLowerCase().includes(searchNeedle)) : subtypeFilteredBlueprints;

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



  function applyBlueprintSubtypeFilter(blueprint: Blueprint) {

    const family = blueprintFamily(blueprint);

    setCategoryFilter(family === "other" ? "all" : family);

    setSubtypeFilter(blueprintSubtype(blueprint) ?? "");

  }


  return <div className="blueprint-browser">
    <div className="blueprint-controls">
      <div className="blueprint-filter">
        <button type="button" className={kindFilter === "all" ? "active" : ""} onClick={() => setKindFilter("all")}>All <span>{blueprints.length.toLocaleString()}</span></button>
        <button type="button" className={kindFilter === "bpo" ? "active" : ""} onClick={() => setKindFilter("bpo")}>BPO <span>{bpoCount.toLocaleString()}</span></button>
        <button type="button" className={kindFilter === "bpc" ? "active" : ""} onClick={() => setKindFilter("bpc")}>BPC <span>{bpcCount.toLocaleString()}</span></button>
      </div>
      <div className="blueprint-filter sort">
        <button type="button" className={sortKey === "name" ? "active" : ""} onClick={() => chooseSort("name")}>A-Z <span>{sortLabel("name")}</span></button>
        <button type="button" className={sortKey === "me" ? "active" : ""} onClick={() => chooseSort("me")}>ME <span>{sortLabel("me")}</span></button>
        <button type="button" className={sortKey === "te" ? "active" : ""} onClick={() => chooseSort("te")}>TE <span>{sortLabel("te")}</span></button>
      </div>
    </div>
    <div className="blueprint-filter family-filter">
      {blueprintCategoryOptions.map((family) => <button type="button" key={family} className={categoryFilter === family ? "active" : ""} onClick={() => { setCategoryFilter(family); setSubtypeFilter(""); }}>{inventoryFamilyLabels[family]}</button>)}
    </div>
    <div className="blueprint-refine-row">
      <label className="blueprint-search">Search blueprints<input value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Blueprint, product, owner, location, hull class, ammo, rig" /></label>
      <label>Subtype<select value={subtypeFilter} onChange={(event) => setSubtypeFilter(event.target.value)}><option value="">All subtypes</option>{subtypeOptions.map((subtype) => <option key={subtype} value={subtype}>{subtype}</option>)}</select></label>
    </div>
    <div className="blueprint-filter owners"><button type="button" className={ownerFilter === null ? "active" : ""} onClick={() => setOwnerFilter(null)}>All owners <span>{blueprints.length.toLocaleString()}</span></button>{ownerOptions.map((owner) => <button type="button" key={owner} className={ownerFilter === owner ? "active" : ""} onClick={() => setOwnerFilter(owner)}>{owner} <span>{(ownerCounts.get(owner) ?? 0).toLocaleString()}</span></button>)}</div>
    <div className="card-list">{visibleBlueprints.map((bp) => { const ownedOutput = visibleAssetQuantity(assets, bp.product_type_name); const outputLocations = visibleAssetLocations(assets, bp.product_type_name); return <article key={bp.id}><BlueprintHoverCard details={blueprintHoverDetails(bp)}><strong>{bp.blueprint_type_name}</strong></BlueprintHoverCard><span><button type="button" className="inline-filter" onClick={() => setOwnerFilter(bp.owner_name)}>{bp.owner_name}</button> · {bp.product_type_name ?? "No product"}</span>{bp.product_group_name && <small>{bp.product_category_name ? `${bp.product_category_name} / ` : ""}{bp.product_group_name}</small>}{bp.product_type_name && <div className="blueprint-context"><span className={ownedOutput > 0 ? "context-owned" : "context-missing"}>Owned output: {numberFormatter.format(ownedOutput)}</span>{outputLocations.length > 0 && <small>{outputLocations.join(" | ")}</small>}<div className="context-actions">{onOpenAssets && <button type="button" onClick={() => onOpenAssets(bp.product_type_name!)}>Assets</button>}{onOpenMarket && <button type="button" onClick={() => onOpenMarket(`1 ${bp.product_type_name}`)}>Price output</button>}</div></div>}<div className="badge-row"><button type="button" className="bp-badge" onClick={() => chooseSort("me")}>ME {bp.material_efficiency}</button><button type="button" className="bp-badge" onClick={() => chooseSort("te")}>TE {bp.time_efficiency}</button><button type="button" className={bp.is_copy ? "bp-badge copy" : "bp-badge original"} onClick={() => setKindFilter(bp.is_copy ? "bpc" : "bpo")}>{bp.is_copy ? "BPC" : "BPO"}</button>{bp.product_group_name && <button type="button" className="bp-badge" onClick={() => applyBlueprintSubtypeFilter(bp)}>{bp.product_group_name}</button>}{bp.capital_construction_related && <button type="button" className="bp-badge original" onClick={() => { setCategoryFilter("capital-construction"); setSubtypeFilter(""); }}>Capital chain</button>}</div></article>; })}{blueprints.length === 0 && <p className="empty">No blueprints yet.</p>}{blueprints.length > 0 && visibleBlueprints.length === 0 && <p className="empty">{searchNeedle ? `No blueprints match "${searchText.trim()}".` : "No blueprints match this filter."}</p>}</div>
    <MissingBlueprintPane onOpenMarket={onOpenMarket} onOpenAssets={onOpenAssets} />
  </div>;

}


function MissingBlueprintPane({ onOpenMarket, onOpenAssets }: { onOpenMarket?: (text: string) => void; onOpenAssets?: (itemName: string) => void }) {

  const [catalog, setCatalog] = useState<MissingBlueprintCatalog | null>(null);

  const [searchText, setSearchText] = useState("");

  const [activeCategory, setActiveCategory] = useState<string>("all");

  const [busy, setBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);

  async function loadMissingBlueprints(query = searchText) {

    setBusy(true);

    setError(null);

    try {

      const params = query.trim() ? `?q=${encodeURIComponent(query.trim())}` : "";

      const nextCatalog = await api<MissingBlueprintCatalog>(`/quartermaster/missing-blueprints${params}`);

      setCatalog(nextCatalog);

      if (activeCategory !== "all" && !nextCatalog.categories.some((category) => category.category_name === activeCategory)) setActiveCategory("all");

    } catch (err) {

      setError(err instanceof Error ? err.message : "Unable to load missing BPOs.");

    } finally {

      setBusy(false);

    }

  }



  useEffect(() => {

    void loadMissingBlueprints("");

  }, []);



  const visibleCategories = catalog ? (activeCategory === "all" ? catalog.categories : catalog.categories.filter((category) => category.category_name === activeCategory)) : [];

  const marketText = visibleCategories.flatMap((category) => category.items.map((item) => `1 ${item.blueprint_type_name}`)).join("\n");

  return <section className="missing-bpo-pane">
    <div className="section-heading compact">
      <div>
        <h4>Missing BPOs</h4>
        <p className="muted">{catalog ? `${catalog.total_missing.toLocaleString()} missing originals by product category · ${catalog.owned_bpos.toLocaleString()} owned originals visible` : "Loading blueprint coverage..."}</p>
      </div>
      <div className="button-row compact"><button type="button" disabled={busy} onClick={() => void loadMissingBlueprints()}>{busy ? "Refreshing..." : "Refresh"}</button>{onOpenMarket && marketText && <button type="button" onClick={() => onOpenMarket(marketText)}>Price visible</button>}</div>
    </div>
    <div className="blueprint-refine-row">
      <label>Search missing BPOs<input value={searchText} onChange={(event) => setSearchText(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void loadMissingBlueprints(); }} placeholder="Ship, ammo, rig, component, blueprint" /></label>
      <button type="button" disabled={busy} onClick={() => void loadMissingBlueprints()}>Search</button>
    </div>
    {error && <div className="mini-alert">{error}</div>}
    {catalog && <div className="blueprint-filter owners"><button type="button" className={activeCategory === "all" ? "active" : ""} onClick={() => setActiveCategory("all")}>All categories <span>{catalog.total_missing.toLocaleString()}</span></button>{catalog.categories.map((category) => <button type="button" key={category.category_name} className={activeCategory === category.category_name ? "active" : ""} onClick={() => setActiveCategory(category.category_name)}>{category.category_name} <span>{category.total_count.toLocaleString()}</span></button>)}</div>}
    <div className="missing-bpo-groups">{visibleCategories.map((category) => <article key={category.category_name}><div className="section-heading compact"><div><strong>{category.category_name}</strong><span>{category.total_count.toLocaleString()} missing BPO{category.total_count === 1 ? "" : "s"}</span></div></div><div className="mini-list">{category.items.map((item) => <div key={item.blueprint_type_id}><BlueprintHoverCard details={{ name: item.blueprint_type_name, kind: "BPO", definitionOnly: true, note: "This BPO is currently missing from visible synced inventory." }}><strong>{item.blueprint_type_name}</strong></BlueprintHoverCard><span>{item.product_type_name ?? "No product"}{item.product_group_name ? ` · ${item.product_group_name}` : ""}{item.capital_construction_related ? " · Capital chain" : ""}</span><div className="context-actions">{onOpenMarket && <button type="button" onClick={() => onOpenMarket(`1 ${item.blueprint_type_name}`)}>Price BPO</button>}{onOpenAssets && item.product_type_name && <button type="button" onClick={() => onOpenAssets(item.product_type_name!)}>Assets</button>}</div></div>)}{category.items.length < category.total_count && <p className="muted">Showing {category.items.length.toLocaleString()} of {category.total_count.toLocaleString()} missing in this category. Search to narrow.</p>}</div></article>)}{catalog && catalog.total_missing === 0 && <p className="empty">No missing BPOs match this search.</p>}</div>
  </section>;

}


function RecipeList({ activities, blueprints, onSelect, onLoadMore, loadingMore, hasMore }: { activities: IndustryActivity[]; blueprints: Blueprint[]; onSelect: (activity: IndustryActivity) => void; onLoadMore: () => void; loadingMore: boolean; hasMore: boolean }) {

  function handleScroll(event: React.UIEvent<HTMLDivElement>) {

    const element = event.currentTarget;

    if (element.scrollHeight - element.scrollTop - element.clientHeight < 160) onLoadMore();

  }



  return <div className="card-list recipe-list" onScroll={handleScroll}>{activities.map((activity) => <article key={activity.id}><button type="button" className="recipe-card-button" onClick={() => onSelect(activity)}><BlueprintHoverCard details={blueprintReferenceDetails(activity.blueprint_type_id, activity.blueprint_type_name, blueprints)}><strong>{activity.blueprint_type_name}</strong></BlueprintHoverCard><span>{activity.activity_kind} · {activity.product_type_name ?? "No product"} x{activity.product_quantity}</span><span>{activity.inputs.length.toLocaleString()} inputs · {activity.time_seconds ? `${numberFormatter.format(activity.time_seconds)} sec` : "No time listed"}</span></button></article>)}{activities.length === 0 && <p className="empty">No recipes yet.</p>}{loadingMore && <p className="muted">Loading more recipes...</p>}{!loadingMore && !hasMore && activities.length > 0 && <p className="muted">All visible recipes loaded.</p>}</div>;

}



function RecipeDetailModal({ activity, blueprints, assets, onOpenMarket, onOpenAssets, onClose }: { activity: IndustryActivity; blueprints: Blueprint[]; assets: Asset[]; onOpenMarket: (text: string) => void; onOpenAssets: (itemName: string) => void; onClose: () => void }) {

  const outputOwned = visibleAssetQuantity(assets, activity.product_type_name);

  const missingInputs = activity.inputs

    .map((input) => ({ input, owned: visibleAssetQuantity(assets, input.input_type_name), missing: Math.max(0, input.quantity - visibleAssetQuantity(assets, input.input_type_name)) }))

    .filter((row) => row.missing > 0);

  const missingMarketText = missingInputs.map((row) => `${row.missing} ${row.input.input_type_name}`).join("\n");

  return <div className="modal-backdrop" role="presentation" onClick={onClose}><section className="modal-window recipe-detail" role="dialog" aria-modal="true" aria-label={`${activity.blueprint_type_name} recipe`} onClick={(event) => event.stopPropagation()}><div className="section-heading"><div><h3><BlueprintHoverCard details={blueprintReferenceDetails(activity.blueprint_type_id, activity.blueprint_type_name, blueprints)}>{activity.blueprint_type_name}</BlueprintHoverCard></h3><p>{activity.activity_kind} · {activity.product_type_name ?? "No product"} x{activity.product_quantity}</p></div><div className="button-row compact">{missingMarketText && <button type="button" onClick={() => onOpenMarket(missingMarketText)}>Price missing inputs</button>}<button type="button" onClick={onClose}>Close</button></div></div><div className="status-grid compact"><Metric icon={<Factory size={18} />} label="Activity" value={activity.activity_kind.replace("_", " ")} /><Metric icon={<PackagePlus size={18} />} label="Output" value={activity.product_quantity} /><Metric icon={<Boxes size={18} />} label="Owned output" value={outputOwned} /><Metric icon={<ScrollText size={18} />} label="Inputs" value={activity.inputs.length} /><Metric icon={<Activity size={18} />} label="Time" value={activity.time_seconds ? `${numberFormatter.format(activity.time_seconds)} sec` : "n/a"} /></div>{activity.product_type_name && <div className="recipe-output-context"><strong>{activity.product_type_name}</strong><span className={outputOwned > 0 ? "context-owned" : "context-missing"}>Already owned: {numberFormatter.format(outputOwned)}</span><div className="context-actions"><button type="button" onClick={() => onOpenAssets(activity.product_type_name!)}>View assets</button><button type="button" onClick={() => onOpenMarket(`${activity.product_quantity} ${activity.product_type_name}`)}>Price output</button></div></div>}<h4>Material Inputs</h4><div className="mini-list recipe-inputs">{activity.inputs.map((input) => { const owned = visibleAssetQuantity(assets, input.input_type_name); const missing = Math.max(0, input.quantity - owned); return <div key={input.id} className={missing > 0 ? "missing" : "covered"}><strong>{input.input_type_name}</strong><span>{numberFormatter.format(input.quantity)} {input.consume_type} · owned {numberFormatter.format(owned)} · {missing > 0 ? `short ${numberFormatter.format(missing)}` : "covered"}</span><div className="context-actions"><button type="button" onClick={() => onOpenAssets(input.input_type_name)}>Assets</button><button type="button" onClick={() => onOpenMarket(`${Math.max(1, missing || input.quantity)} ${input.input_type_name}`)}>Price</button></div></div>; })}{activity.inputs.length === 0 && <p className="empty">No material inputs listed for this activity.</p>}</div></section></div>;

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

  return ({ overview: "Quartermaster Overview", ownership: "Ownership and Locations", characters: "Characters", roster: "Alliance Roster", navigation: "Navigation", market: "Market Appraisal", exchange: "Corporate Exchange", hypernet: "HyperNet Tracker", calendar_events: "Calendar & Events", notes: "Notes & Lists", manufacturing: "Manufacturing", research_projects: "Research Projects", mining: "Mining Ledger", planetary_industry: "Planetary Industry", contracts: "Contracts", analytics: "Analytics Platform", recruiting: "Recruiting", skills: "Character Skills", fittings: "Fittings", jump_clones: "Jump Clones", settings: "Settings", corporations: "Corporations", assets: "Asset Ledger", industry: "Blueprints and Recipes", esi: "ESI Sync", profile: "Profile", users: "User Administration", audit: "Audit Log" } as Record<string, string>)[tab];

}



function subtitleFor(tab: string) {

  return ({ overview: "Live status and the first useful totals from the database.", ownership: "Define the characters, corporations, manual buckets, and places assets can belong to.", characters: "Assign EVE characters to Quartermaster accounts and control public asset visibility.", roster: "A corporation-grouped character roster suitable for diplomats and prospective members.", navigation: "Plan gate routes from imported SDE map data before layering on kill checks and local threat analysis.", market: "Paste item lists and compare buy, sell, and split prices across trade hubs.", hypernet: "Plan, monitor, and reconcile HyperNet offers with seller-seeded nodes kept separate from organic participation.", calendar_events: "Plan fleets, register pilots, record attendance, and measure participation.", notes: "Keep private working notes and destination-aware resupply lists with live asset context.", manufacturing: "Track manufacturing jobs, costs, required inputs, hub prices, and production history.", research_projects: "Monitor ESI research, copying, and invention queues while retaining project history for analytics.", mining: "Track persistent per-character mining yield, residue efficiency, and named fleet operations.", planetary_industry: "Monitor synchronized colonies, extractor cycles, routed production, storage, and factory health.", contracts: "Sync and review current character and corporation contracts.", analytics: "Snapshot history, metric widgets, exports, and the foundation for custom dashboards.", recruiting: "Configure public recruiting, review applicants, and coordinate interviews without exposing internal notes.", skills: "Import trained skills, total skill points, and active skill queues from ESI.", fittings: "Sync saved EVE fittings, review modules, experiment in a scratchpad, and copy EFT-style text.", jump_clones: "Sync jump clones, inspect implants, and build custom implant sets for fitting experiments.", settings: "Control character visibility and sync privacy.", corporations: "Review enrolled corporations and sync corporation asset ledgers through authorized CEO or director tokens.", assets: "Track item stacks by owner, type, location, and EVE-style location flag.", industry: "Store blueprints, recipe activities, and material inputs before wiring in SDE imports.", esi: "A holding area for the upcoming SSO and sync work.", profile: "Manage your account and private messages.", users: "Manage Quartermaster accounts and role levels.", audit: "Review sync peeks, system events, and administrative activity." } as Record<string, string>)[tab];

}



createRoot(document.getElementById("root")!).render(<App />);
