from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models import EveCategory, EveGroup, EveType, IndustryActivity, IndustryActivityInput, User
from app.services.sde_importer import import_sde

router = APIRouter(prefix="/sde", tags=["sde"])


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
        "blueprint_activities": db.scalar(select(func.count()).select_from(IndustryActivity)) or 0,
        "activity_inputs": db.scalar(select(func.count()).select_from(IndustryActivityInput)) or 0,
    }


@router.post("/import")
def import_static_data(payload: dict[str, Any], _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    source_path = str(payload.get("source_path") or get_settings().sde_source_path).strip()
    if not source_path:
        raise HTTPException(status_code=400, detail="An SDE source path is required")
    try:
        return import_sde(source_path, db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SDE import failed: {exc}") from exc
