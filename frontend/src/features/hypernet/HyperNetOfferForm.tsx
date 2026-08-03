import { Calculator, Plus, Search, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import type { ApiClient, HyperNetLocationCandidate, HyperNetMeta, HyperNetOffer, HyperNetTypeCandidate } from "../../types/hypernet";
import { calculateHyperNet } from "./hypernetMath";
import { formatIsk, localInputValue, profitClass } from "./hypernetPresentation";


type Draft = {
  sellerCharacterId: number;
  typeId: number;
  itemName: string;
  quantity: number;
  locationId: number | null;
  locationName: string;
  status: "draft" | "active";
  createdAt: string;
  expiresAt: string;
  totalOfferPrice: number;
  totalNodes: number;
  nodesSold: number;
  sellerOwnedNodes: number;
  uniqueParticipants: number;
  hypercoresRequired: number;
  hypercoreUnitCost: number;
  acquisitionCost: number;
  desiredProfit: number;
  jitaSell: number;
  localSell: number;
  notes: string;
};

const now = new Date();
const initialDraft: Draft = {
  sellerCharacterId: 0, typeId: 0, itemName: "", quantity: 1, locationId: null, locationName: "",
  status: "draft", createdAt: localInputValue(now), expiresAt: localInputValue(new Date(now.getTime() + 72 * 3600_000)),
  totalOfferPrice: 0, totalNodes: 8, nodesSold: 0, sellerOwnedNodes: 0, uniqueParticipants: 0,
  hypercoresRequired: 0, hypercoreUnitCost: 0, acquisitionCost: 0, desiredProfit: 0, jitaSell: 0, localSell: 0, notes: "",
};

function Result({ label, value, formula, tone }: { label: string; value: string; formula: string; tone?: string }) {
  return <div className={`hypernet-result ${tone ?? ""}`} title={formula}><span>{label}</span><strong>{value}</strong><small>{formula}</small></div>;
}

export function HyperNetOfferForm({ api, meta, onSaved, onCancel }: { api: ApiClient; meta: HyperNetMeta; onSaved: (offer: HyperNetOffer) => void; onCancel: () => void }) {
  const [draft, setDraft] = useState<Draft>({ ...initialDraft, sellerCharacterId: meta.seller_characters[0]?.id ?? 0 });
  const [types, setTypes] = useState<HyperNetTypeCandidate[]>([]);
  const [locations, setLocations] = useState<HyperNetLocationCandidate[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const update = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const calculation = useMemo(() => calculateHyperNet({
    totalOfferPrice: draft.totalOfferPrice, totalNodes: draft.totalNodes, hypercoresRequired: draft.hypercoresRequired,
    hypercoreUnitCost: draft.hypercoreUnitCost, acquisitionCost: draft.acquisitionCost, desiredProfit: draft.desiredProfit,
    sellerOwnedNodes: draft.sellerOwnedNodes, jitaSell: draft.jitaSell || undefined, localSell: draft.localSell || undefined,
  }), [draft.totalOfferPrice, draft.totalNodes, draft.hypercoresRequired, draft.hypercoreUnitCost, draft.acquisitionCost, draft.desiredProfit, draft.sellerOwnedNodes, draft.jitaSell, draft.localSell]);

  useEffect(() => {
    if (draft.itemName.trim().length < 2 || draft.typeId) { setTypes([]); return; }
    const timer = window.setTimeout(() => void api<HyperNetTypeCandidate[]>(`/hypernet/search/types?q=${encodeURIComponent(draft.itemName.trim())}`).then(setTypes).catch(() => setTypes([])), 220);
    return () => window.clearTimeout(timer);
  }, [draft.itemName, draft.typeId]);

  useEffect(() => {
    if (draft.locationName.trim().length < 2 || draft.locationId) { setLocations([]); return; }
    const timer = window.setTimeout(() => void api<HyperNetLocationCandidate[]>(`/hypernet/search/locations?q=${encodeURIComponent(draft.locationName.trim())}`).then(setLocations).catch(() => setLocations([])), 220);
    return () => window.clearTimeout(timer);
  }, [draft.locationName, draft.locationId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null);
    if (!draft.typeId) { setError("Choose an item from the imported EVE type results."); return; }
    if (!draft.sellerCharacterId) { setError("Link an EVE character before recording a HyperNet offer."); return; }
    setBusy(true);
    try {
      const offer = await api<HyperNetOffer>("/hypernet/offers", { method: "POST", body: JSON.stringify({
        seller_character_id: draft.sellerCharacterId, type_id: draft.typeId, quantity: draft.quantity,
        location_id: draft.locationId, location_name: draft.locationName || null, status: draft.status,
        created_offer_at: new Date(draft.createdAt).toISOString(), expires_at: new Date(draft.expiresAt).toISOString(),
        total_offer_price: draft.totalOfferPrice, total_nodes: draft.totalNodes, nodes_sold: draft.nodesSold,
        seller_owned_nodes: draft.sellerOwnedNodes, unique_participants: draft.uniqueParticipants,
        hypercores_required: draft.hypercoresRequired, hypercore_unit_cost: draft.hypercoreUnitCost,
        acquisition_cost: draft.acquisitionCost, desired_profit: draft.desiredProfit,
        jita_sell: draft.jitaSell || null, local_sell: draft.localSell || null, notes: draft.notes || null, source: "manual",
      }) });
      onSaved(offer);
    } catch (err) { setError(err instanceof Error ? err.message : "Unable to save the HyperNet offer"); }
    finally { setBusy(false); }
  }

  return <section className="panel hypernet-offer-form">
    <div className="section-heading"><div><span className="eyebrow">Manual-first planning</span><h3>Record or plan a HyperNet offer</h3><p>No in-game offer is created. EQM stores only the values you enter.</p></div><button type="button" className="icon-button" onClick={onCancel} title="Close offer form"><X size={18} /></button></div>
    <form onSubmit={submit}>
      <div className="hypernet-form-layout">
        <div className="hypernet-form-fields">
          <div className="form-grid two">
            <label>Seller character<select value={draft.sellerCharacterId} onChange={(event) => update("sellerCharacterId", Number(event.target.value))} required><option value={0}>Choose character</option>{meta.seller_characters.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
            <label className="hypernet-search-field">Item<input value={draft.itemName} onChange={(event) => setDraft((current) => ({ ...current, itemName: event.target.value, typeId: 0 }))} placeholder="Marshal" required />{types.length > 0 && <div className="hypernet-search-menu">{types.map((row) => <button type="button" key={row.type_id} onClick={() => setDraft((current) => ({ ...current, typeId: row.type_id, itemName: row.name }))}><Search size={14} /><span><strong>{row.name}</strong><small>{row.group ?? row.category ?? `Type ${row.type_id}`}</small></span></button>)}</div>}</label>
            <label>Quantity<input type="number" min="1" value={draft.quantity} onChange={(event) => update("quantity", Number(event.target.value))} required /></label>
            <label className="hypernet-search-field">Offer location<input value={draft.locationName} onChange={(event) => setDraft((current) => ({ ...current, locationName: event.target.value, locationId: null }))} placeholder="Jita IV - Moon 4" />{locations.length > 0 && <div className="hypernet-search-menu">{locations.map((row) => <button type="button" key={`${row.source}-${row.id ?? row.eve_location_id}`} onClick={() => setDraft((current) => ({ ...current, locationId: row.id ?? null, locationName: row.name }))}><span><strong>{row.name}</strong><small>{row.source === "eqm" ? "Known EQM location" : "SDE station"}</small></span></button>)}</div>}</label>
            <label>Created<input type="datetime-local" value={draft.createdAt} onChange={(event) => update("createdAt", event.target.value)} required /></label>
            <label>Expires<input type="datetime-local" value={draft.expiresAt} onChange={(event) => update("expiresAt", event.target.value)} required /></label>
            <label>Starting status<select value={draft.status} onChange={(event) => update("status", event.target.value as Draft["status"])}><option value="draft">Draft</option><option value="active">Active</option></select></label>
          </div>
          <h4>Offer economics</h4>
          <div className="form-grid three">
            <label>Total offer price (ISK)<input type="number" min="0" step="0.01" value={draft.totalOfferPrice || ""} onChange={(event) => update("totalOfferPrice", Number(event.target.value))} required /></label>
            <label>Total nodes<input type="number" min="1" max="512" value={draft.totalNodes} onChange={(event) => update("totalNodes", Number(event.target.value))} required /></label>
            <label>Acquisition cost (ISK)<input type="number" min="0" step="0.01" value={draft.acquisitionCost || ""} onChange={(event) => update("acquisitionCost", Number(event.target.value))} /></label>
            <label>HyperCores required<input type="number" min="0" value={draft.hypercoresRequired || ""} onChange={(event) => update("hypercoresRequired", Number(event.target.value))} /></label>
            <label>HyperCore price (ISK)<input type="number" min="0" step="0.01" value={draft.hypercoreUnitCost || ""} onChange={(event) => update("hypercoreUnitCost", Number(event.target.value))} /></label>
            <label>Desired minimum profit<input type="number" step="0.01" value={draft.desiredProfit || ""} onChange={(event) => update("desiredProfit", Number(event.target.value))} /></label>
          </div>
          <h4>Current progress and market context</h4>
          <div className="form-grid three">
            <label>Nodes sold<input type="number" min="0" max={draft.totalNodes} value={draft.nodesSold} onChange={(event) => update("nodesSold", Number(event.target.value))} /></label>
            <label>Seeded nodes<input type="number" min="0" max={draft.nodesSold} value={draft.sellerOwnedNodes} onChange={(event) => update("sellerOwnedNodes", Number(event.target.value))} /></label>
            <label>Unique participants<input type="number" min="0" value={draft.uniqueParticipants} onChange={(event) => update("uniqueParticipants", Number(event.target.value))} /></label>
            <label>Current Jita sell<input type="number" min="0" step="0.01" value={draft.jitaSell || ""} onChange={(event) => update("jitaSell", Number(event.target.value))} /></label>
            <label>Current local sell<input type="number" min="0" step="0.01" value={draft.localSell || ""} onChange={(event) => update("localSell", Number(event.target.value))} /></label>
          </div>
          <label>Notes<textarea rows={4} value={draft.notes} onChange={(event) => update("notes", event.target.value)} placeholder="Promotion, timing, observations, or manual reference" /></label>
        </div>
        <aside className="hypernet-calculator-panel">
          <div className="section-heading compact"><div><h4><Calculator size={18} /> Profit calculator</h4><p>Formula-backed planning before committing in EVE.</p></div></div>
          <div className="hypernet-results">
            <Result label="Price per node" value={formatIsk(calculation.financials.node_price)} formula="total offer price / total nodes" />
            <Result label="5% completion fee" value={formatIsk(calculation.financials.completion_fee)} formula="total offer price × 0.05" />
            <Result label="HyperCore cost" value={formatIsk(calculation.financials.hypercore_cost)} formula="HyperCores required × unit cost" />
            <Result label="Expected payout" value={formatIsk(calculation.financials.payout_after_fee)} formula="total offer price − completion fee" />
            <Result label="Estimated net proceeds" value={formatIsk(calculation.financials.net_proceeds)} formula="payout after fee − HyperCore cost" />
            <Result label="Estimated profit" value={formatIsk(calculation.financials.profit)} formula="net proceeds − acquisition cost" tone={profitClass(calculation.financials.profit)} />
            <Result label="Return on cost" value={calculation.financials.return_on_cost_percent == null ? "—" : `${calculation.financials.return_on_cost_percent.toFixed(2)}%`} formula="profit / acquisition cost" tone={profitClass(calculation.financials.return_on_cost_percent)} />
            <Result label="Break-even offer" value={formatIsk(calculation.financials.break_even_offer_price)} formula="(acquisition + HyperCores) / 0.95" />
            <Result label="Target-profit offer" value={formatIsk(calculation.financials.minimum_offer_for_target_profit)} formula="(acquisition + desired profit + HyperCores) / 0.95" />
            <Result label="Maximum HyperCore price" value={formatIsk(calculation.financials.maximum_hypercore_unit_cost)} formula="(offer × 0.95 − acquisition − desired profit) / HyperCores" />
          </div>
          <div className="hypernet-scenario-card">
            <h4>Seeded-node outcome analysis</h4>
            <p><strong>{calculation.scenario.seller_win_probability_percent.toFixed(2)}%</strong> seller win chance · <strong>{formatIsk(calculation.scenario.seller_node_spend)}</strong> spent seeding</p>
            <dl><dt>External buyer wins</dt><dd className={profitClass(calculation.scenario.cash_result_if_external_wins)}>{formatIsk(calculation.scenario.cash_result_if_external_wins)}</dd><dt>Seller wins · item retained</dt><dd>{formatIsk(calculation.scenario.cash_result_if_seller_wins)} cash</dd><dt>Seller win · mark to Jita</dt><dd className={profitClass(calculation.scenario.seller_win_mark_to_jita_result)}>{formatIsk(calculation.scenario.seller_win_mark_to_jita_result)}</dd><dt>Expected result</dt><dd className={profitClass(calculation.scenario.expected_monetary_result)}>{formatIsk(calculation.scenario.expected_monetary_result)}</dd><dt>Capital tied up</dt><dd>{formatIsk(calculation.scenario.capital_tied_up)}</dd></dl>
            <small>Seeded nodes are never counted as organic sales. If the seller wins, the item remains an asset and is shown separately from cash.</small>
          </div>
        </aside>
      </div>
      {error && <div className="mini-alert">{error}</div>}
      <div className="button-row"><button type="button" onClick={onCancel}>Cancel</button><button type="submit" disabled={busy || !draft.typeId || !draft.sellerCharacterId}><Plus size={17} /> {busy ? "Saving" : draft.status === "active" ? "Save active offer" : "Save draft"}</button></div>
    </form>
  </section>;
}
