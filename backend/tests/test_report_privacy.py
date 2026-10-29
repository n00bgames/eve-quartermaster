"""Authorization and data-disclosure regressions for report identity/sharing."""
from datetime import timedelta
from io import BytesIO
from unittest.mock import AsyncMock,patch
import importlib.util
from pathlib import Path
from fastapi import HTTPException,Response
from sqlalchemy import select,create_engine,text,inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.models import Asset,EveCharacter,OwnershipEntity,EveType,EveGroup,EveCategory,EsiToken,UserSectionPermission,BattleReportShare
from app.models.enums import OwnerKind,LocationKind
from app.models import Location
from app.models.local_scan import LocalScanReport
from app.api import auth,industry_reports,battle_reports
from app.services import local_scan as lifecycle
from app.services.scan_threat import order_snapshot
from app.services.report_identity import report_identity
from tests.test_local_scan import env,create
from tests.test_dscan import scan_env,generate

def install_auth(env):env.app.include_router(auth.router,prefix='/api')
def main(env):
    user=env.users['member'];char=env.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==user.id))
    user.main_character_id=char.character_id;env.db.commit();return char

def test_profile_main_is_owned_and_linked_only(env):
    install_auth(env)
    chars=env.client.get('/api/auth/me/characters').json()['characters']
    own=chars[0]['character_id'];foreign=env.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==env.users['other'].id)).character_id
    assert env.client.put('/api/auth/me/main-character',json={'main_character_id':foreign}).status_code==422
    assert env.client.put('/api/auth/me/main-character',json={'main_character_id':True}).status_code==422
    assert env.client.put('/api/auth/me/main-character',json={'main_character_id':own,'role':'host'}).status_code==422
    assert env.client.put('/api/auth/me/main-character',json={'main_character_id':own}).json()['main_character_id']==own
    assert env.client.put('/api/auth/me/main-character',json={'main_character_id':None}).status_code==200

def test_old_and_new_named_reports_follow_main_without_account_fallback(env):
    report=create(env)
    assert report['account_name']=='Anonymous'
    row=env.db.get(LocalScanReport,report['token']);row.account_name='Secret account login';env.db.commit()
    char=main(env)
    got=env.client.get('/api/local-scans/public/'+row.token).json()
    assert got['account_name']==char.name and 'Secret account login' not in str(got) and 'Member' not in str(got)
    token=env.db.scalar(select(EsiToken).where(EsiToken.user_id==env.users['member'].id));token.revoked_at=lifecycle.now();env.db.commit()
    assert env.client.get('/api/local-scans/public/'+row.token).json()['account_name']=='Anonymous'

def test_explicit_anonymous_stays_anonymous(env):
    main(env);report=create(env,anonymous=True,corporation_id=101)
    assert report['anonymous'] and report['account_name']=='Anonymous'
    assert report['corporation_id'] is None
    assert env.client.get('/api/local-scans/public/'+report['token']).json()['account_name']=='Anonymous'

def test_private_scan_public_routes_reject_even_creator_and_private_exports_authenticate(env):
    main(env);report=create(env,is_private=True)
    token=report['token'];assert report['share_url'] is None and report['is_private']
    for suffix in ('','/pdf'):assert env.client.get('/api/local-scans/public/'+token+suffix).status_code==404
    assert env.client.get('/api/local-scans/reports/'+token).status_code==200
    with patch('app.services.local_scan_pdf.logo_images',new=AsyncMock(return_value={})):
        pdf=env.client.get('/api/local-scans/reports/'+token+'/pdf')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    for role in ('other','director','admin'):
        env.current[0]=env.users[role]
        assert env.client.get('/api/local-scans/reports/'+token).status_code==404
        assert env.client.get('/api/local-scans/reports/'+token+'/pdf').status_code==404
        assert token not in str(env.client.get('/api/local-scans/reports').json())
    env.current[0]=None
    assert env.client.get('/api/local-scans/reports/'+token).status_code==401

def test_private_dscan_kind_isolation_and_export(scan_env):
    report=generate(scan_env,is_private=True,anonymous=True);token=report['token']
    assert report['share_url'] is None
    for suffix in ('','/pdf'):assert scan_env.client.get('/api/d-scans/public/'+token+suffix).status_code==404
    assert scan_env.client.get('/api/d-scans/reports/'+token).status_code==200
    assert scan_env.client.get('/api/local-scans/reports/'+token).status_code==404
    with patch('app.services.dscan_pdf.report_images',new=AsyncMock(return_value={})):
        assert scan_env.client.get('/api/d-scans/reports/'+token+'/pdf').status_code==200

