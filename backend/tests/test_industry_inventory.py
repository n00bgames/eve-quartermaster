"""Public industry minimization and private inventory regressions."""
from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import json
import pytest
from pypdf import PdfReader
from sqlalchemy import select
from app.api import industry_reports, inventory_reports
from app.models import (Asset,Blueprint,EveCategory,EveGroup,EveType,EveCharacter,OwnershipEntity,
    Location,ResearchProject,PlanetaryColony,PlanetaryPin,UserSectionPermission)
from app.models.enums import OwnerKind,LocationKind
from app.models.local_scan import LocalScanReport
from app.services import industry_reports as service,local_scan as lifecycle
from app.services.industry_storage import StorageIndex
from tests.test_local_scan import env


@pytest.fixture
def stock(env):
    db=env.db;user=env.users['member']
    char=db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==user.id));user.main_character_id=char.character_id
    categories={i:EveCategory(category_id=i,name=n) for i,n in [(4,'Material'),(6,'Ship'),(7,'Module'),(8,'Charge'),(9,'Blueprint'),(18,'Drone'),(23,'Deployable'),(43,'Planetary Commodities')]}
    db.add_all(categories.values());db.flush()
    groups={n:EveGroup(group_id=i,name=n,category_id=c) for i,n,c in [(18,'Mineral',4),(27,'Battleship',6),(53,'Energy Weapon',7),(85,'Hybrid Charge',8),(2,'Blueprint',9),(1888,'Composite Reaction Formulas',9),(100,'Combat Drone',18),(12,'Cargo Container',23),(1040,'Planetary Commodities',43)]}
    db.add_all(groups.values())
    types={n:EveType(type_id=i,name=n,group=groups[g]) for i,n,g in [(34,'Tritanium','Mineral'),(638,'Raven','Battleship'),(1000,'Private Laser','Energy Weapon'),(1001,'Antimatter Charge','Hybrid Charge'),(1002,'Private Drone','Combat Drone'),(1003,'Station Container','Cargo Container'),(1004,'Raven Blueprint','Blueprint'),(1005,'Composite Reaction Formula','Composite Reaction Formulas'),(3689,'Mechanical Parts','Planetary Commodities')]}
    db.add_all(types.values())
    owner=OwnershipEntity(owner_kind=OwnerKind.CHARACTER,character_id=char.id,display_name=char.name);db.add(owner)
    other_char=db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==env.users['other'].id))
    other=OwnershipEntity(owner_kind=OwnerKind.CHARACTER,character_id=other_char.id,display_name=other_char.name);db.add(other)
    station=Location(name='Jita IV - NPC station',location_kind=LocationKind.STATION)
    upwell=Location(name='Example Industrial Citadel',location_kind=LocationKind.STRUCTURE)
    unknown=Location(name='Unresolved',location_kind=LocationKind.UNKNOWN)
    db.add_all([station,upwell,unknown]);db.flush()
    assets={}
    def add(key,tid,qty=1,parent=None,loc=station,flag='Hangar',who=owner):
        a=Asset(ownership_entity_id=who.id,type_id=tid,quantity=qty,location_id=loc.id if loc else None,
            location_flag=flag,parent_asset_id=parent.id if parent else None,last_synced_at=lifecycle.now())
        db.add(a);db.flush();assets[key]=a;return a
    add('mineral',34,100)
    ship=add('ship',638);add('fit',1000,2,ship,None,'HiSlot0');add('cargo',34,999,ship,None,'Cargo')
    add('loose_module',1000,3);add('loose_ammo',1001,10);add('loose_drone',1002,4)
    can=add('can',1003);add('can_ammo',1001,40,can,None,'Unlocked');add('can_module',1000,5,can,None,'Unlocked')
    nested=add('nested',1003,1,can,None,'Unlocked');add('nested_drone',1002,20,nested,None,'Unlocked')
    carried=add('carried_can',1003,1,ship,None,'Cargo');add('carried_ammo',1001,400,carried,None,'Unlocked')
    add('foreign',1001,1000,who=other)
    add('unresolved_mineral',34,888,loc=unknown)
    add('upwell_mineral',34,200,loc=upwell)
    add('pi_stock',3689,80)
    formula=add('formula',1005,2)
    bp=add('bp_asset',1004)
    db.add(Blueprint(asset_id=bp.id,ownership_entity_id=owner.id,blueprint_type_id=1004,is_copy=False,last_synced_at=lifecycle.now()))
    db.add(Blueprint(ownership_entity_id=owner.id,blueprint_type_id=1004,is_copy=True,runs_remaining=3,last_synced_at=lifecycle.now()))
    db.add(ResearchProject(job_id=73001,character_id=char.id,installer_name=char.name,installer_character_id=char.character_id,
        source_type='character',activity_id=1,status='active',runs=2,product_type_id=638,blueprint_type_id=1004,facility_name=upwell.name,last_synced_at=lifecycle.now()))
    colony=PlanetaryColony(character_id=char.id,planet_id=4001,planet_name='Jita IV',last_synced_at=lifecycle.now());db.add(colony);db.flush()
    db.add(PlanetaryPin(colony_id=colony.id,pin_id=78652,type_id=3689,contents_json=[{'type_id':3689,'amount':20}]))
    db.commit()
    env.app.include_router(industry_reports.router,prefix='/api');env.app.include_router(inventory_reports.router,prefix='/api')
    scope={'stock':[owner.id],'blueprint_characters':[char.id],'blueprint_corporations':[],'job_characters':[char.id],'job_corporations':[],'pi':[char.id]}
    grants=SimpleNamespace(characters={'blueprints':{char.id},'jobs':{char.id},'planets':{char.id}},corporations={'blueprints':set(),'jobs':set()})
    with patch.object(service,'oversight_scope',new=AsyncMock(return_value=grants)):
        yield SimpleNamespace(env=env,db=db,char=char,owner=owner,other=other,assets=assets,station=station,upwell=upwell,scope=scope)


