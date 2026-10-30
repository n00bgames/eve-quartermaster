from datetime import datetime,timedelta,timezone
import csv,io
import pytest
from sqlalchemy import select
from app.api import auth,analytics,ship_analytics,ship_reports,industry_reports
from app.models import (Asset,EveCategory,EveGroup,EveType,EveDogmaAttribute,EveTypeDogmaAttribute,
    OwnershipEntity,EveCharacter,User,UserSectionPermission,RoleDefinition,SnapshotRun,SnapshotMetric)
from app.models.enums import OwnerKind
from app.services import ship_analytics as history
from app.services.analytics import create_snapshot,RETENTION_MODE_CHANGES
from app.services.permissions import ROLE_RANK,assign_roles,role_rank,effective_permissions
from app.services.esi_scope_policy import allowed_scopes,private_collection_enabled
from tests.test_local_scan import env
from tests.test_industry_inventory import stock


@pytest.fixture
def fleet(stock):
    db=stock.db
    classes=[(29,'Capsule'),(31,'Shuttle'),(25,'Frigate'),(547,'Carrier'),(659,'Supercarrier'),(30,'Titan'),
        (513,'Freighter'),(902,'Jump Freighter'),(883,'Capital Industrial Ship'),(9001,'Future XL Hull')]
    types={}
    for gid,name in classes:
        group=EveGroup(group_id=gid,name=name,category_id=6);db.add(group);db.flush()
        tid=10000+gid;types[name]=tid
        db.add(EveType(type_id=tid,name=name+' Test Hull',group_id=gid));db.flush()
        db.add(Asset(ownership_entity_id=stock.owner.id,type_id=tid,quantity=50 if gid==29 else 4 if gid==31 else 6 if gid==25 else 2,
            location_id=stock.station.id,location_flag='Hangar',last_synced_at=datetime.now(timezone.utc)))
    db.add(EveDogmaAttribute(attribute_id=1547,name='rigSize'))
    db.add(EveTypeDogmaAttribute(type_id=types['Future XL Hull'],attribute_id=1547,value=4))
    fc=User(email='fc@test.invalid',display_name='Fleet Commander Example',role='fleet_commander',password_hash='synthetic')
    db.add(fc);db.add(UserSectionPermission(user_id=stock.env.users['member'].id,section='analytics',can_view=True));db.commit()
    stock.env.app.include_router(ship_reports.router,prefix='/api')
    stock.env.app.include_router(ship_analytics.router,prefix='/api')
    stock.env.app.include_router(analytics.router,prefix='/api')
    stock.env.app.include_router(auth.router,prefix='/api')
    stock.env.users['fleet_commander']=fc
    officer=User(email='officer@example.test',display_name='Example Officer',role='officer',password_hash='synthetic');db.add(officer);db.commit()
    stock.env.users['officer']=officer;stock.types=types
    return stock


def report(fleet,**body):
    response=fleet.env.client.post('/api/ship-reports',json=body)
    assert response.status_code==201,response.text
    return response.json()


def capture(fleet,at=None,source='manual',mode='full'):
    db=fleet.db
    run=SnapshotRun(scope_type='character',scope_id=fleet.char.id,source=source,status='success',schema_version=2)
    db.add(run);db.flush()
    history.capture_owner(db,run,fleet.owner,retention_mode=mode);db.flush()
    if at:
        for row in db.scalars(select(SnapshotMetric).where(SnapshotMetric.snapshot_run_id==run.id)):row.recorded_at=at
    db.commit();return run


