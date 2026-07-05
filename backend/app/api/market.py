from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.services.market import appraise_market, list_market_hubs
from app.services.permissions import can_view_section

router = APIRouter(prefix="/market", tags=["market"])


def require_market(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(current_user, "market", db):
        raise HTTPException(status_code=403, detail="market permission is required")
    return current_user


@router.get("/hubs")
def market_hubs(_: User = Depends(require_market), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return list_market_hubs(db)


@router.post("/appraise")
async def market_appraise(payload: dict[str, Any], _: User = Depends(require_market), db: Session = Depends(get_db)) -> dict[str, Any]:
    return await appraise_market(db, str(payload.get("text") or ""), payload.get("hubs"))