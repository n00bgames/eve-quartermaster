from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.api.mining_ledger import require_mining, visible_characters
from app.db.session import get_db
from app.models import (
    EveCharacter,
    EveGroup,
    EveType,
    MiningLedgerEntry,
    MiningOperation,
    MiningSettlement,
    MiningSettlementDeduction,
    MiningSettlementLedgerEntry,
    MiningSettlementOutput,
    MiningSettlementParticipant,
    User,
)
from app.services.market import appraise_market, list_market_hubs
from app.services.mining_settlements import SettlementValidationError, calculate_settlement

router = APIRouter(prefix="/mining-ledger/settlements", tags=["mining-settlements"])


def as_float(value: Any) -> float:
    return float(value or 0)


def parse_datetime(value: Any, end_of_day: bool = False) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Settlement ranges must use valid ISO dates or timestamps.") from exc
        parsed = datetime.combine(parsed_date, time.max if end_of_day else time.min)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def settlement_query():
    return select(MiningSettlement).options(
        selectinload(MiningSettlement.operation),
        selectinload(MiningSettlement.refining_pilot),
        selectinload(MiningSettlement.created_by_user),
        selectinload(MiningSettlement.outputs),
        selectinload(MiningSettlement.participants).selectinload(MiningSettlementParticipant.character),
        selectinload(MiningSettlement.deductions),
        selectinload(MiningSettlement.ledger_links),
    )


def valid_minerals(db: Session) -> list[EveType]:
    return list(
        db.scalars(
            select(EveType)
            .join(EveGroup, EveType.group_id == EveGroup.group_id)
            .where(EveGroup.name == "Mineral", EveType.published.is_(True))
            .order_by(EveType.name)
        ).all()
    )


def json_decimal(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_decimal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_decimal(item) for item in value]
    if isinstance(value, set):
        return sorted(value)
    return value


def serialize_settlement(row: MiningSettlement) -> dict[str, Any]:
    participants = sorted(row.participants, key=lambda item: (-as_float(item.payout_isk), item.display_name.lower()))
    return {
        "id": row.id,
        "name": row.name,
        "operation_id": row.operation_id,
        "operation_name": row.operation.name if row.operation else row.source_filter_json.get("operation_name"),
        "source_type": row.source_type,
        "source_filter": row.source_filter_json,
        "range_start": row.range_start.isoformat() if row.range_start else None,
        "range_end": row.range_end.isoformat() if row.range_end else None,
        "status": row.status,
        "contribution_basis": row.contribution_basis,
        "settlement_mode": row.settlement_mode,
        "price_source": row.price_source,
        "reserve": {
            "method": row.reserve_method,
            "entered_value": as_float(row.reserve_entered_value),
            "normalized_percentage": as_float(row.reserve_normalized_percentage) if row.reserve_normalized_percentage is not None else None,
            "calculated_amount": as_float(row.reserve_value),
        },
        "refining_pilot_name": row.refining_pilot_name,
        "refining_pilot_character_id": row.refining_pilot.character_id if row.refining_pilot else None,
        "refining_location": row.refining_location,
        "stated_refine_percent": as_float(row.stated_refine_percent) if row.stated_refine_percent is not None else None,
        "gross_value": as_float(row.gross_value),
        "reserve_value": as_float(row.reserve_value),
        "deduction_total": as_float(row.deduction_total),
        "distributable_value": as_float(row.distributable_value),
        "fixed_payout_total": as_float(row.fixed_payout_total),
        "share_pool_value": as_float(row.share_pool_value),
        "participant_payout_total": as_float(row.participant_payout_total),
        "unallocated_remainder": as_float(row.unallocated_remainder),
        "warnings": row.warnings_json or [],
        "notes": row.notes,
        "created_by": row.created_by_user.display_name if row.created_by_user else "Unknown user",
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "finalized_at": row.finalized_at.isoformat() if row.finalized_at else None,
        "source_entry_count": len(row.ledger_links),
        "outputs": [
            {
                "id": output.id,
                "type_id": output.type_id,
                "type_name": output.type_name_snapshot,
                "quantity": output.quantity,
                "distributed_quantity": output.distributed_quantity,
                "retained_quantity": output.retained_quantity,
                "unit_price": as_float(output.unit_price),
                "total_value": as_float(output.total_value),
                "stated_refine_percent": as_float(output.stated_refine_percent) if output.stated_refine_percent is not None else None,
                "price_source": output.price_source,
                "price_overridden": output.price_overridden,
            }
            for output in sorted(row.outputs, key=lambda item: item.type_name_snapshot)
        ],
        "deductions": [
            {
                "id": deduction.id,
                "deduction_type": deduction.deduction_type,
                "description": deduction.description,
                "calculation_method": deduction.calculation_method,
                "entered_value": as_float(deduction.entered_value),
                "normalized_percentage": as_float(deduction.normalized_percentage) if deduction.normalized_percentage is not None else None,
                "calculated_amount": as_float(deduction.calculated_amount),
            }
            for deduction in row.deductions
        ],
        "participants": [
            {
                "id": participant.id,
                "character_id": participant.character.character_id if participant.character else None,
                "display_name": participant.display_name,
                "role": participant.role,
                "source": participant.source,
                "ore_types": participant.ore_types_snapshot or [],
                "contribution_quantity": as_float(participant.contribution_quantity),
                "contribution_volume": as_float(participant.contribution_volume),
                "contribution_value": as_float(participant.contribution_value),
                "contribution_basis_value": as_float(participant.contribution_basis_value),
                "contribution_percentage": as_float(participant.contribution_percentage),
                "compensation_method": participant.compensation_method,
                "fixed_percentage": as_float(participant.fixed_percentage) if participant.fixed_percentage is not None else None,
                "share_weight": as_float(participant.share_weight) if participant.share_weight is not None else None,
                "share_weight_overridden": participant.share_weight_overridden,
                "payout_ratio": as_float(participant.payout_ratio),
                "payout_isk": as_float(participant.payout_isk),
                "mineral_payouts": participant.mineral_payouts_json or [],
                "notes": participant.notes,
            }
            for participant in participants
        ],
    }


