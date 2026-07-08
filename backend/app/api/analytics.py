from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user, require_role
from app.db.session import get_db
from app.models import BlueprintSnapshot, CharacterSkillSnapshot, CorporationSnapshot, EveCharacter, OwnershipEntity, SnapshotMetric, SnapshotRun, User
from app.services.analytics import create_snapshot
from app.services.permissions import ROLE_RANK, can_view_section, role_rank

router = APIRouter(prefix="/analytics", tags=["analytics"])
METRIC_CATALOG: list[dict[str, Any]] = [
    {"metric": "skill_points.total", "version": 1, "label": "Total Skill Points", "unit": "SP", "aggregation": "latest", "category": "Skills", "supportsCharacter": True, "supportsCorporation": False, "chartTypes": ["line", "bar", "histogram"], "deprecated": False},
    {"metric": "skill_points.lost", "version": 1, "label": "Skill Point History", "unit": "SP", "aggregation": "sum", "category": "Skills", "supportsCharacter": True, "supportsCorporation": False, "chartTypes": ["bar", "histogram"], "deprecated": False},
    {"metric": "skills.count", "version": 1, "label": "Trained Skill Count", "unit": "skills", "aggregation": "latest", "category": "Skills", "supportsCharacter": True, "supportsCorporation": False, "chartTypes": ["line", "bar"], "deprecated": False},
    {"metric": "skill_queue.count", "version": 1, "label": "Skill Queue Count", "unit": "skills", "aggregation": "latest", "category": "Skills", "supportsCharacter": True, "supportsCorporation": False, "chartTypes": ["line", "bar"], "deprecated": False},
    {"metric": "skill_points.category", "version": 1, "label": "Skill Points by Category", "unit": "SP", "aggregation": "sum", "category": "Skills", "supportsCharacter": True, "supportsCorporation": False, "chartTypes": ["bar", "pie", "stacked_bar"], "deprecated": False},
    {"metric": "skill_points.category_lost", "version": 1, "label": "Skill Point History by Category", "unit": "SP", "aggregation": "sum", "category": "Skills", "supportsCharacter": True, "supportsCorporation": False, "chartTypes": ["bar", "pie"], "deprecated": False},
    {"metric": "members.count", "version": 1, "label": "Corporation Members", "unit": "members", "aggregation": "latest", "category": "Corporations", "supportsCharacter": False, "supportsCorporation": True, "chartTypes": ["line", "bar"], "deprecated": False},
    {"metric": "wallet.balance", "version": 1, "label": "Corporation Wallet Balance", "unit": "ISK", "aggregation": "sum", "category": "Finance", "supportsCharacter": False, "supportsCorporation": True, "chartTypes": ["line", "bar"], "deprecated": False},
    {"metric": "wallet.division_balance", "version": 1, "label": "Wallet Division Balance", "unit": "ISK", "aggregation": "sum", "category": "Finance", "supportsCharacter": False, "supportsCorporation": True, "chartTypes": ["line", "bar", "stacked_bar", "pie"], "deprecated": False},
    {"metric": "assets.rows", "version": 1, "label": "Asset Rows", "unit": "rows", "aggregation": "sum", "category": "Assets", "supportsCharacter": True, "supportsCorporation": True, "chartTypes": ["line", "bar", "histogram"], "deprecated": False},
    {"metric": "assets.units", "version": 1, "label": "Asset Units", "unit": "units", "aggregation": "sum", "category": "Assets", "supportsCharacter": True, "supportsCorporation": True, "chartTypes": ["line", "bar", "histogram"], "deprecated": False},
    {"metric": "blueprints.count", "version": 1, "label": "Blueprint Count", "unit": "BPs", "aggregation": "sum", "category": "Industry", "supportsCharacter": True, "supportsCorporation": True, "chartTypes": ["line", "bar"], "deprecated": False},
    {"metric": "blueprint.quantity", "version": 1, "label": "Blueprint Quantity", "unit": "BPs", "aggregation": "sum", "category": "Industry", "supportsCharacter": True, "supportsCorporation": True, "chartTypes": ["bar", "pie", "histogram"], "deprecated": False},
]


def require_analytics(current_user: User, db: Session) -> None:
    if not can_view_section(current_user, "analytics", db):
        raise HTTPException(status_code=403, detail="analytics section access is required")


def as_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def start_cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 3660)))


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


def visible_corporation_ids(current_user: User, db: Session, character_ids: set[int] | None) -> set[int] | None:
    if role_rank(current_user, db) >= ROLE_RANK["officer"]:
        return None
    if not character_ids:
        return set()
    return {
        row[0]
        for row in db.execute(
            select(EveCharacter.corporation_id)
            .where(EveCharacter.id.in_(character_ids), EveCharacter.corporation_id.is_not(None))
            .distinct()
        ).all()
        if row[0] is not None
    }


