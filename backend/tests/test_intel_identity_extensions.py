from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import asyncio,importlib.util
from unittest.mock import patch
import pytest
from sqlalchemy import select,func,inspect,create_engine
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.models import EveCharacter,EveCorporation,EveAlliance,Killmail,UserSectionPermission
from app.models.intel import IntelSighting,IntelSourceCache,IntelSubject
from app.services import intel_affiliations as service
from app.services.intel_sources import PublicSource
from .test_intel_sightings import seen,fields,report
from .test_intel_reports import env,subject

def test_unknown_hull_from_missing_or_null_ship_preserves_zero_combat(seen):
    body=fields(observed_at='2026-10-01T12:30:00Z');body.pop('ship_type_id')
    response=seen.client.post('/intel/subjects',json={'kind':'character','eve_id':9001,'sighting':body})
    assert response.status_code==201,response.text
    sid=response.json()['id'];path=f'/intel/subjects/{sid}/sightings'
    retry=seen.client.post(path,json={**body,'ship_type_id':None})
    assert retry.status_code==201 and retry.json()['ship_type_id'] is None
    assert retry.json()['ship_type_name']=='Unknown Ship Type'
    assert seen.client.post(path,json={**body,'ship_type_id':100}).status_code==409
    assert seen.client.post(path,json=fields()).status_code==201
    data=report(seen,sid,'?from_at=2026-10-01T00:00:00Z&to_at=2026-11-01T00:00:00Z')
    assert (data['summary']['kills'],data['summary']['losses'],data['sightings']['total'])==(0,0,2)
    unknown=next(r for r in data['summary']['ships'] if r['id'] is None)
    assert (unknown['name'],unknown['kills'],unknown['losses'],unknown['sightings'])==('Unknown Ship Type',0,0,1)
    assert seen.db.scalar(select(func.count()).select_from(Killmail))==0
    assert seen.db.scalar(select(func.count()).select_from(EveCharacter))==0

def test_unknown_default_time_requires_valid_system_and_does_not_hide_invalid_hulls(seen):
    sid=subject(seen)['id'];path=f'/intel/subjects/{sid}/sightings'
    before=datetime.now(timezone.utc)
    response=seen.client.post(path,json=fields(ship_type_id=None))
    assert response.status_code==201 and not response.json()['manual_time']
    assert datetime.fromisoformat(response.json()['observed_at'])>=before
    for values in [{'system_id':999,'ship_type_id':None},{'ship_type_id':0},{'ship_type_id':999},{'ship_type_id':'100'}]:
        assert seen.client.post(path,json=fields(**values)).status_code==422

