from datetime import timedelta
import json
from pathlib import Path
import pytest
from sqlalchemy import func,select
from app.api import matchups as api,auth
from app.models import EveCategory,EveGroup,EveType,EveDogmaAttribute,EveTypeDogmaAttribute,UserSectionPermission,RoleDefinition
from app.models.local_scan import LocalScanReport
from app.services import matchups
from app.services.matchup_knowledge import HULLS,SOURCES,COUNTERS,WEAPONS
from app.services.local_scan import now
from app.services.esi_scope_policy import requested_scopes,private_collection_enabled
from app.services.permissions import effective_permissions,assign_roles
from app.core.security import create_access_token
from .test_local_scan import env

@pytest.fixture
def matchup(env):
    e=env;e.app.include_router(api.router,prefix='/api')
    e.db.add_all([EveCategory(category_id=6,name='Ship'),EveCategory(category_id=7,name='Module')]);e.db.flush()
    e.db.add_all([EveGroup(group_id=26,category_id=6,name='Cruiser'),EveGroup(group_id=53,category_id=7,name='Lasers')]);e.db.flush()
    e.db.add_all([EveType(type_id=12023,name='Deimos',group_id=26),EveType(type_id=621,name='Caracal',group_id=26),EveType(type_id=111,name='Unknown Cruiser',group_id=26),EveType(type_id=112,name='Hidden Ship',group_id=26,published=False),EveType(type_id=113,name='Cruiser Module',group_id=53)]);e.db.flush()
    for i,(prefix,values) in enumerate([('shield',[1,.4,.15,.5]),('armor',[.5,.325,.1625,.9]),('',[.67,.67,.67,.67])]):
        for j,(suffix,value) in enumerate(zip(matchups.SUFFIX,values)):
            name=prefix+suffix+'DamageResonance' if prefix else matchups.DAMAGE[j]+'DamageResonance'
            attribute=EveDogmaAttribute(attribute_id=1000+i*4+j,name=name);e.db.add(attribute);e.db.flush()
            e.db.add(EveTypeDogmaAttribute(type_id=12023,attribute_id=attribute.attribute_id,value=value))
    e.db.commit()
    return e

def test_base_resistance_layers_ties_and_scenarios(matchup):
    e=matchup
    r=e.client.get('/api/matchups/ships/12023');assert r.status_code==200,r.text
    assert r.headers['cache-control']=='private, no-store'
    data=r.json();layers=data['layers']
    assert layers[0]['resists']=={'em':0,'thermal':60,'kinetic':85,'explosive':50}
    assert layers[0]['weakest']==['em'] and layers[1]['weakest']==['explosive']
    assert layers[2]['weakest']==list(matchups.DAMAGE)
    assert [v['key'] for v in data['variants']]==['blaster','rail']
    assert all(v['source']['url'].startswith('https://') and v['reviewed_at'] for v in data['variants'])
    assert 'not a fitted ammo recommendation' in data['resist_note']
    other=e.client.get('/api/matchups/ships/12023?context=fleet').json()
    assert other['variants'][0]['plan']!=data['variants'][0]['plan']
    assert other['variants'][0]['counter_tools'][0]['plan']!=data['variants'][0]['counter_tools'][0]['plan']

def test_missing_invalid_dogma_and_unknown_hulls_stay_unknown(matchup):
    e=matchup
    values=e.db.scalars(select(EveTypeDogmaAttribute).where(EveTypeDogmaAttribute.type_id==12023)).all()
    e.db.delete(values[0]);values[1].value=1.5;e.db.commit()
    data=e.client.get('/api/matchups/ships/12023').json()
    assert data['layers'][0]['weakest']==[]
    assert data['layers'][0]['resists']['em'] is None and data['layers'][0]['resists']['thermal'] is None
    unknown=e.client.get('/api/matchups/ships/111').json()
    assert not unknown['curated'] and unknown['variants']==[]
    assert all(l['weakest']==[] and set(l['resists'].values())=={None} for l in unknown['layers'])
    for tid in [112,113,999]:assert e.client.get(f'/api/matchups/ships/{tid}').status_code==404

def test_literal_bounded_published_ship_search(matchup):
    e=matchup
    assert [r['name'] for r in e.client.get('/api/matchups/ships?q=DEI').json()]==['Deimos']
    assert [r['name'] for r in e.client.get('/api/matchups/ships?q=cruiser').json()]==['Unknown Cruiser']
    assert e.client.get('/api/matchups/ships?q=%25_').json()==[]
    for q in ['x','%20%20','x'*101]:assert e.client.get('/api/matchups/ships?q='+q).status_code==422
    for i in range(40):e.db.add(EveType(type_id=2000+i,name=f'Test ship {i}',group_id=26))
    e.db.commit();assert len(e.client.get('/api/matchups/ships?q=test').json())==30

