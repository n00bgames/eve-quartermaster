import base64
from io import BytesIO
import importlib.util
from pathlib import Path
import pytest
from PIL import Image
from sqlalchemy import select,inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_local_scan import env
from app.api import appearance
from app.models import AuditEvent
from app.models.appearance import UserAppearance,SiteBranding

@pytest.fixture
def app(env):
    env.app.include_router(appearance.router,prefix='/api')
    return env

def image(format='PNG'):
    out=BytesIO();Image.new('RGB',(80,30),(40,100,180)).save(out,format=format)
    return base64.b64encode(out.getvalue()).decode()

@pytest.mark.parametrize('role',['host','admin','director','member','intel_analyst','quartermaster','applicant'])
def test_own_preferences_and_isolation(app,role):
    app.current[0]=app.users[role]
    assert app.client.get('/api/appearance/me').json()['preferences']=={}
    payload={'revision':0,'navigation':[{'id':'ops','name':'My operations','modules':['navigation','local_scan']}],'layouts':{'overview':['one','two']}}
    saved=app.client.patch('/api/appearance/me',json=payload)
    assert saved.status_code==200,saved.text
    assert saved.json()['revision']==1
    app.current[0]=app.users['other']
    assert app.client.get('/api/appearance/me').json()['preferences']=={}
    app.current[0]=None
    assert app.client.get('/api/appearance/me').status_code==401
    assert app.client.patch('/api/appearance/me',json=payload).status_code==401
    assert app.client.put('/api/appearance/me/banner',json={'revision':0,'image':image()}).status_code==401

def test_revision_merge_reset_and_banner(app):
    assert app.client.patch('/api/appearance/me',json={'revision':2,'layouts':{}}).status_code==409
    p=app.client.patch('/api/appearance/me',json={'revision':0,'layouts':{'overview':['a','b']}}).json()
    assert app.client.patch('/api/appearance/me',json={'revision':0,'layouts':{}}).status_code==409
    p=app.client.put('/api/appearance/me/banner',json={'revision':p['revision'],'image':image()}).json()
    assert p['preferences']['layouts']['overview']==['a','b'] and p['banner'].startswith('data:image/webp;base64,')
    p=app.client.patch('/api/appearance/me',json={'revision':p['revision'],'layouts':None}).json()
    assert p['preferences']=={} and p['banner']
    p=app.client.put('/api/appearance/me/banner',json={'revision':p['revision'],'image':None}).json()
    assert p['banner'] is None

@pytest.mark.parametrize('patch',[
 {'unknown':'x'},{'user_id':1},{'navigation':[{'id':'x','name':'x','modules':['not-real']}]},
 {'navigation':[{'id':'x','name':'x','modules':['overview','overview']}]},
 {'navigation':[{'id':'x','name':'x','modules':[]},{'id':'x','name':'y','modules':[]}]},
 {'layouts':{'../invalid':['x']}},{'layouts':{'x':['a','a']}},{'layouts':{str(i):[] for i in range(151)}},
 {'theme':{'background':'url(https://evil)','panel':'#111111','text':'#ffffff','muted':'#aaaaaa','accent':'#ffff00','border':'#555555'}},
 {'theme':{'background':'#111111','panel':'#111111','text':'#111111','muted':'#aaaaaa','accent':'#ffff00','border':'#555555'}},
])
def test_invalid_preferences(app,patch):
    assert app.client.patch('/api/appearance/me',json={'revision':0,**patch}).status_code==422
    assert app.client.get('/api/appearance/me').json()['revision']==0

@pytest.mark.parametrize('format',['PNG','JPEG','WEBP'])
def test_image_reencoded_and_public_brand_only(app,format):
    app.client.put('/api/appearance/me/banner',json={'revision':0,'image':image(format)})
    assert app.client.get('/api/appearance/branding/banner').status_code==404
    app.current[0]=app.users['admin']
    saved=app.client.put('/api/appearance/branding/banner',json={'revision':0,'image':image(format)})
    assert saved.status_code==200,saved.text
    assert saved.json()['banner'].endswith('/appearance/branding/banner?v=1')
    assert app.db.scalar(select(AuditEvent).where(AuditEvent.event_kind=='site_branding_updated'))
    app.current[0]=None
    response=app.client.get(saved.json()['banner'])
    assert response.status_code==200 and response.headers['content-type']=='image/webp'
    assert response.headers['cache-control']=='no-store' and response.headers['x-content-type-options']=='nosniff'
    with Image.open(BytesIO(response.content)) as decoded:
        assert decoded.format=='WEBP' and decoded.size==(80,30) and not decoded.getexif()
    assert 'data:' not in str(app.client.get('/api/appearance/branding').json())

