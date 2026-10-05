import { useEffect, useRef, useState } from "react";
import { TimeSeriesChart } from "../../components/TimeSeriesChart";
import type { ApiClient } from "../../types/hypernet";
import { formatIsk, profitClass } from "./hypernetPresentation";
import "./hypernetAnalytics.css";

type Consent = { characters: Array<{ id: number; name: string; enabled: boolean }> };
type Buying = {
  records: number; wins: number; losses: number; pending: number; refunded: number;
  resolved_spend: number; pending_spend: number; refunded_spend: number; lost_spend: number;
  won_value: number; recorded_result: number; unvalued_results: number;
  win_rate: number | null; roi: number | null; expected_wins: number; luck_delta: number;
};
type Selling = {
  records: number; completed: number; retained: number; lost: number; unknown: number;
  active: number; expired: number; gross_completed: number; seeded_spend: number;
  recorded_result: number; unvalued_results: number; completion_rate: number | null;
};
type Stats = { buying: Buying; selling: Selling };
type Analytics = Stats & {
  days: number; characters: Array<Stats & { id: number; name: string }>;
  items: Array<Stats & { type_id: number; name: string; is_ship: boolean }>;
  monthly_results: Array<{ date: string; buying: number; selling: number; buying_count: number; selling_count: number }>;
};
const percent = (value: number | null) => value == null ? "—" : `${value.toFixed(1)}%`;

