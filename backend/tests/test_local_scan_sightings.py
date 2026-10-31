from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import importlib.util
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, func, inspect, select
from app.api import intel
from app.models import Base, EveCharacter, EveSystem
from app.models.intel import IntelSubject, IntelSighting, LocalScanSighting
from app.models.local_scan import LocalScanReport
from app.services import local_scan as service
from app.services.local_scan_sightings import record
from .test_local_scan import env, create


@pytest.fixture
def scans(env):
    env.app.include_router(intel.router, prefix='/api')
    return env


def dossier(env, eve_id=9001, kind='character'):
    row=IntelSubject(kind=kind, eve_id=eve_id, name='Synthetic Pilot', created_by_user_id=env.users['member'].id)
    env.db.add(row);env.db.commit()
    return row.id


def report(env, sid, role='intel_analyst', query=''):
    env.current[0]=env.users[role]
    response=env.client.get(f'/api/intel/subjects/{sid}/report'+query)
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='private, no-store'
    return response.json()


def test_generation_indexes_each_resolved_pilot_before_any_dossier(scans):
    env=scans
    chars=env.db.scalar(select(func.count()).select_from(EveCharacter))
    scan=create(env,system_id=30000142,anonymous=True)
    rows=env.db.scalars(select(LocalScanSighting)).all()
    assert len(rows)==3 and {r.character_eve_id for r in rows}=={9001,9002,9003}
    assert all(service.utc(r.observed_at).isoformat()==scan['created_at'] for r in rows)
    assert env.db.scalar(select(func.count()).select_from(IntelSubject))==0
    assert env.db.scalar(select(func.count()).select_from(EveCharacter))==chars
    assert env.db.scalar(select(func.count()).select_from(IntelSighting))==0
    assert record(env.db,env.db.get(LocalScanReport,scan['token']))==0
    env.db.commit()
    sid=dossier(env)
    data=report(env,sid);summary=data['summary']
    assert (summary['kills'],summary['losses'],summary['sightings'])==(0,0,1)
    assert summary['ships'][0]['name']=='Unknown Ship Type' and summary['ships'][0]['id'] is None
    assert summary['systems'][0]['name']=='Jita' and summary['systems'][0]['sightings']==1
    assert sum(h['appearances'] for h in summary['utc_hours'])==0
    sighting=data['sightings']['rows'][0]
    assert sighting['source']=='local_scan' and sighting['observer'] is None and sighting['id'].startswith('local-scan:')
    assert sighting['ship_type_id'] is None and sighting['kills']==sighting['losses']==0
    assert scan['token'] not in str(data) and rows[0].source_hash not in str(data)
    assert 'Member' not in str(data['sightings'])
    assert report(env,dossier(env,9001,'corporation'))['sightings']['total']==0


def test_no_system_invalid_inputs_and_unresolved_names_do_not_create_sightings(scans):
    create(scans)
    for payload in [{'text':'Unknown Pilot','system_id':30000142}, {'text':'Alpha One','system_id':999}]:
        assert scans.client.post('/api/local-scans',json=payload).status_code==422
    assert scans.db.scalar(select(func.count()).select_from(LocalScanSighting))==0


def test_scan_and_sightings_roll_back_together(scans):
    with patch('app.api.local_scan.record_audit_event',side_effect=RuntimeError('fixture transaction failure')):
        with pytest.raises(RuntimeError):create(scans,system_id=30000142)
    assert scans.db.scalar(select(func.count()).select_from(LocalScanReport))==0
    assert scans.db.scalar(select(func.count()).select_from(LocalScanSighting))==0


def test_private_scan_never_leaks_into_other_users_totals_or_timeline(scans):
    scan=create(scans,'intel_analyst',system_id=30000142,is_private=True)
    sid=dossier(scans)
    own=report(scans,sid)
    assert own['sightings']['total']==1
    for role in ['admin','host','director']:
        other=report(scans,sid,role)
        assert other['sightings']['total']==0 and other['sightings']['rows']==[]
        assert other['summary']['ships']==other['summary']['systems']==other['summary']['regions']==other['summary']['timeline']==[]
    from app.services.intel_reports import build_report
    end=service.now()+timedelta(seconds=1)
    assert build_report(scans.db,scans.db.get(IntelSubject,sid),end-timedelta(days=1),end)['sightings']['total']==0
    # Private observation keeps its scope after deleting the originating scan.
    scans.db.delete(scans.db.get(LocalScanReport,scan['token']));scans.db.commit()
    assert report(scans,sid)['sightings']['total']==1
    assert report(scans,sid,'admin')['sightings']['total']==0


