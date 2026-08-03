import { ArrowLeft, CheckCircle2, Clock3, RefreshCw, Save, ShieldAlert, XCircle } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import type { ApiClient, HyperNetOffer } from "../../types/hypernet";
import { countdown, formatIsk, localInputValue, profitClass } from "./hypernetPresentation";


function FinancialFact({ label, value, formula, tone }: { label: string; value: string; formula: string; tone?: string }) {
  return <div className={`hypernet-financial-fact ${tone ?? ""}`} title={formula}><span>{label}</span><strong>{value}</strong><small>{formula}</small></div>;
}

function ProgressChart({ offer }: { offer: HyperNetOffer }) {
  const rows = offer.snapshots ?? [];
  if (rows.length < 2) return <p className="empty">Add another progress snapshot to begin the timeline chart.</p>;
  const width = 760; const height = 170; const pad = 22;
  const minTime = new Date(rows[0].captured_at).getTime();
  const maxTime = Math.max(minTime + 1, new Date(rows[rows.length - 1].captured_at).getTime());
  const points = rows.map((row) => ({
    x: pad + (new Date(row.captured_at).getTime() - minTime) / (maxTime - minTime) * (width - pad * 2),
    y: height - pad - row.nodes_sold / offer.total_nodes * (height - pad * 2),
    row,
  }));
  return <svg className="hypernet-progress-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Progress history for ${offer.item.name}`}><line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} /><line x1={pad} y1={pad} x2={pad} y2={height - pad} /><polyline points={points.map((point) => `${point.x},${point.y}`).join(" ")} /><g>{points.map((point) => <circle key={point.row.id} cx={point.x} cy={point.y} r="5"><title>{`${new Date(point.row.captured_at).toLocaleString()} · ${point.row.nodes_sold}/${offer.total_nodes} · ${point.row.organic_nodes_sold} organic · ${point.row.seller_owned_nodes} seeded`}</title></circle>)}</g></svg>;
}

