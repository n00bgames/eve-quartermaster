from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user, require_role
from app.db.session import get_db
from app.models import BlueprintSnapshot, CharacterSkillSnapshot, CorporationSnapshot, EveCharacter, EveCorporation, ManufacturingJob, MiningLedgerEntry, OwnershipEntity, ResearchProject, SnapshotMetric, SnapshotRun, User
from app.services.analytics import (
    RETENTION_MODE_CHANGES,
    RETENTION_MODE_FULL,
    analytics_corporation_ids,
    analytics_retention_mode,
    create_snapshot,
    privileged_analytics_corporation_ids,
    scoped_blueprint_records,
    set_analytics_retention_mode,
)
from app.services.audit import record_audit_event
from app.services.metric_registry import METRIC_CATALOG
from app.services.permissions import ROLE_RANK, can_view_section, role_rank
from app.services.research_projects import RESEARCH_ACTIVITY_NAMES

router = APIRouter(prefix="/analytics", tags=["analytics"])


def retention_settings_payload(db: Session, current_user: User) -> dict[str, Any]:
    return {
        "mode": analytics_retention_mode(db),
        "can_manage": role_rank(current_user, db) >= ROLE_RANK["host"],
        "modes": [
            {
                "key": RETENTION_MODE_CHANGES,
                "label": "Changes + Daily Checkpoints",
                "description": "Stores changes plus periodic state snapshots. Much lower storage use while retaining historical reconstruction; removed blueprint series are recorded as zero.",
            },
            {
                "key": RETENTION_MODE_FULL,
                "label": "Full History",
                "description": "Stores every collected observation after normal one-hour scope/source coalescing. Highest storage use; maximum forensic detail.",
            },
        ],
        "note": "The selection affects future observations only. Existing history is not deleted or rewritten.",
    }
def require_analytics(current_user: User, db: Session) -> None:
    if not can_view_section(current_user, "analytics", db):
        raise HTTPException(status_code=403, detail="analytics section access is required")


def as_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def start_cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 3660)))


def manufacturing_analytics(db: Session, days: int) -> dict[str, Any]:
    cutoff = start_cutoff(days)
    jobs = db.scalars(
        select(ManufacturingJob)
        .options(selectinload(ManufacturingJob.output_type), selectinload(ManufacturingJob.items))
        .where(
            or_(
                ManufacturingJob.date_started >= cutoff.date(),
                and_(ManufacturingJob.date_started.is_(None), ManufacturingJob.created_at >= cutoff),
            )
        )
    ).all()
    totals: dict[str, float | int] = {
        "job_count": 0,
        "items_built": 0,
        "current_cost": 0.0,
        "actual_cost": 0.0,
        "savings": 0.0,
        "kept_items": 0,
        "sold_items": 0,
        "sales_revenue": 0.0,
        "realized_profit": 0.0,
    }
    by_item: dict[str, dict[str, float | int | str]] = {}

    for job in jobs:
        activity_flags = {flag.strip() for flag in str(job.activity_flags or "manufacturing").split(",") if flag.strip()}
        is_realized = job.status == "completed" or job.output_disposition in {"kept", "sold"}
        if "manufacturing" not in activity_flags or not is_realized:
            continue

        quantity = max(0, int(job.output_quantity or 0))
        run_cost = as_float(job.cost_to_run)
        current_cost = run_cost + sum(as_float(item.quantity) * as_float(item.unit_price) for item in job.items)
        actual_cost = run_cost + sum(as_float(item.quantity) * as_float(item.price_paid) for item in job.items)
        savings = current_cost - actual_cost
        sale_revenue = as_float(job.output_sale_price) if job.output_disposition == "sold" else 0.0
        profit = sale_revenue - actual_cost if job.output_disposition == "sold" else 0.0
        item_name = job.output_type.name if job.output_type else job.name
        item = by_item.setdefault(item_name, {
            "name": item_name,
            "quantity": 0,
            "actual_cost": 0.0,
            "savings": 0.0,
            "kept_quantity": 0,
            "sold_quantity": 0,
            "sales_revenue": 0.0,
            "realized_profit": 0.0,
        })

        totals["job_count"] += 1
        totals["items_built"] += quantity
        totals["current_cost"] += current_cost
        totals["actual_cost"] += actual_cost
        totals["savings"] += savings
        item["quantity"] += quantity
        item["actual_cost"] += actual_cost
        item["savings"] += savings

        if job.output_disposition == "kept":
            totals["kept_items"] += quantity
            item["kept_quantity"] += quantity
        elif job.output_disposition == "sold":
            totals["sold_items"] += quantity
            totals["sales_revenue"] += sale_revenue
            totals["realized_profit"] += profit
            item["sold_quantity"] += quantity
            item["sales_revenue"] += sale_revenue
            item["realized_profit"] += profit

    money_fields = ["current_cost", "actual_cost", "savings", "sales_revenue", "realized_profit"]
    for field in money_fields:
        totals[field] = round(float(totals[field]), 2)
    top_items = sorted(by_item.values(), key=lambda row: (-int(row["quantity"]), str(row["name"]).lower()))[:8]
    for item in top_items:
        for field in ["actual_cost", "savings", "sales_revenue", "realized_profit"]:
            item[field] = round(float(item[field]), 2)
    return {**totals, "top_items": top_items}


