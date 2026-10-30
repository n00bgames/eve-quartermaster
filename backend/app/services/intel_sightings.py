"""Analyst-reported ship sightings, kept separate from canonical combat evidence."""
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import func,select
from sqlalchemy.exc import IntegrityError
from app.models import EveType,EveGroup,EveSystem,EveConstellation,EveRegion,User
from app.models.intel import IntelSighting
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
    return {'id':row.id,'system_id':row.system_id,'system_name':row.system_name,'region_name':row.region_name,'ship_type_id':row.ship_type_id,
        'ship_type_name':row.ship_type_name,'observed_at':utc(row.observed_at).isoformat(),'recorded_at':utc(row.recorded_at).isoformat(),'manual_time':row.manual_time,'observer':observer,
        'source':'analyst_sighting','kills':0,'losses':0}


def merge(db,subject,summary,from_at,to_at):
    filters=[IntelSighting.subject_id==subject.id,IntelSighting.observed_at>=from_at,IntelSighting.observed_at<to_at]
    count=func.count(IntelSighting.id);last=func.max(IntelSighting.observed_at)
    ships={r['id']:r for r in summary['ships']};systems={r['id']:r for r in summary['systems']}
    total=0
    for tid,name,n,at in db.execute(select(IntelSighting.ship_type_id,func.max(IntelSighting.ship_type_name),count,last).where(*filters).group_by(IntelSighting.ship_type_id)):
        row=ships.setdefault(tid,{'id':tid,'name':name,'kills':0,'losses':0,'evidence':[]})
        row['sightings']=n;total+=n;row['last_sighting_at']=utc(at).isoformat()
    for sid,name,rid,rname,n,at in db.execute(select(IntelSighting.system_id,func.max(IntelSighting.system_name),IntelSighting.region_id,func.max(IntelSighting.region_name),count,last)
        .where(*filters).group_by(IntelSighting.system_id,IntelSighting.region_id)):
        row=systems.setdefault(sid,{'id':sid,'name':name,'region_id':rid,'region_name':rname,'kills':0,'losses':0,'evidence':[]})
        row['sightings']=n;row['last_sighting_at']=utc(at).isoformat()
    day=func.date(func.timezone('UTC',IntelSighting.observed_at)) if db.get_bind().dialect.name=='postgresql' else func.date(IntelSighting.observed_at)
    timeline={r['date']:r for r in summary['timeline']}
    for at,n in db.execute(select(day,count).where(*filters).group_by(day)):
        key=at.isoformat() if hasattr(at,'isoformat') else str(at)
        timeline.setdefault(key,{'date':key,'kills':0,'losses':0})['sightings']=n
    for key,rows in [('ships',ships),('systems',systems)]:
        summary[key]=sorted(rows.values(),key=lambda r:(-(r['kills']+r['losses']),-r.get('sightings',0),r['id'] or 0))
    summary['timeline']=[timeline[key] for key in sorted(timeline)]
    summary['sightings']=total
    rows=db.execute(select(IntelSighting,User.display_name).join(User,User.id==IntelSighting.observer_user_id).where(*filters)
        .order_by(IntelSighting.observed_at.desc(),IntelSighting.id.desc()).limit(200)).all()
    return {'total':total,'limit':200,'rows':[payload(row,name) for row,name in rows],
        'notice':'Analyst-reported sightings at the entered UTC time, or report-run time when blank; not killmail evidence or verified current locations. Each sighting contributes 0 kills and 0 losses.'}
