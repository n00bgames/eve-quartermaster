import { useState, type FormEvent } from "react";
import { Pencil, Save, ShoppingCart, Trash2 } from "lucide-react";
import type { ApiClient, HyperNetOffer } from "../../types/hypernet";
import { formatIsk, localInputValue, profitClass } from "./hypernetPresentation";

export function HyperNetMarketSale({ api, offer, onChanged }: { api: ApiClient; offer: HyperNetOffer; onChanged: (offer: HyperNetOffer) => void }) {
  const [editing, setEditing] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sale = offer.market_sale;
  async function remove() {
    setBusy(true); setError("");
    try { onChanged(await api<HyperNetOffer>(`/hypernet/offers/${offer.id}/market-sale`, { method: "DELETE" })); setRemoving(false); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to remove sale"); }
    finally { setBusy(false); }
  }
  return <section className="panel hypernet-market-sale">
    <div className="section-heading compact"><div><h4>Item disposition · {sale ? "Sold on market" : "Retained after expiration"}</h4><p>{sale ? "This item’s market sale closes its recorded lifecycle. The HyperNet offer remains expired." : "Record a completed market sale to follow this item from acquisition through its expired listing to liquidation."}</p></div>
      {!editing && <div className="button-row"><button type="button" disabled={busy || removing} onClick={() => { setEditing(true); setError(""); }}>{sale ? <Pencil size={16} /> : <ShoppingCart size={16} />}{sale ? "Edit market sale" : "Record market sale"}</button>{sale && <button type="button" className="danger" disabled={busy || removing} onClick={() => setRemoving(true)}><Trash2 size={16} /> Remove sale</button>}</div>}
    </div>
    {error && <div className="mini-alert" role="alert">{error}</div>}
    {removing && <div className="hypernet-warning"><span>Remove this recorded sale? The item will return to retained and lifetime totals will revert to the expired-offer result.</span><div className="button-row"><button className="danger" disabled={busy} onClick={() => void remove()}>Confirm removal</button><button disabled={busy} onClick={() => setRemoving(false)}>Cancel</button></div></div>}
    {editing ? <MarketSaleForm api={api} offer={offer} onCancel={() => setEditing(false)} onSaved={updated => { onChanged(updated); setEditing(false); }} /> : sale && <>
      <div className="hypernet-financial-grid">{[
        ["Gross market sale", sale.gross_proceeds], ["Sales tax", sale.sales_tax], ["Broker fee", sale.broker_fee], ["Other sale fees", sale.other_fees],
        ["Net sale proceeds", sale.net_proceeds], ["Acquisition cost", sale.acquisition_cost], ["Expired listing · HyperCores", sale.hypercore_cost], ["Lifecycle result", sale.lifecycle_profit],
      ].map(([label, value]) => <div className="hypernet-financial-fact" key={label}><span>{label}</span><strong className={label === "Lifecycle result" ? profitClass(Number(value)) : ""}>{formatIsk(Number(value))}</strong></div>)}</div>
      <p>Sold {new Date(sale.sold_at).toLocaleString()} · Entire recorded lot ({offer.quantity} item{offer.quantity === 1 ? "" : "s"}).</p>
      {sale.note && <p style={{ whiteSpace: "pre-wrap" }}>{sale.note}</p>}
      <p className="muted">Lifecycle result = net sale proceeds − recorded acquisition cost − actual HyperCore cost. Refunded seeded nodes add no loss. This replaces the expired offer’s result in lifetime totals; it is not added a second time. HyperNet profit overrides do not alter this cost-based result.</p>
    </>}
  </section>;
}

function MarketSaleForm({ api, offer, onSaved, onCancel }: { api: ApiClient; offer: HyperNetOffer; onSaved: (offer: HyperNetOffer) => void; onCancel: () => void }) {
  const sale = offer.market_sale;
  const [initialSoldAt] = useState(sale?.sold_at ?? new Date().toISOString());
  const [gross, setGross] = useState(sale ? String(sale.gross_proceeds) : "");
  const [tax, setTax] = useState(String(sale?.sales_tax ?? 0));
  const [broker, setBroker] = useState(String(sale?.broker_fee ?? 0));
  const [other, setOther] = useState(String(sale?.other_fees ?? 0));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cores = offer.actual_hypercore_cost ?? offer.hypercores_required * offer.hypercore_unit_cost;
  const net = gross === "" ? null : Number(gross) - Number(tax) - Number(broker) - Number(other);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    const date = String(form.get("sold_at"));
    try {
      const updated = await api<HyperNetOffer>(`/hypernet/offers/${offer.id}/market-sale`, { method: "PUT", body: JSON.stringify({
        sold_at: date === localInputValue(new Date(initialSoldAt)) ? initialSoldAt : new Date(date).toISOString(),
        gross_proceeds: gross, sales_tax: tax, broker_fee: broker, other_fees: other, note: String(form.get("note") ?? "").trim() || null,
      }) }); onSaved(updated);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to save market sale"); }
    finally { setBusy(false); }
  }
  return <form className="stacked-form" onSubmit={save}>
    <p>Enter actual totals for all {offer.quantity} item{offer.quantity === 1 ? "" : "s"} on this offer, not a price per unit or an unfilled sell order.</p>
    <div className="form-grid three">
      <label>Sold at<input name="sold_at" type="datetime-local" required disabled={busy} defaultValue={localInputValue(new Date(initialSoldAt))} /></label>
      <label>Gross market proceeds (ISK)<input type="number" min="0" step="0.01" required disabled={busy} value={gross} onChange={e => setGross(e.target.value)} /></label>
      <label>Sales tax (ISK)<input type="number" min="0" step="0.01" required disabled={busy} value={tax} onChange={e => setTax(e.target.value)} /></label>
      <label>Broker fee (ISK)<input type="number" min="0" step="0.01" required disabled={busy} value={broker} onChange={e => setBroker(e.target.value)} /></label>
      <label>Other sale fees (ISK)<input type="number" min="0" step="0.01" required disabled={busy} value={other} onChange={e => setOther(e.target.value)} /></label>
    </div>
    <div className="hypernet-bid-preview"><span><small>Net sale proceeds</small><strong>{formatIsk(net)}</strong></span><span><small>Acquisition + HyperCores</small><strong>{formatIsk(offer.acquisition_cost + cores)}</strong></span><span><small>Lifecycle result</small><strong className={profitClass(net == null ? null : net - offer.acquisition_cost - cores)}>{formatIsk(net == null ? null : net - offer.acquisition_cost - cores)}</strong></span></div>
    <p className="muted">Fees are total ISK amounts. To correct the acquisition or HyperCore cost, use Edit ended offer. The lifecycle result recalculates from those recorded costs, including any estimates you entered.</p>
    <label>Market sale note<textarea name="note" rows={3} maxLength={2000} disabled={busy} defaultValue={sale?.note ?? ""} /></label>
    {error && <div className="mini-alert" role="alert">{error}</div>}
    <div className="button-row"><button type="button" disabled={busy} onClick={onCancel}>Cancel</button><button disabled={busy}><Save size={16} />{busy ? "Saving…" : "Save market sale"}</button></div>
  </form>;
}