def create(stock,path='/industry-reports',**payload):
    response=stock.env.client.post('/api'+path,json=payload)
    assert response.status_code==201,response.text
    return response.json()


def quantities(report):return {r['item']:r['quantity'] for r in report['totals']}


def test_industry_default_has_only_materials_pi_blueprints_reactions_jobs(stock):
    data=create(stock)
    assert data['is_private'] and stock.char.name in str(data)
    assert quantities(data)=={'Tritanium':300,'Mechanical Parts':100}
    assert data['summary']['bpos']==1 and data['summary']['bpcs']==1 and data['summary']['reaction_formulas']==2
    assert len(data['jobs'])==1 and len(data['pi'])==1
    assert all('Private' not in row['item'] and 'Container' not in row['item'] for row in data['stock'])


def test_selected_hangar_direct_items_does_not_include_nested_or_ship_contents(stock):
    index=StorageIndex(stock.db,stock.scope['stock'])
    data=create(stock,storage=[index.key(stock.assets['ship'])])
    assert quantities(data)['Raven']==1
    assert quantities(data)['Private Laser']==3
    assert quantities(data)['Antimatter Charge']==10
    assert quantities(data)['Private Drone']==4
    assert quantities(data)['Tritanium']==300
    assert 'Station Container' not in quantities(data)


def test_selecting_exact_container_only_adds_its_direct_stock(stock):
    index=StorageIndex(stock.db,stock.scope['stock'])
    data=create(stock,storage=[index.key(stock.assets['can'],True)])
    assert quantities(data)['Private Laser']==5 and quantities(data)['Antimatter Charge']==40
    assert 'Private Drone' not in quantities(data) and 'Station Container' not in quantities(data)


def test_foreign_ship_unresolved_and_forged_storage_denied(stock):
    e=stock.env
    options=e.client.get('/api/industry-reports/storage').json()['storage']
    assert not any(str(stock.assets['carried_can'].id)==o['key'].rsplit(':',1)[-1] for o in options if o['kind']=='container')
    assert all(o['owner']==stock.char.name for o in options)
    for key in ['c:999:999:999',f'c:{stock.owner.id}:{stock.station.id}:{stock.assets["ship"].id}']:
        assert e.client.post('/api/industry-reports',json={'storage':[key]}).status_code==422
    assert e.client.post('/api/industry-reports',json={'storage':['x'*101]}).status_code==422


