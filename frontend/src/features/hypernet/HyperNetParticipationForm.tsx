import { Plus, Search, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import type { ApiClient, HyperNetLocationCandidate, HyperNetMeta, HyperNetParticipation, HyperNetTypeCandidate } from "../../types/hypernet";
import { localInputValue } from "./hypernetPresentation";


export function HyperNetParticipationForm({ api, meta, onSaved, onCancel }: { api: ApiClient; meta: HyperNetMeta; onSaved: (bid: HyperNetParticipation) => void; onCancel: () => void }) {
  const [draft, setDraft] = useState({
    characterId: meta.seller_characters[0]?.id ?? 0, typeId: 0, itemName: "", sellerName: "",
    locationId: null as number | null, locationName: "", reference: "", totalNodes: 8, nodesPurchased: 1,
    nodePrice: 0, createdAt: localInputValue(new Date()), notes: "",
  });
  const [types, setTypes] = useState<HyperNetTypeCandidate[]>([]);
  const [locations, setLocations] = useState<HyperNetLocationCandidate[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const update = <K extends keyof typeof draft>(key: K, value: (typeof draft)[K]) => setDraft((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    if (draft.itemName.trim().length < 2 || draft.typeId) { setTypes([]); return; }
    const timer = window.setTimeout(() => void api<HyperNetTypeCandidate[]>(`/hypernet/search/types?q=${encodeURIComponent(draft.itemName.trim())}`).then(setTypes).catch(() => setTypes([])), 220);
    return () => window.clearTimeout(timer);
  }, [api, draft.itemName, draft.typeId]);

  useEffect(() => {
    if (draft.locationName.trim().length < 2 || draft.locationId) { setLocations([]); return; }
    const timer = window.setTimeout(() => void api<HyperNetLocationCandidate[]>(`/hypernet/search/locations?q=${encodeURIComponent(draft.locationName.trim())}`).then(setLocations).catch(() => setLocations([])), 220);
    return () => window.clearTimeout(timer);
  }, [api, draft.locationName, draft.locationId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null);
    if (!draft.typeId) { setError("Choose an item from the imported EVE type results."); return; }
    if (draft.nodesPurchased > draft.totalNodes) { setError("Nodes purchased cannot exceed total nodes."); return; }
    setBusy(true);
    try {
      const bid = await api<HyperNetParticipation>("/hypernet/participations", { method: "POST", body: JSON.stringify({
        character_id: draft.characterId, item_type_id: draft.typeId, seller_name: draft.sellerName,
        location_id: draft.locationId, location_name: draft.locationName || null,
        external_offer_reference: draft.reference || null, total_nodes: draft.totalNodes,
        nodes_purchased: draft.nodesPurchased, node_price: draft.nodePrice,
        created_at: new Date(draft.createdAt).toISOString(), notes: draft.notes || null,
      }) });
      onSaved(bid);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save HyperNet bid"); }
    finally { setBusy(false); }
  }

  const total = draft.nodePrice * draft.nodesPurchased;
  const odds = draft.totalNodes ? draft.nodesPurchased / draft.totalNodes * 100 : 0;
  return <section className="panel hypernet-offer-form">
    <div className="section-heading"><div><span className="eyebrow">Buyer-side tracking</span><h3>Record HyperNet nodes purchased</h3><p>Track a bid you made on another pilot’s offer and reconcile it as won or lost.</p></div><button type="button" className="icon-button" onClick={onCancel}><X size={18} /></button></div>
    <form onSubmit={submit}>
      <div className="hypernet-form-fields">
        <div className="form-grid three">
          <label>Buyer character<select value={draft.characterId} onChange={(event) => update("characterId", Number(event.target.value))} required><option value={0}>Choose character</option>{meta.seller_characters.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
          <label className="hypernet-search-field">Item<input value={draft.itemName} onChange={(event) => setDraft((current) => ({ ...current, itemName: event.target.value, typeId: 0 }))} placeholder="Nyx" required />{types.length > 0 && <div className="hypernet-search-menu">{types.map((row) => <button type="button" key={row.type_id} onClick={() => setDraft((current) => ({ ...current, typeId: row.type_id, itemName: row.name }))}><Search size={14} /><span><strong>{row.name}</strong><small>{row.group ?? row.category}</small></span></button>)}</div>}</label>
          <label>Offer seller<input value={draft.sellerName} onChange={(event) => update("sellerName", event.target.value)} required /></label>
          <label className="hypernet-search-field">Location<input value={draft.locationName} onChange={(event) => setDraft((current) => ({ ...current, locationName: event.target.value, locationId: null }))} />{locations.length > 0 && <div className="hypernet-search-menu">{locations.map((row) => <button type="button" key={`${row.source}-${row.id ?? row.eve_location_id}`} onClick={() => setDraft((current) => ({ ...current, locationId: row.id ?? null, locationName: row.name }))}><span><strong>{row.name}</strong><small>{row.source}</small></span></button>)}</div>}</label>
          <label>Offer reference<input value={draft.reference} onChange={(event) => update("reference", event.target.value)} placeholder="Optional in-game reference" /></label>
          <label>Purchased at<input type="datetime-local" value={draft.createdAt} onChange={(event) => update("createdAt", event.target.value)} required /></label>
          <label>Total offer nodes<input type="number" min="1" max="512" value={draft.totalNodes} onChange={(event) => update("totalNodes", Number(event.target.value))} required /></label>
          <label>Nodes purchased<input type="number" min="1" max={draft.totalNodes} value={draft.nodesPurchased} onChange={(event) => update("nodesPurchased", Number(event.target.value))} required /></label>
          <label>Price per node (ISK)<input type="number" min="0" step="0.01" value={draft.nodePrice || ""} onChange={(event) => update("nodePrice", Number(event.target.value))} required /></label>
        </div>
        <div className="hypernet-bid-preview"><span><small>Total committed</small><strong>{total.toLocaleString()} ISK</strong></span><span><small>Chance to win</small><strong>{odds.toFixed(2)}%</strong></span><span><small>Loss if unsuccessful</small><strong className="hypernet-loss">−{total.toLocaleString()} ISK</strong></span></div>
        <label>Notes<textarea rows={4} value={draft.notes} onChange={(event) => update("notes", event.target.value)} /></label>
      </div>
      {error && <div className="mini-alert">{error}</div>}
      <div className="button-row"><button type="button" onClick={onCancel}>Cancel</button><button type="submit" disabled={busy || !draft.typeId || !draft.characterId}><Plus size={17} /> {busy ? "Saving" : "Record bid"}</button></div>
    </form>
  </section>;
}
