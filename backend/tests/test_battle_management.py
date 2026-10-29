"""Battle management permissions, deletion boundaries, migrations and complete exports."""
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import importlib.util
import secrets
import pytest
from sqlalchemy import select, create_engine, text, inspect
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.api import battle_reports as api
from app.models import BattleReportShare, EveCharacter, UserSectionPermission, User
from app.services.local_scan import now, utc
from app.services.battle_report_pdf import render_pdf
from app.services.battle_reports import build_latest_battle_report
from tests.test_local_scan import env
from tests import test_battle_reports as existing


@pytest.fixture
def battle():
    fixture=existing.BattleReportTests();fixture.setUp()
    with Session(fixture.engine) as db:
        user=db.scalar(select(User).where(User.email=='pilot@example.test'))
        snapshot=build_latest_battle_report(db,user,character_id=90000001)
    fixture.engine.dispose()
    return snapshot


@pytest.fixture
def managed(env,battle):
    env.app.include_router(api.router,prefix='/api')
    env.battle=battle
    return env


def saved(env,owner='member',corp=101,private=False,**extra):
    row=BattleReportShare(share_token=secrets.token_urlsafe(32),created_by_user_id=env.users[owner].id,
        corporation_id=corp,is_private=private,selected_character_id=90000001,selected_character_name='Selected Pilot',
        report_payload=deepcopy(env.battle),created_at=now(),**extra)
    env.db.add(row);env.db.commit();return row


def test_creation_corporation_must_be_creators_membership(managed):
    e=managed
    with patch.object(api,'build_latest_battle_report',return_value=e.battle):
        assert e.client.post('/api/battle-reports/shares',json={'character_id':90000001,'corporation_id':102}).status_code==422
        response=e.client.post('/api/battle-reports/shares',json={'character_id':90000001,'corporation_id':101,'anonymous':True})
        assert response.status_code==201,response.text
        value=response.json();row=e.db.get(BattleReportShare,value['id'])
        assert row.corporation_id==101 and value['corporation_id'] is None and value['creator_name']=='Anonymous'
        private=e.client.post('/api/battle-reports/shares',json={'character_id':90000001,'corporation_id':101,'is_private':True}).json()
        assert private['share_url'] is None and e.db.get(BattleReportShare,private['id']).corporation_id is None
    e.current[0]=None
    public=e.client.get('/api/battle-reports/public/'+value['share_token'])
    assert public.status_code==200 and 'corporation_id' not in public.json()['share']


@pytest.mark.parametrize('role,allowed', [('member',{'own'}),('director',{'own','corp'}),('admin',{'own','corp','foreign','legacy'}),('host',{'own','corp','foreign','legacy'})])
def test_management_scope(managed,role,allowed):
    e=managed
    records={'own':saved(e,owner=role,private=True),'corp':saved(e,owner='other',corp=101),
        'foreign':saved(e,owner='other',corp=102),'legacy':saved(e,owner='other',corp=None),'private':saved(e,owner='other',private=True)}
    e.current[0]=e.users[role]
    response=e.client.get('/api/battle-reports/reports?scope=managed');assert response.status_code==200,response.text
    assert {r['id'] for r in response.json()['reports']}=={records[k].id for k in allowed}
    assert response.headers['cache-control']=='no-store'
    for key,row in records.items():
        for suffix in ('','/pdf'):
            got=e.client.get(f'/api/battle-reports/shares/{row.id}{suffix}')
            assert got.status_code==(200 if key in allowed else 404),(key,suffix,got.text[:100])
    assert {r['id'] for r in e.client.get('/api/battle-reports/reports?scope=own').json()['reports']}=={records['own'].id}


