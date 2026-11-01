import asyncio,importlib.util
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock,patch
import httpx,pytest
from sqlalchemy import select,func,create_engine,inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.models import EveType,EsiToken,EveCharacter,UserSectionPermission
from app.models.journey import JourneyShipSegment,JourneyTracker
from app.services import journey,journey_worker as worker
from app.services.esi_scope_policy import private_collection_enabled,requested_scopes,allowed_scopes
from .test_local_scan import env
from .test_journey import trip,path,enable,seen,due,history,history_count,refresh

def grant(e):
    e.token.scopes+=' '+worker.SHIP_SCOPE;e.db.commit()

def enable_ships(e):
    grant(e);r=e.client.patch(path(e),json={'enabled':True,'track_ship':True});assert r.status_code==200,r.text
    return e.db.scalar(select(JourneyTracker).where(JourneyTracker.character_id==e.character.id))

def segments(e):return e.db.scalars(select(JourneyShipSegment).order_by(JourneyShipSegment.id)).all()

def test_hull_consent_is_explicit_minimal_and_does_not_enable_other_collection(trip,monkeypatch):
    e=trip;from app.api import esi
    settings=e.client.get('/api/journey/settings').json()['characters'][0]
    assert not settings['track_ship'] and not settings['ship_authorized']
    monkeypatch.setattr(esi,'build_auth_url',lambda scopes,user,mode:{'scopes':scopes,'mode':mode})
    r=e.client.get(path(e,'/auth-url')+'?include_ship=true');assert r.status_code==200
    assert set(r.json()['scopes'])==worker.SCOPES|{worker.SHIP_SCOPE,'publicData'}
    assert worker.SHIP_SCOPE in allowed_scopes(e.db,e.current[0])
    assert not private_collection_enabled(e.db,e.current[0])
    assert requested_scopes(e.db,e.current[0],[worker.SHIP_SCOPE],'core')==['publicData']
    assert e.client.patch(path(e),json={'enabled':True,'track_ship':True}).status_code==409
    grant(e);settings=e.client.get('/api/journey/settings').json()['characters'][0]
    assert settings['ship_authorized'] and not settings['track_ship'] and not settings['enabled']
    assert history(e)['ship_segments']==[]

def test_broad_token_never_records_hulls_without_ship_opt_in(trip):
    e=trip;grant(e);t=enable(e);fetch=AsyncMock(return_value=(30000142,15));ref=refresh()
    asyncio.run(worker.poll(t.id,e.factory,fetch,ref))
    assert fetch.await_args.kwargs=={} and ref.await_args.kwargs=={} and segments(e)==[]

def test_ship_changes_within_one_system_never_inflate_visits_and_icons_have_type_ids(trip):
    e=trip;t=enable_ships(e);e.db.add(EveType(type_id=11178,name='Raptor'));e.db.commit();at=worker.now()-timedelta(minutes=2)
    for seconds,tid in [(0,11178),(15,11178),(30,12023),(45,11178)]:
        worker.observe(e.db,t,30000142,at+timedelta(seconds=seconds),tid)
    e.db.commit();data=history(e)
    assert data['total_visits']==1 and data['unique_systems']==1 and len(data['ship_segments'])==3
    assert [s['ship_type_id'] for s in data['ship_segments']]==[11178,12023,11178]
    assert [s['samples'] for s in data['ship_segments']]==[2,1,1]
    assert data['ship_segments'][0]['ship_name']=='Raptor' and data['ship_segments'][1]['ship_name']=='Type 12023'
    assert [s['gap_before'] for s in data['ship_segments']]==[True,False,False]
    assert len({s['visit_id'] for s in data['ship_segments']})==1
    assert all(s['first_seen_at'].endswith('+00:00') for s in data['ship_segments'])
    worker.observe(e.db,t,30000142,at,999);e.db.commit();assert len(segments(e))==3
    worker.observe(e.db,t,30000144,at+timedelta(seconds=60),11178);e.db.commit()
    assert history(e)['total_visits']==2 and not segments(e)[-1].gap_before