def mining_analytics(db: Session, days: int, character_ids: set[int] | None) -> dict[str, Any]:
    query = (
        select(MiningLedgerEntry)
        .options(selectinload(MiningLedgerEntry.character))
        .where(MiningLedgerEntry.mined_date >= start_cutoff(days).date())
    )
    if character_ids is not None:
        if not character_ids:
            return {"entry_count": 0, "recovered_volume": 0, "residue_volume": 0, "gross_volume": 0, "net_value": 0, "efficiency": None, "measured_volume": 0, "top_by_volume": [], "top_by_efficiency": []}
        query = query.where(MiningLedgerEntry.character_id.in_(character_ids))
    entries = db.scalars(query).all()
    by_character: dict[str, dict[str, float]] = {}
    recovered = residue = net_value = measured_recovered = measured_residue = 0.0
    for entry in entries:
        volume = as_float(entry.volume)
        residue_volume = as_float(entry.residue_volume)
        recovered += volume
        residue += residue_volume
        net_value += as_float(entry.estimated_price)
        row = by_character.setdefault(entry.character.name, {"volume": 0.0, "measured_recovered": 0.0, "measured_residue": 0.0})
        row["volume"] += volume
        if entry.has_residue_data:
            measured_recovered += volume
            measured_residue += residue_volume
            row["measured_recovered"] += volume
            row["measured_residue"] += residue_volume
    measured_gross = measured_recovered + measured_residue
    volume_rows = [{"name": name, "volume": round(values["volume"], 2)} for name, values in by_character.items()]
    efficiency_rows = [
        {"name": name, "efficiency": round(values["measured_recovered"] / (values["measured_recovered"] + values["measured_residue"]) * 100, 2)}
        for name, values in by_character.items()
        if values["measured_recovered"] + values["measured_residue"] > 0
    ]
    return {
        "entry_count": len(entries), "recovered_volume": round(recovered, 2), "residue_volume": round(residue, 2),
        "gross_volume": round(recovered + residue, 2), "net_value": round(net_value, 2),
        "efficiency": round(measured_recovered / measured_gross * 100, 2) if measured_gross else None,
        "measured_volume": round(measured_gross, 2),
        "top_by_volume": sorted(volume_rows, key=lambda row: (-row["volume"], row["name"]))[:8],
        "top_by_efficiency": sorted(efficiency_rows, key=lambda row: (-row["efficiency"], row["name"]))[:8],
    }

def research_project_analytics(db: Session, days: int, character_ids: set[int] | None) -> dict[str, Any]:
    cutoff = start_cutoff(days)
    query = select(ResearchProject).options(
        selectinload(ResearchProject.character),
        selectinload(ResearchProject.corporation),
    ).where(
        or_(ResearchProject.start_date >= cutoff, ResearchProject.status.in_({"active", "paused", "ready"}))
    )
    included_corporations = analytics_corporation_ids(db)
    query = query.where(
        or_(ResearchProject.corporation_id.is_(None), ResearchProject.corporation_id.in_(included_corporations))
    )
    if character_ids is not None:
        if not character_ids:
            return {"project_count": 0, "active_count": 0, "completed_count": 0, "by_activity": [], "by_character": []}
        query = query.where(ResearchProject.character_id.in_(character_ids))
    projects = db.scalars(query).all()
    active_statuses = {"active", "paused", "ready"}
    by_activity: dict[str, int] = {}
    by_character: dict[str, int] = {}
    for project in projects:
        activity = RESEARCH_ACTIVITY_NAMES.get(project.activity_id, f"Activity {project.activity_id}")
        character = project.character.name if project.character else project.installer_name or f"Character {project.installer_character_id or 'unknown'}"
        by_activity[activity] = by_activity.get(activity, 0) + 1
        by_character[character] = by_character.get(character, 0) + 1
    return {
        "project_count": len(projects),
        "active_count": sum(project.status in active_statuses for project in projects),
        "completed_count": sum(project.status == "delivered" for project in projects),
        "by_activity": [{"name": name, "count": count} for name, count in sorted(by_activity.items(), key=lambda item: (-item[1], item[0]))],
        "by_character": [{"name": name, "count": count} for name, count in sorted(by_character.items(), key=lambda item: (-item[1], item[0]))[:8]],
    }

def can_view_character_analytics(viewer: User, character: EveCharacter, db: Session) -> bool:
    viewer_rank = role_rank(viewer, db)
    if viewer_rank >= ROLE_RANK["director"]:
        return True
    if character.owner_user_id == viewer.id:
        return True
    if viewer_rank >= ROLE_RANK["officer"] and character.owner_user and role_rank(character.owner_user, db) < ROLE_RANK["officer"]:
        return True
    return False


