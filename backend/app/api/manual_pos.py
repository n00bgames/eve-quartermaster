"""Owner-only manual POS CRUD. Mounted under Structures' section permission."""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.models.manual_pos import ManualPos

router = APIRouter(prefix="/manual-pos")
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]
Quantity = Annotated[int, Field(strict=True, ge=0, le=2_000_000_000)]
Rate = Annotated[float, Field(ge=0.01, le=100_000, allow_inf_nan=False)]


def utcnow():
    return datetime.now(timezone.utc)


class Reading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    tower_type: Name
    corporation_name: ShortText = ""
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=240)] = ""
    state: Literal["online", "offline", "reinforced", "unknown"]
    fuel_blocks: Quantity | None = None
    fuel_per_hour: Rate
    stront_units: Quantity | None = None
    stront_per_hour: Rate
    observed_at: AwareDatetime
    reinforced_until: AwareDatetime | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] = ""

    @field_validator("observed_at", "reinforced_until")
    @classmethod
    def normalize_utc(cls, value):
        return value.astimezone(timezone.utc) if value is not None else None

    @model_validator(mode="after")
    def validate_times(self):
        earliest = datetime(2003, 1, 1, tzinfo=timezone.utc)
        if not earliest <= self.observed_at <= utcnow() + timedelta(minutes=5):
            raise ValueError("Reading time must be in the past or within five minutes of now")
        if self.reinforced_until is not None:
            if self.state != "reinforced":
                raise ValueError("Reinforcement end requires the Reinforced state")
            if not self.observed_at <= self.reinforced_until <= datetime(2100, 1, 1, tzinfo=timezone.utc):
                raise ValueError("Reinforcement end must follow the reading time and be before 2100")
        return self


class CreateReading(Reading):
    id: UUID


class UpdateReading(Reading):
    version: Annotated[int, Field(strict=True, ge=1)]


FIELDS = tuple(Reading.model_fields)


def iso(value):
    # SQLite returns naive datetimes; stored dates always represent UTC.
    return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat() if value else None


def serialize(row):
    result = {key: getattr(row, key) for key in FIELDS}
    for key in ("observed_at", "reinforced_until"):
        result[key] = iso(result[key])
    return {"id": row.id, **result, "version": row.version, "created_at": iso(row.created_at),
            "updated_at": iso(row.updated_at), "source": "manual"}


def owned(db, user, record_id):
    row = db.scalar(select(ManualPos).where(ManualPos.id == str(record_id), ManualPos.owner_user_id == user.id))
    if row is None:
        raise HTTPException(404, "Manual POS was not found")
    return row


@router.get("")
def listing(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ManualPos).where(ManualPos.owner_user_id == user.id)
                      .order_by(ManualPos.name, ManualPos.id))
    return {"rows": [serialize(row) for row in rows]}


def replay(existing, body, user, response):
    if existing.owner_user_id != user.id:
        raise HTTPException(409, "Choose a new record ID and retry")
    expected = body.model_dump(exclude={"id"})
    for key in ("observed_at", "reinforced_until"):
        expected[key] = iso(expected[key])
    current = serialize(existing)
    if any(current[key] != expected[key] for key in FIELDS):
        raise HTTPException(409, "This record was already saved with different values. Cancel and reload records.")
    response.status_code = 200
    return current


@router.post("", status_code=201)
def create(body: CreateReading, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Client-generated UUID makes a timed-out create safely retryable.
    existing = db.get(ManualPos, str(body.id))
    if existing is not None:
        return replay(existing, body, user, response)
    at = utcnow()
    row = ManualPos(id=str(body.id), owner_user_id=user.id, **body.model_dump(exclude={"id"}),
                    version=1, created_at=at, updated_at=at)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(ManualPos, str(body.id))
        if existing is None:
            raise
        return replay(existing, body, user, response)
    db.refresh(row)
    return serialize(row)


@router.put("/{record_id}")
def replace(record_id: UUID, body: UpdateReading, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned(db, user, record_id)
    result = db.execute(update(ManualPos).where(ManualPos.id == str(record_id), ManualPos.owner_user_id == user.id,
        ManualPos.version == body.version).values(**body.model_dump(exclude={"version"}),
        version=body.version + 1, updated_at=utcnow()).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This POS changed in another tab. Reload before editing again.")
    from app.services.structure_timers import sync_manual
    sync_manual(db, user.id, str(record_id))
    db.commit()
    db.expire_all()
    return serialize(owned(db, user, record_id))


@router.delete("/{record_id}")
def remove(record_id: UUID, version: Annotated[int, Query(ge=1)], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned(db, user, record_id)
    result = db.execute(delete(ManualPos).where(ManualPos.id == str(record_id), ManualPos.owner_user_id == user.id,
        ManualPos.version == version).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "This POS changed in another tab. Reload before removing it.")
    from app.services.structure_timers import sync_manual
    sync_manual(db, user.id, str(record_id))
    db.commit()
    return {"removed": True, "id": str(record_id)}
