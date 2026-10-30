from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.services.market import appraise_market, create_custom_market_hub, delete_custom_market_hub, list_market_hubs
from app.services.permissions import can_view_section

router = APIRouter(prefix="/market", tags=["market"])


def require_market(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(current_user, "market", db):
        raise HTTPException(status_code=403, detail="market permission is required")
    return current_user


def require_market_admin(current_user: User = Depends(require_market)) -> User:
    if current_user.role not in {"host", "admin"}:
        raise HTTPException(status_code=403, detail="admin role is required")
    return current_user


@router.get("/hubs")
def market_hubs(_: User = Depends(require_market), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return list_market_hubs(db)


@router.post("/hubs")
def create_market_hub(payload: dict[str, Any], _: User = Depends(require_market_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return create_custom_market_hub(db, str(payload.get("label") or ""), str(payload.get("system_name") or ""))


@router.delete("/hubs/{key}")
def remove_market_hub(key: str, _: User = Depends(require_market_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return delete_custom_market_hub(db, key)


@router.post("/appraise")
async def market_appraise(payload: dict[str, Any], _: User = Depends(require_market), db: Session = Depends(get_db)) -> dict[str, Any]:
    hubs = payload.get("hubs")
    return await appraise_market(db, str(payload.get("text") or ""), hubs if isinstance(hubs, list) else None)

@router.get("/items/{type_id}/history")
async def item_history(response:Response,type_id:int=Path(gt=0,le=2147483647),hub:str=Query("jita",max_length=120),limit:int=Query(5,ge=1,le=30),
    _:User=Depends(require_market),db:Session=Depends(get_db)):
    from app.services.market_history import market_history_summary
    response.headers["Cache-Control"]="private, no-store"
    return await market_history_summary(db,type_id,hub,limit)