def test_capsules_removed_from_new_and_old_reports_and_exports(fleet):
    data=report(fleet)
    assert data['summary']['ships']==25 and data['summary']['ship_types']==10
    assert 'Capsule Test Hull' not in str(data)
    # A saved pre-policy snapshot must also lose its capsules at read/export time.
    from app.models.local_scan import LocalScanReport
    row=fleet.db.get(LocalScanReport,data['token']);payload=dict(row.payload)
    payload['stock']=[*payload['stock'],{'owner':'Old pilot','owner_kind':'character','type_id':10029,'item':'Capsule Test Hull','quantity':50,'category':'Ship','ship_class':'Capsule','location':'Jita'}]
    row.payload=payload;fleet.db.commit()
    saved=fleet.env.client.get('/api/ship-reports/reports/'+row.token).json()
    assert saved['summary']['ships']==25 and 'Capsule Test Hull' not in str(saved)
    csv=fleet.env.client.get('/api/ship-reports/reports/'+row.token+'/export/csv').text
    assert 'Capsule Test Hull' not in csv and 'TOTAL SHIPS,25' in csv


def test_per_class_filters_and_subcaps_context_include_all_capitals(fleet):
    context=fleet.env.client.get('/api/ship-reports/context').json()
    classes=context['ship_classes'];assert all(c['id']!=29 for c in classes)
    excluded=[c['id'] for c in classes if c['subcaps_excluded']]
    assert {31,547,659,30,513,902,883,9001}.issubset(excluded)
    data=report(fleet,excluded_group_ids=excluded)
    assert data['summary']['ships']==7 and data['summary']['ship_types']==2
    assert {r['item'] for r in data['totals']}=={'Raven','Frigate Test Hull'}
    assert data['ship_filters']['excluded_group_ids']==sorted(excluded)
    individual=report(fleet,excluded_group_ids=[27])
    assert individual['summary']['ships']==24 and 'Raven' not in str(individual['totals'])
    for invalid in ([True],[999999],[-1]):
        assert fleet.env.client.post('/api/ship-reports',json={'excluded_group_ids':invalid}).status_code==422


def test_fleet_commander_assignment_and_least_privilege_ship_access(fleet):
    fc=fleet.env.users['fleet_commander'];fleet.env.current[0]=fc
    permissions=fleet.env.client.get('/api/auth/permissions/effective').json()
    assert permissions['ship_reports_available']
    assert permissions['permissions']['ship_reports'] and permissions['permissions']['analytics']
    assert not permissions['permissions']['assets'] and not permissions['permissions']['inventory_reports']
    assert not private_collection_enabled(fleet.db,fc) and allowed_scopes(fleet.db,fc)=={'publicData','esi-ui.write_waypoint.v1','esi-universe.read_structures.v1','esi-search.search_structures.v1'}
    assert report(fleet)['summary']['ships']==25
    assert fleet.env.client.post('/api/inventory-reports',json={}).status_code==403
    assert ROLE_RANK['officer']<role_rank(fc,fleet.db)<ROLE_RANK['director']
    fleet.env.current[0]=fleet.env.users['admin']
    roles=fleet.env.client.get('/api/auth/roles').json()
    assert any(r['name']=='fleet_commander' and r['display_name']=='Fleet Commander' for r in roles)
    response=fleet.env.client.patch('/api/auth/users/'+str(fleet.env.users['other'].id),json={'roles':['member','fleet_commander']})
    assert response.status_code==200,response.text
    assert set(response.json()['roles'])=={'member','fleet_commander'}


