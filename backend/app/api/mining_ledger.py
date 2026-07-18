from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import can_view_all_characters, get_current_user
from app.db.session import get_db
from app.models import EsiToken, EveCharacter, EveSystem, MiningLedgerEntry, MiningOperation, MiningOperationParticipant, User
from app.services.mining_ledger import import_detailed_ledger
from app.services.permissions import can_view_section

router = APIRouter(prefix="/mining-ledger", tags=["mining-ledger"])
MINING_SCOPE = "esi-industry.read_character_mining.v1"


def require_mining(current_user: User, db: Session) -> None:
    if not can_view_section(current_user, "mining", db):
        raise HTTPException(status_code=403, detail="mining ledger access is required")


def visible_characters(current_user: User, db: Session) -> list[EveCharacter]:
    query = (
        select(EveCharacter)
        .where(
            exists().where(
                EsiToken.character_id == EveCharacter.id,
                EsiToken.revoked_at.is_(None),
            )
        )
        .order_by(EveCharacter.name)
    )
    if not can_view_all_characters(current_user, db):
        query = query.where(EveCharacter.owner_user_id == current_user.id)
    return list(db.scalars(query).all())


def resolve_character(db: Session, current_user: User, eve_character_id: int) -> EveCharacter:
    character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == eve_character_id))
    if character is None:
        raise HTTPException(status_code=404, detail="Character was not found.")
    if not can_view_all_characters(current_user, db) and character.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot manage this character's mining ledger.")
    if character.sync_opt_out:
        raise HTTPException(status_code=403, detail=f"{character.name} has opted out of shared sync.")
    active_token_id = db.scalar(
        select(EsiToken.id)
        .where(EsiToken.character_id == character.id, EsiToken.revoked_at.is_(None))
        .limit(1)
    )
    if active_token_id is None:
        raise HTTPException(status_code=403, detail=f"{character.name} does not have an active ESI connection.")
    return character


def as_float(value: Any) -> float:
    return float(value or 0)


def efficiency(collected: float, residue: float) -> float | None:
    gross = collected + residue
    return round(collected / gross * 100, 2) if gross > 0 else None


def rollup(entries: list[MiningLedgerEntry]) -> dict[str, Any]:
    totals = {"quantity": 0, "residue_quantity": 0, "volume": 0.0, "residue_volume": 0.0, "estimated_price": 0.0, "estimated_residue_price": 0.0}
    measured_volume = measured_residue = 0.0
    dimensions: dict[str, dict[Any, dict[str, Any]]] = {key: {} for key in ("day", "ore", "character", "system")}
    for row in entries:
        values = {
            "quantity": int(row.quantity), "residue_quantity": int(row.residue_quantity),
            "volume": as_float(row.volume), "residue_volume": as_float(row.residue_volume),
            "estimated_price": as_float(row.estimated_price), "estimated_residue_price": as_float(row.estimated_residue_price),
        }
        for key, value in values.items():
            totals[key] += value
        if row.has_residue_data:
            measured_volume += values["volume"]
            measured_residue += values["residue_volume"]
        dimension_keys = {
            "day": (row.mined_date.isoformat(), row.mined_date.isoformat()),
            "ore": (row.ore_type_id, row.ore_type_name),
            "character": (row.character_id, row.character.name),
            "system": (row.solar_system_id, row.solar_system_name),
        }
        for dimension, (key, name) in dimension_keys.items():
            bucket = dimensions[dimension].setdefault(key, {"id": key, "name": name, **{field: 0 for field in values}, "measured_volume": 0.0, "measured_residue_volume": 0.0})
            for field, value in values.items():
                bucket[field] += value
            if row.has_residue_data:
                bucket["measured_volume"] += values["volume"]
                bucket["measured_residue_volume"] += values["residue_volume"]

    def finish(bucket: dict[str, Any]) -> dict[str, Any]:
        result = dict(bucket)
        result["gross_volume"] = result["volume"] + result["residue_volume"]
        result["gross_value"] = result["estimated_price"] + result["estimated_residue_price"]
        result["efficiency"] = efficiency(result.pop("measured_volume"), result.pop("measured_residue_volume"))
        return result

    totals["gross_quantity"] = totals["quantity"] + totals["residue_quantity"]
    totals["gross_volume"] = totals["volume"] + totals["residue_volume"]
    totals["gross_value"] = totals["estimated_price"] + totals["estimated_residue_price"]
    totals["efficiency"] = efficiency(measured_volume, measured_residue)
    totals["measured_volume"] = measured_volume + measured_residue
    return {
        "totals": totals,
        "by_day": sorted((finish(row) for row in dimensions["day"].values()), key=lambda row: row["name"]),
        "by_ore": sorted((finish(row) for row in dimensions["ore"].values()), key=lambda row: -row["volume"]),
        "by_character": sorted((finish(row) for row in dimensions["character"].values()), key=lambda row: -row["volume"]),
        "by_system": sorted((finish(row) for row in dimensions["system"].values()), key=lambda row: -row["volume"]),
    }


