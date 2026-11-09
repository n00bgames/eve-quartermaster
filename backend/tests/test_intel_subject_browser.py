import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import select, func, create_engine, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.api import intel
from app.models import EveCharacter, Killmail
from app.models.intel import IntelSubject, IntelNote, IntelCollection, IntelObservation, IntelSighting
from app.models.intel_membership import IntelMembershipMonitor, IntelMembershipSnapshot
from app.services.intel_subjects import seed_scan
from app.services.intel_collection import owned_job, profile_stage
from app.services.intel_membership import persist
from app.models.local_scan import LocalScanReport
from .test_intel_reports import env, subject
from .test_local_scan import env as scan_env, create

AT=datetime.now(timezone.utc)

def pilot(eid=9001,name="Demo Pilot",cid=101,aid=201):
    return dict(character_id=eid,name=name,corporation_id=cid,corporation_name=f"Corp {cid}",
        alliance_id=aid,alliance_name=f"Alliance {aid}" if aid else None,affiliation_available=cid is not None)

def seed(env,pilots):
    seed_scan(env.db,env.users[0],{"pilots":pilots,"system":{"id":123,"name":"Private System"}},AT)
    env.db.commit()

def test_actual_local_scan_seeds_identity_without_enrollment_or_collection(scan_env):
    n=scan_env.db.scalar(select(func.count()).select_from(EveCharacter))
    report=create(scan_env,is_private=True,system_id=30000142)
    subjects=scan_env.db.scalars(select(IntelSubject)).all()
    assert len(subjects)==3
    for row in subjects:
        assert row.public_data["esi"]["state"]=="partial"
        assert not any(key in str(row.public_data) for key in ("token","system","created_by","sighting","zkill"))
    assert scan_env.db.scalar(select(func.count()).select_from(EveCharacter))==n
    assert scan_env.db.scalar(select(func.count()).select_from(IntelCollection))==0
    create(scan_env)
    assert scan_env.db.scalar(select(func.count()).select_from(IntelSubject))==3

def test_stub_write_failure_rolls_back_the_scan(scan_env):
    def fail(db,user,snapshot,at):
        seed_scan(db,user,snapshot,at)
        raise RuntimeError('Synthetic seed failure')
    with patch('app.services.intel_subjects.seed_scan',side_effect=fail),pytest.raises(RuntimeError,match='Synthetic seed failure'):
        create(scan_env)
    assert scan_env.db.scalar(select(func.count()).select_from(IntelSubject))==0
    assert scan_env.db.scalar(select(func.count()).select_from(LocalScanReport))==0

def test_tree_complete_paged_search_unknown_and_same_name_ids(env):
    seed(env,[pilot(10000+i,f"Pilot {i:03}") for i in range(235)]+[pilot(9002,"Neutral",102,None),pilot(9003,"Unknown",None,None)])
    tree=env.client.get('/intel/subject-tree').json()
    group=next(a for a in tree if a['eve_id']==201)
    assert group['pilot_count']==235 and group['corporations'][0]['pilot_count']==235
    assert 'pilots' not in group['corporations'][0]
    rows=[]
    for offset in range(0,235,50):
        r=env.client.get(f'/intel/subject-tree/pilots?alliance=201&corporation=101&offset={offset}').json()
        rows+=r['rows'];assert r['total']==235
    assert len({r['id'] for r in rows})==235 and rows[0]['name']=='Pilot 000'
    assert {a['key'] for a in tree}=={'201','none','unknown'}
    assert env.client.get('/intel/subject-tree?q=Pilot%20234').json()[0]['pilot_count']==1
    assert env.client.get('/intel/subject-tree?q=Corp%20101').json()[0]['pilot_count']==235
    seed(env,[{**pilot(9004,'Other ID',103,202),'alliance_name':'Alliance 201','corporation_name':'Corp 101'}])
    assert len([a for a in env.client.get('/intel/subject-tree').json() if a['name']=='Alliance 201'])==2
    assert env.client.get('/intel/subject-tree/pilots?alliance=201&corporation=101&offset=-1').status_code==422

