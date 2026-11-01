"""Owner-only journey queries and bounded, existing-data context."""
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import and_, case, delete, distinct, func, literal, or_, select
from sqlalchemy.orm import aliased
from app.domain.intel import utc
from app.models import Asset, EveCharacter, EveConstellation, EveRegion, EveStation, EveSystem, EveType, EsiToken, Location, OwnershipEntity, Killmail, KillmailAttacker
from app.models.journey import JourneyTracker, JourneyVisit
from app.services.journey_worker import SCOPES, character_token, now
from app.services.permissions import can_view_section

LIMIT = 2000


def own_character(db, user, character_id):
    row = db.get(EveCharacter, character_id, populate_existing=True)
    if row is None or row.owner_user_id != user.id:
        raise HTTPException(404, 'Linked character not found')
    return row


def tracker_for(db, user, character_id):
    own_character(db, user, character_id)
    return db.scalar(select(JourneyTracker).where(JourneyTracker.user_id == user.id, JourneyTracker.character_id == character_id))


def state_payload(row):
    return {'enabled': bool(row and row.enabled), 'interval_seconds': row.interval_seconds if row else 15,
        'state': row.state if row else 'paused',
        'checked_at': utc(row.checked_at).isoformat() if row and row.checked_at else None,
        'last_seen_at': utc(row.last_seen_at).isoformat() if row and row.last_seen_at else None}


def settings(db, user):
    rows = db.scalars(select(EveCharacter).where(EveCharacter.owner_user_id == user.id).order_by(EveCharacter.name)).all()
    trackers = {r.character_id:r for r in db.scalars(select(JourneyTracker).where(JourneyTracker.user_id == user.id))}
    return {'characters': [{'character_id': c.id, 'eve_id': c.character_id, 'name': c.name,
        'authorized': character_token(db, user.id, c.id) is not None, **state_payload(trackers.get(c.id))} for c in rows],
        'privacy': 'Only your account can view this history. Tracking is off until you explicitly enable a character.',
        'intervals': [15,30,60,120,300]}


def configure(db, user, character_id, enabled, interval):
    own_character(db, user, character_id)
    if enabled and character_token(db, user.id, character_id) is None:
        raise HTTPException(409, 'Enable read-only location and online access for this character first')
    # Serialize configuration creation and invalidate any in-flight sampling lease.
    db.scalar(select(EveCharacter).where(EveCharacter.id == character_id).with_for_update())
    row = tracker_for(db, user, character_id)
    if row is None:
        row = JourneyTracker(user_id=user.id, character_id=character_id, revision=0)
        db.add(row)
    if row.enabled != enabled:
        row.current_visit_id = None
    row.enabled = enabled; row.interval_seconds = interval; row.revision += 1
    row.state = 'waiting' if enabled else 'paused'
    row.next_poll_at = now() if enabled else None
    row.lease_token = None; row.lease_until = None
    db.commit()
    return settings(db,user)


def clear_history(db, user, character_id):
    row = tracker_for(db,user,character_id)
    if row:
        row = db.scalar(select(JourneyTracker).where(JourneyTracker.id == row.id).with_for_update())
        row.enabled = False; row.state = 'paused'; row.current_visit_id = None
        row.checked_at = None; row.last_seen_at = None; row.next_poll_at = None
        row.lease_token = None; row.lease_until = None; row.revision += 1
        db.execute(delete(JourneyVisit).where(JourneyVisit.tracker_id == row.id))
        db.commit()
    return {'deleted': True, 'tracking_paused': True}


def window(from_at, to_at):
    end = utc(to_at) if to_at else now()+timedelta(seconds=1)
    start = utc(from_at) if from_at else end-timedelta(days=7)
    if start >= end or end-start > timedelta(days=3660):
        raise HTTPException(422, 'Choose a positive UTC date range of at most 3,660 days')
    return start,end


def history(db, user, character_id, start, end):
    character = own_character(db,user,character_id)
    tracker = tracker_for(db,user,character_id)
    filters = [JourneyVisit.tracker_id == (tracker.id if tracker else -1), JourneyVisit.first_seen_at < end, JourneyVisit.last_seen_at >= start]
    visits = db.scalars(select(JourneyVisit).where(*filters).order_by(JourneyVisit.first_seen_at,JourneyVisit.id).limit(LIMIT)).all()
    total = db.scalar(select(func.count()).select_from(JourneyVisit).where(*filters)) or 0
    stats = db.execute(select(JourneyVisit.system_id,func.count(),func.min(JourneyVisit.first_seen_at),func.max(JourneyVisit.last_seen_at))
        .where(JourneyVisit.tracker_id == (tracker.id if tracker else -1)).group_by(JourneyVisit.system_id)).all()
    ids = {r[0] for r in stats}
    meta = {}
    if ids:
        for system,region in db.execute(select(EveSystem,EveRegion.name).outerjoin(EveConstellation,EveConstellation.constellation_id == EveSystem.constellation_id)
            .outerjoin(EveRegion,EveRegion.region_id == EveConstellation.region_id).where(EveSystem.system_id.in_(ids))):
            meta[system.system_id] = {'system_id': system.system_id, 'name': system.name, 'region': region,
                'security':system.security_status, 'x':system.x, 'z':system.z}
    systems = [{**meta.get(sid, {'system_id':sid,'name':f'System {sid}','region':None,'security':None,'x':None,'z':None}),
        'visits':count,'first_seen_at':utc(first).isoformat(),'last_seen_at':utc(last).isoformat()} for sid,count,first,last in stats]
    return {'character': {'character_id':character.id,'eve_id':character.character_id,'name':character.name},
        'tracking':state_payload(tracker),'from_at':start.isoformat(),'to_at':end.isoformat(),
        'total_visits':sum(r[1] for r in stats),'unique_systems':len(stats),'window_visits':total,
        'limit':LIMIT,'truncated':total > LIMIT,'systems':systems,
        'visits':[{'id':v.id,'system_id':v.system_id,'first_seen_at':utc(v.first_seen_at).isoformat(),
            'last_seen_at':utc(v.last_seen_at).isoformat(),'samples':v.samples,'gap_before':v.gap_before,
            'observed_span_seconds':max(0,(utc(v.last_seen_at)-utc(v.first_seen_at)).total_seconds())} for v in visits]}


