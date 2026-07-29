from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EveType, ExchangeListing, ExchangeListingItem
from app.services.exchange_bids import BID_VISIBILITIES, active_bid_rows

VISIBILITIES = {"users", "public"}


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def optional_datetime(value: Any, field: str) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{field} must be an ISO date and time.") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def replace_items(db: Session, listing: ExchangeListing, raw_items: Any) -> None:
    if not isinstance(raw_items, list) or not raw_items:
        raise HTTPException(status_code=400, detail="Add at least one listing item.")
    replacements: list[ExchangeListingItem] = []
    for raw in raw_items[:100]:
        if not isinstance(raw, dict):
            continue
        name = " ".join(str(raw.get("name") or raw.get("item_name") or "").split())
        quantity = int(raw.get("quantity") or 0)
        if not name or quantity <= 0:
            continue
        item_type = None
        if raw.get("type_id"):
            item_type = db.get(EveType, int(raw["type_id"]))
        if item_type is None:
            item_type = db.scalar(select(EveType).where(EveType.name.ilike(name)).limit(1))
        replacements.append(
            ExchangeListingItem(
                type_id=item_type.type_id if item_type else None,
                item_name=item_type.name if item_type else name[:255],
                quantity=quantity,
                notes=str(raw.get("notes") or "").strip()[:500] or None,
            )
        )
    if not replacements:
        raise HTTPException(status_code=400, detail="Add at least one valid listing item.")
    listing.items.clear()
    listing.items.extend(replacements)
    listing.appraisals.clear()


def apply_listing_edits(db: Session, listing: ExchangeListing, payload: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    committed = max(0, int(listing.quantity_total) - int(listing.quantity_available))
    has_commitments = committed > 0 or bool(active_bid_rows(listing.bids))
    previous_total = int(listing.quantity_total)
    previous_unit_price = (
        float(listing.asking_price) / previous_total
        if listing.asking_price is not None and previous_total > 0
        else None
    )

    if "title" in payload:
        title = " ".join(str(payload.get("title") or "").split())
        if not title:
            raise HTTPException(status_code=400, detail="Listing title is required.")
        listing.title = title[:255]
        changed.append("title")

    for field, limit in {
        "summary": 500,
        "contact_method": 255,
        "location_text": 500,
        "division_name": 255,
        "condition_notes": 500,
    }.items():
        if field in payload:
            setattr(listing, field, str(payload.get(field) or "").strip()[:limit] or None)
            changed.append(field)

    for field in ("description", "eligibility_notes"):
        if field in payload:
            setattr(listing, field, str(payload.get(field) or "").strip() or None)
            changed.append(field)

    if "visibility" in payload:
        visibility = str(payload.get("visibility") or "users").strip().lower()
        if visibility not in VISIBILITIES:
            raise HTTPException(status_code=400, detail="Unsupported listing visibility.")
        listing.visibility = visibility
        changed.append("visibility")

    if "sell_as_complete_lot" in payload:
        listing.sell_as_complete_lot = bool(payload.get("sell_as_complete_lot"))
        changed.append("lot policy")

    if "expires_at" in payload:
        expires_at = optional_datetime(payload.get("expires_at"), "expires_at")
        if listing.listing_type == "auction" and (expires_at is None or expires_at <= datetime.now(timezone.utc)):
            raise HTTPException(status_code=400, detail="Auctions require a future ending time.")
        listing.expires_at = expires_at
        changed.append("expiration")

    try:
        total = int(payload.get("quantity_total", listing.quantity_total))
        available = int(payload.get("quantity_available", listing.quantity_available))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Stock values must be whole numbers.") from exc
    if total < max(1, committed):
        raise HTTPException(status_code=409, detail=f"{committed} committed unit(s) cannot be removed from total stock.")
    if available < 0 or available > total - committed:
        raise HTTPException(
            status_code=409,
            detail=f"Available stock must be between 0 and {total - committed}; {committed} unit(s) are committed.",
        )
    stock_changed = total != listing.quantity_total or available != listing.quantity_available
    if stock_changed:
        listing.quantity_total = total
        listing.quantity_available = available
        listing.appraisals.clear()
        if listing.listing_type == "fixed" and previous_unit_price is not None:
            listing.asking_price = previous_unit_price * total
        changed.append("stock")

    if listing.listing_type == "fixed" and "unit_price" in payload:
        unit_price = optional_float(payload.get("unit_price"))
        if unit_price is not None and unit_price < 0:
            raise HTTPException(status_code=400, detail="Price per package cannot be negative.")
        listing.asking_price = unit_price * total if unit_price is not None else None
        changed.append("price per package")

    if listing.listing_type == "auction" and any(key in payload for key in ("minimum_bid", "reserve_price", "bid_visibility")):
        if has_commitments:
            raise HTTPException(status_code=409, detail="Auction pricing cannot change after a bid or reservation exists.")
        minimum = optional_float(payload.get("minimum_bid", listing.minimum_bid))
        reserve = optional_float(payload.get("reserve_price", listing.reserve_price))
        if minimum is None or minimum <= 0:
            raise HTTPException(status_code=400, detail="Auctions require a positive minimum bid.")
        if reserve is not None and reserve < minimum:
            raise HTTPException(status_code=400, detail="The hidden reserve cannot be below the minimum bid.")
        visibility = str(payload.get("bid_visibility", listing.bid_visibility)).strip().lower()
        if visibility not in BID_VISIBILITIES:
            raise HTTPException(status_code=400, detail="Unsupported bid visibility.")
        listing.minimum_bid = minimum
        listing.reserve_price = reserve
        listing.bid_visibility = visibility
        changed.append("auction pricing")

    if "items" in payload:
        if has_commitments:
            raise HTTPException(status_code=409, detail="Package contents cannot change after a bid or reservation exists.")
        replace_items(db, listing, payload["items"])
        changed.append("package contents")

    if stock_changed and available == 0 and listing.status in {"active", "partially_claimed", "reserved"}:
        listing.status = "completed"
        changed.append("status")
    elif stock_changed and available > 0 and listing.status in {"completed", "reserved"}:
        listing.status = "active"
        changed.append("status")
    return changed
