from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.corporate_exchange import (
    appraisal_manifest,
    appraisal_payload,
    as_float,
    market_appraisal_payload,
    audit,
    listing_location,
    listing_query,
    parse_datetime,
    require_exchange,
    serialize_listing,
)
from app.db.session import get_db
from app.models import (
    ExchangeAppraisal,
    ExchangeAuditLog,
    ExchangeBid,
    ExchangeListing,
    ExchangeNotification,
    ExchangeTransaction,
    User,
)
from app.services.market import DEFAULT_HUB_KEYS, appraise_market

from app.services.exchange_bids import (
    auction_payload,
    bid_payload,
    listing_has_ended,
    normalized_datetime,
    validate_bid,
)

router = APIRouter(prefix="/corporate-exchange", tags=["corporate-exchange-auctions"])


def public_listing_payload(listing: ExchangeListing) -> dict[str, Any]:
    stored_asking_price = as_float(listing.asking_price)
    unit_price = stored_asking_price / listing.quantity_total if stored_asking_price is not None and listing.quantity_total else None
    asking_price = unit_price * listing.quantity_available if unit_price is not None else None
    payload: dict[str, Any] = {
        "public_id": listing.public_id,
        "listing_type": listing.listing_type,
        "status": "expired" if listing_has_ended(listing) and listing.status == "active" else listing.status,
        "title": listing.title,
        "summary": listing.summary,
        "description": listing.description,
        "seller_name": listing.seller_character.name if listing.seller_character else (
            listing.seller_user.display_name if listing.seller_user else "Seller"
        ),
        "seller_character_id": listing.seller_character.character_id if listing.seller_character else None,
        "seller_corporation_id": listing.seller_corporation.corporation_id if listing.seller_corporation else None,
        "seller_corporation_name": listing.seller_corporation.name if listing.seller_corporation else None,
        "contact_method": listing.contact_method,
        "quantity_total": listing.quantity_total,
        "quantity_available": listing.quantity_available,
        "asking_price": asking_price,
        "unit_price": unit_price,
        "minimum_bid": as_float(listing.minimum_bid),
        "sell_as_complete_lot": listing.sell_as_complete_lot,
        "visibility": listing.visibility,
        "eligibility_notes": listing.eligibility_notes,
        "location": listing_location(listing),
        "condition_notes": listing.condition_notes,
        "expires_at": listing.expires_at.isoformat() if listing.expires_at else None,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
        "items": [
            {
                "type_id": item.type_id,
                "name": item.item_type.name if item.item_type else item.item_name,
                "quantity": item.quantity,
                "notes": item.notes,
            }
            for item in listing.items
        ],
        "appraisals": [
            appraisal_payload(row, asking_price)
            for row in sorted(listing.appraisals, key=lambda appraisal: appraisal.hub_name)
        ],
    }
    if listing.listing_type == "auction":
        payload.update(auction_payload(listing, is_owner=False, public_view=True))
    return payload


def load_public_listing(db: Session, public_id: str) -> ExchangeListing:
    listing = db.scalar(listing_query().where(ExchangeListing.public_id == public_id))
    if listing is None or listing.visibility != "public" or listing.status == "draft":
        raise HTTPException(status_code=404, detail="Public Exchange listing not found.")
    return listing


def clean_external_identity(payload: dict[str, Any]) -> tuple[str, str]:
    if str(payload.get("website") or "").strip():
        raise HTTPException(status_code=400, detail="Bid could not be submitted.")
    name = " ".join(str(payload.get("bidder_name") or "").split())[:255]
    contact = " ".join(str(payload.get("bidder_contact") or "").split())[:255]
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Enter your EVE character or alliance name.")
    if len(contact) < 3:
        raise HTTPException(status_code=400, detail="Enter a contact method so the seller can reach you.")
    return name, contact


def parsed_bid_values(listing: ExchangeListing, payload: dict[str, Any]) -> tuple[float, int, datetime | None]:
    try:
        amount = float(payload.get("amount") or 0)
        quantity = int(payload.get("quantity") or 1)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Bid amount and quantity must be numeric.") from exc
    expires_at = parse_datetime(payload.get("expires_at"), "bid expiration")
    listing_end = normalized_datetime(listing.expires_at)
    if expires_at and listing_end and expires_at > listing_end:
        expires_at = listing_end
    validate_bid(listing, amount=amount, quantity=quantity)
    return amount, quantity, expires_at


