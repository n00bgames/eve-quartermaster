from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import (
    EveCharacter,
    EveType,
    ExchangeAppraisal,
    ExchangeAuditLog,
    ExchangeBid,
    ExchangeClaim,
    ExchangeListing,
    ExchangeListingItem,
    ExchangeNotification,
    ExchangeTransaction,
    User,
)
from app.services.exchange_bids import BID_VISIBILITIES, auction_payload
from app.services.exchange_listing_updates import apply_listing_edits
from app.services.market import DEFAULT_HUB_KEYS, appraise_market
from app.services.permissions import can_view_section

router = APIRouter(prefix="/corporate-exchange", tags=["corporate-exchange"])

LISTING_TYPES = {"fixed", "auction", "offers", "barter", "wanted", "service"}
LISTING_STATUSES = {
    "draft",
    "active",
    "partially_claimed",
    "reserved",
    "offer_pending",
    "accepted",
    "contract_pending",
    "contract_created",
    "delivered",
    "completed",
    "expired",
    "cancelled",
    "disputed",
}
VISIBILITIES = {"public", "users", "own_corporation", "alliance", "selected"}
ACTIVE_STATUSES = {"active", "partially_claimed", "reserved", "offer_pending"}


def require_exchange(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not can_view_section(current_user, "exchange", db):
        raise HTTPException(status_code=403, detail="Corporate Exchange access is required.")
    return current_user


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def parse_datetime(value: Any, field: str) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field} must be an ISO date and time.") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def clean_choice(value: Any, allowed: set[str], default: str, field: str) -> str:
    clean = str(value or default).strip().lower()
    if clean not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported {field}.")
    return clean


def listing_query():
    return select(ExchangeListing).options(
        selectinload(ExchangeListing.seller_user),
        selectinload(ExchangeListing.seller_character),
        selectinload(ExchangeListing.seller_corporation),
        selectinload(ExchangeListing.location),
        selectinload(ExchangeListing.items).selectinload(ExchangeListingItem.item_type),
        selectinload(ExchangeListing.appraisals),
        selectinload(ExchangeListing.claims).selectinload(ExchangeClaim.claimant_user),
        selectinload(ExchangeListing.bids).selectinload(ExchangeBid.bidder_user),
    )


def listing_location(listing: ExchangeListing) -> str:
    base = listing.location_text or (listing.location.name if listing.location else None) or "Unresolved location"
    if listing.division_name:
        return f"{base} - {listing.division_name}"
    return base


def appraisal_payload(row: ExchangeAppraisal, asking_price: float | None) -> dict[str, Any]:
    replacement = as_float(row.replacement_value)
    delta = asking_price - replacement if asking_price is not None and replacement else None
    return {
        "hub_key": row.hub_key,
        "hub_name": row.hub_name,
        "immediate_buy_value": as_float(row.immediate_buy_value),
        "immediate_sell_value": as_float(row.immediate_sell_value),
        "replacement_value": replacement,
        "asking_delta": delta,
        "asking_delta_percent": (delta / replacement * 100) if delta is not None and replacement else None,
        "source": row.source,
        "priced_at": row.priced_at.isoformat() if row.priced_at else None,
    }


def appraisal_manifest(items: list[Any], quantity_total: int = 1) -> str:
    package_count = max(1, int(quantity_total or 1))
    lines: list[str] = []
    for item in items[:100]:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("item_name") or "").strip()
            quantity = int(item.get("quantity") or 0)
        else:
            name = str(getattr(item, "item_name", "") or "").strip()
            quantity = int(getattr(item, "quantity", 0) or 0)
        if name and quantity > 0:
            lines.append(f"{quantity * package_count} {name}")
    if not lines:
        raise HTTPException(status_code=400, detail="Add at least one valid listing item to appraise.")
    return "\n".join(lines)