def asset_roots(db, character_id):
    # Follow contained items only through assets owned by this exact character.
    owner_ids = select(OwnershipEntity.id).where(OwnershipEntity.character_id == character_id)
    roots = select(Asset.id.label('asset_id'),Asset.location_id.label('location_id'),literal(0).label('depth'))\
        .where(Asset.ownership_entity_id.in_(owner_ids),Asset.location_id.is_not(None)).cte('journey_asset_roots',recursive=True)
    child = aliased(Asset)
    roots = roots.union_all(select(child.id,roots.c.location_id,roots.c.depth+1).join(roots,child.parent_asset_id==roots.c.asset_id)
        .where(child.ownership_entity_id.in_(owner_ids),child.location_id.is_(None),roots.c.depth<32))
    return roots


def asset_context(db,user,character_id,system_ids,detail=False):
    if not can_view_section(user,'assets',db):
        return {'available':False,'notice':'Asset permission and an existing character asset sync are required. Journey tracking never syncs assets.','systems':{},'rows':[]}
    roots = asset_roots(db,character_id)
    system = func.coalesce(Location.system_id,EveStation.system_id,EveSystem.system_id)
    query = select(Asset.id.label('id'),Asset.type_id.label('type_id'),Asset.quantity.label('quantity'),
        Asset.last_synced_at.label('synced_at'),EveType.name.label('name'),system.label('system_id'),Location.name.label('location'))\
        .select_from(roots).join(Asset,Asset.id==roots.c.asset_id).join(Location,Location.id==roots.c.location_id)\
        .join(EveType,EveType.type_id==Asset.type_id).outerjoin(EveStation,EveStation.station_id==Location.eve_location_id)\
        .outerjoin(EveSystem,EveSystem.system_id==Location.eve_location_id).where(system.in_(system_ids)).distinct().subquery()
    grouped = db.execute(select(query.c.system_id,func.count(),func.sum(query.c.quantity),func.max(query.c.synced_at)).group_by(query.c.system_id)).all()
    rows = db.execute(select(query).order_by(query.c.name,query.c.id).limit(100)).mappings().all() if detail else []
    return {'available':True,'notice':'Current stored asset snapshot for this character only, not historical holdings. Unresolved locations are omitted; no new ESI sync is performed.',
        'systems':{str(sid):{'stacks':stacks,'quantity':quantity,'synced_at':utc(at).isoformat() if at else None} for sid,stacks,quantity,at in grouped},
        'rows':[{**dict(r),'synced_at':utc(r['synced_at']).isoformat() if r['synced_at'] else None} for r in rows],'limit':100}


def killmail_context(db,user,eve_id,system_ids,start,end,detail=False):
    if not any(can_view_section(user,s,db) for s in ['killboard','battle_reports','intel_reports']):
        return {'available':False,'notice':'Combat report permission is required.','systems':{},'rows':[]}
    attacker = select(KillmailAttacker.id).where(KillmailAttacker.killmail_id==Killmail.killmail_id,KillmailAttacker.character_id==eve_id).exists()
    query = select(Killmail.killmail_id.label('id'),Killmail.solar_system_id.label('system_id'),Killmail.killmail_time.label('time'),
        Killmail.victim_ship_type_id.label('ship_type_id'),case((Killmail.victim_character_id==eve_id,'loss'),else_='kill').label('side'))\
        .where(Killmail.solar_system_id.in_(system_ids),Killmail.killmail_time>=start,Killmail.killmail_time<end,
            or_(Killmail.victim_character_id==eve_id,attacker)).subquery()
    grouped = db.execute(select(query.c.system_id,func.sum(case((query.c.side=='kill',1),else_=0)),func.sum(case((query.c.side=='loss',1),else_=0))).group_by(query.c.system_id)).all()
    rows = db.execute(select(query,EveType.name.label('ship')).outerjoin(EveType,EveType.type_id==query.c.ship_type_id)
        .order_by(query.c.time.desc(),query.c.id.desc()).limit(100)).mappings().all() if detail else []
    return {'available':True,'notice':'Imported killmails involving this character in the selected UTC range. Coverage depends on existing killboard/Intel imports; tracking never fetches killmails.',
        'systems':{str(sid):{'kills':int(kills),'losses':int(losses)} for sid,kills,losses in grouped},'rows':[{**dict(r),'time':utc(r['time']).isoformat()} for r in rows],'limit':100}


def context(db,user,character_id,start,end,system_id=None):
    character = own_character(db,user,character_id)
    tracker = tracker_for(db,user,character_id)
    ids = set(db.scalars(select(distinct(JourneyVisit.system_id)).where(JourneyVisit.tracker_id==(tracker.id if tracker else -1),
        JourneyVisit.first_seen_at<end,JourneyVisit.last_seen_at>=start)))
    if system_id is not None:
        ids &= {system_id}
    if not ids:
        return {'assets':{'available':True,'systems':{},'rows':[]},'combat':{'available':True,'systems':{},'rows':[]}}
    return {'assets':asset_context(db,user,character_id,ids,system_id is not None),
        'combat':killmail_context(db,user,character.character_id,ids,start,end,system_id is not None)}
