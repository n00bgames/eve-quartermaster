from __future__ import annotations
import asyncio
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import importlib.util,json
import httpx,pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select,func,inspect,update
from sqlalchemy.orm import Session,sessionmaker
from sqlalchemy.pool import StaticPool
from app.api import intel
from app.api.auth import get_current_user
from app.db.session import get_db
from app.domain.intel import parse_entities,summarize_evidence,utc,zkill_badges
from app.models import Base,User,EveCharacter,EveType,EveSystem,EveRegion,EveConstellation,EsiToken,CharacterSkill,RecruitmentApplication,RecruitmentLinkedCharacter,RecruitmentUserCapability,UserSectionPermission,Killmail,KillmailAttacker,KillmailDiscovery
from app.models.intel import IntelSubject,IntelCollection,IntelObservation,IntelSourceCache
from app.services.intel_collection import run_collection,claim,owned_job,cache_put
from app.services.intel_reports import build_report,observe
from app.services.intel_sources import PublicSource,IntelSourceError,trim_stats
from app.services.intel_authorized import private_enrichment

AT=datetime.now(timezone.utc).replace(microsecond=0)-timedelta(hours=2)

class FakeSource:
    def __init__(self):self.pages=[];self.killcalls=[];self.fail_id=None;self.cancel=None
    async def close(self):pass
    async def resolve(self,names):
        return {"characters":[{"id":9001,"name":"Outside Pilot"},{"id":9002,"name":"Shared Name"}],"corporations":[{"id":8001,"name":"Shared Name"},{"id":8002,"name":"Outside Corp"}],"alliances":[{"id":7001,"name":"Outside Alliance"}]}
    async def profile(self,kind,eve_id):return {"name":{"character":"Outside Pilot","corporation":"Outside Corp","alliance":"Outside Alliance"}[kind],"corporation_id":8002,"history":[{"corporation_id":8002,"start_date":"2020-01-01T00:00:00Z"}],"source_errors":[]}
    async def stats(self,kind,eve_id):return trim_stats({"activityTags":{"logi":9,"blops":3},"cyno":{"count":2},"shipsDestroyed":100})
    async def page(self,kind,eve_id,feed,page):
        self.pages.append((kind,eve_id,feed,page))
        if self.cancel:self.cancel()
        ids=[101,102] if feed=="kills" and page==1 else [103] if feed=="losses" and page==1 else []
        return [{"killmail_id":kid,"zkb":{"hash":f"hash-{kid}","totalValue":100,"solo":False,"npc":False},"killmail_time":(AT+timedelta(minutes=kid-100)).isoformat()} for kid in ids]
    async def killmail(self,kid,kill_hash):
        self.killcalls.append(kid)
        if kid==self.fail_id:raise HTTPException(503,'fixture upstream error')
        mine={"character_id":9001,"corporation_id":8002,"alliance_id":7001,"ship_type_id":100,"weapon_type_id":200,"damage_done":50}
        friend={"character_id":9003,"corporation_id":8003,"alliance_id":7002,"ship_type_id":100,"weapon_type_id":201,"damage_done":50}
        victim={"character_id":9010,"corporation_id":8010,"alliance_id":7010,"ship_type_id":100,"damage_taken":100,"items":[]}
        if kid==103:victim={**victim,**{k:v for k,v in mine.items() if k.endswith('_id')}};attackers=[friend]
        else:attackers=[mine,friend]
        return {"killmail_id":kid,"killmail_time":(AT+timedelta(minutes=kid-100)).isoformat(),"solar_system_id":30000001,"victim":victim,"attackers":attackers}
    async def names(self,ids):return [{"id":eid,"name":{9003:"Wingmate",8002:"Outside Corp",8003:"Partner Corp",7002:"Partner Alliance"}.get(eid,f"Entity {eid}"),"category":"character" if eid>=9000 else "corporation" if eid>=8000 else "alliance"} for eid in ids]
    async def type_info(self,eid):return {"id":eid,"name":f"Type {eid}","group_id":72 if eid==200 else 53}
    async def system_info(self,eid):return {"id":eid,"name":"Tama","region_id":10000001,"region_name":"The Forge"}