def source_selection(payload: dict[str, Any], current_user: User, db: Session) -> tuple[list[MiningLedgerEntry], dict[str, Any], str, datetime | None, datetime | None, int | None]:
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    source_type = str(source.get("type") or "operation")
    characters = [row for row in visible_characters(current_user, db) if not row.sync_opt_out]
    allowed_internal = {row.id for row in characters}
    allowed_external = {row.character_id: row.id for row in characters}
    selected_external = {int(value) for value in source.get("character_ids") or [] if int(value) in allowed_external}
    selected_internal = {allowed_external[value] for value in selected_external}
    query = (
        select(MiningLedgerEntry)
        .options(selectinload(MiningLedgerEntry.character))
        .where(MiningLedgerEntry.character_id.in_(allowed_internal))
    )
    operation_id: int | None = None
    range_start: datetime | None = None
    range_end: datetime | None = None
    snapshot: dict[str, Any]

    if source_type == "operation":
        operation_id = int(source.get("operation_id") or 0)
        operation = db.get(MiningOperation, operation_id)
        if operation is None:
            raise HTTPException(status_code=404, detail="Mining operation was not found.")
        query = query.where(MiningLedgerEntry.operation_id == operation_id)
        range_start, range_end = operation.start_at, operation.end_at
        snapshot = {"type": "operation", "operation_id": operation.id, "operation_name": operation.name}
    elif source_type == "range":
        range_start = parse_datetime(source.get("range_start"))
        range_end = parse_datetime(source.get("range_end"), end_of_day=True)
        if range_start is None or range_end is None or range_end < range_start:
            raise HTTPException(status_code=400, detail="Choose a valid settlement start and end range.")
        query = query.where(MiningLedgerEntry.mined_date >= range_start.date(), MiningLedgerEntry.mined_date <= range_end.date())
        snapshot = {"type": "range", "range_start": range_start.isoformat(), "range_end": range_end.isoformat()}
    else:
        raise HTTPException(status_code=400, detail="Settlement source must be a saved operation or date range.")

    if selected_internal:
        query = query.where(MiningLedgerEntry.character_id.in_(selected_internal))
        snapshot["character_ids"] = sorted(selected_external)
    rows = list(db.scalars(query.order_by(MiningLedgerEntry.id)).all())
    signature_payload = {**snapshot, "ledger_entry_ids": [row.id for row in rows]}
    signature = hashlib.sha256(json.dumps(signature_payload, sort_keys=True).encode("utf-8")).hexdigest()
    snapshot["ledger_entry_ids"] = [row.id for row in rows]
    return rows, snapshot, signature, range_start, range_end, operation_id


