"""Private full-scope analytics and a separate allowlisted public snapshot API."""
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import io
import json
import re
import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.journey import access
from app.db.session import get_db
from app.models import EveCharacter, User
from app.models.journey_views import JourneyAnalyticsView
from app.services import journey, journey_insights as service
from app.services.journey_analytics import combat_allowed
from app.services.permissions import can_view_section

router = APIRouter(prefix='/journey/insights', tags=['journey insights'], dependencies=[Depends(access)])
public_router = APIRouter(prefix='/journey-views', tags=['shared journey aggregates'])
Identifier = Annotated[int, Field(gt=0, le=2_147_483_647)]


class Scope(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cohort: Literal['account', 'fleet', 'selected'] = 'account'
    character_ids: list[Identifier] = Field(default_factory=list, max_length=100)
    period: Literal['all', 'range'] = 'all'
    from_at: datetime | None = None
    to_at: datetime | None = None
    ship_type_id: Identifier | None = None
    system_id: Identifier | None = None
    exclude_types: list[Identifier] = Field(default_factory=list, max_length=200)
    exclude_groups: list[Identifier] = Field(default_factory=list, max_length=100)
    exclude_capitals: bool = False
    exclude_supercapitals: bool = False
    show_systems: bool = False
    show_pilots: bool = False
    metric: Literal['visits', 'seconds', 'kills', 'losses'] = 'visits'
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0, le=100000)

    @model_validator(mode='after')
    def valid(self):
        if self.cohort == 'selected' and not self.character_ids:
            raise ValueError('Select at least one pilot')
        if self.cohort == 'account' and self.character_ids:
            raise ValueError('Explicit pilot IDs require selected/fleet scope')
        if self.period == 'range':journey.window(self.from_at, self.to_at)
        return self