@pytest.mark.parametrize('role,capital', [('member',False),('officer',False),('fleet_commander',True),('director',True),('admin',True),('host',True)])
def test_analytics_capital_gate_applies_to_all_totals_types_history_and_exports(fleet,role,capital):
    capture(fleet)
    fleet.env.current[0]=fleet.env.users[role]
    response=fleet.env.client.get('/api/analytics/ships?days=0')
    assert response.status_code==200,response.text
    data=response.json();assert data['capitals_visible']==capital
    assert data['total_ships']==(25 if capital else 11)
    assert data['ship_types']==(10 if capital else 3)
    assert data['series'][-1]['value']==data['total_ships']
    assert all(('Titan' not in row['item'] and 'Carrier' not in row['ship_class'] and 'XL' not in row['ship_class'] and 'Freighter' not in row['ship_class']) for row in data['by_type']) if not capital else True
    selected=fleet.env.client.get('/api/analytics/ships?days=0&type_id='+str(fleet.types['Titan'])).json()
    assert bool(selected['type_series'])==capital
    exported=fleet.env.client.get('/api/analytics/exports/metrics.json?days=0')
    assert exported.status_code==200,exported.text
    rows=[row for row in exported.json() if row['metric_key'].startswith('ships.')]
    assert any(r['metric_key']=='ships.total' for r in rows)==capital
    assert any(r.get('dimensions',{}).get('type_id')==fleet.types['Titan'] for r in rows if isinstance(r.get('dimensions'),dict))==capital
    text=fleet.env.client.get('/api/analytics/exports/metrics.csv?days=0').text
    assert ('ships.total' in text)==capital


def test_multi_and_custom_fc_roles_aggregate_for_capital_gate(fleet):
    capture(fleet)
    fleet.db.add(RoleDefinition(name='fleet_lead',display_name='Fleet Lead',base_role='fleet_commander'))
    user=fleet.env.users['member'];assign_roles(fleet.db,user,['member','fleet_lead']);fleet.db.commit()
    fleet.env.current[0]=user
    assert fleet.env.client.get('/api/analytics/ships?days=0').json()['total_ships']==25
    assert fleet.env.client.get('/api/auth/permissions/effective').json()['ship_reports_available']


def test_removed_type_zeroes_history_and_report_filters_do_not_change_it(fleet):
    first=datetime.now(timezone.utc)-timedelta(days=3);capture(fleet,first)
    titan=fleet.db.scalar(select(Asset).where(Asset.type_id==fleet.types['Titan']));fleet.db.delete(titan);fleet.db.commit()
    capture(fleet,first+timedelta(days=1))
    fleet.env.current[0]=fleet.env.users['fleet_commander']
    report(fleet,excluded_group_ids=[27,25,31,547,659,30,513,902,883,9001])
    data=fleet.env.client.get('/api/analytics/ships?days=0&type_id='+str(fleet.types['Titan'])).json()
    assert data['total_ships']==23 and data['ship_types']==9
    assert [p['value'] for p in data['type_series']]==[2,0]
    assert [p['value'] for p in data['series']]==[25,23]


def test_history_baseline_survives_quiet_period_and_deduplicates_type_counts(fleet):
    capture(fleet,datetime.now(timezone.utc)-timedelta(days=40))
    fleet.env.current[0]=fleet.env.users['fleet_commander']
    data=fleet.env.client.get('/api/analytics/ships?days=7').json()
    assert data['total_ships']==25 and len(data['series'])==1 and data['series'][0]['value']==25
    # Another owner holding the same Raven adds hulls but no distinct hull type.
    other=fleet.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==fleet.env.users['other'].id))
    fleet.db.add(Asset(ownership_entity_id=fleet.other.id,type_id=638,quantity=3,location_id=fleet.station.id))
    run=SnapshotRun(source='manual',scope_type='global',status='success');fleet.db.add(run);fleet.db.flush()
    history.capture_owner(fleet.db,run,fleet.other);fleet.db.commit()
    data=fleet.env.client.get('/api/analytics/ships?days=0').json()
    assert data['total_ships']==28 and data['ship_types']==10


def test_private_scope_and_collection_opt_outs(fleet):
    capture(fleet)
    fleet.env.current[0]=fleet.env.users['other']
    fleet.db.add(UserSectionPermission(user_id=fleet.env.users['other'].id,section='analytics',can_view=True));fleet.db.commit()
    assert fleet.env.client.get('/api/analytics/ships?days=0').json()['total_ships']==0
    fleet.env.current[0]=fleet.env.users['admin'];fleet.char.sync_opt_out=True;fleet.db.commit()
    assert fleet.env.client.get('/api/analytics/ships?days=0').json()['total_ships']==0
    fleet.char.sync_opt_out=False;fleet.env.users['member'].role='fleet_commander';fleet.db.commit()
    run=capture(fleet)
    assert fleet.db.scalar(select(SnapshotMetric).where(SnapshotMetric.snapshot_run_id==run.id)) is None
    assert fleet.env.client.get('/api/analytics/ships?days=0').json()['total_ships']==0


