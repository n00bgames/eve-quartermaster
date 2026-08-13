from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.api.fittings import can_view_fitting
from app.db.session import get_db
from app.models import CharacterFitting, CharacterFittingItem, Doctrine, DoctrineFitting, DoctrineSkillPlan, DoctrinePriorityField, DoctrinePriorityOption, EveCharacter, SkillPlan, User
from app.schemas.fleet_operations import DoctrineInput, DoctrinePatch, PriorityFieldInput
from app.services.doctrine_priority import validate_priority_values
from app.services.market import DEFAULT_HUB_KEYS, appraise_market
from app.services.permissions import can_view_at_least, can_view_section

router = APIRouter(prefix="/doctrines", tags=["doctrines"])


def require_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(user, "doctrines", db):
        raise HTTPException(status_code=403, detail="Doctrine permission is required")
    return user


def require_manager(user: User, db: Session) -> None:
    if not can_view_at_least(user, "officer", db):
        raise HTTPException(status_code=403, detail="Officer role is required to manage doctrines")


def field_query():
    return select(DoctrinePriorityField).options(selectinload(DoctrinePriorityField.options)).order_by(DoctrinePriorityField.display_order, DoctrinePriorityField.name)


def serialize_priority_field(row: DoctrinePriorityField) -> dict[str, Any]:
    return {
        "id": row.id, "key": row.key, "name": row.name, "field_type": row.field_type,
        "is_required": row.is_required, "display_order": row.display_order, "is_active": row.is_active,
        "options": [
            {"id": option.id, "label": option.label, "value": option.value, "short_code": option.short_code,
             "display_order": option.display_order, "is_active": option.is_active}
            for option in sorted(row.options, key=lambda item: (item.display_order, item.label.lower()))
        ],
    }