function Metric({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return <article><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
}

function OutcomeMetrics({ buying: b, selling: s }: Stats) {
  return <div className="hypernet-analytics-outcomes">
    {b.records > 0 && <div><h5>Buying</h5><div className="hypernet-analytics-kpis">
      <Metric label="Wins / losses" value={`${b.wins} / ${b.losses}`} detail={`${percent(b.win_rate)} win rate · ${b.pending} pending · ${b.refunded} refunded`} />
      <Metric label="Resolved node spend" value={formatIsk(b.resolved_spend, true)} detail={`${formatIsk(b.lost_spend, true)} on lost draws`} />
      <Metric label="Won item valuations" value={formatIsk(b.won_value, true)} detail="Recorded estimates, not wallet receipts" />
      <Metric label="Recorded net / ROI" value={formatIsk(b.recorded_result, true)} detail={`${percent(b.roi)} ROI${b.unvalued_results ? ` · ${b.unvalued_results} results unvalued` : ""}`} />
      <Metric label="Pending / refunded ISK" value={formatIsk(b.pending_spend, true)} detail={`${formatIsk(b.refunded_spend, true)} refunded; excluded from ROI`} />
      <Metric label="Expected / actual wins" value={`${b.expected_wins.toFixed(2)} / ${b.wins}`} detail="Historical odds; future draws remain independent" />
    </div></div>}
    {s.records > 0 && <div><h5>Selling</h5><div className="hypernet-analytics-kpis">
      <Metric label="Items retained / lost" value={`${s.retained} / ${s.lost}`} detail={`${s.completed} completed draws · ${s.unknown} unknown winners`} />
      <Metric label="Completed gross value" value={formatIsk(s.gross_completed, true)} detail={`${formatIsk(s.seeded_spend, true)} self-bought nodes`} />
      <Metric label="Recorded selling result" value={formatIsk(s.recorded_result, true)} detail={s.unvalued_results ? `${s.unvalued_results} results unvalued` : "Includes recorded retained-item value and market dispositions"} />
      <Metric label="Completion rate" value={percent(s.completion_rate)} detail={`${s.active} active · ${s.expired} expired; drafts excluded`} />
    </div></div>}
  </div>;
}

export function HyperNetAnalytics({ api, days: sharedDays, characterId = "", refreshToken }: {
  api: ApiClient; days?: number; characterId?: string; refreshToken?: unknown;
}) {
  const [ownDays, setOwnDays] = useState(30);
  const days = sharedDays ?? ownDays;
  const [consent, setConsent] = useState<Consent | null>(null);
  const [data, setData] = useState<Analytics | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [itemFilter, setItemFilter] = useState("all");
  const [revision, setRevision] = useState(0);
  const request = useRef(0);
  const appliedRequest = useRef("");
  const selection = `${days}:${characterId}:${revision}`;

  useEffect(() => {
    const id = ++request.current;
    setData(null); setError(null);
    void (async () => {
      try {
        const preferences = await api<Consent>("/hypernet/analytics/preferences");
        if (id !== request.current) return;
        setConsent(preferences);
        if (!preferences.characters.some(row => row.enabled && (!characterId || row.id === Number(characterId)))) return;
        const next = await api<Analytics | null>(`/hypernet/analytics?days=${days}${characterId ? `&character_id=${encodeURIComponent(characterId)}` : ""}`);
        if (id === request.current) { appliedRequest.current = selection; setData(next); }
      } catch (err) {
        if (id === request.current) setError(err instanceof Error ? err.message : "Unable to load private HyperNet analytics");
      }
    })();
    return () => { ++request.current; };
  }, [api, days, characterId, revision, refreshToken]);

  async function save(enabled: boolean, id?: number) {
    ++request.current; setData(null); setSaving(true); setError(null);
    try {
      const next = await api<Consent>("/hypernet/analytics/preferences", {
        method: "PATCH", body: JSON.stringify({ enabled, ...(id == null ? {} : { character_id: id }) }),
      });
      setConsent(next);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save analytics preference"); }
    finally { setSaving(false); setRevision(value => value + 1); }
  }

  // Privacy controls are available without rendering a blank analytics panel.
  const visible = appliedRequest.current === selection ? data : null;
  if (!consent?.characters.length) return null;
  const effectiveFilter = visible?.items.some(row => itemFilter === "ships" ? row.is_ship : !row.is_ship) ? itemFilter : "all";
  const items = visible?.items.filter(row => effectiveFilter === "all" || (effectiveFilter === "ships" ? row.is_ship : !row.is_ship)) ?? [];
  const allEnabled = consent.characters.every(row => row.enabled);
  return <>
    <div className="hypernet-analytics-controls"><button type="button" onClick={() => setSettingsOpen(value => !value)} aria-expanded={settingsOpen}>HyperNet analytics privacy</button></div>
    {settingsOpen && <section className="panel stacked hypernet-consent" aria-label="HyperNet analytics privacy">
      <strong>Private analytics · opt-in per character</strong>
      <p>Disabled by default. Only you can see these analytics, including when an admin or corporation view is selected. Existing tracker records remain available. Account controls apply to all current characters; newly linked characters start disabled.</p>
      <div className="button-row"><button type="button" disabled={saving || allEnabled} onClick={() => void save(true)}>Enable all current characters</button><button type="button" disabled={saving || !consent.characters.some(row => row.enabled)} onClick={() => void save(false)}>Disable account analytics</button></div>
      <div className="hypernet-consent-characters">{consent.characters.map(row => <label key={row.id}><input type="checkbox" checked={row.enabled} disabled={saving} onChange={event => void save(event.target.checked, row.id)} />{row.name}</label>)}</div>
      {error && <div className="mini-alert">{error}</div>}
    </section>}
    {visible && <section className="panel stacked hypernet-private-analytics" aria-label="Private HyperNet analytics">
      <div className="section-heading"><div><h4>Private HyperNet analytics</h4><p>Only your enabled characters · {days === 0 ? "All-Time" : `${days} days`} · {visible.characters.length} character{visible.characters.length === 1 ? "" : "s"} with records</p></div>{sharedDays == null && <select aria-label="HyperNet analytics reporting period" value={days} onChange={event => setOwnDays(Number(event.target.value))}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>1 year</option><option value={0}>All-Time</option></select>}</div>
      <OutcomeMetrics buying={visible.buying} selling={visible.selling} />
      <p className="muted">Results use completion or refund dates; unresolved records use their entry dates. Buying and selling are separate: retained-item valuations and later relistings can overlap, so these are recorded results, not a combined cash-profit ledger.</p>
      {visible.monthly_results.length > 0 && <div><h5>Monthly recorded results</h5><TimeSeriesChart ariaLabel="Monthly private HyperNet results" selectedDays={days} includeZero formatValue={value => formatIsk(value, true)} series={[
        { key: "buying", name: "Buying", color: "#55c7d8", points: visible.monthly_results.filter(row => row.buying_count > 0).map(row => ({ date: row.date, value: row.buying })) },
        { key: "selling", name: "Selling", color: "#79e0a7", points: visible.monthly_results.filter(row => row.selling_count > 0).map(row => ({ date: row.date, value: row.selling })) },
      ]} /></div>}
      <details><summary>Character breakdown</summary>{visible.characters.map(row => <article className="hypernet-character-analytics" key={row.id}><h5>{row.name}</h5><OutcomeMetrics {...row} /></article>)}</details>
      <div className="section-heading"><h5>Ship and item statistics</h5><select aria-label="HyperNet analytics item category" value={effectiveFilter} onChange={event => setItemFilter(event.target.value)}><option value="all">All items</option>{visible.items.some(row => row.is_ship) && <option value="ships">Ships</option>}{visible.items.some(row => !row.is_ship) && <option value="other">Other items</option>}</select></div>
      {items.length > 0 && <div className="table-wrap"><table><thead><tr><th>Item</th>{visible.buying.records > 0 && <><th>Buyer wins / losses</th><th>Node spend</th><th>Buyer net / ROI</th></>}{visible.selling.records > 0 && <><th>Retained / lost</th><th>Selling result</th></>}</tr></thead><tbody>{items.map(row => <tr key={row.type_id}><td>{row.name}<small>{row.is_ship ? "Ship" : "Item"}</small></td>{visible.buying.records > 0 && <><td>{row.buying.records ? `${row.buying.wins} / ${row.buying.losses}` : "—"}</td><td>{row.buying.records ? formatIsk(row.buying.resolved_spend, true) : "—"}</td><td className={profitClass(row.buying.recorded_result)}>{row.buying.records ? formatIsk(row.buying.recorded_result, true) : "—"}<small>{percent(row.buying.roi)}</small></td></>}{visible.selling.records > 0 && <><td>{row.selling.records ? `${row.selling.retained} / ${row.selling.lost}` : "—"}</td><td className={profitClass(row.selling.recorded_result)}>{row.selling.records ? formatIsk(row.selling.recorded_result, true) : "—"}</td></>}</tr>)}</tbody></table></div>}
    </section>}
  </>;
}
