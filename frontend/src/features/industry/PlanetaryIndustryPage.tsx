import { AlertTriangle, ChevronDown, Factory, Globe2, RefreshCw, Timer, Warehouse } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type {
  CharacterSyncJob,
  PlanetaryColony,
  PlanetaryIndustryPayload,
  PlanetaryPin,
} from "../../types/planetaryIndustry";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type EsiAuthInfo = { ready: boolean; url?: string; message?: string; required_scopes: string[] };

const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

function securityLabel(value?: number | null) {
  return value == null ? "?" : value.toFixed(1);
}

function duration(seconds?: number | null) {
  if (!seconds) return "Not reported";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  return `${hours ? `${hours}h ` : ""}${minutes}m`;
}

function expiryLabel(value?: string | null) {
  if (!value) return "No expiry";
  const milliseconds = new Date(value).getTime() - Date.now();
  if (milliseconds <= 0) return "Expired";
  const hours = Math.ceil(milliseconds / 3_600_000);
  return hours >= 24 ? `${Math.floor(hours / 24)}d ${hours % 24}h` : `${hours}h`;
}

export function PlanetaryIndustryPage({
  api,
  formatDateTime,
}: {
  api: ApiClient;
  formatDateTime: (value?: string | null) => string;
}) {
  const [data, setData] = useState<PlanetaryIndustryPayload | null>(null);
  const [character, setCharacter] = useState("all");
  const [system, setSystem] = useState("all");
  const [planetType, setPlanetType] = useState("all");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [syncJob, setSyncJob] = useState<CharacterSyncJob | null>(null);
  const [authInfo, setAuthInfo] = useState<EsiAuthInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    setData(await api<PlanetaryIndustryPayload>("/planetary-industry"));
  }

  async function syncAll() {
    setBusy(true);
    setError(null);
    try {
      let job = await api<CharacterSyncJob>("/esi/sync/characters/all?sync_kind=planets", {
        method: "POST",
        body: "{}",
      });
      setSyncJob(job);
      while (job.status === "queued" || job.status === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 900));
        job = await api<CharacterSyncJob>(`/esi/sync/characters/all/${job.job_id}`);
        setSyncJob(job);
      }
      await load();
      if (job.failed_count) setError(job.errors.join(" · "));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Planetary Industry sync failed");
    } finally {
      setBusy(false);
    }
  }

  async function syncCharacter(tokenId: number) {
    setBusy(true);
    setError(null);
    try {
      let job = await api<CharacterSyncJob>(`/planetary-industry/sync/${tokenId}`, { method: "POST", body: "{}" });
      setSyncJob(job);
      while (job.status === "queued" || job.status === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 900));
        job = await api<CharacterSyncJob>(`/planetary-industry/sync/jobs/${job.job_id}`);
        setSyncJob(job);
      }
      await load();
      if (job.failed_count) setError(job.errors.join(" · "));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Character PI sync failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const refreshProjection = () => void load().catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load Planetary Industry"));
    refreshProjection();
    void api<EsiAuthInfo>("/esi/auth-url?scope_group=planetary").then(setAuthInfo).catch(() => undefined);
    const projectionTimer = window.setInterval(refreshProjection, 30_000);
    return () => window.clearInterval(projectionTimer);
  }, []);

  const systems = useMemo(
    () => [...new Set((data?.colonies ?? []).map((row) => row.solar_system_name).filter(Boolean))].sort(),
    [data],
  );
  const planetTypes = useMemo(
    () => [...new Set((data?.colonies ?? []).map((row) => row.planet_type).filter(Boolean))].sort(),
    [data],
  );
  const colonies = useMemo(
    () => (data?.colonies ?? []).filter((row) => (
      (character === "all" || row.character_id === Number(character))
      && (system === "all" || row.solar_system_name === system)
      && (planetType === "all" || row.planet_type === planetType)
    )),
    [data, character, system, planetType],
  );
  const eligible = data?.sync_tokens.filter((token) => token.can_sync && token.has_scope).length ?? 0;
  const missingScope = data?.sync_tokens.filter((token) => token.can_sync && !token.has_scope) ?? [];
  const syncPercent = syncJob?.total_count
    ? Math.round(syncJob.processed_count / syncJob.total_count * 100)
    : 0;

  return <section className="panel stacked planetary-page">
    <div className="section-heading">
      <div><h3>Planetary Industry</h3><p>Colony layouts, extractor cycles, routed production, storage, and factory health from ESI.</p></div>
      <div className="button-row compact">
        <button type="button" disabled={busy || eligible === 0} onClick={() => void syncAll()}><RefreshCw size={16} />{busy ? "Syncing" : "Sync all eligible"}</button>
        <button type="button" disabled={busy} onClick={() => void load()}><RefreshCw size={16} />Refresh</button>
      </div>
    </div>
    <div className="privacy-placard planetary-freshness">
      <Timer size={18} />
      <span><strong>Live PI projection:</strong> EQM advances extractor cycles, factory jobs, routed materials, and storage capacity from the last ESI checkpoint to now. The projection refreshes every 30 seconds without contacting ESI. Manual transfers, expedited routes, and colony edits remain unknown until ESI publishes a newer checkpoint; visiting the planet in space and submitting a change may prompt that update.</span>
    </div>
    {error && <div className="mini-alert">{error}</div>}
    {missingScope.length > 0 && <div className="notice warning planetary-reauth">
      <AlertTriangle size={17} />
      <span>{missingScope.map((row) => row.character_name).join(", ")} must reauthorize ESI before PI can sync. Choose each affected character on CCP's authorization screen.</span>
      {authInfo?.ready && authInfo.url
        ? <a className="mini-link" href={authInfo.url}>Reauthorize for PI</a>
        : <small>{authInfo?.message ?? "Preparing planetary authorization..."}</small>}
    </div>}
    {syncJob && <div className={`research-sync-status ${syncJob.failed_count ? "has-errors" : ""}`}>
      <div><strong>{syncJob.processed_count} / {syncJob.total_count}</strong><span>{syncJob.current_character_name ? `Syncing ${syncJob.current_character_name}` : syncJob.status === "complete" ? "PI sync complete" : syncJob.status === "failed" ? "PI sync needs review" : "PI sync queued"}</span></div>
      <progress max={100} value={syncPercent} />
      <small>{syncJob.success_count} synced · {syncJob.failed_count} failed · {syncJob.skipped_count} skipped</small>
    </div>}
    <div className="status-grid planetary-summary-grid">
      <article><Globe2 size={19} /><span>Colonies</span><strong>{data?.summary.colonies ?? 0}</strong></article>
      <article><Timer size={19} /><span>Extractor attention</span><strong>{(data?.summary.expired_extractors ?? 0) + (data?.summary.expiring_extractors ?? 0)}</strong></article>
      <article><Factory size={19} /><span>Factory attention</span><strong>{data?.summary.starved_factories ?? 0}</strong></article>
      <article><Warehouse size={19} /><span>Projected volume</span><strong>{number.format(data?.summary.stored_volume ?? 0)} m3</strong></article>
    </div>
    <div className="planetary-controls">
      <label>Character<select value={character} onChange={(event) => setCharacter(event.target.value)}><option value="all">All characters</option>{data?.characters.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label>System<select value={system} onChange={(event) => setSystem(event.target.value)}><option value="all">All systems</option>{systems.map((value) => <option key={value} value={value!}>{value}</option>)}</select></label>
      <label>Planet type<select value={planetType} onChange={(event) => setPlanetType(event.target.value)}><option value="all">All types</option>{planetTypes.map((value) => <option key={value} value={value!}>{value}</option>)}</select></label>
    </div>
    <div className="planetary-token-row">
      {data?.sync_tokens.map((token) => <button type="button" key={token.token_id} disabled={busy || !token.can_sync || !token.has_scope} onClick={() => void syncCharacter(token.token_id)} title={!token.has_scope ? "Reauthorize ESI to grant the PI scope" : `Sync ${token.character_name}`}>{token.character_name}<small>{token.has_scope ? "PI ready" : "Reauth required"}</small></button>)}
    </div>
    <div className="planetary-colony-list">
      {colonies.map((colony) => <ColonyRow key={colony.id} colony={colony} expanded={expanded === colony.id} onToggle={() => setExpanded(expanded === colony.id ? null : colony.id)} formatDateTime={formatDateTime} />)}
      {data && colonies.length === 0 && <p className="empty">No colonies match these filters.</p>}
      {!data && !error && <p className="empty">Loading planetary colonies...</p>}
    </div>
  </section>;
}

