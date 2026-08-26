import { AlertTriangle, ExternalLink, Swords } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { PublicBattleReportPayload } from "../../types/battleReports";
import { compactIsk, CompositionTable, duration, EveImage, PilotTable, TeamCard, zkillCharacterUrl } from "./BattleReportsPage";
import "./battleReports.css";
import "./battleReportMedia.css";
import "./publicBattleReport.css";

type ApiClient = <T>(path: string, options?: RequestInit) => Promise<T>;
type ReportTab = "involved" | "summary" | "timeline" | "damage" | "composition";

const tabs: { id: ReportTab; label: string }[] = [
  { id: "involved", label: "Involved" },
  { id: "summary", label: "Summary" },
  { id: "timeline", label: "Timeline" },
  { id: "damage", label: "Damage" },
  { id: "composition", label: "Composition" },
];

export function PublicBattleReportPage({ api, shareToken, onBack }: { api: ApiClient; shareToken: string; onBack: () => void }) {
  const [payload, setPayload] = useState<PublicBattleReportPayload | null>(null);
  const [tab, setTab] = useState<ReportTab>("involved");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<PublicBattleReportPayload>(`/battle-reports/public/${encodeURIComponent(shareToken)}`)
      .then((next) => { setPayload(next); document.title = `Battle Report · ${next.pilot.name} · EQM`; })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "This shared battle report is unavailable."));
  }, [shareToken]);

  const report = payload?.report ?? null;
  const damageRows = useMemo(() => report ? [...report.participants].sort((a, b) => b.damage_done - a.damage_done) : [], [report]);

  if (error) return <main className="battle-public-shell"><section className="panel battle-public-error"><Swords size={34} /><h1>Battle Report Unavailable</h1><p>{error}</p><button type="button" onClick={onBack}>Return to EQM</button></section></main>;
  if (!payload || !report) return <main className="battle-public-shell"><section className="panel"><p>Reconstructing the battlefield…</p></section></main>;

  return <main className="battle-public-shell"><div className="battle-page">
    <header className="battle-public-brand"><button type="button" onClick={onBack}><img src="/eqm-logo.webp" alt="" /> EVE Quartermaster</button><span>Public Battle Report Snapshot</span></header>
    <section className="panel battle-header">
      <div><span className="eyebrow">Latest engagement for <a className="battle-pilot-link" href={zkillCharacterUrl(payload.pilot.character_id)} target="_blank" rel="noreferrer">{payload.pilot.name}<ExternalLink size={12} aria-hidden="true" /></a></span><h1>{report.systems.map((system) => system.system_name).join(" · ")}</h1><p>{report.regions.join(" · ") || "Region unresolved"} · {new Date(report.start_time).toLocaleString()} — {new Date(report.end_time).toLocaleTimeString()}</p></div>
      <div className="battle-head-kpis"><span><strong>{compactIsk(report.estimated_total_value)}</strong> destroyed{report.unknown_value_killmails ? ` · ${report.unknown_value_killmails} unknown` : ""}</span><span><strong>{report.killmail_count}</strong> killmails</span><span><strong>{report.pilot_count}</strong> pilots</span><span><strong>{duration(report.duration_seconds)}</strong> duration</span></div>
    </section>

    <div className="battle-placard"><AlertTriangle size={18} /><span>{payload.coverage.warning} This is an immutable snapshot generated {payload.share.created_at ? new Date(payload.share.created_at).toLocaleString() : "by EQM"}.</span></div>
    <nav className="battle-tabs" aria-label="Battle report views">{tabs.map((item) => <button key={item.id} type="button" className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>{item.label}</button>)}</nav>

    {tab === "involved" && <section className="panel battle-view"><div className="battle-team-grid">{report.teams.map((team) => <TeamCard key={team.side} team={team} />)}</div><PilotTable report={report} rows={report.participants} /></section>}
    {tab === "summary" && <section className="battle-team-grid">{report.teams.map((team) => <TeamCard key={team.side} team={team} />)}</section>}
    {tab === "timeline" && <section className="panel battle-timeline">{report.timeline.map((entry) => <a key={entry.killmail_id} href={entry.zkill_url} target="_blank" rel="noreferrer" className={`battle-kill side-${entry.victim_side}`}><time>{new Date(entry.killmail_time).toLocaleTimeString()}</time><span className="battle-kill-identity"><EveImage kind="character" id={entry.victim_character_id} name={entry.victim_name} className="battle-pilot-portrait" /><span><strong>{entry.victim_name}</strong><small>{[entry.victim_corporation_name, entry.victim_alliance_name].filter(Boolean).join(" · ") || "Organization unresolved"}</small></span></span><span className="battle-kill-ship"><EveImage kind="type" id={entry.victim_ship_type_id} name={entry.victim_ship_type_name} className="battle-ship-thumb" /><span><strong>{entry.victim_ship_type_name}</strong><small>{entry.system_name} · {entry.attacker_count} attacker{entry.attacker_count === 1 ? "" : "s"} · {entry.damage_taken.toLocaleString()} damage</small></span></span><strong>{compactIsk(entry.estimated_total_value)}</strong><ExternalLink size={16} /></a>)}</section>}
    {tab === "damage" && <section className="panel battle-view"><PilotTable report={report} rows={damageRows} /></section>}
    {tab === "composition" && <section className="panel battle-view"><CompositionTable report={report} rows={report.composition} /></section>}
    <footer className="battle-footnote"><span>{payload.coverage.grouping_rule}</span><span>Canonical fields: {payload.coverage.canonical_source} · Discovery and value estimates: {payload.coverage.discovery_source}</span><span>{payload.share.view_count} public view{payload.share.view_count === 1 ? "" : "s"}</span></footer>
  </div></main>;
}
