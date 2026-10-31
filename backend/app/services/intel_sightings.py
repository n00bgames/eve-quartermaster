"""Analyst-reported ship sightings, kept separate from canonical combat evidence."""
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import Boolean, Integer, String, func, literal, or_, select, union_all
from sqlalchemy.exc import IntegrityError
from app.models import EveType,EveGroup,EveSystem,EveConstellation,EveRegion,User
from app.models.intel import IntelSighting, LocalScanSighting
from app.domain.intel import utc
from app.services.audit import record_audit_event


def lookup(db,kind,q):
    q=q.strip()
    if not q:return []
    pattern='%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
    if kind=='system':
        rows=db.execute(select(EveSystem.system_id,EveSystem.name,EveRegion.name.label('detail'))
            .outerjoin(EveConstellation,EveConstellation.constellation_id==EveSystem.constellation_id)
            .outerjoin(EveRegion,EveRegion.region_id==EveConstellation.region_id)
            .where(EveSystem.name.ilike(pattern,escape='\\')).order_by(func.lower(EveSystem.name)!=q.casefold(),EveSystem.name).limit(20))
    else:
        rows=db.execute(select(EveType.type_id,EveType.name,EveGroup.name.label('detail')).join(EveGroup,EveGroup.group_id==EveType.group_id)
            .where(EveGroup.category_id==6,EveType.published.is_(True),EveType.name.ilike(pattern,escape='\\'))
            .order_by(func.lower(EveType.name)!=q.casefold(),EveType.name).limit(20))
    return [{'id':r[0],'name':r[1],'detail':r[2]} for r in rows]


def validate(db,payload,kind='character'):
    if kind!='character':raise HTTPException(422,'Ship sightings can only be attached to character dossiers')
    if payload.observed_at is not None and not (datetime(2003,5,6,tzinfo=timezone.utc)<=utc(payload.observed_at)<=datetime.now(timezone.utc)):
        raise HTTPException(422,'Sighting time must be between 6 May 2003 and the current UTC time')
    row=db.execute(select(EveSystem,EveRegion).outerjoin(EveConstellation,EveConstellation.constellation_id==EveSystem.constellation_id)
        .outerjoin(EveRegion,EveRegion.region_id==EveConstellation.region_id).where(EveSystem.system_id==payload.system_id)).first()
    ship=db.scalar(select(EveType).join(EveGroup,EveGroup.group_id==EveType.group_id)
        .where(EveType.type_id==payload.ship_type_id,EveGroup.category_id==6,EveType.published.is_(True))) if payload.ship_type_id is not None else None
    if row is None:raise HTTPException(422,'Select a solar system from the imported SDE')
    if payload.ship_type_id is not None and ship is None:raise HTTPException(422,'Select a published ship hull from the imported SDE')
    system,region=row
    return {'system_id':system.system_id,'system_name':system.name,'region_id':region.region_id if region else None,
        'region_name':region.name if region else None,'ship_type_id':ship.type_id if ship else None,'ship_type_name':ship.name if ship else 'Unknown Ship Type'}


def record(db,subject,payload,user,at=None):
    values=validate(db,payload,subject.kind)
    key=str(payload.request_id)
    def existing():return db.scalar(select(IntelSighting).where(IntelSighting.subject_id==subject.id,IntelSighting.observer_user_id==user.id,IntelSighting.request_id==key))
    def checked(row):
        if row.system_id!=payload.system_id or row.ship_type_id!=payload.ship_type_id or row.manual_time!=(payload.observed_at is not None) or (payload.observed_at is not None and utc(row.observed_at)!=utc(payload.observed_at)):raise HTTPException(409,'This sighting request was already used for a different system, ship or time')
        return row
    previous=existing()
    if previous:return checked(previous)
    recorded_at=at or datetime.now(timezone.utc)
    row=IntelSighting(subject_id=subject.id,observer_user_id=user.id,request_id=key,recorded_at=recorded_at,manual_time=payload.observed_at is not None,observed_at=utc(payload.observed_at) if payload.observed_at is not None else recorded_at,**values)
    try:
        with db.begin_nested():db.add(row);db.flush()
    except IntegrityError:
        previous=existing()
        if previous:return checked(previous)
        raise
    subject.updated_at=recorded_at
    record_audit_event(db,event_kind='intel',title='Intel ship sighting recorded',actor_user=user,body=f'subject={subject.id}; sighting={row.id}; system={row.system_id}; ship={row.ship_type_id}')
    return row


