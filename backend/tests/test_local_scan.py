from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import asyncio
import importlib.util
from pathlib import Path
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.api import local_scan, auth, market, navigation, esi
from app.api.auth import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import Base, User, EveCharacter, EveCorporation, EveSystem, EsiToken, UserSectionPermission, RoleDefinition
from app.models.local_scan import LocalScanReport, ScanHighlight
from app.services import local_scan as service
from app.services.esi_scope_policy import allowed_scopes, effective_token_scopes, requested_scopes, private_collection_enabled
from app.services.permissions import BUILT_IN_ROLES, effective_permissions, role_rank


class Source:
    async def close(self): pass
    async def resolve(self, names):
        pilots = {"Alpha One":9001,"Beta Two":9002,"Gamma Three":9003}
        return {"characters":[{"id":eid,"name":name} for name,eid in pilots.items() if name.casefold() in {n.casefold() for n in names}],
                "corporations":[{"id":101,"name":"Red Corp"}] if "Red Corp" in names else [],
                "alliances":[{"id":201,"name":"Red Alliance"}] if "Red Alliance" in names else []}
    async def affiliations(self, ids):
        return [{"character_id":eid,"corporation_id":101 if eid != 9002 else 102,
                 **({"alliance_id":201} if eid != 9002 else {})} for eid in ids]
    async def names(self, ids):
        return [{"id":eid,"name":{101:"Red Corp",102:"Neutral Corp",201:"Red Alliance"}[eid],
                 "category":"alliance" if eid==201 else "corporation"} for eid in ids]


@pytest.fixture
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db=Session(engine,expire_on_commit=False)
    users={role:User(email=f'{role}@test.invalid',display_name=role.title(),role=role if role!='other' else 'member')
           for role in ['host','admin','director','member','other','intel_analyst','quartermaster','applicant']}
    db.add_all(users.values());db.flush()
    corps=[EveCorporation(corporation_id=i,name=f'Corp {i}') for i in [101,102]]
    db.add_all(corps);db.flush()
    for i,role in enumerate(users):
        char=EveCharacter(character_id=9100+i,name=f'Linked {role}',owner_user_id=users[role].id,corporation_id=corps[1 if role=='other' else 0].id)
        db.add(char);db.flush()
        db.add(EsiToken(user_id=users[role].id,character_id=char.id,scopes='esi-assets.read_assets.v1 esi-skills.read_skills.v1 esi-ui.write_waypoint.v1 esi-universe.read_structures.v1',encrypted_refresh_token='fixture'))
    db.add(EveSystem(system_id=30000142,name='Jita'));db.commit()
    current=[users['member']]
    app=FastAPI(version='2.0.0')
    app.include_router(local_scan.router,prefix='/api')
    def identity():
        if current[0] is None:raise HTTPException(401,'Sign in required')
        return current[0]
    def database():
        try:yield db
        finally:db.rollback()
    app.dependency_overrides[get_current_user]=identity;app.dependency_overrides[get_db]=database
    source=Source()
    with patch.object(local_scan,'source_factory',return_value=source),TestClient(app) as client:
        yield SimpleNamespace(client=client,db=db,users=users,current=current,source=source,app=app)
    db.close();engine.dispose()


def create(env,role='member',**extra):
    env.current[0]=env.users[role]
    response=env.client.post('/api/local-scans',json={'text':'Alpha One\nBeta Two\nGamma Three\nalpha one\nUnknown Pilot','retention':'24h',**extra})
    assert response.status_code==201,response.text
    return response.json()


def test_parse_clipboard_dedup_and_fleet():
    assert service.parse_local('\ufeffAlpha One\r\nalpha one\nBeta Two\tVenture\tJita')==['Alpha One','Beta Two']
    for text in ['', '<script>alert(1)</script>', '32880\tMy Venture\tVenture\t28 km', 'https://private.invalid/a']:
        with pytest.raises(ValueError):service.parse_local(text)
    with pytest.raises(ValueError):service.parse_local('\n'.join(f'Pilot {i}' for i in range(2001)))


