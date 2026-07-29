import { Boxes, Check, Clipboard, Coins, ExternalLink, Gavel, MapPin, PackagePlus, Pencil, RefreshCw, Search, Share2, ShoppingCart, Tag, X } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import "./exchange.css";

import type { ApiClient, ExchangeAppraisal, ExchangeDraftAppraisal, ExchangeListing, SellerCharacter } from "../../types/exchange";
import { auctionPriceLabel, exchangeListingUrl, exchangeManifest, formatExchangeDate, formatIsk } from "./exchangePresentation";
import { ExchangeListingEditor } from "./ExchangeListingEditor";

type DraftItem = { name: string; quantity: number; notes: string };
const integer = new Intl.NumberFormat();
function ListingStatus({ status }: { status: string }) {
  return <span className={`exchange-status exchange-status-${status}`}>{status.replace(/_/g, " ")}</span>;
}

function AppraisalTable({ listing }: { listing: ExchangeListing }) {
  if (!listing.appraisals.length) {
    return <p className="muted">No appraisal snapshot yet. Pricing is timestamped when the seller or viewer requests it.</p>;
  }
  return (
    <div className="table-scroll">
      <table className="exchange-appraisal-table">
        <thead><tr><th>Hub</th><th>Immediate buy</th><th>Immediate sell</th><th>Replacement</th><th>Ask vs. replacement</th><th>Priced</th></tr></thead>
        <tbody>
          {listing.appraisals.map((row) => (
            <tr key={row.hub_key}>
              <td>{row.hub_name}</td>
              <td>{formatIsk(row.immediate_buy_value)}</td>
              <td>{formatIsk(row.immediate_sell_value)}</td>
              <td>{formatIsk(row.replacement_value)}</td>
              <td className={(row.asking_delta ?? 0) <= 0 ? "exchange-discount" : "exchange-premium"}>
                {row.asking_delta == null ? "n/a" : `${row.asking_delta > 0 ? "+" : ""}${formatIsk(row.asking_delta)} (${row.asking_delta_percent?.toFixed(1)}%)`}
              </td>
              <td title={row.source}>{formatExchangeDate(row.priced_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ListingDetail({
  listing,
  currentUserId,
  busy,
  onBack,
  onAppraise,
  onClaim,
  onBid,
  onBidDecision,
  onStatus,
  onUpdate,
}: {
  listing: ExchangeListing;
  currentUserId: number;
  busy: boolean;
  onBack: () => void;
  onAppraise: () => void;
  onClaim: (quantity: number) => void;
  onBid: (payload: Record<string, unknown>) => void;
  onBidDecision: (bidId: number, action: "accept" | "reject") => void;
  onStatus: (status: string) => void;
  onUpdate: (payload: Record<string, unknown>) => Promise<boolean>;
}) {
  const [claimQuantity, setClaimQuantity] = useState(listing.sell_as_complete_lot ? listing.quantity_available : 1);
  const [bidQuantity, setBidQuantity] = useState(listing.sell_as_complete_lot ? listing.quantity_available : 1);
  const [editing, setEditing] = useState(false);
  const share = async () => navigator.clipboard.writeText(exchangeListingUrl(listing.public_id));
  const copyManifest = async () => navigator.clipboard.writeText(exchangeManifest(listing));
  const active = ["active", "partially_claimed", "offer_pending"].includes(listing.status);
  const canClaim = listing.listing_type === "fixed" && active && listing.quantity_available > 0 && listing.seller_user_id !== currentUserId;
  const canBid = listing.listing_type === "auction" && active && !listing.auction_ended && listing.quantity_available > 0 && listing.seller_user_id !== currentUserId;

  function submitBid(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onBid({
      amount: Number(form.get("amount") || 0),
      quantity: bidQuantity,
      bidder_contact: form.get("bidder_contact"),
      expires_at: form.get("expires_at") || null,
      message: form.get("message"),
    });
  }

  const primaryPrice = listing.listing_type === "auction" ? auctionPriceLabel(listing) : formatIsk(listing.asking_price);
  const priceCaption = listing.listing_type === "auction"
    ? `${listing.bid_count || 0} active bid(s)${listing.reserve_met ? " · reserve met" : ""}`
    : listing.unit_price == null ? "Package price" : `${formatIsk(listing.unit_price)} per listing unit`;

  if (editing && listing.is_owner) {
    return <ExchangeListingEditor listing={listing} busy={busy} onCancel={() => setEditing(false)} onSave={onUpdate} />;
  }

  return (
    <section className="panel exchange-detail">
      <div className="section-heading">
        <div>
          <button type="button" className="icon-button" title="Back to Corporate Exchange" onClick={onBack}><X size={18} /></button>
          <span className="eyebrow">{listing.listing_type.replace(/_/g, " ")}</span>
          <h3>{listing.title}</h3>
          <p className="muted">{listing.summary || "Internal EVE trade listing"}</p>
        </div>
        <div className="toolbar">
          <ListingStatus status={listing.status} />
          {listing.is_owner && <button type="button" onClick={() => setEditing(true)}><Pencil size={17} /> Edit listing</button>}
          <button type="button" onClick={() => void share()}><Share2 size={17} /> Share listing</button>
          <button type="button" onClick={() => void copyManifest()}><Clipboard size={17} /> Copy manifest</button>
        </div>
      </div>

      <div className="exchange-facts">
        <div><span>Seller</span><strong>{listing.seller_name}</strong><small>{listing.seller_corporation_name || "Personal listing"}</small></div>
        <div><span>{listing.listing_type === "auction" && listing.highest_bid != null ? "Highest bid" : listing.listing_type === "auction" ? "Opening bid" : "Asking price"}</span><strong>{primaryPrice}</strong><small>{priceCaption}</small></div>
        <div><span>Available</span><strong>{integer.format(listing.quantity_available)} / {integer.format(listing.quantity_total)}</strong><small>{listing.sell_as_complete_lot ? "Complete lot only" : "Partial quantities permitted"}</small></div>
        <div><span>Location</span><strong>{listing.location}</strong><small>{listing.condition_notes || "Condition not specified"}</small></div>
      </div>

      <div className="exchange-detail-columns">
        <section>
          <div className="section-heading compact"><div><h4>Package contents</h4><p className="muted">{listing.items.length} item line(s) per listing unit</p></div></div>
          <div className="exchange-manifest">
            {listing.items.map((item, index) => (
              <div key={item.id ?? `${item.name}-${index}`}>
                {item.type_id ? <img src={`https://images.evetech.net/types/${item.type_id}/icon?size=64`} alt="" loading="lazy" /> : <span className="exchange-item-fallback"><Boxes size={20} /></span>}
                <span><strong>{item.name}</strong><small>{item.notes || `Type ${item.type_id || "unresolved"}`}</small></span>
                <b>x{integer.format(item.quantity)}</b>
              </div>
            ))}
          </div>
        </section>
        <section className="exchange-contact">
          <h4>Trade handoff</h4>
          <dl>
            <dt>Preferred contact</dt><dd>{listing.contact_method || listing.seller_name}</dd>
            <dt>Eligibility</dt><dd>{listing.eligibility_notes || "Available to participating EQM users"}</dd>
            <dt>Expires</dt><dd>{formatExchangeDate(listing.expires_at)}</dd>
            <dt>Visibility</dt><dd>{listing.visibility === "public" ? "Public share link" : "Signed-in EQM users"}</dd>
            <dt>Reference</dt><dd><code>{listing.public_id}</code></dd>
          </dl>
          {canClaim && (
            <div className="exchange-claim">
              <label>Quantity<input type="number" min="1" max={listing.quantity_available} value={claimQuantity} disabled={listing.sell_as_complete_lot} onChange={(event) => setClaimQuantity(Number(event.target.value))} /></label>
              <button className="primary" disabled={busy} onClick={() => onClaim(claimQuantity)}><ShoppingCart size={18} /> Claim It Now</button>
              <small>Reserves EQM listing stock for 48 hours. Item transfer still happens through EVE.</small>
            </div>
          )}
          {canBid && (
            <form className="exchange-claim" onSubmit={submitBid}>
              <div className="form-grid two">
                <label>Bid amount (ISK)<input name="amount" type="number" min={listing.next_minimum_bid || 0.01} step="0.01" defaultValue={listing.next_minimum_bid || listing.minimum_bid || ""} required /></label>
                <label>Quantity<input type="number" min="1" max={listing.quantity_available} value={bidQuantity} readOnly={listing.sell_as_complete_lot} onChange={(event) => setBidQuantity(Number(event.target.value))} /></label>
              </div>
              <label>Seller contact reply<input name="bidder_contact" maxLength={255} placeholder="EVE mail character or Discord handle" /></label>
              <label>Bid valid until<input name="expires_at" type="datetime-local" /></label>
              <label>Message<textarea name="message" rows={2} maxLength={2000} /></label>
              <button className="primary" disabled={busy}><Gavel size={18} /> Make a Bid</button>
              <small>EQM records the offer; the transaction still occurs through EVE.</small>
            </form>
          )}
          {listing.is_owner && (
            <div className="toolbar">
              {listing.status === "draft" && <button onClick={() => onStatus("active")}><Check size={17} /> Publish</button>}
              {!['completed', 'cancelled'].includes(listing.status) && <button className="danger" onClick={() => onStatus("cancelled")}><X size={17} /> Cancel listing</button>}
            </div>
          )}
        </section>
      </div>

      <section className="exchange-appraisal">
        <div className="section-heading compact">
          <div><h4>Hub appraisal</h4><p className="muted">Jita, Amarr, Dodixie, Rens, and Hek market-order snapshots</p></div>
          <button disabled={busy} onClick={onAppraise}><RefreshCw size={17} /> Refresh appraisal</button>
        </div>
        <AppraisalTable listing={listing} />
      </section>

      {listing.is_owner && Boolean(listing.claims?.length) && (
        <section>
          <h4>Reservations</h4>
          <div className="exchange-claims">
            {listing.claims!.map((claim) => <div key={claim.id}><strong>{claim.claimant_name}</strong><span>x{claim.quantity}</span><span>{formatIsk(claim.total_price)}</span><ListingStatus status={claim.status} /><small>Expires {formatExchangeDate(claim.expires_at)}</small></div>)}
          </div>
        </section>
      )}

      {listing.is_owner && listing.listing_type === "auction" && Boolean(listing.bids?.length) && (
        <section>
          <div className="section-heading compact"><div><h4>Auction bids</h4><p className="muted">External identities are unverified; use the supplied contact before contracting.</p></div></div>
          <div className="exchange-bids exchange-owner-bids">
            {listing.bids!.map((bid) => (
              <div key={bid.id}>
                <span><strong>{bid.bidder_name}</strong><small>{bid.external ? "External bidder" : "EQM user"}{bid.bidder_contact ? ` · ${bid.bidder_contact}` : ""}</small></span>
                <b>{formatIsk(bid.amount)}</b>
                <span>x{bid.quantity}</span>
                <ListingStatus status={bid.status} />
                <small>{bid.message || formatExchangeDate(bid.created_at, "")}</small>
                {bid.status === "pending" && <span className="toolbar"><button disabled={busy} onClick={() => onBidDecision(bid.id, "accept")}><Check size={16} /> Accept</button><button className="danger" disabled={busy} onClick={() => onBidDecision(bid.id, "reject")}><X size={16} /> Reject</button></span>}
              </div>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}

function CreateListing({
  api,
  busy,
  sellerCharacters,
  onCancel,
  onCreate,
}: {
  api: ApiClient;
  busy: boolean;
  sellerCharacters: SellerCharacter[];
  onCancel: () => void;
  onCreate: (payload: Record<string, unknown>) => void;
}) {
  const [items, setItems] = useState<DraftItem[]>([{ name: "", quantity: 1, notes: "" }]);
  const [listingType, setListingType] = useState<"fixed" | "auction">("fixed");
  const [packageCount, setPackageCount] = useState(1);
  const [listingPrice, setListingPrice] = useState("");
  const [draftAppraisals, setDraftAppraisals] = useState<ExchangeAppraisal[]>([]);
  const [unmatchedItems, setUnmatchedItems] = useState<string[]>([]);
  const [appraisalBusy, setAppraisalBusy] = useState(false);
  const [appraisalError, setAppraisalError] = useState<string | null>(null);
  const invalidateAppraisal = () => {
    setDraftAppraisals([]);
    setUnmatchedItems([]);
    setAppraisalError(null);
  };
  const updateItem = (index: number, patch: Partial<DraftItem>) => {
    invalidateAppraisal();
    setItems((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row));
  };
  const appraiseDraft = async () => {
    setAppraisalBusy(true);
    setAppraisalError(null);
    try {
      const result = await api<ExchangeDraftAppraisal>("/corporate-exchange/appraise-draft", {
        method: "POST",
        body: JSON.stringify({
          quantity_total: packageCount,
          items: items.filter((item) => item.name.trim() && item.quantity > 0),
        }),
      });
      setDraftAppraisals(result.appraisals);
      setUnmatchedItems(result.unmatched_items);
    } catch (reason) {
      setDraftAppraisals([]);
      setAppraisalError(reason instanceof Error ? reason.message : "Could not appraise this package.");
    } finally {
      setAppraisalBusy(false);
    }
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onCreate({
      title: form.get("title"),
      seller_character_id: Number(form.get("seller_character_id") || 0) || null,
      summary: form.get("summary"),
      listing_type: form.get("listing_type"),
      status: form.get("status"),
      quantity_total: packageCount,
      asking_price: listingType === "fixed" ? Number(listingPrice || 0) || null : null,
      minimum_bid: listingType === "auction" ? Number(listingPrice || 0) || null : null,
      reserve_price: listingType === "auction" ? Number(form.get("reserve_price") || 0) || null : null,
      bid_visibility: listingType === "auction" ? form.get("bid_visibility") : "private",
      location_text: form.get("location_text"),
      division_name: form.get("division_name"),
      contact_method: form.get("contact_method"),
      condition_notes: form.get("condition_notes"),
      description: form.get("description"),
      visibility: form.get("visibility"),
      sell_as_complete_lot: form.get("sell_as_complete_lot") === "on",
      expires_at: form.get("expires_at") || null,
      items: items.filter((item) => item.name.trim() && item.quantity > 0),
    });
  };
  return (
    <section className="panel exchange-create">
      <div className="section-heading"><div><span className="eyebrow">New listing</span><h3>Advertise on the Corporate Exchange</h3></div><button type="button" className="icon-button" title="Close" onClick={onCancel}><X size={18} /></button></div>
      <form onSubmit={submit}>
        <div className="form-grid">
          <label>Title<input name="title" required maxLength={255} placeholder="Covetor mining package" /></label>
          <label>Seller character<select name="seller_character_id" required={sellerCharacters.length > 0}><option value="">EQM account identity</option>{sellerCharacters.map((character) => <option key={character.id} value={character.id}>{character.name}{character.corporation_name ? ` - ${character.corporation_name}` : ""}</option>)}</select></label>
          <label>Listing type<select name="listing_type" value={listingType} onChange={(event) => setListingType(event.target.value as "fixed" | "auction")}><option value="fixed">Fixed-price sale</option><option value="auction">Auction / bid sale</option></select></label>
          <label>Package summary<input name="summary" maxLength={500} placeholder="Hull, fit, charges, and spare crystals" /></label>
          <label>Visibility<select name="visibility"><option value="users">Participating EQM users</option><option value="public">Public share link</option></select></label>
          <label>Number of packages<input name="quantity_total" type="number" min="1" value={packageCount} onChange={(event) => { invalidateAppraisal(); setPackageCount(Math.max(1, Number(event.target.value) || 1)); }} required /></label>
          {listingType === "fixed" ? <label>Total asking price (ISK)<input name="asking_price" type="number" min="0" step="0.01" value={listingPrice} onChange={(event) => setListingPrice(event.target.value)} /></label> : <><label>Minimum bid (ISK)<input name="minimum_bid" type="number" min="0.01" step="0.01" value={listingPrice} onChange={(event) => setListingPrice(event.target.value)} required /></label><label>Hidden reserve (ISK)<input name="reserve_price" type="number" min="0" step="0.01" placeholder="Optional; never shown publicly" /></label><label>Bid display<select name="bid_visibility" defaultValue="highest_only"><option value="public">Public bid history</option><option value="highest_only">Highest amount only</option><option value="private">Private offers</option></select></label></>}
          <label>Location<input name="location_text" maxLength={500} required placeholder="Hahda VII - Moon 1 - Factory" /></label>
          <label>Hangar / division<input name="division_name" maxLength={255} placeholder="Ships" /></label>
          <label>Preferred contact<input name="contact_method" maxLength={255} placeholder="Character name or Discord handle" /></label>
          <label>Condition<input name="condition_notes" maxLength={500} placeholder="Packaged, fitted, assembled, researched..." /></label>
          <label>{listingType === "auction" ? "Auction ending" : "Expiration"}<input name="expires_at" type="datetime-local" required={listingType === "auction"} /></label>
          <label className="check-row"><input name="sell_as_complete_lot" type="checkbox" /> Sell remaining stock only as a complete lot</label>
        </div>
        <label>Description<textarea name="description" rows={3} placeholder="Trade details, restrictions, handoff notes, or package context." /></label>
        <div className="section-heading compact"><div><h4>Package contents</h4><p className="muted">Quantities below describe one package.</p></div><button type="button" onClick={() => { invalidateAppraisal(); setItems((rows) => [...rows, { name: "", quantity: 1, notes: "" }]); }}><PackagePlus size={17} /> Add item</button></div>
        <div className="exchange-item-editor">
          {items.map((item, index) => (
            <div key={index}>
              <label>Item<input value={item.name} onChange={(event) => updateItem(index, { name: event.target.value })} placeholder="Exact EVE item name" required /></label>
              <label>Qty<input type="number" min="1" value={item.quantity} onChange={(event) => updateItem(index, { quantity: Number(event.target.value) })} required /></label>
              <label>Notes<input value={item.notes} onChange={(event) => updateItem(index, { notes: event.target.value })} placeholder="Optional" /></label>
              <button type="button" className="icon-button danger" title="Remove item" disabled={items.length === 1} onClick={() => { invalidateAppraisal(); setItems((rows) => rows.filter((_, rowIndex) => rowIndex !== index)); }}><X size={17} /></button>
            </div>
          ))}
        </div>
        <section className="exchange-draft-appraisal">
          <div className="section-heading compact">
            <div><h4>Price this listing</h4><p className="muted">Appraise every package at the five major trade hubs before setting your price.</p></div>
            <button type="button" disabled={appraisalBusy} onClick={() => void appraiseDraft()}><RefreshCw size={17} /> {appraisalBusy ? "Appraising..." : "Appraise package"}</button>
          </div>
          {appraisalError && <div className="alert">{appraisalError}</div>}
          {Boolean(unmatchedItems.length) && <div className="alert">No market match for: {unmatchedItems.join(", ")}. Check these item names before relying on the total.</div>}
          {Boolean(draftAppraisals.length) && (
            <div className="table-scroll">
              <table className="exchange-appraisal-table exchange-draft-appraisal-table">
                <thead><tr><th>Hub</th><th>Immediate buy</th><th>Immediate sell</th><th>Set listing price</th></tr></thead>
                <tbody>{draftAppraisals.map((row) => (
                  <tr key={row.hub_key}>
                    <td>{row.hub_name}</td>
                    <td>{formatIsk(row.immediate_buy_value)}</td>
                    <td>{formatIsk(row.immediate_sell_value)}</td>
                    <td><span className="toolbar"><button type="button" disabled={!row.immediate_buy_value} onClick={() => setListingPrice(String(row.immediate_buy_value || ""))}>Use buy</button><button type="button" disabled={!row.immediate_sell_value} onClick={() => setListingPrice(String(row.immediate_sell_value || ""))}>Use sell</button></span></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {!draftAppraisals.length && !appraisalError && <p className="muted">Add exact EVE item names, then appraise the complete offered quantity.</p>}
        </section>
        <div className="toolbar exchange-form-actions">
          <button type="button" onClick={onCancel}>Cancel</button>
          <label className="inline-field">Save as<select name="status" defaultValue="active"><option value="active">Active listing</option><option value="draft">Draft</option></select></label>
          <button className="primary" disabled={busy}><Tag size={18} /> Create listing</button>
        </div>
      </form>
    </section>
  );
}

export function CorporateExchangePage({ api, currentUserId }: { api: ApiClient; currentUserId: number }) {
  const [listings, setListings] = useState<ExchangeListing[]>([]);
  const [selected, setSelected] = useState<ExchangeListing | null>(null);
  const [creating, setCreating] = useState(false);
  const [mine, setMine] = useState(false);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sellerCharacters, setSellerCharacters] = useState<SellerCharacter[]>([]);

  const detailId = window.location.hash.startsWith("#exchange/") ? window.location.hash.slice("#exchange/".length) : null;
  const load = useCallback(async () => {
    setError(null);
    try {
      if (detailId) {
        const listing = await api<ExchangeListing>(`/corporate-exchange/listings/${encodeURIComponent(detailId)}`);
        setSelected(listing);
      } else {
        const params = new URLSearchParams();
        if (mine) params.set("mine", "true");
        if (search.trim()) params.set("search", search.trim());
        const result = await api<{ listings: ExchangeListing[] }>(`/corporate-exchange/listings?${params}`);
        setListings(result.listings);
        setSelected(null);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the Corporate Exchange.");
    }
  }, [api, detailId, mine, search]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    void api<{ characters: SellerCharacter[] }>("/corporate-exchange/seller-context")
      .then((result) => setSellerCharacters(result.characters))
      .catch(() => setSellerCharacters([]));
  }, [api]);
  useEffect(() => {
    const refresh = () => void load();
    window.addEventListener("hashchange", refresh);
    return () => window.removeEventListener("hashchange", refresh);
  }, [load]);
  useEffect(() => () => {
    if (window.location.hash.startsWith("#exchange")) {
      window.history.replaceState({}, "", `${window.location.pathname}${window.location.search}`);
    }
  }, []);

  const open = (listing: ExchangeListing) => {
    window.location.hash = `exchange/${listing.public_id}`;
    setSelected(listing);
  };
  const back = () => {
    window.location.hash = "exchange";
    setSelected(null);
    void load();
  };
  const mutate = async (path: string, options: RequestInit, message: string): Promise<boolean> => {
    setBusy(true);
    setError(null);
    try {
      const listing = await api<ExchangeListing>(path, options);
      setSelected(listing);
      setNotice(message);
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Exchange action failed.");
      return false;
    } finally {
      setBusy(false);
    }
  };
  const create = async (payload: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      const listing = await api<ExchangeListing>("/corporate-exchange/listings", { method: "POST", body: JSON.stringify(payload) });
      setCreating(false);
      window.location.hash = `exchange/${listing.public_id}`;
      setSelected(listing);
      setNotice("Listing created.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create the listing.");
    } finally {
      setBusy(false);
    }
  };

  const sorted = useMemo(() => listings.slice().sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")), [listings]);
  if (selected) {
    return <>
      {error && <div className="alert">{error}</div>}
      {notice && <div className="notice">{notice}</div>}
      <ListingDetail
        listing={selected}
        currentUserId={currentUserId}
        busy={busy}
        onBack={back}
        onAppraise={() => void mutate(`/corporate-exchange/listings/${selected.public_id}/appraise`, { method: "POST", body: "{}" }, "Hub appraisal refreshed.")}
        onClaim={(quantity) => void mutate(`/corporate-exchange/listings/${selected.public_id}/claims`, { method: "POST", body: JSON.stringify({ quantity }) }, "Listing stock reserved. Contact the seller for the in-game handoff.")}
        onBid={(payload) => void mutate(`/corporate-exchange/listings/${selected.public_id}/bids`, { method: "POST", body: JSON.stringify(payload) }, "Bid submitted.")}
        onBidDecision={(bidId, action) => void mutate(`/corporate-exchange/listings/${selected.public_id}/bids/${bidId}/decision`, { method: "POST", body: JSON.stringify({ action }) }, `Bid ${action === "accept" ? "accepted" : "rejected"}.`)}
        onStatus={(status) => void mutate(`/corporate-exchange/listings/${selected.public_id}`, { method: "PATCH", body: JSON.stringify({ status }) }, `Listing marked ${status}.`)}
        onUpdate={(payload) => mutate(`/corporate-exchange/listings/${selected.public_id}`, { method: "PATCH", body: JSON.stringify(payload) }, "Listing updated.")}
      />
    </>;
  }
  if (creating) return <><CreateListing api={api} busy={busy} sellerCharacters={sellerCharacters} onCancel={() => setCreating(false)} onCreate={(payload) => void create(payload)} />{error && <div className="alert">{error}</div>}</>;

  return (
    <section className="panel exchange-board">
      <div className="section-heading">
        <div><h3>Corporate Exchange</h3><p className="muted">Ships, materials, blueprints, packages, and services offered by participating members.</p></div>
        <button className="primary" onClick={() => setCreating(true)}><PackagePlus size={18} /> Create listing</button>
      </div>
      {error && <div className="alert">{error}</div>}
      {notice && <div className="notice">{notice}</div>}
      <div className="exchange-filterbar">
        <label><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void load(); }} placeholder="Item, seller, system, or listing title" /></label>
        <button className={mine ? "active" : ""} onClick={() => setMine((value) => !value)}>{mine ? "My listings" : "All active listings"}</button>
        <button className="icon-button" title="Refresh listings" onClick={() => void load()}><RefreshCw size={18} /></button>
      </div>
      <div className="exchange-list">
        {sorted.map((listing) => (
          <button type="button" className="exchange-listing" key={listing.public_id} onClick={() => open(listing)}>
            <span className="exchange-listing-icon">{listing.items[0]?.type_id ? <img src={`https://images.evetech.net/types/${listing.items[0].type_id}/icon?size=64`} alt="" loading="lazy" /> : <Boxes size={24} />}</span>
            <span className="exchange-listing-main"><strong>{listing.title}</strong><small>{listing.items.slice(0, 3).map((item) => `${item.name} x${item.quantity}`).join(" · ")}</small><small>{listing.seller_name}{listing.seller_corporation_name ? ` · ${listing.seller_corporation_name}` : ""}</small></span>
            <span className="exchange-listing-location"><MapPin size={16} />{listing.location}</span>
            <span className="exchange-listing-stock"><b>{listing.quantity_available}/{listing.quantity_total}</b><small>available</small></span>
            <span className="exchange-listing-price">
              {listing.listing_type === "auction" ? <Gavel size={16} /> : <Coins size={16} />}
              <b>{listing.listing_type === "auction" ? auctionPriceLabel(listing) : formatIsk(listing.asking_price)}</b>
              <small>{listing.listing_type === "auction" ? `${listing.bid_count || 0} bid(s) · ${formatExchangeDate(listing.expires_at)}` : listing.unit_price ? `${formatIsk(listing.unit_price)} each` : "Fixed-price package"}</small>
            </span>
            <ListingStatus status={listing.status} />
            <ExternalLink size={17} />
          </button>
        ))}
        {!sorted.length && <div className="empty-state"><ShoppingCart size={28} /><strong>No listings match this view.</strong><span>Create the first listing or clear the current filters.</span></div>}
      </div>
    </section>
  );
}
