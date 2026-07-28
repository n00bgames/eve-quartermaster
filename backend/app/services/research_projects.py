from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models import EsiToken, EveCharacter, EveStation, EveSystem, Location, ResearchProject
from app.services.analytics import analytics_corporation_ids
from app.services.esi_client import EsiClient

RESEARCH_ACTIVITY_NAMES = {
    3: "Time Efficiency",
    4: "Material Efficiency",
    5: "Copying",
    8: "Invention",
}
ACTIVE_RESEARCH_STATUSES = {"active", "paused", "ready"}
MAX_POSTGRES_INTEGER = 2_147_483_647


def visible_research_project_filter(db: Session):
    """Keep linked-character jobs visible while limiting broader corporation queues."""
    included_corporation_ids = analytics_corporation_ids(db)
    linked_installer = exists(
        select(EsiToken.id)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(
            EsiToken.revoked_at.is_(None),
            EveCharacter.sync_opt_out.is_(False),
            or_(
                EsiToken.character_id == ResearchProject.character_id,
                EveCharacter.character_id == ResearchProject.installer_character_id,
            ),
        )
    )
    clauses = [
        ResearchProject.source_type != "corporation",
        linked_installer,
    ]
    if included_corporation_ids:
        clauses.append(ResearchProject.corporation_id.in_(included_corporation_ids))
    return or_(*clauses)


def active_sso_character_eve_ids(db: Session) -> set[int]:
    return set(
        db.scalars(
            select(EveCharacter.character_id)
            .join(EsiToken, EsiToken.character_id == EveCharacter.id)
            .where(
                EsiToken.revoked_at.is_(None),
                EveCharacter.sync_opt_out.is_(False),
            )
            .distinct()
        ).all()
    )


def scoped_corporation_research_rows(
    db: Session,
    corporation_id: int,
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Limit excluded corporation feeds to jobs installed by linked characters."""
    if corporation_id in analytics_corporation_ids(db):
        return rows, False
    linked_installer_ids = active_sso_character_eve_ids(db)
    return [
        row
        for row in rows
        if int(row.get("installer_id") or 0) in linked_installer_ids
    ], True


def parse_esi_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def research_location_name(db: Session, location_id: int | None) -> str | None:
    if location_id is None:
        return None
    location = db.scalar(select(Location).where(Location.eve_location_id == location_id).limit(1))
    if location:
        return location.name
    if location_id <= MAX_POSTGRES_INTEGER:
        station = db.get(EveStation, location_id)
        if station:
            return station.name
        system = db.get(EveSystem, location_id)
        if system:
            return system.name
    return f"Structure {location_id}" if location_id > MAX_POSTGRES_INTEGER else f"Location {location_id}"


async def fetch_character_industry_jobs(client: EsiClient, character_id: int) -> list[dict[str, Any]]:
    payload = await client.get(
        f"/characters/{character_id}/industry/jobs/",
        params={"include_completed": "true"},
    )
    return list(payload or [])


async def fetch_corporation_industry_jobs(client: EsiClient, corporation_id: int) -> list[dict[str, Any]]:
    payload = await client.get(
        f"/corporations/{corporation_id}/industry/jobs/",
        params={"include_completed": "true"},
    )
    return list(payload or [])


async def resolve_installer_names(client: EsiClient, rows: list[dict[str, Any]]) -> dict[int, str]:
    installer_ids = sorted({int(row["installer_id"]) for row in rows if row.get("installer_id")})
    if not installer_ids:
        return {}
    names: dict[int, str] = {}
    for offset in range(0, len(installer_ids), 1000):
        payload = await client.post("/universe/names/", installer_ids[offset:offset + 1000])
        names.update({
            int(row["id"]): str(row["name"])
            for row in (payload or [])
            if row.get("category") == "character" and row.get("id") and row.get("name")
        })
    return names


def upsert_research_projects(
    db: Session,
    character_id: int | None,
    rows: list[dict[str, Any]],
    *,
    corporation_id: int | None = None,
    source_type: str = "character",
    installer_names: dict[int, str] | None = None,
) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    installer_names = installer_names or {}
    synced = 0
    active = 0
    for row in rows:
        activity_id = int(row.get("activity_id") or 0)
        if activity_id not in RESEARCH_ACTIVITY_NAMES:
            continue
        job_id = int(row["job_id"])
        project = db.scalar(select(ResearchProject).where(ResearchProject.job_id == job_id))
        installer_character_id = int(row["installer_id"]) if row.get("installer_id") else None
        linked_installer = db.scalar(
            select(EveCharacter).where(EveCharacter.character_id == installer_character_id)
        ) if installer_character_id is not None else None
        linked_character_id = linked_installer.id if linked_installer else character_id
        if source_type == "corporation" and linked_installer is None:
            linked_character_id = None
        if project is None:
            project = ResearchProject(
                job_id=job_id,
                character_id=linked_character_id,
                corporation_id=corporation_id,
                source_type=source_type,
                activity_id=activity_id,
                status="active",
                last_synced_at=now,
            )
            db.add(project)

        facility_id = row.get("facility_id") or row.get("station_id")
        project.character_id = linked_character_id
        if source_type == "corporation" or project.source_type != "corporation":
            project.corporation_id = corporation_id
            project.source_type = source_type
        project.installer_character_id = installer_character_id
        project.installer_name = (
            linked_installer.name if linked_installer else installer_names.get(installer_character_id)
        )
        project.completed_character_id = row.get("completed_character_id")
        project.activity_id = activity_id
        project.blueprint_id = row.get("blueprint_id")
        project.blueprint_type_id = row.get("blueprint_type_id")
        project.product_type_id = row.get("product_type_id")
        project.facility_id = facility_id
        project.station_id = row.get("station_id")
        project.facility_name = research_location_name(db, int(facility_id)) if facility_id is not None else None
        project.status = str(row.get("status") or "active")
        project.runs = int(row.get("runs") or 1)
        project.licensed_runs = row.get("licensed_runs")
        project.successful_runs = row.get("successful_runs")
        project.probability = decimal_or_none(row.get("probability"))
        project.cost = decimal_or_none(row.get("cost"))
        project.duration = row.get("duration")
        project.start_date = parse_esi_datetime(row.get("start_date"))
        project.end_date = parse_esi_datetime(row.get("end_date"))
        project.pause_date = parse_esi_datetime(row.get("pause_date"))
        project.completed_date = parse_esi_datetime(row.get("completed_date"))
        project.last_synced_at = now
        synced += 1
        if project.status in ACTIVE_RESEARCH_STATUSES:
            active += 1
    return synced, active