function ColonyRow({
  colony,
  expanded,
  onToggle,
  formatDateTime,
}: {
  colony: PlanetaryColony;
  expanded: boolean;
  onToggle: () => void;
  formatDateTime: (value?: string | null) => string;
}) {
  const attention = colony.summary.expired_extractors + colony.summary.expiring_extractors + colony.summary.starved_factories;
  return <article className={`planetary-colony ${attention ? "needs-attention" : ""}`}>
    <button type="button" className="planetary-colony-heading" onClick={onToggle}>
      <img src={colony.character_portrait_url || `https://images.evetech.net/characters/${colony.character_eve_id}/portrait?size=64`} alt="" />
      <span><strong>{colony.planet_name}</strong><small>{colony.solar_system_name ?? `System ${colony.solar_system_id ?? "unknown"}`} · Sec {securityLabel(colony.security_status)} · {colony.planet_type ?? "Unknown type"}</small></span>
      <span><b>{colony.character_name}</b><small>Command Center {colony.upgrade_level}</small></span>
      <span><b>{colony.num_pins} pins</b><small>{colony.link_count} links · {colony.route_count} routes</small></span>
      <span className={attention ? "planetary-attention" : "planetary-healthy"}><b>{attention ? `${attention} alerts` : "Healthy"}</b><small>Projected {formatDateTime(colony.projection.projected_at)} · ESI {formatDateTime(colony.projection.checkpoint_at)}</small></span>
      <ChevronDown size={18} className={expanded ? "rotated" : ""} />
    </button>
    {expanded && <div className="planetary-colony-detail">
      <div className="planetary-projection-note">
        <Timer size={16} />
        <span><strong>{colony.projection.is_projection ? "Calculated to now" : "Observed inventory"}</strong> from ESI checkpoint {formatDateTime(colony.projection.checkpoint_at)} · {number.format(colony.projection.events_processed)} production events simulated</span>
      </div>
      {colony.projection.warning && <div className="notice warning planetary-projection-warning"><AlertTriangle size={16} /><span>{colony.projection.warning}</span></div>}
      <div className="planetary-detail-summary">
        <span><b>{colony.summary.extractors}</b> extractors</span>
        <span><b>{colony.summary.factories}</b> factories</span>
        <span><b>{number.format(colony.summary.stored_volume)} m3</b> projected</span>
        <span><b>{number.format(colony.summary.observed_stored_volume)} m3</b> ESI observed</span>
        <span><b>{number.format(colony.summary.projected_daily_output)}</b> projected units/day</span>
      </div>
      <div className="table-wrap"><table className="planetary-pin-table">
        <thead><tr><th>Installation</th><th>Projected role / status</th><th>Projected product or contents</th><th>Cycle / expiry</th><th>Routing</th></tr></thead>
        <tbody>{colony.pins.map((pin) => <PinRow key={pin.pin_id} pin={pin} />)}</tbody>
      </table></div>
    </div>}
  </article>;
}

