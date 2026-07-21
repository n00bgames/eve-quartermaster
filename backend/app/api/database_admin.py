from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app.api.auth import get_current_user, require_host
from app.core.security import verify_password
from app.db.session import engine, get_db
from app.models import User
from app.services.database_admin import (
    DatabaseAdminError,
    MAX_BACKUP_BYTES,
    clear_database,
    create_backup,
    current_revision,
    database_status,
    remove_backup,
    restore_backup,
)

router = APIRouter(prefix="/database", tags=["database"])


def host_user(current_user: User = Depends(get_current_user)) -> User:
    require_host(current_user)
    return current_user


def require_current_password(user: User, password: str) -> None:
    if not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current host password is incorrect.")


@router.get("/status")
def status(_: User = Depends(host_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return database_status(db)
    except DatabaseAdminError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/export")
def export_database(_: User = Depends(host_user), db: Session = Depends(get_db)) -> FileResponse:
    try:
        archive_path, filename = create_backup(db)
    except DatabaseAdminError as exc:
        raise HTTPException(status_code=500, detail=f"Database export failed: {exc}") from exc
    return FileResponse(
        archive_path,
        filename=filename,
        media_type="application/vnd.eqm.database-backup",
        background=BackgroundTask(remove_backup, archive_path),
    )


@router.post("/import")
async def import_database(
    request: Request,
    confirmation: str = Header(default="", alias="X-EQM-Confirmation"),
    current_password: str = Header(default="", alias="X-EQM-Password"),
    current_user: User = Depends(host_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if confirmation != "RESTORE EQM DATABASE":
        raise HTTPException(status_code=400, detail='Type "RESTORE EQM DATABASE" to confirm.')
    require_current_password(current_user, current_password)

    expected_revision = current_revision(db)
    host_fallback = {
        "email": current_user.email,
        "display_name": current_user.display_name,
        "password_hash": current_user.password_hash,
        "role": "host",
        "timezone": current_user.timezone,
    }
    work_dir = Path(tempfile.mkdtemp(prefix="eqm-restore-"))
    archive_path = work_dir / "upload.eqmbackup"
    total = 0
    try:
        with archive_path.open("wb") as target:
            async for chunk in request.stream():
                total += len(chunk)
                if total > MAX_BACKUP_BYTES:
                    raise HTTPException(status_code=413, detail="Backup exceeds the 8 GiB upload limit.")
                target.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="Choose an EQM backup file.")

        db.rollback()
        db.close()
        engine.dispose()
        return restore_backup(archive_path, expected_revision, host_fallback)
    except DatabaseAdminError as exc:
        raise HTTPException(status_code=400, detail=f"Database import failed: {exc}") from exc
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@router.post("/clear")
def clear_all_data(
    payload: dict[str, Any],
    current_user: User = Depends(host_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if str(payload.get("confirmation") or "") != "CLEAR EQM DATABASE":
        raise HTTPException(status_code=400, detail='Type "CLEAR EQM DATABASE" to confirm.')
    require_current_password(current_user, str(payload.get("current_password") or ""))
    try:
        return clear_database(db, current_user.id)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database clear failed: {exc}") from exc