def test_generate_public_snapshot_system_and_no_private_data(env):
    report=create(env,system_id=30000142,corporation_id=101)
    assert report['character_count']==3 and report['input_count']==4
    assert report['unresolved']==['Unknown Pilot'] and report['system']=={'id':30000142,'name':'Jita'}
    assert report['application_version']=='2.0.0' and report['account_name']=='Anonymous'
    assert len(report['token'])==43 and report['share_url'].endswith('/#local-scan/'+report['token'])
    assert not any(key in str(report) for key in ['encrypted_refresh_token','owner_user_id','email'])
    env.current[0]=None
    response=env.client.get('/api/local-scans/public/'+report['token'])
    assert response.status_code==200 and response.json()['pilots']==report['pilots']
    assert response.headers['cache-control']=='no-store' and 'noindex' in response.headers['x-robots-tag']
    assert env.client.get('/api/local-scans/reports').status_code==401


@pytest.mark.parametrize('retention,seconds',service.RETENTIONS.items())
def test_retention_choices(env,retention,seconds):
    report=create(env,retention=retention)
    if seconds is None:assert report['expires_at'] is None
    else:assert (service.utc(__import__('datetime').datetime.fromisoformat(report['expires_at']))-__import__('datetime').datetime.fromisoformat(report['created_at'])).total_seconds()==seconds


def test_expiry_denies_public_and_pdf_before_cleanup(env):
    report=create(env);row=env.db.get(LocalScanReport,report['token']);row.expires_at=service.now()-timedelta(seconds=1);env.db.commit()
    for suffix in ['', '/pdf']:
        assert env.client.get('/api/local-scans/public/'+report['token']+suffix).status_code==404
    assert env.client.get('/api/local-scans/reports').json()['total']==0
    assert service.purge_expired(env.db)==1;env.db.commit()
    assert env.db.get(LocalScanReport,report['token']) is None


def test_saved_highlights_are_private_and_snapshot_persists(env):
    target=env.client.post('/api/local-scans/highlights',json={'kind':'alliance','name':'Red Alliance'}).json()
    assert env.client.post('/api/local-scans/highlights',json={'kind':'alliance','name':'Red Alliance'}).json()['id']==target['id']
    report=create(env)
    assert report['highlighted_count']==2 and sum(p['alliance_highlighted'] for p in report['pilots'])==2
    env.current[0]=env.users['other']
    assert env.client.get('/api/local-scans/highlights').json()==[]
    env.client.delete('/api/local-scans/highlights/'+str(target['id']))
    env.current[0]=env.users['member']
    assert len(env.client.get('/api/local-scans/highlights').json())==1
    env.client.delete('/api/local-scans/highlights/'+str(target['id']))
    assert env.client.get('/api/local-scans/highlights').json()==[]
    assert env.client.get('/api/local-scans/public/'+report['token']).json()['highlighted_count']==2


def test_corporation_highlight_does_not_mark_other_alliance_members(env):
    env.client.post('/api/local-scans/highlights',json={'kind':'corporation','name':'Red Corp'})
    report=create(env)
    assert report['highlighted_count']==2 and not any(p['alliance_highlighted'] for p in report['pilots'])


def test_no_alliance_and_unknown_affiliation_remain_distinct(env):
    original=env.source.affiliations
    async def partial(ids):return [r for r in await original(ids) if r['character_id']!=9001]
    env.source.affiliations=partial
    report=create(env);byid={p['character_id']:p for p in report['pilots']}
    assert byid[9002]['affiliation_available'] and byid[9002]['alliance_id'] is None
    assert not byid[9001]['affiliation_available'] and report['warnings']


