from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import EveCharacter, User
from app.services.permissions import can_view_section
from app.services.analytics_scope import resolve_analytics_character_scope
from app.services.planetary_analytics import planetary_analytics_summary


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/planetary-industry")
def planetary_industry_analytics(
    days: int = Query(30, ge=1, le=3660),
    scope: str = Query("all"),
    corporation_id: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not can_view_section(current_user, "analytics", db):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Analytics permission is required")
    resolved_ids, _ = resolve_analytics_character_scope(
        current_user,
        db,
        scope=scope,
        corporation_id=corporation_id,
    )
    character_ids = set(db.scalars(select(EveCharacter.id)).all()) if resolved_ids is None else resolved_ids
    return planetary_analytics_summary(db, days, character_ids)