def test_threat_sort_handles_old_payload_and_faction_battleships():
    names=[('Rifter','Frigate',99),('Raven','Battleship',8),('Raven Navy Issue','Battleship',1),('Redeemer','Black Ops',2),('Golem','Marauder',2),('Archon','Carrier',1),('Command hull','Command Carrier',1),('Revelation','Dreadnought',1),('Bane','Lancer Dreadnought',1),('Nyx','Supercarrier',1),('Avatar','Titan',1)]
    old={'rows':[{'type_name':n,'group_name':g,'count':c,'category':'ships','type_id':i} for i,(n,g,c) in enumerate(names)],'classes':[]}
    ordered=order_snapshot(old)
    assert [r['type_name'] for r in ordered['rows']]==[n for n,_,_ in reversed(names)]
    assert [r['name'] for r in ordered['classes']][:4]==['Titan','Supercarrier','Lancer Dreadnought','Dreadnought']
    assert old['rows'][0]['type_name']=='Rifter' # No mutation of immutable snapshots.

def seed_stock(env):
    char=main(env);cat=EveCategory(category_id=4,name='Material');group=EveGroup(group_id=18,name='Mineral',category=cat)
    item=EveType(type_id=34,name='Tritanium',group=group);owner=OwnershipEntity(owner_kind=OwnerKind.CHARACTER,character_id=char.id,display_name='Stock owner')
    env.db.add_all([cat,group,item,owner]);env.db.flush();location=Location(name='Example NPC station',location_kind=LocationKind.STATION);env.db.add(location);env.db.flush();asset=Asset(location_id=location.id,location_flag='Hangar',ownership_entity_id=owner.id,type_id=34,quantity=100,last_synced_at=lifecycle.now());env.db.add(asset);env.db.commit()
    env.app.include_router(industry_reports.router,prefix='/api');return asset

def test_industry_private_default_csv_pdf_and_no_scope_leak(env):
    seed_stock(env)
    report=env.client.post('/api/industry-reports',json={}).json();token=report['token']
    assert report['is_private'] and report['share_url'] is None
    assert report['totals'][0]['quantity']==100 and '_scope' not in str(report)
    assert env.client.get('/api/industry-reports/public/'+token).status_code==404
    csv=env.client.get('/api/industry-reports/reports/'+token+'/export/csv');assert csv.status_code==200 and 'Tritanium' in csv.text
    pdf=env.client.get('/api/industry-reports/reports/'+token+'/export/pdf');assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    env.current[0]=env.users['other'];assert env.client.get('/api/industry-reports/reports/'+token).status_code==404

def test_dynamic_industry_updates_snapshot_does_not_and_revoke_denies(env):
    asset=seed_stock(env)
    dynamic=env.client.post('/api/industry-reports',json={'is_private':False,'dynamic':True}).json()
    snapshot=env.client.post('/api/industry-reports',json={'is_private':False}).json()
    asset.quantity=240;env.db.commit();env.current[0]=None
    assert env.client.get('/api/industry-reports/public/'+dynamic['token']).json()['totals'][0]['quantity']==240
    assert env.client.get('/api/industry-reports/public/'+snapshot['token']).json()['totals'][0]['quantity']==100
    env.current[0]=env.users['member']
    env.db.add(UserSectionPermission(user_id=env.users['member'].id,section='assets',can_view=False));env.db.commit()
    assert env.client.get('/api/industry-reports/public/'+dynamic['token']).status_code==404

def test_dynamic_industry_does_not_add_new_owners_and_expiry_delete_work(env):
    seed_stock(env);report=env.client.post('/api/industry-reports',json={'is_private':False,'dynamic':True}).json();token=report['token']
    char=main(env);owner=OwnershipEntity(owner_kind=OwnerKind.CHARACTER,character_id=char.id,display_name='New owner');env.db.add(owner);env.db.flush();env.db.add(Asset(ownership_entity_id=owner.id,type_id=34,quantity=900));env.db.commit()
    assert env.client.get('/api/industry-reports/public/'+token).json()['totals'][0]['quantity']==100
    row=env.db.get(LocalScanReport,token);row.expires_at=lifecycle.now()-timedelta(seconds=1);env.db.commit()
    for suffix in ('','/export/csv','/export/pdf'):assert env.client.get('/api/industry-reports/public/'+token+suffix).status_code==404
    report=env.client.post('/api/industry-reports',json={'is_private':False}).json()
    assert env.client.post('/api/industry-reports/reports/delete',json={'tokens':[report['token']]}).json()['deleted']==1
    assert env.client.get('/api/industry-reports/public/'+report['token']).status_code==404