def calculation_rows(rows: list[MiningLedgerEntry]) -> list[dict[str, Any]]:
    return [
        {
            "ledger_entry_id": row.id,
            "character_id": row.character.character_id,
            "internal_character_id": row.character_id,
            "character_name": row.character.name,
            "ore_type_name": row.ore_type_name,
            "quantity": row.quantity,
            "volume": row.volume,
            "estimated_price": row.estimated_price,
        }
        for row in rows
    ]


def prepare_payload(payload: dict[str, Any], current_user: User, db: Session) -> tuple[dict[str, Any], list[MiningLedgerEntry], dict[str, Any], str, datetime | None, datetime | None, int | None]:
    rows, source_filter, signature, range_start, range_end, operation_id = source_selection(payload, current_user, db)
    mineral_map = {row.type_id: row for row in valid_minerals(db)}
    clean_outputs: list[dict[str, Any]] = []
    for raw in payload.get("outputs") if isinstance(payload.get("outputs"), list) else []:
        if not isinstance(raw, dict):
            continue
        type_id = int(raw.get("type_id") or 0)
        mineral = mineral_map.get(type_id)
        if mineral is None:
            raise HTTPException(status_code=400, detail="Every refined output must be a published SDE mineral.")
        clean_outputs.append({**raw, "type_id": mineral.type_id, "type_name": mineral.name})
    cleaned = {**payload, "outputs": clean_outputs}
    try:
        calculation = calculate_settlement(calculation_rows(rows), cleaned)
    except SettlementValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return calculation, rows, source_filter, signature, range_start, range_end, operation_id