def test_invalid_and_empty_resolution_dont_publish(env):
    for payload in [{'text':'Unknown Pilot'}, {'text':'Alpha One','retention':'forever'}, {'text':'Alpha One','system_id':999}, {'text':'Alpha One','corporation_id':102}]:
        assert env.client.post('/api/local-scans',json=payload).status_code in [422,403]
    assert env.db.scalars(select(LocalScanReport)).all()==[]


@pytest.mark.parametrize('mode',['tokens','range','all'])
def test_member_deletion_never_exceeds_own_scope(env,mode):
    mine=create(env);other=create(env,'other',corporation_id=102)
    env.current[0]=env.users['member']
    spec={'tokens':[mine['token'],other['token']]} if mode=='tokens' else {'all_in_scope':True} if mode=='all' else {'from_at':(service.now()-timedelta(days=1)).isoformat(),'to_at':(service.now()+timedelta(days=1)).isoformat()}
    response=env.client.post('/api/local-scans/reports/delete',json=spec)
    assert response.json()['deleted']==1
    assert env.client.get('/api/local-scans/public/'+other['token']).status_code==200
    assert env.client.get('/api/local-scans/public/'+mine['token']).status_code==404


def test_director_corporation_scope_admin_and_custom_roles(env):
    corp=create(env,corporation_id=101);personal=create(env);other=create(env,'other',corporation_id=102)
    env.current[0]=env.users['director']
    assert [r['token'] for r in env.client.get('/api/local-scans/reports').json()['reports']]==[corp['token']]
    assert env.client.post('/api/local-scans/reports/delete',json={'all_in_scope':True}).json()['deleted']==1
    env.db.add(RoleDefinition(name='report_admin',display_name='Report admin',base_role='admin'));env.users['admin'].role='report_admin';env.db.commit()
    env.current[0]=env.users['admin']
    assert env.client.post('/api/local-scans/reports/delete',json={'all_in_scope':True}).json()['deleted']==2
    assert env.client.get('/api/local-scans/public/'+other['token']).status_code==404


def test_range_is_utc_start_inclusive_end_exclusive(env):
    r1=create(env);r2=create(env)
    at=service.now().replace(microsecond=0)
    env.db.get(LocalScanReport,r1['token']).created_at=at
    env.db.get(LocalScanReport,r2['token']).created_at=at+timedelta(hours=1);env.db.commit()
    response=env.client.post('/api/local-scans/reports/delete',json={'from_at':at.isoformat(),'to_at':(at+timedelta(hours=1)).isoformat()})
    assert response.json()['deleted']==1
    assert env.client.get('/api/local-scans/public/'+r2['token']).status_code==200
    for bad in [{},{'all_in_scope':True,'tokens':[r2['token']]},{'from_at':at.isoformat()},{'from_at':at.isoformat(),'to_at':at.isoformat()}]:
        assert env.client.post('/api/local-scans/reports/delete',json=bad).status_code==422


def test_report_permission_and_disabled_section(env):
    env.current[0]=env.users['intel_analyst'];assert env.client.get('/api/local-scans/context').status_code==200
    env.db.add(UserSectionPermission(user_id=env.current[0].id,section='local_scan',can_view=False));env.db.commit()
    assert env.client.post('/api/local-scans',json={'text':'Alpha One'}).status_code==403


def test_destination_characters_own_only_and_scope_checked(env):
    env.current[0]=env.users['admin']
    rows=env.client.get('/api/local-scans/destination-characters').json()
    assert len(rows)==1 and rows[0]['name']=='Linked admin'
    token=env.db.get(EsiToken,rows[0]['token_id']);token.scopes='esi-assets.read_assets.v1';env.db.commit()
    assert env.client.get('/api/local-scans/destination-characters').json()==[]