def serialize_entry(row: MiningLedgerEntry) -> dict[str, Any]:
    return {
        "id": row.id, "date": row.mined_date.isoformat(), "timestamp": row.mined_at.isoformat() if row.mined_at else None,
        "character_id": row.character.character_id, "character_name": row.character.name,
        "ore_type_id": row.ore_type_id, "ore_type": row.ore_type_name,
        "solar_system_id": row.solar_system_id, "solar_system": row.solar_system_name,
        "quantity": row.quantity, "residue_quantity": row.residue_quantity,
        "volume": as_float(row.volume), "residue_volume": as_float(row.residue_volume),
        "estimated_price": as_float(row.estimated_price), "estimated_residue_price": as_float(row.estimated_residue_price),
        "has_residue_data": row.has_residue_data, "source": row.source,
        "operation_id": row.operation_id, "operation_name": row.operation.name if row.operation else None,
    }


def serialize_operation(operation: MiningOperation) -> dict[str, Any]:
    summary = rollup(list(operation.entries))["totals"]
    return {
        "id": operation.id, "name": operation.name,
        "solar_system_id": operation.solar_system_id, "solar_system_name": operation.solar_system_name or (operation.system.name if operation.system else None),
        "start_at": operation.start_at.isoformat(), "end_at": operation.end_at.isoformat(), "notes": operation.notes,
        "created_by": operation.created_by_user.display_name,
        "participants": [{"character_id": row.character.character_id, "character_name": row.character.name, "role": row.role, "ship_name": row.ship_name, "crystal_name": row.crystal_name} for row in operation.participants],
        "summary": summary,
    }


@router.get("")
def mining_ledger(
    character_id: int | None = Query(None), system_id: int | None = Query(None), operation_id: int | None = Query(None),
    date_from: date | None = Query(None), date_to: date | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=25, le=500),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_mining(current_user, db)
    characters = visible_characters(current_user, db)
    internal_ids = {row.id for row in characters if not row.sync_opt_out}
    query = select(MiningLedgerEntry).options(selectinload(MiningLedgerEntry.character), selectinload(MiningLedgerEntry.operation)).where(MiningLedgerEntry.character_id.in_(internal_ids))
    if character_id:
        selected = next((row for row in characters if row.character_id == character_id), None)
        query = query.where(MiningLedgerEntry.character_id == (selected.id if selected else -1))
    if system_id:
        query = query.where(MiningLedgerEntry.solar_system_id == system_id)
    if operation_id:
        query = query.where(MiningLedgerEntry.operation_id == operation_id)
    if date_from:
        query = query.where(MiningLedgerEntry.mined_date >= date_from)
    if date_to:
        query = query.where(MiningLedgerEntry.mined_date <= date_to)
    entries = list(db.scalars(query.order_by(MiningLedgerEntry.mined_date.desc(), MiningLedgerEntry.character_id, MiningLedgerEntry.ore_type_name)).all())

    token_map: dict[int, EsiToken] = {}
    for token in db.scalars(select(EsiToken).where(EsiToken.revoked_at.is_(None)).order_by(EsiToken.created_at.desc())).all():
        token_map.setdefault(token.character_id, token)
    operations = list(db.scalars(select(MiningOperation).options(selectinload(MiningOperation.system), selectinload(MiningOperation.created_by_user), selectinload(MiningOperation.participants).selectinload(MiningOperationParticipant.character), selectinload(MiningOperation.entries).selectinload(MiningLedgerEntry.character)).order_by(MiningOperation.start_at.desc())).unique().all())
    return {
        "characters": [{"character_id": row.character_id, "name": row.name, "portrait_url": row.portrait_url, "can_sync": bool(token_map.get(row.id) and MINING_SCOPE in set(token_map[row.id].scopes.split())), "sync_opt_out": row.sync_opt_out} for row in characters],
        "systems": [(row.system_id, row.name) for row in db.scalars(select(EveSystem).order_by(EveSystem.name)).all()],
        "analytics": rollup(entries), "entry_count": len(entries), "page": page, "page_size": page_size,
        "entries": [serialize_entry(row) for row in entries[(page - 1) * page_size:page * page_size]],
        "operations": [serialize_operation(row) for row in operations],
    }