def replace_snapshot(settlement: MiningSettlement, payload: dict[str, Any], calculation: dict[str, Any], rows: list[MiningLedgerEntry], source_filter: dict[str, Any], signature: str, range_start: datetime | None, range_end: datetime | None, operation_id: int | None, current_user: User, db: Session) -> None:
    settlement.name = str(payload.get("name") or "").strip()
    if not settlement.name:
        raise HTTPException(status_code=400, detail="Settlement name is required.")
    character_map = {row.character_id: row for row in visible_characters(current_user, db)}
    refiner_external_id = int(payload.get("refining_pilot_character_id") or 0)
    refiner = character_map.get(refiner_external_id) if refiner_external_id else None
    if refiner_external_id and refiner is None:
        raise HTTPException(status_code=400, detail="The linked refining pilot is not an available EQM character.")

    settlement.operation_id = operation_id
    settlement.source_type = source_filter["type"]
    settlement.source_signature = signature
    settlement.source_filter_json = source_filter
    settlement.range_start = range_start
    settlement.range_end = range_end
    settlement.contribution_basis = calculation["contribution_basis"]
    settlement.settlement_mode = calculation["settlement_mode"]
    settlement.price_source = calculation["price_source"]
    settlement.reserve_method = calculation["reserve_method"]
    settlement.reserve_entered_value = calculation["reserve_entered_value"]
    settlement.reserve_normalized_percentage = calculation["reserve_normalized_percentage"]
    settlement.refining_pilot_name = str(payload.get("refining_pilot_name") or "").strip() or None
    settlement.refining_pilot_character_id = refiner.id if refiner else None
    settlement.refining_location = str(payload.get("refining_location") or "").strip() or None
    settlement.stated_refine_percent = calculation["stated_refine_percent"]
    for field in ("gross_value", "reserve_value", "deduction_total", "distributable_value", "fixed_payout_total", "share_pool_value", "participant_payout_total", "unallocated_remainder"):
        setattr(settlement, field, calculation[field])
    settlement.warnings_json = calculation["warnings"]
    settlement.notes = str(payload.get("notes") or "").strip() or None

    settlement.outputs.clear()
    settlement.participants.clear()
    settlement.deductions.clear()
    settlement.ledger_links.clear()
    db.flush()

    for output in calculation["outputs"]:
        settlement.outputs.append(MiningSettlementOutput(
            type_id=output["type_id"], type_name_snapshot=output["type_name"], quantity=int(output["quantity"]),
            distributed_quantity=output["distributed_quantity"], retained_quantity=output["retained_quantity"],
            unit_price=output["unit_price"], total_value=output["total_value"], stated_refine_percent=output["stated_refine_percent"],
            price_source=output["price_source"], price_overridden=output["price_overridden"],
        ))
    for participant in calculation["participants"]:
        linked = character_map.get(int(participant["character_id"])) if participant.get("character_id") else None
        settlement.participants.append(MiningSettlementParticipant(
            character_id=linked.id if linked else None, display_name=participant["display_name"], role=participant["role"],
            source=participant["source"], ore_types_snapshot=participant["ore_types"],
            contribution_quantity=participant["quantity"], contribution_volume=participant["volume"],
            contribution_value=participant["estimated_value"], contribution_basis_value=participant["basis_value"],
            contribution_percentage=participant["contribution_percentage"], compensation_method=participant["compensation_method"],
            fixed_percentage=participant["fixed_percentage"], share_weight=participant["share_weight"],
            share_weight_overridden=participant["share_weight_overridden"], payout_ratio=participant["payout_ratio"],
            payout_isk=participant["payout_isk"], mineral_payouts_json=json_decimal(participant["mineral_payouts"]),
            notes=participant["notes"],
        ))
    for deduction in calculation["deductions"]:
        settlement.deductions.append(MiningSettlementDeduction(
            deduction_type=deduction["deduction_type"], description=deduction["description"],
            calculation_method=deduction["calculation_method"], entered_value=deduction["entered_value"],
            normalized_percentage=deduction["normalized_percentage"], calculated_amount=deduction["calculated_amount"],
        ))
    contribution_map = {row["character_id"]: row for row in calculation["participants"] if row["source"] == "ledger"}
    for ledger_row in rows:
        contribution = contribution_map.get(ledger_row.character.character_id, {})
        settlement.ledger_links.append(MiningSettlementLedgerEntry(
            ledger_entry_id=ledger_row.id, character_id=ledger_row.character_id,
            contribution_snapshot_json=json_decimal({
                "character_id": ledger_row.character.character_id,
                "character_name": ledger_row.character.name,
                "ore_type_id": ledger_row.ore_type_id,
                "ore_type_name": ledger_row.ore_type_name,
                "quantity": ledger_row.quantity,
                "volume": ledger_row.volume,
                "estimated_price": ledger_row.estimated_price,
                "participant_contribution_percentage": contribution.get("contribution_percentage", 0),
            }),
        ))


def editable_settlement(settlement_id: int, current_user: User, db: Session) -> MiningSettlement:
    settlement = db.scalar(settlement_query().where(MiningSettlement.id == settlement_id))
    if settlement is None:
        raise HTTPException(status_code=404, detail="Mining settlement was not found.")
    if settlement.created_by_user_id != current_user.id and current_user.role not in {"host", "admin"}:
        raise HTTPException(status_code=403, detail="Only the settlement owner or an admin can edit it.")
    if settlement.status != "draft":
        raise HTTPException(status_code=409, detail="Finalized mining settlements are immutable.")
    return settlement


