"""On-demand analytics: no shared snapshots, corporation scope, or staff override."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, StrictBool, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.hypernet import require_hypernet
from app.db.session import get_db
from app.models import EveCharacter, EveGroup, EveType, HyperNetAnalyticsPreference, HyperNetOffer, HyperNetParticipation, User
from app.services.hypernet_disposition import realized_item_result, utc

router = APIRouter(prefix="/hypernet/analytics", tags=["hypernet"])


class AnalyticsConsent(BaseModel):
    enabled: StrictBool
    character_id: int | None = Field(default=None, gt=0)


def eligible_characters(db: Session, user: User):
    # An account can still analyse its own historical transactions after unlinking a pilot.
    return db.scalars(select(EveCharacter).where(or_(
        EveCharacter.owner_user_id == user.id,
        EveCharacter.id.in_(select(HyperNetOffer.seller_character_id).where(HyperNetOffer.owner_user_id == user.id)),
        EveCharacter.id.in_(select(HyperNetParticipation.character_id).where(HyperNetParticipation.user_id == user.id)),
    )).order_by(EveCharacter.name, EveCharacter.id)).all()


def consent_payload(db: Session, user: User):
    enabled = set(db.scalars(select(HyperNetAnalyticsPreference.character_id).where(
        HyperNetAnalyticsPreference.user_id == user.id, HyperNetAnalyticsPreference.enabled.is_(True),
    )).all())
    return {"characters": [{"id": row.id, "name": row.name, "enabled": row.id in enabled}
                           for row in eligible_characters(db, user)]}


@router.get("/preferences")
def analytics_preferences(response: Response, user: User = Depends(require_hypernet), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return consent_payload(db, user)


@router.patch("/preferences")
def update_analytics_preferences(payload: AnalyticsConsent, response: Response,
                                 user: User = Depends(require_hypernet), db: Session = Depends(get_db)):
    characters = eligible_characters(db, user)
    if payload.character_id is not None:
        characters = [row for row in characters if row.id == payload.character_id]
        if not characters:
            raise HTTPException(404, "Character not found")
    for character in characters:
        preference = db.get(HyperNetAnalyticsPreference, (user.id, character.id))
        if preference is None:
            preference = HyperNetAnalyticsPreference(user_id=user.id, character_id=character.id)
            db.add(preference)
        preference.enabled = payload.enabled
    # Disabling the account also clears consent for any no-longer-eligible characters.
    if payload.character_id is None and not payload.enabled:
        for preference in db.scalars(select(HyperNetAnalyticsPreference).where(HyperNetAnalyticsPreference.user_id == user.id)):
            preference.enabled = False
    db.commit()
    response.headers["Cache-Control"] = "private, no-store"
    return consent_payload(db, user)


def event_time(row):
    if isinstance(row, HyperNetOffer):
        if row.market_sale:
            return utc(datetime.fromisoformat(row.market_sale["sold_at"].replace("Z", "+00:00")))
        return utc(row.completed_at or row.reconciled_at or row.created_offer_at)
    return utc(row.completed_at or row.created_at)


def metrics(offers, bids) -> dict[str, Any]:
    resolved = [row for row in bids if row.outcome in {"won", "lost"}]
    wins = [row for row in resolved if row.outcome == "won"]
    spend = sum((row.total_spent for row in resolved), Decimal(0))
    missing = sum(row.profit_loss is None for row in resolved)
    net = sum((row.profit_loss or Decimal(0) for row in resolved), Decimal(0))
    expected = sum(row.nodes_purchased / row.total_nodes for row in resolved)
    completed = [row for row in offers if row.status == "completed"]
    settled = [row for row in offers if row.status == "completed" or row.market_sale]
    seller_missing = sum(row.final_profit is None and not row.market_sale for row in settled)
    return {
        "buying": {
            "records": len(bids), "wins": len(wins), "losses": len(resolved) - len(wins),
            "pending": sum(row.outcome == "pending" for row in bids),
            "refunded": sum(row.outcome in {"expired", "cancelled"} for row in bids),
            "resolved_spend": float(spend),
            "pending_spend": float(sum(row.total_spent for row in bids if row.outcome == "pending")),
            "refunded_spend": float(sum(row.total_spent for row in bids if row.outcome in {"expired", "cancelled"})),
            "lost_spend": float(sum(row.total_spent for row in resolved if row.outcome == "lost")),
            "won_value": float(sum(row.item_value_at_completion or 0 for row in wins)),
            "recorded_result": float(net), "unvalued_results": missing,
            "win_rate": len(wins) / len(resolved) * 100 if resolved else None,
            "roi": float(net / spend * 100) if spend and not missing else None,
            "expected_wins": expected, "luck_delta": len(wins) - expected,
        },
        "selling": {
            "records": len(offers), "completed": len(completed),
            "retained": sum(row.quantity for row in completed if row.winner == "seller"),
            "lost": sum(row.quantity for row in completed if row.winner == "external"),
            "unknown": sum(row.winner not in {"seller", "external"} for row in completed),
            "active": sum(row.status in {"active", "awaiting_reconciliation"} for row in offers),
            "expired": sum(row.status == "expired" for row in offers),
            "gross_completed": float(sum(row.total_offer_price for row in completed)),
            "seeded_spend": float(sum(row.total_offer_price * row.seller_owned_nodes / row.total_nodes for row in completed)),
            "recorded_result": float(sum(realized_item_result(row) for row in settled)),
            "unvalued_results": seller_missing,
            "completion_rate": len(completed) / len([row for row in offers if row.status in {"completed", "expired", "cancelled"}]) * 100
                if any(row.status in {"completed", "expired", "cancelled"} for row in offers) else None,
        },
    }


@router.get("")
def private_hypernet_analytics(response: Response, days: int = Query(30, ge=0, le=3660),
                               character_id: int | None = Query(None, gt=0),
                               user: User = Depends(require_hypernet), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    consent = consent_payload(db, user)
    characters = {row["id"]: row["name"] for row in consent["characters"] if row["enabled"]
                  and (character_id is None or row["id"] == character_id)}
    if not characters:
        return None
    offers = db.scalars(select(HyperNetOffer).options(
        selectinload(HyperNetOffer.item_type).selectinload(EveType.group).selectinload(EveGroup.category),
    ).where(HyperNetOffer.owner_user_id == user.id, HyperNetOffer.seller_character_id.in_(characters),
            HyperNetOffer.status.notin_({"draft", "invalid"}))).all()
    bids = db.scalars(select(HyperNetParticipation).options(
        selectinload(HyperNetParticipation.item_type).selectinload(EveType.group).selectinload(EveGroup.category),
    ).where(HyperNetParticipation.user_id == user.id, HyperNetParticipation.character_id.in_(characters))).all()
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        offers = [row for row in offers if event_time(row) >= cutoff]
        bids = [row for row in bids if event_time(row) >= cutoff]
    if not offers and not bids:
        return None
    by_character = []
    for cid, name in characters.items():
        char_offers = [row for row in offers if row.seller_character_id == cid]
        char_bids = [row for row in bids if row.character_id == cid]
        if char_offers or char_bids:
            by_character.append({"id": cid, "name": name, **metrics(char_offers, char_bids)})
    items = {}
    for row in [*offers, *bids]:
        item = row.item_type
        tid = row.type_id if isinstance(row, HyperNetOffer) else row.item_type_id
        if tid not in items:
            items[tid] = {"offers": [], "bids": [], "type_id": tid, "name": item.name if item else f"Type {tid}",
                          "is_ship": bool(item and item.group and item.group.category_id == 6)}
        items[tid]["offers" if isinstance(row, HyperNetOffer) else "bids"].append(row)
    item_rows = [{"type_id": item["type_id"], "name": item["name"], "is_ship": item["is_ship"],
                  **metrics(item["offers"], item["bids"])} for item in items.values()]
    trend = defaultdict(lambda: {"buying": Decimal(0), "selling": Decimal(0), "buying_count": 0, "selling_count": 0})
    for row in bids:
        if row.outcome in {"won", "lost"} and row.profit_loss is not None:
            month = event_time(row).strftime("%Y-%m-01")
            trend[month]["buying"] += row.profit_loss
            trend[month]["buying_count"] += 1
    for row in offers:
        if row.market_sale or (row.status == "completed" and row.final_profit is not None):
            month = event_time(row).strftime("%Y-%m-01")
            trend[month]["selling"] += realized_item_result(row)
            trend[month]["selling_count"] += 1
    return {"days": days, **metrics(offers, bids), "characters": by_character,
            "items": sorted(item_rows, key=lambda row: row["name"].lower()),
            "monthly_results": [{"date": month, **{key: float(value) for key, value in values.items()}}
                                for month, values in sorted(trend.items())]}
