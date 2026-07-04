from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_role
from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.models import EveCategory, EveConstellation, EveDogmaAttribute, EveDogmaEffect, EveGroup, EveRegion, EveStargate, EveStation, EveSystem, EveType, EveTypeDogmaAttribute, EveTypeDogmaEffect, IndustryActivity, IndustryActivityInput, User
from app.services.sde_importer import import_sde

router = APIRouter(prefix="/sde", tags=["sde"])

_IMPORT_LOCK = Lock()
_IMPORT_STATE: dict[str, Any] = {
    "running": False,
    "status": "idle",
    "stage": "idle",
    "source_path": None,
    "started_at": None,
    "updated_at": None,
    "completed_at": None,
    "error": None,
    "stats": None,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def import_state_snapshot() -> dict[str, Any]:
    with _IMPORT_LOCK:
        state = dict(_IMPORT_STATE)
        state["stats"] = dict(_IMPORT_STATE["stats"]) if _IMPORT_STATE.get("stats") else None
        return state


def update_import_state(**updates: Any) -> None:
    with _IMPORT_LOCK:
        _IMPORT_STATE.update(updates)
        _IMPORT_STATE["updated_at"] = utc_now_iso()


def import_progress(stats: Any, stage: str) -> None:
    update_import_state(running=True, status="running", stage=stage, stats=stats.to_dict())


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    require_role(current_user, "admin")
    return current_user


@router.get("/status")
def sde_status(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {
        "default_source_path": get_settings().sde_source_path,
        "categories": db.scalar(select(func.count()).select_from(EveCategory)) or 0,
        "groups": db.scalar(select(func.count()).select_from(EveGroup)) or 0,
        "types": db.scalar(select(func.count()).select_from(EveType)) or 0,
        "regions": db.scalar(select(func.count()).select_from(EveRegion)) or 0,
        "constellations": db.scalar(select(func.count()).select_from(EveConstellation)) or 0,
        "systems": db.scalar(select(func.count()).select_from(EveSystem)) or 0,
        "stargates": db.scalar(select(func.count()).select_from(EveStargate)) or 0,
        "stations": db.scalar(select(func.count()).select_from(EveStation)) or 0,
        "dogma_attributes": db.scalar(select(func.count()).select_from(EveDogmaAttribute)) or 0,
        "dogma_effects": db.scalar(select(func.count()).select_from(EveDogmaEffect)) or 0,
        "type_dogma_attributes": db.scalar(select(func.count()).select_from(EveTypeDogmaAttribute)) or 0,
        "type_dogma_effects": db.scalar(select(func.count()).select_from(EveTypeDogmaEffect)) or 0,
        "blueprint_activities": db.scalar(select(func.count()).select_from(IndustryActivity)) or 0,
        "activity_inputs": db.scalar(select(func.count()).select_from(IndustryActivityInput)) or 0,
    }


@router.get("/import-status")
def sde_import_status(_: User = Depends(require_admin)) -> dict[str, Any]:
    return import_state_snapshot()


def run_import_job(source_path: str) -> None:
    db = SessionLocal()
    try:
        result = import_sde(source_path, db, progress=import_progress)
        update_import_state(running=False, status="success", stage="complete", completed_at=utc_now_iso(), stats=result)
    except FileNotFoundError as exc:
        update_import_state(running=False, status="failed", stage="failed", completed_at=utc_now_iso(), error=str(exc))
    except Exception as exc:
        message = f"SDE import failed: {exc}"
        update_import_state(running=False, status="failed", stage="failed", completed_at=utc_now_iso(), error=message)
    finally:
        db.close()


@router.post("/import")
def import_static_data(payload: dict[str, Any], _: User = Depends(require_admin)) -> dict[str, Any]:
    source_path = str(payload.get("source_path") or get_settings().sde_source_path).strip()
    if not source_path:
        raise HTTPException(status_code=400, detail="An SDE source path is required")
    with _IMPORT_LOCK:
        if _IMPORT_STATE.get("running"):
            raise HTTPException(status_code=409, detail="An SDE import is already running")
        _IMPORT_STATE.update(
            {
                "running": True,
                "status": "running",
                "stage": "queued",
                "source_path": source_path,
                "started_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "completed_at": None,
                "error": None,
                "stats": None,
            }
        )
    Thread(target=run_import_job, args=(source_path,), daemon=True).start()
    return import_state_snapshot()