def test_pauses_unknown_old_visits_and_toggle_off_are_not_backfilled(trip):
    e=trip;t=enable(e);at=worker.now()-timedelta(minutes=3);seen(e,t,30000142,at)
    assert history(e)['ship_segments']==[]
    grant(e);e.client.patch(path(e),json={'enabled':True,'track_ship':True});e.db.expire_all()
    t=e.db.get(JourneyTracker,t.id);worker.observe(e.db,t,30000142,at+timedelta(seconds=30),11178);e.db.commit()
    assert segments(e)[0].first_seen_at.replace(tzinfo=at.tzinfo)==at+timedelta(seconds=30)
    assert history_count(e)==1
    e.client.patch(path(e),json={'enabled':True,'track_ship':False});e.db.expire_all()
    t=e.db.get(JourneyTracker,t.id);worker.observe(e.db,t,30000142,at+timedelta(seconds=45),12023);e.db.commit()
    assert len(segments(e))==1 and history_count(e)==1
    e.client.patch(path(e),json={'enabled':True,'track_ship':True});e.db.expire_all()
    t=e.db.get(JourneyTracker,t.id);worker.observe(e.db,t,30000142,at+timedelta(seconds=60),11178);e.db.commit()
    assert len(segments(e))==2 and segments(e)[-1].gap_before and history_count(e)==1

def test_pause_remains_available_when_ship_scope_is_revoked(trip):
    e=trip;t=enable_ships(e);e.token.scopes=' '.join(worker.SCOPES);e.db.commit()
    r=e.client.patch(path(e),json={'enabled':False});assert r.status_code==200,r.text
    state=r.json()['characters'][0];assert not state['enabled'] and state['track_ship'] and not state['ship_authorized']
    assert e.client.patch(path(e),json={'enabled':True}).status_code==409
    assert e.client.patch(path(e),json={'enabled':True,'track_ship':False}).status_code==200

def test_opt_in_forces_new_bearer_scope_and_rechecks_during_network_wait(trip):
    e=trip;grant(e);t=enable(e);ref=refresh();fetch=AsyncMock(return_value=(30000142,5))
    asyncio.run(worker.poll(t.id,e.factory,fetch,ref));assert ref.await_count==1
    e.client.patch(path(e),json={'enabled':True,'track_ship':True});e.db.expire_all()
    fetch.return_value=(30000142,5,11178);asyncio.run(worker.poll(t.id,e.factory,fetch,ref))
    assert ref.await_count==2 and ref.await_args.kwargs=={'include_ship':True}
    assert fetch.await_args.kwargs=={'include_ship':True} and len(segments(e))==1
    due(e,t)
    async def changed(*args,**kwargs):
        with e.factory() as db:
            tracker=db.get(JourneyTracker,t.id);tracker.track_ship=False;tracker.lease_token=None;db.commit()
        return 30000142,5,12023
    asyncio.run(worker.poll(t.id,e.factory,changed,ref));e.db.expire_all()
    assert len(segments(e))==1

def test_ship_scope_revoked_inflight_discards_result(trip):
    e=trip;t=enable_ships(e)
    async def revoked(*args,**kwargs):
        with e.factory() as db:db.get(EsiToken,e.token.id).scopes=' '.join(worker.SCOPES);db.commit()
        return 30000142,5,11178
    asyncio.run(worker.poll(t.id,e.factory,revoked,refresh()));e.db.expire_all()
    assert segments(e)==[] and history_count(e)==0

def test_ship_fetch_cache_discards_instance_name_and_respects_optout(trip):
    worker._ships.clear()
    with patch.object(worker,'EsiClient') as client:
        get=AsyncMock(side_effect=[({'online':True},{'cache-control':'max-age=60'}),
            ({'solar_system_id':30000142},{'cache-control':'max-age=5'}),
            ({'ship_type_id':11178,'ship_name':'PRIVATE','ship_item_id':999999999},{'cache-control':'max-age=60','age':'20'}),
            ({'solar_system_id':30000144},{'cache-control':'max-age=5'})])
        client.return_value.get_with_headers=get;client.return_value.close=AsyncMock()
        assert asyncio.run(worker.fetch_sample('fixture',9001,('ship',1),True))==(30000142,5,11178)
        assert asyncio.run(worker.fetch_sample('fixture',9001,('ship',1),True))==(30000144,5,11178)
        assert get.await_count==4 and 'PRIVATE' not in str(worker._ships) and '999999999' not in str(worker._ships)
        assert 35<(worker._ships[('ship',1)][1]-worker.now()).total_seconds()<=40
    with patch.object(worker,'EsiClient') as client:
        client.return_value.get_with_headers=AsyncMock(return_value=({'online':False},{'cache-control':'max-age=60'}));client.return_value.close=AsyncMock()
        assert asyncio.run(worker.fetch_sample('fixture',9001,('offline',1),True))[0] is None
        assert client.return_value.get_with_headers.await_count==1

