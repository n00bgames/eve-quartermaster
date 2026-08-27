import { Activity, Database, MapIcon, ScrollText } from "lucide-react";
import type { FormEvent, ReactElement, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { WardecBadge } from "../../components/WardecBadge";
import { PilotSecurityStatus } from "../characters/PilotSecurityStatus";
import { eveSecurityClass, eveSecurityLabel, isUedamaSystem } from "../../lib/evePresentation";
import { formatDateTime, preferredTimeZone } from "../../lib/time";
import { iskFormatter } from "../../lib/market";
import type { NavigationGatecheckRoute, NavigationRoute, NavigationSystem, UedamaScoutStatus } from "../../types/navigation";
import { OperationalMap } from "./OperationalMap";

type RouteCheckerUser = { timezone?: string };
type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type EveEntityKind = "character" | "corporation" | "alliance";
type EveIconSize = "tiny" | "sm" | "md" | "lg";

type RouteCheckerProps = {
  currentUser: RouteCheckerUser;
  api: ApiClient;
  numberFormatter: Intl.NumberFormat;
  Metric: (props: { icon: ReactNode; label: string; value: string | number; delta?: string }) => ReactElement;
  EveEntityIcon: (props: { kind: EveEntityKind; id?: number | null; name?: string | null; size?: EveIconSize }) => ReactElement;
  CharacterHoverName: (props: { characterId?: number | null; name: string; className?: string; href?: string }) => ReactElement;
  UedamaScoutLiveLink: (props: { status: UedamaScoutStatus | null }) => ReactElement | null;
};
export function SystemSearchField({ label, value, options, placeholder, onChange, onPick }: { label: string; value: string; options: NavigationSystem[]; placeholder: string; onChange: (value: string) => void; onPick: (system: NavigationSystem) => void }) {

  return <div className="system-search-field"><label>{label}<input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} autoComplete="off" /></label>{options.length > 0 && <div className="system-suggestions">{options.map((system) => <button key={system.system_id} type="button" onClick={() => onPick(system)}><strong>{system.name}</strong><span>{system.region_name ?? "Unknown region"}{system.constellation_name ? ` · ${system.constellation_name}` : ""}</span><span className={`security-dot ${eveSecurityClass(system.security_status)}`}>{eveSecurityLabel(system.security_status)}</span></button>)}</div>}</div>;

}



