"""Intel report builder and immutable, revocable public combat snapshots."""
import asyncio
from datetime import datetime, timedelta, timezone
import secrets
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.api.intel import access
from app.api.local_scan import public_headers, public_row
from app.db.session import get_db
from app.domain.intel import utc
from app.models import User, EveSystem, Killmail
from app.models.intel import IntelSourceCache
from app.models.local_scan import LocalScanReport
from app.services.intel_reports import name_map, require_intel
from app.services.intel_sources import PublicSource
from app.services import intel_report_builder as builder, intel_report_refresh as refresh
from app.services.local_scan import RETENTIONS, active_reports
from app.services.permissions import quartermaster_read_only
from app.services.report_identity import report_identity
from app.services.audit import record_audit_event
from app.services.character_notes import conflict_insert

Kind=Literal['system','character','corporation','alliance']
router=APIRouter(prefix='/intel-reports',tags=['intel reports'],dependencies=[Depends(access)])
public_router=APIRouter(prefix='/intel-reports',tags=['public intel reports'])
_refreshing=set()
def source_factory():return PublicSource()
def now():return datetime.now(timezone.utc)

class ResolveInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Kind
    name:str=Field(min_length=1,max_length=255)
class TargetInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Kind
    eve_id:int=Field(gt=0,le=2147483647)
class SaveInput(TargetInput):
    from_at:datetime
    to_at:datetime
    is_private:StrictBool=True
    anonymous:StrictBool=True
    retention:Literal['30m','1h','2h','12h','24h','3days','7days','30days','permanent']='24h'

def window(start,end):
    if start.tzinfo is None or end.tzinfo is None:raise HTTPException(422,'Use timezone-aware UTC report dates')
    start,end=utc(start),utc(end)
    if start>=end or end-start>timedelta(days=90) or start>=now():raise HTTPException(422,'Choose a past-start report window of at most 90 days')
    return start,min(end,now())
def target(db,kind,eid):
    if kind=='system':
        row=db.get(EveSystem,eid)
        if row:return dict(kind=kind,eve_id=eid,name=row.name,security_status=float(row.security_status) if row.security_status is not None else None)
    else:
        names=name_map(db,kind,{eid});cached=db.get(IntelSourceCache,f'intel-report-target:{kind}:{eid}')
        name=names.get(eid) or (cached.payload.get('name') if cached else None)
        if name:return dict(kind=kind,eve_id=eid,name=name)
    raise HTTPException(404,'Resolve and choose a known target first; systems require imported SDE data')
def writable(db,user):
    if quartermaster_read_only(user,db):raise HTTPException(403,'Your role cannot create or refresh reports')
def revalidate(db,uid):
    current=db.get(User,uid,populate_existing=True)
    if current is None:raise HTTPException(403,'Intel access is no longer available')
    require_intel(current,db)
    return current

