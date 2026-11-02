import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api import battle_reports as api
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, User, EveCharacter, EveSystem, Killmail, KillboardSyncRun, BattleReportShare
from app.services import battle_report_discovery as service
from app.services.battle_report_scope import BattleWindow
from app.services.battle_reports import build_latest_battle_report
from app.services.killboard_sync import upsert_killmail


@pytest.fixture
def battle_env(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'battle.sqlite'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    at=service.now()-timedelta(hours=1)
    def raw(kid,*,system=30000142,offset=0,selected=False):
        return {'killmail_id':kid,'killmail_time':(at+timedelta(minutes=offset)).isoformat(),
            'solar_system_id':system,'victim':{'character_id':9000+kid,'corporation_id':20+kid,'ship_type_id':587,'damage_taken':100,'items':[]},
            'attackers':[{'character_id':9001 if selected else 8000+kid,'corporation_id':10 if selected else 50+kid,'ship_type_id':587,'damage_done':100,'final_blow':True}]}
    with factory() as db:
        user=User(email='battle@test.invalid',display_name='Example Analyst',role='host');other=User(email='other@test.invalid',display_name='Other Analyst',role='host');db.add_all([user,other]);db.flush()
        # Keep the selected pilot distinct from the first victim.
        db.add(EveCharacter(character_id=9001,name='Example Pilot',owner_user_id=user.id))
        db.add_all([EveSystem(system_id=30000142,name='Example Arena'),EveSystem(system_id=30000144,name='Example Neighbor')]);db.flush()
        seed=raw(1,selected=True);seed['victim']['character_id']=9991
        upsert_killmail(db,killmail_id=1,killmail_hash='a'*40,esi_payload=seed,zkill_payload={'zkb':{'totalValue':100000000}},owner_type='character',owner_id=9001,feed='kills');db.commit()
        uid,other_id=user.id,other.id
    scope={'start_time':(at-timedelta(minutes=20)).isoformat(),'end_time':(at+timedelta(minutes=20)).isoformat(),'system_ids':[30000142]}
    with patch.object(service,'SessionLocal',factory):
        yield SimpleNamespace(engine=engine,factory=factory,at=at,raw=raw,scope=scope,uid=uid,other_id=other_id)
    engine.dispose()


def create_job(e):
    with e.factory() as db:
        run=service.create_job(db,db.get(User,e.uid),character_id=9001,seed_killmail_id=1,battle_window=e.scope)
        db.commit();return run.id


def entry(kid,e,**kwargs):
    return {'killmail_id':kid,'killmail_time':e.raw(kid,**kwargs)['killmail_time'],'zkb':{'hash':('a' if kid==1 else 'b')*40,'totalValue':100000000}}


def test_all_system_window_includes_disconnected_kills_and_preserves_default(battle_env):
    e=battle_env
    with e.factory() as db:
        for kid in (2,3):
            upsert_killmail(db,killmail_id=kid,killmail_hash='b'*40,esi_payload=e.raw(kid,system=30000144 if kid==3 else 30000142),
                zkill_payload={'zkb':{'totalValue':100000000}},owner_type='system',owner_id=30000142,feed='battle')
        db.commit();user=db.get(User,e.uid)
        narrow=build_latest_battle_report(db,user,character_id=9001,seed_killmail_id=1)
        full=build_latest_battle_report(db,user,character_id=9001,seed_killmail_id=1,battle_window=e.scope)
        assert narrow['report']['killmail_count']==1
        assert {r['killmail_id'] for r in full['report']['timeline']}=={1,2}
        assert full['report']['estimated_total_value']==200000000
        assert full['coverage']['scope']=='system_window'
        assert full['coverage']['search_window']==BattleWindow.model_validate(e.scope).model_dump(mode='json')


def test_window_validation_and_anchor_authorization(battle_env):
    e=battle_env
    for scope in [dict(e.scope,end_time=e.scope['start_time']),dict(e.scope,end_time=(e.at+timedelta(hours=13)).isoformat()),
        dict(e.scope,system_ids=list(range(1,10))),dict(e.scope,start_time='2026-01-01T00:00')]:
        with pytest.raises(ValidationError):BattleWindow.model_validate(scope)
    with e.factory() as db:
        with pytest.raises(PermissionError):
            user=db.get(User,e.other_id);user.role='member';db.commit()
            build_latest_battle_report(db,user,character_id=9001,battle_window=e.scope)
        with pytest.raises(ValueError,match='contain'):
            build_latest_battle_report(db,db.get(User,e.uid),character_id=9001,battle_window=dict(e.scope,system_ids=[30000144]))


def test_pages_continue_past_cached_records_and_import_absent_pilot_kills(battle_env):
    e=battle_env;job=create_job(e);calls=[]
    class Discovery:
        async def fetch_page(self,target,page):
            assert e.engine.pool.checkedout()==0
            calls.append(page)
            return {1:[entry(1,e)],2:[entry(2,e),entry(2,e)],3:[entry(4,e),entry(5,e)]}.get(page,[])
    class Canonical:
        async def get(self,path):
            assert e.engine.pool.checkedout()==0
            kid=int(path.split('/')[2])
            return e.raw(kid,offset=-60 if kid==4 else 0,system=30000144 if kid==5 else 30000142)
    asyncio.run(service.execute(job,discovery=Discovery(),canonical=Canonical()))
    assert calls==[1,2,3,4]
    with e.factory() as db:
        run=db.get(KillboardSyncRun,job)
        assert run.status=='complete' and run.imported_count==1
        assert set(db.scalars(select(Killmail.killmail_id)))=={1,2}
        assert run.discovered_count==4
        assert service.report_coverage(db,db.get(User,e.uid),job,character_id=9001,window=e.scope)['status']=='complete'


def test_pause_and_resume_without_duplicate_kills(battle_env):
    e=battle_env;job=create_job(e)
    class Discovery:
        async def fetch_page(self,target,page):return [entry(2,e)] if page==1 else []
    class Canonical:
        async def get(self,path):return e.raw(2)
    asyncio.run(service.execute(job,discovery=Discovery(),canonical=Canonical(),budget_seconds=0))
    with e.factory() as db:assert db.get(KillboardSyncRun,job).status=='paused'
    asyncio.run(service.execute(job,discovery=Discovery(),canonical=Canonical()))
    asyncio.run(service.execute(job,discovery=Discovery(),canonical=Canonical()))
    with e.factory() as db:
        assert db.get(KillboardSyncRun,job).status=='complete'
        assert len(list(db.scalars(select(Killmail))))==2


@pytest.mark.parametrize('revoke',['cancel','permission'])
def test_cancel_or_permission_loss_during_network_discards_late_writes(battle_env,revoke):
    e=battle_env;job=create_job(e)
    class Discovery:
        async def fetch_page(self,target,page):return [entry(2,e)]
    class Canonical:
        async def get(self,path):
            with e.factory() as db:
                if revoke=='cancel':db.get(KillboardSyncRun,job).status='cancelled'
                else:db.get(User,e.uid).deleted_at=service.now()
                db.commit()
            return e.raw(2)
    asyncio.run(service.execute(job,discovery=Discovery(),canonical=Canonical()))
    with e.factory() as db:assert db.get(Killmail,2) is None


def test_failed_record_and_page_cap_are_explicit_partial_coverage(battle_env):
    e=battle_env;job=create_job(e)
    class Discovery:
        async def fetch_page(self,target,page):return [entry(2,e)] if page==1 else []
    class Canonical:
        async def get(self,path):raise ValueError('fixture missing canonical record')
    asyncio.run(service.execute(job,discovery=Discovery(),canonical=Canonical()))
    with e.factory() as db:assert db.get(KillboardSyncRun,job).status=='partial'


def test_job_and_metadata_are_owner_scoped(battle_env):
    e=battle_env;job=create_job(e)
    with e.factory() as db:
        with pytest.raises(LookupError):service.require_job(db,db.get(User,e.other_id),job)
        with pytest.raises(ValueError):service.report_coverage(db,db.get(User,e.uid),job,character_id=9001,
            window=dict(e.scope,end_time=(e.at+timedelta(minutes=10)).isoformat()))


def test_render_share_and_public_snapshot_preserve_expanded_scope(battle_env):
    e=battle_env;job=create_job(e)
    with e.factory() as db:
        upsert_killmail(db,killmail_id=2,killmail_hash='b'*40,esi_payload=e.raw(2),zkill_payload={'zkb':{'totalValue':200000000}},owner_type='system',owner_id=30000142,feed='battle')
        db.get(KillboardSyncRun,job).status='partial';db.commit()
    app=FastAPI(version='2.0.1');app.include_router(api.router,prefix='/api')
    def database():
        with e.factory() as db:yield db
    def identity():
        with e.factory() as db:
            user=db.get(User,e.uid);db.expunge(user);return user
    app.dependency_overrides[get_db]=database;app.dependency_overrides[get_current_user]=identity
    request=dict(character_id=9001,seed_killmail_id=1,battle_window=e.scope,discovery_job_id=job)
    with TestClient(app) as client,patch.object(api,'refresh_killboard_entity_names',new=__import__('unittest.mock',fromlist=['AsyncMock']).AsyncMock()):
        report=client.post('/api/battle-reports/render',json=request)
        assert report.status_code==200,report.text
        assert report.json()['report']['killmail_count']==2
        saved=client.post('/api/battle-reports/shares',json={**request,'anonymous':True})
        assert saved.status_code==201,saved.text
        token=saved.json()['share_token']
        public=client.get('/api/battle-reports/public/'+token).json()
        assert public['report']['killmail_count']==2
        assert public['coverage']['scope']=='system_window' and public['coverage']['discovery']['status']=='partial'
        assert 'job_id' not in public['coverage']['discovery']
        with e.factory() as db:
            db.get(KillboardSyncRun,job).status='complete';db.commit()
        assert client.get('/api/battle-reports/public/'+token).json()['coverage']['discovery']['status']=='partial'


def test_month_crossing_and_recent_targets():
    window=BattleWindow(start_time='2026-08-31T23:30:00Z',end_time='2026-09-01T00:30:00Z',system_ids=[30000142])
    targets=service.targets_for(window)
    assert [(r['year'],r['month']) for r in targets]==[(2026,8),(2026,9)]
    at=service.now()
    recent=service.targets_for(BattleWindow(start_time=at-timedelta(hours=2),end_time=at,system_ids=[30000142]))
    assert len(recent)==1 and recent[0]['past_seconds']%3600==0


def test_page_limit_never_reports_complete(battle_env):
    e=battle_env;job=create_job(e)
    class Discovery:
        async def fetch_page(self,target,page):return [entry(1,e)]
    class Canonical:
        async def get(self,path):raise AssertionError('Known kills must not be fetched again')
    with patch.object(service,'MAX_PAGES',1):
        asyncio.run(service.execute(job,discovery=Discovery(),canonical=Canonical()))
    with e.factory() as db:
        run=db.get(KillboardSyncRun,job)
        assert run.status=='partial' and run.failed_count==1


def test_discovery_controls_require_owner_and_do_not_start_http_during_request(battle_env):
    e=battle_env
    app=FastAPI();app.include_router(api.router,prefix='/api')
    actor=[e.uid]
    def database():
        with e.factory() as db:yield db
    def identity():
        with e.factory() as db:
            row=db.get(User,actor[0]);db.expunge(row);return row
    app.dependency_overrides[get_db]=database;app.dependency_overrides[get_current_user]=identity
    with TestClient(app) as client,patch.object(service,'start') as start:
        created=client.post('/api/battle-reports/discovery',json=dict(character_id=9001,seed_killmail_id=1,battle_window=e.scope))
        assert created.status_code==202,created.text
        job=created.json()['job_id'];start.assert_called_once_with(job)
        assert client.get(f'/api/battle-reports/discovery/{job}').status_code==200
        assert client.get('/api/battle-reports/discovery/latest?character_id=9001&seed_killmail_id=1').json()['job_id']==job
        assert client.post('/api/battle-reports/discovery',json=dict(character_id=9001,seed_killmail_id=1,battle_window=e.scope)).status_code==409
        actor[0]=e.other_id
        assert client.get(f'/api/battle-reports/discovery/{job}').status_code==404
        assert client.post(f'/api/battle-reports/discovery/{job}/cancel').status_code==404
        actor[0]=e.uid
        assert client.post(f'/api/battle-reports/discovery/{job}/resume').status_code==200
        assert client.post(f'/api/battle-reports/discovery/{job}/cancel').json()['status']=='cancelled'
        assert client.post(f'/api/battle-reports/discovery/{job}/resume').status_code==409


def test_discovery_http_client_uses_supported_filters_and_rejects_error_objects():
    import httpx
    async def check():
        urls=[]
        def respond(request):
            urls.append(str(request.url))
            return httpx.Response(200,json={'error':'fixture invalid source query'})
        source=service.SystemDiscoveryClient()
        await source.client.aclose()
        source.client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            with pytest.raises(ValueError,match='unsupported response'):
                await source.fetch_page({'owner_id':30000142,'year':2026,'month':8},2)
            assert urls==['https://zkillboard.com/api/solarSystemID/30000142/year/2026/month/8/page/2/']
        finally:await source.close()
    asyncio.run(check())


def test_old_native_engine_cannot_silently_drop_full_window_rows():
    import json
    from app.services.battle_report_engine import evaluate_battle_report_with_engine
    reference={'report':{'timeline':[{'killmail_id':1},{'killmail_id':2}]}}
    output={'schema_version':'eqm.battle-report-output.v1','report':{'timeline':[{'killmail_id':1}]}}
    completed=SimpleNamespace(returncode=0,stderr='',stdout=json.dumps(output))
    with patch('app.services.battle_report_engine.subprocess.run',return_value=completed):
        result=evaluate_battle_report_with_engine(payload={'include_all_killmails':True,'rows':[{'killmail_id':1},{'killmail_id':2}]},
            python_result=reference,engine='rust',binary='fixture')
    assert result['report']==reference['report'] and result['engine_used']=='python-fallback'
