from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.auth import get_current_user
from app.db.session import get_db
from app.domain.fleet_assignments import MAX_SLOTS, SCHEMA_VERSION, assignment_targets, may_view_assignment
from app.models import CharacterFitting, Doctrine, DoctrineFitting, EsiToken, EveCharacter, User
from app.models.fleet_assignments import FleetAssignmentOperation as Operation, FleetAssignmentPilot as Pilot, FleetAssignmentPreset as Preset
from app.schemas.fleet_assignments import AssignmentInput, OperationCreate, OperationPatch, PresetCreate, Revision, RosterImport, SlotCreate, SlotPatch
from app.services import fleet_assignments as service
from app.services.permissions import can_view_section


def viewer(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    service.require_access(user, db)
    response.headers["Cache-Control"] = "private, no-store"
    return user


router = APIRouter(prefix="/fleet-assignments", tags=["fleet-assignments"], dependencies=[Depends(viewer)])


@router.get("/meta")
def metadata(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"can_manage": service.is_manager(user, db), "schema_version": SCHEMA_VERSION}


@router.get("/my")
@router.get("/my/{operation_id}")
def personal(operation_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    principal = service.principal_for(user, db)
    query = select(Operation, Pilot).join(Pilot, Pilot.operation_id == Operation.id).where(
        Operation.status == "published", Pilot.character_eve_id.in_(principal.character_ids),
        Pilot.fitting_snapshot.is_not(None), Pilot.slot_key.is_not(None))
    if operation_id is not None:
        query = query.where(Operation.id == operation_id)
    grouped = {}
    for operation, pilot in db.execute(query.order_by(Operation.id.desc(), Pilot.name)).all():
        if pilot.fitting_snapshot is None or not may_view_assignment(principal, pilot.character_eve_id, True):
            continue
        row = grouped.setdefault(operation.id, {"id": operation.id, "name": operation.name,
                                                "briefing": operation.briefing, "assignments": []})
        row["assignments"].append(service.pilot_payload(pilot))
    if operation_id is not None and not grouped:
        raise HTTPException(404, "No published assignments are available for your linked characters in this fleet")
    return list(grouped.values())


@router.get("/sources")
def sources(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    fittings = list(db.scalars(select(CharacterFitting).options(selectinload(CharacterFitting.character), selectinload(CharacterFitting.ship_type)).order_by(CharacterFitting.name)).all()) if can_view_section(user, "fittings", db) else []
    fittings = [fit for fit in fittings if service.can_distribute(fit, user)]
    fit_ids = {fit.id for fit in fittings}
    doctrines = db.scalars(select(Doctrine).where(Doctrine.archived_at.is_(None)).order_by(Doctrine.name)).all() if can_view_section(user, "doctrines", db) else []
    doctrine_rows = []
    for doctrine in doctrines:
        if not (doctrine.is_shared or doctrine.created_by_user_id == user.id):
            continue
        linked = list(db.scalars(select(DoctrineFitting.fitting_id).where(DoctrineFitting.doctrine_id == doctrine.id)).all())
        if doctrine.fitting_id and doctrine.fitting_id not in linked:
            linked.insert(0, doctrine.fitting_id)
        doctrine_rows.append({"id": doctrine.id, "name": doctrine.name, "fitting_ids": [fid for fid in linked if fid in fit_ids]})
    tokens = db.execute(select(EsiToken, EveCharacter).join(EveCharacter, EveCharacter.id == EsiToken.character_id).where(
        EsiToken.user_id == user.id, EsiToken.revoked_at.is_(None), EveCharacter.owner_user_id == user.id,
        EveCharacter.sync_opt_out.is_(False))).all()
    return {"fittings": [{"id": fit.id, "name": fit.name, "ship_name": fit.ship_type.name if fit.ship_type else None,
                           "ship_type_id": fit.ship_type_id, "character_id": fit.character.character_id,
                           "character_name": fit.character.name} for fit in fittings],
            "doctrines": doctrine_rows,
            "sync_tokens": [{"id": token.id, "name": character.name} for token, character in tokens
                            if "esi-fittings.read_fittings.v1" in token.scopes.split()]}


@router.get("/presets")
def presets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    return [{"id": preset.id, "name": preset.name, "slot_count": len(preset.slots)}
            for preset in db.scalars(select(Preset).order_by(Preset.name)).all()]


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    preset = db.get(Preset, preset_id)
    if preset is None:
        raise HTTPException(404, "Preset not found")
    from app.services.audit import record_audit_event
    record_audit_event(db, event_kind="fleet_assignments", title=f"Fleet preset deleted: {preset.name}"[:255], actor_user=user)
    db.delete(preset)
    db.commit()
    return {"deleted": True}


@router.get("/operations")
def operations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    return [{"id": row.id, "name": row.name, "status": row.status}
            for row in db.scalars(select(Operation).order_by(Operation.id.desc()).limit(200)).all()]


@router.post("/operations", status_code=201)
def create_operation(payload: OperationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    preset = db.get(Preset, payload.preset_id) if payload.preset_id else None
    if payload.preset_id and preset is None:
        raise HTTPException(404, "Preset not found")
    row = Operation(name=payload.name, briefing=payload.briefing or (preset.briefing if preset else ""),
                    slots=service.copied_slots(preset.slots) if preset else [], created_by_user_id=user.id)
    db.add(row)
    db.flush()
    service.audit(db, user, row, "created", {"preset_id": payload.preset_id})
    db.commit()
    return service.operation_payload(row, [])


@router.get("/operations/{operation_id}")
def operation_detail(operation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    return service.operation_payload(service.get_operation(db, operation_id), service.pilots_for(db, operation_id))


@router.patch("/operations/{operation_id}")
def patch_operation(operation_id: int, payload: OperationPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    row = service.get_operation(db, operation_id)
    if row.status == "archived" and payload.status != "draft":
        raise HTTPException(409, "Restore this archived fleet to draft before editing")
    pilots = service.pilots_for(db, row.id)
    if payload.status == "published" and not any(pilot.slot_key and pilot.character_eve_id for pilot in pilots):
        raise HTTPException(422, "Assign a fitting to at least one resolved pilot before publishing")
    service.claim_revision(db, row, payload.revision)
    previous = {"name": row.name, "briefing": row.briefing, "status": row.status}
    for field in ("name", "briefing", "status"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    service.audit(db, user, row, "updated", {"previous": previous, "new": {key: getattr(row, key) for key in previous}})
    db.commit()
    return service.operation_payload(row, pilots)


@router.post("/operations/{operation_id}/roster")
async def import_roster(operation_id: int, payload: RosterImport, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    row = service.get_operation(db, operation_id)
    service.require_editable(row)
    rows, duplicates, warning = await service.resolve_roster(db, payload.text)
    service.claim_revision(db, row, payload.revision)
    report = service.merge_roster(db, row, rows)
    report["duplicates"] = list(dict.fromkeys([*duplicates, *report["duplicates"]]))
    report["warning"] = warning
    service.audit(db, user, row, "roster imported", report)
    db.commit()
    return {"operation": service.operation_payload(row, service.pilots_for(db, row.id)), "report": report}


@router.post("/operations/{operation_id}/slots")
def add_slot(operation_id: int, payload: SlotCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    row = service.get_operation(db, operation_id)
    service.require_editable(row)
    if len(row.slots) >= MAX_SLOTS:
        raise HTTPException(422, "A fleet may contain at most 100 fitting roles")
    if not can_view_section(user, "fittings", db) or (payload.doctrine_id and not can_view_section(user, "doctrines", db)):
        raise HTTPException(403, "Fitting source permission is required")
    snapshot = service.fit_snapshot(db, user, payload.fitting_id, payload.doctrine_id)
    service.claim_revision(db, row, payload.revision)
    slot = {"key": str(uuid4()), "role": payload.role.strip(), "target_count": payload.target_count, "fitting": snapshot}
    row.slots = [*row.slots, slot]
    service.audit(db, user, row, "fitting added", {"slot": slot})
    db.commit()
    return service.operation_payload(row, service.pilots_for(db, row.id))


@router.patch("/operations/{operation_id}/slots/{slot_key}")
def patch_slot(operation_id: int, slot_key: str, payload: SlotPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    row = service.get_operation(db, operation_id)
    service.require_editable(row)
    slots = deepcopy(row.slots)
    slot = next((slot for slot in slots if slot["key"] == slot_key), None)
    if slot is None:
        raise HTTPException(404, "Fitting role not found")
    service.claim_revision(db, row, payload.revision)
    slot.update(role=payload.role.strip(), target_count=payload.target_count)
    row.slots = slots
    service.audit(db, user, row, "role updated", {"slot_key": slot_key, "role": slot["role"], "target_count": slot["target_count"]})
    db.commit()
    return service.operation_payload(row, service.pilots_for(db, row.id))


@router.delete("/operations/{operation_id}/slots/{slot_key}")
def delete_slot(operation_id: int, slot_key: str, revision: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    row = service.get_operation(db, operation_id)
    service.require_editable(row)
    if not any(slot["key"] == slot_key for slot in row.slots):
        raise HTTPException(404, "Fitting role not found")
    if db.scalar(select(Pilot.id).where(Pilot.operation_id == row.id, Pilot.slot_key == slot_key).limit(1)):
        raise HTTPException(409, "Clear or move assignments before removing this fitting role")
    service.claim_revision(db, row, revision)
    row.slots = [slot for slot in row.slots if slot["key"] != slot_key]
    service.audit(db, user, row, "fitting removed", {"slot_key": slot_key})
    db.commit()
    return service.operation_payload(row, service.pilots_for(db, row.id))


@router.post("/operations/{operation_id}/assign")
def assign(operation_id: int, payload: AssignmentInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    row = service.get_operation(db, operation_id)
    service.require_editable(row)
    pilots = service.pilots_for(db, row.id)
    try:
        targets = assignment_targets(payload.pilot_ids, [pilot.id for pilot in pilots])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    slot = next((slot for slot in row.slots if slot["key"] == payload.slot_key), None)
    if payload.slot_key is not None and slot is None:
        raise HTTPException(404, "Fitting role not found")
    selected = [pilot for pilot in pilots if pilot.id in targets]
    if slot and any(pilot.character_eve_id is None for pilot in selected):
        raise HTTPException(422, "Resolve these pilot names before assigning fittings")
    service.claim_revision(db, row, payload.revision)
    changes = []
    for pilot in selected:
        changes.append({"pilot_id": pilot.id, "character_id": pilot.character_eve_id,
                        "previous_slot": pilot.slot_key, "previous_fitting": pilot.fitting_snapshot,
                        "new_slot": payload.slot_key, "new_fitting": slot["fitting"] if slot else None})
        pilot.slot_key = payload.slot_key
        pilot.fitting_snapshot = deepcopy(slot["fitting"]) if slot else None
        pilot.assigned_at = datetime.now(timezone.utc) if slot else None
    service.audit(db, user, row, "assignments changed", {"changes": changes})
    db.commit()
    return service.operation_payload(row, pilots)


@router.delete("/operations/{operation_id}/pilots/{pilot_id}")
def remove_pilot(operation_id: int, pilot_id: int, revision: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    row = service.get_operation(db, operation_id)
    service.require_editable(row)
    pilot = db.get(Pilot, pilot_id)
    if pilot is None or pilot.operation_id != operation_id:
        raise HTTPException(404, "Pilot not found in this operation")
    service.claim_revision(db, row, revision)
    service.audit(db, user, row, "pilot removed", {"previous": service.pilot_payload(pilot)})
    db.delete(pilot)
    db.commit()
    return service.operation_payload(row, service.pilots_for(db, row.id))


@router.post("/operations/{operation_id}/preset", status_code=201)
def save_preset(operation_id: int, payload: PresetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.require_manager(user, db)
    row = service.get_operation(db, operation_id)
    service.claim_revision(db, row, payload.revision)
    preset = Preset(name=payload.name, briefing=row.briefing, slots=deepcopy(row.slots), created_by_user_id=user.id)
    db.add(preset)
    db.flush()
    service.audit(db, user, row, "preset saved", {"preset_id": preset.id})
    db.commit()
    return {"id": preset.id, "name": preset.name, "operation": service.operation_payload(row, service.pilots_for(db, row.id))}
