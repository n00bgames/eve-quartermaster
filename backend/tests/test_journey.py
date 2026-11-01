import asyncio
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import AsyncMock,patch
import importlib.util
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,func,inspect,select
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.api import journey as api
from app.models import Asset,EsiToken,EveCharacter,EveSystem,EveType,Location,OwnershipEntity,Killmail,KillmailAttacker,UserSectionPermission
from app.models.journey import JourneyTracker,JourneyVisit
from app.services import journey,journey_worker as worker
from app.services.esi_scope_policy import private_collection_enabled,requested_scopes
from app.domain.intel import utc
from .test_local_scan import env

@pytest.fixture
def trip(env):
    env.app.include_router(api.router,prefix='/api')
    env.current[0]=env.users['intel_analyst']
    character=env.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==env.current[0].id))
    token=env.db.scalar(select(EsiToken).where(EsiToken.character_id==character.id))
    token.scopes='publicData '+' '.join(sorted(worker.SCOPES));env.db.commit()
    env.character=character;env.token=token
    env.factory=lambda:Session(env.db.bind,expire_on_commit=False)
    worker._access.clear();worker._online.clear()
    yield env
    worker._access.clear();worker._online.clear()

def path(e,suffix=''):
    return f'/api/journey/characters/{e.character.id}'+suffix

def enable(e):
    r=e.client.patch(path(e),json={'enabled':True,'interval_seconds':15})
    assert r.status_code==200,r.text
    return e.db.scalar(select(JourneyTracker).where(JourneyTracker.character_id==e.character.id))

def seen(e,tracker,sid,at):
    worker.observe(e.db,tracker,sid,at);e.db.commit()

def history(e,query=''):
    r=e.client.get(path(e,'/history')+query);assert r.status_code==200,r.text
    assert r.headers['cache-control']=='private, no-store'
    return r.json()

def refresh():
    return AsyncMock(return_value=('transient-access','rotated-fixture',worker.now()+timedelta(minutes=10)))

def due(e,tracker):
    e.db.expire_all();tracker.next_poll_at=worker.now()-timedelta(seconds=1);e.db.commit()

def test_off_by_default_explicit_minimal_consent_and_utilities(trip,monkeypatch):
    e=trip
    data=e.client.get('/api/journey/settings').json()
    assert len(data['characters'])==1 and not data['characters'][0]['enabled']
    assert data['characters'][0]['authorized'] and history(e)['total_visits']==0
    assert not private_collection_enabled(e.db,e.current[0])
    assert requested_scopes(e.db,e.current[0],['esi-assets.read_assets.v1'],'core')==['publicData']
    e.token.scopes='publicData';e.db.commit()
    assert e.client.patch(path(e),json={'enabled':True}).status_code==409
    from app.api import esi
    monkeypatch.setattr(esi,'build_auth_url',lambda scopes,user,mode:{'scopes':scopes,'mode':mode})
    consent=e.client.get(path(e,'/auth-url')).json()
    assert set(consent['scopes'])==worker.SCOPES|{'publicData'}
    api.validate_consent_character(e.db,e.current[0].id,consent['mode'],e.character.character_id)
    with pytest.raises(HTTPException):api.validate_consent_character(e.db,e.current[0].id,consent['mode'],123)
    assert e.db.scalar(select(func.count()).select_from(JourneyTracker))==0

@pytest.mark.parametrize('role',['host','admin','director','member','other'])
def test_other_accounts_including_staff_cannot_read_configure_consent_or_erase(trip,role):
    e=trip;tracker=enable(e);seen(e,tracker,30000142,worker.now()-timedelta(minutes=1))
    e.current[0]=e.users[role]
    for suffix in ['/history','/context','/auth-url']:
        assert e.client.get(path(e,suffix)).status_code==404
    assert e.client.patch(path(e),json={'enabled':False}).status_code==404
    assert e.client.delete(path(e)).status_code==404
    assert history_count(e)==1

def history_count(e):return e.db.scalar(select(func.count()).select_from(JourneyVisit))

def test_only_changes_make_visits_and_returns_increment_system_totals(trip):
    e=trip;t=enable(e);at=worker.now()-timedelta(minutes=2)
    for seconds,sid in [(0,30000142),(15,30000142),(30,30000001),(45,30000142),(60,30000142)]:seen(e,t,sid,at+timedelta(seconds=seconds))
    data=history(e)
    assert data['total_visits']==3 and data['unique_systems']==2 and data['window_visits']==3
    assert [v['samples'] for v in data['visits']]==[2,1,2]
    assert [v['gap_before'] for v in data['visits']]==[True,False,False]
    assert data['visits'][0]['observed_span_seconds']==15
    assert next(s for s in data['systems'] if s['system_id']==30000142)['visits']==2
    # Repeated/stale delivery cannot fabricate another visit or sample.
    seen(e,t,999,at)
    assert history_count(e)==3
    assert not e.db.scalar(select(func.count()).select_from(Killmail))