@router.get("")
def list_settlements(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    settlements = list(db.scalars(settlement_query().order_by(MiningSettlement.created_at.desc(), MiningSettlement.id.desc()).limit(100)).unique().all())
    minerals = valid_minerals(db)
    return {
        "minerals": [{"type_id": row.type_id, "name": row.name} for row in minerals],
        "price_sources": [{"key": row["key"], "label": row["label"], "available": row["available"]} for row in list_market_hubs(db)],
        "settlements": [serialize_settlement(row) for row in settlements],
    }


@router.post("/preview")
def preview_settlement(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    calculation, _, source_filter, _, range_start, range_end, operation_id = prepare_payload(payload, current_user, db)
    return {
        **json_decimal(calculation),
        "operation_id": operation_id,
        "source_type": source_filter["type"],
        "source_filter": source_filter,
        "range_start": range_start.isoformat() if range_start else None,
        "range_end": range_end.isoformat() if range_end else None,
    }


@router.post("/appraise")
async def appraise_outputs(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    minerals = {row.type_id: row for row in valid_minerals(db)}
    lines: list[str] = []
    for raw in payload.get("outputs") if isinstance(payload.get("outputs"), list) else []:
        mineral = minerals.get(int(raw.get("type_id") or 0)) if isinstance(raw, dict) else None
        quantity = int(raw.get("quantity") or 0) if isinstance(raw, dict) else 0
        if mineral and quantity > 0:
            lines.append(f"{quantity} {mineral.name}")
    if not lines:
        raise HTTPException(status_code=400, detail="Add mineral quantities before pricing outputs.")
    hubs = payload.get("hubs")
    return await appraise_market(db, "\n".join(lines), [str(value) for value in hubs] if isinstance(hubs, list) else None)


@router.post("")
def create_draft(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    calculation, rows, source_filter, signature, range_start, range_end, operation_id = prepare_payload(payload, current_user, db)
    settlement = MiningSettlement(
        name="Pending settlement", source_type=source_filter["type"], source_signature=signature,
        source_filter_json=source_filter, status="draft", contribution_basis=calculation["contribution_basis"],
        created_by_user_id=current_user.id,
    )
    db.add(settlement)
    replace_snapshot(settlement, payload, calculation, rows, source_filter, signature, range_start, range_end, operation_id, current_user, db)
    db.commit()
    settlement = db.scalar(settlement_query().where(MiningSettlement.id == settlement.id))
    return serialize_settlement(settlement)


@router.put("/{settlement_id}")
def update_draft(settlement_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    settlement = editable_settlement(settlement_id, current_user, db)
    calculation, rows, source_filter, signature, range_start, range_end, operation_id = prepare_payload(payload, current_user, db)
    replace_snapshot(settlement, payload, calculation, rows, source_filter, signature, range_start, range_end, operation_id, current_user, db)
    db.commit()
    settlement = db.scalar(settlement_query().where(MiningSettlement.id == settlement.id))
    return serialize_settlement(settlement)


@router.post("/{settlement_id}/finalize")
def finalize_settlement(settlement_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    settlement = editable_settlement(settlement_id, current_user, db)
    duplicate = db.scalar(
        select(MiningSettlement.id).where(
            MiningSettlement.id != settlement.id,
            MiningSettlement.status == "finalized",
            MiningSettlement.source_signature == settlement.source_signature,
        ).limit(1)
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="This exact Mining Ledger scope already has a finalized settlement.")
    if abs(Decimal(str(settlement.unallocated_remainder or 0))) > Decimal("0.01"):
        raise HTTPException(status_code=409, detail="The settlement must reconcile before finalization.")
    settlement.status = "finalized"
    settlement.finalized_at = datetime.now(timezone.utc)
    db.commit()
    settlement = db.scalar(settlement_query().where(MiningSettlement.id == settlement.id))
    return serialize_settlement(settlement)


@router.delete("/{settlement_id}")
def delete_draft(settlement_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    settlement = editable_settlement(settlement_id, current_user, db)
    db.execute(delete(MiningSettlement).where(MiningSettlement.id == settlement.id))
    db.commit()
    return {"status": "deleted", "id": settlement_id}
