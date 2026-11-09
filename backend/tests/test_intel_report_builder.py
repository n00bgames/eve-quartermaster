import asyncio
from datetime import datetime,timedelta,timezone
import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import select,func,create_engine,inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.api import intel_reports as api
from app.models import Killmail,EveCharacter,KillmailAttacker
from app.models.intel import IntelSubject,IntelNote,IntelSighting,LocalScanSighting,IntelSourceCache
from app.models.intel_activity import IntelActivitySample
from app.models.local_scan import LocalScanReport
from app.services import intel_report_refresh as refresh
from .test_intel_reports import env,subject,FakeSource,AT

BASE='/intel-reports'
SYSTEM=30000001
def bounds():
    at=datetime.now(timezone.utc)
    return dict(from_at=(at-timedelta(days=7)).isoformat(),to_at=(at+timedelta(minutes=1)).isoformat())
def read(e,kind='system',eid=SYSTEM):
    r=e.client.get(BASE+'/report',params={'kind':kind,'eve_id':eid,**bounds()})
    assert r.status_code==200,r.text
    assert r.headers['cache-control']=='private, no-store'
    return r.json()
class Source(FakeSource):
    async def zget(self,path):
        self.pages.append(path)
        return [{'killmail_id':kid,'zkb':{'hash':f'hash-{kid}','npc':False,'totalValue':100}} for kid in (101,102,103)]
@pytest.fixture
def reports(env):
    env.app.version='2.4.0';env.app.include_router(api.router);env.app.include_router(api.public_router)
    env.report_source=Source()
    with patch.object(api,'source_factory',return_value=env.report_source):yield env

def pull(e,kind='system',eid=SYSTEM):
    r=e.client.post(BASE+'/refresh',json={'kind':kind,'eve_id':eid})
    assert r.status_code==200,r.text
    return r.json()
def test_pull_and_all_four_report_scopes(reports):
    e=reports;before=e.db.scalar(select(func.count()).select_from(EveCharacter))
    value=pull(e);assert value['imported']==3 and value['status']=='completed'
    assert e.report_source.pages==[f'solarSystemID/{SYSTEM}/page/1']
    assert len(e.report_source.killcalls)==3
    for kind,eid in [('system',SYSTEM),('character',9001),('corporation',8002),('alliance',7001)]:
        if kind!='system':subject(e,kind,eid)
        data=read(e,kind,eid)['public_report']
        assert data['summary']['killmails']==3 and data['summary']['combat_pilots']>0
        assert len(data['recent_killmails'])==3 and data['active_systems'][0]['system_id']==SYSTEM
        assert sum(r['killmails'] for r in data['utc_hours'])==3
        assert len(data['common_hulls'])==1
    assert e.db.scalar(select(func.count()).select_from(EveCharacter))==before
    assert pull(e)['cached'] and len(e.report_source.pages)==1

def test_no_external_fetch_on_report_reads_and_unknown_counts(reports):
    data=read(reports)
    assert reports.report_source.pages==[]
    assert data['public_report']['recent_killmails']==[]
    assert all(r['jumps'] is None and r['pod_kills'] is None for r in data['public_report']['hourly'])
    assert not data['public_report']['esi_activity']['available']

def observations(e):
    sid=subject(e)['id']
    e.db.add(IntelNote(subject_id=sid,author_user_id=e.users[0].id,body='SECRET PRIVATE NOTE',is_private=True))
    e.db.get(IntelSubject,sid).priority=True
    for i,(private,owner) in enumerate([(False,0),(True,0),(True,1)]):
        e.db.add(LocalScanSighting(source_hash=str(i)*64,created_by_user_id=e.users[owner].id,is_private=private,
            character_eve_id=9001 if i<2 else 9009,system_id=SYSTEM,system_name='Test System',observed_at=AT,recorded_at=AT))
    e.db.add(IntelSighting(subject_id=sid,observer_user_id=e.users[0].id,request_id='manual-fixture',recorded_at=AT,
        manual_time=False,system_id=SYSTEM,system_name='Test System',ship_type_id=100,ship_type_name='Test Cruiser',observed_at=AT))
    e.db.commit()
    return sid
def test_sightings_privacy_before_counts_and_no_journey_or_notes(reports):
    e=reports;observations(e)
    data=read(e);internal=data['internal_sightings']
    assert internal['total_sightings']==3 and internal['distinct_pilots']==1
    assert internal['rows'][0]['sightings']==3
    assert {r['name'] for r in internal['hulls']}=={'Unknown hull','Test Cruiser'}
    assert 'SECRET PRIVATE NOTE' not in str(data) and 'priority' not in str(data)
    e.current[0]=e.users[1]
    other=read(e)['internal_sightings'];assert other['total_sightings']==3 and other['distinct_pilots']==2

