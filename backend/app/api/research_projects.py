from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import can_view_all_characters, get_current_user
from app.db.session import get_db
from app.models import Blueprint, EsiToken, EveCharacter, OwnershipEntity, ResearchProject, ResearchQueueItem, User
from app.services.asset_visibility import can_view_owner_records
from app.services.permissions import can_view_section
from app.services.research_projects import ACTIVE_RESEARCH_STATUSES, RESEARCH_ACTIVITY_NAMES
from app.services.research_queue import (
    clean_queue_activity,
    clean_queue_runs,
    clean_queue_status,
    clean_source_hangar,
    serialize_queue_item,
)

router = APIRouter(prefix="/research-projects", tags=["research-projects"])
RESEARCH_SCOPE = "esi-industry.read_character_jobs.v1"


def require_research_access(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not can_view_section(current_user, "industry", db):
        raise HTTPException(status_code=403, detail="industry section access is required")
    return current_user


def number(value: Any) -> float | None:
    return float(value) if value is not None else None


def serialize_project(project: ResearchProject) -> dict[str, Any]:
    character = project.character
    corporation = project.corporation
    return {
        "id": project.id,
        "job_id": project.job_id,
        "activity_id": project.activity_id,
        "activity_name": RESEARCH_ACTIVITY_NAMES.get(project.activity_id, f"Activity {project.activity_id}"),
        "status": project.status,
        "character_id": character.character_id if character else None,
        "installer_character_id": project.installer_character_id,
        "character_name": character.name if character else project.installer_name or f"Character {project.installer_character_id or 'unknown'}",
        "character_portrait_url": character.portrait_url if character else None,
        "source_type": project.source_type,
        "corporation_id": corporation.corporation_id if corporation else None,
        "corporation_name": corporation.name if corporation else None,
        "blueprint_type_id": project.blueprint_type_id,
        "blueprint_name": project.blueprint_type.name if project.blueprint_type else f"Blueprint type {project.blueprint_type_id}",
        "product_type_id": project.product_type_id,
        "product_name": project.product_type.name if project.product_type else None,
        "facility_id": project.facility_id,
        "facility_name": project.facility_name,
        "runs": project.runs,
        "licensed_runs": project.licensed_runs,
        "successful_runs": project.successful_runs,
        "probability": number(project.probability),
        "cost": number(project.cost),
        "duration": project.duration,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "end_date": project.end_date.isoformat() if project.end_date else None,
        "pause_date": project.pause_date.isoformat() if project.pause_date else None,
        "completed_date": project.completed_date.isoformat() if project.completed_date else None,
        "last_synced_at": project.last_synced_at.isoformat(),
    }


@router.get("")
def list_research_projects(
    include_history: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_research_access(current_user, db)
    query = (
        select(ResearchProject)
        .options(
            selectinload(ResearchProject.character),
            selectinload(ResearchProject.corporation),
            selectinload(ResearchProject.blueprint_type),
            selectinload(ResearchProject.product_type),
        )
        .order_by(ResearchProject.end_date.desc().nullslast(), ResearchProject.start_date.desc().nullslast())
    )
    if not include_history:
        query = query.where(ResearchProject.status.in_(ACTIVE_RESEARCH_STATUSES))
    projects = list(db.scalars(query).all())

    tokens = db.execute(
        select(EsiToken, EveCharacter)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.revoked_at.is_(None), EveCharacter.sync_opt_out.is_(False))
        .order_by(EveCharacter.name, EsiToken.created_at.desc())
    ).all()
    token_rows = []
    seen_characters: set[int] = set()
    for token, character in tokens:
        if character.id in seen_characters:
            continue
        seen_characters.add(character.id)
        scopes = set(token.scopes.split())
        token_rows.append({
            "token_id": token.id,
            "character_id": character.character_id,
            "character_name": character.name,
            "has_scope": RESEARCH_SCOPE in scopes,
            "has_corporation_scope": "esi-industry.read_corporation_jobs.v1" in scopes,
            "has_corporation_role_scope": "esi-characters.read_corporation_roles.v1" in scopes,
            "can_sync": token.user_id == current_user.id or can_view_all_characters(current_user, db),
        })

    active_projects = [project for project in projects if project.status in ACTIVE_RESEARCH_STATUSES]
    now = datetime.now(timezone.utc)
    return {
        "as_of": now.isoformat(),
        "summary": {
            "active": len(active_projects),
            "material_efficiency": sum(project.activity_id == 4 for project in active_projects),
            "time_efficiency": sum(project.activity_id == 3 for project in active_projects),
            "copying": sum(project.activity_id == 5 for project in active_projects),
            "invention": sum(project.activity_id == 8 for project in active_projects),
            "history": len(projects),
        },
        "sync_tokens": token_rows,
        "projects": [serialize_project(project) for project in projects],
    }

def owned_blueprint_query():
    return select(Blueprint).options(
        selectinload(Blueprint.ownership_entity).selectinload(OwnershipEntity.character),
        selectinload(Blueprint.blueprint_type),
        selectinload(Blueprint.location),
        selectinload(Blueprint.asset),
    )


def blueprint_option(blueprint: Blueprint) -> dict[str, Any]:
    return {
        "id": blueprint.id,
        "blueprint_type_id": blueprint.blueprint_type_id,
        "name": blueprint.blueprint_type.name if blueprint.blueprint_type else f"Blueprint type {blueprint.blueprint_type_id}",
        "kind": "BPC" if blueprint.is_copy else "BPO",
        "is_copy": blueprint.is_copy,
        "owner_name": blueprint.ownership_entity.display_name if blueprint.ownership_entity else "Unknown owner",
        "material_efficiency": blueprint.material_efficiency,
        "time_efficiency": blueprint.time_efficiency,
        "runs_remaining": blueprint.runs_remaining,
        "source_location_name": blueprint.location.name if blueprint.location else None,
        "source_hangar": blueprint.asset.location_flag if blueprint.asset else None,
    }


@router.get("/queue")
def list_research_queue(
    _: User = Depends(require_research_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items = list(db.scalars(select(ResearchQueueItem).order_by(ResearchQueueItem.sort_order, ResearchQueueItem.id)).all())
    items.sort(key=lambda item: (item.status == "completed", item.sort_order, item.id))
    return {
        "summary": {
            "pending": sum(item.status == "pending" for item in items),
            "completed": sum(item.status == "completed" for item in items),
        },
        "items": [serialize_queue_item(item) for item in items],
    }


@router.get("/queue/blueprints")
def search_research_queue_blueprints(
    q: str = Query("", max_length=255),
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(require_research_access),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = list(db.scalars(owned_blueprint_query().order_by(Blueprint.id.desc())).all())
    visible = [row for row in rows if can_view_owner_records(row.ownership_entity, current_user, db)]
    needle = q.strip().casefold()
    if needle:
        visible = [
            row for row in visible
            if needle in (row.blueprint_type.name if row.blueprint_type else "").casefold()
            or needle in (row.ownership_entity.display_name if row.ownership_entity else "").casefold()
            or needle in (row.location.name if row.location else "").casefold()
        ]
    visible.sort(key=lambda row: (
        (row.blueprint_type.name if row.blueprint_type else "").casefold(),
        row.is_copy,
        (row.ownership_entity.display_name if row.ownership_entity else "").casefold(),
        row.id,
    ))
    return [blueprint_option(row) for row in visible[:limit]]


@router.post("/queue")
def create_research_queue_item(
    payload: dict[str, Any],
    current_user: User = Depends(require_research_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        blueprint_id = int(payload.get("blueprint_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="An owned BPO or BPC is required") from None
    blueprint = db.scalar(owned_blueprint_query().where(Blueprint.id == blueprint_id))
    if blueprint is None or not can_view_owner_records(blueprint.ownership_entity, current_user, db):
        raise HTTPException(status_code=404, detail="That owned blueprint was not found")
    current_items = list(db.scalars(select(ResearchQueueItem).where(ResearchQueueItem.status == "pending")).all())
    item = ResearchQueueItem(
        blueprint_id=blueprint.id,
        blueprint_type_id=blueprint.blueprint_type_id,
        blueprint_name=blueprint.blueprint_type.name if blueprint.blueprint_type else f"Blueprint type {blueprint.blueprint_type_id}",
        blueprint_kind="BPC" if blueprint.is_copy else "BPO",
        owner_name=blueprint.ownership_entity.display_name if blueprint.ownership_entity else None,
        material_efficiency=blueprint.material_efficiency,
        time_efficiency=blueprint.time_efficiency,
        runs_remaining=blueprint.runs_remaining,
        source_location_name=blueprint.location.name if blueprint.location else None,
        source_hangar=clean_source_hangar(payload.get("source_hangar") or (blueprint.asset.location_flag if blueprint.asset else None)),
        activity_id=clean_queue_activity(payload.get("activity_id"), blueprint.is_copy),
        runs=clean_queue_runs(payload.get("runs", 1)),
        status="pending",
        sort_order=max((row.sort_order for row in current_items), default=-1) + 1,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize_queue_item(item)


@router.post("/queue/reorder")
def reorder_research_queue(
    payload: dict[str, Any],
    _: User = Depends(require_research_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item_ids = [int(value) for value in payload.get("item_ids", [])]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="item_ids must contain integers") from None
    if len(item_ids) != len(set(item_ids)):
        raise HTTPException(status_code=400, detail="Queue order contains duplicate entries")
    items = list(db.scalars(select(ResearchQueueItem).where(ResearchQueueItem.id.in_(item_ids))).all()) if item_ids else []
    if len(items) != len(item_ids) or any(item.status != "pending" for item in items):
        raise HTTPException(status_code=400, detail="Only existing pending entries can be reordered")
    by_id = {item.id: item for item in items}
    for index, item_id in enumerate(item_ids):
        by_id[item_id].sort_order = index
    db.commit()
    return {"status": "reordered", "item_ids": item_ids}


@router.patch("/queue/{queue_id}")
def update_research_queue_item(
    queue_id: int,
    payload: dict[str, Any],
    _: User = Depends(require_research_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.get(ResearchQueueItem, queue_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Research queue entry not found")
    if "activity_id" in payload:
        item.activity_id = clean_queue_activity(payload.get("activity_id"), item.blueprint_kind == "BPC")
    if "runs" in payload:
        item.runs = clean_queue_runs(payload.get("runs"))
    if "source_hangar" in payload:
        item.source_hangar = clean_source_hangar(payload.get("source_hangar"))
    if "status" in payload:
        item.status = clean_queue_status(payload.get("status"))
        item.completed_at = datetime.now(timezone.utc) if item.status == "completed" else None
    db.commit()
    db.refresh(item)
    return serialize_queue_item(item)


@router.delete("/queue/{queue_id}")
def delete_research_queue_item(
    queue_id: int,
    _: User = Depends(require_research_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    item = db.get(ResearchQueueItem, queue_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Research queue entry not found")
    db.delete(item)
    db.commit()
    return {"status": "deleted", "id": queue_id}