def test_pdf_snapshot_header_and_content(env):
    from pypdf import PdfReader
    report=create(env,system_id=30000142)
    with patch('app.services.local_scan_pdf.logo_images',new=AsyncMock(return_value={})):
        response=env.client.get('/api/local-scans/public/'+report['token']+'/pdf')
    assert response.status_code==200,response.text[:100] if response.status_code!=200 else ''
    assert response.content.startswith(b'%PDF') and response.headers['content-type']=='application/pdf'
    text='\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    for expected in ['Generated by EVE Quartermaster v2.0.0 by Anonymous','Red Alliance','Red Corp','Neutral Corp','Alpha One','System: Jita','Total pilots: 4','3 resolved / 1 unresolved names','Unknown Pilot']:
        assert expected in text


def test_batched_enrichment_no_individual_profile_requests():
    class BatchSource:
        calls=[]
        async def resolve(self,names):
            self.calls.append(('resolve',len(names)))
            return {'characters':[{'id':int(n.split()[-1])+1,'name':n} for n in names]}
        async def affiliations(self,ids):
            self.calls.append(('affiliations',len(ids)));return [{'character_id':i,'corporation_id':101} for i in ids]
        async def names(self,ids):return [{'id':101,'name':'Red Corp','category':'corporation'}]
    source=BatchSource();result=asyncio.run(service.enrich([f'Pilot {i}' for i in range(2000)],source))
    assert result['character_count']==2000 and max(n for _,n in source.calls)==250 and len(source.calls)==16


@pytest.mark.parametrize('role',['quartermaster','intel_analyst'])
def test_utility_scope_consent_and_existing_broad_tokens(env,role):
    user=env.users[role];token=env.db.scalar(select(EsiToken).where(EsiToken.user_id==user.id));char=env.db.get(EveCharacter,token.character_id)
    for group in ['core','full','contacts','mail','planetary']:
        assert requested_scopes(env.db,user,esi.auth_scopes_for_group(group),group)==['publicData']
    assert requested_scopes(env.db,user,esi.CORE_AUTH_SCOPES,'waypoint')==['publicData','esi-ui.write_waypoint.v1']
    assert effective_token_scopes(token)=={'esi-ui.write_waypoint.v1','esi-universe.read_structures.v1'}
    assert not private_collection_enabled(env.db,user)
    assert not esi.can_force_sync_character_token(token,char,env.users['admin'],env.db)
    with pytest.raises(HTTPException):esi.require_scope(token,'esi-assets.read_assets.v1','Read assets')
    from app.services.quartermaster_access import authenticated_rows
    assert token.id not in [t.id for t,c in authenticated_rows(env.db)]


def test_role_and_section_policy_changes_take_effect_without_relink(env):
    token=env.db.scalar(select(EsiToken).where(EsiToken.user_id==env.users['member'].id))
    assert 'esi-assets.read_assets.v1' in effective_token_scopes(token)
    env.db.add(UserSectionPermission(user_id=token.user_id,section='assets',can_view=False));env.db.commit()
    assert 'esi-assets.read_assets.v1' not in effective_token_scopes(token)
    env.users['member'].role='intel_analyst';env.db.commit()
    assert 'esi-skills.read_skills.v1' not in effective_token_scopes(token)


def test_custom_utility_roles_and_navigation_market_every_role(env):
    env.db.add(RoleDefinition(name='front_analyst',display_name='Front Analyst',base_role='intel_analyst'));env.users['intel_analyst'].role='front_analyst';env.db.commit()
    assert not private_collection_enabled(env.db,env.users['intel_analyst'])
    for role in BUILT_IN_ROLES:
        user=User(role=role,email=role+'2@test.invalid',display_name=role);env.db.add(user);env.db.flush()
        perms=effective_permissions(user,env.db)
        assert perms['navigation'] and perms['market'],role
        if role=='intel_analyst':assert perms['intel_reports'] and perms['local_scan'] and not perms['assets'] and not perms['skills']


