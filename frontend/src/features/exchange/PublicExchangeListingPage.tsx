import { ArrowLeft, Boxes, Clock3, Coins, Gavel, Mail, MapPin, RefreshCw, ShieldCheck, UserRound } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import type { ApiClient, ExchangeListing } from "../../types/exchange";
import { auctionPriceLabel, formatExchangeDate, formatIsk } from "./exchangePresentation";
import "./exchange.css";

type PublicBidResponse = { listing: ExchangeListing };

type Props = {
  api: ApiClient;
  publicId: string;
  onBack: () => void;
};

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

function bidVisibilityCopy(listing: ExchangeListing): string {
  if (listing.bid_visibility === "public") return "Bid history is visible to everyone viewing this auction.";
  if (listing.bid_visibility === "highest_only") return "Only the current highest amount is public.";
  return "Bid amounts are private and visible only to the seller.";
}

function timeRemaining(value?: string | null): string {
  if (!value) return "No scheduled ending";
  const milliseconds = new Date(value).getTime() - Date.now();
  if (!Number.isFinite(milliseconds)) return value;
  if (milliseconds <= 0) return "Auction ended";
  const minutes = Math.ceil(milliseconds / 60000);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const remainder = minutes % 60;
  return days > 0 ? `${days}d ${hours}h remaining` : hours > 0 ? `${hours}h ${remainder}m remaining` : `${remainder}m remaining`;
}