def test_scan_analysis_is_read_only_counts_duplicates_and_ignores_ship_names(matchup):
    e=matchup;before=e.db.scalar(select(func.count()).select_from(LocalScanReport))
    text='12023\tPRIVATE PILOT NAME\tDeimos\t14 km\n12023\tother\tDeimos\t15 km\n621\tCaracal\tCaracal\t30 km\n111\tfoo\tUnknown Cruiser\t1 km\n999\tfoo\tMystery\t1 km\nbad row'
    r=e.client.post('/api/matchups/analyze',json={'text':text});assert r.status_code==200,r.text
    data=r.json();assert data['total']==4 and data['covered']==3 and data['unresolved']==1 and len(data['ignored'])==1
    assert data['ships'][0]['type_name']=='Deimos' and data['ships'][0]['count']==2
    assert 'PRIVATE PILOT NAME' not in r.text and 'share_url' not in r.text and 'pilot' not in data
    assert dict((r['name'],r['count']) for r in data['possible_roles'])['projection']==2
    assert e.db.scalar(select(func.count()).select_from(LocalScanReport))==before
    assert not private_collection_enabled(e.db,e.users['intel_analyst'])
    assert requested_scopes(e.db,e.users['intel_analyst'],['esi-assets.read_assets.v1'],'core')==['publicData']

def test_input_context_and_permission_validation(matchup):
    e=matchup
    for data in [{'text':''},{'text':'x'*500001},{'text':'bad'},{'text':'x','public':True}]:
        assert e.client.post('/api/matchups/analyze',json=data).status_code==422
    many='12023\tX\tDeimos\t1 km\n'*5001
    assert e.client.post('/api/matchups/analyze',json={'text':many}).status_code==422
    assert e.client.get('/api/matchups/ships/12023?context=bogus').status_code==422
    e.current[0]=None;assert e.client.get('/api/matchups/catalog').status_code==401
    e.current[0]=e.users['applicant'];assert e.client.get('/api/matchups/catalog').status_code==403
    e.current[0]=e.users['member'];e.db.add(UserSectionPermission(user_id=e.current[0].id,section='matchups',can_view=False));e.db.commit()
    assert e.client.get('/api/matchups/catalog').status_code==403
    assert e.client.post('/api/matchups/analyze',json={'text':many}).status_code==403

def test_utility_role_real_auth_can_analyze_but_not_generate_reports(matchup):
    e=matchup;e.app.dependency_overrides.pop(auth.get_current_user)
    headers={'Authorization':'Bearer '+create_access_token(str(e.users['quartermaster'].id))}
    r=e.client.post('/api/matchups/analyze',headers=headers,json={'text':'12023\tX\tDeimos\t1 km'})
    assert r.status_code==200,r.text
    assert e.client.post('/api/local-scans',headers=headers,json={'text':'Alpha One'}).status_code==403

def test_custom_combined_role_and_disable_preserve_standard_permission_rules(matchup):
    e=matchup;u=e.users['applicant']
    e.db.add(RoleDefinition(name='fleet-trainee',display_name='Fleet trainee',base_role='intel_analyst',is_system=False,sort_order=100));e.db.flush()
    assign_roles(e.db,u,['applicant','fleet-trainee']);e.db.commit();e.current[0]=u
    assert effective_permissions(u,e.db)['matchups'] and e.client.get('/api/matchups/catalog').status_code==200
    from app.services.permissions import set_disabled_sections
    set_disabled_sections(e.db,{'matchups'});e.db.commit()
    assert e.client.get('/api/matchups/catalog').status_code==403

def test_saved_scan_keeps_private_and_expiry_boundaries_and_only_projects_counts(matchup):
    e=matchup;at=now()
    payload={'rows':[{'category':'ships','type_id':12023,'type_name':'Deimos','count':3,'observed':2,'manual':1}], 'local_scan':{'characters':['PRIVATE']},'system':{'name':'PRIVATE SYSTEM'},'objects':[{'name':'PRIVATE'}]}
    for token,private,expired in [('private',True,False),('public',False,False),('expired',False,True)]:
        e.db.add(LocalScanReport(report_kind='dscan',token=token,is_private=private,created_by_user_id=e.users['member'].id,account_name='PRIVATE',application_version='2.0.1',created_at=at,expires_at=at+timedelta(hours=-1 if expired else 1),retention='1h',payload=payload))
    e.db.commit()
    r=e.client.get('/api/matchups/scans/private');assert r.status_code==200 and r.json()['total']==3
    assert 'PRIVATE' not in r.text and r.json()['ships'][0]['manual']==1
    for role in ['other','admin','host']:
        e.current[0]=e.users[role]
        assert e.client.get('/api/matchups/scans/private').status_code==404
        assert e.client.get('/api/matchups/scans/public').status_code==200
    assert e.client.get('/api/matchups/scans/expired').status_code==404
    e.current[0]=e.users['member'];e.db.add(UserSectionPermission(user_id=e.current[0].id,section='dscan',can_view=False));e.db.commit()
    assert e.client.get('/api/matchups/scans/public').status_code==403
    assert e.client.get('/api/matchups/ships/12023').status_code==200