@pytest.fixture
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(bind=engine,expire_on_commit=False);db=factory()
    users=[User(email=f'intel{i}@test.invalid',display_name=f'Intel User {i}',role=role) for i,role in enumerate(['host','officer','officer','member','applicant','member'])]
    db.add_all(users);db.flush()
    db.add_all([EveType(type_id=100,name='Test Cruiser',group_id=26),EveType(type_id=200,name='Large Smartbomb',group_id=72),EveType(type_id=201,name='Launcher',group_id=53)])
    db.add_all([EveRegion(region_id=10000001,name='Test Region'),EveConstellation(constellation_id=20000001,region_id=10000001,name='Test Constellation'),EveSystem(system_id=30000001,constellation_id=20000001,name='Test System')]);db.commit()
    app=FastAPI();app.include_router(intel.router);current=[users[0]];source=FakeSource()
    def identity():
        if current[0] is None:raise HTTPException(401,'Sign in required')
        return current[0]
    def database():
        try:yield db
        finally:db.rollback()
    app.dependency_overrides[get_current_user]=identity;app.dependency_overrides[get_db]=database
    with patch.object(intel,'source_factory',return_value=source),TestClient(app) as client:
        yield SimpleNamespace(client=client,db=db,factory=factory,users=users,current=current,source=source,app=app)
    db.close();engine.dispose()


def subject(env,kind='character',eve_id=9001):
    r=env.client.post('/intel/subjects',json={'kind':kind,'eve_id':eve_id});assert r.status_code==201,r.text;return r.json()

def collect(env,subject_id,max_pages=3):
    r=env.client.post(f'/intel/subjects/{subject_id}/collect',json={'days':90,'max_pages':max_pages});assert r.status_code==202,r.text;return r.json()

def finish(env,job):
    asyncio.run(run_collection(job['id'],source=env.source,factory=env.factory));env.db.expire_all()
    return env.client.get(f"/intel/collections/{job['id']}").json()


def test_entity_parser_exact_types_dedup_and_url_restriction():
    rows=parse_entities('Outside Pilot\nOutside Pilot\nhttps://zkillboard.com/corporation/8002/\nalliance:7001')
    assert len(rows)==3 and rows[1]['kind']=='corporation' and rows[2]['eve_id']==7001
    for bad in ['https://internal.invalid/secret','x'*256,'\n']:
        with pytest.raises(ValueError):parse_entities(bad)
    with pytest.raises(ValueError):parse_entities('\n'.join(f'Pilot {i}' for i in range(101)))


def test_utc_offset_normalization():
    assert utc('2026-01-01T03:00:00+03:00').isoformat()=='2026-01-01T00:00:00+00:00'


def test_zkill_badges_keep_upstream_windows_and_do_not_use_kill_labels():
    result=zkill_badges({'activityTags':{'logi':9,'titan':2},'cyno':{'count':3},'labels':{'ganked':100}})
    assert {row['label'] for row in result}=={'LOGI','TITAN','CYNO'}
    assert next(row for row in result if row['label']=='CYNO')['window_days']==365
    assert next(row for row in result if row['label']=='LOGI')['window_days']==90
    assert 'totals' in trim_stats({'shipsDestroyed':15,'wallet':'DO NOT COPY'})
    assert 'wallet' not in json.dumps(trim_stats({'wallet':'DO NOT COPY'}))


def test_subject_weapon_only_and_evidence_based_associations():
    mine={'character_id':1,'corporation_id':10,'alliance_id':100,'ship_type_id':50,'weapon_known':False,'smartbomb':False}
    friend={'character_id':2,'corporation_id':20,'alliance_id':200,'ship_type_id':51,'weapon_known':True,'smartbomb':True}
    facts=[{'id':i,'time':AT+timedelta(minutes=i),'system_id':300,'victim':{'character_id':3,'corporation_id':30},'attackers':[mine,friend]} for i in range(1,4)]
    facts.append(facts[0])
    summary=summarize_evidence('character',1,facts,AT,AT+timedelta(days=1))
    assert summary['kills']==3 and summary['smartbomb']['confirmed_kills']==0
    assert summary['smartbomb']['weapon_known_kills']==0
    assert all(row['id']!=3 for row in summary['associates'] if row['kind']=='character')
    other=next(row for row in summary['associates'] if row['kind']=='character' and row['id']==2)
    assert other['kills']==3 and other['estimated_engagements']==1 and other['distinct_days']==1
    for f in facts:f['attackers']=[{**mine,'weapon_known':True,'smartbomb':True},friend]
    summary=summarize_evidence('character',1,facts,AT,AT+timedelta(days=1))
    assert summary['smartbomb']['confirmed_percent']==100
    assert not summary['smartbomb']['frequent'] # minimum sample of five


