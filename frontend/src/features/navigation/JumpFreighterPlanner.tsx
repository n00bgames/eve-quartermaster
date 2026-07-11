import { Activity, Database, Factory, MapIcon } from "lucide-react";
import type { FormEvent, ReactElement, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { WardecBadge } from "../../components/WardecBadge";
import { eveSecurityClass, eveSecurityLabel, isUedamaSystem } from "../../lib/evePresentation";
import { formatDateTime, preferredTimeZone } from "../../lib/time";
import { iskFormatter } from "../../lib/market";
import type { JumpFreighterRoute, NavigationSystem, UedamaScoutStatus } from "../../types/navigation";
import { OperationalMap } from "./OperationalMap";
import { SystemSearchField } from "./RouteChecker";

type JumpFreighterPlannerUser = { timezone?: string };
type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type EveEntityKind = "character" | "corporation" | "alliance";
type EveIconSize = "tiny" | "sm" | "md" | "lg";

type JumpFreighterPlannerProps = {
  currentUser: JumpFreighterPlannerUser;
  api: ApiClient;
  numberFormatter: Intl.NumberFormat;
  Metric: (props: { icon: ReactNode; label: string; value: string | number; delta?: string }) => ReactElement;
  EveEntityIcon: (props: { kind: EveEntityKind; id?: number | null; name?: string | null; size?: EveIconSize }) => ReactElement;
  CharacterHoverName: (props: { characterId?: number | null; name: string; className?: string; href?: string }) => ReactElement;
  UedamaScoutLiveLink: (props: { status: UedamaScoutStatus | null }) => ReactElement | null;
};
export function JumpFreighterPlanner({ currentUser, api, numberFormatter, Metric, EveEntityIcon, CharacterHoverName, UedamaScoutLiveLink }: JumpFreighterPlannerProps) {

  const [origin, setOrigin] = useState("Jita");

  const [destination, setDestination] = useState("Tama");

  const [originOptions, setOriginOptions] = useState<NavigationSystem[]>([]);

  const [destinationOptions, setDestinationOptions] = useState<NavigationSystem[]>([]);

  const [ship, setShip] = useState("Rhea");
  const [killFilter, setKillFilter] = useState("industrial");
  const [jumpActivityHours, setJumpActivityHours] = useState(6);

  const [jdc, setJdc] = useState(5);

  const [jfc, setJfc] = useState(5);

  const [contextHops, setContextHops] = useState(1);

  const [stationSafety, setStationSafety] = useState("any");

  const [avoidSystems, setAvoidSystems] = useState<NavigationSystem[]>([]);

  const [route, setRoute] = useState<JumpFreighterRoute | null>(null);

  const [expandedJump, setExpandedJump] = useState<number | null>(null);

  const [uedamaScout, setUedamaScout] = useState<UedamaScoutStatus | null>(null);

  const [busy, setBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const originSelectionRef = useRef(origin);

  const destinationSelectionRef = useRef(destination);

  const timeZone = preferredTimeZone(currentUser);






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




  function replotWithAvoid(nextAvoidSystems: NavigationSystem[]) {

    if (route) void plotRoute(undefined, nextAvoidSystems);

  }

  function addAvoidSystem(system: NavigationSystem) {

    if (system.system_id === route?.origin.system_id || system.system_id === route?.destination.system_id) {

      setError("Origin and destination cannot be avoided for this route.");

      return;

    }

    setAvoidSystems((current) => {

      if (current.some((entry) => entry.system_id === system.system_id)) return current;

      const next = [...current, system];

      replotWithAvoid(next);

      return next;

    });

  }

  function removeAvoidSystem(systemId: number) {

    setAvoidSystems((current) => {

      const next = current.filter((system) => system.system_id !== systemId);

      replotWithAvoid(next);

      return next;

    });

  }

  function clearAvoidSystems() {

    setAvoidSystems([]);

    replotWithAvoid([]);

  }

  async function plotRoute(event?: FormEvent, overrideAvoidSystems = avoidSystems) {

    event?.preventDefault();

    setBusy(true);

    setError(null);

    setRoute(null);

    setExpandedJump(null);

    try {

      const params = new URLSearchParams({ origin, destination, ship, jump_drive_calibration: String(jdc), jump_fuel_conservation: String(jfc), context_gate_hops: String(contextHops), station_safety: stationSafety, kill_filter: killFilter, jump_activity_hours: String(jumpActivityHours) });

      if (overrideAvoidSystems.length > 0) params.set("avoid_systems", overrideAvoidSystems.map((system) => system.name).join(","));

      setRoute(await api<JumpFreighterRoute>(`/navigation/jump-freighter/route?${params.toString()}`));

    } catch (err) {

      setError(err instanceof Error ? err.message : "Jump-capable route plotting failed");

    } finally {

      setBusy(false);

    }

  }



  useEffect(() => { if (origin.trim() === originSelectionRef.current.trim()) { setOriginOptions([]); return; } const timer = window.setTimeout(() => void searchSystems(origin, setOriginOptions), 180); return () => window.clearTimeout(timer); }, [origin]);

  useEffect(() => { if (destination.trim() === destinationSelectionRef.current.trim()) { setDestinationOptions([]); return; } const timer = window.setTimeout(() => void searchSystems(destination, setDestinationOptions), 180); return () => window.clearTimeout(timer); }, [destination]);



  const capitalRouteScoutKey = route ? [route.origin.system_id, ...route.jumps.map((jump) => jump.to_system.system_id)].join(":") : "";

  const capitalRouteHasUedama = Boolean(route && [route.origin, ...route.jumps.map((jump) => jump.to_system)].some(isUedamaSystem));

  useEffect(() => {
    if (!capitalRouteHasUedama) {
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
  }, [capitalRouteHasUedama, capitalRouteScoutKey]);
  return <section className="panel stacked jf-planner"><div className="section-heading"><div><h3>Jump Capable Ship Plotter</h3><p>Jump-capable ship routes with fuel math, cyno guidance, and 24h kill checks.</p></div>{route && <span className="version-badge">{route.ship.name} · {route.max_range_ly} LY</span>}</div><form className="route-form jf-form" onSubmit={(event) => void plotRoute(event)}><SystemSearchField label="Origin" value={origin} options={originOptions} placeholder="Jita" onChange={(value) => { originSelectionRef.current = ""; setOrigin(value); }} onPick={pickOrigin} /><SystemSearchField label="Cyno destination" value={destination} options={destinationOptions} placeholder="Tama" onChange={(value) => { destinationSelectionRef.current = ""; setDestination(value); }} onPick={pickDestination} /><label>Ship<select value={ship} onChange={(event) => setShip(event.target.value)}><optgroup label="Jump Freighters"><option>Rhea</option><option>Ark</option><option>Anshar</option><option>Nomad</option></optgroup><optgroup label="Black Ops"><option>Redeemer</option><option>Sin</option><option>Widow</option><option>Panther</option><option>Marshal</option></optgroup><optgroup label="Industrial Capital"><option>Rorqual</option></optgroup><optgroup label="Carriers"><option>Archon</option><option>Chimera</option><option>Nidhoggur</option><option>Thanatos</option></optgroup><optgroup label="Command Carriers"><option>Salvation</option><option>Simurgh</option><option>Gaia</option><option>Ymir</option></optgroup><optgroup label="Dreadnoughts"><option>Revelation</option><option>Moros</option><option>Phoenix</option><option>Naglfar</option><option>Chemosh</option><option>Vehement</option><option>Caiman</option><option>Zirnitra</option><option>Sarathiel</option><option>Revelation Navy Issue</option><option>Moros Navy Issue</option><option>Phoenix Navy Issue</option><option>Naglfar Fleet Issue</option></optgroup><optgroup label="Lancer Dreadnoughts"><option>Bane</option><option>Hubris</option><option>Karura</option><option>Valravn</option></optgroup><optgroup label="Force Auxiliaries"><option>Apostle</option><option>Minokawa</option><option>Lif</option><option>Ninazu</option><option>Dagon</option><option>Loggerhead</option></optgroup><optgroup label="Supercarriers"><option>Aeon</option><option>Wyvern</option><option>Hel</option><option>Nyx</option><option>Revenant</option><option>Vendetta</option></optgroup><optgroup label="Titans"><option>Avatar</option><option>Leviathan</option><option>Ragnarok</option><option>Erebus</option><option>Vanquisher</option><option>Molok</option><option>Komodo</option><option>Azariel</option></optgroup></select></label><label>JDC<input type="number" min="0" max="5" value={jdc} onChange={(event) => setJdc(Number(event.target.value))} /></label><label>JFC<input type="number" min="0" max="5" value={jfc} onChange={(event) => setJfc(Number(event.target.value))} /></label><label>Context<select value={contextHops} onChange={(event) => setContextHops(Number(event.target.value))}><option value={0}>Route only</option><option value={1}>1 gate hop</option><option value={2}>2 gate hops</option></select></label><label>Station safety<select value={stationSafety} onChange={(event) => setStationSafety(event.target.value)}><option value="any">Any NPC station</option><option value="avoid_red_only">Avoid red-only</option><option value="green">Only green stations</option></select></label><label className="checkbox-row"><input type="checkbox" checked={killFilter === "industrial"} onChange={(event) => setKillFilter(event.target.checked ? "industrial" : "all")} /> Industrial kills only</label><label>Observed activity<select value={jumpActivityHours} onChange={(event) => setJumpActivityHours(Number(event.target.value))}>{[1, 3, 6, 9, 12, 15, 18, 21, 24].map((hours) => <option key={hours} value={hours}>{hours}h</option>)}</select></label><button type="submit" disabled={busy || !origin.trim() || !destination.trim()}><MapIcon size={18} /> {busy ? "Plotting" : "Plot jump route"}</button></form>{avoidSystems.length > 0 && <div className="avoid-list-panel"><div><strong>Avoiding</strong><span>{avoidSystems.length} system{avoidSystems.length === 1 ? "" : "s"}</span></div><div className="avoid-chip-row">{avoidSystems.map((system) => <button type="button" key={system.system_id} className={`avoid-chip ${eveSecurityClass(system.security_status)}`} onClick={() => removeAvoidSystem(system.system_id)}>{system.name} x</button>)}<button type="button" className="avoid-clear" onClick={clearAvoidSystems}>Clear avoid list</button></div></div>}{error && <div className="mini-alert">{error}</div>}{route && <><div className="gatecheck-summary"><Metric icon={<MapIcon size={18} />} label="Jumps" value={route.jump_count} delta={`${route.total_distance_ly} LY`} /><Metric icon={<Database size={18} />} label="Fuel" value={numberFormatter.format(route.total_fuel_units)} delta={route.ship.fuel_type_name} /><Metric icon={<Activity size={18} />} label="Range" value={`${route.max_range_ly} LY`} delta={`${route.ship.ship_class ?? "Capital"} · JDC ${route.skills.jump_drive_calibration}`} /><Metric icon={<Factory size={18} />} label="Fuel skill" value={`JFC ${route.skills.jump_fuel_conservation}`} delta={`${numberFormatter.format(route.ship.base_fuel_per_light_year)}/LY base`} /><Metric icon={<Factory size={18} />} label="Station safety" value={route.station_safety?.label ?? "Any NPC station"} delta="cyno target filter" /><Metric icon={<Activity size={18} />} label="Kill display" value={route.kill_filter?.label ?? "Industrial kills only"} delta="24h cached samples" /><Metric icon={<Activity size={18} />} label={`Observed Activity (${route.jump_activity?.hours ?? jumpActivityHours}h)`} value={route.jump_activity?.cache?.refreshed ? "refreshed" : "cached"} delta="hourly ESI samples" /></div><div className="jf-notes">{route.notes.map((note) => <span key={note}>{note}</span>)}</div><OperationalMap title="Operational Map" subtitle={`${route.origin.name} to ${route.destination.name} · ${route.jump_count.toLocaleString()} jumps`} badge={`${route.total_distance_ly} LY`} routeSystems={[route.origin, ...route.jumps.map((jump) => jump.to_system)].map((system, index) => ({ ...system, map_index: index, label: `${index}. ${system.name}`, meta: `${system.region_name ?? "Unknown region"} · ${eveSecurityLabel(system.security_status)}`, selected_key: index > 0 ? String(route.jumps[index - 1].jump_index) : null, segment_label: index > 0 ? `${route.jumps[index - 1].distance_ly} LY` : null }))} mapContext={route.map_context} selectedKey={expandedJump ? String(expandedJump) : null} onSelectRouteSystem={(key) => setExpandedJump(key ? Number(key) : null)} /><div className="jf-jump-list">{route.jumps.map((jump) => { const expanded = expandedJump === jump.jump_index; return <article key={jump.jump_index} className="jf-jump"><button type="button" onClick={() => setExpandedJump(expanded ? null : jump.jump_index)}><span className="route-index">{jump.jump_index}</span><strong>{jump.from_system.name} to {jump.to_system.name}</strong><span>{jump.distance_ly} LY · {numberFormatter.format(jump.fuel_units)} {route.ship.fuel_type_name}</span><span className={`security-badge ${eveSecurityClass(jump.to_system.security_status)}`}>{eveSecurityLabel(jump.to_system.security_status)}</span><span className={`risk-badge risk-${(jump.kills_24h ?? jump.industrial_kills_24h).count > 0 ? "active" : "quiet"}`}>{(jump.kills_24h ?? jump.industrial_kills_24h).count} {route.kill_filter?.mode === "all" ? "kills" : "industrial kills"} / 24h</span>{jump.jump_activity && <span className={`intel-badge intel-${(jump.jump_activity.activity_label ?? "unknown").replace(/\s+/g, "-").toLowerCase()}`} title={`Observed Activity (${jump.jump_activity.hours}h): ${jump.jump_activity.total_jumps.toLocaleString()} jumps, ${jump.jump_activity.jumps_per_hour.toLocaleString()} jumps/hr, confidence ${jump.jump_activity.confidence} from ${jump.jump_activity.observations} observations`}>{jump.jump_activity.activity_label} · {jump.jump_activity.total_jumps.toLocaleString()} jumps / {jump.jump_activity.hours}h · {jump.jump_activity.confidence}</span>}</button><div className="jf-jump-actions">{isUedamaSystem(jump.to_system) && <UedamaScoutLiveLink status={uedamaScout} />}<button type="button" disabled={jump.to_system.system_id === route.destination.system_id || avoidSystems.some((system) => system.system_id === jump.to_system.system_id)} onClick={() => addAvoidSystem(jump.to_system)}>{jump.to_system.system_id === route.destination.system_id ? "Destination" : avoidSystems.some((system) => system.system_id === jump.to_system.system_id) ? "Avoiding" : `Avoid ${jump.to_system.name}`}</button></div>{expanded && <div className="jf-jump-detail"><section><h4>Stations in {jump.to_system.name}</h4>{jump.stations.length > 0 ? <div className="jf-stations">{jump.stations.map((station) => <div key={station.station_id} className={`station-risk station-${station.cyno_guidance.risk}`}><strong>{station.name}</strong><span>{station.type_name ?? "Unknown station type"}</span><span>{station.operation_name ?? "Unknown operation"}</span><span>{station.cyno_guidance.range_km ? `${station.cyno_guidance.range_km} km docking guide` : "No docking range guide"}</span><small>{station.cyno_guidance.note}</small>{station.cyno_guidance.reference_links?.length ? <div className="cyno-reference-links">{station.cyno_guidance.reference_links.map((link) => <a key={link.url} href={link.url} target="_blank" rel="noreferrer">{link.label}</a>)}</div> : null}</div>)}</div> : <p className="empty">No NPC stations imported for this target system yet.</p>}</section><section><h4>{route.kill_filter?.mode === "all" ? "All kills" : "Industrial kills"}, last 24h</h4>{(jump.kills_24h ?? jump.industrial_kills_24h).sample_killmails.length > 0 ? <div className="killmail-detail-list jf-kills">{(jump.kills_24h ?? jump.industrial_kills_24h).sample_killmails.map((kill) => <article key={kill.killmail_id}><div><strong>{kill.victim_hull ?? "Unknown hull"}</strong>{kill.smartbomb_used && <span className="smartbomb-badge">Smartbombs</span>}{kill.is_wardec && <WardecBadge />}<span className="killmail-entity-line"><EveEntityIcon kind="character" id={kill.victim_character_id} name={kill.victim_character_name} size="tiny" /><CharacterHoverName characterId={kill.victim_character_id} name={kill.victim_character_name ?? "Unknown pilot"} href={kill.victim_character_id ? `https://zkillboard.com/character/${kill.victim_character_id}/` : undefined} />{kill.victim_corporation_id && <EveEntityIcon kind="corporation" id={kill.victim_corporation_id} name={kill.victim_corporation_name} size="tiny" />}{kill.victim_corporation_name ? ` · ${kill.victim_corporation_name}` : ""}{kill.victim_alliance_id && <EveEntityIcon kind="alliance" id={kill.victim_alliance_id} name={kill.victim_alliance_name} size="tiny" />}{kill.victim_alliance_name ? ` · ${kill.victim_alliance_name}` : ""}</span><span>{kill.location_kind ?? "space"} · {kill.location_name ?? "Unknown location"}</span>{kill.killmail_time && <span>{formatDateTime(kill.killmail_time, timeZone)}</span>}</div><div><span>{kill.attacker_count ?? "?"} attackers</span><span className="killmail-entity-line"><EveEntityIcon kind="character" id={kill.final_blow_character_id} name={kill.final_blow_character_name} size="tiny" />Final blow: {kill.final_blow_ship_type_name ?? "Unknown ship"} · <CharacterHoverName characterId={kill.final_blow_character_id} name={kill.final_blow_character_name ?? "Unknown pilot"} href={kill.final_blow_character_id ? `https://zkillboard.com/character/${kill.final_blow_character_id}/` : undefined} />{kill.final_blow_corporation_id && <EveEntityIcon kind="corporation" id={kill.final_blow_corporation_id} name={kill.final_blow_corporation_name} size="tiny" />}{kill.final_blow_corporation_name ? ` · ${kill.final_blow_corporation_name}` : ""}{kill.final_blow_alliance_id && <EveEntityIcon kind="alliance" id={kill.final_blow_alliance_id} name={kill.final_blow_alliance_name} size="tiny" />}{kill.final_blow_alliance_name ? ` · ${kill.final_blow_alliance_name}` : ""}</span>{kill.zkb_url && <a href={kill.zkb_url} target="_blank" rel="noreferrer">Open killmail #{kill.killmail_id}</a>}</div></article>)}</div> : <p className="empty">No cached {route.kill_filter?.mode === "all" ? "kills" : "industrial kills"} in the last 24 hours.</p>}</section></div>}</article>; })}</div><section className="station-guide"><h4>Station Cyno Risk Reference</h4><p>EQM-rendered reference from pilot-provided station docking/cyno guidance. Use it as planning support, not a replacement for practiced bookmarks.</p><div>{route.station_cyno_guide.map((row) => <span key={row.station_type} className={`station-risk station-${row.risk}`}><strong>{row.station_type}</strong><small>{row.range_km ?? "?"} km · {row.risk}</small></span>)}</div></section></>}</section>;

}