export function PublicExchangeListingPage({ api, publicId, onBack }: Props) {
  const [listing, setListing] = useState<ExchangeListing | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    setBusy(true);
    api<ExchangeListing>(`/corporate-exchange/public/listings/${encodeURIComponent(publicId)}`)
      .then((result) => {
        setListing(result);
        document.title = `${result.title} | EQM Corporate Exchange`;
        const description = result.summary || `${result.seller_name} listed ${result.items.map((item) => item.name).slice(0, 3).join(", ")}.`;
        let meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
        if (!meta) {
          meta = document.createElement("meta");
          meta.name = "description";
          document.head.appendChild(meta);
        }
        meta.content = description;
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "The shared listing could not be loaded."))
      .finally(() => setBusy(false));
    return () => { document.title = "EVE Quartermaster"; };
  }, [api, publicId]);

  const totalUnits = useMemo(
    () => listing?.items.reduce((total, item) => total + item.quantity * listing.quantity_total, 0) ?? 0,
    [listing],
  );

  async function refreshAppraisal() {
    if (!listing) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const refreshed = await api<ExchangeListing>(
        `/corporate-exchange/public/listings/${encodeURIComponent(publicId)}/appraise`,
        { method: "POST", body: "{}" },
      );
      setListing(refreshed);
      setNotice("Five-hub market appraisal refreshed for the currently available stock.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The market appraisal could not be refreshed.");
    } finally {
      setBusy(false);
    }
  }

  async function copySellerForMail() {
    const sellerName = listing?.seller_name || "";
    const fallbackCopy = () => {
      const input = document.createElement("textarea");
      input.value = sellerName;
      input.setAttribute("readonly", "");
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.appendChild(input);
      input.select();
      const copied = document.execCommand("copy");
      input.remove();
      if (!copied) throw new Error("Clipboard copy was rejected.");
    };
    try {
      if (navigator.clipboard?.writeText) {
        await Promise.race([
          navigator.clipboard.writeText(sellerName),
          new Promise<never>((_, reject) => window.setTimeout(() => reject(new Error("Clipboard permission timed out.")), 750)),
        ]);
      }
      else fallbackCopy();
      setNotice(`${sellerName} copied. Paste the name into the recipient field in EVE Mail.`);
      setError(null);
    } catch {
      try {
        fallbackCopy();
        setNotice(`${sellerName} copied. Paste the name into the recipient field in EVE Mail.`);
        setError(null);
      } catch {
        setError(`Copy failed. Enter ${sellerName || "the seller"} in the EVE Mail recipient field.`);
      }
    }
  }

  async function submitBid(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!listing) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api<PublicBidResponse>(
        `/corporate-exchange/public/listings/${encodeURIComponent(publicId)}/bids`,
        {
          method: "POST",
          body: JSON.stringify({
            bidder_name: form.get("bidder_name"),
            bidder_contact: form.get("bidder_contact"),
            amount: Number(form.get("amount") || 0),
            quantity: Number(form.get("quantity") || 1),
            expires_at: form.get("expires_at") || null,
            message: form.get("message"),
            website: form.get("website"),
          }),
        },
      );
      setListing(result.listing);
      formElement.reset();
      setNotice("Bid recorded. The seller can now review it and contact you through the method provided.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The bid could not be submitted.");
    } finally {
      setBusy(false);
    }
  }

  if (busy && !listing) {
    return <main className="exchange-public-shell"><section className="exchange-public-card"><p className="muted">Loading shared auction...</p></section></main>;
  }
  if (!listing) {
    return (
      <main className="exchange-public-shell">
        <section className="exchange-public-card exchange-public-missing">
          <Boxes size={38} />
          <h1>Listing unavailable</h1>
          <p className="alert">{error || "This link is invalid or the listing is not public."}</p>
          <button type="button" onClick={onBack}><ArrowLeft size={17} /> Back to EQM</button>
        </section>
      </main>
    );
  }

  const isAuction = listing.listing_type === "auction";
  const canBid = isAuction && !listing.auction_ended && ["active", "offer_pending", "partially_claimed"].includes(listing.status);
  return (
    <main className="exchange-public-shell">
      <section className="exchange-public-card">
        <header className="exchange-public-header">
          <div className="exchange-public-brand"><img src="/eqm-logo.png" alt="EVE Quartermaster" /><span>Corporate Exchange</span></div>
          <span className={`exchange-status exchange-status-${listing.status}`}>{statusLabel(listing.status)}</span>
        </header>

        <div className="exchange-public-title">
          <div>
            <span className="eyebrow">{listing.listing_type === "auction" ? "Public auction" : "Public listing"}</span>
            <h1>{listing.title}</h1>
            <p>{listing.summary || "A shared EVE Quartermaster trade listing."}</p>
          </div>
          {listing.items[0]?.type_id ? <img src={`https://images.evetech.net/types/${listing.items[0].type_id}/icon?size=128`} alt="" /> : <Boxes size={56} />}
        </div>

        {error && <div className="alert">{error}</div>}
        {notice && <div className="notice">{notice}</div>}

        <div className="exchange-public-facts">
          <div>{isAuction ? <Gavel size={19} /> : <Coins size={19} />}<span>{isAuction ? listing.highest_bid != null ? "Highest bid" : "Opening bid" : "Asking price"}</span><strong>{isAuction ? auctionPriceLabel(listing) : formatIsk(listing.asking_price)}</strong><small>{isAuction ? `${listing.bid_count || 0} active bid(s)` : `${listing.quantity_available} package(s) available`}</small></div>
          <div><Clock3 size={19} /><span>{isAuction ? "Closes" : "Available until"}</span><strong>{listing.expires_at ? timeRemaining(listing.expires_at) : "Contact seller"}</strong><small>{formatExchangeDate(listing.expires_at)}</small></div>
          <div><MapPin size={19} /><span>Handoff</span><strong>{listing.location}</strong><small>{listing.condition_notes || "Condition not specified"}</small></div>
          <div><UserRound size={19} /><span>Seller</span><strong>{listing.seller_name}</strong><small>{listing.seller_corporation_name || "Personal listing"}</small></div>
        </div>

        <div className="exchange-public-columns">
          <section>
            <div className="section-heading compact"><div><h2>Package contents</h2><p className="muted">{totalUnits.toLocaleString()} item units across {listing.items.length} lines</p></div></div>
            <div className="exchange-manifest">
              {listing.items.map((item, index) => (
                <div key={`${item.type_id || item.name}-${index}`}>
                  {item.type_id ? <img src={`https://images.evetech.net/types/${item.type_id}/icon?size=64`} alt="" /> : <span className="exchange-item-fallback"><Boxes size={20} /></span>}
                  <span><strong>{item.name}</strong><small>{item.notes || "Included in each listing unit"}</small></span>
                  <b>x{(item.quantity * listing.quantity_total).toLocaleString()}</b>
                </div>
              ))}
            </div>
            {listing.description && <div className="exchange-public-description"><h2>Seller notes</h2><p>{listing.description}</p></div>}
          </section>

          <aside className="exchange-public-bid-panel">
            <h2>{isAuction ? canBid ? "Make a bid" : "Auction closed" : "Contact the seller"}</h2>
            <p className="muted">{isAuction ? bidVisibilityCopy(listing) : "This is a fixed-price public listing. Contact the seller to arrange the in-game trade."}</p>
            <div className="exchange-public-trust"><ShieldCheck size={18} /><span>External bids are unverified. EQM records the offer; all item and ISK transfers still happen in EVE.</span></div>
            {listing.seller_character_id && <><button type="button" onClick={() => void copySellerForMail()}><Mail size={18} /> EVE Mail the seller</button><small>Copies the seller character name for the recipient field in EVE Mail.</small></>}
            {canBid ? (
              <form onSubmit={submitBid}>
                <label>Character or alliance name<input name="bidder_name" required minLength={2} maxLength={255} autoComplete="name" /></label>
                <label>Contact method<input name="bidder_contact" required minLength={3} maxLength={255} placeholder="EVE mail character or Discord handle" /></label>
                <div className="form-grid two">
                  <label>Bid amount (ISK)<input name="amount" type="number" min={listing.next_minimum_bid || 0.01} step="0.01" defaultValue={listing.next_minimum_bid || listing.minimum_bid || ""} required /></label>
                  <label>Quantity<input name="quantity" type="number" min="1" max={listing.quantity_available} defaultValue={listing.sell_as_complete_lot ? listing.quantity_available : 1} readOnly={listing.sell_as_complete_lot} required /></label>
                </div>
                <label>Bid valid until<input name="expires_at" type="datetime-local" /></label>
                <label>Message<textarea name="message" rows={3} maxLength={2000} placeholder="Delivery timing, contact details, or offer context" /></label>
                <label className="exchange-honeypot" aria-hidden="true">Website<input name="website" tabIndex={-1} autoComplete="off" /></label>
                <button className="primary exchange-bid-submit" disabled={busy}><Gavel size={19} /> {busy ? "Recording bid..." : "Submit bid"}</button>
                <small>Your contact information is visible only to the seller.</small>
              </form>
            ) : <p className="muted">Contact {listing.contact_method || listing.seller_name} to discuss or claim this listing.</p>}
          </aside>
        </div>

        <section className="exchange-public-history exchange-public-appraisal">
          <div className="section-heading compact">
            <div><h2>Current market appraisal</h2><p className="muted">Five-hub market-order value for the stock still available</p></div>
            <button type="button" disabled={busy || listing.quantity_available <= 0} onClick={() => void refreshAppraisal()}><RefreshCw size={17} /> {busy ? "Appraising..." : "Refresh appraisal"}</button>
          </div>
          {listing.appraisals.length ? <div className="table-scroll"><table className="exchange-appraisal-table"><thead><tr><th>Hub</th><th>Immediate buy</th><th>Immediate sell</th><th>Replacement</th><th>Ask vs. replacement</th><th>Priced</th></tr></thead><tbody>{listing.appraisals.map((row) => <tr key={row.hub_key}><td>{row.hub_name}</td><td>{formatIsk(row.immediate_buy_value)}</td><td>{formatIsk(row.immediate_sell_value)}</td><td>{formatIsk(row.replacement_value)}</td><td className={(row.asking_delta ?? 0) <= 0 ? "exchange-discount" : "exchange-premium"}>{row.asking_delta == null ? "n/a" : `${row.asking_delta > 0 ? "+" : ""}${formatIsk(row.asking_delta)} (${row.asking_delta_percent?.toFixed(1)}%)`}</td><td>{formatExchangeDate(row.priced_at)}</td></tr>)}</tbody></table></div> : <p className="muted">No appraisal snapshot yet. Refresh to compare the listing with current market orders.</p>}
        </section>

        {listing.bid_visibility === "public" && Boolean(listing.bids?.length) && (
          <section className="exchange-public-history">
            <h2>Public bid history</h2>
            <div className="exchange-bids">
              {listing.bids!.map((bid) => <div key={bid.id}><strong>{bid.bidder_name}</strong><span>{formatIsk(bid.amount)}</span><span>x{bid.quantity}</span><small>{formatExchangeDate(bid.created_at, "")}</small></div>)}
            </div>
          </section>
        )}

        <footer><Coins size={17} /><span>Seller contact: {listing.contact_method || listing.seller_name}</span><button type="button" onClick={onBack}><ArrowLeft size={16} /> EQM sign in</button></footer>
      </section>
    </main>
  );
}