def test_private_battle_route_and_expiry(env):
    env.app.include_router(battle_reports.router,prefix='/api');main(env)
    row=BattleReportShare(share_token='P'*43,created_by_user_id=env.users['member'].id,selected_character_id=9001,selected_character_name='Subject',is_private=True,report_payload={'pilot':{'name':'Subject'},'report':{}},creator_name='Secret account')
    env.db.add(row);env.db.commit()
    assert env.client.get('/api/battle-reports/public/'+row.share_token).status_code==404
    got=env.client.get('/api/battle-reports/shares/'+str(row.id));assert got.status_code==200 and got.json()['share']['creator_name']=='Linked member'
    env.current[0]=env.users['other'];assert env.client.get('/api/battle-reports/shares/'+str(row.id)).status_code==404
    row.is_private=False;row.expires_at=lifecycle.now()-timedelta(seconds=1);env.db.commit()
    assert env.client.get('/api/battle-reports/public/'+row.share_token).status_code==404


def test_main_selection_exception_does_not_unlock_other_quartermaster_writes(env):
    install_auth(env)
    from app.core.security import create_access_token
    from app.api.auth import get_current_user
    env.app.dependency_overrides.pop(get_current_user)
    user=env.users['quartermaster'];char=env.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==user.id))
    headers={'Authorization':'Bearer '+create_access_token(str(user.id))}
    assert env.client.put('/api/auth/me/main-character',json={'main_character_id':char.character_id},headers=headers).status_code==200
    assert env.client.patch('/api/auth/me',json={'role':'host'},headers=headers).status_code==403
    assert env.client.put('/api/auth/me/main-character',json={'main_character_id':char.character_id,'role':'host'},headers=headers).status_code==422

def test_privacy_migration_redacts_legacy_accounts_and_safe_downgrade():
    path=Path(__file__).resolve().parents[1]/'alembic/versions/0093_report_privacy.py'
    spec=importlib.util.spec_from_file_location('privacy_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE local_scan_reports (token TEXT PRIMARY KEY, account_name TEXT, report_kind TEXT)'))
        conn.execute(text('CREATE TABLE battle_report_shares (id INTEGER PRIMARY KEY)'))
        conn.execute(text("INSERT INTO local_scan_reports VALUES ('old','SECRET_LOGIN','local')"))
        with Operations.context(MigrationContext.configure(conn)):module.upgrade()
        assert conn.execute(text("SELECT account_name,anonymous,is_private,dynamic FROM local_scan_reports")).one()==('Anonymous',0,0,0)
        assert 'main_character_id' in {c['name'] for c in inspect(conn).get_columns('users')}
        conn.execute(text("INSERT INTO local_scan_reports (token,account_name,report_kind,is_private) VALUES ('private','Anonymous','local',true),('industry','Anonymous','industry',false)"))
        conn.execute(text('INSERT INTO battle_report_shares (id,is_private) VALUES (1,true),(2,false)'))
        with Operations.context(MigrationContext.configure(conn)):module.downgrade()
        assert conn.execute(text('SELECT token FROM local_scan_reports')).scalars().all()==['old']
        assert conn.execute(text('SELECT id FROM battle_report_shares')).scalars().all()==[2]

def test_battle_creation_privacy_pdf_and_retroactive_attribution(env):
    from tests.test_battle_reports import BattleReportTests
    from app.services.battle_reports import build_latest_battle_report
    from sqlalchemy.orm import Session
    fixture=BattleReportTests();fixture.setUp()
    with Session(fixture.engine) as db:
        from app.models import User
        data=build_latest_battle_report(db,db.scalar(select(User).where(User.email=='pilot@example.test')),character_id=90000001)
    env.app.include_router(battle_reports.router,prefix='/api');main(env)
    with patch.object(battle_reports,'build_latest_battle_report',return_value=data),patch.object(battle_reports,'killboard_settings',return_value={'enabled':True}):
        response=env.client.post('/api/battle-reports/shares',json={'character_id':90000001,'is_private':True,'anonymous':True,'retention':'1h'})
    assert response.status_code==201,response.text
    private=response.json();assert private['share_url'] is None and private['creator_name']=='Anonymous'
    assert env.client.get('/api/battle-reports/public/'+private['share_token']+'/pdf').status_code==404
    pdf=env.client.get('/api/battle-reports/shares/'+str(private['id'])+'/pdf')
    assert pdf.status_code==200
    from pypdf import PdfReader
    text_content=''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert 'by Anonymous' in text_content and 'Member' not in text_content
    assert 'Selected Pilot' in text_content
    row=env.db.get(BattleReportShare,private['id']);row.is_private=False;row.anonymous=False;env.db.commit()
    public=env.client.get('/api/battle-reports/public/'+row.share_token).json()
    assert public['share']['creator_name']=='Linked member'
    env.current[0]=env.users['other'];assert env.client.get('/api/battle-reports/shares/'+str(private['id'])+'/pdf').status_code==404
    fixture.tearDown()