def test_nullable_ship_migration_preserves_known_rows_and_safe_downgrade():
    versions=Path(__file__).parents[1]/'alembic/versions'
    def module(name):
        spec=importlib.util.spec_from_file_location(name,versions/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    old=module('0099_intel_sightings');new=module('0100_unknown_ship_sightings');engine=create_engine('sqlite://')
    with engine.begin() as conn:
        for table,key in [('users','id'),('intel_subjects','id'),('eve_systems','system_id'),('eve_types','type_id')]:conn.exec_driver_sql(f'CREATE TABLE {table} ({key} INTEGER PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(conn)):
            old.upgrade()
            conn.exec_driver_sql("INSERT INTO intel_sightings (id,subject_id,observer_user_id,request_id,system_id,system_name,ship_type_id,ship_type_name,observed_at) VALUES (1,1,1,'known',1,'System',100,'Hull','2026-10-01')")
            new.upgrade();assert next(c for c in inspect(conn).get_columns('intel_sightings') if c['name']=='ship_type_id')['nullable']
            assert conn.exec_driver_sql('SELECT ship_type_id FROM intel_sightings WHERE id=1').scalar()==100
            conn.exec_driver_sql("INSERT INTO intel_sightings (id,subject_id,observer_user_id,request_id,system_id,system_name,ship_type_id,ship_type_name,observed_at) VALUES (2,1,1,'unknown',1,'System',NULL,'Unknown Ship Type','2026-10-01')")
            with pytest.raises(RuntimeError,match='unknown-ship sightings'):new.downgrade()
            assert conn.exec_driver_sql('SELECT COUNT(*) FROM intel_sightings').scalar()==2
            conn.exec_driver_sql('DELETE FROM intel_sightings WHERE id=2');new.downgrade()
            assert not next(c for c in inspect(conn).get_columns('intel_sightings') if c['name']=='ship_type_id')['nullable']
            new.upgrade()
            assert any(c['column_names']==['subject_id','observer_user_id','request_id'] for c in inspect(conn).get_unique_constraints('intel_sightings'))

def affiliations_subject(env):
    sid=subject(env)['id'];row=env.db.get(IntelSubject,sid)
    row.public_data={'esi':{'state':'available','data':{'name':row.name,'corporation_id':8002,'alliance_id':7001}}};env.db.commit()
    return sid

class OrganizationSource:
    calls=[];fail=False
    async def close(self):pass
    async def organization(self,kind,eid):
        self.calls.append((kind,eid))
        if self.fail:raise ValueError('fixture failure')
        return {'name':'Example Corporation' if kind=='corporation' else 'Example Alliance','ticker':'EXCO' if kind=='corporation' else 'EXAL'}

def test_affiliation_names_tags_cached_and_available_on_saved_reports(env):
    sid=affiliations_subject(env);source=OrganizationSource();source.calls=[]
    with patch.object(service,'PublicSource',return_value=source):
        first=env.client.get(f'/intel/subjects/{sid}/affiliations');assert first.status_code==200,first.text
        rows=first.json();assert [(r['name'],r['ticker']) for r in rows]==[('Example Corporation','EXCO'),('Example Alliance','EXAL')]
        assert not any(r['stale'] for r in rows)
        assert env.client.get(f'/intel/subjects/{sid}/affiliations').json()==rows and len(source.calls)==2
    assert report(env,sid)['affiliations']==rows
    assert env.db.scalar(select(func.count()).select_from(EveCharacter))==0
    assert env.db.scalar(select(func.count()).select_from(IntelSighting))==0

def test_affiliation_failures_keep_prior_names_and_back_off(env):
    sid=affiliations_subject(env);now=datetime.now(timezone.utc)
    env.db.add(IntelSourceCache(key='organization:corporation:8002',payload={'name':'Retained Corporation','ticker':'OLD'},expires_at=now-timedelta(seconds=1)));env.db.commit()
    source=OrganizationSource();source.calls=[];source.fail=True
    with patch.object(service,'PublicSource',return_value=source):
        rows=env.client.get(f'/intel/subjects/{sid}/affiliations').json()
        assert rows[0]['name']=='Retained Corporation' and rows[0]['ticker']=='OLD' and rows[0]['stale']
        assert rows[1]['name']=='Alliance 7001' and rows[1]['ticker'] is None and rows[1]['stale']
        env.client.get(f'/intel/subjects/{sid}/affiliations');assert len(source.calls)==2

def test_affiliation_access_and_no_alliance_or_organization_dossiers(env):
    sid=subject(env)['id'];source=OrganizationSource();source.calls=[]
    with patch.object(service,'PublicSource',return_value=source):
        rows=env.client.get(f'/intel/subjects/{sid}/affiliations').json();assert [r['kind'] for r in rows]==['corporation']
        org=subject(env,'corporation',8002)['id'];assert env.client.get(f'/intel/subjects/{org}/affiliations').json()==[]
    assert env.client.get('/intel/subjects/99999/affiliations').status_code==404
    env.current[0]=env.users[3];assert env.client.get(f'/intel/subjects/{sid}/affiliations').status_code==403
    env.current[0]=None;assert env.client.get(f'/intel/subjects/{sid}/affiliations').status_code==401

def test_public_organization_adapter_uses_only_public_metadata():
    source=PublicSource();paths=[]
    async def fetch(path):paths.append(path);return {'name':'Example Corp','ticker':'TEST','description':'ignored','ceo_id':123}
    source.esi.get=fetch
    async def run():
        try:
            assert await source.organization('corporation',8002)=={'name':'Example Corp','ticker':'TEST'}
            assert await source.organization('alliance',7001)=={'name':'Example Corp','ticker':'TEST'}
            with pytest.raises(ValueError):await source.organization('character',9001)
        finally:await source.close()
    asyncio.run(run());assert paths==['/corporations/8002/','/alliances/7001/']

def test_membership_change_uses_new_ids_without_old_affiliation_cards(env):
    sid=affiliations_subject(env);source=OrganizationSource();source.calls=[]
    with patch.object(service,'PublicSource',return_value=source):
        assert len(env.client.get(f'/intel/subjects/{sid}/affiliations').json())==2
        row=env.db.get(IntelSubject,sid);row.public_data={'esi':{'state':'available','data':{'corporation_id':8003}}};env.db.commit()
        rows=env.client.get(f'/intel/subjects/{sid}/affiliations').json()
        assert len(rows)==1 and rows[0]['eve_id']==8003 and rows[0]['kind']=='corporation'
        assert report(env,sid)['affiliations']==rows
        assert ('corporation',8003) in source.calls
