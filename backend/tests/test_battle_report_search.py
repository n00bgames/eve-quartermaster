from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from sqlalchemy import select,func
from sqlalchemy.dialects import postgresql
from app.models import EveCategory,EveGroup,EveType,BattleReportShare,UserSectionPermission
from app.services import battle_report_search as service
from app.services.local_scan import now
from .test_battle_management import managed,battle,saved
from .test_local_scan import env

@pytest.fixture
def searchable(managed):
    e=managed
    e.db.add_all([EveCategory(category_id=6,name='Ship'),EveCategory(category_id=22,name='Deployable'),EveCategory(category_id=65,name='Structure')]);e.db.flush()
    e.db.add_all([EveGroup(group_id=25,name='Frigate',category_id=6),EveGroup(group_id=485,name='Dreadnought',category_id=6),
        EveGroup(group_id=1250,name='Mobile Tractor Unit',category_id=22),EveGroup(group_id=1657,name='Citadel',category_id=65)]);e.db.flush()
    e.db.add_all([EveType(type_id=587,name='Rifter',group_id=25),EveType(type_id=19720,name='Revelation',group_id=485),
        EveType(type_id=33475,name='Mobile Tractor Unit',group_id=1250),EveType(type_id=35832,name='Astrahus',group_id=1657)]);e.db.commit()
    return e

def pilot(name,side=1,corp='BlackWhiteCyno Corp',alliance='BlackWhiteCyno Alliance',tid=19720,gid=485):
    return {'character_id':None,'character_name':name,'side':side,'corporation_id':98001,'corporation_name':corp,'alliance_id':99001,'alliance_name':alliance,
        'ships':[{'type_id':tid,'type_name':'Revelation' if tid==19720 else 'Rifter','ship_group_id':gid,'ship_group_name':'Dreadnought' if gid==485 else 'Frigate'}],
        'ship_type_names':['Revelation' if tid==19720 else 'Rifter']}

def store(e,pilots=None,**extra):
    data=deepcopy(e.battle)
    pilots=pilots if pilots is not None else [pilot('Our Anchor',0,'Home Corp','Home Alliance',587,25),pilot('Enemy Commander'),pilot('Enemy Support',corp='Other Corp',alliance='Other Alliance',tid=587,gid=25),pilot('Neutral Dread',2)]
    for i,p in enumerate(pilots):
        if p['character_id'] is None:p['character_id']=90000001+i
    data['report'].update(participants=pilots,timeline=[],systems=[{'system_id':30000001,'system_name':'Hagilua'}])
    data['report']['composition']=[{'side':p['side'],'ship_type_id':s['type_id'],'ship_type_name':s['type_name'],'ship_group_id':s.get('ship_group_id')} for p in pilots for s in p.get('ships',[])]
    row=saved(e,**extra);row.report_payload=data;e.db.commit();return row

def listing(e,**params):
    response=e.client.get('/api/battle-reports/reports',params=params);assert response.status_code==200,response.text
    return response.json()

def test_fields_are_side_specific_and_and_matches_the_same_combatant(searchable):
    e=searchable;row=store(e)
    values={'side':'hostile','pilot_name':'enemy COMMAND','combat_corporation':'blackwhite','alliance_name':'Cyno Alliance','class_key':'capitals','type_id':19720,'combatants':'2-4','system_name':'hagi'}
    result=listing(e,**values);assert result['total']==1 and result['reports'][0]['id']==row.id
    for changed in [{'side':'my'},{'pilot_name':'Neutral Dread'},{'pilot_name':'Enemy Support'},{'class_key':'g:25','type_id':587},{'system_name':'Bei'},{'combatants':'solo'}]:
        assert listing(e,**(values|changed))['total']==0
    assert listing(e,side='my',pilot_name='Anchor',combatants='solo')['total']==1
    assert result['reports'][0]['battle_summary']['hostile_pilots']==2