def test_industry_totals_combine_inventory_and_pi_then_itemize(env):
    from app.models import PlanetaryColony,PlanetaryPin,Blueprint,ResearchProject
    from app.services.industry_reports import build,csv_content
    asset=seed_stock(env);char=main(env)
    owner=env.db.get(OwnershipEntity,asset.ownership_entity_id)
    pi_category=EveCategory(category_id=43,name='Planetary Commodities');pi_group=EveGroup(group_id=1040,name='Planetary Commodities',category=pi_category);env.db.add_all([pi_category,pi_group,EveType(type_id=3689,name='Mechanical Parts',group=pi_group)]);env.db.flush()
    env.db.add(Asset(location_id=asset.location_id,location_flag="Hangar",ownership_entity_id=owner.id,type_id=3689,quantity=80,last_synced_at=lifecycle.now()))
    colony=PlanetaryColony(character_id=char.id,planet_id=4001,planet_name='Example planet',last_synced_at=lifecycle.now());env.db.add(colony);env.db.flush()
    env.db.add(PlanetaryPin(colony_id=colony.id,pin_id=1,type_id=3689,contents_json=[{'type_id':3689,'amount':20}]))
    env.db.add(Blueprint(ownership_entity_id=owner.id,blueprint_type_id=34,is_copy=False,material_efficiency=10,time_efficiency=20,last_synced_at=lifecycle.now()))
    env.db.add(ResearchProject(job_id=17,character_id=char.id,source_type='character',activity_id=1,status='active',runs=5,last_synced_at=lifecycle.now()))
    env.db.commit()
    scope={'stock':[owner.id],'blueprint_characters':[char.id],'blueprint_corporations':[],'job_characters':[char.id],'job_corporations':[],'pi':[char.id]}
    data=build(env.db,scope)
    assert sum(r['quantity'] for r in data['totals'] if r['item']=='Mechanical Parts')==100
    assert len(data['stock'])==3 and len(data['blueprints'])==1 and len(data['jobs'])==1 and len(data['pi'])==1
    assert data['summary']['stock_units']==200
    assert any(r['category']=='PI' and r['item']=='Mechanical Parts' and r['quantity']==100 for r in data['totals'])
    env.db.add(ResearchProject(job_id=18,installer_character_id=char.character_id,installer_name=char.name,source_type='corporation',activity_id=1,status='active',runs=1,last_synced_at=lifecycle.now()));env.db.commit()
    assert len(build(env.db,scope)['jobs'])==2
    data.update(application_version='2.0.0',account_name='=FORMULA()',created_at=lifecycle.now().isoformat())
    data['stock'][0]['owner']='=HYPERLINK("bad")'
    assert "'=HYPERLINK" in csv_content(data)


def test_long_ship_table_starts_on_first_pdf_page(scan_env):
    from app.services.dscan_pdf import render_pdf
    from pypdf import PdfReader
    group=EveGroup(group_id=30100,name='Long synthetic combat ship classification',category_id=6)
    titan=EveGroup(group_id=30,name='Titan',category_id=6)
    scan_env.db.add_all([group,titan]);scan_env.db.flush()
    scan_env.db.add(EveType(type_id=671,name='Avatar',group=titan,mass=1000000000))
    for i in range(18):scan_env.db.add(EveType(type_id=800000+i,name=f'Example hull {i:02d}',group=group,mass=10000000))
    scan_env.db.commit()
    clipboard='671\tTitan\tAvatar\t1 AU\n'+'\n'.join(f'{800000+i}\tExample\tExample hull {i:02d}\t1 AU' for i in range(18))
    data=generate(scan_env,text=clipboard)
    reader=PdfReader(BytesIO(render_pdf(data,{})))
    assert 'Avatar' in reader.pages[0].extract_text()
    assert 'Ships' in reader.pages[0].extract_text()
