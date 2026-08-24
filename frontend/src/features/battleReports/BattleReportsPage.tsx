import { AlertTriangle, ChevronLeft, ChevronRight, Clipboard, ExternalLink, Pencil, RefreshCw, RotateCcw, Share2, Swords, Trash2, UsersRound } from "lucide-react";
import { useEffect, useMemo, useState, type DragEvent } from "react";

import type {
  BattleReport,
  BattleReportComposition,
  BattleReportContext,
  BattleReportHistoryEntry,
  BattleReportHistoryPayload,
  BattleReportParticipant,
  BattleReportPayload,
  BattleReportShare,
  BattleReportTeam,
} from "../../types/battleReports";
import "./battleReports.css";
import "./battleReportMedia.css";
import "./publicBattleReport.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type ReportTab = "involved" | "summary" | "timeline" | "damage" | "composition";
type BattleSide = 0 | 1 | 2;
type SideOverrides = Record<number, BattleSide>;
type OrganizationKind = "alliance" | "corporation";
type OrganizationOverride = { organization_type: OrganizationKind; organization_id: number; side: BattleSide };
type OrganizationOverrides = Record<string, OrganizationOverride>;
type BattleSourceSync = { job_id: string; status: string; target_count: number; target_index: number; message?: string | null };

const activeSyncStatuses = new Set(["queued", "running"]);

const tabs: { id: ReportTab; label: string }[] = [
  { id: "involved", label: "Involved" },
  { id: "summary", label: "Summary" },
  { id: "timeline", label: "Timeline" },
  { id: "damage", label: "Damage" },
  { id: "composition", label: "Composition" },
];

export function compactIsk(value?: number | null): string {
  if (value === null || value === undefined) return "Unknown";
  const absolute = Math.abs(value);
  const divisor = absolute >= 1e12 ? 1e12 : absolute >= 1e9 ? 1e9 : absolute >= 1e6 ? 1e6 : 1;
  const suffix = divisor === 1e12 ? "T" : divisor === 1e9 ? "B" : divisor === 1e6 ? "M" : "";
  return `${(value / divisor).toLocaleString(undefined, { maximumFractionDigits: 2 })}${suffix} ISK`;
}

export function duration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

function sideLabel(report: BattleReport, side: number): string {
  return report.teams.find((team) => team.side === side)?.label ?? "Third parties / ambiguous";
}

export function zkillCharacterUrl(characterId: number): string {
  return `https://zkillboard.com/character/${characterId}/`;
}

function imageUrl(kind: "character" | "corporation" | "alliance" | "type", id: number, size = 64): string {
  const segment = kind === "character" ? "characters" : kind === "corporation" ? "corporations" : kind === "alliance" ? "alliances" : "types";
  const variant = kind === "character" ? "portrait" : kind === "type" ? "render" : "logo";
  return `https://images.evetech.net/${segment}/${id}/${variant}?size=${size}`;
}

export function EveImage({ kind, id, name, className }: { kind: "character" | "corporation" | "alliance" | "type"; id?: number | null; name: string; className: string }) {
  if (!id) return <span className={`${className} battle-image-fallback`} aria-hidden="true">?</span>;
  return <img className={className} src={imageUrl(kind, id)} alt={`${name} ${kind === "type" ? "ship" : kind} image`} loading="lazy" onError={(event) => { event.currentTarget.style.display = "none"; }} />;
}

export function TeamCard({ team }: { team: BattleReportTeam }) {
  return <article className={`battle-team side-${team.side}`}>
    <div className="battle-team-heading"><h3>{team.label}</h3><strong>{team.efficiency === null || team.efficiency === undefined ? "—" : `${team.efficiency.toFixed(1)}%`} efficiency</strong></div>
    <div className="battle-team-kpis">
      <span><strong>{team.pilot_count}</strong> pilots</span>
      <span><strong>{compactIsk(team.isk_lost)}</strong> lost</span>
      <span><strong>{team.ships_lost}</strong> ships lost</span>
      <span><strong>{team.damage_inflicted.toLocaleString()}</strong> damage</span>
    </div>
    {team.unknown_value_losses > 0 && <small>{team.unknown_value_losses} loss value{team.unknown_value_losses === 1 ? "" : "s"} unknown</small>}
    <div className="battle-orgs">{team.organizations.map((organization) => <span key={`${organization.organization_type ?? "organization"}:${organization.organization_id ?? organization.name}`}><EveImage kind={organization.organization_type ?? "corporation"} id={organization.organization_id} name={organization.name} className="battle-org-logo" />{organization.name} <b>{organization.pilot_count}</b></span>)}</div>
  </article>;
}

