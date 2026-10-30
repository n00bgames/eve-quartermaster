from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import importlib.util
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from alembic.config import Config
from sqlalchemy import select,func,inspect,create_engine
from app.models import EveCategory,EveGroup,EveType,AuditEvent,EveCharacter,Killmail,KillmailAttacker,UserSectionPermission
from app.models.intel import IntelSighting,IntelObservation
from .test_intel_reports import env,subject,collect,finish,AT

@pytest.fixture
def seen(env):
    env.db.add_all([EveCategory(category_id=6,name='Ship'),EveCategory(category_id=7,name='Module')]);env.db.flush()
    env.db.add_all([EveGroup(group_id=26,name='Cruiser',category_id=6),EveGroup(group_id=53,name='Launcher',category_id=7)]);env.db.flush()
    env.db.add_all([EveType(type_id=300,name='Other Cruiser',group_id=26),EveType(type_id=301,name='Unpublished Hull',group_id=26,published=False)]);env.db.commit()
    env.users[3].role='intel_analyst';env.db.commit();env.current[0]=env.users[3]
    return env

def fields(**values):return {'system_id':30000001,'ship_type_id':100,'request_id':str(uuid4()),**values}
def report(env,sid,query=''):return env.client.get(f'/intel/subjects/{sid}/report{query}').json()

def test_new_subject_sighting_creates_zero_zero_rows_and_no_combat(seen):
    before=datetime.now(timezone.utc)
    r=seen.client.post('/intel/subjects',json={'kind':'character','eve_id':9001,'sighting':fields()})
    assert r.status_code==201,r.text
    data=report(seen,r.json()['id']);s=data['summary']
    assert (s['kills'],s['losses'],s['sightings'])==(0,0,1)
    assert s['ships'][0]['id']==100 and s['ships'][0]['name']=='Test Cruiser' and s['ships'][0]['kills']==s['ships'][0]['losses']==0
    assert s['systems'][0]['name']=='Test System' and s['systems'][0]['sightings']==1
    assert s['regions'][0]['sightings']==1
    assert s['timeline'][0]['kills']==s['timeline'][0]['losses']==0 and s['timeline'][0]['sightings']==1
    assert not s['associates'] and not s['evidence'] and sum(row['appearances'] for row in s['utc_hours'])==0
    sight=data['sightings']['rows'][0]
    assert sight['system_name']=='Test System' and sight['ship_type_name']=='Test Cruiser' and sight['source']=='analyst_sighting'
    assert datetime.fromisoformat(sight['observed_at'])>=before and sight['observer']==seen.current[0].display_name
    assert seen.db.scalar(select(func.count()).select_from(Killmail))==0
    assert seen.db.scalar(select(func.count()).select_from(KillmailAttacker))==0
    assert seen.db.scalar(select(func.count()).select_from(EveCharacter))==0
    assert seen.db.scalar(select(func.count()).select_from(IntelObservation).where(IntelObservation.source=='manual_sighting'))==0

def test_existing_subject_retry_is_idempotent_but_new_run_records_again(seen):
    sid=subject(seen)['id'];body=fields()
    for i in range(2):assert seen.client.post(f'/intel/subjects/{sid}/sightings',json=body).status_code==201
    assert seen.client.post('/intel/subjects',json={'kind':'character','eve_id':9001,'sighting':body}).status_code==201
    assert report(seen,sid)['sightings']['total']==1
    assert seen.client.post(f'/intel/subjects/{sid}/sightings',json={**body,'ship_type_id':300}).status_code==409
    assert seen.client.post(f'/intel/subjects/{sid}/sightings',json=fields(ship_type_id=300)).status_code==201
    data=report(seen,sid);assert data['sightings']['total']==2 and {row['id'] for row in data['summary']['ships']}=={100,300}
    for i in range(3):report(seen,sid)
    assert seen.db.scalar(select(func.count()).select_from(IntelSighting))==2
    events=list(seen.db.scalars(select(AuditEvent).where(AuditEvent.title=='Intel ship sighting recorded')))
    assert len(events)==2

def test_manual_sightings_never_change_retained_combat_totals(seen):
    sid=subject(seen)['id'];job=collect(seen,sid);finish(seen,job)
    original=report(seen,sid)['summary']
    for i in range(2):assert seen.client.post(f'/intel/subjects/{sid}/sightings',json=fields()).status_code==201
    data=report(seen,sid)['summary']
    for key in ['kills','losses','solo_kills','smartbomb','average_recorded_attacker_count','utc_hours','evidence','associates']:
        assert data[key]==original[key],key
    assert [(r['id'],r['kills'],r['losses']) for r in data['ships']]==[(r['id'],r['kills'],r['losses']) for r in original['ships']]
    assert data['sightings']==2 and data['ships'][0]['sightings']==2

def test_date_boundaries_filter_sightings_without_affecting_profile_history(seen):
    sid=subject(seen)['id'];start=datetime(2026,10,1,tzinfo=timezone.utc);end=start+timedelta(days=1)
    for at in [start-timedelta(seconds=1),start,end]:
        seen.db.add(IntelSighting(subject_id=sid,observer_user_id=seen.current[0].id,request_id=str(uuid4()),system_id=30000001,system_name='Test System',region_id=10000001,region_name='Test Region',ship_type_id=100,ship_type_name='Test Cruiser',observed_at=at))
    seen.db.commit()
    data=report(seen,sid,'?from_at=2026-10-01T00:00:00Z&to_at=2026-10-02T00:00:00Z')
    assert data['sightings']['total']==1 and len(data['sightings']['rows'])==1
    assert data['summary']['timeline']==[{'date':'2026-10-01','kills':0,'losses':0,'sightings':1}]
    assert data['observations'] # Existing public profile history remains separate.

