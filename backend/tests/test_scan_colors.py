import importlib.util
from pathlib import Path
from io import BytesIO
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy import text, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pypdf import PdfReader

from app.models.local_scan import ScanHighlight
from app.services.scan_colors import PALETTE, pilot_color
from tests.test_local_scan import env, create
from tests.test_dscan import scan_env, generate


def save(env, kind='alliance', name='Red Alliance', color='blue', base='/api/local-scans'):
    response=env.client.post(base+'/highlights',json=dict(kind=kind,name=name,color=color))
    assert response.status_code==200,response.text
    return response.json()


def test_persistence_updates_owner_isolation_and_validation(env):
    rule=save(env)
    assert rule['color']=='blue'
    env.db.expire_all()
    assert env.client.get('/api/local-scans/highlights').json()[0]['color']=='blue'
    changed=env.client.patch('/api/local-scans/highlights/'+str(rule['id']),json={'color':'orange'})
    assert changed.status_code==200 and changed.json()['color']=='orange'
    assert save(env,color='green')['id']==rule['id']
    assert env.client.patch('/api/local-scans/highlights/'+str(rule['id']),json={'color':'url(evil)'}).status_code==422
    env.current[0]=env.users['other']
    assert env.client.get('/api/local-scans/highlights').json()==[]
    assert env.client.patch('/api/local-scans/highlights/'+str(rule['id']),json={'color':'red'}).status_code==404
    env.current[0]=env.users['member']
    assert env.client.get('/api/local-scans/highlights').json()[0]['color']=='green'


def test_colors_snapshot_corporation_override_and_removal(env):
    alliance=save(env,color='blue')
    corp=save(env,'corporation','Red Corp','orange')
    report=create(env)
    pilot=next(p for p in report['pilots'] if p['name']=='Alpha One')
    assert (pilot['highlight_color'],pilot['corporation_highlight_color'],pilot['alliance_highlight_color'])==('orange','orange','blue')
    assert report['highlighted_count']==2
    env.client.delete('/api/local-scans/highlights/'+str(corp['id']))
    newer=create(env)
    assert next(p for p in newer['pilots'] if p['name']=='Alpha One')['highlight_color']=='blue'
    env.client.patch('/api/local-scans/highlights/'+str(alliance['id']),json={'color':'purple'})
    env.current[0]=None
    frozen=env.client.get('/api/local-scans/public/'+report['token']).json()
    assert frozen['pilots']==report['pilots']


@pytest.mark.parametrize('color',PALETTE)
def test_all_colors_and_pdf_labels(env,color):
    save(env,color=color)
    report=create(env)
    with patch('app.services.local_scan_pdf.logo_images',new=AsyncMock(return_value={})):
        response=env.client.get('/api/local-scans/public/'+report['token']+'/pdf')
    assert response.status_code==200,response.text
    pdf='\n'.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
    assert PALETTE[color][0] in pdf


def test_dscan_shares_rules_but_never_assigns_ship_owners(scan_env):
    env=scan_env
    rule=save(env,color='light_blue',base='/api/d-scans')
    assert env.client.patch('/api/d-scans/highlights/'+str(rule['id']),json={'color':'purple'}).status_code==200
    report=generate(env,local_text='Alpha One\nBeta Two')
    assert report['local_scan']['pilots'][0]['highlight_color']=='purple'
    assert all('highlight_color' not in row for row in report['rows'])
    with patch('app.services.dscan_pdf.report_images',new=AsyncMock(return_value={})):
        response=env.client.get('/api/d-scans/public/'+report['token']+'/pdf')
    assert response.status_code==200
    pdf='\n'.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
    assert 'EVE Purple' in pdf


def test_legacy_booleans_remain_red():
    assert pilot_color({'highlighted':True})=='red'
    assert pilot_color({'highlighted':False}) is None
    assert pilot_color({'alliance_highlighted':True},'alliance')=='red'


def test_existing_rules_remain_editable_at_limit(env):
    rule=save(env)
    env.db.add_all([ScanHighlight(user_id=env.users['member'].id,kind='corporation',eve_id=1000+i,name=f'Fixture {i}') for i in range(199)])
    env.db.commit()
    assert save(env,color='orange')['id']==rule['id']
    assert env.client.post('/api/local-scans/highlights',json={'kind':'corporation','name':'Red Corp','color':'green'}).status_code==422


def test_migration_backfills_existing_red_and_downgrades(env):
    # An isolated old-schema table avoids touching report snapshots or production.
    from sqlalchemy import create_engine
    engine=create_engine('sqlite://')
    path=Path(__file__).resolve().parents[1]/'alembic/versions/0101_scan_highlight_colors.py'
    spec=importlib.util.spec_from_file_location('color_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE scan_highlights (id INTEGER PRIMARY KEY, user_id INTEGER, kind VARCHAR(16), eve_id INTEGER, name VARCHAR(255))'))
        connection.execute(text("INSERT INTO scan_highlights VALUES (1,1,'alliance',201,'Existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.execute(text('SELECT color FROM scan_highlights')).scalar()=='red'
            migration.downgrade()
        assert 'color' not in {c['name'] for c in inspect(connection).get_columns('scan_highlights')}
    engine.dispose()
