from datetime import timedelta
from sqlalchemy import select
from app.models import EsiToken,EveCharacter,Killmail,UserSectionPermission
from app.models.journey import JourneyVisit,JourneyShipSegment
from app.services import journey_exports as exports,journey_worker as worker
from .test_journey import trip,path,enable
from .test_local_scan import env


def seed(e,count):
    e.current[0]=e.users['member'];e.character=e.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==e.current[0].id))
    token=e.db.scalar(select(EsiToken).where(EsiToken.character_id==e.character.id));token.scopes=' '.join(worker.SCOPES);e.db.commit()
    tracker=enable(e);start=worker.now()-timedelta(days=20)
    rows=[JourneyVisit(tracker_id=tracker.id,system_id=30000142+i%2,first_seen_at=start+timedelta(minutes=i),last_seen_at=start+timedelta(minutes=i,seconds=30),samples=2,gap_before=i==0) for i in range(count)]
    e.db.add_all(rows);e.db.commit();return tracker,rows


def request(e,cursor=None,**params):
    response=e.client.get(path(e,'/export-history'),params={'cursor':cursor} if cursor else {'scope':'all',**params})
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='private, no-store'
    return response.json()


def test_entire_history_pages_past_2000_and_ignores_new_visits_after_snapshot(trip):
    e=trip;tracker,visits=seed(e,2001);page=request(e);seen=[];sizes=[]
    assert page['history']['window_visits']==2001 and page['history']['visit_offset']==0
    e.db.add(JourneyVisit(tracker_id=tracker.id,system_id=30000142,first_seen_at=visits[0].first_seen_at-timedelta(minutes=1),last_seen_at=visits[0].last_seen_at,samples=1,gap_before=True));e.db.commit()
    while True:
        seen.extend(v['id'] for v in page['history']['visits']);sizes.append(len(page['history']['visits']))
        if not page['next_cursor']:break
        page=request(e,page['next_cursor'])
    assert sizes==[500,500,500,500,1] and seen==[v.id for v in visits] and len(set(seen))==2001


def test_attachments_paginate_without_the_old_5000_record_omission(trip,monkeypatch):
    e=trip;tracker,visits=seed(e,1);at=visits[0].first_seen_at
    monkeypatch.setattr(exports,'ATTACHMENT_LIMIT',2)
    for i in range(7):e.db.add(Killmail(killmail_id=5000+i,killmail_hash='fixture',killmail_time=at+timedelta(seconds=i),solar_system_id=30000142,victim_character_id=e.character.character_id,victim_ship_type_id=587,canonical_esi_payload={}))
    for i in range(5):e.db.add(JourneyShipSegment(visit_id=visits[0].id,ship_type_id=587,first_seen_at=at+timedelta(seconds=i),last_seen_at=at+timedelta(seconds=i),samples=1,gap_before=False))
    e.db.commit();page=request(e);kills=page['combat']['rows'];ships=page['history']['ship_segments']
    cursor=page['combat_cursor']
    while cursor:data=request(e,cursor);kills+=data['rows'];cursor=data['next_cursor']
    cursor=page['ship_cursor']
    while cursor:data=request(e,cursor);ships+=data['rows'];cursor=data['next_cursor']
    assert len(kills)==page['combat']['total']==7 and len({r['id'] for r in kills})==7
    assert len(ships)==page['history']['ship_segment_count']==5


def test_page_boundary_lookahead_preserves_combat_until_the_next_system_sample(trip):
    e=trip;_,visits=seed(e,501);left=visits[499];right=visits[500]
    for kid,at,sid in [(9001,left.last_seen_at+timedelta(seconds=10),left.system_id),(9002,right.first_seen_at,right.system_id)]:
        e.db.add(Killmail(killmail_id=kid,killmail_hash='fixture',killmail_time=at,solar_system_id=sid,victim_character_id=e.character.character_id,victim_ship_type_id=587,canonical_esi_payload={}))
    e.db.commit();first=request(e);second=request(e,first['next_cursor'])
    assert [r['id'] for r in first['combat']['rows']]==[9001]
    assert first['history']['next_visit']['id']==right.id
    assert [r['id'] for r in second['combat']['rows']]==[9002]


def test_cursor_owner_integrity_expiry_and_erasure_are_checked(trip):
    e=trip;tracker,_=seed(e,501);page=request(e);cursor=page['next_cursor']
    assert e.client.get(path(e,'/export-history'),params={'cursor':cursor+'x'}).status_code==400
    payload=exports.decoded(cursor,e.current[0].id,e.character.id);payload['expires']=0
    assert e.client.get(path(e,'/export-history'),params={'cursor':exports.signed(payload)}).status_code==409
    for role in ['host','admin','other']:
        e.current[0]=e.users[role];assert e.client.get(path(e,'/export-history'),params={'cursor':cursor}).status_code==404
    e.current[0]=e.users['member'];tracker.revision+=1;e.db.commit()
    assert e.client.get(path(e,'/export-history'),params={'cursor':cursor}).status_code==409


def test_combat_permission_changes_and_post_snapshot_imports_are_not_exported(trip,monkeypatch):
    e=trip;_,visits=seed(e,501);monkeypatch.setattr(exports,'ATTACHMENT_LIMIT',1)
    for i in range(2):e.db.add(Killmail(killmail_id=10000+i,killmail_hash='fixture',killmail_time=visits[0].first_seen_at,solar_system_id=visits[0].system_id,victim_character_id=e.character.character_id,victim_ship_type_id=587,canonical_esi_payload={}))
    e.db.commit();first=request(e);assert first['combat_cursor']
    from datetime import datetime
    e.db.add(Killmail(killmail_id=20000,killmail_hash='fixture',killmail_time=visits[500].first_seen_at,first_seen_at=datetime.fromisoformat(first['snapshot_at'])+timedelta(seconds=1),solar_system_id=visits[500].system_id,victim_character_id=e.character.character_id,victim_ship_type_id=587,canonical_esi_payload={}))
    e.db.commit();assert request(e,first['next_cursor'])['combat']['rows']==[]
    for section in ['killboard','battle_reports','intel_reports']:e.db.add(UserSectionPermission(user_id=e.current[0].id,section=section,can_view=False))
    e.db.commit();data=request(e,first['combat_cursor'])
    assert not data['available'] and data['rows']==[] and data['next_cursor'] is None
