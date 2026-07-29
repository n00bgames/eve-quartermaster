from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.characters import visible_characters
from app.db.session import get_db
from app.models import User
from app.services.permissions import can_view_section
from app.services.planetary_analytics import planetary_analytics_summary


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/planetary-industry")
def planetary_industry_analytics(
    days: int = Query(30, ge=1, le=3660),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not can_view_section(current_user, "analytics", db):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Analytics permission is required")
    character_ids = {row.id for row in visible_characters(current_user, db)}
    return planetary_analytics_summary(db, days, character_ids)