def test_pause_resume_clock_gap_and_erasure_break_continuity(trip):
    e=trip;t=enable(e);at=worker.now()-timedelta(minutes=10)
    seen(e,t,30000142,at);seen(e,t,30000142,at+timedelta(minutes=5))
    assert history_count(e)==2
    assert e.client.patch(path(e),json={'enabled':False}).status_code==200
    t=e.db.get(JourneyTracker,t.id);assert not t.enabled and t.current_visit_id is None
    enable(e);seen(e,t,30000142,worker.now()-timedelta(seconds=1))
    assert history_count(e)==3
    r=e.client.delete(path(e));assert r.status_code==200 and r.json()['tracking_paused']
    assert history(e)['total_visits']==0
    assert not e.db.get(JourneyTracker,t.id).enabled

def test_online_sampler_cache_due_time_and_offline_gap(trip):
    e=trip;t=enable(e);fetch=AsyncMock(return_value=(30000142,60));ref=refresh()
    asyncio.run(worker.poll(t.id,e.factory,fetch,ref));e.db.expire_all()
    assert fetch.await_count==ref.await_count==1 and history_count(e)==1
    assert (utc(e.db.get(JourneyTracker,t.id).next_poll_at)-worker.now()).total_seconds()>55
    asyncio.run(worker.poll(t.id,e.factory,fetch,ref));assert fetch.await_count==1
    due(e,t);asyncio.run(worker.poll(t.id,e.factory,fetch,ref));assert ref.await_count==1 and fetch.await_count==2
    e.db.expire_all();assert history_count(e)==1
    due(e,t);fetch.return_value=(None,60);asyncio.run(worker.poll(t.id,e.factory,fetch,ref));e.db.expire_all()
    assert e.db.get(JourneyTracker,t.id).state=='offline' and e.db.get(JourneyTracker,t.id).current_visit_id is None
    due(e,t);fetch.return_value=(30000142,5);asyncio.run(worker.poll(t.id,e.factory,fetch,ref));e.db.expire_all()
    assert history_count(e)==2 and history(e)['visits'][-1]['gap_before']

@pytest.mark.parametrize('action',['pause','revoke','transfer','erase','lose_permission'])
def test_network_inflight_results_recheck_consent_and_ownership(trip,action):
    e=trip;t=enable(e)
    async def fetch(*args):
        with e.factory() as db:
            row=db.get(JourneyTracker,t.id)
            if action=='pause':row.enabled=False;row.lease_token=None
            elif action=='revoke':db.get(EsiToken,e.token.id).revoked_at=worker.now()
            elif action=='transfer':db.get(EveCharacter,e.character.id).owner_user_id=e.users['other'].id
            elif action=='erase':row.enabled=False;row.lease_token=None
            else:db.add(UserSectionPermission(user_id=e.current[0].id,section_key='navigation',can_view=False))
            db.commit()
        return 30000142,5
    asyncio.run(worker.poll(t.id,e.factory,fetch,refresh()));e.db.expire_all()
    assert history_count(e)==0

def test_lease_is_exclusive_and_obsolete_rotation_never_overwrites_token(trip):
    e=trip;t=enable(e)
    with e.factory() as db:assert worker.claim(db,t.id,'first',worker.now())
    with e.factory() as db:assert not worker.claim(db,t.id,'second',worker.now())
    e.db.expire_all();t.lease_until=worker.now()-timedelta(seconds=1);e.db.commit()
    async def changed(encrypted):
        with e.factory() as db:db.get(EsiToken,e.token.id).encrypted_refresh_token='newer-rotation';db.commit()
        return 'not-persisted-access','stale-rotation',worker.now()+timedelta(minutes=5)
    fetch=AsyncMock(return_value=(30000142,5))
    asyncio.run(worker.poll(t.id,e.factory,fetch,changed));e.db.expire_all()
    assert e.db.get(EsiToken,e.token.id).encrypted_refresh_token=='newer-rotation' and not fetch.await_count