def save(e,private=False,kind='system',eid=SYSTEM):
    r=e.client.post(BASE+'/snapshots',json={'kind':kind,'eve_id':eid,**bounds(),'is_private':private,'anonymous':True,'retention':'24h'})
    assert r.status_code==201,r.text
    return r.json()
@pytest.mark.parametrize('kind,eid',[('system',SYSTEM),('character',9001),('corporation',8002),('alliance',7001)])
def test_public_snapshot_allowlist_anonymous_immutable_expiry_and_revocation(reports,kind,eid):
    e=reports;observations(e);pull(e)
    if kind not in ('system','character'):subject(e,kind,eid)
    item=save(e,kind=kind,eid=eid);token=item['token']
    assert item['application_version']=='2.4.0' and item['creator']=='Anonymous' and item['share_path']==f'#intel-report/{token}'
    e.current[0]=None
    r=e.client.get(BASE+'/public/'+token);assert r.status_code==200
    assert r.headers['cache-control']=='no-store' and 'noindex' in r.headers['x-robots-tag'] and r.headers['referrer-policy']=='no-referrer'
    public=r.json();assert public['report']['summary']['killmails']==3
    assert public['created_at']==item['created_at'] and public['expires_at']==item['expires_at']
    for secret in ('SECRET PRIVATE NOTE','internal_sightings','priority','authorized','source_hash','created_by_user_id','observer_user_id'):
        assert secret not in str(public)
    e.db.get(Killmail,101).solar_system_id=30000142;e.db.commit()
    assert e.client.get(BASE+'/public/'+token).json()==public
    e.current[0]=e.users[1]
    assert e.client.delete(BASE+'/snapshots/'+token).status_code==404
    assert e.client.get(BASE+'/snapshots').json()['total']==0
    e.current[0]=e.users[0]
    assert e.client.delete(BASE+'/snapshots/'+token).status_code==200
    e.current[0]=None
    assert e.client.get(BASE+'/public/'+token).status_code==404
    e.current[0]=e.users[0];item=save(e,kind=kind,eid=eid)
    e.db.get(LocalScanReport,item['token']).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);e.db.commit()
    assert e.client.get(BASE+'/public/'+item['token']).status_code==404

def test_private_snapshots_and_token_kind_boundaries(reports):
    e=reports;item=save(e,private=True)
    assert item['share_path'] is None
    assert e.client.get(BASE+'/snapshots/'+item['token']).status_code==200
    e.current[0]=None
    assert e.client.get(BASE+'/public/'+item['token']).status_code==404
    for token in ('x','../etc','a'*43):assert e.client.get(BASE+'/public/'+token).status_code==404
    e.db.get(LocalScanReport,item['token']).report_kind='local';e.db.get(LocalScanReport,item['token']).is_private=False;e.db.commit()
    assert e.client.get(BASE+'/public/'+item['token']).status_code==404

def test_esi_reported_hours_independent_missing_feed_and_idempotency(reports):
    e=reports;at=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
    snapshot={'jumps':{'observed_at':at.isoformat(),'data':{str(SYSTEM):{'ship_jumps':42}},'stale':False},
        'kills':{'observed_at':at.isoformat(),'data':None,'stale':True}}
    assert refresh.save_activity(e.db,SYSTEM,snapshot)['saved']==1
    assert refresh.save_activity(e.db,SYSTEM,snapshot)['saved']==1
    assert e.db.scalar(select(func.count()).select_from(IntelActivitySample))==1
    rows=read(e)['public_report']['hourly'];known=[r for r in rows if r['jumps'] is not None]
    assert len(known)==1 and known[0]['jumps']==42 and known[0]['pod_kills'] is None
    snapshot['kills']={'observed_at':at.isoformat(),'data':{},'stale':False}
    assert refresh.save_activity(e.db,SYSTEM,snapshot)['saved']==2
    assert [r for r in read(e)['public_report']['hourly'] if r['pod_kills'] is not None][0]['pod_kills']==0
    assert refresh.save_activity(e.db,31000001,snapshot)['saved']==0
    assert refresh.save_activity(e.db,SYSTEM,{'jumps':{'observed_at':None,'data':{}},'kills':{}})['saved']==0

