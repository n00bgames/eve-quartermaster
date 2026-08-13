from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import can_view_all_characters, get_current_user
from app.api.fittings import can_view_fitting
from app.db.session import get_db
from app.models import CharacterFitting, CharacterSkill, Doctrine, DoctrineFitting, EveCategory, EveCharacter, EveGroup, EveType, SkillPlan, SkillPlanEntry, User
from app.schemas.fleet_operations import SkillPlanGenerationInput, SkillPlanInput, SkillPlanMergeInput
from app.services.permissions import can_view_section
from app.services.skill_plan_generator import generate_fitting_skill_plan

router = APIRouter(prefix="/skill-plans", tags=["skill-plans"])


def require_view(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(user, "skills", db):
        raise HTTPException(status_code=403, detail="Skills permission is required")
    return user


def can_manage_plan(user: User, plan: SkillPlan) -> bool:
    return plan.owner_user_id == user.id


def can_view_plan(user: User, plan: SkillPlan, db: Session) -> bool:
    return can_manage_plan(user, plan) or can_view_all_characters(user, db)


def plan_query():
    return select(SkillPlan).options(
        selectinload(SkillPlan.character), selectinload(SkillPlan.fitting).selectinload(CharacterFitting.ship_type),
        selectinload(SkillPlan.source_doctrine), selectinload(SkillPlan.owner_user),
        selectinload(SkillPlan.entries).selectinload(SkillPlanEntry.skill_type),
    )


def load_plan(db: Session, plan_id: int, current_user: User) -> SkillPlan:
    row = db.scalar(plan_query().where(SkillPlan.id == plan_id))
    if row is None or not can_view_plan(current_user, row, db):
        raise HTTPException(status_code=404, detail="Skill plan not found")
    return row


def serialize_plan(row: SkillPlan, db: Session, current_user: User, character_id: int | None = None) -> dict[str, Any]:
    target_character_id = character_id or row.character_id
    levels: dict[int, int] = {}
    if target_character_id:
        levels = {skill_id: level for skill_id, level in db.execute(select(CharacterSkill.skill_type_id, CharacterSkill.trained_skill_level).where(CharacterSkill.character_id == target_character_id)).all()}
    entries = []
    complete = partial = missing = 0
    for entry in sorted(row.entries, key=lambda item: (item.sort_order, item.id)):
        trained = levels.get(entry.skill_type_id, 0)
        state = "complete" if trained >= entry.target_level else "partial" if trained > 0 else "missing"
        complete += state == "complete"; partial += state == "partial"; missing += state == "missing"
        entries.append({"id": entry.id, "skill_type_id": entry.skill_type_id,
                        "skill_name": entry.skill_type.name if entry.skill_type else f"Type {entry.skill_type_id}",
                        "target_level": entry.target_level, "sort_order": entry.sort_order, "notes": entry.notes,
                        "introduced_by": entry.introduced_by or [], "trained_level": trained, "state": state})
    return {
        "id": row.id, "name": row.name, "description": row.description, "notes": row.notes, "source": row.source,
        "owner_user_id": row.owner_user_id, "owner_name": row.owner_user.display_name if row.owner_user else None,
        "character_id": row.character_id, "character_name": row.character.name if row.character else None,
        "fitting_id": row.fitting_id, "fitting_name": row.fitting.name if row.fitting else None,
        "ship_name": row.fitting.ship_type.name if row.fitting and row.fitting.ship_type else None,
        "source_doctrine_id": row.source_doctrine_id, "source_doctrine_name": row.source_doctrine.name if row.source_doctrine else None,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
        "can_manage": can_manage_plan(current_user, row),
        "progress": {"complete": complete, "partial": partial, "missing": missing, "total": len(entries)}, "entries": entries,
    }


def validate_character(character_id: int | None, current_user: User, db: Session) -> EveCharacter | None:
    if character_id is None: return None
    character = db.get(EveCharacter, character_id)
    if character is None: raise HTTPException(status_code=400, detail="Character not found")
    if character.owner_user_id != current_user.id and not can_view_all_characters(current_user, db):
        raise HTTPException(status_code=403, detail="You cannot use that character")
    return character


def validate_skill_entries(payload: SkillPlanInput, db: Session) -> list[SkillPlanEntry]:
    seen: dict[int, Any] = {}
    for entry in payload.entries:
        current = seen.get(entry.skill_type_id)
        if current is None or entry.target_level > current.target_level: seen[entry.skill_type_id] = entry
    known = set(db.scalars(select(EveType.type_id).where(EveType.type_id.in_(seen))).all()) if seen else set()
    missing = sorted(set(seen) - known)
    if missing: raise HTTPException(status_code=400, detail=f"Unknown skill type(s): {', '.join(map(str, missing))}")
    ordered = sorted(seen.values(), key=lambda item: item.sort_order)
    return [SkillPlanEntry(skill_type_id=item.skill_type_id, target_level=item.target_level, sort_order=index,
                           notes=item.notes, introduced_by=item.introduced_by) for index, item in enumerate(ordered)]


def validate_plan_links(payload: SkillPlanInput, current_user: User, db: Session) -> None:
    if payload.fitting_id:
        fitting = db.scalar(select(CharacterFitting).options(selectinload(CharacterFitting.character)).where(CharacterFitting.id == payload.fitting_id))
        if fitting is None or not can_view_fitting(current_user, fitting, db):
            raise HTTPException(status_code=400, detail="Fitting is unavailable")
    if payload.source_doctrine_id:
        doctrine = db.get(Doctrine, payload.source_doctrine_id)
        if doctrine is None or doctrine.archived_at is not None:
            raise HTTPException(status_code=400, detail="Doctrine is unavailable")
        doctrine_fitting_ids = set(db.scalars(select(DoctrineFitting.fitting_id).where(DoctrineFitting.doctrine_id == doctrine.id)).all())
        if doctrine.fitting_id:
            doctrine_fitting_ids.add(doctrine.fitting_id)
        if payload.fitting_id and payload.fitting_id not in doctrine_fitting_ids:
            raise HTTPException(status_code=400, detail="Plan fitting must match doctrine fitting")


@router.get("/meta")
def skill_plan_meta(current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    characters = db.scalars(select(EveCharacter).where(or_(EveCharacter.owner_user_id == current_user.id, can_view_all_characters(current_user, db))).order_by(EveCharacter.name)).all() if can_view_all_characters(current_user, db) else db.scalars(select(EveCharacter).where(EveCharacter.owner_user_id == current_user.id).order_by(EveCharacter.name)).all()
    fittings = db.scalars(select(CharacterFitting).options(selectinload(CharacterFitting.character), selectinload(CharacterFitting.ship_type)).order_by(CharacterFitting.name)).all()
    doctrines = db.scalars(select(Doctrine).where(Doctrine.archived_at.is_(None), Doctrine.fitting_id.is_not(None)).order_by(Doctrine.name)).all()
    return {"characters": [{"id": row.id, "name": row.name} for row in characters],
            "fittings": [{"id": row.id, "name": row.name, "ship_name": row.ship_type.name if row.ship_type else None} for row in fittings if can_view_fitting(current_user, row, db)],
            "doctrines": [{"id": row.id, "name": row.name, "fitting_id": row.fitting_id} for row in doctrines]}


@router.get("/search/skills")
def search_skills(q: str = Query(..., min_length=1), current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(EveType).join(EveGroup).join(EveCategory).where(func.lower(EveCategory.name) == "skill", EveType.name.ilike(f"%{q.strip()}%")).order_by(EveType.name).limit(40)).all()
    return [{"type_id": row.type_id, "name": row.name} for row in rows]


@router.post("/generate-preview")
def generation_preview(payload: SkillPlanGenerationInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    fitting_id = payload.fitting_id
    if payload.doctrine_id:
        doctrine = db.get(Doctrine, payload.doctrine_id)
        if doctrine is None or doctrine.archived_at is not None or doctrine.fitting_id is None: raise HTTPException(status_code=400, detail="Doctrine has no available fitting")
        if fitting_id and fitting_id != doctrine.fitting_id: raise HTTPException(status_code=400, detail="Fitting does not match doctrine")
        fitting_id = doctrine.fitting_id
    fitting = db.scalar(select(CharacterFitting).options(selectinload(CharacterFitting.character)).where(CharacterFitting.id == fitting_id))
    if fitting is None or not can_view_fitting(current_user, fitting, db): raise HTTPException(status_code=403, detail="Fitting is unavailable")
    try: result = generate_fitting_skill_plan(db, fitting.id)
    except ValueError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc
    result["doctrine_id"] = payload.doctrine_id
    return result


@router.post("/merge-preview")
def merge_preview(payload: SkillPlanMergeInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    plans = list(db.scalars(plan_query().where(SkillPlan.id.in_(payload.plan_ids))).unique().all())
    by_id = {plan.id: plan for plan in plans}
    ordered: list[SkillPlan] = []
    for plan_id in payload.plan_ids:
        plan = by_id.get(plan_id)
        if plan is None or plan.archived_at is not None or not can_view_plan(current_user, plan, db):
            raise HTTPException(status_code=404, detail="One or more source skill plans are unavailable")
        ordered.append(plan)
    merged: dict[int, dict[str, Any]] = {}
    sequence: list[int] = []
    for plan in ordered:
        for entry in sorted(plan.entries, key=lambda item: (item.sort_order, item.id)):
            source = f"Plan: {plan.name}"
            current = merged.get(entry.skill_type_id)
            if current is None:
                sequence.append(entry.skill_type_id)
                merged[entry.skill_type_id] = {
                    "skill_type_id": entry.skill_type_id,
                    "skill_name": entry.skill_type.name if entry.skill_type else f"Type {entry.skill_type_id}",
                    "target_level": entry.target_level,
                    "notes": entry.notes,
                    "introduced_by": list(dict.fromkeys([*(entry.introduced_by or []), source])),
                }
            else:
                current["target_level"] = max(current["target_level"], entry.target_level)
                current["introduced_by"] = list(dict.fromkeys([*current["introduced_by"], *(entry.introduced_by or []), source]))
                if not current.get("notes") and entry.notes:
                    current["notes"] = entry.notes
    entries = [{**merged[skill_id], "sort_order": index} for index, skill_id in enumerate(sequence)]
    return {
        "source_plan_ids": payload.plan_ids,
        "source_plan_names": [plan.name for plan in ordered],
        "name": f"{' + '.join(plan.name for plan in ordered)} Master Plan",
        "entries": entries,
        "source": "merged",
    }


@router.get("")
def list_plans(include_archived: bool = False, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    statement = plan_query()
    if not can_view_all_characters(current_user, db): statement = statement.where(SkillPlan.owner_user_id == current_user.id)
    if not include_archived: statement = statement.where(SkillPlan.archived_at.is_(None))
    return [serialize_plan(row, db, current_user) for row in db.scalars(statement.order_by(SkillPlan.archived_at.nullsfirst(), SkillPlan.name)).unique().all()]


@router.post("")
def create_plan(payload: SkillPlanInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    validate_character(payload.character_id, current_user, db)
    validate_plan_links(payload, current_user, db)
    row = SkillPlan(name=payload.name, description=payload.description, notes=payload.notes, owner_user_id=current_user.id,
                    character_id=payload.character_id, fitting_id=payload.fitting_id, source_doctrine_id=payload.source_doctrine_id, source=payload.source)
    row.entries = validate_skill_entries(payload, db); db.add(row); db.commit()
    return serialize_plan(load_plan(db, row.id, current_user), db, current_user)


@router.get("/{plan_id}")
def get_plan(plan_id: int, character_id: int | None = None, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    if character_id: validate_character(character_id, current_user, db)
    return serialize_plan(load_plan(db, plan_id, current_user), db, current_user, character_id)


@router.put("/{plan_id}")
def update_plan(plan_id: int, payload: SkillPlanInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = load_plan(db, plan_id, current_user)
    if not can_manage_plan(current_user, row): raise HTTPException(status_code=403, detail="Only the plan owner may edit it")
    validate_character(payload.character_id, current_user, db)
    validate_plan_links(payload, current_user, db)
    row.name = payload.name; row.description = payload.description; row.notes = payload.notes; row.character_id = payload.character_id
    row.fitting_id = payload.fitting_id; row.source_doctrine_id = payload.source_doctrine_id; row.source = payload.source
    row.entries.clear(); row.entries.extend(validate_skill_entries(payload, db)); db.commit()
    return serialize_plan(load_plan(db, row.id, current_user), db, current_user)


@router.delete("/{plan_id}")
def archive_plan(plan_id: int, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = load_plan(db, plan_id, current_user)
    if not can_manage_plan(current_user, row): raise HTTPException(status_code=403, detail="Only the plan owner may archive it")
    row.archived_at = datetime.now(timezone.utc); db.commit(); return {"id": row.id, "archived": True}