def test_failure_backoff_and_reauthorization_stop_do_not_log_fake_positions(trip):
    e=trip;t=enable(e);bad=AsyncMock(side_effect=RuntimeError('fixture transport error'))
    asyncio.run(worker.poll(t.id,e.factory,bad,refresh()));e.db.expire_all()
    row=e.db.get(JourneyTracker,t.id)
    assert row.state=='unavailable' and row.current_visit_id is None and history_count(e)==0
    assert (utc(row.next_poll_at)-worker.now()).total_seconds()>55
    e.db.get(EsiToken,e.token.id).revoked_at=worker.now();e.db.commit();due(e,row)
    asyncio.run(worker.poll(t.id,e.factory,bad,refresh()));e.db.expire_all()
    assert not e.db.get(JourneyTracker,t.id).enabled
    assert e.db.get(JourneyTracker,t.id).state=='authorization_needed'

def test_sample_cache_headers_and_online_cache_avoid_extra_endpoint_calls(trip):
    assert worker.cache_seconds({'cache-control':'public, max-age=60','age':'10'},5)==50
    assert worker.cache_seconds({'cache-control':'max-age=5','age':'10'},5)==0
    assert worker.cache_seconds({'cache-control':'max-age=broken'},15)==15
    with patch.object(worker,'EsiClient') as client:
        client.return_value.get_with_headers=AsyncMock(side_effect=[({'online':True},{'cache-control':'max-age=60'}),
            ({'solar_system_id':30000142,'structure_id':123},{'cache-control':'max-age=20'}),
            ({'solar_system_id':30000142},{'cache-control':'max-age=20'})])
        client.return_value.close=AsyncMock()
        assert asyncio.run(worker.fetch_sample('access',9001,('cache',1)))==(30000142,20)
        assert asyncio.run(worker.fetch_sample('access',9001,('cache',1)))==(30000142,20)
        assert client.return_value.get_with_headers.await_count==3

def test_private_context_counts_nested_own_assets_and_distinct_own_killmails(trip):
    e=trip;e.current[0]=e.users['member'];e.character=e.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==e.current[0].id))
    e.token=e.db.scalar(select(EsiToken).where(EsiToken.character_id==e.character.id));e.token.scopes=' '.join(worker.SCOPES)
    e.db.commit();t=enable(e);at=worker.now()-timedelta(minutes=5);seen(e,t,30000142,at)
    other=e.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==e.users['other'].id))
    owner=OwnershipEntity(character_id=e.character.id,display_name='Mine');outsider=OwnershipEntity(character_id=other.id,display_name='Private other')
    location=Location(name='Stored station',eve_location_id=60000001,system_id=30000142)
    e.db.add_all([owner,outsider,location,EveType(type_id=500,name='Warrior II')]);e.db.flush()
    container=Asset(ownership_entity_id=owner.id,type_id=500,quantity=1,location_id=location.id,last_synced_at=at)
    e.db.add(container);e.db.flush()
    e.db.add_all([Asset(ownership_entity_id=owner.id,type_id=500,quantity=25,parent_asset_id=container.id,last_synced_at=at),
        Asset(ownership_entity_id=outsider.id,type_id=500,quantity=999,location_id=location.id),
        Asset(ownership_entity_id=outsider.id,type_id=500,quantity=888,parent_asset_id=container.id)])
    for kid,victim in [(100,999),(101,e.character.character_id),(102,999)]:
        e.db.add(Killmail(killmail_id=kid,killmail_hash='fixture',killmail_time=at,solar_system_id=30000142,victim_character_id=victim,victim_ship_type_id=500,canonical_esi_payload={}))
    e.db.flush()
    e.db.add_all([KillmailAttacker(killmail_id=100,attacker_index=i,character_id=e.character.character_id) for i in range(2)])
    e.db.commit()
    r=e.client.get(path(e,'/context')+'?system_id=30000142');assert r.status_code==200,r.text
    data=r.json()
    assert data['assets']['systems']['30000142']['quantity']==26 and len(data['assets']['rows'])==2
    assert data['combat']['systems']['30000142']=={'kills':1,'losses':1}
    assert {k['id'] for k in data['combat']['rows']}=={100,101}
    assert all(datetime.fromisoformat(k['time'])==at for k in data['combat']['rows'])
    assert all(datetime.fromisoformat(a['synced_at'])==at for a in data['assets']['rows'])
    e.current[0]=e.users['intel_analyst']
    # Utility role has no character inventory access; no implicit collection or exposure.
    r=journey.asset_context(e.db,e.current[0],e.character.id,{30000142},True)
    assert not r['available'] and r['rows']==[]

