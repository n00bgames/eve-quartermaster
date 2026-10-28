from __future__ import annotations

import asyncio
import re
import secrets
from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.api.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import User, EveSystem, EveCharacter, EsiToken
from app.models.local_scan import LocalScanReport, ScanHighlight
from sqlalchemy.exc import IntegrityError
from app.services import local_scan as service
from app.services.audit import record_audit_event
from app.services.permissions import ROLE_RANK, base_role_for, can_view_section, role_rank, quartermaster_read_only

router = APIRouter(prefix="/local-scans", tags=["local-scans"])
_generating: set[int] = set()


class ScanInput(BaseModel):
    text: str = Field(min_length=1, max_length=150000)
    retention: Literal["30m", "1h", "2h", "12h", "24h", "3days", "7days", "30days", "permanent"] = "24h"
    corporation_id: int | None = Field(default=None, gt=0)
    system_id: int | None = Field(default=None, gt=0)


class HighlightInput(BaseModel):
    kind: Literal["corporation", "alliance"]
    name: str = Field(min_length=1, max_length=255)


class DeleteInput(BaseModel):
    tokens: list[str] = Field(default_factory=list, max_length=500)
    from_at: datetime | None = None
    to_at: datetime | None = None
    all_in_scope: bool = False

    @model_validator(mode="after")
    def one_mode(self):
        dates = self.from_at is not None or self.to_at is not None
        if int(bool(self.tokens)) + int(dates) + int(self.all_in_scope) != 1:
            raise ValueError("Choose report IDs, a complete date range, or all reports in scope.")
        if dates and (self.from_at is None or self.to_at is None or service.utc(self.from_at) >= service.utc(self.to_at)):
            raise ValueError("Choose a start before the end of the generation-date range.")
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{32,48}", t) for t in self.tokens):
            raise ValueError("Invalid report identifier.")
        return self


