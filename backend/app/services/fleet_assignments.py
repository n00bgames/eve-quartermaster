"""EQM persistence/identity adapter for the portable Fleet Assignments rules."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import json
import httpx
from fastapi import HTTPException
from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session, selectinload
from app.domain.fleet_assignments import MAX_PILOTS, Principal, SCHEMA_VERSION, parse_roster
from app.models import CharacterFitting, CharacterFittingItem, Doctrine, DoctrineFitting, EsiToken, EveCharacter, User
from app.models.fleet_assignments import FleetAssignmentOperation as Operation, FleetAssignmentPilot as Pilot
from app.services.audit import record_audit_event
from app.services.permissions import can_view_at_least, can_view_section


def require_access(user: User, db: Session) -> None:
    if user.deleted_at or user.role == "applicant" or not can_view_section(user, "fleet_assignments", db):
        raise HTTPException(403, "Fleet Assignments permission is required")


def is_manager(user: User, db: Session) -> bool:
    return can_view_at_least(user, "officer", db)


def require_manager(user: User, db: Session) -> None:
    require_access(user, db)
    if not is_manager(user, db):
        raise HTTPException(403, "Officer role is required to plan fleet assignments")


def principal_for(user: User, db: Session) -> Principal:
    # Match both current ownership and the active token's owning account. No
    # staff override, supplied user ID, display name, or browser-side filtering.
    ids = db.scalars(select(EveCharacter.character_id).where(
        EveCharacter.owner_user_id == user.id,
        exists().where(EsiToken.character_id == EveCharacter.id,
                       EsiToken.user_id == user.id, EsiToken.revoked_at.is_(None)),
    )).all()
    return Principal(str(user.id), frozenset(ids), is_manager(user, db))


def get_operation(db: Session, operation_id: int) -> Operation:
    operation = db.get(Operation, operation_id)
    if operation is None:
        raise HTTPException(404, "Fleet operation not found")
    return operation


def pilots_for(db: Session, operation_id: int) -> list[Pilot]:
    return list(db.scalars(select(Pilot).where(Pilot.operation_id == operation_id).order_by(Pilot.name)).all())


def claim_revision(db: Session, operation: Operation, revision: int) -> None:
    # Atomic compare-and-swap also works on SQLite; PostgreSQL holds the row
    # lock through the transaction. Every mutation claims before changing data.
    result = db.execute(update(Operation).where(Operation.id == operation.id, Operation.revision == revision)
                        .values(revision=revision + 1, updated_at=datetime.now(timezone.utc))
                        .execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This fleet changed in another session. Reload before trying again.")
    db.refresh(operation)


def require_editable(operation: Operation) -> None:
    if operation.status == "archived":
        raise HTTPException(409, "Restore this archived fleet to draft before editing")


def audit(db: Session, user: User, operation: Operation, action: str, details: dict | None = None) -> None:
    record_audit_event(db, event_kind="fleet_assignments", title=f"Fleet {action}: {operation.name}"[:255],
                       actor_user=user, body=json.dumps({"operation_id": operation.id, "revision": operation.revision,
                                                       "action": action, **(details or {})}))


def pilot_payload(pilot: Pilot) -> dict:
    return {"id": pilot.id, "name": pilot.name, "character_id": pilot.character_eve_id,
            "resolved": pilot.character_eve_id is not None, "slot_key": pilot.slot_key,
            "fitting": pilot.fitting_snapshot, "assigned_at": pilot.assigned_at.isoformat() if pilot.assigned_at else None}


def operation_payload(operation: Operation, pilots: list[Pilot]) -> dict:
    return {"schema_version": SCHEMA_VERSION, "id": operation.id, "name": operation.name,
            "briefing": operation.briefing, "status": operation.status, "revision": operation.revision,
            "slots": operation.slots, "pilots": [pilot_payload(pilot) for pilot in pilots],
            "personal_path": f"#fleet-assignments/my/{operation.id}",
            "updated_at": operation.updated_at.isoformat()}


def catalog_query():
    return select(CharacterFitting).options(
        selectinload(CharacterFitting.character), selectinload(CharacterFitting.ship_type),
        selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.item_type),
        selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.charge_type))


def can_distribute(fitting: CharacterFitting, user: User) -> bool:
    # Broad staff inspection rights are not permission to distribute private fits.
    return fitting.is_shared or bool(fitting.character and fitting.character.owner_user_id == user.id)


def fit_snapshot(db: Session, user: User, fitting_id: int, doctrine_id: int | None = None) -> dict:
    from app.api.fittings import fitting_copy_text
    fitting = db.scalar(catalog_query().where(CharacterFitting.id == fitting_id))
    if fitting is None or not can_distribute(fitting, user):
        raise HTTPException(403, "Choose a shared fitting or one owned by your account")
    doctrine = None
    if doctrine_id is not None:
        doctrine = db.get(Doctrine, doctrine_id)
        if doctrine is None or doctrine.archived_at or not (doctrine.is_shared or doctrine.created_by_user_id == user.id):
            raise HTTPException(403, "Doctrine is not available")
        linked = doctrine.fitting_id == fitting_id or db.scalar(select(DoctrineFitting.id).where(
            DoctrineFitting.doctrine_id == doctrine_id, DoctrineFitting.fitting_id == fitting_id))
        if not linked:
            raise HTTPException(400, "That fitting does not belong to the selected doctrine")
    return {"schema_version": SCHEMA_VERSION, "source_fitting_id": fitting.id,
            "name": fitting.name, "ship_type_id": fitting.ship_type_id,
            "ship_name": fitting.ship_type.name if fitting.ship_type else str(fitting.ship_type_id),
            "doctrine_id": doctrine_id, "doctrine_name": doctrine.name if doctrine else None,
            "eft": fitting_copy_text(fitting), "captured_at": datetime.now(timezone.utc).isoformat(),
            "items": [{"type_id": item.type_id, "name": item.item_type.name if item.item_type else str(item.type_id),
                       "flag": item.flag, "quantity": item.quantity, "charge_type_id": item.charge_type_id}
                      for item in sorted(fitting.items, key=lambda item: (item.flag, item.id))]}


def copied_slots(slots: list[dict]) -> list[dict]:
    return [{**deepcopy(slot), "key": str(uuid4())} for slot in slots]


async def resolve_roster(db: Session, text: str) -> tuple[list[dict], list[str], str | None]:
    try:
        names, duplicates = parse_roster(text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    keys = [name.casefold() for name in names]
    local = db.scalars(select(EveCharacter).where(func.lower(EveCharacter.name).in_(keys))).all() if keys else []
    resolved = {character.name.casefold(): {"name": character.name, "id": character.character_id} for character in local}
    missing = [name for name in names if name.casefold() not in resolved]
    warning = None
    if missing:
        from app.services.esi_client import EsiClient
        try:
            response = await EsiClient().post("/universe/ids/", missing)
            for character in response.get("characters", []):
                # Only exact character matches; corporations and alliances are ignored.
                if character["name"].casefold() in keys:
                    resolved[character["name"].casefold()] = character
        except (HTTPException, OSError, httpx.HTTPError):
            # Public ESI failure does not prevent locally known pilots being used.
            # Unresolved rows are never matched to an account by name.
            warning = "EVE name lookup is unavailable. Unresolved names remain unassigned; paste them again to retry."
    rows = [{"name": resolved.get(name.casefold(), {}).get("name", name),
             "character_id": resolved.get(name.casefold(), {}).get("id")} for name in names]
    return rows, duplicates, warning


def merge_roster(db: Session, operation: Operation, rows: list[dict]) -> dict:
    existing = pilots_for(db, operation.id)
    by_name = {pilot.normalized_name: pilot for pilot in existing}
    by_id = {pilot.character_eve_id: pilot for pilot in existing if pilot.character_eve_id is not None}
    additions, duplicates, resolved = [], [], 0
    for row in rows:
        key = row["name"].casefold()
        pilot = by_name.get(key) or by_id.get(row["character_id"])
        if pilot:
            if pilot.character_eve_id is None and row["character_id"] is not None:
                pilot.character_eve_id = row["character_id"]
                resolved += 1
            else:
                duplicates.append(row["name"])
            continue
        pilot = Pilot(operation_id=operation.id, name=row["name"], normalized_name=key,
                      character_eve_id=row["character_id"])
        additions.append(pilot)
        by_name[key] = pilot
        if row["character_id"] is not None:
            by_id[row["character_id"]] = pilot
    if len(existing) + len(additions) > MAX_PILOTS:
        raise HTTPException(422, "A fleet may contain at most 500 pilots")
    db.add_all(additions)
    db.flush()
    return {"added": len(additions), "duplicates": duplicates, "resolved": resolved,
            "unresolved": [pilot.name for pilot in [*existing, *additions] if pilot.character_eve_id is None]}
