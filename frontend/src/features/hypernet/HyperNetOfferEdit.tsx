import { Save, XCircle } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import type { ApiClient, HyperNetLocationCandidate, HyperNetMeta, HyperNetOffer } from "../../types/hypernet";
import { formatIsk, localInputValue } from "./hypernetPresentation";

export function HyperNetOfferEdit({ api, offer, onSaved, onCancel }: {
  api: ApiClient; offer: HyperNetOffer; onSaved: (offer: HyperNetOffer) => void; onCancel: () => void;
}) {
  const [totalNodes, setTotalNodes] = useState(offer.total_nodes);
  const [price, setPrice] = useState(offer.total_offer_price);
  const [sellerId, setSellerId] = useState(offer.seller.id);
  const [characters, setCharacters] = useState<HyperNetMeta["seller_characters"]>([]);
  const [characterError, setCharacterError] = useState(false);
  const [characterRequest, setCharacterRequest] = useState(0);
  const [location, setLocation] = useState({ id: offer.location.id ?? null, name: offer.location.name === "Location not recorded" ? "" : offer.location.name });
  const [locationChanged, setLocationChanged] = useState(false);
  const [locationQuery, setLocationQuery] = useState("");
  const [locations, setLocations] = useState<HyperNetLocationCandidate[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const minimumNodes = Math.max(1, offer.nodes_sold, offer.seller_owned_nodes,
    ...(offer.snapshots ?? []).map((row) => Math.max(row.nodes_sold, row.seller_owned_nodes)),
    (offer.participants ?? []).reduce((sum, row) => sum + row.nodes_owned, 0));

  useEffect(() => {
    let cancelled = false;
    setCharacterError(false);
    void api<HyperNetMeta>("/hypernet/meta")
      .then((meta) => { if (!cancelled) setCharacters(meta.seller_characters); })
      .catch(() => { if (!cancelled) setCharacterError(true); });
    return () => { cancelled = true; };
  }, [api, characterRequest]);

  useEffect(() => {
    let cancelled = false;
    if (locationQuery.trim().length < 2) { setLocations([]); return; }
    const timer = window.setTimeout(() => {
      void api<HyperNetLocationCandidate[]>(`/hypernet/search/locations?q=${encodeURIComponent(locationQuery.trim())}`)
        .then((rows) => { if (!cancelled) setLocations(rows); })
        .catch(() => { if (!cancelled) setLocations([]); });
    }, 220);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [api, locationQuery]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    const form = new FormData(event.currentTarget);
    const enteredExpiry = String(form.get("expires_at"));
    try {
      const updated = await api<HyperNetOffer>(`/hypernet/offers/${offer.id}`, {
        method: "PATCH", body: JSON.stringify({
          total_nodes: totalNodes, total_offer_price: price,
          ...(sellerId !== offer.seller.id ? { seller_character_id: sellerId } : {}),
          ...(locationChanged ? { location_id: location.id, location_name: location.name.trim() || null } : {}),
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
        <label>Seller character<select aria-label="Seller character" value={sellerId} disabled={busy} onChange={(event) => setSellerId(Number(event.target.value))} required>{!characters.some((row) => row.id === offer.seller.id) && <option value={offer.seller.id}>{offer.seller.name} (current)</option>}{characters.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select><small>Correct the pilot who posted this offer. Node counts and participant observations stay unchanged.</small></label>
        <label className="hypernet-search-field">Offer location<input name="location_name" maxLength={500} value={location.name} placeholder="Search or enter a station name" onChange={(event) => { setLocation({ id: null, name: event.target.value }); setLocationChanged(true); setLocationQuery(event.target.value); setLocations([]); }} />{locations.length > 0 && <div className="hypernet-search-menu">{locations.map((row) => <button type="button" key={`${row.source}-${row.id ?? row.eve_location_id}`} onClick={() => { setLocation({ id: row.id ?? null, name: row.name }); setLocationChanged(true); setLocationQuery(""); setLocations([]); }}><span><strong>{row.name}</strong><small>{row.source === "eqm" ? "Known EQM location" : "SDE station"}</small></span></button>)}</div>}<small>Select a search result or enter the location manually. Clear to remove it.</small></label>
        <label>Total nodes<input name="total_nodes" type="number" min={minimumNodes} max="512" required value={totalNodes} onChange={(event) => setTotalNodes(Number(event.target.value))} /><small>At least {minimumNodes}, based on recorded progress.</small></label>
        <label>Total offer price (ISK)<input name="total_offer_price" type="number" min="0" step="0.01" required value={price} onChange={(event) => setPrice(Number(event.target.value))} /><small>Total for all nodes, not the price of one node.</small></label>
        <label>Quantity<input name="quantity" type="number" min="1" defaultValue={offer.quantity} required /></label>
        <label>HyperCores required<input name="hypercores_required" type="number" min="0" defaultValue={offer.hypercores_required} required /></label>
        <label>HyperCore unit cost (ISK)<input name="hypercore_unit_cost" type="number" min="0" step="0.01" defaultValue={offer.hypercore_unit_cost} required /></label>
        <label>Acquisition cost (ISK)<input name="acquisition_cost" type="number" min="0" step="0.01" defaultValue={offer.acquisition_cost} required /></label>
        <label>Desired profit (ISK)<input name="desired_profit" type="number" step="0.01" defaultValue={offer.desired_profit} required /></label>
        <label>Expires<input name="expires_at" type="datetime-local" defaultValue={localInputValue(new Date(offer.expires_at))} required /></label>
      </div>
      {characterError && <div className="mini-alert" role="alert">Could not load linked characters. You can still edit other details. <button type="button" disabled={busy} onClick={() => setCharacterRequest((value) => value + 1)}>Retry characters</button></div>}
      <p className="muted">{offer.nodes_sold}/{totalNodes || "—"} nodes sold · {offer.seller_owned_nodes} seeded · {totalNodes > 0 ? formatIsk(price / totalNodes) : "—"} per node · {totalNodes > 0 ? (offer.seller_owned_nodes / totalNodes * 100).toFixed(2) : "—"}% seller win chance</p>
      <label>Notes<textarea name="notes" rows={3} defaultValue={offer.notes ?? ""} /></label>
      {error && <div className="mini-alert" role="alert">{error}</div>}
      <div className="button-row"><button type="button" disabled={busy} onClick={onCancel}>Cancel</button><button type="submit" disabled={busy}><Save size={17} /> {busy ? "Saving" : "Save offer changes"}</button></div>
    </form>
  </section>;
}