export function HyperNetOfferDetail({ api, offer, onBack, onChanged }: { api: ApiClient; offer: HyperNetOffer; onBack: () => void; onChanged: (offer: HyperNetOffer) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reconcileStatus, setReconcileStatus] = useState<"completed" | "expired" | null>(null);
  const terminal = ["completed", "expired", "cancelled", "invalid"].includes(offer.status);
  const f = offer.calculations.financials;
  const scenario = offer.calculations.seeded_scenario;
  const latestMarket = offer.snapshots?.[offer.snapshots.length - 1];
  const externalParticipants = (offer.participants ?? []).filter((row) => !row.is_seller);
  const timeline = useMemo(() => [...(offer.snapshots ?? [])].reverse(), [offer.snapshots]);

  async function activate() {
    setBusy(true); setError(null);
    try { onChanged(await api<HyperNetOffer>(`/hypernet/offers/${offer.id}`, { method: "PATCH", body: JSON.stringify({ status: "active" }) })); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to activate offer"); }
    finally { setBusy(false); }
  }

  async function addSnapshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const nodesSold = Number(form.get("nodes_sold") || 0);
    const seeded = Number(form.get("seller_owned_nodes") || 0);
    const participantLines = String(form.get("participants") || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const participants = participantLines.map((line) => {
      const [name, nodes = "0", marker = ""] = line.split("|").map((value) => value.trim());
      return { participant_name: name, nodes_owned: Number(nodes || 0), is_seller: marker.toLowerCase() === "seeded" };
    });
    if (seeded > 0 && !participants.some((row) => row.is_seller)) participants.push({ participant_name: offer.seller.name, nodes_owned: seeded, is_seller: true });
    try {
      onChanged(await api<HyperNetOffer>(`/hypernet/offers/${offer.id}/snapshots`, { method: "POST", body: JSON.stringify({
        captured_at: new Date(String(form.get("captured_at"))).toISOString(), nodes_sold: nodesSold, seller_owned_nodes: seeded,
        unique_participants: Number(form.get("unique_participants") || participants.length),
        jita_buy: Number(form.get("jita_buy")) || null, jita_sell: Number(form.get("jita_sell")) || null,
        local_buy: Number(form.get("local_buy")) || null, local_sell: Number(form.get("local_sell")) || null,
        hypercore_buy: Number(form.get("hypercore_buy")) || null, hypercore_sell: Number(form.get("hypercore_sell")) || null,
        note: form.get("note") || null, participants,
      }) }));
      formElement.reset();
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save progress snapshot"); }
    finally { setBusy(false); }
  }

  async function reconcile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!reconcileStatus) return;
    setBusy(true); setError(null); const form = new FormData(event.currentTarget);
    const optional = (name: string) => String(form.get(name) || "").trim() ? Number(form.get(name)) : null;
    try {
      onChanged(await api<HyperNetOffer>(`/hypernet/offers/${offer.id}/reconcile`, { method: "POST", body: JSON.stringify({
        status: reconcileStatus, reconciled_at: new Date(String(form.get("reconciled_at"))).toISOString(),
        winner: reconcileStatus === "completed" ? form.get("winner") : "unknown",
        seller_owned_nodes: Number(form.get("seller_owned_nodes") || offer.seller_owned_nodes),
        unique_participants: Number(form.get("unique_participants") || offer.unique_participants),
        final_payout: optional("final_payout"), actual_hypercore_cost: optional("actual_hypercore_cost"),
        final_market_value: optional("final_market_value"), final_profit: optional("final_profit"), note: form.get("note") || null,
      }) }));
      setReconcileStatus(null);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to reconcile offer"); }
    finally { setBusy(false); }
  }

  return <div className="hypernet-detail-page">
    <section className="panel hypernet-detail-hero">
      <div className="section-heading"><div><button type="button" className="icon-button" title="Back to HyperNet Tracker" onClick={onBack}><ArrowLeft size={18} /></button><span className="eyebrow">{offer.status.replace(/_/g, " ")}</span><h3><img src={`https://images.evetech.net/types/${offer.item.type_id}/icon?size=64`} alt="" /> {offer.quantity > 1 ? `${offer.quantity}× ` : ""}{offer.item.name}</h3><p>{offer.seller.name} · {offer.location.name}</p></div><div className="button-row">{offer.status === "draft" && <button type="button" disabled={busy} onClick={() => void activate()}><CheckCircle2 size={17} /> Activate</button>}{!terminal && <><button type="button" disabled={busy} onClick={() => setReconcileStatus("completed")}><CheckCircle2 size={17} /> Complete</button><button type="button" className="danger" disabled={busy} onClick={() => setReconcileStatus("expired")}><XCircle size={17} /> Expire</button></>}</div></div>
      <div className="hypernet-progress-summary"><span><strong>{offer.nodes_sold}/{offer.total_nodes}</strong> nodes sold</span><span><strong>{offer.organic_nodes_sold}</strong> organic</span><span><strong>{offer.seller_owned_nodes}</strong> seeded</span><span><strong>{offer.unique_participants}</strong> participants</span><span><Clock3 size={15} /><strong>{terminal ? offer.status : countdown(offer.remaining_seconds)}</strong></span></div>
      <div className="hypernet-progress-track"><i style={{ width: `${offer.filled_percent}%` }} /><b style={{ width: `${offer.total_nodes ? offer.seller_owned_nodes / offer.total_nodes * 100 : 0}%` }} /></div>
    </section>

    {error && <div className="mini-alert">{error}</div>}
    {offer.status === "awaiting_reconciliation" && <div className="hypernet-warning"><ShieldAlert size={19} /><span><strong>All nodes are recorded, but the result is unresolved.</strong> Reconcile the winner, payout, core cost, and retained/transferred item before treating this as realized profit.</span></div>}

    <section className="panel"><div className="section-heading compact"><div><h4>Financial breakdown</h4><p>Hover any result to see the formula.</p></div></div><div className="hypernet-financial-grid">
      <FinancialFact label="Gross offer value" value={formatIsk(f.gross_offer_value)} formula="total offer price" />
      <FinancialFact label="Price per node" value={formatIsk(f.node_price)} formula="gross / total nodes" />
      <FinancialFact label="Completion fee" value={formatIsk(f.completion_fee)} formula="gross × 5%" />
      <FinancialFact label="HyperCore cost" value={formatIsk(f.hypercore_cost)} formula="required cores × acquired unit cost" />
      <FinancialFact label="Expected payout" value={formatIsk(f.payout_after_fee)} formula="gross − 5% fee" />
      <FinancialFact label="Net proceeds" value={formatIsk(f.net_proceeds)} formula="payout − HyperCore cost" />
      <FinancialFact label="Base profit" value={formatIsk(f.profit)} formula="net proceeds − acquisition cost; seeded-node outcomes shown separately" tone={profitClass(f.profit)} />
      <FinancialFact label="Return on cost" value={f.return_on_cost_percent == null ? "—" : `${f.return_on_cost_percent.toFixed(2)}%`} formula="base profit / acquisition cost" tone={profitClass(f.return_on_cost_percent)} />
      <FinancialFact label="Break-even offer" value={formatIsk(f.break_even_offer_price)} formula="(acquisition + HyperCores) / 0.95" />
      <FinancialFact label="Final recorded result" value={formatIsk(offer.final_profit)} formula="manual reconciliation; expired offers default to realized HyperCore loss" tone={profitClass(offer.final_profit)} />
    </div></section>

    <div className="hypernet-detail-columns">
      <section className="panel"><div className="section-heading compact"><div><h4>Seeded-node risk</h4><p>Seller purchases remain separate from organic demand.</p></div></div><dl className="hypernet-scenario-list"><dt>Seller win probability</dt><dd>{scenario.seller_win_probability_percent.toFixed(2)}%</dd><dt>Seeded-node spend</dt><dd>{formatIsk(scenario.seller_node_spend)}</dd><dt>External buyer wins</dt><dd className={profitClass(scenario.cash_result_if_external_wins)}>{formatIsk(scenario.cash_result_if_external_wins)}</dd><dt>Seller wins · cash</dt><dd>{formatIsk(scenario.cash_result_if_seller_wins)}</dd><dt>Seller wins · mark to Jita</dt><dd className={profitClass(scenario.seller_win_mark_to_jita_result)}>{formatIsk(scenario.seller_win_mark_to_jita_result)}</dd><dt>Expected monetary result</dt><dd className={profitClass(scenario.expected_monetary_result)}>{formatIsk(scenario.expected_monetary_result)}</dd><dt>Capital tied up</dt><dd>{formatIsk(scenario.capital_tied_up)}</dd></dl><p className="muted">If the seller wins, the item remains an asset. Cash and mark-to-market outcomes are shown independently.</p></section>
      <section className="panel"><div className="section-heading compact"><div><h4>Offer observations</h4><p>{offer.calculations.progress.hours_to_first_organic_node == null ? "No organic sale recorded yet" : `First organic node after ${offer.calculations.progress.hours_to_first_organic_node.toFixed(1)} hours`}</p></div></div><dl className="hypernet-scenario-list"><dt>Organic velocity</dt><dd>{offer.calculations.progress.organic_nodes_per_hour == null ? "—" : `${offer.calculations.progress.organic_nodes_per_hour.toFixed(2)} nodes/hour`}</dd><dt>Projected completion</dt><dd>{offer.calculations.progress.estimated_hours_to_completion == null ? "Insufficient data" : `${offer.calculations.progress.estimated_hours_to_completion.toFixed(1)} hours`}</dd><dt>Jita sell snapshot</dt><dd>{formatIsk(latestMarket?.jita_sell)}</dd><dt>Local sell snapshot</dt><dd>{formatIsk(latestMarket?.local_sell)}</dd><dt>Premium over Jita</dt><dd>{f.premium_over_jita_percent == null ? "—" : `${f.premium_over_jita_percent.toFixed(2)}%`}</dd><dt>Premium over local</dt><dd>{f.premium_over_local_percent == null ? "—" : `${f.premium_over_local_percent.toFixed(2)}%`}</dd></dl></section>
    </div>

    <section className="panel"><div className="section-heading compact"><div><h4>Progress history</h4><p>Manual snapshots keep seeded and organic nodes distinct.</p></div></div><ProgressChart offer={offer} /><div className="hypernet-timeline">{timeline.map((row) => <article key={row.id}><span>{new Date(row.captured_at).toLocaleString()}</span><strong>{row.nodes_sold}/{offer.total_nodes} sold</strong><em>{row.organic_nodes_sold} organic · {row.seller_owned_nodes} seeded</em><small>{row.note || `${row.unique_participants} unique participants`}</small></article>)}</div></section>

    {!terminal && <section className="panel"><div className="section-heading compact"><div><h4>Add progress snapshot</h4><p>Use cumulative counts from the in-game offer.</p></div></div><form className="stacked-form" onSubmit={addSnapshot}><div className="form-grid three"><label>Captured at<input name="captured_at" type="datetime-local" defaultValue={localInputValue(new Date())} required /></label><label>Nodes sold<input name="nodes_sold" type="number" min="0" max={offer.total_nodes} defaultValue={offer.nodes_sold} required /></label><label>Seeded nodes<input name="seller_owned_nodes" type="number" min="0" max={offer.total_nodes} defaultValue={offer.seller_owned_nodes} required /></label><label>Unique participants<input name="unique_participants" type="number" min="0" defaultValue={offer.unique_participants} /></label><label>Jita buy<input name="jita_buy" type="number" min="0" step="0.01" /></label><label>Jita sell<input name="jita_sell" type="number" min="0" step="0.01" defaultValue={latestMarket?.jita_sell ?? ""} /></label><label>Local buy<input name="local_buy" type="number" min="0" step="0.01" /></label><label>Local sell<input name="local_sell" type="number" min="0" step="0.01" defaultValue={latestMarket?.local_sell ?? ""} /></label><label>HyperCore buy<input name="hypercore_buy" type="number" min="0" step="0.01" /></label><label>HyperCore sell<input name="hypercore_sell" type="number" min="0" step="0.01" /></label></div><label>Participants (optional)<textarea name="participants" rows={3} placeholder={`Character Name | 1\n${offer.seller.name} | ${offer.seller_owned_nodes} | seeded`} /><small>One participant per line: name | cumulative nodes | optional “seeded”. EQM adds the seller row automatically when seeded nodes are entered.</small></label><label>Observation<textarea name="note" rows={3} placeholder="Shared in corp chat; first organic node arrived after promotion…" /></label><button disabled={busy}><Save size={17} /> {busy ? "Saving" : "Save snapshot"}</button></form></section>}

    <section className="panel"><div className="section-heading compact"><div><h4>Participant list</h4><p>Manual observations only; no HyperNet participant data is assumed from ESI.</p></div></div><div className="hypernet-participant-list">{(offer.participants ?? []).map((row) => <article key={row.id} className={row.is_seller ? "seeded" : "organic"}><strong>{row.participant_name}</strong><span>{row.nodes_owned} node{row.nodes_owned === 1 ? "" : "s"}</span><em>{row.is_seller ? "Seeded nodes" : "External participant"}</em></article>)}{externalParticipants.length === 0 && offer.seller_owned_nodes === 0 && <p className="empty">No participant identities recorded yet.</p>}</div></section>

    {reconcileStatus && !terminal && <section className="panel hypernet-reconcile"><div className="section-heading compact"><div><h4>{reconcileStatus === "completed" ? "Complete and reconcile" : "Record expiration"}</h4><p>{reconcileStatus === "expired" ? "The item remains retained, node purchases are treated as refunded, and HyperCores become the realized loss." : "Record the actual payout, winner, costs, and final item value."}</p></div><button type="button" className="icon-button" onClick={() => setReconcileStatus(null)}><XCircle size={17} /></button></div><form className="stacked-form" onSubmit={reconcile}><div className="form-grid three"><label>Reconciled at<input name="reconciled_at" type="datetime-local" defaultValue={localInputValue(new Date())} required /></label>{reconcileStatus === "completed" && <label>Winner<select name="winner" defaultValue="external"><option value="external">External participant</option><option value="seller">Seller won item back</option></select></label>}<label>Final seeded nodes<input name="seller_owned_nodes" type="number" min="0" max={offer.total_nodes} defaultValue={offer.seller_owned_nodes} /></label><label>Unique participants<input name="unique_participants" type="number" min="0" defaultValue={offer.unique_participants} /></label>{reconcileStatus === "completed" && <label>Final payout<input name="final_payout" type="number" min="0" step="0.01" defaultValue={offer.payout ?? f.payout_after_fee} /></label>}<label>Actual HyperCore cost<input name="actual_hypercore_cost" type="number" min="0" step="0.01" defaultValue={f.hypercore_cost} /></label>{reconcileStatus === "completed" && <label>Final item market value<input name="final_market_value" type="number" min="0" step="0.01" defaultValue={latestMarket?.jita_sell ?? ""} /></label>}<label>Final profit override<input name="final_profit" type="number" step="0.01" placeholder="Leave blank to calculate" /></label></div><label>Reconciliation note<textarea name="note" rows={3} /></label><button className={reconcileStatus === "expired" ? "danger" : ""} disabled={busy}>{reconcileStatus === "completed" ? <CheckCircle2 size={17} /> : <XCircle size={17} />} {busy ? "Saving" : reconcileStatus === "completed" ? "Record completion" : "Record expiration"}</button></form></section>}
    {busy && <div className="hypernet-working"><RefreshCw className="spin" size={16} /> Updating manual HyperNet record…</div>}
  </div>;
}