def test_or_details_keep_side_system_count_and_dates_as_and_constraints(searchable):
    e=searchable;store(e)
    values={'side':'hostile','pilot_name':'Not There','combat_corporation':'BlackWhite','match':'any','combatants':'2-4','system_name':'Hagilua'}
    assert listing(e,**values)['total']==1
    for changed in [{'side':'my'},{'system_name':'Elsewhere'},{'combatants':'solo'},{'match':'all'}]:assert listing(e,**(values|changed))['total']==0

@pytest.mark.parametrize('bucket,low,high',[(k,*v) for k,v in service.RANGES.items()])
def test_combatant_bucket_boundaries_and_unique_pilots(searchable,bucket,low,high):
    e=searchable
    def data(count):
        rows=[pilot(f'Enemy {i}') for i in range(count)]
        for i,p in enumerate(rows):p['character_id']=90000001+i
        if rows:rows.append(deepcopy(rows[-1])) # repeated appearances are not extra pilots
        return rows
    row=store(e,data(low));assert listing(e,side='hostile',combatants=bucket)['total']==1
    row.report_payload={**row.report_payload,'report':{**row.report_payload['report'],'participants':data(low-1)}};e.db.commit()
    assert listing(e,side='hostile',combatants=bucket)['total']==0
    if high is not None:
        row.report_payload={**row.report_payload,'report':{**row.report_payload['report'],'participants':data(high)}};e.db.commit()
        assert listing(e,side='hostile',combatants=bucket)['total']==1
        row.report_payload={**row.report_payload,'report':{**row.report_payload['report'],'participants':data(high+1)}};e.db.commit()
        assert listing(e,side='hostile',combatants=bucket)['total']==0

def test_pilotless_structure_and_deployable_losses_match_side_and_owner(searchable):
    e=searchable;row=store(e)
    events=[{'victim_side':1,'victim_character_id':None,'victim_name':'BlackWhiteCyno Corp','victim_corporation_name':'BlackWhiteCyno Corp','victim_alliance_name':'BlackWhiteCyno Alliance','victim_ship_type_id':35832,'system_name':'Hagilua'},
        {'victim_side':0,'victim_character_id':None,'victim_ship_type_id':33475,'victim_corporation_name':'Home Corp','system_name':'Hagilua'}]
    row.report_payload={**row.report_payload,'report':{**row.report_payload['report'],'timeline':events}};e.db.commit()
    assert listing(e,side='hostile',class_key='structures',type_id=35832,combat_corporation='BlackWhite')['total']==1
    assert listing(e,side='hostile',class_key='g:1657',type_id=35832)['total']==1
    assert listing(e,side='my',class_key='structures')['total']==0
    assert listing(e,side='my',class_key='deployables',type_id=33475)['total']==1
    assert listing(e,side='hostile',class_key='structures',pilot_name='BlackWhiteCyno')['total']==0

def test_old_name_only_ship_rows_are_searchable_without_changing_snapshot(searchable):
    e=searchable;row=store(e)
    original=deepcopy(row.report_payload)
    for p in original['report']['participants']:p.pop('ships')
    original['report']['composition']=[];row.report_payload=deepcopy(original);e.db.commit()
    assert listing(e,side='hostile',class_key='g:485',pilot_name='Enemy Commander')['total']==1
    assert listing(e,side='hostile',type_id=19720,pilot_name='Enemy Commander')['total']==1
    e.db.refresh(row);assert row.report_payload==original

def test_search_covers_all_pages_and_result_summary_is_bounded(searchable):
    e=searchable;match=store(e);match.created_at=now()-timedelta(days=2);e.db.commit()
    for i in range(28):store(e,[pilot(f'Decoy {i}',corp='Decoy',alliance='Other',tid=587,gid=25)])
    assert listing(e)['total']==29
    result=listing(e,side='hostile',class_key='capitals');assert result['total']==1 and result['reports'][0]['id']==match.id
    assert result['reports'][0]['battle_summary']['systems']==['Hagilua']
    assert result['reports'][0]['battle_summary']['side_hulls']==['Revelation','Rifter']