def test_public_json_csv_pdf_hide_creator_owner_identifiers_but_show_structure_names(stock):
    data=create(stock,is_private=False,anonymous=False)
    assert data['anonymous'] and data['account_name']=='Anonymous'
    token=data['token'];stock.env.current[0]=None
    for suffix in ['', '/export/csv','/export/pdf']:
        response=stock.env.client.get('/api/industry-reports/public/'+token+suffix)
        assert response.status_code==200,response.text
        text=''.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages) if suffix.endswith('pdf') else response.text
        for secret in [stock.char.name,'73001','78652','owner_user_id','_scope','_storage']:
            assert secret not in text
        assert 'Character Owned' in text
        assert 'Private Laser' not in text and 'Antimatter Charge' not in text
        assert response.headers['cache-control']=='no-store'


def test_private_industry_keeps_character_names_but_no_general_personal_inventory(stock):
    data=create(stock)
    assert data['account_name']==stock.char.name
    assert all(row['owner']==stock.char.name for row in data['stock'])
    assert 'Private Laser' not in quantities(data)
    assert stock.env.client.get('/api/industry-reports/public/'+data['token']).status_code==404


def test_legacy_public_link_sanitizes_names_totals_and_unapproved_stock(stock):
    data=create(stock,is_private=False);row=stock.db.get(LocalScanReport,data['token'])
    old=dict(row.payload);old.pop('policy_version');old['stock'].append({'owner':stock.char.name,'item':'Hidden fit','quantity':10000,'category':'Other assets','type_id':1000,'location':'SECRET_CAN','source':'Assets'})
    old['extra_private_field']=stock.char.name;row.payload=old;row.anonymous=False;stock.db.commit()
    response=stock.env.client.get('/api/industry-reports/public/'+row.token)
    assert response.status_code==200
    got=response.json();assert got['stock']==[] and got['totals']==[] and got['summary']['stock_units']==0
    assert stock.char.name not in response.text and 'SECRET_CAN' not in response.text and 'extra_private_field' not in response.text
    assert 'Legacy stock omitted' in got['notice'] and got['blueprints'] and got['jobs'] and got['pi']
    listing=stock.env.client.get('/api/industry-reports/reports').json();assert stock.char.name not in str(listing)


def test_dynamic_frozen_storage_updates_but_moving_can_into_ship_disables_link(stock):
    index=StorageIndex(stock.db,stock.scope['stock'])
    data=create(stock,is_private=False,dynamic=True,storage=[index.key(stock.assets['can'],True)])
    stock.assets['can_ammo'].quantity=60;stock.db.commit()
    got=stock.env.client.get('/api/industry-reports/public/'+data['token']);assert quantities(got.json())['Antimatter Charge']==60
    stock.assets['can'].parent_asset_id=stock.assets['ship'].id;stock.assets['can'].location_id=None;stock.assets['can'].location_flag='Cargo';stock.db.commit()
    for suffix in ('','/export/csv','/export/pdf'):
        assert stock.env.client.get('/api/industry-reports/public/'+data['token']+suffix).status_code==404


def test_cycle_or_cross_owner_ancestors_fail_closed(stock):
    stock.assets['can'].parent_asset_id=stock.assets['nested'].id;stock.assets['can'].location_id=None
    stock.assets['loose_module'].parent_asset_id=stock.assets['foreign'].id;stock.assets['loose_module'].location_id=None;stock.db.commit()
    index=StorageIndex(stock.db,stock.scope['stock'])
    assert index.placement(stock.assets['can']) is None and index.placement(stock.assets['nested']) is None
    assert index.placement(stock.assets['loose_module']) is None


def test_inventory_includes_fittings_personal_stock_names_and_private_exports(stock):
    data=create(stock,'/inventory-reports')
    assert data['report_kind']=='inventory' and data['share_url'] is None and data['is_private']
    assert quantities(data)['Private Laser']==10 and quantities(data)['Antimatter Charge']==450
    assert quantities(data)['Station Container']==3 and quantities(data)['Tritanium']==2187
    assert quantities(data)['Private Drone']==24
    assert stock.char.name in str(data) and 'HiSlot0' in str(data)
    assert all(row['owner']==stock.char.name for row in data['stock'])
    for fmt in ('csv','pdf'):
        response=stock.env.client.get(f'/api/inventory-reports/reports/{data["token"]}/export/{fmt}')
        assert response.status_code==200
        text=''.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages) if fmt=='pdf' else response.text
        assert stock.char.name in text and 'Private Laser' in text
        if fmt=='pdf':assert 'Inventory Report' in text