@router.post('/resolve')
async def resolve(payload:ResolveInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    text=payload.name.strip()
    if not text:raise HTTPException(422,'Enter a name')
    if payload.kind=='system':
        rows=db.scalars(select(EveSystem).where(EveSystem.name.ilike('%'+text+'%')).order_by(func.lower(EveSystem.name),EveSystem.system_id).limit(20)).all()
        return {'rows':[target(db,'system',r.system_id) for r in rows],'notice':'Choose an imported SDE system.' if rows else 'No imported system matches. Import/update SDE if needed.'}
    uid=user.id
    from app.models import EveCharacter,EveCorporation,EveAlliance
    from app.models.intel import IntelSubject
    model,column={'character':(EveCharacter,EveCharacter.character_id),'corporation':(EveCorporation,EveCorporation.corporation_id),'alliance':(EveAlliance,EveAlliance.alliance_id)}[payload.kind]
    matches={eid:name for eid,name in db.execute(select(column,model.name).where(model.name.ilike('%'+text+'%')).limit(20))}
    matches.update({r.eve_id:r.name for r in db.scalars(select(IntelSubject).where(IntelSubject.kind==payload.kind,IntelSubject.name.ilike('%'+text+'%')).limit(20))})
    db.rollback();source=source_factory();notice=''
    try:
        result=await asyncio.wait_for(source.resolve([text]),timeout=20)
        for r in result.get(payload.kind+'s',[]):
            if isinstance(r,dict) and type(r.get('id')) is int and isinstance(r.get('name'),str) and r['name'].casefold()==text.casefold():matches[r['id']]=r['name']
    except Exception:notice='Public ESI name lookup unavailable; cached matches only.'
    finally:await source.close()
    current=revalidate(db,uid)
    at=now()
    for eid,name in list(matches.items())[:20]:
        value=conflict_insert(db,IntelSourceCache).values(key=f'intel-report-target:{payload.kind}:{eid}',payload={'name':name},expires_at=at+timedelta(days=1))
        db.execute(value.on_conflict_do_update(index_elements=['key'],set_={'payload':value.excluded.payload,'expires_at':value.excluded.expires_at}))
    db.commit()
    return {'rows':[dict(kind=payload.kind,eve_id=eid,name=name) for eid,name in sorted(matches.items(),key=lambda p:(p[1].casefold(),p[0]))[:20]],'notice':notice}

@router.get('/report')
def report(kind:Kind,eve_id:int=Query(gt=0,le=2147483647),from_at:datetime=Query(),to_at:datetime=Query(),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    start,end=window(from_at,to_at);identity=target(db,kind,eve_id)
    public=builder.build_public(db,identity,start,end)
    return {'public_report':public,'internal_sightings':builder.internal_sightings(db,eve_id,start,end,user.id) if kind=='system' else None,'refresh':refresh.status(db,kind,eve_id)}

@router.post('/refresh')
async def pull(payload:TargetInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    writable(db,user);identity=target(db,payload.kind,payload.eve_id);uid=user.id
    if len(_refreshing)>=4:raise HTTPException(429,'Intel refresh is busy; retry shortly')
    token=refresh.claim(db,payload.kind,payload.eve_id)
    if not token:return {'cached':True,**refresh.status(db,payload.kind,payload.eve_id)}
    known=set(db.scalars(select(Killmail.killmail_id).order_by(Killmail.killmail_time.desc()).limit(1000)))
    db.rollback();source=source_factory();_refreshing.add(token)
    result=None;error=None
    try:
        try:result=await asyncio.wait_for(refresh.fetch(source,payload.kind,payload.eve_id,known),timeout=55)
        except Exception as issue:error=issue
        current=revalidate(db,uid);writable(db,current)
        value=refresh.persist(db,payload.kind,payload.eve_id,token,result,error)
        record_audit_event(db,event_kind='intel',title='Intel public killmail pull',actor_user=current,body=f"{identity['kind']}:{identity['eve_id']}; imported={value['imported']}; failed={value['failed']}")
        db.commit();return {'cached':False,**value}
    finally:_refreshing.discard(token);await source.close()

@router.post('/activity')
async def activity(payload:TargetInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    writable(db,user)
    if payload.kind!='system':raise HTTPException(422,'Hourly jump/kill totals apply to systems')
    target(db,'system',payload.eve_id);uid=user.id;db.rollback()
    from app.services.atlas_esi import activity_snapshot
    try:snapshot=await asyncio.wait_for(activity_snapshot(),timeout=35)
    except Exception as error:raise HTTPException(502,'Latest ESI activity unavailable; retained samples are unchanged') from error
    current=revalidate(db,uid);writable(db,current)
    return refresh.save_activity(db,payload.eve_id,snapshot)

def metadata(row):
    return dict(token=row.token,is_private=row.is_private,anonymous=row.anonymous,creator=row.account_name,created_at=utc(row.created_at),expires_at=utc(row.expires_at) if row.expires_at else None,
        retention=row.retention,application_version=row.application_version,share_path=None if row.is_private else f'#intel-report/{row.token}')

@router.post('/snapshots',status_code=201)
def save(payload:SaveInput,request:Request,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    writable(db,user);start,end=window(payload.from_at,payload.to_at);identity=target(db,payload.kind,payload.eve_id)
    count=db.scalar(select(func.count()).select_from(LocalScanReport).where(LocalScanReport.report_kind=='intel',LocalScanReport.created_by_user_id==user.id,LocalScanReport.created_at>now()-timedelta(minutes=1))) or 0
    if count>=10:raise HTTPException(429,'Save at most 10 Intel snapshots per minute')
    # Only this public projection is stored. No staff response/request object is
    # accepted or reused, even when the source report has private observations.
    snapshot=builder.build_public(db,identity,start,end);creator,anonymous=report_identity(db,user,payload.anonymous)
    at=now();lifetime=RETENTIONS[payload.retention]
    row=LocalScanReport(report_kind='intel',token=secrets.token_urlsafe(32),created_by_user_id=user.id,account_name=creator,anonymous=anonymous,
        is_private=payload.is_private,application_version=request.app.version,created_at=at,expires_at=at+timedelta(seconds=lifetime) if lifetime else None,
        retention=payload.retention,payload=jsonable_encoder(snapshot))
    db.add(row)
    record_audit_event(db,event_kind='intel',title='Intel snapshot created',actor_user=user,body=f"{identity['kind']}:{identity['eve_id']}; private={payload.is_private}; retention={payload.retention}")
    db.commit();return {**metadata(row),'report':row.payload}

@router.get('/snapshots')
def snapshots(offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    conditions=[LocalScanReport.created_by_user_id==user.id,active_reports(kind='intel')]
    rows=db.scalars(select(LocalScanReport).where(*conditions).order_by(LocalScanReport.created_at.desc(),LocalScanReport.token).offset(offset).limit(limit))
    return {'rows':[{**metadata(row),'target':row.payload['target']} for row in rows],'total':db.scalar(select(func.count()).select_from(LocalScanReport).where(*conditions)) or 0}

def owned(db,token,user):
    row=db.scalar(select(LocalScanReport).where(LocalScanReport.token==token,LocalScanReport.created_by_user_id==user.id,active_reports(kind='intel')))
    if row is None:raise HTTPException(404,'Snapshot not found or expired')
    return row

@router.get('/snapshots/{token}')
def saved(token:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=owned(db,token,user);return {**metadata(row),'report':row.payload}

@router.delete('/snapshots/{token}')
def revoke(token:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    writable(db,user);row=owned(db,token,user);db.delete(row)
    record_audit_event(db,event_kind='intel',title='Intel snapshot revoked',actor_user=user,body='Owned Intel snapshot removed; public access revoked')
    db.commit();return {'deleted':True}

@public_router.get('/public/{token}')
def public(token:str,response:Response,db:Session=Depends(get_db)):
    public_headers(response);row=public_row(db,token,kind='intel')
    return {**metadata(row),'report':row.payload}
