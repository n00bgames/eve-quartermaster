import { BarChart3, Calculator, Clock3, Coins, History, LayoutGrid, List, Plus, RefreshCw, TicketCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ModuleFinder } from "../../components/ModuleFinder";
import { matchesSearchTerms } from "../../lib/search";
import type { ApiClient, HyperNetMeta, HyperNetOffer, HyperNetSummary } from "../../types/hypernet";
import { HyperNetOfferDetail } from "./HyperNetOfferDetail";
import { HyperNetOfferForm } from "./HyperNetOfferForm";
import { countdown, formatIsk, profitClass } from "./hypernetPresentation";
import "./hypernet.css";


type View = { kind: "board" | "new" } | { kind: "detail"; id: number };
function routeFromHash(): View {
  const path = window.location.hash.replace(/^#/, "").replace(/\/$/, "");
  if (path === "hypernet/new") return { kind: "new" };
  const detail = path.match(/^hypernet\/offers\/(\d+)$/);
  return detail ? { kind: "detail", id: Number(detail[1]) } : { kind: "board" };
}

function SummaryMetric({ label, value, detail, tone }: { label: string; value: string; detail?: string; tone?: string }) {
  return <article className={`hypernet-summary-metric ${tone ?? ""}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
}

function Status({ value }: { value: string }) {
  return <span className={`hypernet-status hypernet-status-${value}`}>{value.replace(/_/g, " ")}</span>;
}

function OfferCard({ offer, onOpen }: { offer: HyperNetOffer; onOpen: () => void }) {
  const profit = offer.final_profit ?? offer.calculations.financials.profit;
  return <button type="button" className="hypernet-offer-card" onClick={onOpen}>
    <div className="hypernet-offer-card-heading"><img src={`https://images.evetech.net/types/${offer.item.type_id}/icon?size=64`} alt="" loading="lazy" /><span><strong>{offer.quantity > 1 ? `${offer.quantity}× ` : ""}{offer.item.name}</strong><small>{offer.seller.name} · {offer.location.name}</small></span><Status value={offer.status} /></div>
    <div className="hypernet-progress-track"><i style={{ width: `${offer.filled_percent}%` }} /><b style={{ width: `${offer.total_nodes ? offer.seller_owned_nodes / offer.total_nodes * 100 : 0}%` }} /></div>
    <div className="hypernet-offer-stats"><span><strong>{offer.nodes_sold}/{offer.total_nodes}</strong> nodes</span><span><strong>{offer.organic_nodes_sold}</strong> organic</span><span><strong>{offer.seller_owned_nodes}</strong> seeded</span><span><strong>{offer.unique_participants}</strong> pilots</span></div>
    <div className="hypernet-offer-economics"><span><small>Gross</small><strong>{formatIsk(offer.total_offer_price, true)}</strong></span><span><small>{offer.final_profit == null ? "Estimated profit" : "Final result"}</small><strong className={profitClass(profit)}>{formatIsk(profit, true)}</strong></span><span><small>{["active", "awaiting_reconciliation"].includes(offer.status) ? "Remaining" : "Closed"}</small><strong>{["active", "awaiting_reconciliation"].includes(offer.status) ? countdown(offer.remaining_seconds) : new Date(offer.reconciled_at || offer.updated_at).toLocaleDateString()}</strong></span></div>
  </button>;
}

export function HyperNetTrackerPage({ api }: { api: ApiClient }) {
  const [route, setRoute] = useState<View>(routeFromHash());
  const [meta, setMeta] = useState<HyperNetMeta | null>(null);
  const [summary, setSummary] = useState<HyperNetSummary | null>(null);
  const [offers, setOffers] = useState<HyperNetOffer[]>([]);
  const [selected, setSelected] = useState<HyperNetOffer | null>(null);
  const [status, setStatus] = useState("active");
  const [mode, setMode] = useState<"cards" | "table">("cards");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useCallback((path = "hypernet") => {
    window.location.hash = path;
    setRoute(routeFromHash());
  }, []);

  const loadBoard = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const [nextMeta, nextSummary, nextOffers] = await Promise.all([
        api<HyperNetMeta>("/hypernet/meta"), api<HyperNetSummary>("/hypernet/summary"), api<HyperNetOffer[]>(`/hypernet/offers?status=${encodeURIComponent(status)}`),
      ]);
      setMeta(nextMeta); setSummary(nextSummary); setOffers(nextOffers);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to load HyperNet Tracker"); }
    finally { setBusy(false); }
  }, [api, status]);

  const loadDetail = useCallback(async (id: number) => {
    setBusy(true); setError(null);
    try { setSelected(await api<HyperNetOffer>(`/hypernet/offers/${id}`)); }
    catch (err) { setSelected(null); setError(err instanceof Error ? err.message : "Unable to load HyperNet offer"); }
    finally { setBusy(false); }
  }, [api]);

  useEffect(() => {
    const sync = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);
  useEffect(() => { if (route.kind === "board") void loadBoard(); else if (route.kind === "detail") void loadDetail(route.id); }, [route.kind, route.kind === "detail" ? route.id : status]);
  useEffect(() => { if (!meta) void api<HyperNetMeta>("/hypernet/meta").then(setMeta).catch((err) => setError(err instanceof Error ? err.message : "Unable to load HyperNet setup")); }, [meta, api]);

  const sortedOffers = useMemo(() => offers.filter((offer) => matchesSearchTerms(query, [
    offer.id,
    offer.item.type_id,
    offer.item.name,
    offer.item.group,
    offer.item.category,
    offer.seller.name,
    offer.location.name,
    offer.status,
    offer.notes,
    offer.source,
    offer.source_reference,
    offer.winner,
    ...(offer.participants ?? []).map((participant) => participant.participant_name),
  ])).sort((a, b) => {
    if (["active", "awaiting_reconciliation"].includes(a.status) && ["active", "awaiting_reconciliation"].includes(b.status)) return a.remaining_seconds - b.remaining_seconds;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  }), [offers, query]);

  if (route.kind === "new") return meta ? <HyperNetOfferForm api={api} meta={meta} onCancel={() => navigate()} onSaved={(offer) => { setSelected(offer); navigate(`hypernet/offers/${offer.id}`); }} /> : <section className="panel"><p className="muted">Loading HyperNet setup…</p>{error && <div className="mini-alert">{error}</div>}</section>;
  if (route.kind === "detail") return selected?.id === route.id ? <HyperNetOfferDetail api={api} offer={selected} onBack={() => navigate()} onChanged={(offer) => { setSelected(offer); void loadBoard(); }} /> : <section className="panel"><p className="muted">Loading HyperNet offer…</p>{error && <div className="mini-alert">{error}</div>}</section>;

  return <div className="hypernet-page">
    <div className="hypernet-toolbar"><div><span className="eyebrow">Finance and trade</span><h3>HyperNet Tracker</h3><p>Manual seller-side performance, seeded-node risk, and reconciliation. No HyperNet offer API is assumed.</p></div><div className="button-row"><button type="button" disabled={busy} onClick={() => void loadBoard()}><RefreshCw className={busy ? "spin" : ""} size={17} /> Refresh</button><button type="button" onClick={() => navigate("hypernet/new")}><Plus size={17} /> Plan or record offer</button></div></div>
    <div className="hypernet-manual-placard"><TicketCheck size={21} /><span><strong>Manual data source active.</strong> ESI supports character, item, location, and market context, but EQM does not assume it can read HyperNet offers. Reconcile outcomes from the in-game offer.</span></div>
    {error && <div className="mini-alert">{error}</div>}
    {summary && <>
      <div className="hypernet-summary-grid">
        <SummaryMetric label="Active offers" value={summary.active_offers.toLocaleString()} detail={`${summary.nearing_expiration} expire within 12h`} />
        <SummaryMetric label="Nodes filled" value={`${summary.nodes_sold}/${summary.total_nodes}`} detail={summary.total_nodes ? `${(summary.nodes_sold / summary.total_nodes * 100).toFixed(1)}% active fill` : "No active nodes"} />
        <SummaryMetric label="Gross active value" value={formatIsk(summary.gross_offer_value, true)} detail={`${formatIsk(summary.expected_payout, true)} after 5% fee`} />
        <SummaryMetric label="Estimated active profit" value={formatIsk(summary.estimated_profit, true)} detail={`${formatIsk(summary.capital_tied_up, true)} tied up`} tone={profitClass(summary.estimated_profit)} />
        <SummaryMetric label="Lifetime result" value={formatIsk(summary.lifetime_profit, true)} detail={`${summary.completed_offers} complete · ${summary.expired_offers} expired`} tone={profitClass(summary.lifetime_profit)} />
        <SummaryMetric label="Completion rate" value={summary.completion_rate_percent == null ? "—" : `${summary.completion_rate_percent.toFixed(1)}%`} detail={summary.average_hours_to_completion == null ? "No completed sample" : `${summary.average_hours_to_completion.toFixed(1)}h average`} />
      </div>
      {summary.next_expiring_offer && <button className="hypernet-next-expiring" type="button" onClick={() => navigate(`hypernet/offers/${summary.next_expiring_offer!.id}`)}><Clock3 size={20} /><span><small>Next expiring offer</small><strong>{summary.next_expiring_offer.item.name}</strong><em>{summary.next_expiring_offer.nodes_sold}/{summary.next_expiring_offer.total_nodes} nodes · {countdown(summary.next_expiring_offer.remaining_seconds)}</em></span><b>{formatIsk(summary.next_expiring_offer.calculations.financials.profit, true)}</b></button>}
    </>}

    <section className="panel hypernet-board">
      <div className="section-heading"><div><h3>{status === "active" ? "Active Offers" : status === "all" ? "Offer History" : status.replace(/_/g, " ")}</h3><p>{sortedOffers.length} manual record{sortedOffers.length === 1 ? "" : "s"}</p></div><div className="hypernet-board-controls"><ModuleFinder query={query} onQueryChange={setQuery} label="Search HyperNet offers" placeholder="Item, seller, location, participant…" resultCount={sortedOffers.length} totalCount={offers.length} /><label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="active">Active</option><option value="all">All history</option>{meta?.statuses.map((value) => <option key={value} value={value}>{value.replace(/_/g, " ")}</option>)}</select></label><div className="hypernet-view-toggle"><button type="button" className={mode === "cards" ? "active" : ""} title="Card view" onClick={() => setMode("cards")}><LayoutGrid size={16} /></button><button type="button" className={mode === "table" ? "active" : ""} title="Dense table view" onClick={() => setMode("table")}><List size={16} /></button></div></div></div>
      {mode === "cards" ? <div className="hypernet-offer-grid">{sortedOffers.map((offer) => <OfferCard key={offer.id} offer={offer} onOpen={() => navigate(`hypernet/offers/${offer.id}`)} />)}</div> : <div className="table-scroll"><table className="hypernet-table"><thead><tr><th>Offer</th><th>Status</th><th>Progress</th><th>Gross</th><th>Core cost</th><th>Profit/result</th><th>Remaining</th></tr></thead><tbody>{sortedOffers.map((offer) => <tr key={offer.id} onClick={() => navigate(`hypernet/offers/${offer.id}`)}><td><strong>{offer.item.name}</strong><small>{offer.seller.name} · {offer.location.name}</small></td><td><Status value={offer.status} /></td><td>{offer.nodes_sold}/{offer.total_nodes}<small>{offer.organic_nodes_sold} organic · {offer.seller_owned_nodes} seeded</small></td><td>{formatIsk(offer.total_offer_price, true)}</td><td>{formatIsk(offer.calculations.financials.hypercore_cost, true)}</td><td className={profitClass(offer.final_profit ?? offer.calculations.financials.profit)}>{formatIsk(offer.final_profit ?? offer.calculations.financials.profit, true)}</td><td>{["active", "awaiting_reconciliation"].includes(offer.status) ? countdown(offer.remaining_seconds) : "—"}</td></tr>)}</tbody></table></div>}
      {sortedOffers.length === 0 && !busy && <div className="hypernet-empty"><Calculator size={28} /><strong>No matching HyperNet offers</strong><p>Use the calculator to plan one or record an offer already running in EVE.</p><button type="button" onClick={() => navigate("hypernet/new")}><Plus size={17} /> Plan first offer</button></div>}
    </section>
    {summary && <section className="panel hypernet-history-strip"><div><BarChart3 size={19} /><span><strong>Average completed profit</strong><small>{formatIsk(summary.average_profit_per_completed_offer)}</small></span></div><div><History size={19} /><span><strong>Average first organic node</strong><small>{summary.average_hours_to_first_node == null ? "Insufficient sample" : `${summary.average_hours_to_first_node.toFixed(1)} hours`}</small></span></div><div><Coins size={19} /><span><strong>Active HyperCore expense</strong><small>{formatIsk(summary.hypercore_cost)}</small></span></div></section>}
  </div>;
}