def test_org_association_deduplicates_many_members_and_uses_historical_ids():
    mine={'character_id':1,'corporation_id':10,'ship_type_id':50}
    friends=[{'character_id':i,'corporation_id':20,'alliance_id':200,'ship_type_id':51} for i in range(2,8)]
    f={'id':1,'time':AT,'system_id':300,'victim':{'character_id':90},'attackers':[mine,*friends]}
    result=summarize_evidence('corporation',10,[f],AT,AT+timedelta(days=1))
    assert next(row for row in result['associates'] if row['kind']=='corporation' and row['id']==20)['kills']==1
    assert result['kills']==1


def test_time_boundaries_and_npc_exclusion():
    facts=[{'id':i,'time':at,'system_id':300,'victim':{'character_id':9},'attackers':[{'character_id':1,'ship_type_id':50}],'npc_only':i==3} for i,at in [(1,AT),(2,AT+timedelta(days=1)),(3,AT+timedelta(hours=1))]]
    r=summarize_evidence('character',1,facts,AT,AT+timedelta(days=1))
    assert r['kills']==1 and len(r['evidence'])==2


def test_resolve_mixed_names_and_ambiguity_without_enrolling(env):
    r=env.client.post('/intel/resolve',json={'text':'Outside Pilot\nShared Name\nOutside Alliance\nUnknown'})
    assert r.status_code==200
    assert [row['state'] for row in r.json()['rows']]==['resolved','ambiguous','resolved','unresolved']
    assert env.db.scalar(select(func.count()).select_from(EveCharacter))==0
    assert env.db.scalar(select(func.count()).select_from(IntelSubject))==0


@pytest.mark.parametrize('kind,eid',[('character',9001),('corporation',8002),('alliance',7001)])
def test_external_subject_collection_and_report(env,kind,eid):
    s=subject(env,kind,eid);job=collect(env,s['id']);done=finish(env,job)
    assert done['status']=='completed',done
    r=env.client.get(f"/intel/subjects/{s['id']}/report")
    assert r.status_code==200 and r.headers['cache-control']=='private, no-store'
    data=r.json()
    assert data['summary']['kills']==2 and data['summary']['losses']==1
    assert data['summary']['systems'][0]['name']=='Test System'
    assert data['summary']['regions'][0]['name']=='Test Region'
    assert data['summary']['smartbomb']['confirmed_kills']==2
    assert data['summary']['smartbomb']['confirmed_percent']==100
    assert env.db.scalar(select(func.count()).select_from(EveCharacter))==0
    assert env.db.scalar(select(func.count()).select_from(Killmail))==3
    assert done['coverage']['kills']['status']=='feed_exhausted'
    assert 'badges' in data['subject']['public_data']['zkill']['data']


def test_page_cap_is_partial_not_complete(env):
    s=subject(env);done=finish(env,collect(env,s['id'],max_pages=1))
    assert done['status']=='partial'
    assert done['coverage']['kills']['status']=='page_cap'
    assert env.client.post(f"/intel/collections/{done['id']}/retry").status_code==409


def test_leases_are_exclusive_and_expired_worker_loses_ownership(env):
    s=subject(env);job=collect(env,s['id'])
    with env.factory() as db:assert claim(db,job['id'],'worker-a')
    with env.factory() as db:assert not claim(db,job['id'],'worker-b')
    with env.factory() as db:db.execute(update(IntelCollection).where(IntelCollection.id==job['id']).values(lease_until=AT));db.commit()
    with env.factory() as db:assert claim(db,job['id'],'worker-b')
    with env.factory() as db:assert owned_job(db,job['id'],'worker-a') is None


