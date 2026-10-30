from __future__ import annotations

from datetime import datetime, timezone, timedelta
import secrets
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, func, delete
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import BattleReportShare, User
from app.services.battle_reports import available_report_pilots, battle_report_history, build_latest_battle_report
from app.services import battle_report_management as management
from app.services import battle_report_search as search_service
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
    anonymous: bool = False
    is_private: bool = False
    retention: Literal["30m","1h","2h","12h","24h","3days","7days","30days","permanent"] = "24h"
    character_id: int
    gap_minutes: int = 15
    seed_killmail_id: int | None = None
    side_overrides: list[PilotSideOverride] = Field(default_factory=list)
    organization_overrides: list[OrganizationSideOverride] = Field(default_factory=list)


class ShareRequest(ReportRequest):
    corporation_id: int | None = Field(default=None, gt=0)


def side_override_map(payload: ReportRequest) -> dict[int, int]:
    if len(payload.side_overrides) > 500:
        raise HTTPException(status_code=400, detail="A battle report can override at most 500 pilots")
    return {row.character_id: row.side for row in payload.side_overrides}


def organization_override_map(payload: ReportRequest) -> dict[tuple[str, int], int]:
    if len(payload.organization_overrides) > 500:
        raise HTTPException(status_code=400, detail="A battle report can override at most 500 organizations")
    return {(row.organization_type, row.organization_id): row.side for row in payload.organization_overrides}


def creator_label(db, row):
    from app.services.report_identity import report_identity
    creator = db.get(User, row.created_by_user_id) if row.created_by_user_id else None
    return report_identity(db, creator, row.anonymous)[0] if creator and creator.deleted_at is None else "Anonymous"

def share_payload(row: BattleReportShare) -> dict[str, Any]:
    from sqlalchemy.orm import object_session
    return {
        "id": row.id,
        "corporation_id": None if row.anonymous or row.is_private else row.corporation_id,
        "application_version": row.application_version,
        "share_token": row.share_token,
        "is_private": row.is_private, "anonymous": row.anonymous, "creator_name": creator_label(object_session(row), row), "expires_at": management.utc(row.expires_at).isoformat() if row.expires_at else None, "share_url": None if row.is_private else f"{get_settings().frontend_url.rstrip('/')}/#battle-report/{row.share_token}",
        "selected_character_id": row.selected_character_id,
        "selected_character_name": row.selected_character_name,
        "view_count": row.view_count,
        "created_at": management.utc(row.created_at).isoformat() if row.created_at else None,
        "last_viewed_at": management.utc(row.last_viewed_at).isoformat() if row.last_viewed_at else None,
        "revoked_at": management.utc(row.revoked_at).isoformat() if row.revoked_at else None,
    }


def require_view(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(current_user, "battle_reports", db):
        raise HTTPException(status_code=403, detail="Battle Reports permission is required")
    return current_user


@router.get("/context")
def context(current_user: User = Depends(require_view), db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.services.report_identity import report_identity
    settings = killboard_settings(db)
    return {**management.management_context(db, current_user), "creator_name": report_identity(db,current_user)[0],
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
        or_(BattleReportShare.expires_at.is_(None), BattleReportShare.expires_at > datetime.now(timezone.utc)),
    )
    if character_id is not None:
        query = query.where(BattleReportShare.selected_character_id == character_id)
    rows = db.scalars(query.order_by(BattleReportShare.created_at.desc()).limit(100)).all()
    return [share_payload(row) for row in rows]



@router.get("/report-search-options")
def report_search_options(class_key:str=Query('',max_length=40,pattern=r'^(|capitals|deployables|structures|g:[1-9][0-9]{0,9})$'),
    current_user:User=Depends(require_view),db:Session=Depends(get_db)):
    return search_service.options(db,class_key)


@router.get("/reports")
def managed_reports(
    scope: Literal["own", "managed"] = "own",
    corporation_id: int | None = Query(default=None, gt=0),
    from_at: datetime | None = None, to_at: datetime | None = None,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100),
    response: Response = None,
    search: search_service.SearchFilters = Depends(),
    current_user: User = Depends(require_view), db: Session = Depends(get_db),
):
    from app.api.local_scan import public_headers
    public_headers(response if response is not None else Response())
    conditions = management.filters(db, current_user, scope, corporation_id, from_at, to_at)
    conditions.extend(search_service.conditions(db,search))
    rows = db.scalars(select(BattleReportShare).where(*conditions)
        .order_by(BattleReportShare.created_at.desc(), BattleReportShare.id.desc()).offset(offset).limit(limit)).all()
    return {"reports": [{**share_payload(row), "is_owner": row.created_by_user_id == current_user.id,"battle_summary":search_service.summary(row.report_payload,search.side)} for row in rows],
        "total": db.scalar(select(func.count()).select_from(BattleReportShare).where(*conditions))}


@router.post("/reports/delete-preview")
def preview_delete_reports(payload: management.DeleteReportsInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)):
    # Freeze the upper generation boundary so confirmation cannot sweep up newly saved reports.
    payload = payload.model_copy(update={"created_before": min(management.utc(payload.created_before), management.now()) if payload.created_before else management.now()})
    count = db.scalar(select(func.count()).select_from(BattleReportShare).where(*management.delete_filters(db, current_user, payload)))
    return {"count": count, "selection": payload.model_dump(mode="json")}


