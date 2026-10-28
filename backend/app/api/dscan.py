from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.api import local_scan as shared
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import EveSystem, User
from app.models.local_scan import LocalScanReport, ScanHighlight
from app.services import dscan, local_scan as lifecycle
from app.services.scan_threat import order_snapshot
from app.services.audit import record_audit_event
from app.services.permissions import can_view_section, quartermaster_read_only

router = APIRouter(prefix="/d-scans", tags=["d-scans"])


class DScanInput(shared.ScanInput):
    text: str = Field(min_length=1, max_length=500000)
    local_text: str = Field(default="", max_length=150000)
    manual_recons: dict[str, Annotated[int, Field(ge=0, le=1000, strict=True)]] = Field(default_factory=dict)

    @field_validator("manual_recons")
    @classmethod
    def recon_types(cls, value):
        if set(value) - set(dscan.RECONS):
            raise ValueError("Manual additions support Huginn, Lachesis, Rook and Curse only")
        return {name: value.get(name, 0) for name in dscan.RECONS}


def require_dscan(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not can_view_section(user, "dscan", db):
        raise HTTPException(403, "D-Scan permission is required")
    response.headers["Cache-Control"] = "private, no-store"
    return user


@router.get("/context")
def context(user: User = Depends(require_dscan), db: Session = Depends(get_db)):
    return {**shared.context(user=user, db=db), "max_objects": dscan.MAX_OBJECTS, "recon_types": list(dscan.RECONS)}


@router.get("/highlights")
def highlights(user: User = Depends(require_dscan), db: Session = Depends(get_db)):
    return shared.highlights(user=user, db=db)


@router.post("/highlights")
async def add_highlight(payload: shared.HighlightInput, user: User = Depends(require_dscan), db: Session = Depends(get_db)):
    return await shared.add_highlight(payload, user=user, db=db)


@router.delete("/highlights/{highlight_id}")
def remove_highlight(highlight_id: int, user: User = Depends(require_dscan), db: Session = Depends(get_db)):
    return shared.remove_highlight(highlight_id, user=user, db=db)


@router.post("", status_code=201)
async def generate(payload: DScanInput, request: Request, user: User = Depends(require_dscan), db: Session = Depends(get_db)):
    if quartermaster_read_only(user, db):
        raise HTTPException(403, "This account can view reports but cannot generate them")
    try:
        objects, ignored = dscan.parse(payload.text)
        names = lifecycle.parse_local(payload.local_text) if payload.local_text.strip() else None
        snapshot = dscan.summarize(db, objects, payload.manual_recons)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if payload.corporation_id is not None and payload.corporation_id not in {c[0] for c in lifecycle.corporations(db, user)}:
        raise HTTPException(403, "Choose a corporation belonging to one of your linked characters")
    system = db.get(EveSystem, payload.system_id) if payload.system_id else None
    if payload.system_id is not None and system is None:
        raise HTTPException(422, "Select a valid solar system from search results")
    system_snapshot = {"id": system.system_id, "name": system.name} if system else None
    if user.id in shared._generating or len(shared._generating) >= 4:
        raise HTTPException(429, "A scan is already generating or the scan queue is busy; retry shortly")
    if (db.scalar(select(func.count()).select_from(LocalScanReport).where(
        LocalScanReport.created_by_user_id == user.id,
        LocalScanReport.created_at > lifecycle.now() - timedelta(minutes=1))) or 0) >= 10:
        raise HTTPException(429, "Generate at most 10 scan reports per minute")
    shared._generating.add(user.id)
    source = None
    try:
        local = None
        if names:
            source = shared.source_factory()
            try:
                local = await asyncio.wait_for(lifecycle.enrich(names, source), timeout=90)
            except asyncio.TimeoutError as error:
                raise HTTPException(504, "Local pilot lookup timed out. No report was saved; retry shortly.") from error
        db.refresh(user)
        if user.deleted_at is not None or not can_view_section(user, "dscan", db) or quartermaster_read_only(user, db):
            raise HTTPException(403, "D-Scan generation is no longer allowed for this account")
        if payload.corporation_id is not None and payload.corporation_id not in {c[0] for c in lifecycle.corporations(db, user)}:
            raise HTTPException(403, "The selected corporation is no longer linked to your account")
        if local:
            targets = {(h.kind, h.eve_id) for h in db.scalars(select(ScanHighlight).where(ScanHighlight.user_id == user.id))}
            for pilot in local["pilots"]:
                pilot["alliance_highlighted"] = ("alliance", pilot["alliance_id"]) in targets
                pilot["highlighted"] = pilot["alliance_highlighted"] or ("corporation", pilot["corporation_id"]) in targets
            local["highlighted_count"] = sum(p["highlighted"] for p in local["pilots"])
            local["system"] = system_snapshot
        snapshot.update(local_scan=local, system=system_snapshot, ignored=ignored, input_count=len(objects) + len(ignored))
        if ignored:
            snapshot["warnings"].append(f"{len(ignored)} input rows could not be parsed; line numbers and reasons are listed separately.")
        at = lifecycle.now()
        lifetime = lifecycle.RETENTIONS[payload.retention]
        from app.services.report_identity import report_identity
        creator, anonymous = report_identity(db, user, payload.anonymous)
        row = LocalScanReport(is_private=payload.is_private, anonymous=payload.anonymous, report_kind="dscan", token=secrets.token_urlsafe(32), created_by_user_id=user.id,
            corporation_id=payload.corporation_id, account_name=creator, application_version=request.app.version,
            created_at=at, expires_at=at + timedelta(seconds=lifetime) if lifetime is not None else None,
            retention=payload.retention, payload=snapshot)
        db.add(row)
        record_audit_event(db, event_kind="intel", title="Directional scan generated", actor_user=user,
                           body=f"objects={snapshot['object_count']}; ships={snapshot['ship_count']}; retention={payload.retention}")
        db.commit()
        return {**shared.metadata(row), **order_snapshot(snapshot)}
    finally:
        shared._generating.discard(user.id)
        if source:
            await source.close()


@router.get("/reports")
def reports(from_at: datetime | None = None, to_at: datetime | None = None,
            offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
            user: User = Depends(require_dscan), db: Session = Depends(get_db)):
    return shared.report_listing(user, db, from_at, to_at, offset, limit, "dscan")


@router.post("/reports/delete")
def delete_reports(payload: shared.DeleteInput, user: User = Depends(require_dscan), db: Session = Depends(get_db)):
    return shared.delete_scoped_reports(payload, user, db, "dscan")


@router.get("/public/{token}")
def public_report(token: str, response: Response, db: Session = Depends(get_db)):
    shared.public_headers(response)
    row = shared.public_row(db, token, "dscan")
    return {**shared.metadata(row), **order_snapshot(row.payload)}


@router.get("/public/{token}/pdf")
async def export_pdf(token: str, db: Session = Depends(get_db)):
    from app.services.dscan_pdf import report_images, render_pdf
    row = shared.public_row(db, token, "dscan")
    snapshot = {**shared.metadata(row), **order_snapshot(row.payload)}
    images = await report_images(snapshot)
    content = await run_in_threadpool(render_pdf, snapshot, images)
    db.expire_all()
    shared.public_row(db, token, "dscan")
    response = Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="eqm-dscan-{token[:10]}.pdf"'})
    shared.public_headers(response)
    return response


@router.get("/reports/{token}")
def saved_report(token: str, response: Response, user: User = Depends(require_dscan), db: Session = Depends(get_db)):
    shared.public_headers(response)
    row = shared.authenticated_row(db, token, user, "dscan")
    return {**shared.metadata(row), **order_snapshot(row.payload)}

@router.get("/reports/{token}/pdf")
async def saved_pdf(token: str, user: User = Depends(require_dscan), db: Session = Depends(get_db)):
    return await shared.authenticated_pdf(db, token, user, "dscan")