def test_director_membership_change_rechecks_saved_pdf_and_delete(managed):
    e=managed;row=saved(e,owner='other');e.current[0]=e.users['director']
    assert e.client.get(f'/api/battle-reports/shares/{row.id}/pdf').status_code==200
    char=e.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==e.users['director'].id))
    char.corporation_id=None;e.db.commit()
    assert e.client.get(f'/api/battle-reports/shares/{row.id}').status_code==404
    assert e.client.get(f'/api/battle-reports/shares/{row.id}/pdf').status_code==404
    assert e.client.delete(f'/api/battle-reports/shares/{row.id}').status_code==404
    assert e.client.post('/api/battle-reports/reports/delete',json={'scope':'managed','all_in_scope':True}).json()['deleted']==0


def test_date_deletion_is_inclusive_start_exclusive_end_and_scoped(managed):
    e=managed;start=now()-timedelta(days=2);end=start+timedelta(days=1)
    a=saved(e);b=saved(e);c=saved(e);foreign=saved(e,owner='other');private=saved(e,owner='other',private=True)
    for row,time in [(a,start),(b,end-timedelta(seconds=1)),(c,end),(foreign,start),(private,start)]:row.created_at=time
    e.db.commit()
    token=a.share_token
    payload={'from_at':start.isoformat(),'to_at':end.isoformat(),'scope':'managed'}
    assert e.client.get('/api/battle-reports/reports',params=payload|{'scope':'own'}).json()['total']==2
    preview=e.client.post('/api/battle-reports/reports/delete-preview',json=payload).json()
    assert preview['count']==2
    assert e.client.post('/api/battle-reports/reports/delete',json=preview['selection']).json()['deleted']==2
    assert e.db.get(BattleReportShare,c.id) is not None and e.db.get(BattleReportShare,foreign.id) is not None
    for suffix in ('','/pdf'):assert e.client.get('/api/battle-reports/public/'+token+suffix).status_code==404


def test_all_deletion_excludes_new_reports_and_foreign_private(managed):
    e=managed;old=saved(e,owner='other');private=saved(e,owner='other',private=True)
    foreign=saved(e,owner='other',corp=102);e.current[0]=e.users['director']
    preview=e.client.post('/api/battle-reports/reports/delete-preview',json={'scope':'managed','all_in_scope':True}).json()
    assert preview['count']==1
    new=saved(e,owner='other');new.created_at=utc(__import__('datetime').datetime.fromisoformat(preview['selection']['created_before']))+timedelta(seconds=1);e.db.commit()
    token=old.share_token
    result=e.client.post('/api/battle-reports/reports/delete',json=preview['selection'])
    assert result.json()['deleted']==1
    assert all(e.db.get(BattleReportShare,r.id) is not None for r in [private,foreign,new])
    assert e.client.get('/api/battle-reports/public/'+token).status_code==404


def test_selected_deletion_and_legacy_revoke_use_same_scope(managed):
    e=managed;allowed=saved(e,owner='other');foreign=saved(e,owner='other',corp=102);private=saved(e,owner='other',private=True)
    e.current[0]=e.users['director']
    result=e.client.post('/api/battle-reports/reports/delete',json={'scope':'managed','ids':[allowed.id,foreign.id,private.id]})
    assert result.json()['deleted']==1
    allowed=saved(e,owner='other')
    assert e.client.delete(f'/api/battle-reports/shares/{allowed.id}').status_code==200
    assert e.client.delete(f'/api/battle-reports/shares/{foreign.id}').status_code==404
    e.current[0]=e.users['admin']
    assert e.client.delete(f'/api/battle-reports/shares/{private.id}').status_code==404
    assert e.client.delete(f'/api/battle-reports/shares/{foreign.id}').status_code==200