def can_view_owner_analytics(viewer: User, owner: OwnershipEntity, db: Session) -> bool:
    if role_rank(viewer, db) >= ROLE_RANK["officer"]:
        return True
    if owner.character and can_view_character_analytics(viewer, owner.character, db):
        return True
    if owner.character and owner.character.public_assets_visible and not owner.character.sync_opt_out:
        return True
    return False


def visible_ownership_entity_ids(current_user: User, db: Session) -> set[int] | None:
    if role_rank(current_user, db) >= ROLE_RANK["officer"]:
        return None
    owners = db.scalars(
        select(OwnershipEntity).options(
            selectinload(OwnershipEntity.character).selectinload(EveCharacter.owner_user),
            selectinload(OwnershipEntity.corporation),
        )
    ).all()
    return {owner.id for owner in owners if can_view_owner_analytics(current_user, owner, db)}


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


def latest_and_earliest_character_rows(db: Session, days: int, character_ids: set[int] | None) -> tuple[list[CharacterSkillSnapshot], list[CharacterSkillSnapshot]]:
    cutoff = start_cutoff(days)
    if character_ids is not None and not character_ids:
        return [], []
    query = select(CharacterSkillSnapshot).where(CharacterSkillSnapshot.recorded_at >= cutoff, CharacterSkillSnapshot.category_name.is_(None))
    if character_ids is not None:
        query = query.where(CharacterSkillSnapshot.character_id.in_(character_ids))
    rows = db.scalars(query.order_by(CharacterSkillSnapshot.character_id, CharacterSkillSnapshot.recorded_at, CharacterSkillSnapshot.id)).all()
    grouped: dict[int, list[CharacterSkillSnapshot]] = {}
    for row in rows:
        grouped.setdefault(int(row.character_id), []).append(row)
    latest = [history[-1] for history in grouped.values()]
    earliest = [history[0] for history in grouped.values() if len(history) > 1]
    return latest, earliest


def latest_and_earliest_corp_rows(db: Session, days: int, corporation_ids: set[int] | None) -> tuple[list[CorporationSnapshot], list[CorporationSnapshot]]:
    cutoff = start_cutoff(days)
    if corporation_ids is not None and not corporation_ids:
        return [], []
    query = select(CorporationSnapshot).where(CorporationSnapshot.recorded_at >= cutoff)
    if corporation_ids is not None:
        query = query.where(CorporationSnapshot.corporation_id.in_(corporation_ids))
    rows = db.scalars(query.order_by(CorporationSnapshot.corporation_id, CorporationSnapshot.recorded_at, CorporationSnapshot.id)).all()
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


def category_deltas(db: Session, days: int, character_ids: set[int] | None) -> list[dict[str, Any]]:
    cutoff = start_cutoff(days)
    if character_ids is not None and not character_ids:
        return []
    query = select(CharacterSkillSnapshot).where(CharacterSkillSnapshot.recorded_at >= cutoff, CharacterSkillSnapshot.category_name.is_not(None))
    if character_ids is not None:
        query = query.where(CharacterSkillSnapshot.character_id.in_(character_ids))
    rows = db.scalars(query.order_by(CharacterSkillSnapshot.character_id, CharacterSkillSnapshot.category_name, CharacterSkillSnapshot.recorded_at, CharacterSkillSnapshot.id)).all()
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


def skill_point_losses(db: Session, days: int, character_ids: set[int] | None) -> list[dict[str, Any]]:
    if character_ids is not None and not character_ids:
        return []
    query = select(CharacterSkillSnapshot).where(CharacterSkillSnapshot.recorded_at >= start_cutoff(days), CharacterSkillSnapshot.category_name.is_(None))
    if character_ids is not None:
        query = query.where(CharacterSkillSnapshot.character_id.in_(character_ids))
    rows = db.scalars(query.order_by(CharacterSkillSnapshot.character_id, CharacterSkillSnapshot.recorded_at)).all()
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


def skill_category_losses(db: Session, days: int, character_ids: set[int] | None) -> list[dict[str, Any]]:
    if character_ids is not None and not character_ids:
        return []
    query = select(CharacterSkillSnapshot).where(CharacterSkillSnapshot.recorded_at >= start_cutoff(days), CharacterSkillSnapshot.category_name.is_not(None))
    if character_ids is not None:
        query = query.where(CharacterSkillSnapshot.character_id.in_(character_ids))
    rows = db.scalars(query.order_by(CharacterSkillSnapshot.character_id, CharacterSkillSnapshot.category_name, CharacterSkillSnapshot.recorded_at)).all()
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
    latest_run_id = db.scalar(select(func.max(BlueprintSnapshot.snapshot_run_id)))
    if not latest_run_id:
        return []
    query = select(BlueprintSnapshot).where(BlueprintSnapshot.snapshot_run_id == latest_run_id)
    if ownership_entity_ids is not None:
        query = query.where(BlueprintSnapshot.ownership_entity_id.in_(ownership_entity_ids))
    rows = db.scalars(query).all()
    grouped: dict[tuple[str, str, bool], int] = {}
    for row in rows:
        key = (row.owner_name, row.blueprint_type_name, row.is_copy)
        grouped[key] = grouped.get(key, 0) + int(row.quantity or 0)
    duplicates = [
        {"owner_name": owner, "blueprint_type_name": name, "is_copy": is_copy, "quantity": quantity}
        for (owner, name, is_copy), quantity in grouped.items()
        if quantity > 1
    ]
    return sorted(duplicates, key=lambda item: item["quantity"], reverse=True)[:50]