@pytest.mark.parametrize('bad',[None,True,-1,2**40,'11178'])
def test_malformed_ship_response_never_records_or_caches_a_guess(trip,bad):
    with patch.object(worker,'EsiClient') as client:
        client.return_value.get_with_headers=AsyncMock(side_effect=[({'online':True},{}),({'solar_system_id':30000142},{}),({'ship_type_id':bad},{})]);client.return_value.close=AsyncMock()
        with pytest.raises(ValueError):asyncio.run(worker.fetch_sample('fixture',9001,('bad',1),True))
        assert ('bad',1) not in worker._ships

def test_ship_history_retains_ownership_limits_and_erasure(trip,monkeypatch):
    e=trip;t=enable_ships(e);at=worker.now()-timedelta(minutes=1)
    for i in range(3):worker.observe(e.db,t,30000142,at+timedelta(seconds=i*15),11178+i)
    e.db.commit();monkeypatch.setattr(journey,'SHIP_LIMIT',2)
    data=history(e);assert len(data['ship_segments'])==2 and data['ship_segments_truncated'] and data['ship_segment_count']==3
    for role in ['other','admin','host']:
        e.current[0]=e.users[role];assert e.client.get(path(e,'/history')).status_code==404
    e.current[0]=e.users['intel_analyst'];assert e.client.delete(path(e)).status_code==200
    assert segments(e)==[] and history_count(e)==0

def test_ship_migration_keeps_old_history_unknown_and_does_not_enroll():
    directory=Path(__file__).resolve().parents[1]/'alembic/versions'
    def load(name):
        spec=importlib.util.spec_from_file_location(name,directory/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    old=load('0103_journey_history');new=load('0104_journey_ship_history')
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY)');conn.exec_driver_sql('CREATE TABLE eve_characters (id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(conn)):
            old.upgrade();conn.exec_driver_sql('INSERT INTO journey_trackers (id,user_id,character_id,enabled) VALUES (1,1,1,1)')
            conn.exec_driver_sql("INSERT INTO journey_visits (tracker_id,system_id,first_seen_at,last_seen_at) VALUES (1,30000142,'2026-11-01','2026-11-01')")
            new.upgrade();assert conn.exec_driver_sql('SELECT enabled,track_ship FROM journey_trackers').one()==(1,0)
            assert conn.exec_driver_sql('SELECT COUNT(*) FROM journey_ship_segments').scalar()==0
            new.downgrade();assert 'journey_ship_segments' not in inspect(conn).get_table_names()
            assert conn.exec_driver_sql('SELECT COUNT(*) FROM journey_visits').scalar()==1
            new.upgrade()
    engine.dispose()


@pytest.mark.parametrize('include_ship',[False,True])
def test_actual_oauth_refresh_requests_only_the_selected_journey_scopes(include_ship):
    from types import SimpleNamespace
    from app.core import config,security
    response=httpx.Response(200,json={'access_token':'short-fixture','refresh_token':'rotated','expires_in':1200},request=httpx.Request('POST','https://login.eveonline.com/v2/oauth/token'))
    with patch.object(config,'get_settings',return_value=SimpleNamespace(token_encryption_key='fixture',eve_sso_client_id='fixture',eve_sso_client_secret='fixture')),patch.object(security,'decrypt_secret',return_value='refresh-fixture'),patch.object(security,'encrypt_secret',return_value='encrypted-fixture'),patch.object(worker.httpx,'AsyncClient') as client:
        post=AsyncMock(return_value=response);client.return_value.__aenter__.return_value.post=post
        result=asyncio.run(worker.refresh_access('encrypted',include_ship))
        assert result[0]=='short-fixture' and result[1]=='encrypted-fixture'
        assert set(post.await_args.kwargs['data']['scope'].split())==worker.SCOPES|({worker.SHIP_SCOPE} if include_ship else set())

def test_ship_poll_releases_database_before_all_network_waits(trip):
    from contextlib import contextmanager
    e=trip;t=enable_ships(e);active=[]
    @contextmanager
    def factory():
        with e.factory() as db:
            active.append(True)
            try:yield db
            finally:active.pop()
    async def ref(encrypted,**kwargs):
        assert not active and kwargs=={'include_ship':True}
        return 'fixture-access',encrypted,worker.now()+timedelta(minutes=10)
    async def fetch(*args,**kwargs):
        assert not active and kwargs=={'include_ship':True}
        return 30000142,5,11178
    asyncio.run(worker.poll(t.id,factory,fetch,ref));e.db.expire_all()
    assert len(segments(e))==1