def add_bid(
    db: Session,
    listing: ExchangeListing,
    payload: dict[str, Any],
    *,
    bidder_user: User | None,
    bidder_name: str | None,
    bidder_contact: str | None,
) -> ExchangeBid:
    amount, quantity, expires_at = parsed_bid_values(listing, payload)
    bid = ExchangeBid(
        listing_id=listing.id,
        bidder_user_id=bidder_user.id if bidder_user else None,
        bidder_name=bidder_name,
        bidder_contact=bidder_contact,
        quantity=quantity,
        amount=amount,
        message=str(payload.get("message") or "").strip()[:2000] or None,
        expires_at=expires_at,
    )
    db.add(bid)
    db.flush()
    if listing.seller_user_id:
        label = bidder_user.display_name if bidder_user else bidder_name or "An external bidder"
        db.add(
            ExchangeNotification(
                user_id=listing.seller_user_id,
                listing_id=listing.id,
                notification_kind="auction_bid_received",
                title=f"New bid on {listing.title}",
                body=f"{label} bid {amount:,.2f} ISK for {quantity} unit(s).",
            )
        )
    db.add(
        ExchangeAuditLog(
            listing_id=listing.id,
            actor_user_id=bidder_user.id if bidder_user else None,
            event_kind="auction_bid_submitted",
            detail=f"Bid {amount:,.2f} ISK for {quantity} unit(s).",
        )
    )
    return bid