def test_literal_wildcards_and_malformed_or_empty_snapshots(searchable):
    e=searchable;store(e,[pilot('Percent%_Pilot')]);empty=store(e,[])
    empty.report_payload={'report':{'participants':None,'composition':[],'systems':[],'timeline':[]}};e.db.commit()
    assert listing(e,pilot_name='%_',side='hostile')['total']==1
    assert listing(e,pilot_name='does_not_exist',side='hostile')['total']==0
    assert listing(e,combatants='solo',side='hostile')['total']==1

def test_filter_validation_and_dependent_options(searchable):
    e=searchable
    for params in [{'side':'third'},{'combatants':'0-100'},{'match':'sometimes'},{'pilot_name':'x'*121},{'class_key':'bad'},{'class_key':'g:999999'},{'type_id':999999},{'class_key':'g:25','type_id':19720}]:
        assert e.client.get('/api/battle-reports/reports',params=params).status_code==422
    opts=e.client.get('/api/battle-reports/report-search-options?class_key=capitals').json()
    assert opts['types']==[{'id':19720,'name':'Revelation'}]
    assert {c['section'] for c in opts['classes']}=={'Ship classes','Deployables','Structures'}
    assert e.client.get('/api/battle-reports/report-search-options?class_key=g:1657').json()['types']==[{'id':35832,'name':'Astrahus'}]

def test_search_and_options_do_not_expand_permissions_or_leak_foreign_private(searchable):
    e=searchable;own=store(e);store(e,owner='other',private=True);store(e,owner='other',corp=102)
    assert listing(e,scope='managed',side='hostile',alliance_name='BlackWhite')['total']==1
    e.current[0]=e.users['admin'];assert listing(e,scope='managed',side='hostile',alliance_name='BlackWhite')['total']==2
    e.current[0]=None
    for endpoint in ['reports?side=hostile&class_key=capitals','report-search-options']:assert e.client.get('/api/battle-reports/'+endpoint).status_code==401
    e.current[0]=e.users['member'];e.db.add(UserSectionPermission(user_id=e.current[0].id,section='battle_reports',can_view=False));e.db.commit()
    assert e.client.get('/api/battle-reports/report-search-options').status_code==403

def test_bulk_review_and_deletion_use_exact_applied_search_conditions(searchable):
    e=searchable;match=store(e);other=store(e,[pilot('Unrelated',tid=587,gid=25)]);match_id=match.id;other_id=other.id
    payload={'all_in_scope':True,'side':'hostile','class_key':'capitals','combatants':'2-4','system_name':'Hagilua'}
    preview=e.client.post('/api/battle-reports/reports/delete-preview',json=payload)
    assert preview.status_code==200 and preview.json()['count']==1
    assert e.client.post('/api/battle-reports/reports/delete',json=preview.json()['selection']).json()['deleted']==1
    assert e.db.get(BattleReportShare,other_id) is not None and e.db.get(BattleReportShare,match_id) is None

@pytest.mark.parametrize('extra',[{}, {'class_key':'g:485'}, {'class_key':'capitals','type_id':19720,'match':'any'}])
def test_postgresql_query_compiles_as_correlated_jsonb_exists(searchable,extra):
    e=searchable
    connection=SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))
    real=e.db.get_bind
    with patch.object(e.db,'get_bind',return_value=connection),patch.object(service,'validate_hull',return_value={485} if extra else None):
        # SDE validation is separately exercised against SQLite; compile every JSON path for PostgreSQL.
        clauses=service.conditions(e.db,service.SearchFilters(side='hostile',pilot_name='Enemy',combatants='251-350',system_name='Hagilua',**extra))
    sql=str(select(BattleReportShare.id).where(*clauses).compile(dialect=postgresql.dialect()))
    assert 'jsonb_array_elements' in sql and 'count(distinct(' in sql.lower() and ' AS JSONB)' in sql
    assert sql.count('FROM battle_report_shares')==1