def visible_character_ids(current_user: User, db: Session) -> set[int] | None:
    if role_rank(current_user, db) >= ROLE_RANK["director"]:
        return None
    characters = db.scalars(select(EveCharacter).options(selectinload(EveCharacter.owner_user))).all()
    return {character.id for character in characters if can_view_character_analytics(current_user, character, db)}



def visible_corporation_ids(current_user: User, db: Session, character_ids: set[int] | None) -> set[int]:
    included_ids = analytics_corporation_ids(db)
    if role_rank(current_user, db) >= ROLE_RANK["officer"]:
        return included_ids
    if not character_ids:
        return set()
    affiliated_ids = {
        row[0]
        for row in db.execute(
            select(EveCharacter.corporation_id)
            .where(EveCharacter.id.in_(character_ids), EveCharacter.corporation_id.is_not(None))
            .distinct()
        ).all()
        if row[0] is not None
    }
    return affiliated_ids & included_ids


def can_view_owner_analytics(viewer: User, owner: OwnershipEntity, db: Session) -> bool:
    if role_rank(viewer, db) >= ROLE_RANK["officer"]:
        return True
    if owner.character and can_view_character_analytics(viewer, owner.character, db):
        return True
    if owner.character and owner.character.public_assets_visible and not owner.character.sync_opt_out:
        return True
    return False


def visible_ownership_entity_ids(current_user: User, db: Session) -> set[int]:
    corporation_ids = analytics_corporation_ids(db)
    owners = db.scalars(
        select(OwnershipEntity).options(
            selectinload(OwnershipEntity.character).selectinload(EveCharacter.owner_user),
            selectinload(OwnershipEntity.corporation),
        )
    ).all()
    return {
        owner.id
        for owner in owners
        if can_view_owner_analytics(current_user, owner, db)
        and not (owner.corporation and owner.corporation.id not in corporation_ids)
    }


@router.get("/corporations")
def analytics_corporations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_analytics(current_user, db)
    snapshot_ids = set(db.scalars(select(CorporationSnapshot.corporation_id).distinct()).all())
    affiliation_ids = set(
        db.scalars(select(EveCharacter.corporation_id).where(EveCharacter.corporation_id.is_not(None)).distinct()).all()
    )
    managed_ids = privileged_analytics_corporation_ids(db)
    candidate_ids = snapshot_ids | affiliation_ids | managed_ids
    corporations = db.scalars(
        select(EveCorporation).where(EveCorporation.id.in_(candidate_ids)).order_by(EveCorporation.name)
    ).all() if candidate_ids else []
    return {
        "can_manage": role_rank(current_user, db) >= ROLE_RANK["director"],
        "corporations": [
            {
                "id": corporation.id,
                "name": corporation.name,
                "ticker": corporation.ticker,
                "hidden": corporation.hide_from_corporation_list,
                "excluded": corporation.exclude_from_analytics or corporation.hide_from_corporation_list or corporation.id not in managed_ids,
                "managed": corporation.id in managed_ids,
                "affiliation": corporation.id in affiliation_ids,
                "historical": corporation.id in snapshot_ids,
                "wallet_totals_visible": corporation.character_wallet_totals_visible,
            }
            for corporation in corporations
        ],
    }


@router.get("/retention")
def analytics_retention_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_analytics(current_user, db)
    return retention_settings_payload(db, current_user)


