from datetime import timedelta
from sqlalchemy import select
from app.models import EveCharacter,EsiToken,Killmail,KillmailAttacker,UserSectionPermission
from app.services import journey,journey_worker as worker
from .test_journey import trip,path,enable,seen
from .test_local_scan import env


def populate(e,count=110):
    e.current[0]=e.users['member']
    e.character=e.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==e.current[0].id))
    e.token=e.db.scalar(select(EsiToken).where(EsiToken.character_id==e.character.id))
    e.token.scopes=' '.join(worker.SCOPES);e.db.commit()
    tracker=enable(e);at=worker.now()-timedelta(minutes=5);seen(e,tracker,30000142,at)
    for i in range(count):
        e.db.add(Killmail(killmail_id=800000+i,killmail_hash='fixture',killmail_time=at,solar_system_id=30000142,
            victim_character_id=e.character.character_id,victim_ship_type_id=500,canonical_esi_payload={}))
    # Same system/time without pilot involvement must not be exported.
    e.db.add(Killmail(killmail_id=900000,killmail_hash='fixture',killmail_time=at,solar_system_id=30000142,
        victim_character_id=999,victim_ship_type_id=500,canonical_esi_payload={}))
    # A kill where the pilot appears twice must still appear once.
    e.db.add(Killmail(killmail_id=900001,killmail_hash='fixture',killmail_time=at,solar_system_id=30000142,
        victim_character_id=999,victim_ship_type_id=500,canonical_esi_payload={}))
    e.db.flush()
    e.db.add_all([KillmailAttacker(killmail_id=900001,attacker_index=i,character_id=e.character.character_id) for i in range(2)])
    e.db.commit();return at


def test_export_has_complete_bounded_pilot_records_and_private_headers(trip):
    e=trip;populate(e)
    response=e.client.get(path(e,'/export-combat'));assert response.status_code==200,response.text
    assert response.headers['cache-control']=='private, no-store'
    data=response.json();assert data['available'] and not data['truncated']
    assert data['limit']==5000 and data['total']==111 and len(data['rows'])==111
    assert 900000 not in {r['id'] for r in data['rows']}
    assert [r['side'] for r in data['rows']].count('kill')==1
    normal=e.client.get(path(e,'/context')+'?system_id=30000142').json()['combat']
    assert len(normal['rows'])==100 and normal['truncated'] and normal['total']==111


def test_export_enforces_owner_section_access_and_date_window(trip):
    e=trip;at=populate(e,2)
    response=e.client.get(path(e,'/export-combat'),params={'from_at':(at+timedelta(minutes=1)).isoformat(),'to_at':(at+timedelta(minutes=2)).isoformat()})
    assert response.status_code==200 and response.json()['rows']==[]
    for section in ['killboard','battle_reports','intel_reports']:
        p=e.db.scalar(select(UserSectionPermission).where(UserSectionPermission.user_id==e.current[0].id,UserSectionPermission.section==section))
        if p:p.can_view=False
        else:e.db.add(UserSectionPermission(user_id=e.current[0].id,section=section,can_view=False))
    e.db.commit()
    assert not e.client.get(path(e,'/export-combat')).json()['available']
    for role in ['host','admin','director','other']:
        e.current[0]=e.users[role]
        assert e.client.get(path(e,'/export-combat')).status_code==404


def test_export_limit_is_explicit_instead_of_silently_dropping_records(trip):
    e=trip;at=populate(e,3)
    data=journey.killmail_context(e.db,e.current[0],e.character.character_id,{30000142},at-timedelta(seconds=1),at+timedelta(seconds=1),True,2)
    assert data['truncated'] and data['total']==4 and data['limit']==2 and len(data['rows'])==2