def test_invalid_system_ship_kind_timestamp_and_partial_payload_rejected(seen):
    sid=subject(seen)['id'];org=subject(seen,'corporation',8002)['id']
    bad=[fields(system_id=999),fields(ship_type_id=201),fields(ship_type_id=301),fields(ship_type_id=999),fields(system_id='30000001'),fields(observed_at='2001-01-01T00:00:00Z'),{'system_id':30000001,'request_id':str(uuid4())}]
    for body in bad:
        r=seen.client.post(f'/intel/subjects/{sid}/sightings',json=body);assert r.status_code==422,r.text
    assert seen.client.post(f'/intel/subjects/{org}/sightings',json=fields()).status_code==422
    assert seen.client.post('/intel/subjects',json={'kind':'corporation','eve_id':8001,'sighting':fields()}).status_code==422
    assert seen.client.post(f'/intel/subjects/999/sightings',json=fields()).status_code==404
    assert seen.db.scalar(select(func.count()).select_from(IntelSighting))==0

def test_picker_is_intel_scoped_and_only_matches_systems_or_hulls(seen):
    ships=seen.client.get('/intel/sighting-lookups?kind=ship&q=Test').json()
    assert ships==[{'id':100,'name':'Test Cruiser','detail':'Cruiser'}]
    assert seen.client.get('/intel/sighting-lookups?kind=ship&q=Launcher').json()==[]
    assert seen.client.get('/intel/sighting-lookups?kind=ship&q=Unpublished').json()==[]
    assert seen.client.get('/intel/sighting-lookups?kind=system&q=Test').json()[0]['id']==30000001
    assert seen.client.get('/intel/sighting-lookups?kind=system&q=%25').json()==[]
    assert seen.client.get('/intel/sighting-lookups?kind=other&q=Test').status_code==422
    seen.db.add(UserSectionPermission(user_id=seen.current[0].id,section='intel_reports',can_view=False));seen.db.commit()
    assert seen.client.get('/intel/sighting-lookups?kind=system&q=Test').status_code==403

def test_sightings_require_current_intel_access(seen):
    sid=subject(seen)['id'];seen.current[0]=seen.users[4]
    assert seen.client.post(f'/intel/subjects/{sid}/sightings',json=fields()).status_code==403
    seen.current[0]=None
    assert seen.client.post(f'/intel/subjects/{sid}/sightings',json=fields()).status_code==401

def test_sighting_event_list_is_bounded_but_totals_cover_the_full_window(seen):
    sid=subject(seen)['id'];at=datetime.now(timezone.utc)
    for i in range(205):seen.db.add(IntelSighting(subject_id=sid,observer_user_id=seen.current[0].id,request_id=str(uuid4()),system_id=30000001,system_name='Test System',ship_type_id=100,ship_type_name='Test Cruiser',observed_at=at-timedelta(seconds=i)))
    seen.db.commit();data=report(seen,sid)
    assert data['sightings']['total']==205 and len(data['sightings']['rows'])==200
    assert data['summary']['ships'][0]['sightings']==205

def test_sighting_migration_roundtrip_and_head():
    path=Path(__file__).parents[1]/'alembic/versions/0099_intel_sightings.py'
    spec=importlib.util.spec_from_file_location('sighting_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        for table,key in [('users','id'),('intel_subjects','id'),('eve_systems','system_id'),('eve_types','type_id')]:conn.exec_driver_sql(f'CREATE TABLE {table} ({key} INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade();assert 'intel_sightings' in inspect(conn).get_table_names()
            assert any(x['column_names']==['subject_id','observer_user_id','request_id'] for x in inspect(conn).get_unique_constraints('intel_sightings'))
            module.downgrade();assert 'intel_sightings' not in inspect(conn).get_table_names();module.upgrade()
    config=Config();config.set_main_option('script_location',str(path.parents[1]));assert ScriptDirectory.from_config(config).get_heads()==['0099_intel_sightings']


def test_backdated_sighting_preserves_posting_time_and_utc_offset(seen):
    sid=subject(seen)['id'];before=datetime.now(timezone.utc)
    body=fields(observed_at='2020-10-20T13:30:00+03:00')
    response=seen.client.post(f'/intel/subjects/{sid}/sightings',json=body)
    assert response.status_code==201,response.text
    row=response.json();assert row['observed_at']=='2020-10-20T10:30:00+00:00' and row['manual_time'] is True
    assert datetime.fromisoformat(row['recorded_at'])>=before
    assert report(seen,sid)['sightings']['total']==0 # Outside the default 90-day window.
    data=report(seen,sid,'?from_at=2020-10-20T00:00:00Z&to_at=2020-10-21T00:00:00Z')
    assert data['sightings']['total']==1 and data['sightings']['rows'][0]['manual_time']
    assert data['summary']['timeline']==[{'date':'2020-10-20','kills':0,'losses':0,'sightings':1}]
    assert seen.client.post(f'/intel/subjects/{sid}/sightings',json=body).status_code==201
    assert seen.client.post(f'/intel/subjects/{sid}/sightings',json={**body,'observed_at':'2020-10-20T10:31:00Z'}).status_code==409


def test_future_naive_or_pre_launch_manual_time_is_rejected(seen):
    sid=subject(seen)['id']
    for at in [(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'2020-01-01T12:00:00','2000-01-01T12:00:00Z']:
        response=seen.client.post(f'/intel/subjects/{sid}/sightings',json=fields(observed_at=at))
        assert response.status_code==422,response.text
    assert seen.db.scalar(select(func.count()).select_from(IntelSighting))==0
