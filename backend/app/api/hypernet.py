from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import mean
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.core.config import get_settings
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
    HyperNetParticipation,
    Location,
    User,
)
from app.schemas.hypernet import (
    HyperNetCalculatorRequest,
    HyperNetOfferCreate,
    HyperNetOfferPatch,
    HyperNetReconcileRequest,
    HyperNetSnapshotCreate,
    HyperNetParticipationCreate,
    HyperNetParticipationPatch,
    HyperNetParticipationResolve,
)
from app.services.audit import record_audit_event
from app.services.hypernet import data_source, money, offer_financials, progress_metrics, seeded_node_scenario
from app.services.hypernet_economics_engine import (
    evaluate_offer_with_engine,
    evaluate_participation_with_engine,
    evaluate_reconciliation_with_engine,
)
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


def participation_options() -> tuple[Any, ...]:
    return (
        selectinload(HyperNetParticipation.character),
        selectinload(HyperNetParticipation.item_type).selectinload(EveType.group).selectinload(EveGroup.category),
        selectinload(HyperNetParticipation.location),
    )


def owned_participation(db: Session, participation_id: int, user: User) -> HyperNetParticipation:
    row = db.scalar(
        select(HyperNetParticipation)
        .options(*participation_options())
        .where(HyperNetParticipation.id == participation_id, HyperNetParticipation.user_id == user.id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="HyperNet bid not found")
    return row


def as_number(value: Decimal | int | float | None) -> float | None:
    return float(value) if value is not None else None


def financial_payload(values: dict[str, Decimal | None]) -> dict[str, float | None]:
    return {key: as_number(value) for key, value in values.items()}


def participation_calculations(
    *,
    total_nodes: int,
    nodes_purchased: int,
    node_price: Decimal,
    outcome: str,
    item_value_at_completion: Decimal | None,
) -> dict[str, Any]:
    spent = money(node_price * nodes_purchased)
    value = money(item_value_at_completion) if item_value_at_completion is not None else None
    if outcome == "won":
        profit_loss = money((value or Decimal("0")) - spent)
    elif outcome == "lost":
        value = None
        profit_loss = money(-spent)
    elif outcome == "cancelled":
        value = None
        profit_loss = money(0)
    else:
        value = None
        profit_loss = None
    return evaluate_participation_with_engine(
        python_result={
            "win_probability_percent": round(float(Decimal(nodes_purchased) / Decimal(total_nodes) * Decimal("100")), 4),
            "total_spent": spent,
            "item_value_at_completion": value,
            "profit_loss": profit_loss,
        },
        total_nodes=total_nodes,
        nodes_purchased=nodes_purchased,
        node_price=node_price,
        outcome=outcome,
        item_value_at_completion=value,
    )


def authoritative_offer_financials(
    *,
    total_offer_price: Decimal,
    total_nodes: int,
    seller_owned_nodes: int,
    hypercores_required: int,
    hypercore_unit_cost: Decimal,
    acquisition_cost: Decimal,
    desired_profit: Decimal,
    jita_sell: Decimal | None = None,
    local_sell: Decimal | None = None,
) -> dict[str, Decimal | None]:
    financials = offer_financials(
        total_offer_price=total_offer_price,
        total_nodes=total_nodes,
        hypercores_required=hypercores_required,
        hypercore_unit_cost=hypercore_unit_cost,
        acquisition_cost=acquisition_cost,
        desired_profit=desired_profit,
        jita_sell=jita_sell,
        local_sell=local_sell,
    )
    scenario = seeded_node_scenario(
        total_nodes=total_nodes,
        seller_owned_nodes=seller_owned_nodes,
        node_price=financials["node_price"] or 0,
        acquisition_cost=acquisition_cost,
        hypercore_cost=financials["hypercore_cost"] or 0,
        payout_after_fee=financials["payout_after_fee"] or 0,
        current_jita_sell=jita_sell,
    )
    evaluated = evaluate_offer_with_engine(
        python_result={
            "financials": financials,
            "seeded_scenario": scenario,
            "progress": {
                "first_organic_node_at": None,
                "hours_to_first_organic_node": None,
                "organic_nodes_per_hour": None,
                "estimated_hours_to_completion": None,
            },
        },
        total_offer_price=total_offer_price,
        total_nodes=total_nodes,
        seller_owned_nodes=seller_owned_nodes,
        hypercores_required=hypercores_required,
        hypercore_unit_cost=hypercore_unit_cost,
        acquisition_cost=acquisition_cost,
        desired_profit=desired_profit,
        jita_sell=jita_sell,
        local_sell=local_sell,
    )
    return evaluated["financials"]


def serialize_participation(row: HyperNetParticipation) -> dict[str, Any]:
    probability = Decimal(row.nodes_purchased) / Decimal(row.total_nodes) * Decimal("100")
    return {
        "id": row.id,
        "character": {"id": row.character_id, "name": row.character.name if row.character else f"Character {row.character_id}"},
        "item": {
            "type_id": row.item_type_id,
            "name": row.item_type.name if row.item_type else f"Type {row.item_type_id}",
            "group": row.item_type.group.name if row.item_type and row.item_type.group else None,
        },
        "seller_name": row.seller_name,
        "location": {
            "id": row.location_id,
            "name": row.location.name if row.location else (row.location_name_snapshot or "Unspecified"),
        },
        "external_offer_reference": row.external_offer_reference,
        "total_nodes": row.total_nodes,
        "nodes_purchased": row.nodes_purchased,
        "win_probability_percent": round(float(probability), 4),
        "node_price": as_number(row.node_price),
        "total_spent": as_number(row.total_spent),
        "outcome": row.outcome,
        "won": row.won,
        "item_value_at_completion": as_number(row.item_value_at_completion),
        "profit_loss": as_number(row.profit_loss),
        "created_at": row.created_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "notes": row.notes,
    }


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
    evaluated = evaluate_offer_with_engine(
        python_result={
            "financials": financials,
            "seeded_scenario": scenario,
            "progress": progress_metrics(
                created_at=offer.created_offer_at,
                total_nodes=offer.total_nodes,
                snapshots=offer.snapshots,
            ),
        },
        total_offer_price=offer.total_offer_price,
        total_nodes=offer.total_nodes,
        seller_owned_nodes=offer.seller_owned_nodes,
        hypercores_required=offer.hypercores_required,
        hypercore_unit_cost=offer.hypercore_unit_cost,
        acquisition_cost=offer.acquisition_cost,
        desired_profit=offer.desired_profit,
        jita_sell=jita_sell,
        local_sell=local_sell,
        created_at=offer.created_offer_at,
        snapshots=offer.snapshots,
    )
    return {
        "financials": financial_payload(evaluated["financials"]),
        "seeded_scenario": {
            key: value if isinstance(value, bool) or value is None else as_number(value)
            for key, value in evaluated["seeded_scenario"].items()
        },
        "progress": evaluated["progress"],
        **{key: value for key, value in evaluated.items() if key.startswith("engine_")},
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
        "economics_engine": get_settings().eqm_hypernet_engine,
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
    calculator_values = payload.model_dump(exclude={"seller_owned_nodes"})
    for field in ("total_offer_price", "hypercore_unit_cost", "acquisition_cost", "desired_profit", "jita_sell", "local_sell"):
        if calculator_values.get(field) is not None:
            calculator_values[field] = money(calculator_values[field])
    financials = offer_financials(**calculator_values)
    scenario = seeded_node_scenario(
        total_nodes=payload.total_nodes,
        seller_owned_nodes=payload.seller_owned_nodes,
        node_price=financials["node_price"] or 0,
        acquisition_cost=payload.acquisition_cost,
        hypercore_cost=financials["hypercore_cost"] or 0,
        payout_after_fee=financials["payout_after_fee"] or 0,
        current_jita_sell=calculator_values["jita_sell"],
    )
    evaluated = evaluate_offer_with_engine(
        python_result={"financials": financials, "seeded_scenario": scenario, "progress": {
            "first_organic_node_at": None,
            "hours_to_first_organic_node": None,
            "organic_nodes_per_hour": None,
            "estimated_hours_to_completion": None,
        }},
        total_offer_price=calculator_values["total_offer_price"],
        total_nodes=payload.total_nodes,
        seller_owned_nodes=payload.seller_owned_nodes,
        hypercores_required=payload.hypercores_required,
        hypercore_unit_cost=calculator_values["hypercore_unit_cost"],
        acquisition_cost=calculator_values["acquisition_cost"],
        desired_profit=calculator_values["desired_profit"],
        jita_sell=calculator_values["jita_sell"],
        local_sell=calculator_values["local_sell"],
    )
    return {
        "financials": financial_payload(evaluated["financials"]),
        "seeded_scenario": {
            key: value if isinstance(value, bool) or value is None else as_number(value)
            for key, value in evaluated["seeded_scenario"].items()
        },
        **{key: value for key, value in evaluated.items() if key.startswith("engine_")},
    }


@router.get("/summary")
def hypernet_summary(user: User = Depends(require_hypernet), db: Session = Depends(get_db)) -> dict[str, Any]:
    offers = db.scalars(
        select(HyperNetOffer)
        .options(*offer_options())
        .where(HyperNetOffer.owner_user_id == user.id)
        .order_by(HyperNetOffer.created_offer_at.desc())
    ).unique().all()
    participations = db.scalars(
        select(HyperNetParticipation)
        .where(HyperNetParticipation.user_id == user.id)
        .order_by(HyperNetParticipation.created_at.desc())
    ).all()
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
    pending_bids = [row for row in participations if row.outcome == "pending"]
    resolved_bids = [row for row in participations if row.outcome in {"won", "lost"}]
    won_bids = [row for row in resolved_bids if row.outcome == "won"]
    lost_bids = [row for row in resolved_bids if row.outcome == "lost"]
    bid_spend = sum((row.total_spent for row in resolved_bids), Decimal("0"))
    bid_result = sum((row.profit_loss or Decimal("0") for row in resolved_bids), Decimal("0"))
    expected_wins = sum((Decimal(row.nodes_purchased) / Decimal(row.total_nodes) for row in resolved_bids), Decimal("0"))
    item_value_won = sum((row.item_value_at_completion or Decimal("0") for row in won_bids), Decimal("0"))
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
        "participation": {
            "active_bids": len(pending_bids),
            "active_nodes": sum(row.nodes_purchased for row in pending_bids),
            "active_spend": as_number(sum((row.total_spent for row in pending_bids), Decimal("0"))),
            "resolved_bids": len(resolved_bids),
            "won_bids": len(won_bids),
            "lost_bids": len(lost_bids),
            "win_rate_percent": round(len(won_bids) / len(resolved_bids) * 100, 2) if resolved_bids else None,
            "expected_wins": round(float(expected_wins), 4),
            "luck_delta_wins": round(float(Decimal(len(won_bids)) - expected_wins), 4),
            "total_spent": as_number(bid_spend),
            "item_value_won": as_number(item_value_won),
            "realized_profit_loss": as_number(bid_result),
            "return_on_spend_percent": round(float(bid_result / bid_spend * 100), 2) if bid_spend else None,
        },
        "combined_lifetime_result": as_number(lifetime_profit + bid_result),
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


@router.get("/participations")
def list_hypernet_participations(
    outcome: str = "all",
    limit: int = Query(500, ge=1, le=1000),
    user: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = (
        select(HyperNetParticipation)
        .options(*participation_options())
        .where(HyperNetParticipation.user_id == user.id)
    )
    if outcome != "all":
        if outcome not in {"pending", "won", "lost", "cancelled"}:
            raise HTTPException(status_code=400, detail="Unsupported bid outcome filter")
        query = query.where(HyperNetParticipation.outcome == outcome)
    rows = db.scalars(query.order_by(HyperNetParticipation.created_at.desc()).limit(limit)).unique().all()
    return [serialize_participation(row) for row in rows]


@router.post("/participations")
def create_hypernet_participation(
    payload: HyperNetParticipationCreate,
    user: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    character = validate_character(db, payload.character_id, user)
    item_type = db.get(EveType, payload.item_type_id)
    if item_type is None:
        raise HTTPException(status_code=400, detail="Item type was not found in the imported SDE")
    location = db.get(Location, payload.location_id) if payload.location_id else None
    if payload.location_id and location is None:
        raise HTTPException(status_code=400, detail="Location was not found")
    economics = participation_calculations(
        total_nodes=payload.total_nodes,
        nodes_purchased=payload.nodes_purchased,
        node_price=money(payload.node_price),
        outcome="pending",
        item_value_at_completion=None,
    )
    row = HyperNetParticipation(
        user_id=user.id,
        character_id=character.id,
        external_offer_reference=(payload.external_offer_reference or "").strip() or None,
        item_type_id=item_type.type_id,
        seller_name=payload.seller_name,
        location_id=location.id if location else None,
        location_name_snapshot=location.name if location else (payload.location_name or "").strip() or None,
        total_nodes=payload.total_nodes,
        nodes_purchased=payload.nodes_purchased,
        node_price=money(payload.node_price),
        total_spent=economics["total_spent"],
        outcome="pending",
        created_at=payload.created_at,
        notes=payload.notes,
    )
    db.add(row)
    record_audit_event(
        db,
        event_kind="hypernet_bid_created",
        title=f"HyperNet bid recorded: {item_type.name}",
        body=f"{payload.nodes_purchased}/{payload.total_nodes} nodes · {row.total_spent} ISK",
        actor_user=user,
    )
    db.commit()
    return serialize_participation(owned_participation(db, row.id, user))


@router.patch("/participations/{participation_id}")
def patch_hypernet_participation(
    participation_id: int,
    payload: HyperNetParticipationPatch,
    user: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = owned_participation(db, participation_id, user)
    changes = payload.model_dump(exclude_unset=True)

    if "character_id" in changes:
        row.character_id = validate_character(db, changes["character_id"], user).id
    if "item_type_id" in changes:
        item_type = db.get(EveType, changes["item_type_id"])
        if item_type is None:
            raise HTTPException(status_code=400, detail="Item type was not found in the imported SDE")
        row.item_type_id = item_type.type_id
    if "location_id" in changes or "location_name" in changes:
        location_id = changes.get("location_id")
        location = db.get(Location, location_id) if location_id else None
        if location_id and location is None:
            raise HTTPException(status_code=400, detail="Location was not found")
        row.location_id = location.id if location else None
        row.location_name_snapshot = location.name if location else (changes.get("location_name") or "").strip() or None

    for field in ("external_offer_reference", "seller_name", "total_nodes", "nodes_purchased", "created_at", "outcome", "completed_at", "notes"):
        if field in changes:
            value = changes[field]
            if field in {"external_offer_reference", "notes"} and isinstance(value, str):
                value = value.strip() or None
            setattr(row, field, value)
    if "node_price" in changes:
        row.node_price = money(changes["node_price"])
    if "item_value_at_completion" in changes:
        row.item_value_at_completion = money(changes["item_value_at_completion"]) if changes["item_value_at_completion"] is not None else None

    if row.nodes_purchased > row.total_nodes:
        raise HTTPException(status_code=400, detail="nodes_purchased cannot exceed total_nodes")
    if row.outcome == "pending":
        row.completed_at = None
        row.won = None
        row.item_value_at_completion = None
        row.profit_loss = None
    else:
        if row.completed_at is None:
            raise HTTPException(status_code=400, detail="Resolved bids require a completion time")
        if row.completed_at < row.created_at:
            raise HTTPException(status_code=400, detail="Completion time cannot precede the bid")
        if row.outcome == "won" and row.item_value_at_completion is None:
            raise HTTPException(status_code=400, detail="Won bids require the item value at completion")
        row.won = True if row.outcome == "won" else False if row.outcome == "lost" else None

    economics = participation_calculations(
        total_nodes=row.total_nodes,
        nodes_purchased=row.nodes_purchased,
        node_price=row.node_price,
        outcome=row.outcome,
        item_value_at_completion=row.item_value_at_completion,
    )
    row.total_spent = economics["total_spent"]
    row.item_value_at_completion = economics["item_value_at_completion"]
    row.profit_loss = economics["profit_loss"]

    record_audit_event(db, event_kind="hypernet_bid_edited", title=f"HyperNet bid edited: {row.item_type.name if row.item_type else row.item_type_id}", body=f"{row.nodes_purchased}/{row.total_nodes} nodes · {row.outcome} · result {row.profit_loss} ISK", actor_user=user)
    db.commit()
    return serialize_participation(owned_participation(db, row.id, user))


@router.post("/participations/{participation_id}/resolve")
def resolve_hypernet_participation(
    participation_id: int,
    payload: HyperNetParticipationResolve,
    user: User = Depends(require_hypernet),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = owned_participation(db, participation_id, user)
    if row.outcome != "pending":
        raise HTTPException(status_code=409, detail="HyperNet bid is already resolved")
    if payload.completed_at < row.created_at:
        raise HTTPException(status_code=400, detail="Completion time cannot precede the bid")
    row.outcome = payload.outcome
    row.completed_at = payload.completed_at
    row.won = True if payload.outcome == "won" else False if payload.outcome == "lost" else None
    economics = participation_calculations(
        total_nodes=row.total_nodes,
        nodes_purchased=row.nodes_purchased,
        node_price=row.node_price,
        outcome=payload.outcome,
        item_value_at_completion=money(payload.item_value_at_completion) if payload.item_value_at_completion is not None else None,
    )
    row.total_spent = economics["total_spent"]
    row.item_value_at_completion = economics["item_value_at_completion"]
    row.profit_loss = economics["profit_loss"]
    if payload.notes:
        row.notes = "\n\n".join(value for value in [row.notes, payload.notes.strip()] if value)
    record_audit_event(
        db,
        event_kind="hypernet_bid_resolved",
        title=f"HyperNet bid {payload.outcome}: {row.item_type.name if row.item_type else row.item_type_id}",
        body=f"Result: {row.profit_loss} ISK",
        actor_user=user,
    )
    db.commit()
    return serialize_participation(owned_participation(db, row.id, user))


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
    calculations = authoritative_offer_financials(
        total_offer_price=money(payload.total_offer_price),
        total_nodes=payload.total_nodes,
        seller_owned_nodes=payload.seller_owned_nodes,
        hypercores_required=payload.hypercores_required,
        hypercore_unit_cost=money(payload.hypercore_unit_cost),
        acquisition_cost=money(payload.acquisition_cost),
        desired_profit=money(payload.desired_profit),
        jita_sell=money(payload.jita_sell) if payload.jita_sell is not None else None,
        local_sell=money(payload.local_sell) if payload.local_sell is not None else None,
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
    calculations = authoritative_offer_financials(
        total_offer_price=offer.total_offer_price,
        total_nodes=offer.total_nodes,
        seller_owned_nodes=offer.seller_owned_nodes,
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
    actual_hypercore_cost = money(payload.actual_hypercore_cost) if payload.actual_hypercore_cost is not None else money(offer.hypercores_required * offer.hypercore_unit_cost)
    offer.final_market_value = money(payload.final_market_value) if payload.final_market_value is not None else None
    if payload.status == "completed":
        offer.completed_at = payload.reconciled_at
        offer.nodes_sold = offer.total_nodes
        offer.payout = money(payload.final_payout) if payload.final_payout is not None else offer.payout
        seeded_spend = money(offer.seller_owned_nodes * (offer.total_offer_price / offer.total_nodes))
        if payload.final_profit is not None:
            final_profit = money(payload.final_profit)
        elif payload.winner == "external":
            final_profit = money((offer.payout or 0) - actual_hypercore_cost - seeded_spend - offer.acquisition_cost)
        else:
            final_profit = money((offer.payout or 0) - actual_hypercore_cost - seeded_spend + (offer.final_market_value or offer.acquisition_cost) - offer.acquisition_cost)
        item_outcome = "transferred" if payload.winner == "external" else "retained"
    elif payload.status == "expired":
        seeded_spend = money(offer.seller_owned_nodes * (offer.total_offer_price / offer.total_nodes))
        final_profit = money(payload.final_profit) if payload.final_profit is not None else money(-actual_hypercore_cost)
        item_outcome = "retained"
    else:
        seeded_spend = money(offer.seller_owned_nodes * (offer.total_offer_price / offer.total_nodes))
        final_profit = money(payload.final_profit) if payload.final_profit is not None else None
        item_outcome = "unresolved"
    economics = evaluate_reconciliation_with_engine(
        python_result={
            "actual_hypercore_cost": actual_hypercore_cost,
            "seeded_spend": seeded_spend,
            "final_profit": final_profit,
            "item_outcome": item_outcome,
        },
        status=payload.status,
        winner=payload.winner,
        total_offer_price=offer.total_offer_price,
        total_nodes=offer.total_nodes,
        seller_owned_nodes=offer.seller_owned_nodes,
        hypercores_required=offer.hypercores_required,
        hypercore_unit_cost=offer.hypercore_unit_cost,
        acquisition_cost=offer.acquisition_cost,
        actual_hypercore_cost=actual_hypercore_cost,
        payout=offer.payout,
        final_market_value=offer.final_market_value,
        final_profit=money(payload.final_profit) if payload.final_profit is not None else None,
    )
    offer.actual_hypercore_cost = economics["actual_hypercore_cost"]
    offer.final_profit = economics["final_profit"]
    offer.item_outcome = economics["item_outcome"]
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