def test_priority_order_clear_and_cached_entity_summary(env):
    seed(env,[pilot(9001,'Alpha',101,201),pilot(9002,'Zulu',102,202),pilot(9003,'Beta',101,201)])
    # Group names open ordinary summaries without an upstream lookup or job.
    with patch.object(intel,'source_factory',side_effect=AssertionError('No network')):
        aid=subject(env,'alliance',202)['id'];cid=subject(env,'corporation',102)['id']
    assert env.client.get(f'/intel/subjects/{cid}/report').json()['subject']['kind']=='corporation'
    assert env.db.scalar(select(func.count()).select_from(IntelCollection))==0
    for sid in (aid,cid):assert env.client.patch(f'/intel/subjects/{sid}/priority',json={'priority':True}).status_code==200
    tree=env.client.get('/intel/subject-tree').json()
    assert tree[0]['eve_id']==202 and tree[0]['priority'] and tree[0]['corporations'][0]['priority']
    pid=env.db.scalar(select(IntelSubject.id).where(IntelSubject.eve_id==9003))
    assert env.client.patch(f'/intel/subjects/{pid}/priority',json={'priority':True}).status_code==200
    assert env.client.get('/intel/subject-tree/pilots?alliance=201&corporation=101').json()['rows'][0]['name']=='Beta'
    env.client.patch(f'/intel/subjects/{pid}/priority',json={'priority':False})
    assert env.client.get('/intel/subject-tree/pilots?alliance=201&corporation=101').json()['rows'][0]['name']=='Alpha'
    env.client.patch(f'/intel/subjects/{aid}/priority',json={'priority':False})
    assert env.client.get('/intel/subject-tree').json()[0]['eve_id']==201
    assert env.client.patch(f'/intel/subjects/{pid}/priority',json={'priority':'true'}).status_code==422

@pytest.mark.parametrize('kind',['character','corporation','alliance'])
def test_delete_preserves_notes_other_entities_and_shared_records(env,kind):
    sid=subject(env,kind,9001 if kind=='character' else 8002 if kind=='corporation' else 7001)['id']
    other=subject(env,'character',9004)['id']
    env.db.add(Killmail(killmail_id=123,killmail_hash='synthetic',killmail_time=AT,
        solar_system_id=30000001,victim_character_id=9001,victim_corporation_id=8002,
        victim_alliance_id=7001,canonical_esi_payload={}))
    env.db.add_all([IntelNote(subject_id=sid,author_user_id=env.users[i].id,body=f'Note {i}',is_private=bool(i)) for i in (0,1)])
    job=env.client.post(f'/intel/subjects/{sid}/collect',json={'days':90,'max_pages':1}).json()
    env.db.add(IntelMembershipMonitor(subject_id=sid,enabled=True,status='running',lease_token='old',lease_until=AT+timedelta(hours=1)))
    env.db.add(IntelMembershipSnapshot(subject_id=sid,utc_day='2026-11-09',observed_at=AT,member_count=3,corporations=[]))
    env.db.commit()
    assert env.client.delete(f'/intel/subjects/{sid}').json()=={'deleted':True,'notes_preserved':True}
    row=env.db.get(IntelSubject,sid)
    assert row.archived and row.public_data=={} and not row.priority
    assert env.db.get(IntelSubject,other) is not None
    assert env.db.get(Killmail,123) is not None
    for model in (IntelCollection,IntelObservation,IntelSighting,IntelMembershipMonitor,IntelMembershipSnapshot):
        assert env.db.scalar(select(func.count()).select_from(model).where(model.subject_id==sid))==0
    assert owned_job(env.db,job['id'],'old') is None
    persist(env.factory,sid,'old',{'member_count':5})
    assert env.db.get(IntelMembershipMonitor,sid) is None
    archived=env.client.get(f'/intel/subjects/{sid}/report').json()
    assert archived['summary']['kills']==0 and archived['subject']['archived'] and not archived['observations']
    assert len(env.client.get(f'/intel/subjects/{sid}/notes').json())==1
    env.current[0]=env.users[1]
    assert len(env.client.get(f'/intel/subjects/{sid}/notes').json())==2
    assert env.client.post(f'/intel/subjects/{sid}/collect',json={'days':90,'max_pages':1}).status_code==404
    assert env.client.patch(f'/intel/subjects/{sid}/priority',json={'priority':True}).status_code==409
    env.current[0]=env.users[0]
    if kind=='character':seed(env,[pilot()])
    else:assert subject(env,kind,row.eve_id)['id']==sid
    assert not env.db.get(IntelSubject,sid).archived
    assert env.db.scalar(select(func.count()).select_from(IntelNote).where(IntelNote.subject_id==sid))==2