def test_inventory_no_public_generation_or_cross_kind_access(stock):
    data=create(stock,'/inventory-reports');token=data['token']
    assert stock.env.client.post('/api/inventory-reports',json={'is_private':False}).status_code==422
    for kind in ('inventory-reports','industry-reports','local-scans','d-scans'):
        for suffix in ('','/export/pdf','/export/csv'):
            assert stock.env.client.get(f'/api/{kind}/public/{token}{suffix}').status_code==404
    assert stock.env.client.get('/api/industry-reports/reports/'+token).status_code==404


def test_inventory_creator_only_listing_read_export_delete_even_for_admin(stock):
    data=create(stock,'/inventory-reports');token=data['token']
    for role in ('other','director','admin'):
        stock.env.current[0]=stock.env.users[role]
        assert stock.env.client.get('/api/inventory-reports/reports').json()['total']==0
        assert stock.env.client.get('/api/inventory-reports/reports/'+token).status_code==404
        assert stock.env.client.get('/api/inventory-reports/reports/'+token+'/export/pdf').status_code==404
        assert stock.env.client.post('/api/inventory-reports/reports/delete',json={'tokens':[token]}).json()['deleted']==0
    stock.env.current[0]=None
    assert stock.env.client.get('/api/inventory-reports/reports').status_code==401


def test_inventory_requires_assets_permission_and_expiry_deletion_work(stock):
    data=create(stock,'/inventory-reports');token=data['token']
    stock.env.current[0]=stock.env.users['quartermaster'];assert stock.env.client.get('/api/inventory-reports/context').status_code==403
    stock.env.current[0]=stock.env.users['member']
    permission=UserSectionPermission(user_id=stock.env.users['member'].id,section='assets',can_view=False);stock.db.add(permission);stock.db.commit()
    assert stock.env.client.get('/api/inventory-reports/reports/'+token).status_code==403
    stock.db.delete(permission);stock.db.commit()
    row=stock.db.get(LocalScanReport,token);row.expires_at=lifecycle.now()-timedelta(seconds=1);stock.db.commit()
    assert stock.env.client.get('/api/inventory-reports/reports/'+token).status_code==404
    data=create(stock,'/inventory-reports')
    assert stock.env.client.post('/api/inventory-reports/reports/delete',json={'all_in_scope':True}).json()['deleted']==2
    assert stock.env.client.get('/api/inventory-reports/reports/'+data['token']).status_code==404


def test_upwell_corporation_hangar_selection_and_generic_public_ownership(stock):
    from app.models import CorporationDivision
    stock.env.current[0]=stock.env.users['admin']
    corp=stock.char.corporation
    owner=OwnershipEntity(owner_kind=OwnerKind.CORPORATION,corporation_id=corp.id,display_name=corp.name)
    stock.db.add(owner);stock.db.flush()
    stock.db.add(CorporationDivision(corporation_id=corp.id,division_type='hangar',division=2,name='Approved ammunition'))
    asset=Asset(ownership_entity_id=owner.id,type_id=1001,quantity=250,location_id=stock.upwell.id,location_flag='CorpSAG2')
    stock.db.add(asset);stock.db.commit()
    options=stock.env.client.get('/api/industry-reports/storage').json()['storage']
    option=next(o for o in options if o['name']=='Approved ammunition (CorpSAG2)')
    report=create(stock,is_private=False,storage=[option['key']])
    assert quantities(report)['Antimatter Charge']==250
    row=next(r for r in report['stock'] if r['item']=='Antimatter Charge')
    assert row['owner']=='Corporation Owned' and row['location']==stock.upwell.name
    assert corp.name not in str(report) and stock.char.name not in str(report)


def test_inventory_date_deletion_is_own_and_kind_scoped(stock):
    inventory=create(stock,'/inventory-reports');industry=create(stock)
    inventory_row=stock.db.get(LocalScanReport,inventory['token'])
    start=lifecycle.now()-timedelta(hours=1);end=lifecycle.now()+timedelta(hours=1)
    deleted=stock.env.client.post('/api/inventory-reports/reports/delete',json={'from_at':start.isoformat(),'to_at':end.isoformat()})
    assert deleted.json()['deleted']==1
    assert stock.env.client.get('/api/industry-reports/reports/'+industry['token']).status_code==200
    assert stock.env.client.get('/api/inventory-reports/reports/'+inventory['token']).status_code==404