def test_pagination_filters_and_expiry(managed):
    e=managed
    for _ in range(28):saved(e)
    saved(e,expires_at=now()-timedelta(seconds=1));saved(e,revoked_at=now())
    first=e.client.get('/api/battle-reports/reports?limit=25').json()
    last=e.client.get('/api/battle-reports/reports?limit=25&offset=25').json()
    assert first['total']==last['total']==28 and len(first['reports'])==25 and len(last['reports'])==3
    assert not {r['id'] for r in first['reports']} & {r['id'] for r in last['reports']}
    assert e.client.get('/api/battle-reports/reports?corporation_id=102').json()['total']==0
    assert e.client.get('/api/battle-reports/reports?from_at=2026-01-01T00:00:00Z').status_code==422
    assert e.client.get('/api/battle-reports/reports?scope=anything').status_code==422


@pytest.mark.parametrize('payload',[{}, {'ids':[1],'all_in_scope':True},{'ids':[True]},{'ids':[-1]}, {'all_in_scope':True,'scope':'admin'}, {'from_at':'2026-01-02T00:00:00Z','to_at':'2026-01-01T00:00:00Z'}, {'from_at':'2026-01-01T00:00:00Z'}, {'all_in_scope':True,'created_by_user_id':1}])
def test_delete_validation(managed,payload):
    for path in ['delete-preview','delete']:
        assert managed.client.post('/api/battle-reports/reports/'+path,json=payload).status_code==422


def test_permission_and_authentication_required(managed):
    e=managed;saved(e)
    e.current[0]=None
    assert e.client.get('/api/battle-reports/reports').status_code==401
    e.current[0]=e.users['member'];e.db.add(UserSectionPermission(user_id=e.current[0].id,section='battle_reports',can_view=False));e.db.commit()
    assert e.client.get('/api/battle-reports/reports').status_code==403
    assert e.client.post('/api/battle-reports/reports/delete',json={'all_in_scope':True}).status_code==403


def test_pdf_rechecks_scope_after_render(managed):
    e=managed;row=saved(e,owner='other');e.current[0]=e.users['director']
    def revoke(*args):
        char=e.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==e.current[0].id));char.corporation_id=None;e.db.commit();return b'%PDF-test'
    with patch('app.services.battle_report_pdf.render_pdf',side_effect=revoke):
        assert e.client.get(f'/api/battle-reports/shares/{row.id}/pdf').status_code==404


def test_pdf_contains_team_composition_and_last_pilot_without_mutation(battle):
    from pypdf import PdfReader
    data=deepcopy(battle)
    for i in range(85):
        row=deepcopy(data['report']['participants'][0]);row.update(character_name=f'Example Pilot {i:03}',character_id=99000000+i)
        data['report']['participants'].append(row)
    original=deepcopy(data)
    doc=PdfReader(BytesIO(render_pdf(data,'Anonymous','2.0.0','2026-10-29T06:00:00+00:00')))
    words='\n'.join(p.extract_text() for p in doc.pages)
    for phrase in ['Team summary','Ship composition','Third parties','Involved pilots and damage','Example Pilot 084','Loss timeline','Drake','80.0%','Generated by EVE Quartermaster v2.0.0 by Anonymous']:
        assert phrase in words,phrase
    assert len(doc.pages)>2 and data==original


def test_migration_preserves_unattributed_historical_rows():
    path=Path(__file__).resolve().parents[1]/'alembic/versions/0094_battle_report_corporation.py'
    spec=importlib.util.spec_from_file_location('migration0094',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE battle_report_shares (id INTEGER PRIMARY KEY, share_token VARCHAR(64), is_private BOOLEAN)'))
        conn.execute(text("INSERT INTO battle_report_shares VALUES (1,'legacy',0),(2,'private',1)"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            assert conn.execute(text('SELECT corporation_id FROM battle_report_shares')).all()==[(None,),(None,)]
            assert 'ix_battle_report_shares_corporation_id' in {i['name'] for i in inspect(conn).get_indexes('battle_report_shares')}
            module.downgrade()
            assert conn.execute(text('SELECT COUNT(*) FROM battle_report_shares')).scalar()==2
            assert 'corporation_id' not in {c['name'] for c in inspect(conn).get_columns('battle_report_shares')}
    engine.dispose()
