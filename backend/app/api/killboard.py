from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import KillboardSyncRun, Killmail, User
from app.services.audit import record_audit_event
from app.services.killboard_analytics import available_scopes, build_killboard_analytics
from app.services.killboard_entities import refresh_killboard_entity_names
from app.services.killboard_settings import killboard_settings, update_killboard_settings
from app.services.killboard_sync import create_sync_run, start_sync_task, sync_run_payload
from app.services.permissions import ROLE_RANK, can_view_section, role_rank


router = APIRouter(prefix="/killboard", tags=["killboard"])


class SyncRequest(BaseModel):
    scope: Literal["account", "corporations", "all"] = "account"
    lookback_days: int | None = None


class SettingsPatch(BaseModel):
    enabled: bool | None = None
    sync_period_hours: int | None = None
    lookback_days: int | None = None
    request_delay_seconds: float | None = None
    max_pages: int | None = None


def require_view(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(current_user, "killboard", db):
        raise HTTPException(status_code=403, detail="Killboard permission is required")
    return current_user


def require_admin(user: User, db: Session) -> None:
    if role_rank(user, db) < ROLE_RANK["admin"]:
        raise HTTPException(status_code=403, detail="Administrator access is required")


def latest_run(db: Session, user: User) -> KillboardSyncRun | None:
    query = select(KillboardSyncRun).order_by(KillboardSyncRun.created_at.desc()).limit(1)
    if role_rank(user, db) < ROLE_RANK["admin"]:
        query = query.where(KillboardSyncRun.initiated_by_user_id == user.id)
    return db.scalar(query)


def can_access_run(db: Session, user: User, run: KillboardSyncRun) -> bool:
    return run.initiated_by_user_id == user.id or role_rank(user, db) >= ROLE_RANK["admin"]


@router.get("/context")
def context(current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = killboard_settings(db)
    run = latest_run(db, current_user)
    finished = run.finished_at if run and run.finished_at else None
    if finished is not None and finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    due = run is None or finished is None or finished <= datetime.now(timezone.utc) - timedelta(hours=settings["sync_period_hours"])
    return {
        "enabled": settings["enabled"],
        "settings": settings,
        "can_manage": role_rank(current_user, db) >= ROLE_RANK["admin"],
        "scopes": available_scopes(db, current_user),
        "latest_sync": sync_run_payload(run) if run else None,
        "sync_due": due,
        "cached_killmail_count": int(db.scalar(select(func.count()).select_from(Killmail)) or 0),
        "coverage_notice": "zKillboard discovery is best-effort and may not be complete. Killmail facts come from ESI; value and classification fields are zKillboard enrichment.",
    }


@router.get("/analytics")
async def analytics(
    scope_type: Literal["account", "character", "corporation", "all"] = Query(default="account"),
    scope_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=3650),
    current_user: User = Depends(require_view),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not killboard_settings(db)["enabled"]:
        raise HTTPException(status_code=409, detail="The Killboard module is disabled")
    try:
        # Public ESI translation is best-effort: analytics remains usable with ID
        # fallbacks when an entity is deleted, inaccessible, or ESI is unavailable.
        # A cold installation may have several thousand public combatants.
        # The resolver internally splits this cap into ESI-sized requests; later
        # page loads are cache-only until entries become stale.
        await refresh_killboard_entity_names(db, limit=5_000)
        return build_killboard_analytics(db, current_user, scope_type=scope_type, scope_id=scope_id, days=days)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync", status_code=202)
async def start_sync(payload: SyncRequest, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    if payload.scope in {"corporations", "all"} and role_rank(current_user, db) < ROLE_RANK["officer"]:
        raise HTTPException(status_code=403, detail="Officer access is required for corporation killboard sync")
    active = db.scalar(select(KillboardSyncRun).where(
        KillboardSyncRun.initiated_by_user_id == current_user.id,
        KillboardSyncRun.status.in_(["queued", "running"]),
    ).order_by(KillboardSyncRun.created_at.desc()).limit(1))
    if active is not None:
        start_sync_task(active.id)
        return sync_run_payload(active)
    try:
        run = create_sync_run(db, current_user, scope=payload.scope, lookback_days=payload.lookback_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(db, event_kind="killboard_sync_started", title="Killboard synchronization started", body=f"{len(run.targets_json)} discovery targets; {run.lookback_days}-day lookback.", actor_user=current_user)
    db.commit()
    db.refresh(run)
    start_sync_task(run.id)
    return sync_run_payload(run)


@router.post("/sync/ensure", status_code=202)
async def ensure_sync(current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = killboard_settings(db)
    if not settings["enabled"]:
        raise HTTPException(status_code=409, detail="The Killboard module is disabled")
    run = latest_run(db, current_user)
    if run is not None and run.status in {"queued", "running"}:
        start_sync_task(run.id)
        return {"started": False, "due": True, "sync": sync_run_payload(run)}
    finished = run.finished_at if run else None
    if finished is not None and finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    due = run is None or finished is None or finished <= datetime.now(timezone.utc) - timedelta(hours=settings["sync_period_hours"])
    if not due:
        return {"started": False, "due": False, "sync": sync_run_payload(run)}
    try:
        new_run = create_sync_run(db, current_user, scope="account")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(new_run)
    start_sync_task(new_run.id)
    return {"started": True, "due": True, "sync": sync_run_payload(new_run)}


@router.get("/sync/latest")
def get_latest_sync(current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any] | None:
    run = latest_run(db, current_user)
    return sync_run_payload(run) if run else None


@router.get("/sync/{run_id}")
def get_sync(run_id: str, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    run = db.get(KillboardSyncRun, run_id)
    if run is None or not can_access_run(db, current_user, run):
        raise HTTPException(status_code=404, detail="Killboard synchronization was not found")
    return sync_run_payload(run)


@router.post("/sync/{run_id}/resume", status_code=202)
async def resume_sync(run_id: str, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    run = db.get(KillboardSyncRun, run_id)
    if run is None or not can_access_run(db, current_user, run):
        raise HTTPException(status_code=404, detail="Killboard synchronization was not found")
    if run.status in {"complete", "complete_with_errors", "cancelled"}:
        raise HTTPException(status_code=409, detail="This synchronization is already finished")
    run.status = "queued"
    run.finished_at = None
    run.message = "Killboard synchronization queued to resume from its durable cursor."
    db.commit()
    start_sync_task(run.id)
    return sync_run_payload(run)


@router.post("/sync/{run_id}/cancel")
def cancel_sync(run_id: str, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    run = db.get(KillboardSyncRun, run_id)
    if run is None or not can_access_run(db, current_user, run):
        raise HTTPException(status_code=404, detail="Killboard synchronization was not found")
    if run.status not in {"queued", "running", "failed"}:
        raise HTTPException(status_code=409, detail="This synchronization is already finished")
    run.status = "cancelled"
    run.finished_at = datetime.now(timezone.utc)
    run.updated_at = run.finished_at
    run.message = "Killboard synchronization cancelled. Previously imported records were preserved."
    db.commit()
    return sync_run_payload(run)


@router.patch("/settings")
def patch_settings(payload: SettingsPatch, current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_admin(current_user, db)
    try:
        updated = update_killboard_settings(db, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(db, event_kind="killboard_settings_updated", title="Killboard settings updated", body=str(updated), actor_user=current_user)
    db.commit()
    return updated