@pytest.fixture
def office_stock(stock):
    db=stock.db
    owner=OwnershipEntity(owner_kind=OwnerKind.CORPORATION,corporation_id=stock.char.corporation_id,display_name='Demo corporation')
    group=EveGroup(group_id=16,name='Station Services',category_id=23)
    db.add_all([owner,group]);db.flush()
    db.add(EveType(type_id=27,name='Office',group=group));db.flush()
    office=Asset(ownership_entity_id=owner.id,type_id=27,location_id=stock.station.id,location_flag='OfficeFolder')
    db.add(office);db.flush()
    can=Asset(ownership_entity_id=owner.id,type_id=1003,parent_asset_id=office.id,location_flag='CorpSAG7')
    ammo=Asset(ownership_entity_id=owner.id,type_id=1001,quantity=20,parent_asset_id=office.id,location_flag='CorpSAG7')
    mineral=Asset(ownership_entity_id=owner.id,type_id=34,quantity=123,parent_asset_id=office.id,location_flag='CorpSAG7')
    db.add_all([can,ammo,mineral]);db.flush()
    nested=Asset(ownership_entity_id=owner.id,type_id=1001,quantity=30,parent_asset_id=can.id,location_flag='Unlocked')
    db.add(nested);db.commit()
    scope={**stock.scope,'stock':[owner.id],'blueprint_characters':[],'blueprint_corporations':[stock.char.corporation_id]}
    return SimpleNamespace(stock=stock,db=db,owner=owner,office=office,can=can,ammo=ammo,mineral=mineral,nested=nested,scope=scope)


def test_corporate_office_hangars_and_nested_stock(office_stock):
    o=office_stock
    for location in (o.stock.station,o.stock.upwell):
        o.office.location_id=location.id;o.db.commit()
        idx=StorageIndex(o.db,[o.owner.id]);options=idx.options([o.owner.id])
        hangar=next(x['key'] for x in options if x['kind']=='hangar')
        can=next(x['key'] for x in options if x['kind']=='container')
        assert hangar.endswith(':CorpSAG7')
        assert quantities(service.build(o.db,o.scope))=={'Tritanium':123,'Mechanical Parts':20}
        assert quantities(service.build(o.db,o.scope,[hangar]))['Antimatter Charge']==20
        assert quantities(service.build(o.db,o.scope,[can]))['Antimatter Charge']==30
        assert idx.placement(o.office) is None
        public=service.present(service.build(o.db,o.scope,[hangar]),public=True)
        assert o.stock.char.name not in str(public)


def test_office_blueprints_above_2500_and_dynamic_existing_link(office_stock):
    o=office_stock
    assets=[Asset(ownership_entity_id=o.owner.id,type_id=1004,parent_asset_id=o.can.id,location_flag='Unlocked') for _ in range(2501)]
    o.db.add_all(assets);o.db.flush()
    o.db.add_all([Blueprint(asset_id=a.id,ownership_entity_id=o.owner.id,blueprint_type_id=1004,is_copy=False) for a in assets]);o.db.commit()
    data=create(o.stock,is_private=False,dynamic=True)
    saved=o.db.get(LocalScanReport,data['token']);saved.payload={**saved.payload,'_scope':o.scope};o.db.commit()
    with patch.object(service,'permitted_scope',new=AsyncMock(return_value=o.scope)):
        response=o.stock.env.client.get('/api/industry-reports/public/'+data['token'])
        assert response.status_code==200,response.text
        result=response.json();assert len(result['blueprints'])==2501 and result['summary']['bpos']==2501
        csv=o.stock.env.client.get('/api/industry-reports/public/'+data['token']+'/export/csv')
        assert csv.status_code==200 and csv.text.split('BLUEPRINTS',1)[1].split('TOTALS',1)[0].count('Raven Blueprint')==2501


