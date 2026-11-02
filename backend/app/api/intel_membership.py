from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.api.intel import access
from app.db.session import get_db
from app.domain.intel import utc
from app.models import User
from app.services.intel_reports import subject_or_404
from app.services.intel_membership import organization, request_refresh, monitor_payload, now
from app.services.intel_membership_report import read
from app.services.audit import record_audit_event

router = APIRouter(prefix="/intel", tags=["intel"], dependencies=[Depends(access)])


class MonitoringInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool


@router.get("/subjects/{subject_id}/membership")
def membership(subject_id: int, from_at: datetime | None = None, to_at: datetime | None = None,
               db: Session = Depends(get_db)):
    subject = subject_or_404(db, subject_id)
    organization(subject)
    end = utc(to_at) if to_at else now()
    start = utc(from_at) if from_at else end - timedelta(days=90)
    if start >= end or end - start > timedelta(days=20000):
        raise HTTPException(422, "Choose a positive membership window of at most 20,000 days")
    return read(db, subject, start, end)


@router.post("/subjects/{subject_id}/membership/refresh", status_code=202)
def refresh(subject_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = request_refresh(db, subject_or_404(db, subject_id), user)
    record_audit_event(db, event_kind="intel", title="Organization membership refresh requested",
                       actor_user=user, body=f"subject={subject_id}")
    db.commit()
    return monitor_payload(row)


@router.put("/subjects/{subject_id}/membership/monitoring")
def monitoring(subject_id: int, payload: MonitoringInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = request_refresh(db, subject_or_404(db, subject_id), user, payload.enabled)
    record_audit_event(db, event_kind="intel", title="Organization membership monitoring changed",
                       actor_user=user, body=f"subject={subject_id}; enabled={payload.enabled}")
    db.commit()
    return monitor_payload(row)