def require_scan(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not can_view_section(user, "local_scan", db):
        raise HTTPException(403, "Local Scan permission is required")
    response.headers["Cache-Control"] = "private, no-store"
    return user


def metadata(row):
    return {"token": row.token, "share_url": f"{get_settings().frontend_url.rstrip('/')}/#local-scan/{row.token}",
            "created_at": service.utc(row.created_at).isoformat(),
            "expires_at": service.utc(row.expires_at).isoformat() if row.expires_at else None,
            "retention": row.retention, "account_name": row.account_name,
            "corporation_id": row.corporation_id, "application_version": row.application_version,
            "character_count": row.payload.get("character_count", 0), "input_count": row.payload.get("input_count", 0)}


@router.get("/context")
def context(user: User = Depends(require_scan), db: Session = Depends(get_db)):
    rank = role_rank(user, db)
    return {"retentions": list(service.RETENTIONS), "max_pilots": service.MAX_PILOTS,
            "corporations": [{"id": cid, "name": name} for cid, name in service.corporations(db, user)],
            "can_generate": not quartermaster_read_only(user, db),
            "management_scope": "all reports" if rank >= ROLE_RANK["admin"] else
                "your reports and your corporations' reports" if rank >= ROLE_RANK["director"] else "your reports"}


def source_factory():
    return service.ScanSource()


@router.get("/destination-characters")
def destination_characters(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.api.esi import token_scopes
    if not can_view_section(user, "navigation", db):
        raise HTTPException(403, "Navigation permission is required")
    rows = db.execute(select(EsiToken, EveCharacter).join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.user_id == user.id, EveCharacter.owner_user_id == user.id, EsiToken.revoked_at.is_(None))
        .order_by(EveCharacter.name, EsiToken.id.desc())).all()
    seen = set()
    result = []
    for token, character in rows:
        if character.character_id not in seen and "esi-ui.write_waypoint.v1" in token_scopes(token):
            result.append({"token_id": token.id, "character_id": character.character_id, "name": character.name})
            seen.add(character.character_id)
    return result


def highlight_payload(row):
    return {"id": row.id, "kind": row.kind, "eve_id": row.eve_id, "name": row.name}


@router.get("/highlights")
def highlights(user: User = Depends(require_scan), db: Session = Depends(get_db)):
    return [highlight_payload(r) for r in db.scalars(select(ScanHighlight).where(
        ScanHighlight.user_id == user.id).order_by(ScanHighlight.kind, ScanHighlight.name))]


@router.post("/highlights")
async def add_highlight(payload: HighlightInput, user: User = Depends(require_scan), db: Session = Depends(get_db)):
    if (db.scalar(select(func.count()).select_from(ScanHighlight).where(ScanHighlight.user_id == user.id)) or 0) >= 200:
        raise HTTPException(422, "Keep at most 200 highlighted organizations; remove one before adding another")
    source = source_factory()
    try:
        result = await asyncio.wait_for(source.resolve([payload.name.strip()]), timeout=30)
    except Exception as error:
        raise HTTPException(502, "Organization name lookup is unavailable; retry shortly") from error
    finally:
        await source.close()
    matches = [r for r in result.get(payload.kind + "s", []) if r.get("name", "").casefold() == payload.name.strip().casefold()]
    if len(matches) != 1:
        raise HTTPException(422, f"Enter the exact {payload.kind} name")
    found = matches[0]
    existing = db.scalar(select(ScanHighlight).where(ScanHighlight.user_id == user.id,
        ScanHighlight.kind == payload.kind, ScanHighlight.eve_id == found["id"]))
    if existing:
        return highlight_payload(existing)
    row = ScanHighlight(user_id=user.id, kind=payload.kind, eve_id=found["id"], name=found["name"])
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.scalar(select(ScanHighlight).where(ScanHighlight.user_id == user.id,
            ScanHighlight.kind == payload.kind, ScanHighlight.eve_id == found["id"]))
        if row is None:
            raise HTTPException(409, "The highlight list changed; reload it and retry")
    return highlight_payload(row)


@router.delete("/highlights/{highlight_id}")
def remove_highlight(highlight_id: int, user: User = Depends(require_scan), db: Session = Depends(get_db)):
    db.execute(delete(ScanHighlight).where(ScanHighlight.id == highlight_id, ScanHighlight.user_id == user.id))
    db.commit()
    return {"deleted": True}


@router.post("", status_code=201)
async def generate(payload: ScanInput, request: Request, user: User = Depends(require_scan), db: Session = Depends(get_db)):
    try:
        names = service.parse_local(payload.text)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if payload.corporation_id is not None and payload.corporation_id not in {r[0] for r in service.corporations(db, user)}:
        raise HTTPException(403, "Choose a corporation belonging to one of your linked characters")
    system = db.get(EveSystem, payload.system_id) if payload.system_id else None
    if payload.system_id is not None and system is None:
        raise HTTPException(422, "Select a valid solar system from search results")
    system_snapshot = {"id": system.system_id, "name": system.name} if system else None
    if user.id in _generating or len(_generating) >= 4:
        raise HTTPException(429, "A scan is already generating or the scan queue is busy; retry shortly")
    if (db.scalar(select(func.count()).select_from(LocalScanReport).where(
        LocalScanReport.created_by_user_id == user.id, LocalScanReport.created_at > service.now() - timedelta(minutes=1))) or 0) >= 10:
        raise HTTPException(429, "Generate at most 10 local-scan reports per minute")
    source = source_factory()
    _generating.add(user.id)
    try:
        try:
            snapshot = await asyncio.wait_for(service.enrich(names, source), timeout=90)
        except asyncio.TimeoutError as error:
            raise HTTPException(504, "Public ESI lookup timed out. No report was saved; retry shortly.") from error
        if not snapshot["character_count"]:
            raise HTTPException(422, "No pilot names could be resolved through public ESI. Check the pasted names or retry if ESI is unavailable.")
        snapshot["system"] = system_snapshot
        # Re-evaluate ownership and permissions after the network work.
        db.refresh(user)
        if user.deleted_at is not None or not can_view_section(user, "local_scan", db) or quartermaster_read_only(user, db):
            raise HTTPException(403, "Local Scan generation is no longer allowed for this account")
        if payload.corporation_id is not None and payload.corporation_id not in {r[0] for r in service.corporations(db, user)}:
            raise HTTPException(403, "The selected corporation is no longer linked to your account")
        at = service.now()
        targets = {(r.kind, r.eve_id) for r in db.scalars(select(ScanHighlight).where(ScanHighlight.user_id == user.id))}
        for pilot in snapshot["pilots"]:
            pilot["alliance_highlighted"] = ("alliance", pilot["alliance_id"]) in targets
            pilot["highlighted"] = pilot["alliance_highlighted"] or ("corporation", pilot["corporation_id"]) in targets
        snapshot["highlighted_count"] = sum(p["highlighted"] for p in snapshot["pilots"])
        lifetime = service.RETENTIONS[payload.retention]
        row = LocalScanReport(token=secrets.token_urlsafe(32), created_by_user_id=user.id,
            corporation_id=payload.corporation_id, account_name=user.display_name, application_version=request.app.version,
            created_at=at, expires_at=at + timedelta(seconds=lifetime) if lifetime is not None else None,
            retention=payload.retention, payload=snapshot)
        db.add(row)
        record_audit_event(db, event_kind="intel", title="Public local scan generated", actor_user=user,
                           body=f"characters={snapshot['character_count']}; retention={payload.retention}")
        db.commit()
        return {**metadata(row), **snapshot}
    finally:
        _generating.discard(user.id)
        await source.close()


@router.get("/reports")
def reports(from_at: datetime | None = None, to_at: datetime | None = None,
            offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
            user: User = Depends(require_scan), db: Session = Depends(get_db)):
    filters = [service.management_scope(db, user), service.active_reports()]
    if from_at:
        filters.append(LocalScanReport.created_at >= service.utc(from_at))
    if to_at:
        filters.append(LocalScanReport.created_at < service.utc(to_at))
    if from_at and to_at and service.utc(from_at) >= service.utc(to_at):
        raise HTTPException(422, "Start must precede end")
    rows = db.scalars(select(LocalScanReport).where(*filters)
        .order_by(LocalScanReport.created_at.desc(), LocalScanReport.token).offset(offset).limit(limit)).all()
    return {"reports": [metadata(r) for r in rows],
            "total": db.scalar(select(func.count()).select_from(LocalScanReport).where(*filters))}


@router.post("/reports/delete")
def delete_reports(payload: DeleteInput, user: User = Depends(require_scan), db: Session = Depends(get_db)):
    filters = [service.management_scope(db, user)]
    if payload.tokens:
        filters.append(LocalScanReport.token.in_(payload.tokens))
    elif payload.from_at is not None:
        filters.extend([LocalScanReport.created_at >= service.utc(payload.from_at), LocalScanReport.created_at < service.utc(payload.to_at)])
    count = db.execute(delete(LocalScanReport).where(*filters)).rowcount
    record_audit_event(db, event_kind="intel", title="Local scan reports deleted", actor_user=user,
        body=f"count={count}; mode={'individual' if payload.tokens else 'date_range' if payload.from_at else 'all_in_scope'}")
    db.commit()
    return {"deleted": count}


def public_row(db, token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(404, "Report not found or expired", headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow, noarchive"})
    row = db.scalar(select(LocalScanReport).where(LocalScanReport.token == token, service.active_reports()))
    if row is None:
        raise HTTPException(404, "Report not found or expired", headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow, noarchive"})
    return row


def public_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Referrer-Policy"] = "no-referrer"


@router.get("/public/{token}")
def public_report(token: str, response: Response, db: Session = Depends(get_db)):
    public_headers(response)
    row = public_row(db, token)
    return {**metadata(row), **row.payload}


@router.get("/public/{token}/pdf")
async def export_pdf(token: str, db: Session = Depends(get_db)):
    from app.services.local_scan_pdf import logo_images, render_pdf
    row = public_row(db, token)
    snapshot = {**metadata(row), **row.payload}
    logos = await logo_images(snapshot)
    content = await run_in_threadpool(render_pdf, snapshot, logos)
    # Do not serve a report that expired or was deleted while the PDF was rendered.
    db.expire_all()
    public_row(db, token)
    response = Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="eqm-local-scan-{token[:10]}.pdf"'})
    public_headers(response)
    return response
