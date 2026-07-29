from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from fastapi import HTTPException

from app.models import ExchangeBid, ExchangeListing

BID_VISIBILITIES = {"public", "highest_only", "private"}
PENDING_BID_STATUSES = {"pending"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalized_datetime(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def listing_has_ended(listing: ExchangeListing, now: datetime | None = None) -> bool:
    expires_at = normalized_datetime(listing.expires_at)
    return bool(expires_at and expires_at <= (now or utc_now()))


def active_bid_rows(
    bids: Iterable[ExchangeBid],
    now: datetime | None = None,
) -> list[ExchangeBid]:
    current = now or utc_now()
    return [
        bid
        for bid in bids
        if bid.status in PENDING_BID_STATUSES
        and (normalized_datetime(bid.expires_at) is None or normalized_datetime(bid.expires_at) > current)
    ]


def bidder_label(bid: ExchangeBid) -> str:
    if bid.bidder_user:
        return bid.bidder_user.display_name
    return bid.bidder_name or "External bidder"


def highest_active_bid(listing: ExchangeListing) -> ExchangeBid | None:
    rows = active_bid_rows(listing.bids)
    return max(rows, key=lambda bid: (float(bid.amount), bid.created_at), default=None)


def next_bid_floor(listing: ExchangeListing) -> float:
    highest = highest_active_bid(listing)
    configured = float(listing.minimum_bid or 0)
    if highest is None:
        return max(configured, 0.01)
    return max(configured, float(highest.amount) + 0.01)


def validate_bid(
    listing: ExchangeListing,
    *,
    amount: float,
    quantity: int,
) -> None:
    if listing.listing_type != "auction":
        raise HTTPException(status_code=409, detail="This listing is not accepting auction bids.")
    if listing.status not in {"active", "offer_pending", "partially_claimed"}:
        raise HTTPException(status_code=409, detail="This auction is not active.")
    if listing_has_ended(listing):
        raise HTTPException(status_code=409, detail="This auction has ended.")
    if quantity < 1 or quantity > listing.quantity_available:
        raise HTTPException(status_code=409, detail=f"Bid quantity must be between 1 and {listing.quantity_available}.")
    if listing.sell_as_complete_lot and quantity != listing.quantity_available:
        raise HTTPException(status_code=409, detail="The seller is auctioning the remaining stock as one lot.")
    floor = next_bid_floor(listing)
    if amount < floor:
        raise HTTPException(status_code=409, detail=f"The next bid must be at least {floor:,.2f} ISK.")


def bid_payload(bid: ExchangeBid, *, include_contact: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": bid.id,
        "bidder_name": bidder_label(bid),
        "external": bid.bidder_user_id is None,
        "quantity": bid.quantity,
        "amount": float(bid.amount),
        "message": bid.message,
        "status": bid.status,
        "expires_at": bid.expires_at.isoformat() if bid.expires_at else None,
        "created_at": bid.created_at.isoformat() if bid.created_at else None,
    }
    if include_contact:
        payload["bidder_contact"] = bid.bidder_contact
        payload["bidder_user_id"] = bid.bidder_user_id
    return payload


def auction_payload(
    listing: ExchangeListing,
    *,
    is_owner: bool,
    public_view: bool = False,
) -> dict[str, Any]:
    pending = sorted(
        active_bid_rows(listing.bids),
        key=lambda bid: (float(bid.amount), bid.created_at),
        reverse=True,
    )
    highest = pending[0] if pending else None
    visibility = listing.bid_visibility if listing.bid_visibility in BID_VISIBILITIES else "private"
    visible_bids: list[dict[str, Any]] = []
    if is_owner:
        visible_bids = [
            bid_payload(bid, include_contact=True)
            for bid in sorted(listing.bids, key=lambda row: row.created_at, reverse=True)
        ]
    elif visibility == "public":
        visible_bids = [bid_payload(bid) for bid in pending]

    highest_amount = None
    if highest and (is_owner or visibility in {"public", "highest_only"}):
        highest_amount = float(highest.amount)

    return {
        "bid_visibility": visibility,
        "bid_count": len(pending),
        "highest_bid": highest_amount,
        "next_minimum_bid": next_bid_floor(listing) if not listing_has_ended(listing) else None,
        "reserve_met": bool(
            highest
            and listing.reserve_price is not None
            and float(highest.amount) >= float(listing.reserve_price)
        ),
        "auction_ended": listing_has_ended(listing),
        "bids": visible_bids,
        "public_view": public_view,
    }