@router.get("/public/listings/{public_id}")
def get_public_exchange_listing(public_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return public_listing_payload(load_public_listing(db, public_id))


@router.post("/public/listings/{public_id}/appraise")
async def appraise_public_exchange_listing(
    public_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    listing = load_public_listing(db, public_id)
    if listing.quantity_available <= 0:
        raise HTTPException(status_code=409, detail="This listing has no available stock to appraise.")
    fresh_after = datetime.now(timezone.utc) - timedelta(minutes=5)
    if listing.appraisals and all(
        row.priced_at and normalized_datetime(row.priced_at) >= fresh_after
        for row in listing.appraisals
    ):
        return public_listing_payload(listing)
    manifest = appraisal_manifest(list(listing.items), listing.quantity_available)
    result = await appraise_market(db, manifest, DEFAULT_HUB_KEYS)
    for row in list(listing.appraisals):
        db.delete(row)
    now = datetime.now(timezone.utc)
    for appraisal in market_appraisal_payload(result):
        listing.appraisals.append(
            ExchangeAppraisal(
                hub_key=appraisal["hub_key"],
                hub_name=appraisal["hub_name"],
                immediate_buy_value=appraisal["immediate_buy_value"],
                immediate_sell_value=appraisal["immediate_sell_value"],
                replacement_value=appraisal["replacement_value"],
                priced_at=now,
            )
        )
    db.commit()
    return public_listing_payload(load_public_listing(db, public_id))


@router.post("/public/listings/{public_id}/bids")
def create_public_exchange_bid(
    public_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    listing = db.scalar(select(ExchangeListing).where(ExchangeListing.public_id == public_id).with_for_update())
    if listing is None or listing.visibility != "public" or listing.status == "draft":
        raise HTTPException(status_code=404, detail="Public Exchange listing not found.")
    name, contact = clean_external_identity(payload)
    pending_count = db.scalar(
        select(func.count(ExchangeBid.id)).where(
            ExchangeBid.listing_id == listing.id,
            ExchangeBid.bidder_user_id.is_(None),
            ExchangeBid.bidder_contact == contact,
            ExchangeBid.status == "pending",
        )
    ) or 0
    if pending_count >= 10:
        raise HTTPException(status_code=429, detail="This contact already has several pending bids on the auction.")
    bid = add_bid(db, listing, payload, bidder_user=None, bidder_name=name, bidder_contact=contact)
    db.commit()
    listing = load_public_listing(db, public_id)
    return {"bid": bid_payload(bid), "listing": public_listing_payload(listing)}


@router.post("/listings/{public_id}/bids")
def create_authenticated_exchange_bid(
    public_id: str,
    payload: dict[str, Any],
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    listing = db.scalar(select(ExchangeListing).where(ExchangeListing.public_id == public_id).with_for_update())
    if listing is None:
        raise HTTPException(status_code=404, detail="Exchange listing not found.")
    if listing.seller_user_id == current_user.id:
        raise HTTPException(status_code=409, detail="You cannot bid on your own auction.")
    bid = add_bid(
        db,
        listing,
        payload,
        bidder_user=current_user,
        bidder_name=None,
        bidder_contact=str(payload.get("bidder_contact") or "").strip()[:255] or None,
    )
    db.commit()
    listing = db.scalar(listing_query().where(ExchangeListing.id == listing.id))
    return serialize_listing(listing, current_user)


@router.post("/listings/{public_id}/bids/{bid_id}/decision")
def decide_exchange_bid(
    public_id: str,
    bid_id: int,
    payload: dict[str, Any],
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    listing = db.scalar(select(ExchangeListing).where(ExchangeListing.public_id == public_id).with_for_update())
    if listing is None:
        raise HTTPException(status_code=404, detail="Exchange listing not found.")
    if listing.seller_user_id != current_user.id and current_user.role not in {"host", "admin"}:
        raise HTTPException(status_code=403, detail="Only the seller can manage auction bids.")
    bid = db.get(ExchangeBid, bid_id)
    if bid is None or bid.listing_id != listing.id:
        raise HTTPException(status_code=404, detail="Auction bid not found.")
    if bid.status != "pending":
        raise HTTPException(status_code=409, detail="This bid has already been decided.")
    action = str(payload.get("action") or "").strip().lower()
    if action not in {"accept", "reject"}:
        raise HTTPException(status_code=400, detail="Choose accept or reject.")
    if action == "reject":
        bid.status = "rejected"
        audit(db, listing, current_user, "auction_bid_rejected", f"Rejected bid {bid.id}.")
    else:
        if listing_has_ended(listing) and listing.status not in {"active", "offer_pending", "partially_claimed"}:
            raise HTTPException(status_code=409, detail="This auction can no longer accept a winning bid.")
        if bid.quantity > listing.quantity_available:
            raise HTTPException(status_code=409, detail="The listing no longer has enough quantity for this bid.")
        bid.status = "accepted"
        listing.quantity_available -= bid.quantity
        listing.status = "reserved" if listing.quantity_available == 0 else "partially_claimed"
        db.add(
            ExchangeTransaction(
                listing_id=listing.id,
                bid_id=bid.id,
                seller_user_id=listing.seller_user_id,
                buyer_user_id=bid.bidder_user_id,
                quantity=bid.quantity,
                total_price=bid.amount,
            )
        )
        if listing.quantity_available == 0:
            for other in listing.bids:
                if other.id != bid.id and other.status == "pending":
                    other.status = "rejected"
        if bid.bidder_user_id:
            db.add(
                ExchangeNotification(
                    user_id=bid.bidder_user_id,
                    listing_id=listing.id,
                    notification_kind="auction_bid_accepted",
                    title=f"Bid accepted: {listing.title}",
                    body="Contact the seller to arrange the in-game contract.",
                )
            )
        audit(db, listing, current_user, "auction_bid_accepted", f"Accepted bid {bid.id} for {float(bid.amount):,.2f} ISK.")
    db.commit()
    listing = db.scalar(listing_query().where(ExchangeListing.id == listing.id))
    return serialize_listing(listing, current_user)


@router.post("/listings/{public_id}/bids/{bid_id}/withdraw")
def withdraw_exchange_bid(
    public_id: str,
    bid_id: int,
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    listing = db.scalar(listing_query().where(ExchangeListing.public_id == public_id))
    bid = db.get(ExchangeBid, bid_id)
    if listing is None or bid is None or bid.listing_id != listing.id:
        raise HTTPException(status_code=404, detail="Auction bid not found.")
    if bid.bidder_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the bidder can withdraw this bid.")
    if bid.status != "pending":
        raise HTTPException(status_code=409, detail="This bid can no longer be withdrawn.")
    bid.status = "withdrawn"
    audit(db, listing, current_user, "auction_bid_withdrawn", f"Withdrew bid {bid.id}.")
    db.commit()
    listing = db.scalar(listing_query().where(ExchangeListing.id == listing.id))
    return serialize_listing(listing, current_user)