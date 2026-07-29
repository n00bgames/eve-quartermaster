import { LockKeyhole, PackagePlus, Save, Trash2, X } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import type { ExchangeItem, ExchangeListing } from "../../types/exchange";
import { formatIsk } from "./exchangePresentation";

type EditableItem = Pick<ExchangeItem, "type_id" | "name" | "quantity" | "notes">;

type Props = {
  listing: ExchangeListing;
  busy: boolean;
  onCancel: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<boolean>;
};

function dateTimeLocal(value?: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return "";
  const offset = parsed.getTimezoneOffset() * 60000;
  return new Date(parsed.getTime() - offset).toISOString().slice(0, 16);
}

function numberOrNull(value: FormDataEntryValue | null): number | null {
  if (value == null || String(value).trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function ExchangeListingEditor({ listing, busy, onCancel, onSave }: Props) {
  const [items, setItems] = useState<EditableItem[]>(
    listing.items.map((item) => ({ type_id: item.type_id, name: item.name, quantity: item.quantity, notes: item.notes || "" })),
  );
  const [fixedPrice, setFixedPrice] = useState(String(listing.unit_price ?? ""));
  const [minimumBid, setMinimumBid] = useState(String(listing.minimum_bid ?? ""));
  const [reservePrice, setReservePrice] = useState(String(listing.reserve_price ?? ""));
  const committed = Math.max(0, listing.quantity_total - listing.quantity_available);
  const hasActiveBids = (listing.bid_count || 0) > 0;
  const packageLocked = committed > 0 || hasActiveBids;
  const auctionLocked = listing.listing_type === "auction" && packageLocked;
  const appraisalDivisor = Math.max(1, listing.quantity_available);
  const appraisalLabel = listing.listing_type === "fixed" ? "per package" : "full available lot";

  const appraisalRows = useMemo(() => listing.appraisals.slice().sort((a, b) => a.hub_name.localeCompare(b.hub_name)), [listing.appraisals]);

  const updateItem = (index: number, patch: Partial<EditableItem>) => {
    setItems((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  };

  const useAppraisal = (value?: number | null) => {
    if (value == null) return;
    const suggested = listing.listing_type === "fixed" ? value / appraisalDivisor : value;
    if (listing.listing_type === "fixed") setFixedPrice(suggested.toFixed(2));
    else setMinimumBid(suggested.toFixed(2));
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = {
      title: form.get("title"),
      summary: form.get("summary"),
      description: form.get("description"),
      visibility: form.get("visibility"),
      quantity_total: Number(form.get("quantity_total") || 0),
      quantity_available: Number(form.get("quantity_available") || 0),
      sell_as_complete_lot: form.get("sell_as_complete_lot") === "on",
      location_text: form.get("location_text"),
      division_name: form.get("division_name"),
      contact_method: form.get("contact_method"),
      condition_notes: form.get("condition_notes"),
      eligibility_notes: form.get("eligibility_notes"),
      expires_at: form.get("expires_at") || null,
    };
    if (listing.listing_type === "fixed") payload.unit_price = numberOrNull(form.get("unit_price"));
    if (listing.listing_type === "auction" && !auctionLocked) {
      payload.minimum_bid = numberOrNull(form.get("minimum_bid"));
      payload.reserve_price = numberOrNull(form.get("reserve_price"));
      payload.bid_visibility = form.get("bid_visibility");
    }
    if (!packageLocked) payload.items = items;
    if (await onSave(payload)) onCancel();
  }

  return (
    <section className="panel exchange-edit">
      <div className="section-heading">
        <div><span className="eyebrow">Owner controls</span><h3>Edit listing</h3><p className="muted">Update stock, pricing, package details, and the public handoff information.</p></div>
        <button type="button" className="icon-button" title="Cancel editing" onClick={onCancel}><X size={18} /></button>
      </div>

      {committed > 0 && <div className="exchange-edit-warning"><LockKeyhole size={18} /><span>{committed} package(s) are committed to existing transactions and cannot be removed. Those transactions keep their recorded price.</span></div>}
      {hasActiveBids && <div className="exchange-edit-warning"><LockKeyhole size={18} /><span>Auction pricing and package contents are locked because an active bid exists.</span></div>}

      <form onSubmit={submit}>
        <div className="form-grid three">
          <label>Listing title<input name="title" defaultValue={listing.title} required maxLength={255} /></label>
          <label>Visibility<select name="visibility" defaultValue={listing.visibility}><option value="users">Participating EQM users</option><option value="public">Public share link</option></select></label>
          <label>Expires<input name="expires_at" type="datetime-local" defaultValue={dateTimeLocal(listing.expires_at)} required={listing.listing_type === "auction"} /></label>
        </div>
        <label>Summary<input name="summary" defaultValue={listing.summary || ""} maxLength={500} /></label>

        <section className="exchange-edit-band">
          <div className="section-heading compact"><div><h4>Stock and price</h4><p className="muted">Available stock may be reduced as packages sell or increased when you restock.</p></div></div>
          <div className="form-grid three">
            <label>Total listing stock<input name="quantity_total" type="number" min={committed} defaultValue={listing.quantity_total} required /></label>
            <label>Available now<input name="quantity_available" type="number" min="0" defaultValue={listing.quantity_available} required /></label>
            {listing.listing_type === "fixed"
              ? <label>Price per package (ISK)<input name="unit_price" type="number" min="0" step="0.01" value={fixedPrice} onChange={(event) => setFixedPrice(event.target.value)} /></label>
              : <label>Opening bid (ISK)<input name="minimum_bid" type="number" min="0.01" step="0.01" value={minimumBid} disabled={auctionLocked} onChange={(event) => setMinimumBid(event.target.value)} required /></label>}
          </div>
          {listing.listing_type === "auction" && <div className="form-grid two"><label>Hidden reserve (ISK)<input name="reserve_price" type="number" min="0" step="0.01" value={reservePrice} disabled={auctionLocked} onChange={(event) => setReservePrice(event.target.value)} /></label><label>Bid display<select name="bid_visibility" defaultValue={listing.bid_visibility || "private"} disabled={auctionLocked}><option value="public">Public bid history</option><option value="highest_only">Highest amount only</option><option value="private">Private offers</option></select></label></div>}
          <label className="inline-field"><input name="sell_as_complete_lot" type="checkbox" defaultChecked={listing.sell_as_complete_lot} /> Sell all available packages as one complete lot</label>
          {appraisalRows.length > 0 && <div className="exchange-edit-appraisals">{appraisalRows.map((row) => <div key={row.hub_key}><strong>{row.hub_name}</strong><small>Suggestions {appraisalLabel}</small><span><button type="button" onClick={() => useAppraisal(row.immediate_buy_value)}>Use buy {formatIsk(row.immediate_buy_value == null ? null : row.immediate_buy_value / (listing.listing_type === "fixed" ? appraisalDivisor : 1))}</button><button type="button" onClick={() => useAppraisal(row.immediate_sell_value)}>Use sell {formatIsk(row.immediate_sell_value == null ? null : row.immediate_sell_value / (listing.listing_type === "fixed" ? appraisalDivisor : 1))}</button></span></div>)}</div>}
        </section>

        <section className="exchange-edit-band">
          <div className="section-heading compact"><div><h4>Package contents</h4><p className="muted">Each line describes one package. Contents lock after a claim or bid.</p></div>{!packageLocked && <button type="button" onClick={() => setItems((current) => [...current, { name: "", quantity: 1, notes: "" }])}><PackagePlus size={17} /> Add item</button>}</div>
          <div className="exchange-item-editor">
            {items.map((item, index) => <div key={index}><label>Item<input value={item.name} disabled={packageLocked} onChange={(event) => updateItem(index, { name: event.target.value })} required /></label><label>Qty<input type="number" min="1" value={item.quantity} disabled={packageLocked} onChange={(event) => updateItem(index, { quantity: Number(event.target.value) })} /></label><label>Notes<input value={item.notes || ""} disabled={packageLocked} onChange={(event) => updateItem(index, { notes: event.target.value })} /></label><button type="button" className="icon-button danger" title="Remove item" disabled={packageLocked || items.length === 1} onClick={() => setItems((current) => current.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={17} /></button></div>)}
          </div>
        </section>

        <section className="exchange-edit-band">
          <div className="section-heading compact"><div><h4>Handoff and notes</h4></div></div>
          <div className="form-grid two"><label>Location<input name="location_text" defaultValue={listing.location_text || ""} maxLength={500} /></label><label>Hangar or division<input name="division_name" defaultValue={listing.division_name || ""} maxLength={255} /></label><label>Preferred contact<input name="contact_method" defaultValue={listing.contact_method || ""} maxLength={255} /></label><label>Condition<input name="condition_notes" defaultValue={listing.condition_notes || ""} maxLength={500} /></label></div>
          <label>Eligibility notes<textarea name="eligibility_notes" rows={2} defaultValue={listing.eligibility_notes || ""} /></label>
          <label>Description<textarea name="description" rows={5} defaultValue={listing.description || ""} /></label>
        </section>

        <div className="toolbar exchange-form-actions"><button type="button" onClick={onCancel}><X size={17} /> Cancel</button><button className="primary" disabled={busy}><Save size={18} /> {busy ? "Saving..." : "Save listing"}</button></div>
      </form>
    </section>
  );
}