def corporation_series(db: Session, days: int, value_attr: str, corporation_ids: set[int] | None) -> list[dict[str, Any]]:
    cutoff = start_cutoff(days)
    if corporation_ids is not None and not corporation_ids:
        return []
    query = select(CorporationSnapshot).where(CorporationSnapshot.recorded_at >= cutoff)
    if corporation_ids is not None:
        query = query.where(CorporationSnapshot.corporation_id.in_(corporation_ids))
    rows = db.scalars(query.order_by(CorporationSnapshot.recorded_at, CorporationSnapshot.corporation_name)).all()
    return [
        {"date": iso(row.recorded_at), "corporation_name": row.corporation_name, "value": as_float(getattr(row, value_attr) or 0)}
        for row in rows
    ]


@router.get("/summary")
def analytics_summary(days: int = Query(30, ge=1, le=3660), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_analytics(current_user, db)
    latest_run = db.scalar(select(SnapshotRun).order_by(SnapshotRun.started_at.desc()))
    snapshot_count = db.scalar(select(func.count()).select_from(SnapshotRun).where(SnapshotRun.started_at >= start_cutoff(days))) or 0
    character_ids = visible_character_ids(current_user, db)
    corporation_ids = visible_corporation_ids(current_user, db, character_ids)
    ownership_entity_ids = visible_ownership_entity_ids(current_user, db)
    latest_characters, earliest_characters = latest_and_earliest_character_rows(db, days, character_ids)
    latest_corps, earliest_corps = latest_and_earliest_corp_rows(db, days, corporation_ids)
    sp_gainers = delta_rows(latest_characters, earliest_characters, "character_id", "total_skill_points", "character_name")[:12]
    wallet_growth = delta_rows(latest_corps, earliest_corps, "corporation_id", "wallet_balance", "corporation_name")[:12]
    member_growth = delta_rows(latest_corps, earliest_corps, "corporation_id", "member_count", "corporation_name")[:12]
    blueprint_growth = delta_rows(latest_corps, earliest_corps, "corporation_id", "blueprint_count", "corporation_name")[:12]
    latest_wallet_total = sum(as_float(row.wallet_balance) for row in latest_corps)
    latest_blueprints = sum(int(row.blueprint_count or 0) for row in latest_corps)
    latest_members = sum(int(row.member_count or 0) for row in latest_corps)
    return {
        "days": days,
        "latest_snapshot_at": iso(latest_run.completed_at or latest_run.started_at) if latest_run else None,
        "latest_snapshot_status": latest_run.status if latest_run else None,
        "snapshot_count": snapshot_count,
        "cards": {
            "wallet_total": latest_wallet_total,
            "blueprint_total": latest_blueprints,
            "member_total": latest_members,
            "character_count": len(latest_characters),
        },
        "top_sp_gainers": sp_gainers,
        "top_sp_losses": skill_point_losses(db, days, character_ids),
        "top_skill_category_gainers": category_deltas(db, days, character_ids),
        "top_skill_category_losses": skill_category_losses(db, days, character_ids),
        "wallet_growth": wallet_growth,
        "member_growth": member_growth,
        "blueprint_growth": blueprint_growth,
        "duplicate_blueprints": duplicate_blueprints(db, ownership_entity_ids),
        "series": {
            "wallet_totals": corporation_series(db, days, "wallet_balance", corporation_ids),
            "member_counts": corporation_series(db, days, "member_count", corporation_ids),
            "blueprint_counts": corporation_series(db, days, "blueprint_count", corporation_ids),
        },
    }


@router.get("/exports/metrics.csv")
def export_metrics_csv(days: int = Query(365, ge=1, le=3660), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StreamingResponse:
    require_analytics(current_user, db)
    rows = db.scalars(select(SnapshotMetric).where(SnapshotMetric.recorded_at >= start_cutoff(days)).order_by(SnapshotMetric.recorded_at)).all()
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
    rows = db.scalars(select(SnapshotMetric).where(SnapshotMetric.recorded_at >= start_cutoff(days)).order_by(SnapshotMetric.recorded_at)).all()
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
            "label": metric.replace(".", " ").title(),
            "unit": "value",
            "aggregation": "latest",
            "category": "Discovered",
            "supportsCharacter": True,
            "supportsCorporation": True,
            "chartTypes": ["line", "bar"],
            "hasData": True,
        }
        for metric in sorted(discovered - cataloged)
    )
    return rows