def market_appraisal_payload(result: dict[str, Any]) -> list[dict[str, Any]]:
    hub_names = {row["key"]: row["label"] for row in result.get("hubs", [])}
    priced_at = datetime.now(timezone.utc).isoformat()
    return [
        {
            "hub_key": hub_key,
            "hub_name": hub_names.get(hub_key, hub_key.title()),
            "immediate_buy_value": totals.get("buy_total"),
            "immediate_sell_value": totals.get("sell_total"),
            "replacement_value": totals.get("sell_total"),
            "asking_delta": None,
            "asking_delta_percent": None,
            "source": "ESI market orders",
            "priced_at": priced_at,
        }
        for hub_key, totals in result.get("totals", {}).items()
    ]


def serialize_listing(
    listing: ExchangeListing,
    current_user: User,
    *,
    include_private: bool = False,
) -> dict[str, Any]:
    stored_asking_price = as_float(listing.asking_price)
    unit_price = stored_asking_price / listing.quantity_total if stored_asking_price is not None and listing.quantity_total else None
    asking_price = unit_price * listing.quantity_available if unit_price is not None else None
    is_owner = listing.seller_user_id == current_user.id
    claims = []
    if include_private or is_owner:
        claims = [
            {
                "id": claim.id,
                "claimant_user_id": claim.claimant_user_id,
                "claimant_name": claim.claimant_user.display_name if claim.claimant_user else "Deleted user",
                "quantity": claim.quantity,
                "unit_price": as_float(claim.unit_price),
                "total_price": as_float(claim.total_price),
                "status": claim.status,
                "expires_at": claim.expires_at.isoformat() if claim.expires_at else None,
                "contract_id": claim.contract_id,
                "contract_notes": claim.contract_notes,
                "created_at": claim.created_at.isoformat() if claim.created_at else None,
            }
            for claim in sorted(listing.claims, key=lambda row: row.created_at, reverse=True)
        ]
    payload = {
        "id": listing.id,
        "public_id": listing.public_id,
        "listing_type": listing.listing_type,
        "status": listing.status,
        "title": listing.title,
        "summary": listing.summary,
        "description": listing.description,
        "seller_user_id": listing.seller_user_id,
        "seller_name": listing.seller_character.name if listing.seller_character else (listing.seller_user.display_name if listing.seller_user else "Deleted user"),
        "seller_character_id": listing.seller_character.character_id if listing.seller_character else None,
        "seller_corporation_id": listing.seller_corporation.corporation_id if listing.seller_corporation else None,
        "seller_corporation_name": listing.seller_corporation.name if listing.seller_corporation else None,
        "contact_method": listing.contact_method,
        "quantity_total": listing.quantity_total,
        "quantity_available": listing.quantity_available,
        "asking_price": asking_price,
        "unit_price": unit_price,
        "minimum_bid": as_float(listing.minimum_bid),
        "reserve_price": as_float(listing.reserve_price) if is_owner else None,
        "sell_as_complete_lot": listing.sell_as_complete_lot,
        "bid_visibility": listing.bid_visibility,
        "visibility": listing.visibility,
        "eligibility_notes": listing.eligibility_notes,
        "location": listing_location(listing),
        "location_text": listing.location_text,
        "division_name": listing.division_name,
        "condition_notes": listing.condition_notes,
        "expires_at": listing.expires_at.isoformat() if listing.expires_at else None,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
        "updated_at": listing.updated_at.isoformat() if listing.updated_at else None,
        "is_owner": is_owner,
        "items": [
            {
                "id": item.id,
                "type_id": item.type_id,
                "name": item.item_type.name if item.item_type else item.item_name,
                "quantity": item.quantity,
                "asset_id": item.asset_id,
                "notes": item.notes,
            }
            for item in listing.items
        ],
        "appraisals": [
            appraisal_payload(row, asking_price)
            for row in sorted(listing.appraisals, key=lambda appraisal: appraisal.hub_name)
        ],
        "claims": claims,
    }
    if listing.listing_type == "auction":
        payload.update(auction_payload(listing, is_owner=is_owner))
    return payload