function organizationKey(kind: OrganizationKind, id: number): string {
  return `${kind}:${id}`;
}

function TeamOrganizationEditor({ report, overrides, onSideChange }: {
  report: BattleReport;
  overrides: OrganizationOverrides;
  onSideChange: (kind: OrganizationKind, organizationId: number, side: BattleSide) => void;
}) {
  const organizations = useMemo(() => {
    const grouped = new Map<string, { kind: OrganizationKind; id: number; name: string; memberCount: number; sides: Map<number, number> }>();
    for (const pilot of report.participants) {
      const identities: { kind: OrganizationKind; id?: number | null; name?: string | null }[] = [
        { kind: "alliance", id: pilot.alliance_id, name: pilot.alliance_name },
        { kind: "corporation", id: pilot.corporation_id, name: pilot.corporation_name },
      ];
      for (const identity of identities) {
        if (!identity.id || !identity.name) continue;
        const key = organizationKey(identity.kind, identity.id);
        const row = grouped.get(key) ?? { kind: identity.kind, id: identity.id, name: identity.name, memberCount: 0, sides: new Map<number, number>() };
        row.memberCount += 1;
        row.sides.set(pilot.side, (row.sides.get(pilot.side) ?? 0) + 1);
        grouped.set(key, row);
      }
    }
    return [...grouped.entries()].map(([key, row]) => ({
      ...row,
      side: overrides[key]?.side ?? ([...row.sides.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? 2) as BattleSide,
    })).sort((left, right) => left.name.localeCompare(right.name));
  }, [report.participants, overrides]);
  const labels = ["Selected pilot's side", "Opposing side", "Third parties / ambiguous"];

  function dropOrganization(event: DragEvent<HTMLElement>, side: BattleSide) {
    event.preventDefault();
    try {
      const organization = JSON.parse(event.dataTransfer.getData("application/x-eqm-organization")) as { kind: OrganizationKind; id: number };
      if ((organization.kind === "alliance" || organization.kind === "corporation") && organization.id > 0) onSideChange(organization.kind, organization.id, side);
    } catch { /* Ignore unrelated drag payloads. */ }
  }

  return <div className="battle-organization-editor" aria-label="Organization team classification">
    {([0, 1, 2] as BattleSide[]).map((side) => <section key={side} className={`battle-org-dropzone side-${side}`} onDragOver={(event) => event.preventDefault()} onDrop={(event) => dropOrganization(event, side)}>
      <h4>{labels[side]}</h4>
      <div className="battle-org-drag-list">{organizations.filter((organization) => organization.side === side).map((organization) => <div className="battle-org-drag-chip" key={organizationKey(organization.kind, organization.id)} draggable onDragStart={(event) => { event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("application/x-eqm-organization", JSON.stringify({ kind: organization.kind, id: organization.id })); }}>
        <EveImage kind={organization.kind} id={organization.id} name={organization.name} className="battle-org-logo" />
        <span><strong>{organization.name}</strong><small>{organization.kind} · {organization.memberCount} pilot{organization.memberCount === 1 ? "" : "s"}</small></span>
        <select value={organization.side} aria-label={`Move ${organization.name} to team`} onChange={(event) => onSideChange(organization.kind, organization.id, Number(event.target.value) as BattleSide)}><option value={0}>Pilot</option><option value={1}>Opposing</option><option value={2}>Third party</option></select>
      </div>)}</div>
      {!organizations.some((organization) => organization.side === side) && <small>Drop an alliance or corporation here.</small>}
    </section>)}
  </div>;
}

export function PilotTable({ report, rows, editable = false, selectedPilotId, onSideChange }: {
  report: BattleReport;
  rows: BattleReportParticipant[];
  editable?: boolean;
  selectedPilotId?: number | null;
  onSideChange?: (characterId: number, side: BattleSide) => void;
}) {
  return <div className="battle-table-wrap"><table className="battle-table">
    <thead><tr><th>Pilot</th><th>Team</th><th>Ships</th><th>Damage</th><th>Kills / final blows</th><th>Losses</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={row.character_id} className={`side-${row.side}`}>
      <td><div className="battle-pilot-cell"><EveImage kind="character" id={row.character_id} name={row.character_name} className="battle-pilot-portrait" /><span><a className="battle-pilot-link" href={zkillCharacterUrl(row.character_id)} target="_blank" rel="noreferrer"><strong>{row.character_name}</strong><ExternalLink size={13} aria-hidden="true" /></a><span className="battle-affiliations">{row.corporation_name && <span><EveImage kind="corporation" id={row.corporation_id} name={row.corporation_name} className="battle-affiliation-logo" />{row.corporation_name}</span>}{row.alliance_name && <span><EveImage kind="alliance" id={row.alliance_id} name={row.alliance_name} className="battle-affiliation-logo" />{row.alliance_name}</span>}{!row.corporation_name && !row.alliance_name && <small>No resolved organization</small>}</span></span></div></td>
      <td>{editable && row.character_id !== selectedPilotId ? <select className="battle-side-select" value={row.side} aria-label={`Classify ${row.character_name}`} onChange={(event) => onSideChange?.(row.character_id, Number(event.target.value) as BattleSide)}><option value={0}>Pilot's side</option><option value={1}>Opposing side</option><option value={2}>Third party / ambiguous</option></select> : <>{sideLabel(report, row.side)}{editable && row.character_id === selectedPilotId && <small>Selected pilot anchor</small>}</>}</td>
      <td><div className="battle-ship-list">{row.ships?.length ? row.ships.map((ship) => <span key={ship.type_id}><EveImage kind="type" id={ship.type_id} name={ship.type_name} className="battle-ship-thumb" /><span>{ship.type_name}<small>{ship.ship_group_name ?? "Class unresolved"}</small></span></span>) : row.ship_type_names.join(", ") || "Unknown hull"}</div></td>
      <td>{row.damage_done.toLocaleString()}<small>{row.damage_taken.toLocaleString()} taken</small></td>
      <td>{row.killmail_participations} / {row.final_blows}</td>
      <td>{row.losses}<small>{compactIsk(row.loss_value)}</small></td>
    </tr>)}</tbody>
  </table></div>;
}