export function RouteChecker({ currentUser, api, numberFormatter, Metric, EveEntityIcon, CharacterHoverName, UedamaScoutLiveLink }: RouteCheckerProps) {

  const [origin, setOrigin] = useState("Jita");

  const [destination, setDestination] = useState("Amarr");

  const [highsecOnly, setHighsecOnly] = useState(false);

  const [preferSafer, setPreferSafer] = useState(true);

  const [industrialOnly, setIndustrialOnly] = useState(true);

  const [gatecheckHours, setGatecheckHours] = useState(1);

  const [originOptions, setOriginOptions] = useState<NavigationSystem[]>([]);

  const [destinationOptions, setDestinationOptions] = useState<NavigationSystem[]>([]);

  const [route, setRoute] = useState<NavigationRoute | null>(null);

  const [gatecheck, setGatecheck] = useState<NavigationGatecheckRoute | null>(null);

  const [avoidSystems, setAvoidSystems] = useState<NavigationSystem[]>([]);

  const [uedamaScout, setUedamaScout] = useState<UedamaScoutStatus | null>(null);

  const [expandedSystems, setExpandedSystems] = useState<Set<number>>(new Set());

  const [status, setStatus] = useState<{ systems: number; stargates: number; stations?: number } | null>(null);

  const [busy, setBusy] = useState(false);

  const [gatecheckBusy, setGatecheckBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const originSelectionRef = useRef(origin);

  const destinationSelectionRef = useRef(destination);

  const timeZone = preferredTimeZone(currentUser);






  async function loadStatus() {

    setStatus(await api<{ systems: number; stargates: number; stations?: number }>("/navigation/status"));

  }



  async function searchSystems(query: string, setter: (systems: NavigationSystem[]) => void) {

    if (query.trim().length < 2) {

      setter([]);

      return;

    }

    try {

      setter(await api<NavigationSystem[]>(`/navigation/systems?q=${encodeURIComponent(query)}&limit=12`));

    } catch {

      setter([]);

    }

  }



  function pickOrigin(system: NavigationSystem) {

    originSelectionRef.current = system.name;

    setOrigin(system.name);

    setOriginOptions([]);

  }



  function pickDestination(system: NavigationSystem) {

    destinationSelectionRef.current = system.name;

    setDestination(system.name);

    setDestinationOptions([]);

  }



  function toggleSystem(systemId: number) {

    setExpandedSystems((current) => {

      const next = new Set(current);

      if (next.has(systemId)) next.delete(systemId);

      else next.add(systemId);

      return next;

    });

  }



  function routeParams(routeAvoidSystems = avoidSystems) {

    const params = new URLSearchParams({ origin, destination, highsec_only: String(highsecOnly), prefer_safer: String(preferSafer) });

    if (routeAvoidSystems.length > 0) params.set("avoid_systems", routeAvoidSystems.map((system) => system.name).join(","));

    return params;

  }



  async function planRoute(event?: FormEvent, routeAvoidSystems = avoidSystems) {

    event?.preventDefault();

    setBusy(true);

    setError(null);

    setGatecheck(null);

    setExpandedSystems(new Set());

    try {

      setRoute(await api<NavigationRoute>(`/navigation/route?${routeParams(routeAvoidSystems).toString()}`));

    } catch (err) {

      setError(err instanceof Error ? err.message : "Route planning failed");

      setRoute(null);

    } finally {

      setBusy(false);

    }

  }



  async function runGatecheck() {

    setGatecheckBusy(true);

    setError(null);

    try {

      const params = routeParams();

      params.set("hours", String(gatecheckHours));

      params.set("industrial_only", String(industrialOnly));

      setGatecheck(await api<NavigationGatecheckRoute>(`/navigation/gatecheck?${params.toString()}`));

      setExpandedSystems(new Set());

    } catch (err) {

      setError(err instanceof Error ? err.message : "Gatecheck failed");

      setGatecheck(null);

    } finally {

      setGatecheckBusy(false);

    }

  }



  function addRouteAvoidSystem(system: NavigationSystem) {

    if (route && (system.system_id === route.origin.system_id || system.system_id === route.destination.system_id)) {

      setError("Origin and destination cannot be avoided for this route.");

      return;

    }

    if (avoidSystems.some((candidate) => candidate.system_id === system.system_id)) return;

    const next = [...avoidSystems, system];

    setAvoidSystems(next);

    if (route) void planRoute(undefined, next);

    else setGatecheck(null);

  }



  function removeRouteAvoidSystem(systemId: number) {

    const next = avoidSystems.filter((system) => system.system_id !== systemId);

    setAvoidSystems(next);

    if (route) void planRoute(undefined, next);

    else setGatecheck(null);

  }



  function clearRouteAvoidSystems() {

    setAvoidSystems([]);

    if (route) void planRoute(undefined, []);

    else setGatecheck(null);

  }



  useEffect(() => { void loadStatus().catch(() => setStatus(null)); }, []);

  useEffect(() => { if (origin.trim() === originSelectionRef.current.trim()) { setOriginOptions([]); return; } const timer = window.setTimeout(() => void searchSystems(origin, setOriginOptions), 180); return () => window.clearTimeout(timer); }, [origin]);

  useEffect(() => { if (destination.trim() === destinationSelectionRef.current.trim()) { setDestinationOptions([]); return; } const timer = window.setTimeout(() => void searchSystems(destination, setDestinationOptions), 180); return () => window.clearTimeout(timer); }, [destination]);



  const mapLoaded = (status?.systems ?? 0) > 0 && (status?.stargates ?? 0) > 0;

  const displayedRoute = gatecheck ?? route;
  const routeScoutKey = displayedRoute?.systems.map((system) => system.system_id).join(":") ?? "";

  const routeHasUedama = Boolean(displayedRoute?.systems.some(isUedamaSystem));

  useEffect(() => {
    if (!routeHasUedama) {
      setUedamaScout(null);
      return;
    }
    let cancelled = false;
    void api<UedamaScoutStatus>("/navigation/uedama-scout")
      .then((status) => {
        if (!cancelled) setUedamaScout(status);
      })
      .catch(() => {
        if (!cancelled) setUedamaScout(null);
      });
    return () => {
      cancelled = true;
    };
  }, [routeHasUedama, routeScoutKey]);



  return <section className="panel stacked navigation-planner"><div className="section-heading"><div><h3>Route Checker</h3><p>{status ? `${numberFormatter.format(status.systems)} systems, ${numberFormatter.format(status.stargates)} stargates, and ${numberFormatter.format(status.stations ?? 0)} stations loaded from SDE` : "Checking imported map data"}</p></div><button type="button" onClick={() => void loadStatus()}>Refresh map status</button></div>{!mapLoaded && <div className="mini-alert">No stargate map is loaded yet. Import the SDE again from Settings to load regions, systems, and stargates.</div>}<form className="route-form" onSubmit={(event) => void planRoute(event)}><SystemSearchField label="Origin" value={origin} options={originOptions} placeholder="Jita" onChange={(value) => { originSelectionRef.current = ""; setOrigin(value); }} onPick={pickOrigin} /><SystemSearchField label="Destination" value={destination} options={destinationOptions} placeholder="Amarr" onChange={(value) => { destinationSelectionRef.current = ""; setDestination(value); }} onPick={pickDestination} /><label className="checkbox-row"><input type="checkbox" checked={highsecOnly} onChange={(event) => setHighsecOnly(event.target.checked)} /> Highsec only</label><label className="checkbox-row"><input type="checkbox" checked={preferSafer} disabled={highsecOnly} onChange={(event) => setPreferSafer(event.target.checked)} /> Prefer safer route</label><button type="submit" disabled={busy || !origin.trim() || !destination.trim()}><MapIcon size={18} /> {busy ? "Planning" : "Plan route"}</button></form>{avoidSystems.length > 0 && <div className="avoid-list-panel"><div><strong>Avoiding</strong><span>{avoidSystems.length} system{avoidSystems.length === 1 ? "" : "s"}</span></div><div className="avoid-chip-row">{avoidSystems.map((system) => <button type="button" key={system.system_id} className={`avoid-chip ${eveSecurityClass(system.security_status)}`} onClick={() => removeRouteAvoidSystem(system.system_id)}>{system.name} x</button>)}<button type="button" className="avoid-clear" onClick={clearRouteAvoidSystems}>Clear avoid list</button></div></div>}{error && <div className="mini-alert">{error}</div>}{displayedRoute && <div className="route-results"><div className="section-heading compact"><div><h3>{displayedRoute.origin.name} to {displayedRoute.destination.name}</h3><p>{displayedRoute.jump_count.toLocaleString()} jumps · {displayedRoute.highsec_count} high · {displayedRoute.lowsec_count} low · {displayedRoute.nullsec_count} null</p></div><div className="button-row compact"><label className="compact-field">Hours<input type="number" min="1" max="168" value={gatecheckHours} onChange={(event) => setGatecheckHours(Number(event.target.value))} /></label><label className="checkbox-row compact-check"><input type="checkbox" checked={industrialOnly} onChange={(event) => setIndustrialOnly(event.target.checked)} /> Industrial kills only</label><button type="button" disabled={gatecheckBusy} onClick={() => void runGatecheck()}><Activity size={18} /> {gatecheckBusy ? "Checking" : "Gatecheck"}</button></div></div>{gatecheck && <div className="gatecheck-summary"><Metric icon={<Activity size={18} />} label={gatecheck.gatecheck.industrial_only ? "Industrial kills" : "Recent kills"} value={gatecheck.gatecheck.total_recent_kills} /><Metric icon={<Database size={18} />} label="Destroyed value" value={`${iskFormatter.format(gatecheck.gatecheck.total_destroyed_value)} ISK`} /><Metric icon={<MapIcon size={18} />} label="Systems checked" value={gatecheck.gatecheck.checked_systems} /><Metric icon={<ScrollText size={18} />} label="Lookback" value={`${gatecheck.gatecheck.hours}h`} /></div>}{gatecheck?.gatecheck.error_count ? <div className="mini-alert">Gatecheck reached the route, but {gatecheck.gatecheck.error_count} system lookup{gatecheck.gatecheck.error_count === 1 ? "" : "s"} failed.</div> : null}<details className="route-map-disclosure"><summary>Show on Operational Map</summary><OperationalMap title="Operational Map" subtitle={`${displayedRoute.origin.name} to ${displayedRoute.destination.name} · ${displayedRoute.jump_count.toLocaleString()} gates`} badge={`${displayedRoute.jump_count} gates`} routeSystems={displayedRoute.systems.map((system) => ({ ...system, map_index: system.jump_index, label: `${system.jump_index}. ${system.name}`, meta: `${system.region_name ?? "Unknown region"} · ${eveSecurityLabel(system.security_status)}`, selected_key: String(system.system_id), segment_label: system.jump_index > 0 ? "Gate" : null }))} mapContext={displayedRoute.map_context} selectedKey={Array.from(expandedSystems)[0] ? String(Array.from(expandedSystems)[0]) : null} onSelectRouteSystem={(key) => { if (key) toggleSystem(Number(key)); }} /></details><div className="route-list" role="list">{displayedRoute.systems.map((system) => { const expanded = expandedSystems.has(system.system_id); const samples = system.sample_killmails ?? []; const isEndpoint = system.system_id === displayedRoute.origin.system_id || system.system_id === displayedRoute.destination.system_id; const isAvoiding = avoidSystems.some((candidate) => candidate.system_id === system.system_id); return <div key={`${system.jump_index}-${system.system_id}`} className={`route-row risk-${system.risk_label ?? "none"} ${expanded ? "expanded" : ""}`} role="button" tabIndex={0} onClick={() => toggleSystem(system.system_id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggleSystem(system.system_id); } }}><span className="route-index">{system.jump_index}</span><div><strong>{system.name}</strong><span>{system.region_name ?? "Unknown region"}{system.constellation_name ? ` · ${system.constellation_name}` : ""}</span>{system.jump_activity && <span className="gatecheck-line">{system.jump_activity.observations > 0 ? <>Last hour: {system.jump_activity.jumps_last_hour.toLocaleString()} jumps · {system.jump_activity.ship_kills_last_hour.toLocaleString()} ship kills · {system.jump_activity.pod_kills_last_hour.toLocaleString()} pod kills</> : <>Last-hour traffic unavailable</>}</span>}{system.recent_kill_count !== undefined && <span className="gatecheck-line">{system.recent_kill_count ?? "?"} {gatecheck?.gatecheck.industrial_only ? "industrial kills" : "recent kills"}{typeof system.recent_destroyed_value === "number" ? ` · ${iskFormatter.format(system.recent_destroyed_value)} ISK destroyed` : ""}{system.latest_killmail_time ? ` · latest ${formatDateTime(system.latest_killmail_time, timeZone)}` : ""}</span>}</div><div className="route-badges"><span className={`security-badge ${eveSecurityClass(system.security_status)}`}>{eveSecurityLabel(system.security_status)}</span>{system.risk_label && <span className={`risk-badge risk-${system.risk_label}`}>{system.risk_label}</span>}{isUedamaSystem(system) && <UedamaScoutLiveLink status={uedamaScout} />}{!isEndpoint && <button type="button" className="route-avoid-button" disabled={isAvoiding} onClick={(event) => { event.stopPropagation(); addRouteAvoidSystem(system); }}>{isAvoiding ? "Avoiding" : "Avoid"}</button>}</div>{expanded && <div className="killmail-detail-list">{samples.length > 0 ? samples.map((kill) => <article key={kill.killmail_id ?? `${system.system_id}-${kill.killmail_time}`}><div><strong>{kill.victim_hull ?? "Unknown hull"}</strong>{kill.smartbomb_used && <span className="smartbomb-badge">Smartbombs</span>}{kill.is_wardec && <WardecBadge />}<span className="killmail-entity-line"><EveEntityIcon kind="character" id={kill.victim?.character_id} name={kill.victim?.character_name} size="tiny" />Victim: <CharacterHoverName characterId={kill.victim?.character_id} name={kill.victim?.character_name ?? "Unknown pilot"} href={kill.victim?.character_id ? `https://zkillboard.com/character/${kill.victim.character_id}/` : undefined} /><PilotSecurityStatus securityStatus={kill.victim?.security_status} compact />{kill.victim?.corporation_id && <EveEntityIcon kind="corporation" id={kill.victim.corporation_id} name={kill.victim.corporation_name} size="tiny" />}{kill.victim?.corporation_name ? ` · ${kill.victim.corporation_name}` : ""}{kill.victim?.alliance_id && <EveEntityIcon kind="alliance" id={kill.victim.alliance_id} name={kill.victim.alliance_name} size="tiny" />}{kill.victim?.alliance_name ? ` · ${kill.victim.alliance_name}` : ""}</span><span>{kill.location_kind ?? "space"} · {kill.location_name ?? "Unknown location"}</span></div><div><span>{kill.attacker_count ?? "?"} attackers · {kill.combatant_count ?? "?"} combatants</span><span className="killmail-entity-line"><EveEntityIcon kind="character" id={kill.final_blow?.character_id} name={kill.final_blow?.character_name} size="tiny" />Final blow: {kill.final_blow?.ship_type_name ?? "Unknown ship"} · <CharacterHoverName characterId={kill.final_blow?.character_id} name={kill.final_blow?.character_name ?? "Unknown pilot"} href={kill.final_blow?.character_id ? `https://zkillboard.com/character/${kill.final_blow.character_id}/` : undefined} /><PilotSecurityStatus securityStatus={kill.final_blow?.security_status} compact />{kill.final_blow?.corporation_id && <EveEntityIcon kind="corporation" id={kill.final_blow.corporation_id} name={kill.final_blow.corporation_name} size="tiny" />}{kill.final_blow?.corporation_name ? ` · ${kill.final_blow.corporation_name}` : ""}{kill.final_blow?.alliance_id && <EveEntityIcon kind="alliance" id={kill.final_blow.alliance_id} name={kill.final_blow.alliance_name} size="tiny" />}{kill.final_blow?.alliance_name ? ` · ${kill.final_blow.alliance_name}` : ""}</span>{kill.killmail_time && <span>{formatDateTime(kill.killmail_time, timeZone)} · {typeof kill.total_value === "number" ? `${iskFormatter.format(kill.total_value)} ISK` : "value unknown"}</span>}{(kill.zkb_url || (kill.killmail_id ? `https://zkillboard.com/kill/${kill.killmail_id}/` : null)) && <a href={kill.zkb_url || `https://zkillboard.com/kill/${kill.killmail_id}/`} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>Open killmail{kill.killmail_id ? ` #${kill.killmail_id}` : ""}</a>}</div></article>) : <p className="empty">No recent killmail details for this system in the selected window.</p>}</div>}</div>; })}</div></div>}</section>;

}



