from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import can_view_all_characters, get_current_user
from app.db.session import get_db
from app.models import EsiToken, EveCharacter, ResearchProject, User
from app.services.permissions import can_view_section
from app.services.research_projects import ACTIVE_RESEARCH_STATUSES, RESEARCH_ACTIVITY_NAMES

router = APIRouter(prefix="/research-projects", tags=["research-projects"])
RESEARCH_SCOPE = "esi-industry.read_character_jobs.v1"


def require_research_access(current_user: User, db: Session) -> None:
    if not can_view_section(current_user, "industry", db):
        raise HTTPException(status_code=403, detail="industry section access is required")


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