def payload(row,observer=None):
    return {'id':f'local-scan:{row.id}' if getattr(row,'source',None)=='local_scan' else row.id,'system_id':row.system_id,'system_name':row.system_name,'region_name':row.region_name,'ship_type_id':row.ship_type_id,
        'ship_type_name':row.ship_type_name,'observed_at':utc(row.observed_at).isoformat(),'recorded_at':utc(row.recorded_at).isoformat(),'manual_time':row.manual_time,'observer':observer,
        'source':getattr(row,'source','analyst_sighting'),'kills':0,'losses':0}


def visible_sightings(subject, from_at, to_at, viewer_user_id):
    """Apply privacy BEFORE aggregates/limits; no private signal escapes via totals."""
    manual = select(IntelSighting.id, IntelSighting.system_id, IntelSighting.system_name,
        IntelSighting.region_id, IntelSighting.region_name, IntelSighting.ship_type_id,
        IntelSighting.ship_type_name, IntelSighting.observed_at, IntelSighting.recorded_at,
        IntelSighting.manual_time, User.display_name.label('observer'), literal('analyst_sighting').label('source'))
    manual = manual.join(User, User.id == IntelSighting.observer_user_id).where(
        IntelSighting.subject_id == subject.id, IntelSighting.observed_at >= from_at, IntelSighting.observed_at < to_at)
    scans = select(LocalScanSighting.id, LocalScanSighting.system_id, LocalScanSighting.system_name,
        LocalScanSighting.region_id, LocalScanSighting.region_name, literal(None, Integer).label('ship_type_id'),
        literal('Unknown Ship Type').label('ship_type_name'), LocalScanSighting.observed_at, LocalScanSighting.recorded_at,
        literal(False, Boolean).label('manual_time'), literal(None, String).label('observer'), literal('local_scan').label('source'))
    visibility = LocalScanSighting.is_private.is_(False)
    if viewer_user_id is not None:
        visibility = or_(visibility, LocalScanSighting.created_by_user_id == viewer_user_id)
    scans = scans.where(visibility, LocalScanSighting.character_eve_id == subject.eve_id,
        literal(subject.kind) == 'character', LocalScanSighting.observed_at >= from_at, LocalScanSighting.observed_at < to_at)
    return union_all(manual, scans).subquery()


def merge(db,subject,summary,from_at,to_at,viewer_user_id=None):
    observations=visible_sightings(subject,from_at,to_at,viewer_user_id)
    c=observations.c
    count=func.count();last=func.max(c.observed_at)
    ships={r['id']:r for r in summary['ships']};systems={r['id']:r for r in summary['systems']}
    total=0
    for tid,name,n,at in db.execute(select(c.ship_type_id,func.max(c.ship_type_name),count,last).group_by(c.ship_type_id)):
        row=ships.setdefault(tid,{'id':tid,'name':name,'kills':0,'losses':0,'evidence':[]})
        row['sightings']=n;total+=n;row['last_sighting_at']=utc(at).isoformat()
    for sid,name,rid,rname,n,at in db.execute(select(c.system_id,func.max(c.system_name),c.region_id,func.max(c.region_name),count,last)
        .group_by(c.system_id,c.region_id)):
        row=systems.setdefault(sid,{'id':sid,'name':name,'region_id':rid,'region_name':rname,'kills':0,'losses':0,'evidence':[]})
        row['sightings']=n;row['last_sighting_at']=utc(at).isoformat()
    day=func.date(func.timezone('UTC',c.observed_at)) if db.get_bind().dialect.name=='postgresql' else func.date(c.observed_at)
    timeline={r['date']:r for r in summary['timeline']}
    for at,n in db.execute(select(day,count).group_by(day)):
        key=at.isoformat() if hasattr(at,'isoformat') else str(at)
        timeline.setdefault(key,{'date':key,'kills':0,'losses':0})['sightings']=n
    for key,rows in [('ships',ships),('systems',systems)]:
        summary[key]=sorted(rows.values(),key=lambda r:(-(r['kills']+r['losses']),-r.get('sightings',0),r['id'] or 0))
    summary['timeline']=[timeline[key] for key in sorted(timeline)]
    summary['sightings']=total
    rows=db.execute(select(observations).order_by(c.observed_at.desc(),c.source,c.id.desc()).limit(200)).all()
    return {'total':total,'limit':200,'rows':[payload(row,row.observer) for row in rows],
        'notice':'Analyst sightings use the entered UTC time or report-run time. Local Scan sightings use the scan generation time and manually selected system; ship type is unknown. These are reported observations, not killmail evidence or verified current locations. Each contributes 0 kills and 0 losses.'}
