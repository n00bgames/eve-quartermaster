"""Owner-bound, signed pagination for an entire journey export (no server media jobs)."""
import base64
from datetime import datetime,timedelta,timezone
import hashlib
import hmac
import json

from fastapi import HTTPException
from sqlalchemy import select,func,or_,case,tuple_
from app.core.config import get_settings
from app.domain.intel import utc
from app.models import EveSystem,EveType,Killmail,KillmailAttacker
from app.models.journey import JourneyVisit,JourneyShipSegment
from app.services import journey
from app.services.permissions import can_view_section

PAGE_VISITS=500
ATTACHMENT_LIMIT=5000


def signed(data):
    body=base64.urlsafe_b64encode(json.dumps(data,separators=(',',':')).encode()).decode().rstrip('=')
    signature=hmac.new(get_settings().auth_secret_key.encode(),body.encode(),hashlib.sha256).hexdigest()
    return body+'.'+signature


def decoded(cursor,user_id,character_id):
    try:
        body,signature=cursor.split('.')
        expected=hmac.new(get_settings().auth_secret_key.encode(),body.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected):raise ValueError()
        data=json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
        if data['v']!=1 or data['user']!=user_id or data['character']!=character_id:raise ValueError()
        if datetime.now(timezone.utc).timestamp()>data['expires']:
            raise HTTPException(409,'The export snapshot expired. Start a new export; already saved clips remain available.')
        return data
    except (ValueError,KeyError,TypeError):
        raise HTTPException(400,'Invalid journey export cursor')


def at(value):return utc(datetime.fromisoformat(value))
def key(visit):return [utc(visit.first_seen_at).isoformat(),visit.id]
def key_value(value):return (at(value[0]),int(value[1]))
def visit_data(v,end):
    last=min(utc(v.last_seen_at),end)
    return {'id':v.id,'system_id':v.system_id,'first_seen_at':utc(v.first_seen_at).isoformat(),'last_seen_at':last.isoformat(),
        'samples':v.samples,'gap_before':v.gap_before,'observed_span_seconds':max(0,(last-utc(v.first_seen_at)).total_seconds())}


def filters(state):
    return [JourneyVisit.tracker_id==state['tracker'],JourneyVisit.id<=state['max_visit'],
        JourneyVisit.first_seen_at<at(state['end']),JourneyVisit.last_seen_at>=at(state['start'])]


def rows_query(state):
    query=select(JourneyVisit).where(*filters(state))
    if state.get('after_visit'):query=query.where(tuple_(JourneyVisit.first_seen_at,JourneyVisit.id)>key_value(state['after_visit']))
    return query.order_by(JourneyVisit.first_seen_at,JourneyVisit.id)


def page_visits(db,state):
    query=select(JourneyVisit).where(*filters(state),tuple_(JourneyVisit.first_seen_at,JourneyVisit.id)<=key_value(state['page_end']))
    if state.get('page_after'):query=query.where(tuple_(JourneyVisit.first_seen_at,JourneyVisit.id)>key_value(state['page_after']))
    return list(db.scalars(query.order_by(JourneyVisit.first_seen_at,JourneyVisit.id)))


def attachment(db,user,character,state,kind,visits=None,next_visit=None):
    visits=visits if visits is not None else page_visits(db,state)
    ids=[v.id for v in visits]
    if kind=='ships':
        query=select(JourneyShipSegment,JourneyVisit.system_id,EveType.name).join(JourneyVisit,JourneyVisit.id==JourneyShipSegment.visit_id)\
            .outerjoin(EveType,EveType.type_id==JourneyShipSegment.ship_type_id).where(JourneyShipSegment.visit_id.in_(ids),
                JourneyShipSegment.id<=state['max_ship'],JourneyShipSegment.first_seen_at<at(state['end']),JourneyShipSegment.last_seen_at>=at(state['start']))
        time,id_column=JourneyShipSegment.first_seen_at,JourneyShipSegment.id
        available=True
    else:
        available=any(can_view_section(user,s,db) for s in ['killboard','battle_reports','intel_reports'])
        if not available:return {'kind':'combat','available':False,'rows':[],'total':0,'next_cursor':None}
        if next_visit is None:
            next_visit=db.scalar(select(JourneyVisit).where(*filters(state),tuple_(JourneyVisit.first_seen_at,JourneyVisit.id)>key_value(state['page_end']))
                .order_by(JourneyVisit.first_seen_at,JourneyVisit.id).limit(1))
        end=min(at(state['end']),utc(next_visit.first_seen_at) if next_visit and not next_visit.gap_before else utc(visits[-1].last_seen_at)+timedelta(microseconds=1))
        start=max(at(state['start']),utc(visits[0].first_seen_at))
        attacker=select(KillmailAttacker.id).where(KillmailAttacker.killmail_id==Killmail.killmail_id,KillmailAttacker.character_id==character.character_id).exists()
        query=select(Killmail.killmail_id.label('id'),Killmail.solar_system_id.label('system_id'),Killmail.killmail_time.label('time'),
            Killmail.victim_ship_type_id.label('ship_type_id'),EveType.name.label('ship'),case((Killmail.victim_character_id==character.character_id,'loss'),else_='kill').label('side'))\
            .outerjoin(EveType,EveType.type_id==Killmail.victim_ship_type_id).where(Killmail.solar_system_id.in_({v.system_id for v in visits}),
                Killmail.killmail_time>=start,Killmail.killmail_time<end,Killmail.first_seen_at<=at(state['as_of']),or_(Killmail.victim_character_id==character.character_id,attacker))
        time,id_column=Killmail.killmail_time,Killmail.killmail_id
    total=db.scalar(select(func.count()).select_from(query.subquery())) or 0
    if state.get('after_row'):query=query.where(tuple_(time,id_column)>key_value(state['after_row']))
    records=db.execute(query.order_by(time,id_column).limit(ATTACHMENT_LIMIT+1)).all()
    more=len(records)>ATTACHMENT_LIMIT;records=records[:ATTACHMENT_LIMIT]
    if kind=='ships':
        rows=[{'id':s.id,'visit_id':s.visit_id,'system_id':sid,'ship_type_id':s.ship_type_id,'ship_name':name or f'Type {s.ship_type_id}',
            'first_seen_at':utc(s.first_seen_at).isoformat(),'last_seen_at':min(utc(s.last_seen_at),at(state['end'])).isoformat(),'samples':s.samples,'gap_before':s.gap_before} for s,sid,name in records]
        last=[rows[-1]['first_seen_at'],rows[-1]['id']] if rows else None
    else:
        rows=[{**dict(r._mapping),'time':utc(r.time).isoformat()} for r in records]
        last=[rows[-1]['time'],rows[-1]['id']] if rows else None
    return {'kind':kind,'available':available,'rows':rows,'total':total,'next_cursor':signed({**state,'stage':kind,'after_row':last}) if more else None}


