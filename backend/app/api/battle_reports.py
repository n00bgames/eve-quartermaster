from __future__ import annotations

from datetime import datetime, timezone
import secrets
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import BattleReportShare, User
from app.services.battle_reports import available_report_pilots, battle_report_history, build_latest_battle_report
from app.services.killboard_entities import refresh_killboard_entity_names
from app.services.killboard_settings import killboard_settings
from app.services.permissions import ROLE_RANK, can_view_section, role_rank


router = APIRouter(prefix="/battle-reports", tags=["battle-reports"])


class PilotSideOverride(BaseModel):
    character_id: int
    side: Literal[0, 1, 2]


class OrganizationSideOverride(BaseModel):
    organization_type: Literal["alliance", "corporation"]
    organization_id: int
    side: Literal[0, 1, 2]


class ReportRequest(BaseModel):
    character_id: int
    gap_minutes: int = 15
    seed_killmail_id: int | None = None
    side_overrides: list[PilotSideOverride] = Field(default_factory=list)
    organization_overrides: list[OrganizationSideOverride] = Field(default_factory=list)


class ShareRequest(ReportRequest):
    pass


def side_override_map(payload: ReportRequest) -> dict[int, int]:
    if len(payload.side_overrides) > 500:
        raise HTTPException(status_code=400, detail="A battle report can override at most 500 pilots")
    return {row.character_id: row.side for row in payload.side_overrides}


def organization_override_map(payload: ReportRequest) -> dict[tuple[str, int], int]:
    if len(payload.organization_overrides) > 500:
        raise HTTPException(status_code=400, detail="A battle report can override at most 500 organizations")
    return {(row.organization_type, row.organization_id): row.side for row in payload.organization_overrides}


def share_payload(row: BattleReportShare) -> dict[str, Any]:
    return {
        "id": row.id,
        "share_token": row.share_token,
        "share_url": f"{get_settings().frontend_url.rstrip('/')}/#battle-report/{row.share_token}",
        "selected_character_id": row.selected_character_id,
        "selected_character_name": row.selected_character_name,
        "view_count": row.view_count,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_viewed_at": row.last_viewed_at.isoformat() if row.last_viewed_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
    }


def require_view(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(current_user, "battle_reports", db):
        raise HTTPException(status_code=403, detail="Battle Reports permission is required")
    return current_user


@router.get("/context")
def context(current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = killboard_settings(db)
    return {
        "enabled": settings["enabled"],
        "pilots": available_report_pilots(db, current_user),
        "can_sync": can_view_section(current_user, "killboard", db),
        "default_gap_minutes": 15,
        "coverage_notice": "Battle reports use EQM's local canonical ESI killmails. zKillboard discovery is best-effort and may not contain every loss.",
    }


@router.get("/latest")
async def latest(
    character_id: int = Query(..., gt=0),
    gap_minutes: int = Query(default=15, ge=5, le=60),
    seed_killmail_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_view),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not killboard_settings(db)["enabled"]:
        raise HTTPException(status_code=409, detail="The Killboard data source is disabled")
    try:
        await refresh_killboard_entity_names(db, limit=5_000)
        return build_latest_battle_report(db, current_user, character_id=character_id, gap_minutes=gap_minutes, seed_killmail_id=seed_killmail_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/history")
def history(
    character_id: int = Query(..., gt=0),
    gap_minutes: int = Query(default=15, ge=5, le=60),
    limit: int = Query(default=50, ge=1, le=250),
    current_user: User = Depends(require_view),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not killboard_settings(db)["enabled"]:
        raise HTTPException(status_code=409, detail="The Killboard data source is disabled")
    try:
        return battle_report_history(db, current_user, character_id=character_id, gap_minutes=gap_minutes, limit=limit)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/render")
async def render(
    payload: ReportRequest,
    current_user: User = Depends(require_view),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not killboard_settings(db)["enabled"]:
        raise HTTPException(status_code=409, detail="The Killboard data source is disabled")
    try:
        await refresh_killboard_entity_names(db, limit=5_000)
        return build_latest_battle_report(
            db,
            current_user,
            character_id=payload.character_id,
            gap_minutes=payload.gap_minutes,
            seed_killmail_id=payload.seed_killmail_id,
            side_overrides=side_override_map(payload),
            organization_overrides=organization_override_map(payload),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/shares")
def list_shares(
    character_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(require_view),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(BattleReportShare).where(
        BattleReportShare.created_by_user_id == current_user.id,
        BattleReportShare.revoked_at.is_(None),
    )
    if character_id is not None:
        query = query.where(BattleReportShare.selected_character_id == character_id)
    rows = db.scalars(query.order_by(BattleReportShare.created_at.desc()).limit(100)).all()
    return [share_payload(row) for row in rows]


@router.post("/shares", status_code=201)
def create_share(
    payload: ShareRequest,
    current_user: User = Depends(require_view),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not killboard_settings(db)["enabled"]:
        raise HTTPException(status_code=409, detail="The Killboard data source is disabled")
    try:
        snapshot = build_latest_battle_report(
            db,
            current_user,
            character_id=payload.character_id,
            gap_minutes=payload.gap_minutes,
            seed_killmail_id=payload.seed_killmail_id,
            side_overrides=side_override_map(payload),
            organization_overrides=organization_override_map(payload),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if snapshot["report"] is None:
        raise HTTPException(status_code=409, detail="No cached battle is available to share for this pilot")
    row = BattleReportShare(
        share_token=secrets.token_urlsafe(32),
        created_by_user_id=current_user.id,
        selected_character_id=payload.character_id,
        selected_character_name=str(snapshot["pilot"]["name"]),
        report_payload=snapshot,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return share_payload(row)


@router.delete("/shares/{share_id}")
def revoke_share(
    share_id: int,
    current_user: User = Depends(require_view),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.get(BattleReportShare, share_id)
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Shared battle report was not found")
    if row.created_by_user_id != current_user.id and role_rank(current_user, db) < ROLE_RANK["admin"]:
        raise HTTPException(status_code=403, detail="Only the link creator or an administrator may revoke this share")
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "revoked", "id": row.id}


@router.get("/public/{share_token}")
def public_share(share_token: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.scalar(
        select(BattleReportShare).where(
            BattleReportShare.share_token == share_token,
            BattleReportShare.revoked_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Shared battle report was not found or has been revoked")
    row.view_count += 1
    row.last_viewed_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "share": {
            "selected_character_name": row.selected_character_name,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "view_count": row.view_count,
        },
        **row.report_payload,
    }
