from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.models.structure_timer import StructureTimerConfig as Config, StructureTimer as Timer, StructureTimerDelivery as Delivery
from app.services import structure_timers as service
from app.services.permissions import role_payload, role_exists

router = APIRouter(prefix='/structure-timers', tags=['structures'])


class Setting(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: Literal['manual', 'upwell', 'pos']
    source_id: str = Field(min_length=1, max_length=36, pattern=r'^[0-9a-fA-F-]+$')
    token_key: StrictInt = Field(default=0, ge=0)
    enabled: StrictBool
    roles: list[str] = Field(min_length=1, max_length=40)
    minutes: list[StrictInt] = Field(min_length=1, max_length=8)
    version: StrictInt = Field(default=0, ge=0)


def serialize(config, db):
    return {'id': config.id, 'source': config.source, 'source_id': config.source_id,
            'token_key': config.token_key, 'enabled': config.enabled, 'roles': config.roles,
            'minutes': config.minutes, 'version': config.version, 'status': config.status,
            'checked_at': service.utc(config.checked_at) if config.checked_at else None, 'events': [
                {'kind': t.kind, 'deadline': service.utc(t.deadline), 'event_id': t.event_id}
                for t in db.scalars(select(Timer).where(Timer.config_id == config.id, Timer.deadline.is_not(None)))] if config.enabled and config.status == 'Tracking' else []}


@router.get('')
def listing(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    if not service.manager(user, db):
        return {'can_manage': False, 'roles': [], 'rows': []}
    return {'can_manage': True, 'roles': [{'name': r['name'], 'label': r['display_name']} for r in role_payload(db)],
            'rows': [serialize(c, db) for c in db.scalars(select(Config).where(Config.owner_user_id == user.id))]}


@router.put('')
async def save(body: Setting, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not service.manager(user, db):
        raise HTTPException(403, 'Structures and Officer-level Calendar event management are required')
    if any(not role_exists(db, role) or role == 'applicant' for role in body.roles):
        raise HTTPException(422, 'Select existing non-applicant recipient roles')
    if any(m < 1 or m > 43200 for m in body.minutes):
        raise HTTPException(422, 'Use 1–43200 minutes before the deadline')
    if (body.source == 'manual') != (body.token_key == 0):
        raise HTTPException(422, 'Select the source character for an ESI structure')
    # Fetch ESI before taking a settings write lock; authorize again below.
    reading = None
    if body.enabled:
        candidate = Config(owner_user_id=user.id, source=body.source, source_id=body.source_id, token_key=body.token_key)
        try:
            reading = await service.source(candidate, db)
        except Exception:
            raise HTTPException(409, 'Source unavailable. Check ownership, ESI scope and corporation role, then retry.')
        db.rollback()
        if not service.manager(user, db) or not service.source_authorized(candidate, db):
            raise HTTPException(409, 'Source permissions changed. Reload before saving.')
    config = db.scalar(select(Config).where(Config.owner_user_id == user.id, Config.source == body.source,
        Config.source_id == body.source_id, Config.token_key == body.token_key).with_for_update())
    if config and config.version != body.version or not config and body.version != 0:
        raise HTTPException(409, 'Timer settings changed. Reload before saving.')
    if not config:
        config = Config(owner_user_id=user.id, source=body.source, source_id=body.source_id, token_key=body.token_key,
                        enabled=False, roles=[], minutes=[], version=0)
        db.add(config)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Timer settings changed. Reload before saving.')
    if body.enabled and body.source == 'manual':
        from app.models import ManualPos
        reading = service.manual_source(db.get(ManualPos, body.source_id, populate_existing=True))
    config.enabled = body.enabled
    config.roles = sorted(set(body.roles))
    config.minutes = sorted(set(body.minutes))
    config.version += 1
    service.sync(config, db, reading)
    db.commit()
    return serialize(config, db)


@router.get('/alerts')
def alerts(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'private, no-store'
    rows, seen = [], set()
    for delivery in db.scalars(select(Delivery).where(Delivery.user_id == user.id, Delivery.dismissed.is_(False)).order_by(Delivery.id.desc()).limit(100)):
        timer = db.get(Timer, delivery.timer_id)
        config = db.get(Config, timer.config_id)
        if (delivery.generation != timer.generation or not service.visible(timer, user, db)
                or not service.eligible(config, user, db) or service.utc(timer.deadline) <= service.now()):
            continue
        if timer.id in seen:
            continue
        seen.add(timer.id)
        from app.models import AuditEvent
        notice = db.get(AuditEvent, delivery.notice_id)
        rows.append({'id': delivery.id, 'title': notice.title, 'body': notice.body, 'deadline': service.utc(timer.deadline), 'event_id': timer.event_id})
    return {'rows': rows}


@router.post('/alerts/{delivery_id}/dismiss')
def dismiss(delivery_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Delivery).where(Delivery.id == delivery_id, Delivery.user_id == user.id))
    if not row:
        raise HTTPException(404, 'Reminder was not found')
    # Acknowledge this timer's current and earlier notices, keeping later
    # reminder thresholds able to raise a fresh banner.
    db.execute(update(Delivery).where(Delivery.user_id == user.id, Delivery.timer_id == row.timer_id,
        Delivery.generation == row.generation, Delivery.id <= row.id).values(dismissed=True))
    db.commit()
    return {'dismissed': True}