def test_scan_does_not_overwrite_existing_profile_priority_or_notes(env):
    sid=subject(env)['id'];row=env.db.get(IntelSubject,sid)
    original=row.public_data
    row.priority=True;env.db.commit()
    seed(env,[pilot()])
    env.db.refresh(row)
    assert row.public_data==original and row.priority

def test_priority_change_does_not_make_old_affiliation_newer(env):
    seed(env,[pilot(9001,'Old pilot',101,201)])
    old=env.db.scalar(select(IntelSubject).where(IntelSubject.eve_id==9001))
    old.created_at=AT-timedelta(days=2)
    seed(env,[pilot(9002,'New pilot',101,202)])
    assert env.client.patch(f'/intel/subjects/{old.id}/priority',json={'priority':True}).status_code==200
    tree=env.client.get('/intel/subject-tree').json()
    assert len(tree)==1 and tree[0]['eve_id']==202 and tree[0]['pilot_count']==2

def test_later_scan_restores_deleted_pilot_with_new_affiliation(env):
    seed(env,[pilot(9001,'Old pilot',101,201),pilot(9002,'Other pilot',101,201)])
    sid=env.db.scalar(select(IntelSubject.id).where(IntelSubject.eve_id==9001))
    assert env.client.delete(f'/intel/subjects/{sid}').status_code==200
    seed_scan(env.db,env.users[0],{'pilots':[pilot(9001,'Old pilot',101,202)]},AT+timedelta(days=1));env.db.commit()
    tree=env.client.get('/intel/subject-tree').json()
    assert len(tree)==1 and tree[0]['eve_id']==202 and tree[0]['pilot_count']==2

def test_delete_during_inflight_profile_fences_later_writes(env):
    sid=subject(env)['id']
    job=env.client.post(f'/intel/subjects/{sid}/collect',json={'days':90,'max_pages':1}).json()
    row=env.db.get(IntelCollection,job['id']);row.status='running';row.lease_token='fixture';env.db.commit()
    class Source:
        async def profile(self,*args):
            assert env.client.delete(f'/intel/subjects/{sid}').status_code==200
            return {'name':'Must not return'}
        async def stats(self,*args):return {'totals':{}}
    # Force profile refresh rather than its normal one-hour cache.
    env.db.get(IntelSubject,sid).public_data={};env.db.commit()
    asyncio.run(profile_stage(job['id'],'fixture',Source(),env.factory))
    env.db.expire_all()
    assert env.db.get(IntelSubject,sid).public_data=={} and env.db.get(IntelSubject,sid).archived

def test_access_denied_and_read_only_views(env):
    sid=subject(env)['id']
    for actor,status in ((None,401),(env.users[3],403),(env.users[4],403)):
        env.current[0]=actor
        for method,path,body in [('GET','/intel/subject-tree',None),('GET','/intel/subject-tree/pilots?alliance=none&corporation=unknown',None),('DELETE',f'/intel/subjects/{sid}',None),('PATCH',f'/intel/subjects/{sid}/priority',{'priority':True})]:
            assert env.client.request(method,path,json=body).status_code==status

def test_migration_roundtrip():
    path=Path(__file__).parents[1]/'alembic/versions/0108_intel_subject_browser.py'
    spec=importlib.util.spec_from_file_location('browser_migration',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE intel_subjects (id INTEGER PRIMARY KEY, name TEXT)')
        conn.exec_driver_sql("INSERT INTO intel_subjects VALUES (1, 'Existing')")
        with Operations.context(MigrationContext.configure(conn)):
            mod.upgrade()
            assert conn.exec_driver_sql('SELECT archived, priority FROM intel_subjects').one()==(0,0)
            mod.downgrade()
        assert {c['name'] for c in inspect(conn).get_columns('intel_subjects')}=={'id','name'}