@router.post("/reports/delete")
def delete_reports(payload: management.DeleteReportsInput, current_user: User = Depends(require_view), db: Session = Depends(get_db)):
    from app.services.audit import record_audit_event
    count = db.execute(delete(BattleReportShare).where(*management.delete_filters(db, current_user, payload))
        .execution_options(synchronize_session="fetch")).rowcount
    record_audit_event(db, event_kind="intel", title="Battle reports deleted", actor_user=current_user,
        body=f"count={count}; scope={payload.scope}; mode={'individual' if payload.ids else 'date_range' if payload.from_at else 'all_in_scope'}")
    db.commit()
    return {"deleted": count}


@router.post("/shares", status_code=201)
def create_share(
    payload: ShareRequest,
    request: Request,
    current_user: User = Depends(require_view),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.corporation_id is not None and payload.corporation_id not in {cid for cid, _ in management.corporations(db, current_user)}:
        raise HTTPException(422, "Choose a corporation belonging to one of your linked characters")
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
    from app.services.report_identity import report_identity
    from app.services.local_scan import RETENTIONS
    creator, _ = report_identity(db, current_user, payload.anonymous)
    lifetime = RETENTIONS[payload.retention]
    row = BattleReportShare(
        is_private=payload.is_private, anonymous=payload.anonymous, creator_name=creator,
        application_version=request.app.version,
        expires_at=datetime.now(timezone.utc)+timedelta(seconds=lifetime) if lifetime else None,
        share_token=secrets.token_urlsafe(32),
        created_by_user_id=current_user.id,
        corporation_id=None if payload.is_private else payload.corporation_id,
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
    row = db.scalar(select(BattleReportShare).where(BattleReportShare.id == share_id,
        BattleReportShare.revoked_at.is_(None), management.management_scope(db, current_user)))
    if row is None:
        raise HTTPException(404, "Saved report unavailable")
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "revoked", "id": row.id}


@router.get("/public/{share_token}")
def public_share(share_token: str, response: Response = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.api.local_scan import public_headers
    public_headers(response if response is not None else Response())
    row = db.scalar(
        select(BattleReportShare).where(
            BattleReportShare.share_token == share_token,
            BattleReportShare.is_private.is_(False),
            or_(BattleReportShare.expires_at.is_(None), BattleReportShare.expires_at > datetime.now(timezone.utc)),
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
            "creator_name": creator_label(db, row), "anonymous": row.anonymous,
            "application_version": row.application_version, "is_private": row.is_private,
            "expires_at": management.utc(row.expires_at).isoformat() if row.expires_at else None,
            "selected_character_name": row.selected_character_name,
            "created_at": management.utc(row.created_at).isoformat() if row.created_at else None,
            "view_count": row.view_count,
        },
        **row.report_payload,
    }


@router.get("/shares/{share_id}")
def own_saved_share(share_id: int, response: Response, current_user: User = Depends(require_view), db: Session = Depends(get_db)):
    from app.api.local_scan import public_headers
    public_headers(response)
    row = db.scalar(select(BattleReportShare).where(BattleReportShare.id == share_id,
        management.management_scope(db, current_user), BattleReportShare.revoked_at.is_(None),
        or_(BattleReportShare.expires_at.is_(None), BattleReportShare.expires_at > datetime.now(timezone.utc))))
    if row is None: raise HTTPException(404, "Saved report unavailable")
    return {"share": share_payload(row), **row.report_payload}


def export_row(db,token,user=None):
    filters=[BattleReportShare.share_token==token,BattleReportShare.revoked_at.is_(None),
        or_(BattleReportShare.expires_at.is_(None),BattleReportShare.expires_at>datetime.now(timezone.utc))]
    if user is None:filters.append(BattleReportShare.is_private.is_(False))
    else:filters.append(management.management_scope(db,user))
    row=db.scalar(select(BattleReportShare).where(*filters))
    if row is None:raise HTTPException(404,"Saved report unavailable")
    return row

async def battle_pdf(db,token,user=None):
    from app.services.battle_report_pdf import render_pdf
    from app.api.local_scan import public_headers
    from starlette.concurrency import run_in_threadpool
    row=export_row(db,token,user)
    content=await run_in_threadpool(render_pdf,row.report_payload,creator_label(db,row),row.application_version,management.utc(row.created_at).isoformat())
    db.expire_all()
    if user:
        db.refresh(user)
        if user.deleted_at is not None or not can_view_section(user,"battle_reports",db):raise HTTPException(403,"Report access changed")
    export_row(db,token,user)
    response=Response(content,media_type="application/pdf",headers={"Content-Disposition":'attachment; filename="eqm-battle-report.pdf"'})
    public_headers(response)
    return response

@router.get("/public/{share_token}/pdf")
async def public_pdf(share_token:str,db:Session=Depends(get_db)):
    return await battle_pdf(db,share_token)

@router.get("/shares/{share_id}/pdf")
async def saved_pdf(share_id:int,user:User=Depends(require_view),db:Session=Depends(get_db)):
    row=db.get(BattleReportShare,share_id)
    if row is None:raise HTTPException(404,"Saved report unavailable")
    return await battle_pdf(db,row.share_token,user)