def export_page(db,user,character_id,scope='range',from_at=None,to_at=None,cursor=None):
    character=journey.own_character(db,user,character_id)
    tracker=journey.tracker_for(db,user,character_id)
    if cursor:
        state=decoded(cursor,user.id,character_id)
        if not tracker or tracker.id!=state['tracker'] or tracker.revision!=state['revision']:
            raise HTTPException(409,'Journey settings or history changed. Start a new export; saved clips remain available.')
    else:
        now=journey.now()
        tracker_id=tracker.id if tracker else -1
        earliest=db.scalar(select(func.min(JourneyVisit.first_seen_at)).where(JourneyVisit.tracker_id==tracker_id))
        start,end=journey.window(from_at,to_at) if scope=='range' else (utc(earliest) if earliest else now,now+timedelta(microseconds=1))
        end=min(end,now+timedelta(microseconds=1))
        state={'v':1,'user':user.id,'character':character_id,'tracker':tracker_id,'revision':tracker.revision if tracker else 0,
            'start':start.isoformat(),'end':end.isoformat(),'as_of':now.isoformat(),'expires':now.timestamp()+172800,
            'max_visit':db.scalar(select(func.max(JourneyVisit.id)).where(JourneyVisit.tracker_id==tracker_id)) or 0,
            'max_ship':db.scalar(select(func.max(JourneyShipSegment.id)).join(JourneyVisit,JourneyVisit.id==JourneyShipSegment.visit_id).where(JourneyVisit.tracker_id==tracker_id)) or 0,
            'after_visit':None,'offset':0,'stage':'visits'}
        state['total']=db.scalar(select(func.count()).select_from(JourneyVisit).where(*filters(state))) or 0
    if state['stage'] in {'ships','combat'}:return attachment(db,user,character,state,state['stage'])
    records=list(db.scalars(rows_query(state).limit(PAGE_VISITS+1)))
    visits=records[:PAGE_VISITS];next_visit=records[PAGE_VISITS] if len(records)>PAGE_VISITS else None
    ids={v.system_id for v in visits};systems=[]
    for system in db.scalars(select(EveSystem).where(EveSystem.system_id.in_(ids))):
        systems.append({'system_id':system.system_id,'name':system.name,'x':system.x,'z':system.z,'security':system.security_status,
            'region':None,'visits':sum(v.system_id==system.system_id for v in visits),'first_seen_at':state['start'],'last_seen_at':state['end']})
    known={s['system_id'] for s in systems}
    systems.extend({'system_id':sid,'name':f'System {sid}','x':None,'z':None,'security':None,'region':None,'visits':0,'first_seen_at':state['start'],'last_seen_at':state['end']} for sid in ids-known)
    page_state={**state,'page_after':state['after_visit'],'page_end':key(visits[-1])} if visits else state
    ships=attachment(db,user,character,page_state,'ships',visits,next_visit) if visits else {'rows':[],'total':0,'next_cursor':None}
    combat=attachment(db,user,character,page_state,'combat',visits,next_visit) if visits else {'rows':[],'total':0,'available':True,'next_cursor':None}
    history={'character':{'character_id':character.id,'eve_id':character.character_id,'name':character.name},
        'tracking':{**journey.state_payload(tracker),'authorized':journey.character_token(db,user.id,character_id) is not None,'ship_authorized':journey.character_token(db,user.id,character_id,True) is not None},'from_at':state['start'],'to_at':state['end'],
        'total_visits':state['total'],'window_visits':state['total'],'unique_systems':len(ids),'limit':PAGE_VISITS,'truncated':False,
        'systems':systems,'visits':[visit_data(v,at(state['end'])) for v in visits],'next_visit':visit_data(next_visit,at(state['end'])) if next_visit else None,
        'visit_offset':state['offset'],'ship_segments':ships['rows'],'ship_segment_count':ships['total'],'ship_segments_truncated':bool(ships['next_cursor']),'ship_segment_limit':ATTACHMENT_LIMIT}
    return {'kind':'visits','history':history,'combat':{**combat,'truncated':False,'limit':ATTACHMENT_LIMIT},
        'ship_cursor':ships['next_cursor'],'combat_cursor':combat['next_cursor'],
        'next_cursor':signed({**state,'after_visit':key(visits[-1]),'offset':state['offset']+len(visits)}) if next_visit else None,'snapshot_at':state['as_of']}
