import { Save, XCircle } from "lucide-react";
import { FormEvent, useState } from "react";

import type { ApiClient, HyperNetOffer } from "../../types/hypernet";
import { formatIsk, localInputValue } from "./hypernetPresentation";

export function HyperNetOfferEdit({ api, offer, onSaved, onCancel }: {
  api: ApiClient; offer: HyperNetOffer; onSaved: (offer: HyperNetOffer) => void; onCancel: () => void;
}) {
  const [totalNodes, setTotalNodes] = useState(offer.total_nodes);
  const [price, setPrice] = useState(offer.total_offer_price);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const minimumNodes = Math.max(1, offer.nodes_sold, offer.seller_owned_nodes,
    ...(offer.snapshots ?? []).map((row) => Math.max(row.nodes_sold, row.seller_owned_nodes)),
    (offer.participants ?? []).reduce((sum, row) => sum + row.nodes_owned, 0));

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    const form = new FormData(event.currentTarget);
    const enteredExpiry = String(form.get("expires_at"));
    try {
      const updated = await api<HyperNetOffer>(`/hypernet/offers/${offer.id}`, {
        method: "PATCH", body: JSON.stringify({
          total_nodes: totalNodes, total_offer_price: price,
          quantity: Number(form.get("quantity")),
          hypercores_required: Number(form.get("hypercores_required")),
          hypercore_unit_cost: Number(form.get("hypercore_unit_cost")),
          acquisition_cost: Number(form.get("acquisition_cost")),
          desired_profit: Number(form.get("desired_profit")),
          expires_at: enteredExpiry === localInputValue(new Date(offer.expires_at))
            ? offer.expires_at : new Date(enteredExpiry).toISOString(),
          notes: String(form.get("notes") ?? "").trim() || null,
        }),
      });
      onSaved(updated);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save offer changes"); }
    finally { setBusy(false); }
  }

  return <section className="panel hypernet-offer-edit">
    <div className="section-heading compact"><div><h4>Edit offer</h4><p>Correct the recorded offer details. Sold and seeded node counts stay unchanged.</p></div><button type="button" className="icon-button" title="Cancel offer edit" disabled={busy} onClick={onCancel}><XCircle size={17} /></button></div>
    <form className="stacked-form" onSubmit={save}>
      <div className="form-grid three">
        <label>Total nodes<input name="total_nodes" type="number" min={minimumNodes} max="512" required value={totalNodes} onChange={(event) => setTotalNodes(Number(event.target.value))} /><small>At least {minimumNodes}, based on recorded progress.</small></label>
        <label>Total offer price (ISK)<input name="total_offer_price" type="number" min="0" step="0.01" required value={price} onChange={(event) => setPrice(Number(event.target.value))} /><small>Total for all nodes, not the price of one node.</small></label>
        <label>Quantity<input name="quantity" type="number" min="1" defaultValue={offer.quantity} required /></label>
        <label>HyperCores required<input name="hypercores_required" type="number" min="0" defaultValue={offer.hypercores_required} required /></label>
        <label>HyperCore unit cost (ISK)<input name="hypercore_unit_cost" type="number" min="0" step="0.01" defaultValue={offer.hypercore_unit_cost} required /></label>
        <label>Acquisition cost (ISK)<input name="acquisition_cost" type="number" min="0" step="0.01" defaultValue={offer.acquisition_cost} required /></label>
        <label>Desired profit (ISK)<input name="desired_profit" type="number" step="0.01" defaultValue={offer.desired_profit} required /></label>
        <label>Expires<input name="expires_at" type="datetime-local" defaultValue={localInputValue(new Date(offer.expires_at))} required /></label>
      </div>
      <p className="muted">{offer.nodes_sold}/{totalNodes || "—"} nodes sold · {offer.seller_owned_nodes} seeded · {totalNodes > 0 ? formatIsk(price / totalNodes) : "—"} per node · {totalNodes > 0 ? (offer.seller_owned_nodes / totalNodes * 100).toFixed(2) : "—"}% seller win chance</p>
      <label>Notes<textarea name="notes" rows={3} defaultValue={offer.notes ?? ""} /></label>
      {error && <div className="mini-alert" role="alert">{error}</div>}
      <div className="button-row"><button type="button" disabled={busy} onClick={onCancel}>Cancel</button><button type="submit" disabled={busy}><Save size={17} /> {busy ? "Saving" : "Save offer changes"}</button></div>
    </form>
  </section>;
}