def resolve_item_type(db: Session, name: str, type_id: Any) -> EveType | None:
    if type_id:
        return db.get(EveType, int(type_id))
    return db.scalar(select(EveType).where(EveType.name.ilike(name)).limit(1))


def audit(db: Session, listing: ExchangeListing, user: User, event_kind: str, detail: str) -> None:
    db.add(ExchangeAuditLog(listing_id=listing.id, actor_user_id=user.id, event_kind=event_kind, detail=detail))


@router.get("/seller-context")
def exchange_seller_context(
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    characters = db.scalars(
        select(EveCharacter)
        .options(selectinload(EveCharacter.corporation))
        .where(EveCharacter.owner_user_id == current_user.id)
        .order_by(EveCharacter.name)
    ).all()
    return {
        "characters": [
            {
                "id": character.id,
                "character_id": character.character_id,
                "name": character.name,
                "corporation_id": character.corporation.corporation_id if character.corporation else None,
                "corporation_name": character.corporation.name if character.corporation else None,
            }
            for character in characters
        ],
        "default_character_id": characters[0].id if characters else None,
    }


@router.get("/listings")
def list_exchange_listings(
    search: str | None = Query(default=None, max_length=160),
    status: str | None = Query(default=None),
    listing_type: str | None = Query(default=None),
    mine: bool = Query(default=False),
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = listing_query()
    if mine:
        query = query.where(ExchangeListing.seller_user_id == current_user.id)
    elif status is None:
        query = query.where(ExchangeListing.status.in_(ACTIVE_STATUSES))
    if status:
        query = query.where(ExchangeListing.status == clean_choice(status, LISTING_STATUSES, "active", "status"))
    if listing_type:
        query = query.where(ExchangeListing.listing_type == clean_choice(listing_type, LISTING_TYPES, "fixed", "listing type"))
    if search and search.strip():
        needle = f"%{search.strip()}%"
        query = query.where(
            or_(
                ExchangeListing.title.ilike(needle),
                ExchangeListing.summary.ilike(needle),
                ExchangeListing.location_text.ilike(needle),
                ExchangeListing.items.any(ExchangeListingItem.item_name.ilike(needle)),
            )
        )
    listings = db.scalars(query.order_by(ExchangeListing.created_at.desc()).limit(200)).unique().all()
    return {"listings": [serialize_listing(row, current_user) for row in listings]}


@router.post("/appraise-draft")
async def appraise_exchange_draft(
    payload: dict[str, Any],
    _: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise HTTPException(status_code=400, detail="Add at least one listing item to appraise.")
    quantity_total = max(1, int(payload.get("quantity_total") or 1))
    result = await appraise_market(db, appraisal_manifest(raw_items, quantity_total), DEFAULT_HUB_KEYS)
    return {
        "appraisals": market_appraisal_payload(result),
        "unmatched_items": [row["input"] for row in result.get("items", []) if not row.get("matched")],
        "quantity_total": quantity_total,
    }


@router.get("/listings/{public_id}")
def get_exchange_listing(
    public_id: str,
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    listing = db.scalar(listing_query().where(ExchangeListing.public_id == public_id))
    if listing is None:
        raise HTTPException(status_code=404, detail="Exchange listing not found.")
    if listing.status == "draft" and listing.seller_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Exchange listing not found.")
    return serialize_listing(listing, current_user)


@router.post("/listings")
def create_exchange_listing(
    payload: dict[str, Any],
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    title = " ".join(str(payload.get("title") or "").split())
    raw_items = payload.get("items")
    if not title:
        raise HTTPException(status_code=400, detail="Listing title is required.")
    if not isinstance(raw_items, list) or not raw_items:
        raise HTTPException(status_code=400, detail="Add at least one listing item.")
    seller_character = None
    if payload.get("seller_character_id"):
        seller_character = db.get(EveCharacter, int(payload["seller_character_id"]))
        if seller_character is None or seller_character.owner_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Select a character linked to your EQM account.")
    quantity_total = max(1, int(payload.get("quantity_total") or 1))
    listing_type = clean_choice(payload.get("listing_type"), {"fixed", "auction"}, "fixed", "listing type")
    expires_at = parse_datetime(payload.get("expires_at"), "expires_at")
    minimum_bid = as_float(payload.get("minimum_bid"))
    reserve_price = as_float(payload.get("reserve_price"))
    bid_visibility = clean_choice(payload.get("bid_visibility"), BID_VISIBILITIES, "private", "bid visibility")
    if listing_type == "auction":
        if expires_at is None or expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Auctions require a future ending time.")
        if minimum_bid is None or minimum_bid <= 0:
            raise HTTPException(status_code=400, detail="Auctions require a positive minimum bid.")
        if reserve_price is not None and reserve_price < minimum_bid:
            raise HTTPException(status_code=400, detail="The hidden reserve cannot be below the minimum bid.")
    listing = ExchangeListing(
        public_id=secrets.token_urlsafe(12),
        seller_user_id=current_user.id,
        seller_character_id=seller_character.id if seller_character else None,
        seller_corporation_id=seller_character.corporation_id if seller_character else None,
        listing_type=listing_type,
        status=clean_choice(payload.get("status"), {"draft", "active"}, "active", "status"),
        title=title[:255],
        summary=str(payload.get("summary") or "").strip()[:500] or None,
        description=str(payload.get("description") or "").strip() or None,
        contact_method=str(payload.get("contact_method") or "").strip()[:255] or None,
        quantity_total=quantity_total,
        quantity_available=quantity_total,
        asking_price=as_float(payload.get("asking_price")),
        minimum_bid=minimum_bid,
        reserve_price=reserve_price,
        sell_as_complete_lot=bool(payload.get("sell_as_complete_lot")),
        bid_visibility=bid_visibility,
        visibility=clean_choice(payload.get("visibility"), {"users", "public"}, "users", "visibility"),
        eligibility_notes=str(payload.get("eligibility_notes") or "").strip() or None,
        location_text=str(payload.get("location_text") or "").strip()[:500] or None,
        division_name=str(payload.get("division_name") or "").strip()[:255] or None,
        condition_notes=str(payload.get("condition_notes") or "").strip()[:500] or None,
        expires_at=expires_at,
    )
    db.add(listing)
    for raw in raw_items[:100]:
        if not isinstance(raw, dict):
            continue
        name = " ".join(str(raw.get("name") or raw.get("item_name") or "").split())
        quantity = int(raw.get("quantity") or 0)
        if not name or quantity <= 0:
            continue
        item_type = resolve_item_type(db, name, raw.get("type_id"))
        listing.items.append(
            ExchangeListingItem(
                type_id=item_type.type_id if item_type else None,
                item_name=item_type.name if item_type else name[:255],
                quantity=quantity,
                notes=str(raw.get("notes") or "").strip()[:500] or None,
            )
        )
    if not listing.items:
        raise HTTPException(status_code=400, detail="Add at least one valid listing item.")
    db.flush()
    audit(db, listing, current_user, "listing_created", f"Created {listing.listing_type} listing with {len(listing.items)} item lines.")
    db.commit()
    listing = db.scalar(listing_query().where(ExchangeListing.id == listing.id))
    return serialize_listing(listing, current_user)


@router.patch("/listings/{public_id}")
def update_exchange_listing(
    public_id: str,
    payload: dict[str, Any],
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    listing = db.scalar(listing_query().where(ExchangeListing.public_id == public_id))
    if listing is None:
        raise HTTPException(status_code=404, detail="Exchange listing not found.")
    if listing.seller_user_id != current_user.id and current_user.role not in {"host", "admin"}:
        raise HTTPException(status_code=403, detail="Only the seller can manage this listing.")
    changed = apply_listing_edits(db, listing, payload)
    if "status" in payload:
        requested = clean_choice(payload.get("status"), LISTING_STATUSES, listing.status, "status")
        if requested not in {"draft", "active", "cancelled", "completed"}:
            raise HTTPException(status_code=400, detail="That status is managed by the transaction workflow.")
        listing.status = requested
        changed.append("status")
    detail = ", ".join(dict.fromkeys(changed)) if changed else "no fields"
    audit(db, listing, current_user, "listing_updated", f"Updated {detail}; listing status is {listing.status}.")
    db.commit()
    listing = db.scalar(listing_query().where(ExchangeListing.id == listing.id))
    return serialize_listing(listing, current_user)


@router.post("/listings/{public_id}/appraise")
async def appraise_exchange_listing(
    public_id: str,
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    listing = db.scalar(listing_query().where(ExchangeListing.public_id == public_id))
    if listing is None:
        raise HTTPException(status_code=404, detail="Exchange listing not found.")
    if listing.quantity_available <= 0:
        raise HTTPException(status_code=409, detail="Restock this listing before refreshing its appraisal.")
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
    audit(db, listing, current_user, "listing_appraised", f"Priced listing at {len(listing.appraisals)} trade hubs.")
    db.commit()
    listing = db.scalar(listing_query().where(ExchangeListing.id == listing.id))
    return serialize_listing(listing, current_user)


@router.post("/listings/{public_id}/claims")
def claim_exchange_listing(
    public_id: str,
    payload: dict[str, Any],
    current_user: User = Depends(require_exchange),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    listing = db.scalar(
        select(ExchangeListing).where(ExchangeListing.public_id == public_id).with_for_update()
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Exchange listing not found.")
    if listing.listing_type != "fixed" or listing.status not in {"active", "partially_claimed"}:
        raise HTTPException(status_code=409, detail="This listing is not available for an immediate claim.")
    if listing.seller_user_id == current_user.id:
        raise HTTPException(status_code=409, detail="You cannot claim your own listing.")
    quantity = max(1, int(payload.get("quantity") or 1))
    if listing.sell_as_complete_lot and quantity != listing.quantity_available:
        raise HTTPException(status_code=409, detail="The seller requires the remaining stock to be claimed as one lot.")
    if quantity > listing.quantity_available:
        raise HTTPException(status_code=409, detail=f"Only {listing.quantity_available} units remain.")
    asking = as_float(listing.asking_price)
    unit_price = asking / listing.quantity_total if asking is not None else None
    total_price = unit_price * quantity if unit_price is not None else None
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    claim = ExchangeClaim(
        listing_id=listing.id,
        claimant_user_id=current_user.id,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total_price,
        expires_at=expires_at,
    )
    db.add(claim)
    db.flush()
    listing.quantity_available -= quantity
    listing.status = "reserved" if listing.quantity_available == 0 else "partially_claimed"
    db.add(
        ExchangeTransaction(
            listing_id=listing.id,
            claim_id=claim.id,
            seller_user_id=listing.seller_user_id,
            buyer_user_id=current_user.id,
            quantity=quantity,
            total_price=total_price,
        )
    )
    if listing.seller_user_id:
        db.add(
            ExchangeNotification(
                user_id=listing.seller_user_id,
                listing_id=listing.id,
                notification_kind="listing_claimed",
                title=f"{current_user.display_name} claimed {listing.title}",
                body=f"{quantity} listing unit(s) reserved for 48 hours.",
            )
        )
    db.add(
        ExchangeNotification(
            user_id=current_user.id,
            listing_id=listing.id,
            notification_kind="claim_reserved",
            title=f"Reserved: {listing.title}",
            body="Contact the seller to arrange the in-game contract.",
        )
    )
    audit(db, listing, current_user, "listing_claimed", f"Reserved {quantity} listing unit(s).")
    db.commit()
    listing = db.scalar(listing_query().where(ExchangeListing.id == listing.id))
    return serialize_listing(listing, current_user)