def test_quartermaster_utility_posts_work_without_admin_mutations(env):
    app=FastAPI();app.include_router(auth.router,prefix='/api');app.include_router(market.router,prefix='/api');app.include_router(navigation.router,prefix='/api')
    app.dependency_overrides[get_db]=lambda:env.db
    token=create_access_token(str(env.users['quartermaster'].id))
    with patch.object(market,'appraise_market',new=AsyncMock(return_value={'items':[]})),TestClient(app,headers={'Authorization':'Bearer '+token}) as client:
        assert client.post('/api/market/appraise',json={'text':'Venture'}).status_code==200
        assert client.post('/api/market/hubs',json={}).status_code==403
        env.db.add(UserSectionPermission(user_id=env.users['quartermaster'].id,section='market',can_view=False));env.db.commit()
        assert client.post('/api/market/appraise',json={'text':'Venture'}).status_code==403


def test_migration_upgrade_and_downgrade():
    file=Path(__file__).parents[1]/'alembic/versions/0090_local_scan_reports.py'
    spec=importlib.util.spec_from_file_location('local_scan_migration',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY)')
        module.op=Operations(MigrationContext.configure(connection));module.upgrade()
        assert {'local_scan_reports','scan_highlights'}<=set(inspect(connection).get_table_names())
        module.downgrade();assert inspect(connection).get_table_names()==['users']


def test_refresh_downscopes_legacy_utility_token(env):
    import httpx
    token=env.db.scalar(select(EsiToken).where(EsiToken.user_id==env.users['intel_analyst'].id))
    response=httpx.Response(200,json={'access_token':'synthetic-access','expires_in':1200})
    client=SimpleNamespace(post=AsyncMock(return_value=response))
    context=AsyncMock();context.__aenter__.return_value=client
    with patch.object(esi,'decrypt_secret',return_value='not-a-live-refresh'),patch.object(esi.httpx,'AsyncClient',return_value=context):
        assert asyncio.run(esi.refresh_access_token(token))=='synthetic-access'
    data=client.post.call_args.kwargs['data']
    assert set(data['scope'].split())=={'esi-ui.write_waypoint.v1','esi-universe.read_structures.v1'}
    assert 'esi-assets.read_assets.v1' not in data['scope']


def test_custom_navigation_only_role_does_not_request_private_data(env):
    from app.services.permissions import SECTION_DEFINITIONS
    env.db.add(RoleDefinition(name='front_guest',display_name='Front guest',base_role='member'))
    user=env.users['other'];user.role='front_guest'
    for section in SECTION_DEFINITIONS:
        if section not in {'navigation','market','profile','overview'}:
            env.db.add(UserSectionPermission(user_id=user.id,section=section,can_view=False))
    env.db.commit()
    assert requested_scopes(env.db,user,esi.PUBLIC_SCOPES,'full')==['publicData']
    assert not private_collection_enabled(env.db,user)


def test_maximum_scan_pdf_paginates_without_losing_pilots(env):
    from pypdf import PdfReader
    from app.services.local_scan_pdf import render_pdf
    report=create(env)
    seed=report['pilots']
    report['pilots']=[{**seed[i%3],'name':f'Example Pilot {i:04d}','character_id':100000+i} for i in range(2000)]
    report['character_count']=2000;report['input_count']=2000
    pdf=PdfReader(BytesIO(render_pdf(report,{})))
    assert 1 < len(pdf.pages) < 30
    for page in pdf.pages:
        assert 'Total pilots: 2,000' in page.extract_text()
        assert 'System: Not specified' in page.extract_text()
    text='\n'.join(page.extract_text() for page in pdf.pages)
    for i in range(2000):assert f'Example Pilot {i:04d}' in text


def test_pdf_rechecks_expiry_after_rendering(env):
    report=create(env)
    async def expire(snapshot):
        env.db.get(LocalScanReport,report['token']).expires_at=service.now()-timedelta(seconds=1)
        env.db.commit();return {}
    with patch('app.services.local_scan_pdf.logo_images',new=expire):
        response=env.client.get('/api/local-scans/public/'+report['token']+'/pdf')
    assert response.status_code==404 and response.headers['cache-control']=='no-store'