@router.post("/import")
def import_ledger(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    character = resolve_character(db, current_user, int(payload.get("character_id") or 0))
    operation_id = int(payload["operation_id"]) if payload.get("operation_id") else None
    if operation_id:
        operation = db.get(MiningOperation, operation_id)
        if operation is None or character.id not in {row.character_id for row in operation.participants}:
            raise HTTPException(status_code=400, detail="The selected character is not a participant in that operation.")
    return import_detailed_ledger(db, character, str(payload.get("text") or ""), operation_id)


@router.delete("/characters/{character_id}")
def clear_character_ledger(character_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    character = resolve_character(db, current_user, character_id)
    result = db.execute(delete(MiningLedgerEntry).where(MiningLedgerEntry.character_id == character.id))
    db.commit()
    return {"status": "cleared", "character_id": character.character_id, "character_name": character.name, "deleted_count": result.rowcount or 0}

@router.post("/operations")
def create_operation(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Operation name is required.")
    try:
        start_at = datetime.fromisoformat(str(payload.get("start_at") or "").replace("Z", "+00:00"))
        end_at = datetime.fromisoformat(str(payload.get("end_at") or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Valid operation start and end times are required.") from exc
    if start_at.tzinfo is None: start_at = start_at.replace(tzinfo=timezone.utc)
    if end_at.tzinfo is None: end_at = end_at.replace(tzinfo=timezone.utc)
    if end_at <= start_at:
        raise HTTPException(status_code=400, detail="Operation end time must be after its start time.")
    system_id = int(payload["solar_system_id"]) if payload.get("solar_system_id") else None
    system = db.get(EveSystem, system_id) if system_id else db.scalar(select(EveSystem).where(EveSystem.name.ilike(str(payload.get("solar_system_name") or "").strip())))
    if system is None:
        raise HTTPException(status_code=400, detail="Choose a solar system from the imported SDE.")
    operation = MiningOperation(name=name, solar_system_id=system.system_id, solar_system_name=system.name, start_at=start_at, end_at=end_at, notes=str(payload.get("notes") or "").strip() or None, created_by_user_id=current_user.id)
    db.add(operation)
    db.flush()
    allowed = {row.character_id: row for row in visible_characters(current_user, db)}
    participant_ids: set[int] = set()
    for participant in payload.get("participants") or []:
        character = allowed.get(int(participant.get("character_id") or 0))
        if character and not character.sync_opt_out:
            db.add(MiningOperationParticipant(operation_id=operation.id, character_id=character.id, role="booster" if participant.get("role") == "booster" else "miner", ship_name=str(participant.get("ship_name") or "").strip() or None, crystal_name=str(participant.get("crystal_name") or "").strip() or None))
            participant_ids.add(character.id)
    db.flush()
    if not participant_ids:
        raise HTTPException(status_code=400, detail="Select at least one operation participant.")
    day_start, day_end = start_at.date(), end_at.date()
    for entry in db.scalars(select(MiningLedgerEntry).where(MiningLedgerEntry.character_id.in_(participant_ids), MiningLedgerEntry.solar_system_id == system.system_id, MiningLedgerEntry.mined_date >= day_start, MiningLedgerEntry.mined_date <= day_end, MiningLedgerEntry.operation_id.is_(None))).all():
        entry.operation_id = operation.id
    db.commit()
    return {"status": "created", "operation_id": operation.id, "name": operation.name}


@router.delete("/operations/{operation_id}")
def remove_operation(operation_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_mining(current_user, db)
    operation = db.get(MiningOperation, operation_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="Mining operation was not found.")
    if operation.created_by_user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the operation owner or an admin can delete it.")
    db.execute(delete(MiningOperation).where(MiningOperation.id == operation_id))
    db.commit()
    return {"status": "deleted", "operation_id": operation_id}