def test_failed_page_retries_reuse_partial_ingestion_and_compact_cache(env):
    s=subject(env);job=collect(env,s['id']);env.source.fail_id=102
    done=finish(env,job)
    assert done['status']=='queued' and done['page']==1
    assert env.db.scalar(select(func.count()).select_from(Killmail))==1
    env.source.fail_id=None
    with env.factory() as db:db.execute(update(IntelCollection).where(IntelCollection.id==job['id']).values(available_at=AT));db.commit()
    done=finish(env,job)
    assert done['status']=='completed'
    assert env.db.scalar(select(func.count()).select_from(Killmail))==3
    assert env.source.pages.count(('character',9001,'kills',1))==1
    cache=env.db.get(IntelSourceCache,'page:character:9001:kills:1')
    assert set(cache.payload)=={'entries'}
    assert all(set(row)=={'killmail_id','killmail_hash','killmail_time','zkb'} for row in cache.payload['entries'])


def test_overlapping_collections_reuse_one_shared_killmail_store(env):
    first=subject(env);finish(env,collect(env,first['id']))
    second=subject(env,'corporation',8002);done=finish(env,collect(env,second['id']))
    assert done['reused_count']==3 and done['imported_count']==0
    assert env.db.scalar(select(func.count()).select_from(Killmail))==3
    assert len(env.source.killcalls)==3


def test_cancelled_inflight_job_does_not_write_new_killmails(env):
    s=subject(env);job=collect(env,s['id'])
    def cancel():
        with env.factory() as db:db.execute(update(IntelCollection).where(IntelCollection.id==job['id']).values(status='cancelled'));db.commit()
    env.source.cancel=cancel
    done=finish(env,job)
    assert done['status']=='cancelled'
    assert env.db.scalar(select(func.count()).select_from(Killmail))==0
    resumed=env.client.post(f"/intel/collections/{job['id']}/retry")
    assert resumed.status_code==202 and resumed.json()['stage']=='kills'


def test_queued_duplicate_returns_existing_job(env):
    s=subject(env);a=collect(env,s['id']);b=collect(env,s['id'])
    assert a['id']==b['id']


def test_change_observations_do_not_grow_on_identical_refresh(env):
    s=subject(env);row=env.db.get(IntelSubject,s['id']);count=env.db.scalar(select(func.count()).select_from(IntelObservation))
    payload={key:value for key,value in env.source_profile.items()} if hasattr(env,'source_profile') else row.public_data['esi']['data'].copy()
    payload.pop('source_errors',None)
    observe(env.db,row,'esi',payload);env.db.commit()
    assert env.db.scalar(select(func.count()).select_from(IntelObservation))==count
    observe(env.db,row,'esi',{**payload,'corporation_id':123});env.db.commit()
    assert env.db.scalar(select(func.count()).select_from(IntelObservation))==count+1


@pytest.mark.parametrize('index',[3,4])
def test_member_and_applicant_cannot_access_intel(env,index):
    s=subject(env);env.current[0]=env.users[index]
    for path in ['/intel/subjects',f"/intel/subjects/{s['id']}/report",f"/intel/subjects/{s['id']}/authorized",f"/intel/subjects/{s['id']}/notes"]:
        assert env.client.get(path).status_code==403
    assert env.client.post('/intel/resolve',json={'text':'Outside Pilot'}).status_code==403


def test_anonymous_and_disabled_section_denied(env):
    env.current[0]=None;assert env.client.get('/intel/subjects').status_code==401
    env.current[0]=env.users[1]
    env.db.add(UserSectionPermission(user_id=env.users[1].id,section='intel_reports',can_view=False));env.db.commit()
    assert env.client.get('/intel/subjects').status_code==403