def load_doctrine(db: Session, doctrine_id: int) -> Doctrine:
    row = db.scalar(select(Doctrine).options(
        selectinload(Doctrine.fitting).selectinload(CharacterFitting.ship_type),
        selectinload(Doctrine.fitting_links).selectinload(DoctrineFitting.fitting).selectinload(CharacterFitting.ship_type),
        selectinload(Doctrine.fitting_links).selectinload(DoctrineFitting.fitting).selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.item_type),
        selectinload(Doctrine.fitting_links).selectinload(DoctrineFitting.fitting).selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.charge_type),
        selectinload(Doctrine.skill_plan_links).selectinload(DoctrineSkillPlan.skill_plan),
        selectinload(Doctrine.skill_plan_links).selectinload(DoctrineSkillPlan.fitting).selectinload(CharacterFitting.ship_type),
        selectinload(Doctrine.created_by_user), selectinload(Doctrine.updated_by_user), selectinload(Doctrine.linked_skill_plan),
    ).where(Doctrine.id == doctrine_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Doctrine not found")
    return row


def serialize_doctrine(row: Doctrine, include_detail: bool = False) -> dict[str, Any]:
    fitting = row.fitting
    links = sorted(row.fitting_links, key=lambda item: (not item.is_primary, item.sort_order, item.id))
    fittings = [
        {
            "link_id": link.id,
            "fitting_id": link.fitting_id,
            "fitting_name": link.fitting.name if link.fitting else (link.fitting_snapshot or {}).get("name"),
            "ship_type_id": link.fitting.ship_type_id if link.fitting else (link.fitting_snapshot or {}).get("ship_type_id"),
            "ship_name": link.fitting.ship_type.name if link.fitting and link.fitting.ship_type else (link.fitting_snapshot or {}).get("ship_name"),
            "is_primary": link.is_primary,
            "sort_order": link.sort_order,
        }
        for link in links
    ]
    result = {
        "id": row.id, "name": row.name, "purpose": row.purpose or row.description,
        "description": row.description, "notes": row.notes, "priority_code": row.priority_code,
        "priority_values": row.priority_values or {}, "priority_code_manual": row.priority_code_manual,
        "fitting_id": row.fitting_id, "fitting_name": fitting.name if fitting else (row.fitting_snapshot or {}).get("name"),
        "ship_type_id": fitting.ship_type_id if fitting else (row.fitting_snapshot or {}).get("ship_type_id"),
        "ship_name": fitting.ship_type.name if fitting and fitting.ship_type else (row.fitting_snapshot or {}).get("ship_name"),
        "linked_skill_plan_id": row.linked_skill_plan_id,
        "linked_skill_plan_name": row.linked_skill_plan.name if row.linked_skill_plan else None,
        "skill_plan_links": [
            {
                "link_id": link.id,
                "skill_plan_id": link.skill_plan_id,
                "skill_plan_name": link.skill_plan.name if link.skill_plan else f"Plan {link.skill_plan_id}",
                "fitting_id": link.fitting_id,
                "fitting_name": link.fitting.name if link.fitting else None,
                "ship_name": link.fitting.ship_type.name if link.fitting and link.fitting.ship_type else None,
                "sort_order": link.sort_order,
            }
            for link in sorted(row.skill_plan_links, key=lambda item: (item.sort_order, item.id))
        ],
        "is_shared": row.is_shared, "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_by": row.created_by_user.display_name if row.created_by_user else None,
        "updated_by": row.updated_by_user.display_name if row.updated_by_user else None,
        "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
        "fittings": fittings, "fitting_count": len(fittings),
    }
    if include_detail:
        result["fitting_snapshot"] = row.fitting_snapshot
    return result


def fit_snapshot(fitting: CharacterFitting) -> dict[str, Any]:
    return {"id": fitting.id, "name": fitting.name, "ship_type_id": fitting.ship_type_id,
            "ship_name": fitting.ship_type.name if fitting.ship_type else None,
            "captured_at": datetime.now(timezone.utc).isoformat()}


def requested_fitting_ids(payload: DoctrineInput | DoctrinePatch, existing: Doctrine | None) -> tuple[list[int], int | None]:
    fitting_fields_changed = bool(payload.model_fields_set & {"fitting_id", "fitting_ids", "primary_fitting_id"})
    if existing is not None and not fitting_fields_changed:
        ids = [link.fitting_id for link in sorted(existing.fitting_links, key=lambda item: item.sort_order)]
        if not ids and existing.fitting_id:
            ids = [existing.fitting_id]
        return ids, existing.fitting_id
    ids = list(payload.fitting_ids or []) if payload.fitting_ids is not None else []
    for candidate in (payload.fitting_id, payload.primary_fitting_id):
        if candidate and candidate not in ids:
            ids.append(candidate)
    primary_id = payload.primary_fitting_id or payload.fitting_id or (ids[0] if ids else None)
    return list(dict.fromkeys(ids)), primary_id


def validate_links(payload: DoctrineInput | DoctrinePatch, current_user: User, db: Session, existing: Doctrine | None = None) -> tuple[list[CharacterFitting], int | None, dict[str, Any], str]:
    fitting_ids, primary_id = requested_fitting_ids(payload, existing)
    fittings = list(db.scalars(select(CharacterFitting).options(
        selectinload(CharacterFitting.character), selectinload(CharacterFitting.ship_type)
    ).where(CharacterFitting.id.in_(fitting_ids))).all()) if fitting_ids else []
    fitting_by_id = {item.id: item for item in fittings}
    if len(fitting_by_id) != len(fitting_ids) or any(not can_view_fitting(current_user, fitting_by_id[item_id], db) for item_id in fitting_ids):
        raise HTTPException(status_code=400, detail="Choose only fittings you are permitted to view")
    shared = payload.is_shared if payload.is_shared is not None else (existing.is_shared if existing else True)
    if shared and any(not fitting.is_shared for fitting in fittings):
        raise HTTPException(status_code=400, detail="Share every fitting before linking it to a shared doctrine")
    values = payload.priority_values if payload.priority_values is not None else ((existing.priority_values or {}) if existing else {})
    manual = payload.priority_code_manual if payload.priority_code_manual is not None else (existing.priority_code_manual if existing else False)
    supplied_code = (payload.priority_code if payload.priority_code is not None else (existing.priority_code if existing else None)) if manual else None
    normalized, code = validate_priority_values(db.scalars(field_query()).all(), values, supplied_code)
    return [fitting_by_id[item_id] for item_id in fitting_ids], primary_id, normalized, code


def requested_skill_plan_links(payload: DoctrineInput | DoctrinePatch, existing: Doctrine | None) -> list[tuple[int, int | None]]:
    if "skill_plan_links" in payload.model_fields_set and payload.skill_plan_links is not None:
        requested = [(link.skill_plan_id, link.fitting_id) for link in payload.skill_plan_links]
    elif "linked_skill_plan_id" in payload.model_fields_set:
        requested = [(payload.linked_skill_plan_id, None)] if payload.linked_skill_plan_id else []
    elif existing is not None:
        requested = [(link.skill_plan_id, link.fitting_id) for link in sorted(existing.skill_plan_links, key=lambda item: item.sort_order)]
        if not requested and existing.linked_skill_plan_id:
            requested = [(existing.linked_skill_plan_id, existing.fitting_id)]
    else:
        requested = []
    deduplicated: list[tuple[int, int | None]] = []
    seen: set[int] = set()
    for plan_id, fitting_id in requested:
        if plan_id and plan_id not in seen:
            seen.add(plan_id)
            deduplicated.append((plan_id, fitting_id))
    return deduplicated


def validate_skill_plan_links(
    payload: DoctrineInput | DoctrinePatch,
    existing: Doctrine | None,
    fittings: list[CharacterFitting],
    current_user: User,
    db: Session,
) -> list[tuple[SkillPlan, int | None]]:
    requested = requested_skill_plan_links(payload, existing)
    plan_ids = [plan_id for plan_id, _ in requested]
    plans = list(db.scalars(select(SkillPlan).where(SkillPlan.id.in_(plan_ids))).all()) if plan_ids else []
    by_id = {plan.id: plan for plan in plans}
    fitting_ids = {fitting.id for fitting in fittings}
    director = can_view_at_least(current_user, "director", db)
    result: list[tuple[SkillPlan, int | None]] = []
    for plan_id, fitting_id in requested:
        plan = by_id.get(plan_id)
        if plan is None or plan.archived_at is not None or (plan.owner_user_id != current_user.id and not director):
            raise HTTPException(status_code=400, detail="Linked skill plan is unavailable")
        if fitting_id is not None and fitting_id not in fitting_ids:
            raise HTTPException(status_code=400, detail="A skill plan may only target a fitting attached to this doctrine")
        result.append((plan, fitting_id))
    return result


def replace_fitting_links(db: Session, row: Doctrine, fittings: list[CharacterFitting], primary_id: int | None) -> None:
    for link in list(row.fitting_links):
        db.delete(link)
    db.flush()
    row.fitting_id = primary_id
    primary = next((item for item in fittings if item.id == primary_id), None)
    row.fitting_snapshot = fit_snapshot(primary) if primary else None
    row.fitting_links = [
        DoctrineFitting(
            fitting_id=fitting.id,
            is_primary=fitting.id == primary_id,
            sort_order=index,
            fitting_snapshot=fit_snapshot(fitting),
        )
        for index, fitting in enumerate(fittings)
    ]


def replace_skill_plan_links(db: Session, row: Doctrine, links: list[tuple[SkillPlan, int | None]]) -> None:
    for link in list(row.skill_plan_links):
        db.delete(link)
    db.flush()
    row.linked_skill_plan_id = links[0][0].id if links else None
    row.skill_plan_links = [
        DoctrineSkillPlan(skill_plan_id=plan.id, fitting_id=fitting_id, sort_order=index)
        for index, (plan, fitting_id) in enumerate(links)
    ]


@router.get("/meta")
def doctrine_meta(current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    fittings = db.scalars(select(CharacterFitting).options(selectinload(CharacterFitting.character), selectinload(CharacterFitting.ship_type)).order_by(CharacterFitting.name)).all()
    plans = db.scalars(select(SkillPlan).where(SkillPlan.archived_at.is_(None)).order_by(SkillPlan.name)).all()
    characters = db.scalars(select(EveCharacter).where(EveCharacter.owner_user_id == current_user.id).order_by(EveCharacter.name)).all()
    return {
        "can_manage": can_view_at_least(current_user, "officer", db),
        "priority_fields": [serialize_priority_field(row) for row in db.scalars(field_query()).all() if row.is_active],
        "all_priority_fields": [serialize_priority_field(row) for row in db.scalars(field_query()).all()],
        "fittings": [{"id": row.id, "name": row.name, "ship_name": row.ship_type.name if row.ship_type else None,
                      "character_name": row.character.name if row.character else None, "is_draft": row.is_draft}
                     for row in fittings if can_view_fitting(current_user, row, db)],
        "skill_plans": [{"id": row.id, "name": row.name} for row in plans if row.owner_user_id == current_user.id or can_view_at_least(current_user, "director", db)],
        "characters": [{"id": row.id, "name": row.name} for row in characters],
    }


@router.get("/priority-fields")
def list_priority_fields(_: User = Depends(require_view), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [serialize_priority_field(row) for row in db.scalars(field_query()).all()]


@router.post("/priority-fields")
def create_priority_field(payload: PriorityFieldInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db)
    if db.scalar(select(DoctrinePriorityField.id).where(DoctrinePriorityField.key == payload.key)):
        raise HTTPException(status_code=409, detail="Priority field key already exists")
    row = DoctrinePriorityField(**payload.model_dump(exclude={"options"}), created_by_user_id=current_user.id)
    row.options = [DoctrinePriorityOption(**option.model_dump()) for option in payload.options]
    db.add(row); db.commit()
    return serialize_priority_field(db.scalar(field_query().where(DoctrinePriorityField.id == row.id)))


@router.put("/priority-fields/{field_id}")
def update_priority_field(field_id: int, payload: PriorityFieldInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db)
    row = db.scalar(field_query().where(DoctrinePriorityField.id == field_id))
    if row is None: raise HTTPException(status_code=404, detail="Priority field not found")
    duplicate = db.scalar(select(DoctrinePriorityField.id).where(DoctrinePriorityField.key == payload.key, DoctrinePriorityField.id != field_id))
    if duplicate: raise HTTPException(status_code=409, detail="Priority field key already exists")
    for key, value in payload.model_dump(exclude={"options"}).items(): setattr(row, key, value)
    for option in list(row.options): db.delete(option)
    db.flush()
    row.options = [DoctrinePriorityOption(**option.model_dump()) for option in payload.options]
    db.commit()
    return serialize_priority_field(db.scalar(field_query().where(DoctrinePriorityField.id == row.id)))


@router.get("")
def list_doctrines(q: str = "", priority: str = "", fitting_id: int | None = None, ship_type_id: int | None = None,
                   include_archived: bool = False, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    statement = select(Doctrine).options(selectinload(Doctrine.fitting).selectinload(CharacterFitting.ship_type), selectinload(Doctrine.fitting_links).selectinload(DoctrineFitting.fitting).selectinload(CharacterFitting.ship_type), selectinload(Doctrine.skill_plan_links).selectinload(DoctrineSkillPlan.skill_plan), selectinload(Doctrine.skill_plan_links).selectinload(DoctrineSkillPlan.fitting).selectinload(CharacterFitting.ship_type), selectinload(Doctrine.linked_skill_plan), selectinload(Doctrine.created_by_user), selectinload(Doctrine.updated_by_user))
    if not include_archived: statement = statement.where(Doctrine.archived_at.is_(None))
    if not can_view_at_least(current_user, "officer", db): statement = statement.where(Doctrine.is_shared.is_(True))
    if q.strip(): statement = statement.where(or_(Doctrine.name.ilike(f"%{q.strip()}%"), Doctrine.purpose.ilike(f"%{q.strip()}%"), Doctrine.notes.ilike(f"%{q.strip()}%")))
    if priority.strip(): statement = statement.where(Doctrine.priority_code.ilike(f"%{priority.strip()}%"))
    if fitting_id: statement = statement.where(Doctrine.fitting_links.any(DoctrineFitting.fitting_id == fitting_id))
    if ship_type_id: statement = statement.where(Doctrine.fitting_links.any(DoctrineFitting.fitting.has(CharacterFitting.ship_type_id == ship_type_id)))
    return [serialize_doctrine(row) for row in db.scalars(statement.order_by(Doctrine.archived_at.nullsfirst(), func.lower(Doctrine.name))).all()]


@router.post("")
def create_doctrine(payload: DoctrineInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db)
    fittings, primary_id, values, code = validate_links(payload, current_user, db)
    plan_links = validate_skill_plan_links(payload, None, fittings, current_user, db)
    row = Doctrine(name=payload.name, purpose=payload.purpose, description=payload.purpose, notes=payload.notes,
                   priority_values=values, priority_code=code, priority_code_manual=payload.priority_code_manual,
                   is_shared=payload.is_shared, created_by_user_id=current_user.id, updated_by_user_id=current_user.id)
    db.add(row); db.flush(); replace_fitting_links(db, row, fittings, primary_id); replace_skill_plan_links(db, row, plan_links); db.commit()
    return serialize_doctrine(load_doctrine(db, row.id), True)


@router.get("/{doctrine_id}")
def get_doctrine(doctrine_id: int, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = load_doctrine(db, doctrine_id)
    if not row.is_shared and not can_view_at_least(current_user, "officer", db): raise HTTPException(status_code=404, detail="Doctrine not found")
    return serialize_doctrine(row, True)


@router.patch("/{doctrine_id}")
def update_doctrine(doctrine_id: int, payload: DoctrinePatch, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db); row = load_doctrine(db, doctrine_id)
    fittings, primary_id, values, code = validate_links(payload, current_user, db, row)
    plan_links = validate_skill_plan_links(payload, row, fittings, current_user, db)
    for key in ("name", "purpose", "notes", "is_shared", "priority_code_manual"):
        if key in payload.model_fields_set: setattr(row, key, getattr(payload, key))
    row.description = row.purpose; replace_fitting_links(db, row, fittings, primary_id)
    replace_skill_plan_links(db, row, plan_links)
    row.priority_values = values; row.priority_code = code; row.updated_by_user_id = current_user.id
    db.commit(); return serialize_doctrine(load_doctrine(db, row.id), True)


@router.post("/{doctrine_id}/appraise")
async def appraise_doctrine(doctrine_id: int, payload: dict[str, Any], current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = load_doctrine(db, doctrine_id)
    if not row.is_shared and not can_view_at_least(current_user, "officer", db):
        raise HTTPException(status_code=404, detail="Doctrine not found")
    links = [link for link in row.fitting_links if link.fitting]
    if not links:
        raise HTTPException(status_code=409, detail="Add at least one fitting before appraising this doctrine")
    fit_quantities: dict[int, dict[int, int]] = {}
    type_names: dict[int, str] = {}
    combined: dict[int, int] = {}
    for link in links:
        fitting = link.fitting
        quantities = {fitting.ship_type_id: 1}
        if fitting.ship_type:
            type_names[fitting.ship_type_id] = fitting.ship_type.name
        for item in fitting.items:
            quantities[item.type_id] = quantities.get(item.type_id, 0) + max(1, item.quantity)
            if item.item_type:
                type_names[item.type_id] = item.item_type.name
            if item.charge_type_id and item.charge_type:
                quantities[item.charge_type_id] = quantities.get(item.charge_type_id, 0) + max(1, item.quantity)
                type_names[item.charge_type_id] = item.charge_type.name
        fit_quantities[fitting.id] = quantities
        for type_id, quantity in quantities.items():
            combined[type_id] = combined.get(type_id, 0) + quantity
    lines = [f"{quantity} {type_names[type_id]}" for type_id, quantity in combined.items() if type_id in type_names]
    hubs = payload.get("hubs")
    result = await appraise_market(db, "\n".join(lines), hubs if isinstance(hubs, list) and hubs else DEFAULT_HUB_KEYS)
    quotes = {int(item["type_id"]): item for item in result["items"] if item.get("type_id")}
    fitting_results = []
    for link in links:
        totals: dict[str, dict[str, float]] = {}
        for hub in result["hubs"]:
            key = hub["key"]
            totals[key] = {"buy_total": 0.0, "sell_total": 0.0, "split_total": 0.0}
            for type_id, quantity in fit_quantities[link.fitting_id].items():
                quote = quotes.get(type_id, {}).get("hubs", {}).get(key, {})
                for price_key, total_key in (("buy", "buy_total"), ("sell", "sell_total"), ("split", "split_total")):
                    totals[key][total_key] += float(quote.get(price_key) or 0) * quantity
        fitting_results.append({
            "fitting_id": link.fitting_id, "fitting_name": link.fitting.name,
            "ship_name": link.fitting.ship_type.name if link.fitting.ship_type else None,
            "is_primary": link.is_primary, "totals": totals,
        })
    return {"doctrine_id": row.id, "doctrine_name": row.name, "combined": result, "fittings": fitting_results}


@router.delete("/{doctrine_id}")
def archive_doctrine(doctrine_id: int, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db); row = load_doctrine(db, doctrine_id)
    row.archived_at = datetime.now(timezone.utc); row.updated_by_user_id = current_user.id; db.commit()
    return {"id": row.id, "archived": True}


@router.post("/{doctrine_id}/restore")
def restore_doctrine(doctrine_id: int, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_manager(current_user, db); row = load_doctrine(db, doctrine_id)
    row.archived_at = None; row.updated_by_user_id = current_user.id; db.commit()
    return serialize_doctrine(load_doctrine(db, row.id), True)
