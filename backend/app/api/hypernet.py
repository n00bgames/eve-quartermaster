from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import mean
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import (
    EsiToken,
    EveCharacter,
    EveGroup,
    EveStation,
    EveType,
    HyperNetOffer,
    HyperNetOfferSnapshot,
    HyperNetParticipant,
    Location,
    User,
)
from app.schemas.hypernet import (
    HyperNetCalculatorRequest,
    HyperNetOfferCreate,
    HyperNetOfferPatch,
    HyperNetReconcileRequest,
    HyperNetSnapshotCreate,
)
from app.services.audit import record_audit_event
from app.services.hypernet import data_source, money, offer_financials, progress_metrics, seeded_node_scenario
from app.services.permissions import can_view_section


router = APIRouter(prefix="/hypernet", tags=["hypernet"])
ACTIVE_STATUSES = frozenset({"active", "awaiting_reconciliation"})
TERMINAL_STATUSES = frozenset({"completed", "expired", "cancelled", "invalid"})


def require_hypernet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not can_view_section(current_user, "hypernet", db):
        raise HTTPException(status_code=403, detail="HyperNet Tracker access is required")
    return current_user


def offer_options() -> tuple[Any, ...]:
    return (
        selectinload(HyperNetOffer.seller_character),
        selectinload(HyperNetOffer.item_type).selectinload(EveType.group).selectinload(EveGroup.category),
        selectinload(HyperNetOffer.location),
        selectinload(HyperNetOffer.snapshots),
        selectinload(HyperNetOffer.participants).selectinload(HyperNetParticipant.character),
    )