export function CompositionTable({ report, rows }: { report: BattleReport; rows: BattleReportComposition[] }) {
  return <div className="battle-table-wrap"><table className="battle-table">
    <thead><tr><th>Hull</th><th>Class</th><th>Team</th><th>Pilots</th><th>Appearances</th><th>Lost</th><th>Loss value</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={`${row.side}:${row.ship_type_id}`} className={`side-${row.side}`}><td><span className="battle-hull-cell"><EveImage kind="type" id={row.ship_type_id} name={row.ship_type_name} className="battle-ship-portrait" /><strong>{row.ship_type_name}</strong></span></td><td>{row.ship_group_name ?? "Unresolved class"}</td><td>{sideLabel(report, row.side)}</td><td>{row.pilots}</td><td>{row.involved}</td><td>{row.lost}</td><td>{compactIsk(row.loss_value)}</td></tr>)}</tbody>
  </table></div>;
}

export function BattleReportsPage({ api }: { api: ApiClient }) {
  const [context, setContext] = useState<BattleReportContext | null>(null);
  const [pilotId, setPilotId] = useState<number | null>(null);
  const [gapMinutes, setGapMinutes] = useState(15);
  const [history, setHistory] = useState<BattleReportHistoryPayload | null>(null);
  const [selectedSeedId, setSelectedSeedId] = useState<number | null>(null);
  const [payload, setPayload] = useState<BattleReportPayload | null>(null);
  const [tab, setTab] = useState<ReportTab>("involved");
  const [sourceSync, setSourceSync] = useState<BattleSourceSync | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shares, setShares] = useState<BattleReportShare[]>([]);
  const [shareBusy, setShareBusy] = useState(false);
  const [shareNotice, setShareNotice] = useState<string | null>(null);
  const [editingTeams, setEditingTeams] = useState(false);
  const [sideOverrides, setSideOverrides] = useState<SideOverrides>({});
  const [organizationOverrides, setOrganizationOverrides] = useState<OrganizationOverrides>({});

  useEffect(() => {
    setLoading(true);
    api<BattleReportContext>("/battle-reports/context").then((next) => {
      setContext(next);
      setGapMinutes(next.default_gap_minutes);
      setPilotId((current) => current && next.pilots.some((pilot) => pilot.character_id === current) ? current : next.pilots[0]?.character_id ?? null);
      if (next.enabled && next.can_sync) {
        void api<{ sync: BattleSourceSync }>("/killboard/sync/ensure", { method: "POST", body: "{}" }).then((result) => setSourceSync(result.sync)).catch(() => undefined);
      }
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Battle Reports context failed"))
      .finally(() => setLoading(false));
  }, []);

  async function loadReport(selectedPilot = pilotId, selectedGap = gapMinutes, seedId = selectedSeedId, overrides: SideOverrides = sideOverrides, orgOverrides: OrganizationOverrides = organizationOverrides) {
    if (!selectedPilot) return;
    setLoading(true); setError(null);
    try {
      setPayload(await api<BattleReportPayload>("/battle-reports/render", { method: "POST", body: JSON.stringify({
        character_id: selectedPilot,
        gap_minutes: selectedGap,
        seed_killmail_id: seedId,
        side_overrides: Object.entries(overrides).map(([characterId, side]) => ({ character_id: Number(characterId), side })),
        organization_overrides: Object.values(orgOverrides),
      }) }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not build the latest battle report");
    } finally { setLoading(false); }
  }

  async function loadHistory(selectedPilot = pilotId, selectedGap = gapMinutes, preferredSeed: number | null = selectedSeedId) {
    if (!selectedPilot) return;
    setLoading(true); setError(null);
    try {
      const query = new URLSearchParams({ character_id: String(selectedPilot), gap_minutes: String(selectedGap), limit: "250" });
      const next = await api<BattleReportHistoryPayload>(`/battle-reports/history?${query}`);
      setHistory(next);
      const seed = preferredSeed && next.reports.some((row) => row.seed_killmail_id === preferredSeed) ? preferredSeed : next.reports[0]?.seed_killmail_id ?? null;
      setSelectedSeedId(seed);
      setSideOverrides({});
      setOrganizationOverrides({});
      setEditingTeams(false);
      await loadReport(selectedPilot, selectedGap, seed, {}, {});
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load battle report history");
      setLoading(false);
    }
  }

  useEffect(() => { if (pilotId) void loadHistory(pilotId, gapMinutes, null); }, [pilotId, gapMinutes]);

  useEffect(() => {
    if (!pilotId) { setShares([]); return; }
    void api<BattleReportShare[]>(`/battle-reports/shares?character_id=${pilotId}`).then(setShares).catch(() => setShares([]));
  }, [pilotId]);

  useEffect(() => {
    if (!sourceSync || !activeSyncStatuses.has(sourceSync.status)) return;
    const timer = window.setInterval(() => {
      void api<BattleSourceSync>(`/killboard/sync/${sourceSync.job_id}`).then((next) => {
        setSourceSync(next);
        if (!activeSyncStatuses.has(next.status)) void loadHistory();
      }).catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [sourceSync?.job_id, sourceSync?.status, pilotId, gapMinutes, selectedSeedId]);

  async function syncSource() {
    setError(null);
    try {
      setSourceSync(await api<BattleSourceSync>("/killboard/sync", { method: "POST", body: JSON.stringify({ scope: "account" }) }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not refresh Killboard source data"); }
  }

  async function createShare() {
    if (!pilotId || !report) return;
    setShareBusy(true); setError(null); setShareNotice(null);
    try {
      const created = await api<BattleReportShare>("/battle-reports/shares", { method: "POST", body: JSON.stringify({ character_id: pilotId, gap_minutes: gapMinutes, seed_killmail_id: selectedSeedId, side_overrides: Object.entries(sideOverrides).map(([characterId, side]) => ({ character_id: Number(characterId), side })), organization_overrides: Object.values(organizationOverrides) }) });
      setShares((current) => [created, ...current]);
      await navigator.clipboard.writeText(created.share_url);
      setShareNotice("Public snapshot link created and copied. Anyone with the link can view it until you revoke it.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create a public battle report link");
    } finally { setShareBusy(false); }
  }

  async function copyShare(share: BattleReportShare) {
    await navigator.clipboard.writeText(share.share_url);
    setShareNotice("Public battle report link copied.");
  }

  async function revokeShare(shareId: number) {
    setShareBusy(true); setError(null);
    try {
      await api(`/battle-reports/shares/${shareId}`, { method: "DELETE" });
      setShares((current) => current.filter((share) => share.id !== shareId));
      setShareNotice("Public battle report link revoked.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not revoke the public battle report link");
    } finally { setShareBusy(false); }
  }

  const report = payload?.report ?? null;
  const damageRows = useMemo(() => report ? [...report.participants].sort((a, b) => b.damage_done - a.damage_done) : [], [report]);
  const historyIndex = history?.reports.findIndex((row) => row.seed_killmail_id === selectedSeedId) ?? -1;
  const newerBattle = historyIndex > 0 ? history?.reports[historyIndex - 1] ?? null : null;
  const olderBattle = historyIndex >= 0 && historyIndex < (history?.reports.length ?? 0) - 1 ? history?.reports[historyIndex + 1] ?? null : null;

  function historyLabel(row: BattleReportHistoryEntry): string {
    const systems = row.systems.map((system) => system.system_name).join(" / ") || "System unresolved";
    return `${new Date(row.end_time).toLocaleString()} · ${systems} · ${row.pilot_killmail_count} pilot event${row.pilot_killmail_count === 1 ? "" : "s"}`;
  }

  function selectBattle(seedId: number) {
    setSelectedSeedId(seedId);
    setSideOverrides({});
    setOrganizationOverrides({});
    setEditingTeams(false);
    void loadReport(pilotId, gapMinutes, seedId, {}, {});
  }

  function classifyPilot(characterId: number, side: BattleSide) {
    const next = { ...sideOverrides, [characterId]: side };
    setSideOverrides(next);
    void loadReport(pilotId, gapMinutes, selectedSeedId, next, organizationOverrides);
  }

  function classifyOrganization(kind: OrganizationKind, organizationId: number, side: BattleSide) {
    const key = organizationKey(kind, organizationId);
    const next = { ...organizationOverrides, [key]: { organization_type: kind, organization_id: organizationId, side } };
    setOrganizationOverrides(next);
    void loadReport(pilotId, gapMinutes, selectedSeedId, sideOverrides, next);
  }

  function resetClassifications() {
    setSideOverrides({});
    setOrganizationOverrides({});
    void loadReport(pilotId, gapMinutes, selectedSeedId, {}, {});
  }

  if (loading && !context) return <section className="panel"><p>Assembling the battlefield…</p></section>;
  if (!context) return <section className="panel"><div className="alert">{error ?? "Battle Reports are unavailable."}</div></section>;

  return <div className="battle-page">
    <section className="panel battle-command">
      <div><span className="eyebrow">Dynamic reports from retained killmails</span><h2><Swords size={25} /> Battle Reports</h2><p>Select a tracked pilot, then browse their latest and prior connected engagements.</p></div>
      <div className="battle-controls">
        <label>Pilot<select value={pilotId ?? ""} onChange={(event) => setPilotId(Number(event.target.value))}>{context.pilots.map((pilot) => <option key={pilot.character_id} value={pilot.character_id}>{pilot.name}</option>)}</select></label>
        <label>Grouping gap<select value={gapMinutes} onChange={(event) => setGapMinutes(Number(event.target.value))}>{[5, 10, 15, 30, 60].map((value) => <option key={value} value={value}>{value} minutes</option>)}</select></label>
        <label className="battle-history-picker">Battle<select value={selectedSeedId ?? ""} onChange={(event) => selectBattle(Number(event.target.value))} disabled={!history?.reports.length}>{history?.reports.map((row) => <option key={row.seed_killmail_id} value={row.seed_killmail_id}>{historyLabel(row)}</option>)}</select></label>
        <button type="button" onClick={() => olderBattle && selectBattle(olderBattle.seed_killmail_id)} disabled={!olderBattle || loading}><ChevronLeft size={17} /> Older battle</button>
        <button type="button" onClick={() => newerBattle && selectBattle(newerBattle.seed_killmail_id)} disabled={!newerBattle || loading}>Newer battle <ChevronRight size={17} /></button>
        <button type="button" onClick={() => void loadHistory()} disabled={!pilotId || loading}><RefreshCw size={17} className={loading ? "spin" : ""} /> Rebuild history</button>
        <button type="button" onClick={() => { setEditingTeams((current) => !current); setTab("involved"); }} disabled={!report}><Pencil size={17} /> {editingTeams ? "Done editing" : "Edit teams"}</button>
        <button type="button" onClick={() => void createShare()} disabled={!report || shareBusy}><Share2 size={17} /> Share report</button>
        {context.can_sync && <button type="button" className="secondary-action" onClick={() => void syncSource()} disabled={Boolean(sourceSync && activeSyncStatuses.has(sourceSync.status))}><RefreshCw size={17} className={sourceSync && activeSyncStatuses.has(sourceSync.status) ? "spin" : ""} /> Sync source</button>}
      </div>
    </section>

    <div className="battle-placard"><AlertTriangle size={18} /><span>{context.coverage_notice} The grouping gap is the maximum quiet period between the selected pilot’s consecutive killmails.</span></div>
    {error && <div className="alert">{error}</div>}
    {shareNotice && <div className="battle-share-notice">{shareNotice}</div>}
    {editingTeams && report && <section className="panel battle-team-editor"><div className="battle-team-editor-heading"><div><strong>Manual team classification</strong><span>Drag alliances or corporations between teams, or use their selectors. Individual pilot choices below take precedence. Every dependent total rebuilds from the underlying killmails, and shared snapshots preserve these choices.</span></div><button type="button" className="secondary-action" onClick={resetClassifications} disabled={(!Object.keys(sideOverrides).length && !Object.keys(organizationOverrides).length) || loading}><RotateCcw size={16} /> Reset classifications</button></div><TeamOrganizationEditor report={report} overrides={organizationOverrides} onSideChange={classifyOrganization} /></section>}
    {sourceSync && activeSyncStatuses.has(sourceSync.status) && <section className="panel battle-source-sync"><strong>Refreshing zKill discovery and canonical ESI records in the background</strong><span>{sourceSync.message ?? "The report will rebuild when synchronization finishes."}</span><progress value={sourceSync.target_index} max={Math.max(1, sourceSync.target_count)} /></section>}
    {!context.enabled && <div className="alert">The Killboard data source is disabled, so Battle Reports cannot be generated.</div>}
    {context.pilots.length === 0 && <section className="panel"><p className="empty">No eligible tracked pilots are available.</p></section>}

    {payload && !report && <section className="panel battle-empty"><UsersRound size={30} /><h3>No cached battle found for {payload.pilot.name}</h3><p>{payload.coverage.warning}</p>{context.can_sync && <button type="button" onClick={() => { window.location.hash = "killboard"; }}>Open Killboard Sync</button>}</section>}

    {report && <>
      <section className="panel battle-header">
        <div><span className="eyebrow">Engagement {historyIndex >= 0 ? `${historyIndex + 1} of ${history?.total_reports ?? history?.reports.length}` : ""} for <a className="battle-pilot-link" href={zkillCharacterUrl(payload!.pilot.character_id)} target="_blank" rel="noreferrer">{payload?.pilot.name}<ExternalLink size={12} aria-hidden="true" /></a></span><h2>{report.systems.map((system) => system.system_name).join(" · ")}</h2><p>{report.regions.join(" · ") || "Region unresolved"} · {new Date(report.start_time).toLocaleString()} — {new Date(report.end_time).toLocaleTimeString()}</p></div>
        <div className="battle-head-kpis"><span><strong>{compactIsk(report.estimated_total_value)}</strong> destroyed{report.unknown_value_killmails ? ` · ${report.unknown_value_killmails} unknown` : ""}</span><span><strong>{report.killmail_count}</strong> killmails</span><span><strong>{report.pilot_count}</strong> pilots</span><span><strong>{duration(report.duration_seconds)}</strong> duration</span></div>
      </section>

      <nav className="battle-tabs" aria-label="Battle report views">{tabs.map((item) => <button key={item.id} type="button" className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>{item.label}</button>)}</nav>

      {shares.length > 0 && <section className="panel battle-share-panel"><div><strong>Active public snapshots</strong><small>These unguessable links preserve the report as it appeared when shared.</small></div>{shares.map((share) => <div className="battle-share-row" key={share.id}><a href={share.share_url} target="_blank" rel="noreferrer">{share.share_url}</a><span>{share.view_count} view{share.view_count === 1 ? "" : "s"}</span><button type="button" className="secondary-action" onClick={() => void copyShare(share)} aria-label="Copy public report link"><Clipboard size={16} /> Copy</button><button type="button" className="danger-action" onClick={() => void revokeShare(share.id)} disabled={shareBusy} aria-label="Revoke public report link"><Trash2 size={16} /> Revoke</button></div>)}</section>}

      {tab === "involved" && <section className="panel battle-view"><div className="battle-team-grid">{report.teams.map((team) => <TeamCard key={team.side} team={team} />)}</div><PilotTable report={report} rows={report.participants} editable={editingTeams} selectedPilotId={pilotId} onSideChange={classifyPilot} /></section>}

      {tab === "summary" && <section className="battle-team-grid">{report.teams.map((team) => <TeamCard key={team.side} team={team} />)}</section>}

      {tab === "timeline" && <section className="panel battle-timeline">{report.timeline.map((entry) => <a key={entry.killmail_id} href={entry.zkill_url} target="_blank" rel="noreferrer" className={`battle-kill side-${entry.victim_side}`}><time>{new Date(entry.killmail_time).toLocaleTimeString()}</time><span className="battle-kill-identity"><EveImage kind="character" id={entry.victim_character_id} name={entry.victim_name} className="battle-pilot-portrait" /><span><strong>{entry.victim_name}</strong><small>{[entry.victim_corporation_name, entry.victim_alliance_name].filter(Boolean).join(" · ") || "Organization unresolved"}</small></span></span><span className="battle-kill-ship"><EveImage kind="type" id={entry.victim_ship_type_id} name={entry.victim_ship_type_name} className="battle-ship-thumb" /><span><strong>{entry.victim_ship_type_name}</strong><small>{entry.system_name} · {entry.attacker_count} attacker{entry.attacker_count === 1 ? "" : "s"} · {entry.damage_taken.toLocaleString()} damage</small></span></span><strong>{compactIsk(entry.estimated_total_value)}</strong><ExternalLink size={16} /></a>)}</section>}

      {tab === "damage" && <section className="panel battle-view"><PilotTable report={report} rows={damageRows} /></section>}

      {tab === "composition" && <section className="panel battle-view"><CompositionTable report={report} rows={report.composition} /></section>}

      <div className="battle-footnote"><span>{payload?.coverage.grouping_rule}</span><span>Canonical fields: {payload?.coverage.canonical_source} · Discovery and value estimates: {payload?.coverage.discovery_source}</span></div>
    </>}
  </div>;
}