def test_date_window_limits_and_missing_sde_coordinates_preserve_all_time_totals(trip):
    e=trip;t=enable(e);at=worker.now()-timedelta(days=9)
    seen(e,t,999,at);seen(e,t,30000142,worker.now()-timedelta(minutes=1))
    data=history(e)
    assert data['total_visits']==2 and data['window_visits']==1
    assert next(s for s in data['systems'] if s['system_id']==999)['x'] is None
    for q in ['?from_at=2026-01-02T00:00:00Z&to_at=2026-01-01T00:00:00Z','?from_at=2000-01-01T00:00:00Z']:
        assert e.client.get(path(e,'/history')+q).status_code==422
    assert e.client.patch(path(e),json={'enabled':True,'interval_seconds':1}).status_code==422

def test_migration_upgrade_downgrade_does_not_enroll_existing_characters():
    engine=create_engine('sqlite://');path=Path(__file__).resolve().parents[1]/'alembic/versions/0103_journey_history.py'
    spec=importlib.util.spec_from_file_location('journey_migration',path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('CREATE TABLE eve_characters (id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade();assert conn.scalar(select(func.count()).select_from(JourneyTracker))==0
            assert {'journey_trackers','journey_visits'}<=set(inspect(conn).get_table_names())
            migration.downgrade();assert 'journey_visits' not in inspect(conn).get_table_names()
            migration.upgrade()
    engine.dispose()


def test_real_auth_quartermaster_can_opt_in_own_journey_only(trip):
    from app.api.auth import get_current_user
    from app.core.security import create_access_token
    e=trip;user=e.users['quartermaster']
    char=e.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==user.id))
    token=e.db.scalar(select(EsiToken).where(EsiToken.character_id==char.id));token.scopes=' '.join(worker.SCOPES);e.db.commit()
    e.app.dependency_overrides.pop(get_current_user)
    assert e.client.get('/api/journey/settings').status_code==401
    headers={'Authorization':'Bearer '+create_access_token(str(user.id))}
    endpoint=f'/api/journey/characters/{char.id}'
    assert e.client.patch(endpoint,headers=headers,json={'enabled':True}).status_code==200
    assert e.client.patch(path(e),headers=headers,json={'enabled':False}).status_code==404
    assert e.client.delete(endpoint,headers=headers).status_code==200


def test_worker_releases_db_before_auth_and_location_waits(trip):
    from contextlib import contextmanager
    e=trip;t=enable(e);active=[]
    @contextmanager
    def factory():
        with e.factory() as db:
            active.append(True)
            try:yield db
            finally:active.pop()
    async def refresh_without_connection(encrypted):
        assert not active
        return 'short-access',encrypted,worker.now()+timedelta(minutes=10)
    async def fetch_without_connection(*args):
        assert not active
        return 30000142,5
    asyncio.run(worker.poll(t.id,factory,fetch_without_connection,refresh_without_connection));e.db.expire_all()
    assert history_count(e)==1


def test_terminal_esi_authorization_failure_pauses_collection(trip):
    e=trip;t=enable(e)
    asyncio.run(worker.poll(t.id,e.factory,AsyncMock(side_effect=HTTPException(401,'fixture')),refresh()))
    e.db.expire_all();assert not e.db.get(JourneyTracker,t.id).enabled
    assert e.db.get(JourneyTracker,t.id).state=='authorization_needed'


def test_revoked_character_can_request_fresh_minimal_consent_without_starting_tracking(trip,monkeypatch):
    from app.api import esi
    e=trip;e.token.revoked_at=worker.now();e.db.commit()
    monkeypatch.setattr(esi,'build_auth_url',lambda scopes,user,mode:{'scopes':scopes,'mode':mode})
    response=e.client.get(path(e,'/auth-url'));assert response.status_code==200,response.text
    assert set(response.json()['scopes'])==worker.SCOPES|{'publicData'}
    assert not e.client.get('/api/journey/settings').json()['characters'][0]['enabled']


def test_pause_during_oauth_preserves_rotation_but_never_fetches_location(trip):
    e=trip;t=enable(e)
    async def paused_refresh(encrypted):
        with e.factory() as db:
            row=db.get(JourneyTracker,t.id);row.enabled=False;row.lease_token=None;db.commit()
        return 'unused-access','valid-new-rotation',worker.now()+timedelta(minutes=10)
    fetch=AsyncMock(return_value=(30000142,5))
    asyncio.run(worker.poll(t.id,e.factory,fetch,paused_refresh));e.db.expire_all()
    assert e.db.get(EsiToken,e.token.id).encrypted_refresh_token=='valid-new-rotation'
    assert not fetch.await_count and history_count(e)==0