def add_private_character(env,owner_index=1):
    character=EveCharacter(character_id=9001,name='Outside Pilot',owner_user_id=env.users[owner_index].id,total_skill_points=123456789,skills_synced_at=AT)
    env.db.add(character);env.db.flush()
    token=EsiToken(user_id=character.owner_user_id,character_id=character.id,scopes='esi-skills.read_skills.v1 esi-skills.read_skillqueue.v1 esi-fittings.read_fittings.v1',encrypted_refresh_token='fixture-secret-not-for-reports')
    env.db.add(token);env.db.add(CharacterSkill(character_id=character.id,skill_type_id=100,trained_skill_level=5,active_skill_level=5,skillpoints_in_skill=1000));env.db.commit()
    return character,token


def test_authorized_private_is_viewer_scoped_and_never_in_public_report(env):
    s=subject(env);character,token=add_private_character(env)
    env.current[0]=env.users[1]
    private=env.client.get(f"/intel/subjects/{s['id']}/authorized").json()
    assert private['state']=='authorized' and private['datasets']['skills']['total_sp']==123456789
    public=env.client.get(f"/intel/subjects/{s['id']}/report")
    assert '123456789' not in public.text and 'fixture-secret' not in public.text
    env.current[0]=env.users[2]
    assert env.client.get(f"/intel/subjects/{s['id']}/authorized").json()['state']=='not_authorized'
    assert env.client.post(f"/intel/subjects/{s['id']}/authorized/refresh",json={'dataset':'skills'}).status_code==403


def test_revoked_token_and_sync_opt_out_block_even_host(env):
    s=subject(env);character,token=add_private_character(env)
    token.revoked_at=AT;env.db.commit()
    assert env.client.get(f"/intel/subjects/{s['id']}/authorized").json()['state']=='not_authorized'
    token.revoked_at=None;character.sync_opt_out=True;env.db.commit()
    assert env.client.get(f"/intel/subjects/{s['id']}/authorized").json()['state']=='not_authorized'


def test_missing_scope_does_not_expose_cached_sp(env):
    s=subject(env);character,token=add_private_character(env);token.scopes='publicData';env.db.commit()
    private=env.client.get(f"/intel/subjects/{s['id']}/authorized")
    assert private.json()['datasets']['skills']['state']=='not_authorized'
    assert '123456789' not in private.text


def test_recruiter_can_enrich_verified_consented_applicant_only(env):
    s=subject(env);character,token=add_private_character(env,owner_index=4)
    application=RecruitmentApplication(applicant_user_id=env.users[4].id,status='Submitted');env.db.add(application);env.db.flush()
    link=RecruitmentLinkedCharacter(application_id=application.id,character_id=character.id,verification_status='verified',token_health='healthy',granted_scopes_json=['esi-skills.read_skills.v1'],last_successful_sync_at=AT)
    env.db.add_all([link,RecruitmentUserCapability(user_id=env.users[5].id,capability='recruiter'),UserSectionPermission(user_id=env.users[5].id,section='intel_reports',can_view=True)]);env.db.commit();env.current[0]=env.users[5]
    r=env.client.get(f"/intel/subjects/{s['id']}/authorized")
    assert r.status_code==200 and r.json()['state']=='authorized'
    assert r.json()['datasets']['skills']['total_sp']==123456789
    assert 'fittings' not in r.json()['datasets'] and 'queue' not in r.json()['datasets']
    application.status='Withdrawn';env.db.commit()
    assert env.client.get(f"/intel/subjects/{s['id']}/authorized").json()['state']=='not_authorized'


def test_invalid_inputs_and_notes_are_scoped(env):
    s=subject(env)
    assert env.client.post('/intel/subjects',json={'kind':'character','eve_id':9001,'owner_user_id':5}).status_code==422
    assert env.client.post(f"/intel/subjects/{s['id']}/collect",json={'days':0}).status_code==422
    assert env.client.get(f"/intel/subjects/{s['id']}/report?from_at=2026-10-01T00:00:00Z&to_at=2026-09-01T00:00:00Z").status_code==422
    assert env.client.post('/intel/subjects/9999/notes',json={'body':'note'}).status_code==404
    assert env.client.post(f"/intel/subjects/{s['id']}/notes",json={'body':'  '}).status_code==422
    r=env.client.post(f"/intel/subjects/{s['id']}/notes",json={'body':'Hypothesis only; inspect supporting killmails.'})
    assert r.status_code==201
    assert env.client.get(f"/intel/subjects/{s['id']}/notes").json()[0]['body'].startswith('Hypothesis')
    assert 'Hypothesis' not in env.client.get(f"/intel/subjects/{s['id']}/report").text


