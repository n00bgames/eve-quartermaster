from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, Blueprint, BlueprintSnapshot, ResearchProject
from app.services.research_projects import ACTIVE_RESEARCH_STATUSES, RESEARCH_ACTIVITY_NAMES


INDUSTRY_ACTIVITY_NAMES = {
    1: "Manufacturing",
    3: "Time Efficiency",
    4: "Material Efficiency",
    5: "Copying",
    7: "Reverse Engineering",
    8: "Invention",
    9: "Reactions",
}


def research_use_payload(project: ResearchProject) -> dict[str, Any]:
    return {
        "active": project.status in ACTIVE_RESEARCH_STATUSES,
        "activity": INDUSTRY_ACTIVITY_NAMES.get(project.activity_id, RESEARCH_ACTIVITY_NAMES.get(project.activity_id, f"Industry activity {project.activity_id}")),
        "status": project.status,
        "job_id": project.job_id,
        "runs": project.runs,
        "facility": project.facility_name,
        "installer": project.character.name if project.character else project.installer_name,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "end_date": project.end_date.isoformat() if project.end_date else None,
    }


def active_blueprint_uses(db: Session, blueprints: Iterable[Blueprint]) -> dict[int, dict[str, Any]]:
    item_ids = {
        int(blueprint.asset.eve_item_id)
        for blueprint in blueprints
        if blueprint.asset is not None and blueprint.asset.eve_item_id is not None
    }
    if not item_ids:
        return {}
    projects = db.scalars(
        select(ResearchProject)
        .options(selectinload(ResearchProject.character))
        .where(
            ResearchProject.blueprint_id.in_(item_ids),
            ResearchProject.status.in_(ACTIVE_RESEARCH_STATUSES),
        )
        .order_by(ResearchProject.end_date.desc().nullslast(), ResearchProject.id.desc())
    ).all()
    uses: dict[int, dict[str, Any]] = {}
    for project in projects:
        if project.blueprint_id is not None:
            uses.setdefault(int(project.blueprint_id), research_use_payload(project))
    return uses


def blueprint_active_use(blueprint: Blueprint, uses: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    if blueprint.asset is None or blueprint.asset.eve_item_id is None:
        return None
    return uses.get(int(blueprint.asset.eve_item_id))


def project_blueprint_metadata(db: Session, projects: Iterable[ResearchProject]) -> dict[int, dict[str, Any]]:
    project_rows = list(projects)
    item_ids = {int(project.blueprint_id) for project in project_rows if project.blueprint_id is not None}
    current_by_item: dict[int, Blueprint] = {}
    prior_by_item: dict[int, BlueprintSnapshot] = {}
    if item_ids:
        current = db.scalars(
            select(Blueprint)
            .join(Asset, Asset.id == Blueprint.asset_id)
            .options(selectinload(Blueprint.asset), selectinload(Blueprint.location))
            .where(Asset.eve_item_id.in_(item_ids))
        ).all()
        current_by_item = {
            int(blueprint.asset.eve_item_id): blueprint
            for blueprint in current
            if blueprint.asset is not None and blueprint.asset.eve_item_id is not None
        }
        prior_rows = db.scalars(
            select(BlueprintSnapshot)
            .where(BlueprintSnapshot.blueprint_item_id.in_(item_ids))
            .order_by(BlueprintSnapshot.snapshot_run_id.desc(), BlueprintSnapshot.id.desc())
        ).all()
        for row in prior_rows:
            if row.blueprint_item_id is not None:
                prior_by_item.setdefault(int(row.blueprint_item_id), row)

    result: dict[int, dict[str, Any]] = {}
    for project in project_rows:
        item_id = int(project.blueprint_id) if project.blueprint_id is not None else None
        current = current_by_item.get(item_id) if item_id is not None else None
        prior = prior_by_item.get(item_id) if item_id is not None else None
        result[project.id] = {
            "material_efficiency": int(current.material_efficiency) if current else int(prior.material_efficiency) if prior else None,
            "time_efficiency": int(current.time_efficiency) if current else int(prior.time_efficiency) if prior else None,
            "runs_remaining": current.runs_remaining if current else prior.runs_remaining if prior else None,
            "is_copy": bool(current.is_copy) if current else bool(prior.is_copy) if prior else None,
            "blueprint_location_name": current.location.name if current and current.location else project.facility_name,
        }
    return result