@pytest.mark.parametrize('role',['member','director','quartermaster','intel_analyst','applicant'])
def test_site_branding_requires_admin(app,role):
    app.current[0]=app.users[role]
    assert app.client.put('/api/appearance/branding/banner',json={'revision':0,'image':image()}).status_code==403

def test_branding_reset_concurrency_and_slots(app):
    app.current[0]=app.users['host']
    assert app.client.put('/api/appearance/branding/login_background',json={'revision':0,'image':image()}).status_code==200
    assert app.client.put('/api/appearance/branding/banner',json={'revision':0,'image':image()}).status_code==409
    p=app.client.put('/api/appearance/branding/banner',json={'revision':1,'image':image()}).json()
    assert p['login_background'] and p['banner']
    p=app.client.put('/api/appearance/branding/banner',json={'revision':2,'image':None}).json()
    assert p['login_background'] and p['banner'] is None
    assert app.client.get('/api/appearance/branding/personal').status_code==422

@pytest.mark.parametrize('encoded',['!!!',base64.b64encode(b'<svg onload="alert(1)"/>').decode(),base64.b64encode(b'X'*(5*1024*1024+1)).decode()],ids=['base64','svg','oversize'])
def test_invalid_images(app,encoded):
    assert app.client.put('/api/appearance/me/banner',json={'revision':0,'image':encoded}).status_code==422
    assert app.client.get('/api/appearance/me').json()['revision']==0

def test_oversized_dimensions_and_resize(app):
    out=BytesIO();Image.new('RGB',(5000,4100)).save(out,format='PNG')
    assert app.client.put('/api/appearance/me/banner',json={'revision':0,'image':base64.b64encode(out.getvalue()).decode()}).status_code==422
    out=BytesIO();Image.new('RGB',(3000,1500)).save(out,format='PNG')
    p=app.client.put('/api/appearance/me/banner',json={'revision':0,'image':base64.b64encode(out.getvalue()).decode()}).json()
    with Image.open(BytesIO(base64.b64decode(p['banner'].split(',')[1]))) as decoded:assert decoded.size==(2560,1280)

def test_migration_round_trip(app):
    engine=app.db.get_bind();app.db.commit()
    UserAppearance.__table__.drop(engine);SiteBranding.__table__.drop(engine)
    path=Path(__file__).parents[1]/'alembic/versions/0095_appearance.py'
    spec=importlib.util.spec_from_file_location('appearance_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();assert 'user_appearance' in inspect(connection).get_table_names()
            module.downgrade();assert 'user_appearance' not in inspect(connection).get_table_names()
            assert 'users' in inspect(connection).get_table_names()
            module.upgrade()

def test_quartermaster_real_auth_only_allows_personal_appearance(app):
    from app.api.auth import get_current_user
    from app.core.security import create_access_token
    from app.services.permissions import effective_permissions
    user=app.users['quartermaster'];before=effective_permissions(user,app.db)
    app.app.dependency_overrides.pop(get_current_user)
    headers={'Authorization':'Bearer '+create_access_token(str(user.id))}
    assert app.client.patch('/api/appearance/me',json={'revision':0,'layouts':{'overview':['a']}},headers=headers).status_code==200
    assert app.client.put('/api/appearance/me/banner',json={'revision':1,'image':image()},headers=headers).status_code==200
    assert app.client.put('/api/appearance/branding/banner',json={'revision':0,'image':image()},headers=headers).status_code==403
    assert app.client.post('/api/local-scans',json={'text':'Alpha One','retention':'24h'},headers=headers).status_code==403
    assert effective_permissions(user,app.db)==before

@pytest.mark.parametrize('role',['host','intel_analyst','quartermaster'])
def test_quicklaunch_links_round_trip_without_granting_permissions(app,role):
    from app.services.permissions import effective_permissions
    user=app.users[role];app.current[0]=user
    before=effective_permissions(user,app.db)
    groups=[{'id':'quick','name':'Quicklaunch','modules':['navigation','market']},
            {'id':'main','name':'General','modules':['navigation']},
            {'id':'finance','name':'Finance','modules':['market']}]
    saved=app.client.patch('/api/appearance/me',json={'revision':0,'navigation':groups})
    assert saved.status_code==200,saved.text
    assert app.client.get('/api/appearance/me').json()['preferences']['navigation']==groups
    assert effective_permissions(user,app.db)==before
    groups[0]['modules'].remove('market')
    assert app.client.patch('/api/appearance/me',json={'revision':1,'navigation':groups}).status_code==200
    assert app.client.get('/api/appearance/me').json()['preferences']['navigation']==groups
    app.current[0]=app.users['other']
    assert app.client.get('/api/appearance/me').json()['preferences']=={}