def test_source_failure_preserves_evidence_and_scope_mismatch(reports):
    e=reports;pull(e)
    cache=e.db.get(IntelSourceCache,refresh.key('system',SYSTEM));cache.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);e.db.commit()
    async def fail(*args):raise RuntimeError('upstream')
    with patch.object(e.report_source,'zget',side_effect=fail):assert pull(e)['status']=='error'
    assert e.db.scalar(select(func.count()).select_from(Killmail))==3
    assert refresh.matches('system',SYSTEM,{'solar_system_id':SYSTEM})
    assert not refresh.matches('character',9001,{'victim':{'character_id':9002},'attackers':[]})

def test_refresh_cap_partial_failures_and_no_metadata_enrollment(reports):
    e=reports
    async def page(path):return [{'killmail_id':kid,'zkb':{'hash':f'hash-{kid}','npc':False}} for kid in range(101,161)]
    e.report_source.fail_id=102
    with patch.object(e.report_source,'zget',side_effect=page):value=pull(e)
    assert value['status']=='partial' and value['failed']==1 and value['imported']==24
    assert len(e.report_source.killcalls)==25
    assert e.db.scalar(select(func.count()).select_from(Killmail))==24

def test_refresh_cross_request_lease_fencing(reports):
    e=reports;first=refresh.claim(e.db,'system',SYSTEM)
    assert first and refresh.claim(e.db,'system',SYSTEM) is None
    cache=e.db.get(IntelSourceCache,refresh.key('system',SYSTEM));cache.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);e.db.commit()
    second=refresh.claim(e.db,'system',SYSTEM);assert second and second!=first
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as caught:refresh.persist(e.db,'system',SYSTEM,first,None,RuntimeError())
    assert caught.value.status_code==409
    assert e.db.get(IntelSourceCache,refresh.key('system',SYSTEM)).payload['lease']==second

def test_permission_revocation_during_source_wait_cannot_import(reports):
    e=reports
    async def page(path):
        e.users[0].deleted_at=datetime.now(timezone.utc);e.db.commit()
        return [{'killmail_id':101,'zkb':{'hash':'fixture'}}]
    with patch.object(e.report_source,'zget',side_effect=page):
        response=e.client.post(BASE+'/refresh',json={'kind':'system','eve_id':SYSTEM})
    assert response.status_code==403
    assert e.db.scalar(select(func.count()).select_from(Killmail))==0
    assert not api._refreshing

def test_sighting_frequency_is_not_affected_by_public_combat_pull(reports):
    e=reports;observations(e)
    before=read(e)['internal_sightings']
    pull(e)
    assert read(e)['internal_sightings']==before

def test_share_projection_cannot_include_manual_only_system_or_hull(reports):
    e=reports;sid=subject(e)['id']
    e.db.add(IntelSighting(subject_id=sid,observer_user_id=e.users[0].id,request_id='manual-only',recorded_at=AT,manual_time=True,
        system_id=SYSTEM,system_name='Manual-only location',ship_type_id=100,ship_type_name='Manual-only hull',observed_at=AT));e.db.commit()
    data=save(e,kind='character',eid=9001)['report']
    assert data['active_systems']==[] and data['common_hulls']==[] and data['summary']['killmails']==0
    assert 'Manual-only' not in str(data)

def test_lookup_access_window_validation_and_strict_snapshot_input(reports):
    e=reports
    r=e.client.post(BASE+'/resolve',json={'kind':'system','name':'Test Sys'});assert r.status_code==200 and r.json()['rows'][0]['eve_id']==SYSTEM
    bad=bounds();bad['to_at']=(datetime.now(timezone.utc)+timedelta(days=100)).isoformat()
    assert e.client.get(BASE+'/report',params={'kind':'system','eve_id':SYSTEM,**bad}).status_code==422
    assert e.client.post(BASE+'/snapshots',json={'kind':'system','eve_id':SYSTEM,**bounds(),'is_private':False,'report':{'leak':'spoof'}}).status_code==422
    for actor,code in ((None,401),(e.users[3],403),(e.users[4],403)):
        e.current[0]=actor
        assert e.client.get(BASE+'/report',params={'kind':'system','eve_id':SYSTEM,**bounds()}).status_code==code
        assert e.client.post(BASE+'/refresh',json={'kind':'system','eve_id':SYSTEM}).status_code==code
        assert e.client.get(BASE+'/snapshots').status_code==code

def test_migration_roundtrip():
    path=Path(__file__).parents[1]/'alembic/versions/0109_intel_activity.py'
    spec=importlib.util.spec_from_file_location('activity_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE eve_systems (system_id INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade();assert 'intel_activity_samples' in inspect(conn).get_table_names();module.downgrade()
            assert 'intel_activity_samples' not in inspect(conn).get_table_names()