def owned_offer(db: Session, offer_id: int, user: User) -> HyperNetOffer:
    row = db.scalar(
        select(HyperNetOffer)
        .options(*offer_options())
        .where(HyperNetOffer.id == offer_id, HyperNetOffer.owner_user_id == user.id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="HyperNet offer not found")
    return row


def as_number(value: Decimal | int | float | None) -> float | None:
    return float(value) if value is not None else None


def financial_payload(values: dict[str, Decimal | None]) -> dict[str, float | None]:
    return {key: as_number(value) for key, value in values.items()}


def current_market_values(offer: HyperNetOffer) -> tuple[Decimal | None, Decimal | None]:
    snapshots = sorted(offer.snapshots, key=lambda row: (row.captured_at, row.id))
    latest = snapshots[-1] if snapshots else None
    return (latest.jita_sell if latest else None, latest.local_sell if latest else None)


def offer_calculations(offer: HyperNetOffer) -> dict[str, Any]:
    jita_sell, local_sell = current_market_values(offer)
    financials = offer_financials(
        total_offer_price=offer.total_offer_price,
        total_nodes=offer.total_nodes,
        hypercores_required=offer.hypercores_required,
        hypercore_unit_cost=offer.hypercore_unit_cost,
        acquisition_cost=offer.acquisition_cost,
        desired_profit=offer.desired_profit,
        jita_sell=jita_sell,
        local_sell=local_sell,
    )
    scenario = seeded_node_scenario(
        total_nodes=offer.total_nodes,
        seller_owned_nodes=offer.seller_owned_nodes,
        node_price=financials["node_price"] or 0,
        acquisition_cost=offer.acquisition_cost,
        hypercore_cost=financials["hypercore_cost"] or 0,
        payout_after_fee=financials["payout_after_fee"] or 0,
        current_jita_sell=jita_sell,
    )
    return {
        "financials": financial_payload(financials),
        "seeded_scenario": {
            key: value if isinstance(value, bool) or value is None else as_number(value)
            for key, value in scenario.items()
        },
        "progress": progress_metrics(
            created_at=offer.created_offer_at,
            total_nodes=offer.total_nodes,
            snapshots=offer.snapshots,
        ),
    }


def serialize_snapshot(row: HyperNetOfferSnapshot) -> dict[str, Any]:
    return {
        "id": row.id,
        "captured_at": row.captured_at.isoformat(),
        "nodes_sold": row.nodes_sold,
        "seller_owned_nodes": row.seller_owned_nodes,
        "organic_nodes_sold": max(0, row.nodes_sold - row.seller_owned_nodes),
        "unique_participants": row.unique_participants,
        "jita_buy": as_number(row.jita_buy),
        "jita_sell": as_number(row.jita_sell),
        "local_buy": as_number(row.local_buy),
        "local_sell": as_number(row.local_sell),
        "hypercore_buy": as_number(row.hypercore_buy),
        "hypercore_sell": as_number(row.hypercore_sell),
        "note": row.note,
        "source": row.source,
    }


def serialize_offer(offer: HyperNetOffer, *, detail: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    remaining_seconds = max(0, (offer.expires_at - now).total_seconds()) if offer.status in ACTIVE_STATUSES else 0
    payload = {
        "id": offer.id,
        "status": offer.status,
        "visibility": offer.visibility,
        "seller": {
            "id": offer.seller_character_id,
            "character_id": offer.seller_character.character_id if offer.seller_character else None,
            "name": offer.seller_character.name if offer.seller_character else "Unknown character",
        },
        "item": {
            "type_id": offer.type_id,
            "name": offer.item_type.name if offer.item_type else f"Type {offer.type_id}",
            "group": offer.item_type.group.name if offer.item_type and offer.item_type.group else None,
            "category": offer.item_type.group.category.name if offer.item_type and offer.item_type.group and offer.item_type.group.category else None,
        },
        "quantity": offer.quantity,
        "location": {
            "id": offer.location_id,
            "name": offer.location.name if offer.location else offer.location_name_snapshot or "Location not recorded",
            "eve_location_id": offer.location.eve_location_id if offer.location else None,
        },
        "created_offer_at": offer.created_offer_at.isoformat(),
        "expires_at": offer.expires_at.isoformat(),
        "completed_at": offer.completed_at.isoformat() if offer.completed_at else None,
        "reconciled_at": offer.reconciled_at.isoformat() if offer.reconciled_at else None,
        "remaining_seconds": remaining_seconds,
        "total_offer_price": as_number(offer.total_offer_price),
        "total_nodes": offer.total_nodes,
        "nodes_sold": offer.nodes_sold,
        "nodes_remaining": max(0, offer.total_nodes - offer.nodes_sold),
        "seller_owned_nodes": offer.seller_owned_nodes,
        "organic_nodes_sold": max(0, offer.nodes_sold - offer.seller_owned_nodes),
        "filled_percent": round(offer.nodes_sold / offer.total_nodes * 100, 2),
        "unique_participants": offer.unique_participants,
        "hypercores_required": offer.hypercores_required,
        "hypercore_unit_cost": as_number(offer.hypercore_unit_cost),
        "acquisition_cost": as_number(offer.acquisition_cost),
        "desired_profit": as_number(offer.desired_profit),
        "completion_fee": as_number(offer.completion_fee),
        "payout": as_number(offer.payout),
        "actual_hypercore_cost": as_number(offer.actual_hypercore_cost),
        "final_market_value": as_number(offer.final_market_value),
        "final_profit": as_number(offer.final_profit),
        "winner": offer.winner,
        "item_outcome": offer.item_outcome,
        "notes": offer.notes,
        "source": offer.source,
        "source_reference": offer.source_reference,
        "calculations": offer_calculations(offer),
        "updated_at": offer.updated_at.isoformat(),
    }
    if detail:
        payload["snapshots"] = [serialize_snapshot(row) for row in sorted(offer.snapshots, key=lambda row: (row.captured_at, row.id))]
        payload["participants"] = [
            {
                "id": row.id,
                "character_id": row.character_id,
                "participant_name": row.participant_name,
                "nodes_owned": row.nodes_owned,
                "is_seller": row.is_seller,
                "first_seen_at": row.first_seen_at.isoformat(),
                "last_seen_at": row.last_seen_at.isoformat(),
            }
            for row in sorted(offer.participants, key=lambda row: (not row.is_seller, row.participant_name.casefold()))
        ]
    return payload


def validate_character(db: Session, character_id: int, user: User) -> EveCharacter:
    character = db.get(EveCharacter, character_id)
    if character is None or character.owner_user_id != user.id:
        raise HTTPException(status_code=400, detail="Seller character must belong to your EQM account")
    if not db.scalar(select(EsiToken.id).where(EsiToken.character_id == character.id, EsiToken.revoked_at.is_(None)).limit(1)):
        raise HTTPException(status_code=400, detail="Seller character must have an active ESI link")
    return character


@router.get("/meta")
def hypernet_meta(user: User = Depends(require_hypernet), db: Session = Depends(get_db)) -> dict[str, Any]:
    characters = db.scalars(
        select(EveCharacter)
        .where(
            EveCharacter.owner_user_id == user.id,
            select(EsiToken.id).where(EsiToken.character_id == EveCharacter.id, EsiToken.revoked_at.is_(None)).exists(),
        )
        .order_by(EveCharacter.name)
    ).all()
    return {
        "statuses": ["draft", "active", "awaiting_reconciliation", "completed", "expired", "cancelled", "invalid"],
        "data_sources": [{"key": "manual", "label": "Manual entry", "available": True}],
        "seller_characters": [
            {"id": row.id, "character_id": row.character_id, "name": row.name, "portrait_url": row.portrait_url}
            for row in characters
        ],
        "fee_rate": 0.05,
        "manual_only": True,
    }


@router.get("/search/types")
def hypernet_type_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(12, ge=1, le=30),
    _: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(EveType)
        .options(selectinload(EveType.group).selectinload(EveGroup.category))
        .where(EveType.name.ilike(f"%{q.strip()}%"), EveType.published.is_(True))
        .order_by(EveType.name)
        .limit(limit)
    ).all()
    return [
        {
            "type_id": row.type_id,
            "name": row.name,
            "group": row.group.name if row.group else None,
            "category": row.group.category.name if row.group and row.group.category else None,
        }
        for row in rows
    ]


@router.get("/search/locations")
def hypernet_location_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(12, ge=1, le=30),
    _: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    known = db.scalars(select(Location).where(Location.name.ilike(f"%{q.strip()}%")).order_by(Location.name).limit(limit)).all()
    rows = [
        {"id": row.id, "eve_location_id": row.eve_location_id, "name": row.name, "source": "eqm"}
        for row in known
    ]
    if len(rows) < limit:
        known_eve_ids = {row["eve_location_id"] for row in rows if row["eve_location_id"]}
        stations = db.scalars(
            select(EveStation)
            .where(EveStation.name.ilike(f"%{q.strip()}%"))
            .order_by(EveStation.name)
            .limit(limit - len(rows))
        ).all()
        rows.extend(
            {"id": None, "eve_location_id": row.station_id, "name": row.name or f"Station {row.station_id}", "source": "sde"}
            for row in stations
            if row.station_id not in known_eve_ids
        )
    return rows[:limit]


@router.post("/calculator")
def hypernet_calculator(payload: HyperNetCalculatorRequest, _: User = Depends(require_hypernet)) -> dict[str, Any]:
    financials = offer_financials(**payload.model_dump(exclude={"seller_owned_nodes"}))
    scenario = seeded_node_scenario(
        total_nodes=payload.total_nodes,
        seller_owned_nodes=payload.seller_owned_nodes,
        node_price=financials["node_price"] or 0,
        acquisition_cost=payload.acquisition_cost,
        hypercore_cost=financials["hypercore_cost"] or 0,
        payout_after_fee=financials["payout_after_fee"] or 0,
        current_jita_sell=payload.jita_sell,
    )
    return {
        "financials": financial_payload(financials),
        "seeded_scenario": {
            key: value if isinstance(value, bool) or value is None else as_number(value)
            for key, value in scenario.items()
        },
    }


@router.get("/summary")
def hypernet_summary(user: User = Depends(require_hypernet), db: Session = Depends(get_db)) -> dict[str, Any]:
    offers = db.scalars(
        select(HyperNetOffer)
        .options(*offer_options())
        .where(HyperNetOffer.owner_user_id == user.id)
        .order_by(HyperNetOffer.created_offer_at.desc())
    ).unique().all()
    now = datetime.now(timezone.utc)
    active = [row for row in offers if row.status in ACTIVE_STATUSES]
    completed = [row for row in offers if row.status == "completed"]
    expired = [row for row in offers if row.status == "expired"]
    resolved = completed + expired
    calculations = {row.id: offer_calculations(row) for row in offers}
    completion_hours = [
        (row.completed_at - row.created_offer_at).total_seconds() / 3600
        for row in completed
        if row.completed_at and row.completed_at >= row.created_offer_at
    ]
    first_sale_hours = [
        calculations[row.id]["progress"]["hours_to_first_organic_node"]
        for row in offers
        if calculations[row.id]["progress"]["hours_to_first_organic_node"] is not None
    ]
    lifetime_profit = sum((row.final_profit or Decimal("0")) for row in resolved)
    completed_profit = sum((row.final_profit or Decimal("0")) for row in completed)
    next_expiring = min(active, key=lambda row: row.expires_at, default=None)
    return {
        "active_offers": len(active),
        "nearing_expiration": sum(row.expires_at <= now + timedelta(hours=12) for row in active),
        "nodes_sold": sum(row.nodes_sold for row in active),
        "total_nodes": sum(row.total_nodes for row in active),
        "gross_offer_value": as_number(sum((row.total_offer_price for row in active), Decimal("0"))),
        "expected_payout": sum(calculations[row.id]["financials"]["payout_after_fee"] or 0 for row in active),
        "hypercore_cost": sum(calculations[row.id]["financials"]["hypercore_cost"] or 0 for row in active),
        "estimated_net_proceeds": sum(calculations[row.id]["financials"]["net_proceeds"] or 0 for row in active),
        "estimated_profit": sum(calculations[row.id]["financials"]["profit"] or 0 for row in active),
        "completed_offers": len(completed),
        "expired_offers": len(expired),
        "lifetime_profit": as_number(lifetime_profit),
        "average_profit_per_completed_offer": as_number(completed_profit / len(completed)) if completed else None,
        "completion_rate_percent": round(len(completed) / len(resolved) * 100, 2) if resolved else None,
        "average_hours_to_first_node": mean(first_sale_hours) if first_sale_hours else None,
        "average_hours_to_completion": mean(completion_hours) if completion_hours else None,
        "capital_tied_up": sum(calculations[row.id]["seeded_scenario"]["capital_tied_up"] or 0 for row in active),
        "next_expiring_offer": serialize_offer(next_expiring) if next_expiring else None,
    }


@router.get("/offers")
def list_hypernet_offers(
    status: str = "all",
    type_id: int | None = None,
    seller_character_id: int | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = Query(250, ge=1, le=1000),
    user: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(HyperNetOffer).options(*offer_options()).where(HyperNetOffer.owner_user_id == user.id)
    if status == "active":
        query = query.where(HyperNetOffer.status.in_(ACTIVE_STATUSES))
    elif status != "all":
        query = query.where(HyperNetOffer.status == status)
    if type_id:
        query = query.where(HyperNetOffer.type_id == type_id)
    if seller_character_id:
        query = query.where(HyperNetOffer.seller_character_id == seller_character_id)
    if from_date:
        query = query.where(HyperNetOffer.created_offer_at >= from_date)
    if to_date:
        query = query.where(HyperNetOffer.created_offer_at <= to_date)
    offers = db.scalars(query.order_by(HyperNetOffer.expires_at.desc()).limit(limit)).unique().all()
    return [serialize_offer(row) for row in offers]


@router.post("/offers")
def create_hypernet_offer(
    payload: HyperNetOfferCreate,
    user: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    character = validate_character(db, payload.seller_character_id, user)
    item_type = db.get(EveType, payload.type_id)
    if item_type is None:
        raise HTTPException(status_code=400, detail="Item type was not found in the imported SDE")
    location = db.get(Location, payload.location_id) if payload.location_id else None
    if payload.location_id and location is None:
        raise HTTPException(status_code=400, detail="Location was not found")
    source = data_source(payload.source)
    calculations = offer_financials(
        total_offer_price=payload.total_offer_price,
        total_nodes=payload.total_nodes,
        hypercores_required=payload.hypercores_required,
        hypercore_unit_cost=payload.hypercore_unit_cost,
        acquisition_cost=payload.acquisition_cost,
        desired_profit=payload.desired_profit,
        jita_sell=payload.jita_sell,
        local_sell=payload.local_sell,
    )
    offer = HyperNetOffer(
        owner_user_id=user.id,
        seller_character_id=character.id,
        type_id=item_type.type_id,
        quantity=payload.quantity,
        location_id=location.id if location else None,
        location_name_snapshot=location.name if location else (payload.location_name or "").strip() or None,
        status=payload.status,
        created_offer_at=payload.created_offer_at,
        expires_at=payload.expires_at,
        total_offer_price=money(payload.total_offer_price),
        total_nodes=payload.total_nodes,
        nodes_sold=payload.nodes_sold,
        seller_owned_nodes=payload.seller_owned_nodes,
        unique_participants=payload.unique_participants,
        hypercores_required=payload.hypercores_required,
        hypercore_unit_cost=money(payload.hypercore_unit_cost),
        acquisition_cost=money(payload.acquisition_cost),
        desired_profit=money(payload.desired_profit),
        completion_fee=calculations["completion_fee"],
        payout=calculations["payout_after_fee"],
        notes=payload.notes,
        source=source.key,
        source_reference=source.reference(payload.source_reference),
        created_by_user_id=user.id,
    )
    db.add(offer)
    db.flush()
    db.add(
        HyperNetOfferSnapshot(
            offer_id=offer.id,
            captured_at=payload.created_offer_at,
            nodes_sold=offer.nodes_sold,
            seller_owned_nodes=offer.seller_owned_nodes,
            unique_participants=offer.unique_participants,
            jita_sell=payload.jita_sell,
            local_sell=payload.local_sell,
            source=source.key,
            note="Offer entered in EQM",
            created_by_user_id=user.id,
        )
    )
    record_audit_event(
        db,
        event_kind="hypernet_offer_created",
        title=f"HyperNet offer recorded: {item_type.name}",
        body=f"{payload.total_nodes} nodes · {money(payload.total_offer_price)} ISK · {payload.status}",
        actor_user=user,
    )
    db.commit()
    return serialize_offer(owned_offer(db, offer.id, user), detail=True)


@router.get("/offers/{offer_id}")
def get_hypernet_offer(offer_id: int, user: User = Depends(require_hypernet), db: Session = Depends(get_db)) -> dict[str, Any]:
    return serialize_offer(owned_offer(db, offer_id, user), detail=True)


@router.patch("/offers/{offer_id}")
def patch_hypernet_offer(
    offer_id: int,
    payload: HyperNetOfferPatch,
    user: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    offer = owned_offer(db, offer_id, user)
    if offer.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Reconciled offers cannot be edited")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field in {"hypercore_unit_cost", "acquisition_cost", "desired_profit"} and value is not None:
            value = money(value)
        setattr(offer, field, value)
    if offer.expires_at <= offer.created_offer_at:
        raise HTTPException(status_code=400, detail="expires_at must be after created_offer_at")
    calculations = offer_financials(
        total_offer_price=offer.total_offer_price,
        total_nodes=offer.total_nodes,
        hypercores_required=offer.hypercores_required,
        hypercore_unit_cost=offer.hypercore_unit_cost,
        acquisition_cost=offer.acquisition_cost,
        desired_profit=offer.desired_profit,
    )
    offer.completion_fee = calculations["completion_fee"]
    offer.payout = calculations["payout_after_fee"]
    db.commit()
    return serialize_offer(owned_offer(db, offer.id, user), detail=True)


@router.post("/offers/{offer_id}/snapshots")
def add_hypernet_snapshot(
    offer_id: int,
    payload: HyperNetSnapshotCreate,
    user: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    offer = owned_offer(db, offer_id, user)
    if offer.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Reconciled offers cannot receive progress snapshots")
    if payload.nodes_sold > offer.total_nodes:
        raise HTTPException(status_code=400, detail="nodes_sold cannot exceed total_nodes")
    latest = max(offer.snapshots, key=lambda row: (row.captured_at, row.id), default=None)
    if latest and payload.captured_at < latest.captured_at:
        raise HTTPException(status_code=400, detail="Snapshot time cannot precede the latest snapshot")
    row = HyperNetOfferSnapshot(
        offer_id=offer.id,
        captured_at=payload.captured_at,
        nodes_sold=payload.nodes_sold,
        seller_owned_nodes=payload.seller_owned_nodes,
        unique_participants=payload.unique_participants,
        jita_buy=payload.jita_buy,
        jita_sell=payload.jita_sell,
        local_buy=payload.local_buy,
        local_sell=payload.local_sell,
        hypercore_buy=payload.hypercore_buy,
        hypercore_sell=payload.hypercore_sell,
        note=payload.note,
        source="manual",
        created_by_user_id=user.id,
    )
    db.add(row)
    offer.nodes_sold = payload.nodes_sold
    offer.seller_owned_nodes = payload.seller_owned_nodes
    offer.unique_participants = payload.unique_participants
    if offer.nodes_sold == offer.total_nodes:
        offer.status = "awaiting_reconciliation"
    if payload.participants:
        submitted_names = {entry.participant_name.strip().casefold() for entry in payload.participants}
        db.execute(
            delete(HyperNetParticipant).where(
                HyperNetParticipant.offer_id == offer.id,
                func.lower(HyperNetParticipant.participant_name).not_in(submitted_names),
            )
        )
        existing = {entry.participant_name.casefold(): entry for entry in offer.participants}
        for entry in payload.participants:
            participant = existing.get(entry.participant_name.strip().casefold())
            if participant is None:
                participant = HyperNetParticipant(
                    offer_id=offer.id,
                    participant_name=entry.participant_name.strip(),
                    first_seen_at=payload.captured_at,
                )
                db.add(participant)
            participant.character_id = entry.character_id
            participant.nodes_owned = entry.nodes_owned
            participant.is_seller = entry.is_seller
            participant.last_seen_at = payload.captured_at
    record_audit_event(
        db,
        event_kind="hypernet_offer_snapshot",
        title=f"HyperNet progress updated: {offer.item_type.name if offer.item_type else offer.type_id}",
        body=f"{payload.nodes_sold}/{offer.total_nodes} sold · {payload.seller_owned_nodes} seeded",
        actor_user=user,
    )
    db.commit()
    return serialize_offer(owned_offer(db, offer.id, user), detail=True)


@router.post("/offers/{offer_id}/reconcile")
def reconcile_hypernet_offer(
    offer_id: int,
    payload: HyperNetReconcileRequest,
    user: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    offer = owned_offer(db, offer_id, user)
    if offer.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Offer is already reconciled")
    seeded_nodes = payload.seller_owned_nodes if payload.seller_owned_nodes is not None else offer.seller_owned_nodes
    if seeded_nodes > offer.total_nodes:
        raise HTTPException(status_code=400, detail="seller_owned_nodes cannot exceed total_nodes")
    offer.status = payload.status
    offer.reconciled_at = payload.reconciled_at
    offer.seller_owned_nodes = seeded_nodes
    if payload.unique_participants is not None:
        offer.unique_participants = payload.unique_participants
    offer.winner = payload.winner
    offer.actual_hypercore_cost = money(payload.actual_hypercore_cost) if payload.actual_hypercore_cost is not None else money(offer.hypercores_required * offer.hypercore_unit_cost)
    offer.final_market_value = money(payload.final_market_value) if payload.final_market_value is not None else None
    if payload.status == "completed":
        offer.completed_at = payload.reconciled_at
        offer.nodes_sold = offer.total_nodes
        offer.payout = money(payload.final_payout) if payload.final_payout is not None else offer.payout
        seeded_spend = money(offer.seller_owned_nodes * (offer.total_offer_price / offer.total_nodes))
        if payload.final_profit is not None:
            offer.final_profit = money(payload.final_profit)
        elif payload.winner == "external":
            offer.final_profit = money((offer.payout or 0) - offer.actual_hypercore_cost - seeded_spend - offer.acquisition_cost)
        else:
            offer.final_profit = money((offer.payout or 0) - offer.actual_hypercore_cost - seeded_spend + (offer.final_market_value or offer.acquisition_cost) - offer.acquisition_cost)
        offer.item_outcome = "transferred" if payload.winner == "external" else "retained"
    elif payload.status == "expired":
        offer.final_profit = money(payload.final_profit) if payload.final_profit is not None else money(-offer.actual_hypercore_cost)
        offer.item_outcome = "retained"
    else:
        offer.final_profit = money(payload.final_profit) if payload.final_profit is not None else None
        offer.item_outcome = "unresolved"
    if payload.note:
        offer.notes = "\n\n".join(value for value in [offer.notes, payload.note.strip()] if value)
    record_audit_event(
        db,
        event_kind="hypernet_offer_reconciled",
        title=f"HyperNet offer {payload.status}: {offer.item_type.name if offer.item_type else offer.type_id}",
        body=f"Winner: {payload.winner} · final result {offer.final_profit if offer.final_profit is not None else 'unresolved'} ISK",
        actor_user=user,
    )
    db.commit()
    return serialize_offer(owned_offer(db, offer.id, user), detail=True)