def test_expiring_share_links_do_not_erase_intel_history(scans):
    scan=create(scans,system_id=30000142)
    saved=scans.db.get(LocalScanReport,scan['token']);saved.expires_at=service.now()-timedelta(seconds=1);scans.db.commit()
    assert service.purge_expired(scans.db)==1;scans.db.commit()
    sid=dossier(scans)
    assert report(scans,sid)['sightings']['total']==1
    # Another independently generated scan is a second observation, even of the same pilots.
    create(scans,system_id=30000142)
    assert report(scans,sid)['sightings']['total']==2


def test_scan_and_manual_sightings_merge_without_affecting_combat(scans):
    scan=create(scans,system_id=30000142)
    sid=dossier(scans)
    scans.current[0]=scans.users['intel_analyst']
    response=scans.client.post(f'/api/intel/subjects/{sid}/sightings',json={'system_id':30000142,'request_id':'ecf6fe9d-bb8c-4db0-8246-aa85c3984373'})
    assert response.status_code==201,response.text
    data=report(scans,sid)
    assert data['sightings']['total']==2 and len({str(r['id']) for r in data['sightings']['rows']})==2
    assert {r['source'] for r in data['sightings']['rows']}=={'analyst_sighting','local_scan'}
    assert data['summary']['ships'][0]['sightings']==data['summary']['systems'][0]['sightings']==2
    assert data['summary']['timeline'][0]['sightings']==2
    at=datetime.fromisoformat(scan['created_at'])
    from urllib.parse import urlencode
    query='?'+urlencode({'from_at':at.isoformat(),'to_at':(at+timedelta(microseconds=1)).isoformat()})
    assert report(scans,sid,query=query)['sightings']['total']==1
    query='?'+urlencode({'from_at':(at-timedelta(seconds=1)).isoformat(),'to_at':at.isoformat()})
    assert report(scans,sid,query=query)['sightings']['total']==0


def test_all_aggregates_include_more_than_the_latest_200_visible_entries(scans):
    at=service.now()-timedelta(minutes=1)
    for i in range(205):
        scans.db.add(LocalScanSighting(source_hash=sha256(str(i).encode()).hexdigest(),created_by_user_id=scans.users['member'].id,
            is_private=False,character_eve_id=9001,system_id=30000142,system_name='Jita',observed_at=at,recorded_at=at))
    for i in range(220):
        scans.db.add(LocalScanSighting(source_hash=sha256(('private'+str(i)).encode()).hexdigest(),created_by_user_id=scans.users['member'].id,
            is_private=True,character_eve_id=9001,system_id=30000142,system_name='Hidden',observed_at=service.now(),recorded_at=at))
    scans.db.commit()
    data=report(scans,dossier(scans))
    assert data['sightings']['total']==205 and len(data['sightings']['rows'])==200
    assert data['summary']['systems'][0]['sightings']==data['summary']['ships'][0]['sightings']==205
    assert all(r['system_name']=='Jita' for r in data['sightings']['rows'])


def test_migration_backfills_saved_local_snapshots_in_batches(scans):
    # Recreate the pre-migration schema only in an isolated in-memory database.
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine,tables=[t for t in Base.metadata.tables.values() if t.name!='intel_local_scan_sightings'])
    path=Path(__file__).resolve().parents[1]/'alembic/versions/0102_local_scan_sightings.py'
    spec=importlib.util.spec_from_file_location('scan_sighting_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    at=datetime(2024,1,2,3,4,5,tzinfo=timezone.utc)
    with engine.begin() as conn:
        conn.execute(EveSystem.__table__.insert(),{'system_id':30000142,'name':'Jita'})
        rows=[]
        for i in range(205):
            rows.append(dict(token=f'{i:043d}',account_name='Must not copy identity',application_version='2.0.1',created_at=at,
                retention='24h',report_kind='local',is_private=i%2==0,anonymous=True,
                payload={'system':{'id':30000142},'pilots':[{'character_id':9001},{'character_id':9001},{'character_id':9002}], 'unresolved':['Never Guess']}))
        rows.extend([{**rows[0],'token':'nosystem','payload':{}}, {**rows[0],'token':'dscan','report_kind':'dscan'},
            {**rows[0],'token':'bad-system','payload':{'system':{'id':999},'pilots':[{'character_id':9001}]}}])
        conn.execute(LocalScanReport.__table__.insert(),rows)
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            table=LocalScanSighting.__table__
            assert conn.scalar(select(func.count()).select_from(table))==410
            found=conn.execute(select(table)).mappings().first()
            assert service.utc(found['observed_at'])==at and found['system_name']=='Jita'
            assert found['source_hash']==sha256(rows[0]['token'].encode()).hexdigest()
            assert found['is_private'] is True
            assert {c['name'] for c in inspect(conn).get_columns(table.name)}==set(table.c.keys())
            migration.downgrade();assert table.name not in inspect(conn).get_table_names()
            migration.upgrade();assert conn.scalar(select(func.count()).select_from(table))==410
    engine.dispose()
