import { BarChart3, Calculator, Clock3, Coins, Dice5, History, LayoutGrid, List, Pencil, Plus, RefreshCw, TicketCheck, Trophy, XCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ModuleFinder } from "../../components/ModuleFinder";
import { matchesSearchTerms } from "../../lib/search";
import type { ApiClient, HyperNetMeta, HyperNetOffer, HyperNetParticipation, HyperNetSummary } from "../../types/hypernet";
import { HyperNetOfferDetail } from "./HyperNetOfferDetail";
import { HyperNetNodeResearch } from "./HyperNetNodeResearch";
import { HyperNetOfferForm } from "./HyperNetOfferForm";
import { HyperNetParticipationForm } from "./HyperNetParticipationForm";
import { countdown, formatIsk, hypernetItemIcon, profitClass } from "./hypernetPresentation";
import "./hypernet.css";


type View = { kind: "board" | "new" | "new-bid" } | { kind: "detail" | "edit-bid"; id: number };
function routeFromHash(): View {
  const path = window.location.hash.replace(/^#/, "").replace(/\/$/, "");
  if (path === "hypernet/new") return { kind: "new" };
  if (path === "hypernet/bids/new") return { kind: "new-bid" };
  const editBid = path.match(/^hypernet\/bids\/(\d+)\/edit$/);
  if (editBid) return { kind: "edit-bid", id: Number(editBid[1]) };
  const detail = path.match(/^hypernet\/offers\/(\d+)$/);
  return detail ? { kind: "detail", id: Number(detail[1]) } : { kind: "board" };
}

function SummaryMetric({ label, value, detail, tone }: { label: string; value: string; detail?: string; tone?: string }) {
  return <article className={`hypernet-summary-metric ${tone ?? ""}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
}

function Status({ value, refunded = false }: { value: string; refunded?: boolean }) {
  return <span className={`hypernet-status hypernet-status-${refunded ? "refunded" : value}`}>{refunded ? "Expired · refunded" : value.replace(/_/g, " ")}</span>;
}

function OfferCard({ offer, onOpen }: { offer: HyperNetOffer; onOpen: () => void }) {
  const profit = offer.market_sale?.lifecycle_profit ?? offer.final_profit ?? offer.calculations.financials.profit;
  return <button type="button" className="hypernet-offer-card" onClick={onOpen}>
    <div className="hypernet-offer-card-heading"><img src={hypernetItemIcon(offer.item)} alt="" loading="lazy" /><span><strong>{offer.quantity > 1 ? `${offer.quantity}× ` : ""}{offer.item.name}</strong><small>{offer.seller.name} · {offer.location.name}</small></span><Status value={offer.status} />{offer.market_sale && <span className="hypernet-status hypernet-status-market-sold">Market sold</span>}</div>
    <div className="hypernet-progress-track"><i style={{ width: `${offer.filled_percent}%` }} /><b style={{ width: `${offer.total_nodes ? offer.seller_owned_nodes / offer.total_nodes * 100 : 0}%` }} /></div>
    <div className="hypernet-offer-stats"><span><strong>{offer.nodes_sold}/{offer.total_nodes}</strong> nodes</span><span><strong>{offer.organic_nodes_sold}</strong> organic</span><span><strong>{offer.seller_owned_nodes}</strong> seeded</span><span><strong>{offer.unique_participants}</strong> pilots</span></div>
    <div className="hypernet-offer-economics"><span><small>Gross</small><strong>{formatIsk(offer.total_offer_price, true)}</strong></span><span><small>{offer.market_sale ? "Lifecycle result" : offer.final_profit == null ? "Estimated profit" : "Final result"}</small><strong className={profitClass(profit)}>{formatIsk(profit, true)}</strong></span><span><small>{["active", "awaiting_reconciliation"].includes(offer.status) ? "Remaining" : "Closed"}</small><strong>{["active", "awaiting_reconciliation"].includes(offer.status) ? countdown(offer.remaining_seconds) : new Date(offer.reconciled_at || offer.updated_at).toLocaleDateString()}</strong></span></div>
  </button>;
}

export function HyperNetTrackerPage({ api }: { api: ApiClient }) {
  const [route, setRoute] = useState<View>(routeFromHash());
  const [meta, setMeta] = useState<HyperNetMeta | null>(null);
  const [summary, setSummary] = useState<HyperNetSummary | null>(null);
  const [offers, setOffers] = useState<HyperNetOffer[]>([]);
  const [participations, setParticipations] = useState<HyperNetParticipation[]>([]);
  const [selected, setSelected] = useState<HyperNetOffer | null>(null);
  const [status, setStatus] = useState("active");
  const [bidOutcome, setBidOutcome] = useState("all");
  const [characterId, setCharacterId] = useState("");
  const boardRequest = useRef(0);
  const [side, setSide] = useState<"seller" | "buyer" | "combined">("seller");
  const [mode, setMode] = useState<"cards" | "table">("cards");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useCallback((path = "hypernet") => {
    window.location.hash = path;
    setRoute(routeFromHash());
  }, []);

  const loadBoard = useCallback(async () => {
    const request = ++boardRequest.current;
    setBusy(true); setError(null);
    try {
      const characterFilter = characterId ? `character_id=${encodeURIComponent(characterId)}` : "";
      const [nextMeta, nextSummary, nextOffers, nextParticipations] = await Promise.all([
        api<HyperNetMeta>("/hypernet/meta"), api<HyperNetSummary>(`/hypernet/summary?${characterFilter}`), api<HyperNetOffer[]>(`/hypernet/offers?status=${encodeURIComponent(status)}${characterId ? `&seller_${characterFilter}` : ""}`),
        api<HyperNetParticipation[]>(`/hypernet/participations?outcome=${encodeURIComponent(route.kind === "edit-bid" ? "all" : bidOutcome)}&${route.kind === "edit-bid" ? "" : characterFilter}`),
      ]);
      if (request !== boardRequest.current) return;
      setMeta(nextMeta); setSummary(nextSummary); setOffers(nextOffers); setParticipations(nextParticipations);
    } catch (err) { if (request === boardRequest.current) setError(err instanceof Error ? err.message : "Unable to load HyperNet Tracker"); }
    finally { if (request === boardRequest.current) setBusy(false); }
  }, [api, status, bidOutcome, characterId, route.kind]);

  const resolveBid = useCallback(async (bid: HyperNetParticipation, outcome: "won" | "lost" | "expired") => {
    let itemValue: number | null = null;
    if (outcome === "lost" && !window.confirm(`Mark the ${bid.item.name} bid as lost? This records a ${formatIsk(-bid.total_spent)} result.`)) return;
    if (outcome === "won") {
      const supplied = window.prompt(`Market value of the ${bid.item.name} when won (ISK):`, String(bid.total_spent));
      if (supplied === null) return;
      itemValue = Number(supplied.replace(/,/g, ""));
      if (!Number.isFinite(itemValue) || itemValue < 0) { setError("Enter a valid non-negative item value."); return; }
    }
    setBusy(true); setError(null);
    try {
      await api<HyperNetParticipation>(`/hypernet/participations/${bid.id}/resolve`, { method: "POST", body: JSON.stringify({
        outcome, completed_at: new Date().toISOString(), item_value_at_completion: itemValue,
      }) });
      await loadBoard();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to resolve HyperNet bid"); }
    finally { setBusy(false); }
  }, [api, loadBoard]);

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
  useEffect(() => { if (route.kind === "board" || route.kind === "edit-bid") void loadBoard(); else if (route.kind === "detail") void loadDetail(route.id); }, [route, status, bidOutcome, loadBoard, loadDetail]);
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
    offer.market_sale ? "market sold" : null,
    offer.market_sale?.note,
    ...(offer.participants ?? []).map((participant) => participant.participant_name),
  ])).sort((a, b) => {
    if (["active", "awaiting_reconciliation"].includes(a.status) && ["active", "awaiting_reconciliation"].includes(b.status)) return a.remaining_seconds - b.remaining_seconds;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  }), [offers, query]);

  const sortedParticipations = useMemo(() => participations.filter((bid) => matchesSearchTerms(query, [
    bid.id, bid.item.type_id, bid.item.name, bid.item.group, bid.character.name, bid.seller_name,
    bid.location.name, bid.outcome, bid.external_offer_reference, bid.notes,
  ])).sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()), [participations, query]);

  const showSelling = side !== "buyer";
  const showBidding = side !== "seller";
  const visibleCount = (showSelling ? sortedOffers.length : 0) + (showBidding ? sortedParticipations.length : 0);
  const totalCount = (showSelling ? offers.length : 0) + (showBidding ? participations.length : 0);

  if (route.kind === "new") return meta ? <HyperNetOfferForm api={api} meta={meta} onCancel={() => navigate()} onSaved={(offer) => { setSelected(offer); navigate(`hypernet/offers/${offer.id}`); }} /> : <section className="panel"><p className="muted">Loading HyperNet setup…</p>{error && <div className="mini-alert">{error}</div>}</section>;
  if (route.kind === "new-bid") return meta ? <HyperNetParticipationForm api={api} meta={meta} onCancel={() => navigate()} onSaved={() => { setSide((current) => current === "combined" ? "combined" : "buyer"); navigate(); }} /> : <section className="panel"><p className="muted">Loading HyperNet setup…</p>{error && <div className="mini-alert">{error}</div>}</section>;
  if (route.kind === "edit-bid") {
    const bid = participations.find((row) => row.id === route.id);
    return meta && bid ? <HyperNetParticipationForm api={api} meta={meta} bid={bid} onCancel={() => navigate()} onSaved={() => { setSide((current) => current === "combined" ? "combined" : "buyer"); navigate(); }} /> : <section className="panel"><p className="muted">Loading HyperNet bid…</p>{error && <div className="mini-alert">{error}</div>}</section>;
  }
  if (route.kind === "detail") return selected?.id === route.id ? <HyperNetOfferDetail api={api} offer={selected} onBack={() => navigate()} onChanged={(offer) => { setSelected(offer); void loadBoard(); }} /> : <section className="panel"><p className="muted">Loading HyperNet offer…</p>{error && <div className="mini-alert">{error}</div>}</section>;

  return <div className="hypernet-page">
    <div className="hypernet-toolbar"><div><span className="eyebrow">Finance and trade</span><h3>HyperNet Tracker</h3><p>Seller offers, nodes purchased, win/loss history, seeded-node risk, and combined HyperNet performance.</p></div><div className="button-row"><button type="button" disabled={busy} onClick={() => void loadBoard()}><RefreshCw className={busy ? "spin" : ""} size={17} /> Refresh</button><button type="button" onClick={() => navigate("hypernet/bids/new")}><Dice5 size={17} /> Record bid</button><button type="button" onClick={() => navigate("hypernet/new")}><Plus size={17} /> Plan or record offer</button></div></div>
    <div className="hypernet-manual-placard"><TicketCheck size={21} /><span><strong>Manual data source active.</strong> ESI supports character, item, location, and market context, but EQM does not assume it can read HyperNet offers. Reconcile outcomes from the in-game offer.</span></div>
    <div className="hypernet-character-filter"><label><span>View</span><select aria-label="HyperNet view" value={side} onChange={(event) => setSide(event.target.value as typeof side)}><option value="seller">Selling</option><option value="buyer">Bidding</option><option value="combined">Combined</option></select></label><label><span>Character</span><select aria-label="Character" value={characterId} onChange={(event) => {
      ++boardRequest.current;
      setSummary(null); setOffers([]); setParticipations([]); setBusy(true);
      setCharacterId(event.target.value);
    }}><option value="">All My Characters</option>{(meta?.filter_characters ?? meta?.seller_characters ?? []).map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}</select></label><span className="muted">Applies to all views. Summary totals cover the selected character’s full history; search and status filters apply to the records below.</span></div>
    {error && <div className="mini-alert">{error}</div>}
    {summary && <>
      <div className="hypernet-summary-grid">
        {showSelling && <>
        <SummaryMetric label="Active offers" value={summary.active_offers.toLocaleString()} detail={`${summary.nearing_expiration} expire within 12h`} />
        <SummaryMetric label="Nodes filled" value={`${summary.nodes_sold}/${summary.total_nodes}`} detail={summary.total_nodes ? `${(summary.nodes_sold / summary.total_nodes * 100).toFixed(1)}% active fill` : "No active nodes"} />
        <SummaryMetric label="Gross active value" value={formatIsk(summary.gross_offer_value, true)} detail={`${formatIsk(summary.expected_payout, true)} after 5% fee`} />
        <SummaryMetric label="Active profit before self-bought nodes" value={formatIsk(summary.estimated_profit, true)} detail="After hull, HyperCores, and completion fee" tone={profitClass(summary.estimated_profit)} />
        <SummaryMetric label="Seller lifetime result" value={formatIsk(summary.lifetime_profit, true)} detail={`${summary.completed_offers} completed · ${summary.market_sold_items ?? 0} market dispositions`} tone={profitClass(summary.lifetime_profit)} />
        </>}
        {showBidding && <SummaryMetric label="Bid result" value={formatIsk(summary.participation.realized_profit_loss, true)} detail={`${summary.participation.won_bids} won · ${summary.participation.lost_bids} lost`} tone={profitClass(summary.participation.realized_profit_loss)} />}
        {side === "combined" && <SummaryMetric label="Combined lifetime" value={formatIsk(summary.combined_lifetime_result, true)} detail="Seller lifecycle result + resolved bid result" tone={profitClass(summary.combined_lifetime_result)} />}
      </div>
      {showSelling && <div className="hypernet-seller-risk-summary">
        <SummaryMetric label="Self-bought nodes on active offers" value={formatIsk(summary.active_seller_node_spend, true)} detail={`${formatIsk(summary.capital_tied_up, true)} total capital tied up`} />
        <SummaryMetric label="If outside buyers win all active offers" value={formatIsk(summary.active_external_winner_result, true)} detail="Assumes every offer fills; includes hulls, cores, fees, and self-bought nodes" tone={profitClass(summary.active_external_winner_result)} />
      </div>}
      {showBidding && <div className="hypernet-bid-analytics">
        <SummaryMetric label="Open bid exposure" value={formatIsk(summary.participation.active_spend, true)} detail={`${summary.participation.active_bids} bids · ${summary.participation.active_nodes} nodes`} />
        <SummaryMetric label="Observed win rate" value={summary.participation.win_rate_percent == null ? "—" : `${summary.participation.win_rate_percent.toFixed(1)}%`} detail={`${summary.participation.resolved_bids} resolved bids`} />
        <SummaryMetric label="Expected vs actual wins" value={`${summary.participation.expected_wins.toFixed(2)} → ${summary.participation.won_bids}`} detail={`${summary.participation.luck_delta_wins >= 0 ? "+" : ""}${summary.participation.luck_delta_wins.toFixed(2)} wins vs odds`} tone={profitClass(summary.participation.luck_delta_wins)} />
        <SummaryMetric label="Bid ROI" value={summary.participation.return_on_spend_percent == null ? "—" : `${summary.participation.return_on_spend_percent.toFixed(1)}%`} detail={`${formatIsk(summary.participation.total_spent, true)} resolved spend`} tone={profitClass(summary.participation.return_on_spend_percent)} />
      </div>}
      {showSelling && summary.next_expiring_offer && <button className="hypernet-next-expiring" type="button" onClick={() => navigate(`hypernet/offers/${summary.next_expiring_offer!.id}`)}><Clock3 size={20} /><span><small>Next expiring offer</small><strong>{summary.next_expiring_offer.item.name}</strong><em>{summary.next_expiring_offer.nodes_sold}/{summary.next_expiring_offer.total_nodes} nodes · {countdown(summary.next_expiring_offer.remaining_seconds)}</em></span><b>{formatIsk(summary.next_expiring_offer.calculations.financials.profit, true)}</b></button>}
    </>}

    {showBidding && <p className="muted">Expired bids are fully refunded and kept in history. They do not affect bid exposure, spend, win rate, luck, or ROI statistics.</p>}
    <section className="panel hypernet-board">
      <div className="section-heading"><div><h3>{side === "combined" ? "Combined activity" : side === "seller" ? "Selling activity" : "Bidding activity"}</h3><p>{visibleCount} manual record{visibleCount === 1 ? "" : "s"}</p></div><div className="hypernet-board-controls"><ModuleFinder query={query} onQueryChange={setQuery} label="Search HyperNet records" placeholder="Item, seller, location, character…" resultCount={visibleCount} totalCount={totalCount} />
        {showSelling && <label>Offer status<select aria-label="Offer status" value={status} onChange={(event) => { ++boardRequest.current; setOffers([]); setBusy(true); setStatus(event.target.value); }}><option value="active">Active</option><option value="all">All history</option>{meta?.statuses.filter((value) => value !== "active").map((value) => <option key={value} value={value}>{value.replace(/_/g, " ")}</option>)}</select></label>}
        {showBidding && <label>Bid outcome<select aria-label="Bid outcome" value={bidOutcome} onChange={(event) => { ++boardRequest.current; setParticipations([]); setBusy(true); setBidOutcome(event.target.value); }}><option value="all">All bids</option><option value="pending">Pending</option><option value="won">Won</option><option value="lost">Lost</option><option value="expired">Expired · refunded</option><option value="cancelled">Cancelled</option></select></label>}
        <div className="hypernet-view-toggle"><button type="button" className={mode === "cards" ? "active" : ""} title="Card view" onClick={() => setMode("cards")}><LayoutGrid size={16} /></button><button type="button" className={mode === "table" ? "active" : ""} title="Dense table view" onClick={() => setMode("table")}><List size={16} /></button></div></div></div>
      {busy && <p className="muted" role="status">Loading HyperNet records…</p>}
      {side === "combined" && <h4 className="hypernet-activity-heading">Selling · {sortedOffers.length} offers</h4>}
      {showSelling && (mode === "cards" ? <div className="hypernet-offer-grid">{sortedOffers.map((offer) => <OfferCard key={offer.id} offer={offer} onOpen={() => navigate(`hypernet/offers/${offer.id}`)} />)}</div> : <div className="table-scroll"><table className="hypernet-table"><thead><tr><th>Offer</th><th>Status</th><th>Progress</th><th>Gross</th><th>Core cost</th><th>Profit/result</th><th>Remaining</th></tr></thead><tbody>{sortedOffers.map((offer) => <tr key={offer.id} onClick={() => navigate(`hypernet/offers/${offer.id}`)}><td><strong>{offer.item.name}</strong><small>{offer.seller.name} · {offer.location.name}</small></td><td><Status value={offer.status} />{offer.market_sale && <span className="hypernet-status hypernet-status-market-sold">Market sold</span>}</td><td>{offer.nodes_sold}/{offer.total_nodes}<small>{offer.organic_nodes_sold} organic · {offer.seller_owned_nodes} seeded</small></td><td>{formatIsk(offer.total_offer_price, true)}</td><td>{formatIsk(offer.calculations.financials.hypercore_cost, true)}</td><td className={profitClass(offer.market_sale?.lifecycle_profit ?? offer.final_profit ?? offer.calculations.financials.profit)}>{formatIsk(offer.market_sale?.lifecycle_profit ?? offer.final_profit ?? offer.calculations.financials.profit, true)}</td><td>{["active", "awaiting_reconciliation"].includes(offer.status) ? countdown(offer.remaining_seconds) : "—"}</td></tr>)}</tbody></table></div>)}
      {side === "combined" && <h4 className="hypernet-activity-heading">Bidding · {sortedParticipations.length} bids</h4>}
      {showBidding && (mode === "cards" ? <div className="hypernet-offer-grid">{sortedParticipations.map((bid) => <article className="hypernet-bid-card" key={bid.id}><div className="hypernet-offer-card-heading"><img src={hypernetItemIcon(bid.item)} alt="" /><span><strong>{bid.item.name}</strong><small>{bid.character.name} · seller {bid.seller_name}</small></span><Status value={bid.outcome} refunded={bid.outcome === "expired"} /></div><div className="hypernet-offer-stats"><span><strong>{bid.nodes_purchased}/{bid.total_nodes}</strong> nodes</span><span><strong>{bid.win_probability_percent.toFixed(2)}%</strong> odds</span><span><strong>{formatIsk(bid.node_price, true)}</strong> each</span><span><strong>{formatIsk(bid.total_spent, true)}</strong> {bid.outcome === "expired" ? "refunded" : "spent"}</span></div><div className="hypernet-offer-economics"><span><small>Location</small><strong>{bid.location.name}</strong></span><span><small>{bid.outcome === "pending" ? "At risk" : "Result"}</small><strong className={bid.outcome === "expired" ? "hypernet-neutral" : profitClass(bid.profit_loss ?? -bid.total_spent)}>{formatIsk(bid.profit_loss ?? -bid.total_spent, true)}</strong></span><span><small>Purchased</small><strong>{new Date(bid.created_at).toLocaleDateString()}</strong></span></div><div className="button-row"><button type="button" onClick={() => navigate(`hypernet/bids/${bid.id}/edit`)}><Pencil size={16} /> Edit</button>{bid.outcome === "pending" && <><button type="button" onClick={() => void resolveBid(bid, "expired")}><Clock3 size={16} /> Mark expired / refunded</button><button type="button" onClick={() => void resolveBid(bid, "lost")}><XCircle size={16} /> Mark lost</button><button type="button" onClick={() => void resolveBid(bid, "won")}><Trophy size={16} /> Mark won</button></>}</div></article>)}</div> : <div className="table-scroll"><table className="hypernet-table"><thead><tr><th>Bid</th><th>Outcome</th><th>Nodes / odds</th><th>Spent</th><th>Item value</th><th>Result</th><th></th></tr></thead><tbody>{sortedParticipations.map((bid) => <tr key={bid.id}><td><strong>{bid.item.name}</strong><small>{bid.character.name} · {bid.seller_name}</small></td><td><Status value={bid.outcome} refunded={bid.outcome === "expired"} /></td><td>{bid.nodes_purchased}/{bid.total_nodes}<small>{bid.win_probability_percent.toFixed(2)}%</small></td><td>{formatIsk(bid.total_spent, true)}{bid.outcome === "expired" && <small>Refunded in full</small>}</td><td>{formatIsk(bid.item_value_at_completion, true)}</td><td className={bid.outcome === "expired" ? "hypernet-neutral" : profitClass(bid.profit_loss)}>{formatIsk(bid.profit_loss, true)}</td><td><button type="button" onClick={() => navigate(`hypernet/bids/${bid.id}/edit`)}><Pencil size={16} /> Edit</button></td></tr>)}</tbody></table></div>)}
      {visibleCount === 0 && !busy && <div className="hypernet-empty"><Calculator size={28} /><strong>No matching HyperNet records</strong><p>{side === "combined" ? "Adjust the filters, plan an offer, or record a bid." : side === "seller" ? "Plan an offer or record one already running in EVE." : "Record nodes purchased on another pilot’s offer."}</p><button type="button" onClick={() => navigate(side === "seller" ? "hypernet/new" : "hypernet/bids/new")}><Plus size={17} /> Add first record</button></div>}
    </section>
    {showSelling && summary?.node_positions && <HyperNetNodeResearch summary={summary.node_positions} />}
    {showSelling && summary && <section className="panel hypernet-history-strip"><div><BarChart3 size={19} /><span><strong>Average completed profit</strong><small>{formatIsk(summary.average_profit_per_completed_offer)}</small></span></div><div><History size={19} /><span><strong>Average first organic node</strong><small>{summary.average_hours_to_first_node == null ? "Insufficient sample" : `${summary.average_hours_to_first_node.toFixed(1)} hours`}</small></span></div><div><Coins size={19} /><span><strong>Active HyperCore expense</strong><small>{formatIsk(summary.hypercore_cost)}</small></span></div></section>}
  </div>;
}