function contentText(contents: PlanetaryPin["contents"]) {
  return contents.length
    ? contents.map((item) => `${item.name} x${number.format(item.amount)}`).join(" · ")
    : "Empty";
}

function contentsDiffer(pin: PlanetaryPin) {
  const projected = new Map(pin.contents.map((item) => [item.type_id, item.amount]));
  const observed = new Map(pin.observed_contents.map((item) => [item.type_id, item.amount]));
  return projected.size !== observed.size || [...projected].some(([typeId, amount]) => observed.get(typeId) !== amount);
}

function PinRow({ pin }: { pin: PlanetaryPin }) {
  const contents = contentText(pin.contents);
  const observedContents = contentText(pin.observed_contents);
  const role = pin.is_extractor ? "Extractor" : pin.is_factory ? "Factory" : pin.contents.length || pin.observed_contents.length ? "Storage" : "Infrastructure";
  const status = pin.projected_status;
  const routing = pin.is_factory && status === "blocked"
    ? "Output storage full"
    : pin.is_factory && status === "starved"
      ? "Waiting for routed inputs"
      : pin.has_inbound_route
        ? "Inbound route active"
        : pin.is_factory
          ? "No inbound route"
          : "No inbound material";
  const warning = status === "expired" || status === "starved" || status === "blocked" || status === "full";
  const changed = contentsDiffer(pin);
  return <tr className={warning ? "pin-warning" : ""}>
    <td><strong>{pin.type_name}</strong><span>Pin {pin.pin_id}</span></td>
    <td><span className={`planetary-status status-${status}`}>{role} · {status}</span>{pin.schematic && <small>{pin.schematic.name}</small>}{pin.schematic_id && !pin.schematic && <small>Schematic {pin.schematic_id}</small>}</td>
    <td>{pin.extractor ? <><strong>{pin.extractor.product_name ?? "Unknown product"}</strong><span>{number.format(pin.extractor.projected_daily_output)} units/day projected</span><small>{contents}{pin.stored_volume > 0 ? ` · ${number.format(pin.stored_volume)} m3 projected` : ""}</small><small>{number.format(pin.extractor.projected_remaining_output)} remaining · {number.format(pin.extractor.projected_program_output)} full program · {pin.extractor.projection_source === "dogma" ? "SDE Dogma" : "CCP defaults"}</small></> : pin.schematic ? <><strong>{pin.schematic.output.name} x{number.format(pin.schematic.output.quantity)} / cycle</strong><span>{pin.schematic.inputs.map((item) => `${item.name} x${number.format(item.quantity)}`).join(" + ")}</span><small>{contents}{pin.stored_volume > 0 ? ` · ${number.format(pin.stored_volume)} m3 projected` : ""}</small></> : <><span>{contents}</span>{pin.stored_volume > 0 && <small>{number.format(pin.stored_volume)} m3 projected</small>}</>}{changed && <small className="planetary-observed">ESI observed: {observedContents}{pin.observed_stored_volume > 0 ? ` · ${number.format(pin.observed_stored_volume)} m3` : ""}</small>}{pin.projected_blocked.length > 0 && <small className="text-danger">Unrouted/full: {contentText(pin.projected_blocked)}</small>}</td>
    <td>{pin.extractor ? <><strong>{duration(pin.extractor.cycle_time)} cycle</strong><span>{expiryLabel(pin.expiry_time)} remaining · {pin.extractor.head_count} heads</span></> : pin.schematic ? <><strong>{duration(pin.schematic.cycle_time)} cycle</strong><span>{status === "running" ? "Production active" : status === "starved" ? "Inputs unavailable" : status === "blocked" ? "Output blocked" : "Idle"}</span></> : <span>Not cyclical</span>}</td>
    <td><span className={warning ? "text-danger" : ""}>{routing}</span></td>
  </tr>;
}