def test_http_200_error_payload_is_not_an_empty_successful_feed():
    source=PublicSource()
    async def run():
        await source.http.aclose()
        source.http=httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'error':'invalid query'})))
        try:
            with pytest.raises(IntelSourceError):await source.page('character',9001,'kills',1)
        finally:await source.close()
    asyncio.run(run())


def test_migration_roundtrip_and_single_head():
    path=Path(__file__).parents[1]/'alembic/versions/0089_intel_reports.py'
    spec=importlib.util.spec_from_file_location('intel_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();assert 'intel_subjects' in inspect(connection).get_table_names()
            indexes=inspect(connection).get_indexes('intel_collections');assert any(row['name']=='uq_intel_active_collection' and row['unique'] for row in indexes)
            module.downgrade();assert inspect(connection).get_table_names()==['users'];module.upgrade()
    config=Config();config.set_main_option('script_location',str(path.parents[1]));assert len(ScriptDirectory.from_config(config).get_heads())==1
    assert ScriptDirectory.from_config(config).get_revision('0089_intel_reports') is not None


def test_documented_new_badge_fields_and_rookie_rule():
    raw={'awoxCount':10,'allianceAwoxCount':15,'factionAwoxCount':20,'gankerCount':10,'fc':{'level':'HIGH','monitorAppearances':5},'bait':{'level':'MEDIUM','count':8}}
    badges=zkill_badges(raw)
    assert {row['label'] for row in badges}=={'AWOX','ALLIANCE AWOX','FACTION AWOX','GANKER','FC','BAIT'}
    assert 'count' not in next(row for row in badges if row['label']=='FC')
    young={'info':{'birthday':(AT-timedelta(days=30)).isoformat()},'recentLabels':{'pvp':{'shipsDestroyed':1,'shipsLost':3}}}
    assert zkill_badges(young)[0]['source']=='zkill-rule'
    assert not any(row['label']=='ROOKIE' for row in zkill_badges({**young,'cyno':{'count':1}}))


def test_mismatched_killmail_identity_is_not_ingested(env):
    s=subject(env);job=collect(env,s['id'])
    original=env.source.killmail
    async def wrong(kid,kill_hash):
        payload=await original(kid,kill_hash);payload['killmail_id']=kid+1;return payload
    env.source.killmail=wrong
    result=finish(env,job)
    assert result['status']=='queued'
    assert env.db.scalar(select(func.count()).select_from(Killmail))==0

def test_evidence_samples_keep_recent_records_and_engagement_counts():
    facts=[{'id':i,'time':AT+timedelta(minutes=i),'system_id':300,'victim':{'character_id':9},'attackers':[{'character_id':1,'ship_type_id':50},{'character_id':2,'ship_type_id':51}]} for i in range(25)]
    r=summarize_evidence('character',1,facts,AT,AT+timedelta(days=1))
    assert r['systems'][0]['evidence']==list(range(15,25))
    assert r['associates'][0]['evidence']==list(range(15,25))
    assert r['associates'][0]['estimated_engagements']==1


def test_three_failed_attempts_require_manual_resume(env):
    s=subject(env);job=collect(env,s['id']);env.source.fail_id=101
    for attempt in range(3):
        with env.factory() as db:db.execute(update(IntelCollection).where(IntelCollection.id==job['id']).values(available_at=AT));db.commit()
        result=finish(env,job)
    assert result['status']=='failed' and result['failed_count']==3
    assert env.client.post(f"/intel/collections/{job['id']}/retry").status_code==202


def test_private_owner_change_stops_enrichment(env):
    s=subject(env);character,token=add_private_character(env)
    character.owner_user_id=env.users[2].id;env.db.commit()
    assert env.client.get(f"/intel/subjects/{s['id']}/authorized").json()['state']=='not_authorized'
