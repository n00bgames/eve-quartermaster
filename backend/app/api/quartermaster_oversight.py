"""Read-only organizational blueprints, active jobs and planetary infrastructure."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload
from app.api.auth import get_current_user
from app.api.quartermaster import blueprint_rows
from app.api.research_projects import serialize_project
from app.api.planetary_industry import serialize_colony
from app.db.session import get_db
from app.models import Asset, Blueprint, EveCharacter, PlanetaryColony, PlanetaryPin, ResearchProject, User
from app.models.enums import OwnerKind
from app.services.blueprint_hover import INDUSTRY_ACTIVITY_NAMES, project_blueprint_metadata
from app.services.permissions import can_view_section
from app.services.quartermaster_access import oversight_scope
from app.services.research_projects import ACTIVE_RESEARCH_STATUSES

router = APIRouter(prefix="/quartermaster-oversight", tags=["quartermaster-oversight"])


def access(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not can_view_section(user, "quartermaster", db):
        raise HTTPException(403, "Quartermaster section access is required")
    response.headers["Cache-Control"] = "private, no-store"
    return user


@router.get("")
async def overview(user: User = Depends(access), db: Session = Depends(get_db)):
    scope = await oversight_scope(db)

    def owner_visible(owner):
        if owner is None:
            return False
        if owner.owner_kind == OwnerKind.CHARACTER:
            return owner.character_id in scope.characters["blueprints"]
        return owner.owner_kind == OwnerKind.CORPORATION and owner.corporation_id in scope.corporations["blueprints"]

    blueprints = blueprint_rows(user, db, owner_filter=owner_visible)
    # Preserve stacked original quantities, with one item per copy/shadow.
    quantities = dict(db.execute(select(Blueprint.id, Asset.quantity).join(Asset, Asset.id == Blueprint.asset_id)).all())
    for row in blueprints:
        row["quantity"] = max(1, quantities.get(row["id"]) or 1)
    installer_ids = select(EveCharacter.character_id).where(EveCharacter.id.in_(scope.characters["jobs"]))
    projects = list(db.scalars(select(ResearchProject).where(
        ResearchProject.status.in_(ACTIVE_RESEARCH_STATUSES),
        or_(ResearchProject.character_id.in_(scope.characters["jobs"]),
            ResearchProject.installer_character_id.in_(installer_ids),
            and_(ResearchProject.source_type == "corporation", ResearchProject.corporation_id.in_(scope.corporations["jobs"]))),
    ).options(selectinload(ResearchProject.character), selectinload(ResearchProject.corporation),
              selectinload(ResearchProject.blueprint_type), selectinload(ResearchProject.product_type))
      .order_by(ResearchProject.end_date.asc().nullslast(), ResearchProject.id)).all())
    metadata = project_blueprint_metadata(db, projects)
    jobs = [{**serialize_project(row, metadata.get(row.id)), "activity_name": INDUSTRY_ACTIVITY_NAMES.get(row.activity_id, f"Activity {row.activity_id}")} for row in projects]
    colonies = db.scalars(select(PlanetaryColony).where(
        PlanetaryColony.character_id.in_(scope.characters["planets"])
    ).options(selectinload(PlanetaryColony.character), selectinload(PlanetaryColony.system),
              selectinload(PlanetaryColony.pins).selectinload(PlanetaryPin.pin_type),
              selectinload(PlanetaryColony.links), selectinload(PlanetaryColony.routes))
      .order_by(PlanetaryColony.planet_name)).all()
    planets = []
    for colony in colonies:
        payload = serialize_colony(db, colony)
        payload["links"] = [{"source_pin_id": row.source_pin_id, "destination_pin_id": row.destination_pin_id,
                             "link_level": row.link_level} for row in colony.links]
        planets.append(payload)
    return {
        "as_of": datetime.now(timezone.utc).isoformat(), "read_only": True,
        "notice": "Cached ESI records for authenticated characters and verified corporate feeds. Missing scopes, revoked authorizations, deleted owners and opted-out characters are excluded. PI belongs to characters, not corporations. Projections are estimates from the shown ESI checkpoint.",
        "warnings": sorted(set(scope.warnings)),
        "summary": {"bpo": sum(row["quantity"] for row in blueprints if not row["is_copy"]),
                    "bpc": sum(row["quantity"] for row in blueprints if row["is_copy"]), "active_jobs": len(jobs), "colonies": len(planets)},
        "blueprints": blueprints, "jobs": jobs, "colonies": planets,
    }


@router.post("/sync", status_code=202)
def start_sync(user: User = Depends(access), db: Session = Depends(get_db)):
    from app.services.quartermaster_sync import enqueue, payload, schedule
    job = enqueue(db, user)
    schedule(job["job_id"])
    return payload(job)


@router.get("/sync")
def latest_sync(user: User = Depends(access)):
    from app.services.quartermaster_sync import JOBS, payload
    latest = next((job for job in reversed(list(JOBS.values())) if job["user_id"] == user.id), None)
    return payload(latest) if latest else None


@router.get("/sync/{job_id}")
def sync_status(job_id: str, user: User = Depends(access)):
    from app.services.quartermaster_sync import JOBS, payload
    job = JOBS.get(job_id)
    if job is None or job["user_id"] != user.id:
        raise HTTPException(404, "Quartermaster sync job is unavailable; refresh the view to inspect completed records")
    return payload(job)
