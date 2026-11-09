from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.local_scan import authenticated_row, require_scan
from app.api.intel import access as intel_access
from app.db.session import get_db
from app.models import User
from app.services import character_notes as service
from app.services.audit import record_audit_event

router = APIRouter(tags=["character-notes"])


class ScanNoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=5000)
    is_private: bool = True
    request_id: UUID


@router.get("/intel/notes/search")
def search(q: str = Query("", max_length=5000), offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
           user: User = Depends(intel_access), db: Session = Depends(get_db)):
    return service.search(db, user, q, offset, limit)


@router.get("/local-scans/reports/{token}/notes")
def report_notes(token: str, user: User = Depends(require_scan), db: Session = Depends(get_db)):
    service.require_notes(db, user)
    row = authenticated_row(db, token, user)
    return {"characters": service.scan_notes(db, user, row)}


@router.post("/local-scans/reports/{token}/notes")
def add_note(token: str, payload: ScanNoteInput, user: User = Depends(require_scan), db: Session = Depends(get_db)):
    service.require_notes(db, user, write=True)
    row = authenticated_row(db, token, user)
    result = service.add_scan_note(db, user, row, payload.body, payload.is_private, payload.request_id)
    if result["created"]:
        record_audit_event(db, event_kind="intel", title="Local scan character notes added", actor_user=user,
            body=f"batch={result['batch_id']}; characters={result['character_count']}; private={payload.is_private}")
    db.commit()
    return result