@router.patch("/retention")
def update_analytics_retention_settings(
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_analytics(current_user, db)
    require_role(current_user, "host", db)
    mode = str(payload.get("mode", "")).strip().lower()
    if mode not in {RETENTION_MODE_FULL, RETENTION_MODE_CHANGES}:
        raise HTTPException(status_code=400, detail="mode must be full or changes")
    previous = analytics_retention_mode(db)
    set_analytics_retention_mode(db, mode)
    record_audit_event(
        db,
        event_kind="analytics_retention_mode_changed",
        title="Analytics retention mode changed",
        body=f"{previous} -> {mode}. Existing analytics history was preserved.",
        actor_user=current_user,
    )
    db.commit()
    return retention_settings_payload(db, current_user)


@router.patch("/corporations/{corporation_id}")
def update_analytics_corporation(
    corporation_id: int,
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_analytics(current_user, db)
    if role_rank(current_user, db) < ROLE_RANK["director"]:
        raise HTTPException(status_code=403, detail="director role is required")
    corporation = db.get(EveCorporation, corporation_id)
    if corporation is None:
        raise HTTPException(status_code=404, detail="Corporation was not found")
    if "excluded" not in payload and "wallet_totals_visible" not in payload:
        raise HTTPException(status_code=400, detail="excluded or wallet_totals_visible is required")
    if "excluded" in payload:
        excluded = bool(payload["excluded"])
        if corporation.hide_from_corporation_list and not excluded:
            raise HTTPException(status_code=400, detail="Hidden corporations remain excluded from analytics")
        if not excluded and corporation.id not in privileged_analytics_corporation_ids(db):
            raise HTTPException(status_code=400, detail="A successful corporation-level ESI sync is required before this corporation can be included in analytics")
        corporation.exclude_from_analytics = excluded
    if "wallet_totals_visible" in payload:
        corporation.character_wallet_totals_visible = bool(payload["wallet_totals_visible"])
    db.commit()
    return {
        "id": corporation.id,
        "name": corporation.name,
        "excluded": corporation.exclude_from_analytics,
        "wallet_totals_visible": corporation.character_wallet_totals_visible,
    }

@router.post("/snapshot")
def manual_snapshot(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_analytics(current_user, db)
    run = create_snapshot(db, scope_type="global", source="manual", message=f"Manual snapshot by {current_user.display_name}")
    db.commit()
    db.refresh(run)
    return {"status": run.status, "snapshot_run_id": run.id, "completed_at": iso(run.completed_at)}


@router.delete("/snapshots")
def clear_snapshots(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_analytics(current_user, db)
    require_role(current_user, "admin", db)
    deleted_count = db.scalar(select(func.count()).select_from(SnapshotRun)) or 0
    db.execute(delete(SnapshotRun))
    db.commit()
    return {"status": "cleared", "deleted_snapshot_runs": deleted_count}


def legacy_snapshot_candidate_ids():
    daily_keepers = (
        select(func.max(SnapshotRun.id).label("id"))
        .where(
            SnapshotRun.schema_version == 1,
            SnapshotRun.source != "manual",
            SnapshotRun.status == "success",
        )
        .group_by(func.date(SnapshotRun.started_at))
        .subquery()
    )
    return select(SnapshotRun.id).where(
        SnapshotRun.schema_version == 1,
        SnapshotRun.source != "manual",
        SnapshotRun.id.not_in(select(daily_keepers.c.id)),
    )


def legacy_snapshot_compaction_preview(db: Session) -> dict[str, int]:
    candidate_ids = legacy_snapshot_candidate_ids()
    return {
        "snapshot_runs": int(db.scalar(select(func.count()).select_from(SnapshotRun).where(SnapshotRun.id.in_(candidate_ids))) or 0),
        "blueprint_rows": int(db.scalar(select(func.count()).select_from(BlueprintSnapshot).where(BlueprintSnapshot.snapshot_run_id.in_(candidate_ids))) or 0),
        "skill_rows": int(db.scalar(select(func.count()).select_from(CharacterSkillSnapshot).where(CharacterSkillSnapshot.snapshot_run_id.in_(candidate_ids))) or 0),
        "corporation_rows": int(db.scalar(select(func.count()).select_from(CorporationSnapshot).where(CorporationSnapshot.snapshot_run_id.in_(candidate_ids))) or 0),
        "metric_rows": int(db.scalar(select(func.count()).select_from(SnapshotMetric).where(SnapshotMetric.snapshot_run_id.in_(candidate_ids))) or 0),
    }


@router.get("/maintenance/legacy-snapshots")
def legacy_snapshot_maintenance_preview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_analytics(current_user, db)
    require_role(current_user, "admin", db)
    return {
        "strategy": "Keep all manual snapshots and the latest complete legacy automatic snapshot for each UTC day.",
        "candidate_rows": legacy_snapshot_compaction_preview(db),
    }


@router.post("/maintenance/legacy-snapshots/compact")
def compact_legacy_snapshots(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_analytics(current_user, db)
    require_role(current_user, "host", db)
    preview = legacy_snapshot_compaction_preview(db)
    if preview["snapshot_runs"]:
        db.execute(delete(SnapshotRun).where(SnapshotRun.id.in_(legacy_snapshot_candidate_ids())))
        db.commit()
    return {
        "status": "compacted",
        "deleted": preview,
        "maintenance_note": "PostgreSQL can reuse the freed space immediately. A later VACUUM FULL during planned downtime is required to return it to the host filesystem.",
    }


def character_history_rows(
    db: Session,
    days: int,
    character_ids: set[int] | None,
    *,
    categorized: bool,
) -> list[CharacterSkillSnapshot]:
    if character_ids is not None and not character_ids:
        return []
    category_filter = CharacterSkillSnapshot.category_name.is_not(None) if categorized else CharacterSkillSnapshot.category_name.is_(None)
    cutoff = start_cutoff(days)
    ranked_baselines = select(
        CharacterSkillSnapshot.id.label("id"),
        func.row_number().over(
            partition_by=(CharacterSkillSnapshot.character_id, CharacterSkillSnapshot.category_name),
            order_by=(CharacterSkillSnapshot.recorded_at.desc(), CharacterSkillSnapshot.id.desc()),
        ).label("position"),
    ).where(CharacterSkillSnapshot.recorded_at < cutoff, category_filter)
    if character_ids is not None:
        ranked_baselines = ranked_baselines.where(CharacterSkillSnapshot.character_id.in_(character_ids))
    ranked = ranked_baselines.subquery()
    baseline_ids = select(ranked.c.id).where(ranked.c.position == 1)
    query = select(CharacterSkillSnapshot).where(or_(CharacterSkillSnapshot.id.in_(baseline_ids), CharacterSkillSnapshot.recorded_at >= cutoff), category_filter)
    if character_ids is not None:
        query = query.where(CharacterSkillSnapshot.character_id.in_(character_ids))
    return list(
        db.scalars(
            query.order_by(
                CharacterSkillSnapshot.character_id,
                CharacterSkillSnapshot.category_name,
                CharacterSkillSnapshot.recorded_at,
                CharacterSkillSnapshot.id,
            )
        ).all()
    )


def corporation_history_rows(
    db: Session,
    days: int,
    corporation_ids: set[int] | None,
) -> list[CorporationSnapshot]:
    if corporation_ids is not None and not corporation_ids:
        return []
    cutoff = start_cutoff(days)
    ranked_baselines = select(
        CorporationSnapshot.id.label("id"),
        func.row_number().over(
            partition_by=CorporationSnapshot.corporation_id,
            order_by=(CorporationSnapshot.recorded_at.desc(), CorporationSnapshot.id.desc()),
        ).label("position"),
    ).where(CorporationSnapshot.recorded_at < cutoff)
    if corporation_ids is not None:
        ranked_baselines = ranked_baselines.where(CorporationSnapshot.corporation_id.in_(corporation_ids))
    ranked = ranked_baselines.subquery()
    baseline_ids = select(ranked.c.id).where(ranked.c.position == 1)
    query = select(CorporationSnapshot).where(or_(CorporationSnapshot.id.in_(baseline_ids), CorporationSnapshot.recorded_at >= cutoff))
    if corporation_ids is not None:
        query = query.where(CorporationSnapshot.corporation_id.in_(corporation_ids))
    return list(
        db.scalars(
            query.order_by(
                CorporationSnapshot.corporation_id,
                CorporationSnapshot.recorded_at,
                CorporationSnapshot.id,
            )
        ).all()
    )


def latest_and_earliest_character_rows(
    db: Session,
    days: int,
    character_ids: set[int] | None,
    history_rows: list[CharacterSkillSnapshot] | None = None,
) -> tuple[list[CharacterSkillSnapshot], list[CharacterSkillSnapshot]]:
    rows = history_rows if history_rows is not None else character_history_rows(db, days, character_ids, categorized=False)
    grouped: dict[int, list[CharacterSkillSnapshot]] = {}
    for row in rows:
        grouped.setdefault(int(row.character_id), []).append(row)
    latest = [history[-1] for history in grouped.values()]
    earliest = [history[0] for history in grouped.values() if len(history) > 1]
    return latest, earliest

def latest_and_earliest_corp_rows(
    db: Session,
    days: int,
    corporation_ids: set[int] | None,
    history_rows: list[CorporationSnapshot] | None = None,
) -> tuple[list[CorporationSnapshot], list[CorporationSnapshot]]:
    rows = history_rows if history_rows is not None else corporation_history_rows(db, days, corporation_ids)
    grouped: dict[int, list[CorporationSnapshot]] = {}
    for row in rows:
        grouped.setdefault(int(row.corporation_id), []).append(row)
    latest = [history[-1] for history in grouped.values()]
    earliest = [history[0] for history in grouped.values() if len(history) > 1]
    return latest, earliest

def delta_rows(latest: list[Any], earliest: list[Any], key: str, value_attr: str, name_attr: str) -> list[dict[str, Any]]:
    first = {getattr(row, key): row for row in earliest}
    rows: list[dict[str, Any]] = []
    for row in latest:
        row_id = getattr(row, key)
        old = first.get(row_id)
        if old is None:
            continue
        old_value = getattr(old, value_attr, 0)
        new_value = getattr(row, value_attr, 0) or 0
        rows.append({"id": row_id, "name": getattr(row, name_attr), "value": as_float(new_value), "delta": as_float(new_value) - as_float(old_value)})
    return sorted(rows, key=lambda item: item["delta"], reverse=True)


def change_breakdown(
    rows: list[Any],
    *,
    key: str,
    value_attr: str,
    name_attr: str,
    cutoff: datetime,
) -> dict[str, Any]:
    """Separate real movement from owners first observed inside the selected range."""
    grouped: dict[int, list[Any]] = {}
    for row in rows:
        grouped.setdefault(int(getattr(row, key)), []).append(row)

    current = 0.0
    organic_delta = 0.0
    coverage_delta = 0.0
    newly_tracked: list[dict[str, Any]] = []
    for owner_id, history in grouped.items():
        history.sort(key=lambda row: (row.recorded_at, row.id))
        first = history[0]
        latest = history[-1]
        first_value = as_float(getattr(first, value_attr, 0) or 0)
        latest_value = as_float(getattr(latest, value_attr, 0) or 0)
        current += latest_value
        first_observed_at = aware_utc(first.recorded_at)
        if first_observed_at and first_observed_at >= cutoff:
            coverage_delta += first_value
            newly_tracked.append(
                {
                    "id": owner_id,
                    "name": getattr(latest, name_attr),
                    "value": first_value,
                    "first_observed_at": iso(first_observed_at),
                }
            )
        if len(history) > 1:
            organic_delta += latest_value - first_value

    return {
        "current": current,
        "total_delta": organic_delta + coverage_delta,
        "organic_delta": organic_delta,
        "coverage_delta": coverage_delta,
        "newly_tracked_count": len(newly_tracked),
        "newly_tracked": sorted(newly_tracked, key=lambda item: item["value"], reverse=True)[:12],
    }


def category_deltas(
    db: Session,
    days: int,
    character_ids: set[int] | None,
    history_rows: list[CharacterSkillSnapshot] | None = None,
) -> list[dict[str, Any]]:
    rows = history_rows if history_rows is not None else character_history_rows(db, days, character_ids, categorized=True)
    grouped: dict[tuple[int, str], list[CharacterSkillSnapshot]] = {}
    for row in rows:
        grouped.setdefault((int(row.character_id), row.category_name or "Uncategorized"), []).append(row)
    by_category: dict[str, float] = {}
    for (_character_id, category), history in grouped.items():
        if len(history) < 2:
            continue
        display_category = "All skill groups (legacy)" if category == "Skill" else category
        by_category[display_category] = by_category.get(display_category, 0) + int(history[-1].category_skill_points or 0) - int(history[0].category_skill_points or 0)
    return [{"name": category, "delta": delta} for category, delta in sorted(by_category.items(), key=lambda item: item[1], reverse=True)[:12]]

def skill_point_losses(
    db: Session,
    days: int,
    character_ids: set[int] | None,
    history_rows: list[CharacterSkillSnapshot] | None = None,
) -> list[dict[str, Any]]:
    rows = history_rows if history_rows is not None else character_history_rows(db, days, character_ids, categorized=False)
    previous: dict[int, int] = {}
    names: dict[int, str] = {}
    losses: dict[int, int] = {}
    for row in rows:
        current = int(row.total_skill_points or 0)
        character_id = int(row.character_id)
        names[character_id] = row.character_name
        if character_id in previous and current < previous[character_id]:
            losses[character_id] = losses.get(character_id, 0) + previous[character_id] - current
        previous[character_id] = current
    return [
        {"id": character_id, "name": names.get(character_id, f"Character {character_id}"), "delta": loss}
        for character_id, loss in sorted(losses.items(), key=lambda item: item[1], reverse=True)[:12]
        if loss > 0
    ]

def skill_category_losses(
    db: Session,
    days: int,
    character_ids: set[int] | None,
    history_rows: list[CharacterSkillSnapshot] | None = None,
) -> list[dict[str, Any]]:
    rows = history_rows if history_rows is not None else character_history_rows(db, days, character_ids, categorized=True)
    previous: dict[tuple[int, str], int] = {}
    losses: dict[str, int] = {}
    for row in rows:
        raw_category = row.category_name or "Uncategorized"
        category = "All skill groups (legacy)" if raw_category == "Skill" else raw_category
        key = (int(row.character_id), raw_category)
        current = int(row.category_skill_points or 0)
        if key in previous and current < previous[key]:
            losses[category] = losses.get(category, 0) + previous[key] - current
        previous[key] = current
    return [
        {"name": category, "delta": loss}
        for category, loss in sorted(losses.items(), key=lambda item: item[1], reverse=True)[:12]
        if loss > 0
    ]

def duplicate_blueprints(db: Session, ownership_entity_ids: set[int] | None) -> list[dict[str, Any]]:
    if ownership_entity_ids is not None and not ownership_entity_ids:
        return []
    grouped: dict[tuple[str, str, bool], dict[str, Any]] = {}
    for row in scoped_blueprint_records(db):
        owner_id = int(row["owner_id"])
        if ownership_entity_ids is not None and owner_id not in ownership_entity_ids:
            continue
        owner_name = str(row["owner_name"])
        type_name = str(row["type_name"])
        is_copy = bool(row["is_copy"])
        key = (owner_name, type_name, is_copy)
        entry = grouped.setdefault(key, {"quantity": 0, "me": set(), "te": set(), "in_use": 0})
        entry["quantity"] += 1
        entry["me"].add(int(row["material_efficiency"] or 0))
        entry["te"].add(int(row["time_efficiency"] or 0))
        if row["inventory_state"] == "in_production":
            entry["in_use"] += 1
    duplicates = [
        {
            "owner_name": owner,
            "blueprint_type_name": name,
            "is_copy": is_copy,
            "quantity": entry["quantity"],
            "material_efficiency_levels": sorted(entry["me"]),
            "time_efficiency_levels": sorted(entry["te"]),
            "in_use": entry["in_use"],
        }
        for (owner, name, is_copy), entry in grouped.items()
        if entry["quantity"] > 1
    ]
    return sorted(duplicates, key=lambda item: int(item["quantity"]), reverse=True)[:50]


def daily_corporation_series(rows: list[CorporationSnapshot], value_attr: str, range_start: datetime | None = None) -> list[dict[str, Any]]:
    """Return the latest observation for each corporation on each UTC day."""
    latest_by_day: dict[tuple[int, str], CorporationSnapshot] = {}
    for row in rows:
        effective_time = max(row.recorded_at, range_start) if range_start is not None else row.recorded_at
        day = effective_time.date().isoformat()
        key = (int(row.corporation_id), day)
        previous = latest_by_day.get(key)
        if previous is None or row.recorded_at > previous.recorded_at:
            latest_by_day[key] = row

    daily_rows = sorted(
        latest_by_day.items(),
        key=lambda item: (item[0][1], item[1].corporation_name, item[1].corporation_id),
    )
    return [
        {
            "date": day,
            "corporation_id": int(row.corporation_id),
            "corporation_name": row.corporation_name,
            "value": as_float(getattr(row, value_attr) or 0),
        }
        for (_, day), row in daily_rows
    ]


def corporation_series(
    db: Session,
    days: int,
    value_attr: str,
    corporation_ids: set[int] | None,
    history_rows: list[CorporationSnapshot] | None = None,
) -> list[dict[str, Any]]:
    rows = history_rows if history_rows is not None else corporation_history_rows(db, days, corporation_ids)
    return daily_corporation_series(rows, value_attr, start_cutoff(days))

@router.get("/summary")
def analytics_summary(days: int = Query(30, ge=1, le=3660), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_analytics(current_user, db)
    cutoff = start_cutoff(days)
    now = datetime.now(timezone.utc)
    latest_run = db.scalar(select(SnapshotRun).where(SnapshotRun.status.in_({"success", "unchanged"})).order_by(SnapshotRun.started_at.desc()))
    snapshot_count = db.scalar(select(func.count()).select_from(SnapshotRun).where(SnapshotRun.started_at >= cutoff, SnapshotRun.status == "success")) or 0
    observation_count = db.scalar(select(func.count()).select_from(SnapshotRun).where(SnapshotRun.started_at >= cutoff, SnapshotRun.status.in_({"success", "unchanged"}))) or 0
    first_metric_at = aware_utc(db.scalar(select(func.min(SnapshotMetric.recorded_at))))
    observed_through = aware_utc((latest_run.completed_at or latest_run.started_at) if latest_run else None)
    covered_from = max(cutoff, first_metric_at) if first_metric_at else None
    covered_to = min(now, observed_through) if observed_through else None
    coverage_seconds = max(0, int((covered_to - covered_from).total_seconds())) if covered_from and covered_to else 0
    character_ids = visible_character_ids(current_user, db)
    corporation_ids = visible_corporation_ids(current_user, db, character_ids)
    ownership_entity_ids = visible_ownership_entity_ids(current_user, db)
    character_rows = character_history_rows(db, days, character_ids, categorized=False)
    character_category_rows = character_history_rows(db, days, character_ids, categorized=True)
    corporation_rows = corporation_history_rows(db, days, corporation_ids)
    latest_characters, earliest_characters = latest_and_earliest_character_rows(db, days, character_ids, character_rows)
    latest_corps, earliest_corps = latest_and_earliest_corp_rows(db, days, corporation_ids, corporation_rows)
    sp_gainers = delta_rows(latest_characters, earliest_characters, "character_id", "total_skill_points", "character_name")[:12]
    wallet_growth = delta_rows(latest_corps, earliest_corps, "corporation_id", "wallet_balance", "corporation_name")[:12]
    member_growth = delta_rows(latest_corps, earliest_corps, "corporation_id", "member_count", "corporation_name")[:12]
    blueprint_growth = delta_rows(latest_corps, earliest_corps, "corporation_id", "blueprint_count", "corporation_name")[:12]
    latest_wallet_total = sum(as_float(row.wallet_balance) for row in latest_corps)
    latest_blueprints = sum(int(row.blueprint_count or 0) for row in latest_corps)
    latest_members = sum(int(row.member_count or 0) for row in latest_corps)
    change_composition = {
        "skill_points": change_breakdown(character_rows, key="character_id", value_attr="total_skill_points", name_attr="character_name", cutoff=cutoff),
        "corporation_wallets": change_breakdown(corporation_rows, key="corporation_id", value_attr="wallet_balance", name_attr="corporation_name", cutoff=cutoff),
        "members": change_breakdown(corporation_rows, key="corporation_id", value_attr="member_count", name_attr="corporation_name", cutoff=cutoff),
        "blueprints": change_breakdown(corporation_rows, key="corporation_id", value_attr="blueprint_count", name_attr="corporation_name", cutoff=cutoff),
    }
    return {
        "days": days,
        "latest_snapshot_at": iso(latest_run.completed_at or latest_run.started_at) if latest_run else None,
        "latest_snapshot_status": latest_run.status if latest_run else None,
        "snapshot_count": snapshot_count,
        "observation_count": observation_count,
        "retention_mode": analytics_retention_mode(db),
        "coverage": {
            "requested_from": iso(cutoff),
            "requested_to": iso(now),
            "available_from": iso(covered_from),
            "available_to": iso(covered_to),
            "available_seconds": coverage_seconds,
            "complete": bool(first_metric_at and first_metric_at <= cutoff),
        },
        "cards": {
            "wallet_total": latest_wallet_total,
            "blueprint_total": latest_blueprints,
            "member_total": latest_members,
            "character_count": len(latest_characters),
        },
        "change_composition": change_composition,
        "top_sp_gainers": sp_gainers,
        "top_sp_losses": skill_point_losses(db, days, character_ids, character_rows),
        "top_skill_category_gainers": category_deltas(db, days, character_ids, character_category_rows),
        "top_skill_category_losses": skill_category_losses(db, days, character_ids, character_category_rows),
        "wallet_growth": wallet_growth,
        "member_growth": member_growth,
        "blueprint_growth": blueprint_growth,
        "duplicate_blueprints": duplicate_blueprints(db, ownership_entity_ids),
        "manufacturing": manufacturing_analytics(db, days),
        "mining": mining_analytics(db, days, character_ids),
        "research_projects": research_project_analytics(db, days, character_ids),
        "series": {
            "wallet_totals": corporation_series(db, days, "wallet_balance", corporation_ids, corporation_rows),
            "member_counts": corporation_series(db, days, "member_count", corporation_ids, corporation_rows),
            "blueprint_counts": corporation_series(db, days, "blueprint_count", corporation_ids, corporation_rows),
        },
    }


def analytics_metric_rows(db: Session, days: int) -> list[SnapshotMetric]:
    query = select(SnapshotMetric).where(SnapshotMetric.recorded_at >= start_cutoff(days))
    corporation_ids = analytics_corporation_ids(db)
    corporation_filter = SnapshotMetric.owner_type != "corporation"
    if corporation_ids:
        corporation_filter = or_(
            corporation_filter,
            SnapshotMetric.owner_id.in_(corporation_ids),
        )
    query = query.where(corporation_filter)
    return list(db.scalars(query.order_by(SnapshotMetric.recorded_at)).all())

@router.get("/exports/metrics.csv")
def export_metrics_csv(days: int = Query(365, ge=1, le=3660), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StreamingResponse:
    require_analytics(current_user, db)
    rows = analytics_metric_rows(db, days)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["recorded_at", "snapshot_run_id", "owner_type", "owner_id", "owner_name", "metric_key", "metric_version", "metric_value", "dimensions_json"])
    for row in rows:
        writer.writerow([iso(row.recorded_at), row.snapshot_run_id, row.owner_type, row.owner_id, row.owner_name, row.metric_key, row.metric_version, row.metric_value, row.dimensions_json])
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=eqm-metrics.csv"})


@router.get("/exports/metrics.json")
def export_metrics_json(days: int = Query(365, ge=1, le=3660), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_analytics(current_user, db)
    rows = analytics_metric_rows(db, days)
    return [
        {
            "recorded_at": iso(row.recorded_at),
            "snapshot_run_id": row.snapshot_run_id,
            "owner_type": row.owner_type,
            "owner_id": row.owner_id,
            "owner_name": row.owner_name,
            "metric_key": row.metric_key,
            "metric_version": row.metric_version,
            "metric_value": as_float(row.metric_value),
            "dimensions": row.dimensions_json,
        }
        for row in rows
    ]

@router.get("/metrics")
def metric_catalog(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_analytics(current_user, db)
    discovered = {row[0] for row in db.execute(select(SnapshotMetric.metric_key).distinct()).all()}
    cataloged = {item["metric"] for item in METRIC_CATALOG}
    rows = [dict(item, hasData=item["metric"] in discovered) for item in METRIC_CATALOG]
    rows.extend(
        {
            "metric": metric,
            "version": 1,
            "label": metric.replace(".", " ").title(),
            "unit": "value",
            "aggregation": "unregistered",
            "entityAggregation": "unregistered",
            "timeAggregation": "unregistered",
            "supportedAggregations": [],
            "supportedTransforms": [],
            "derivedMetrics": [],
            "valueKind": "unknown",
            "dimensions": [],
            "privacy": "unknown",
            "category": "Discovered",
            "supportsCharacter": False,
            "supportsCorporation": False,
            "chartTypes": [],
            "deprecated": True,
            "registered": False,
            "description": "Historical metric without a registered aggregation contract.",
            "hasData": True,
        }
        for metric in sorted(discovered - cataloged)
    )
    return rows