def test_asset_and_global_snapshot_hooks_record_ship_metrics(fleet):
    run=create_snapshot(fleet.db,scope_type='character',scope_id=fleet.char.id,source='character_assets');fleet.db.commit()
    assert fleet.db.scalar(select(SnapshotMetric).where(SnapshotMetric.snapshot_run_id==run.id,SnapshotMetric.metric_key=='ships.total')).metric_value==25
    run=create_snapshot(fleet.db,source='manual');fleet.db.commit()
    assert fleet.db.scalar(select(SnapshotMetric).where(SnapshotMetric.snapshot_run_id==run.id,SnapshotMetric.metric_key=='ships.total')).metric_value==25


def test_corporation_ship_history_respects_access_and_exclusions(fleet):
    from app.models import EveCorporation,EsiSyncJob,EsiToken
    from app.models.enums import SyncStatus
    db=fleet.db;corp=db.get(EveCorporation,fleet.char.corporation_id)
    owner=OwnershipEntity(owner_kind=OwnerKind.CORPORATION,corporation_id=corp.id,display_name=corp.name);db.add(owner);db.flush()
    token=db.scalar(select(EsiToken).where(EsiToken.character_id==fleet.char.id))
    db.add(EsiSyncJob(token_id=token.id,ownership_entity_id=owner.id,sync_type='corporation_assets',status=SyncStatus.SUCCESS))
    db.add_all([Asset(ownership_entity_id=owner.id,type_id=638,quantity=5,location_id=fleet.station.id),
                Asset(ownership_entity_id=owner.id,type_id=fleet.types['Titan'],quantity=3,location_id=fleet.station.id)])
    db.commit();run=create_snapshot(db,scope_type='corporation',scope_id=corp.id,source='corporation_assets');db.commit()
    assert db.scalar(select(SnapshotMetric).where(SnapshotMetric.snapshot_run_id==run.id,SnapshotMetric.metric_key=='ships.total')).metric_value==8
    fleet.env.current[0]=fleet.env.users['fleet_commander']
    assert fleet.env.client.get('/api/analytics/ships?days=0').json()['total_ships']==8
    fleet.env.current[0]=fleet.env.users['officer']
    assert fleet.env.client.get('/api/analytics/ships?days=0').json()['total_ships']==5
    corp.exclude_from_analytics=True;db.commit()
    assert fleet.env.client.get('/api/analytics/ships?days=0').json()['total_ships']==0


def test_change_retention_suppresses_unchanged_ship_rows(fleet):
    capture(fleet)
    run=capture(fleet,source='character_assets',mode=RETENTION_MODE_CHANGES)
    assert fleet.db.scalar(select(SnapshotMetric).where(SnapshotMetric.snapshot_run_id==run.id)) is None


def test_lower_role_exports_only_safe_type_rows_even_if_old_aggregate_is_wrong(fleet):
    capture(fleet)
    row=fleet.db.scalar(select(SnapshotMetric).where(SnapshotMetric.metric_key=='ships.subcapital_total'))
    row.metric_value=99999;fleet.db.commit()
    data=fleet.env.client.get('/api/analytics/ships?days=0').json()
    assert data['total_ships']==11
    rows=fleet.env.client.get('/api/analytics/exports/metrics.json?days=0').json()
    assert not any(r['metric_key'] in {'ships.total','ships.types','ships.subcapital_total','ships.subcapital_types'} for r in rows)