class SaveView(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field('My Fleet summary', min_length=1, max_length=120)
    scope: Scope
    days: Literal[1, 7, 30, 90] = 7


class Visibility(BaseModel):
    model_config = ConfigDict(extra='forbid')
    is_public: bool | None = None
    preview_hash: str | None = Field(None, pattern=r'^[0-9a-f]{64}$')
    rotate: bool = False


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def digest(report):
    return hashlib.sha256(json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def metadata(row):
    return dict(id=row.id, title=row.title, is_public=row.is_public, created_at=row.created_at,
        expires_at=row.expires_at, share_path=f'#journey-view/{row.token}' if row.is_public else None)


def owned(db, user, ident):
    row = db.scalar(select(JourneyAnalyticsView).where(JourneyAnalyticsView.id == ident, JourneyAnalyticsView.owner_user_id == user.id))
    if row is None:raise HTTPException(404, 'Saved view not found')
    return row


def still_authorized(db, row):
    owner = db.get(User, row.owner_user_id, populate_existing=True)
    if owner is None or owner.deleted_at is not None or not can_view_section(owner, 'navigation', db):return False
    if row.report['combat_available'] and not combat_allowed(db, owner):return False
    current = {c.id:c.character_id for c in db.scalars(select(EveCharacter).where(EveCharacter.owner_user_id == owner.id,
        EveCharacter.id.in_([p['id'] for p in row.cohort])))}
    return current == {p['id']:p['eve_id'] for p in row.cohort}


@router.get('/options')
def options(search: str = Query('', max_length=100), user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.options(db, user, search)


@router.post('/query')
def query(scope: Scope, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return service.build(db, user, scope.model_dump())


@router.post('/views', status_code=201)
def create(payload: SaveView, user=Depends(get_current_user), db: Session = Depends(get_db)):
    # Creating a view NEVER publishes it. The next deliberate action receives
    # the hash of the exact server-filtered report the owner has previewed.
    at = journey.now()
    count = db.scalar(select(func.count()).select_from(JourneyAnalyticsView).where(
        JourneyAnalyticsView.owner_user_id == user.id, JourneyAnalyticsView.created_at > at - timedelta(minutes=1))) or 0
    if count >= 10:raise HTTPException(429, 'Save at most 10 views per minute')
    spec = payload.scope.model_dump()
    people = service.cohort(db, user, spec)
    if not people:raise HTTPException(422, 'No pilots in the selected scope')
    if spec['offset']:raise HTTPException(422, 'Preview sharing from the first ranking page')
    # Freeze the cohort before building, including account/fleet selections.
    spec.update(cohort='selected', character_ids=[p['id'] for p in people])
    report = jsonable_encoder(service.build(db, user, spec, public=True))
    row = JourneyAnalyticsView(owner_user_id=user.id, token=secrets.token_urlsafe(32), title=payload.title.strip(),
        is_public=False, spec=jsonable_encoder(spec), cohort=[{'id':p['id'], 'eve_id':p['eve_id']} for p in people],
        report=report, created_at=at, expires_at=at + timedelta(days=payload.days))
    if not row.title:raise HTTPException(422, 'A view title is required')
    db.add(row); db.commit()
    return {**metadata(row), 'report':row.report, 'preview_hash':digest(row.report)}


@router.post('/export/{fmt}')
def private_export(fmt: Literal['json', 'csv'], scope: Scope, user=Depends(get_current_user), db: Session = Depends(get_db)):
    spec = scope.model_dump()
    result = service.build(db, user, spec)
    src = service.sources(db, user, spec)
    for kind in ('hulls', 'systems', 'pilots'):
        result[kind] = service.ranking(db, src, kind, spec['metric'], None, 0)
    result['notices'].append('Private export includes all qualifying ranking groups, not only the visible page.')
    return exported(result, 'Private Journey analytics', fmt)


@router.post('/combat')
def combat(scope: Scope, user=Depends(get_current_user), db: Session = Depends(get_db)):
    src = service.sources(db, user, scope.model_dump())
    if not src['available']:raise HTTPException(403, 'Combat permission required')
    from sqlalchemy import literal, union_all
    k, l = src['kills'], src['losses']
    rows = union_all(select(k, literal('kill').label('side')), select(l, literal('loss').label('side'))).subquery()
    result = db.execute(select(rows).order_by(rows.c.time.desc(), rows.c.mail_id.desc(), rows.c.pilot_id).offset(
        scope.offset).limit(scope.limit)).mappings()
    return {'rows':[dict(r) for r in result], 'total':db.scalar(select(func.count()).select_from(rows)),
        'notice':'One row per participating selected pilot and side; shared killmails may repeat here. This list stays private.'}


@router.get('/views')
def views(offset: int = Query(0, ge=0), user=Depends(get_current_user), db: Session = Depends(get_db)):
    conditions = [JourneyAnalyticsView.owner_user_id == user.id]
    rows = db.scalars(select(JourneyAnalyticsView).where(*conditions).order_by(JourneyAnalyticsView.created_at.desc(),
        JourneyAnalyticsView.id.desc()).offset(offset).limit(25))
    return {'rows':[metadata(row) for row in rows], 'total':db.scalar(select(func.count()).select_from(JourneyAnalyticsView).where(*conditions))}


@router.get('/views/{ident}')
def saved(ident: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(db, user, ident)
    if not still_authorized(db, row):raise HTTPException(409, 'Saved cohort or combat permission changed. Delete this view and create a new preview.')
    return {**metadata(row), 'report':row.report, 'preview_hash':digest(row.report)}


@router.patch('/views/{ident}')
def visibility(ident: int, payload: Visibility, user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(db, user, ident)
    if payload.is_public is True:
        if utc(row.expires_at) <= journey.now() or not still_authorized(db, row):
            raise HTTPException(409, 'View expired or its permissions/cohort changed. Create a new preview.')
        if not secrets.compare_digest(payload.preview_hash or '', digest(row.report)):
            raise HTTPException(409, 'Review this saved public preview before publishing')
    if payload.is_public is not None:
        if row.is_public != payload.is_public:row.token = secrets.token_urlsafe(32)
        row.is_public = payload.is_public
    if payload.rotate:row.token = secrets.token_urlsafe(32)
    db.commit()
    return metadata(row)


@router.delete('/views/{ident}')
def remove(ident: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = owned(db, user, ident); db.delete(row); db.commit()
    return {'deleted':True}


def public_row(token, request, response, db):
    response.headers.update({'Cache-Control':'no-store, private', 'X-Robots-Tag':'noindex, nofollow', 'Referrer-Policy':'no-referrer'})
    # Public clients cannot widen a saved scope with filters or pilot IDs.
    if request.query_params:raise HTTPException(400, 'Public views do not accept scope overrides', headers={'Cache-Control':'no-store'})
    row = None
    if re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        row = db.scalar(select(JourneyAnalyticsView).where(JourneyAnalyticsView.token == token, JourneyAnalyticsView.is_public.is_(True)))
    if row is None or utc(row.expires_at) <= journey.now() or not still_authorized(db, row):
        raise HTTPException(404, 'Shared view unavailable, expired or revoked', headers={'Cache-Control':'no-store'})
    return row


@public_router.get('/{token}')
def public(token: str, request: Request, response: Response, db: Session = Depends(get_db)):
    row = public_row(token, request, response, db)
    return {'title':row.title, 'expires_at':row.expires_at, 'report':row.report}


def exported(report, title, fmt):
    if fmt == 'json':
        return Response(json.dumps(jsonable_encoder({'title':title, 'report':report})), media_type='application/json',
            headers={'Content-Disposition':'attachment; filename="eqm-journey-view.json"', 'Cache-Control':'no-store'})
    output = io.StringIO(newline=''); writer = csv.writer(output)
    writer.writerow(['section', 'name', 'visits', 'segments', 'systems', 'seconds', 'kills', 'losses', 'from_at', 'to_at', 'checked_at', 'scope_json', 'coverage'])
    def safe(value):
        return "'" + value if isinstance(value, str) and value[:1] in '=+-@\t\r' else value
    for kind in ('summary', 'hulls', 'systems', 'pilots'):
        rows = [dict(report['summary'], name=title)] if kind == 'summary' else report.get(kind, {}).get('rows', [])
        for row in rows:writer.writerow([safe(v) for v in [kind, row.get('name'), *[row.get(k) for k in
            ('visits', 'segments', 'systems', 'seconds', 'kills', 'losses')], report['scope']['from_at'], report['scope']['to_at'], report['checked_at'],
            json.dumps(jsonable_encoder(report['scope']), sort_keys=True), ' '.join(report['notices'])]])
    return Response(output.getvalue(), media_type='text/csv', headers={
        'Content-Disposition':'attachment; filename="eqm-journey-view.csv"', 'Cache-Control':'no-store'})


@public_router.get('/{token}/export/{fmt}')
def public_export(token: str, fmt: Literal['json', 'csv'], request: Request, response: Response, db: Session = Depends(get_db)):
    row = public_row(token, request, response, db)
    result = exported(row.report, row.title, fmt)
    result.headers.update({'X-Robots-Tag':'noindex, nofollow', 'Referrer-Policy':'no-referrer'})
    return result