@pytest.mark.parametrize('invalid',['foreign_owner','inside_ship','wrong_type','wrong_group','wrong_office_flag','wrong_child_flag','unknown_location'])
def test_office_resolution_keeps_storage_boundary(office_stock,invalid):
    o=office_stock
    if invalid=='foreign_owner':o.office.ownership_entity_id=o.stock.other.id
    elif invalid=='inside_ship':o.office.parent_asset_id=o.stock.assets['ship'].id
    elif invalid=='wrong_type':o.office.type_id=638
    elif invalid=='wrong_group':o.db.get(EveType,27).group_id=27
    elif invalid=='wrong_office_flag':o.office.location_flag='Cargo'
    elif invalid=='wrong_child_flag':o.can.location_flag='Cargo'
    else:o.office.location_id=o.db.scalar(select(Location).where(Location.location_kind==LocationKind.UNKNOWN)).id
    o.db.commit();idx=StorageIndex(o.db,[o.owner.id,o.stock.other.id])
    assert idx.placement(o.can) is None and idx.placement(o.nested) is None


def test_station_corporation_deliveries_are_storage_not_ship_cargo(office_stock):
    o=office_stock
    o.ammo.parent_asset_id=None;o.ammo.location_id=o.stock.station.id;o.ammo.location_flag='CorpDeliveries';o.db.commit()
    idx=StorageIndex(o.db,[o.owner.id]);key=idx.key(o.ammo)
    assert key and key.endswith(':CorpDeliveries')
    assert quantities(service.build(o.db,o.scope,[key]))['Antimatter Charge']==20
    o.ammo.parent_asset_id=o.stock.assets['ship'].id;o.db.commit()
    assert StorageIndex(o.db,[o.owner.id,o.stock.owner.id]).placement(o.ammo) is None


def test_industry_exports_jobs_first_and_inventory_still_totals_first(stock):
    data=create(stock)
    csv=service.csv_content(data)
    order=['JOBS','BLUEPRINTS','TOTALS','STOCK','PI']
    assert [csv.index('\r\n'+name+'\r\n') for name in order]==sorted(csv.index('\r\n'+name+'\r\n') for name in order)
    pdf=''.join(page.extract_text() for page in PdfReader(BytesIO(service.pdf_content(data))).pages)
    headings=['Active industry jobs','Blueprints and reaction formulas','Overall stock totals','Stock by ownership','Planetary infrastructure']
    assert [pdf.index(name) for name in headings]==sorted(pdf.index(name) for name in headings)
    inventory=create(stock,'/inventory-reports')
    csv=service.csv_content(inventory)
    assert csv.index('TOTALS')<csv.index('STOCK') and '\r\nJOBS\r\n' not in csv


def test_structure_names_and_latest_cached_facility_name_in_reports_and_exports(stock):
    from app.models import ResearchProject
    stock.upwell.name=stock.char.name+" Industrial Citadel"
    stock.upwell.eve_location_id=1000000000099
    job=stock.db.scalar(select(ResearchProject));job.facility_id=stock.upwell.eve_location_id;job.facility_name='Structure 1000000000099'
    # Blueprint location may still point to a can; resolve the verified station root.
    can=stock.assets['can'];can.location_id=stock.upwell.id
    bp=stock.db.scalar(select(Blueprint).where(Blueprint.asset_id==stock.assets['bp_asset'].id))
    bp.asset.parent_asset_id=can.id;bp.asset.location_id=None;bp.asset.location_flag='Unlocked';bp.location_id=stock.station.id
    stock.db.commit()
    data=create(stock,is_private=False,dynamic=True)
    assert data['account_name']=='Anonymous'
    assert all(x['owner']=='Character Owned' for key in ('stock','blueprints','jobs','pi') for x in data[key])
    assert data['jobs'][0]['facility']==stock.upwell.name
    assert next(b for b in data['blueprints'] if b['kind']=='BPO')['location']==stock.upwell.name
    for fmt in ('csv','pdf'):
        result=stock.env.client.get('/api/industry-reports/public/'+data['token']+'/export/'+fmt)
        assert result.status_code==200
        content=''.join(p.extract_text() for p in PdfReader(BytesIO(result.content)).pages) if fmt=='pdf' else result.text
        assert stock.upwell.name in ' '.join(content.split())
    stock.upwell.name='Renamed Upwell';stock.db.commit()
    refreshed=stock.env.client.get('/api/industry-reports/public/'+data['token']).json()
    assert refreshed['jobs'][0]['facility']=='Renamed Upwell'
    assert next(b for b in refreshed['blueprints'] if b['kind']=='BPO')['location']=='Renamed Upwell'