def test_catalog_references_are_complete_and_no_private_data_tables_added(matchup):
    data=matchup.client.get('/api/matchups/catalog').json()
    assert data['curated_hulls']==7 and len(WEAPONS)==8
    assert len({w['key'] for w in WEAPONS})==len(WEAPONS)
    assert all(w['pair'] in {x['key'] for x in WEAPONS} for w in WEAPONS)
    for hull,variants in HULLS.items():
        assert hull in SOURCES and variants
        assert len({v['key'] for v in variants})==len(variants)
        for v in variants:
            assert set(v['counters'])<=set(COUNTERS)
            assert set(v['weapons'])<={w['key'] for w in WEAPONS}
            assert v['small_gang'] and v['fleet'] and v['range_note']
    # Saved/custom navigation accepts the module without using layouts as permission grants.
    from app.api.appearance import PreferencesPatch
    assert PreferencesPatch(revision=0,navigation=[{'id':'quick','name':'Quicklaunch','modules':['matchups']}]).navigation


def test_full_catalog_uses_subclass_and_name_order(matchup):
    e = matchup
    e.db.add(EveGroup(group_id=894, category_id=6, name='Heavy Interdiction Cruiser'))
    e.db.flush()
    e.db.add(EveType(type_id=11995, name='Onyx', group_id=894))
    e.db.commit()
    rows = e.client.get('/api/matchups/catalog').json()['hulls']
    assert [(row['class_name'], row['name']) for row in rows] == [
        ('Cruiser', 'Caracal'), ('Cruiser', 'Deimos'), ('Cruiser', 'Unknown Cruiser'),
        ('Heavy Interdiction Cruiser', 'Onyx'),
    ]


def test_loss_examples_keep_slot_charges_and_release_db_during_fetch(matchup, monkeypatch):
    from app.models import AppSetting
    from app.services import matchup_examples

    e = matchup
    e.db.add_all([
        AppSetting(key='killboard_enabled', value='true'),
        EveCategory(category_id=8, name='Charge'),
        EveGroup(group_id=74, category_id=7, name='Hybrid Weapon'),
    ])
    e.db.flush()
    e.db.add(EveGroup(group_id=374, category_id=8, name='Advanced Railgun Charge'))
    e.db.flush()
    e.db.add_all([
        EveType(type_id=3082, name='250mm Railgun II', group_id=74),
        EveType(type_id=12801, name='Javelin M', group_id=374),
    ])
    e.db.commit()
    row = {
        'killmail_id': 1, 'killmail_time': '2026-11-06T12:00:00Z',
        'victim': {'ship_type_id': 12023, 'character_id': 98765, 'items': [
            {'flag': 27, 'item_type_id': 3082, 'quantity_dropped': 1},
            {'flag': 27, 'item_type_id': 12801, 'quantity_destroyed': 18},
            {'flag': 5, 'item_type_id': 987654, 'quantity_destroyed': 999},
        ]},
        'zkb': {'npc': False, 'hash': 'fixture-secret'},
    }
    samples = matchup_examples.samples_from_page([
        row, row, {**row, 'killmail_id': 2, 'victim': {'ship_type_id': 621}},
        {**row, 'killmail_id': 3, 'zkb': {'npc': True}},
    ], 12023)
    assert len(samples) == 1

    async def sample(type_id, _delay):
        assert type_id == 12023
        assert not e.db.in_transaction()
        return {'checked_at': row['killmail_time'], 'scanned_count': 4, 'samples': samples}

    monkeypatch.setattr(matchup_examples.source, 'sample', sample)
    response = e.client.get('/api/matchups/ships/12023/examples')
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'private, no-store'
    example = response.json()['examples'][0]
    assert example['modules'] == [{'slot': 'HiSlot0', 'name': '250mm Railgun II', 'quantity': 1, 'charge': 'Javelin M'}]
    assert example['counter_fits'][0]['hull'] == 'Arbitrator'
    assert example['stats'] is None
    assert all(secret not in response.text for secret in ('fixture-secret', '98765', 'character_id'))
    e.current[0] = e.users['applicant']
    assert e.client.get('/api/matchups/ships/12023/examples').status_code == 403


def test_loss_research_rechecks_permissions_after_network(matchup, monkeypatch):
    from app.models import AppSetting
    from app.services import matchup_examples

    e = matchup
    e.db.add(AppSetting(key='killboard_enabled', value='true'))
    e.db.commit()

    async def revoke_access(_type_id, _delay):
        e.db.add(UserSectionPermission(user_id=e.users['member'].id, section='matchups', can_view=False))
        e.db.commit()
        return {'checked_at': '2026-11-06', 'scanned_count': 0, 'samples': []}

    monkeypatch.setattr(matchup_examples.source, 'sample', revoke_access)
    assert e.client.get('/api/matchups/ships/12023/examples').status_code == 403
