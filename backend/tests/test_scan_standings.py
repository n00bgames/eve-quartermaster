import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.models import EsiToken, EveCharacter
from app.models.local_scan import ScanColorSettings
from app.services import scan_standings as source
from app.services.esi_scope_policy import allowed_scopes, private_collection_enabled, requested_scopes
from tests.test_local_scan import env, create
from tests.test_scan_colors import save
from tests.test_dscan import scan_env

RULES=[{'kind':'alliance','eve_id':201,'color':'blue'}, {'kind':'corporation','eve_id':101,'color':'orange'}, {'kind':'corporation','eve_id':102,'color':'gray'}]


def own_token(e, role='member', grant=True):
    token=e.db.scalar(select(EsiToken).where(EsiToken.user_id==e.users[role].id))
    if grant: token.scopes+=' '+source.CONTACT_SCOPE;e.db.commit()
    return token


@pytest.fixture
def mocked(env,monkeypatch):
    token=own_token(env)
    async def fetch(access,eve_id):
        assert not env.db.in_transaction(), 'Contact paging must not pin a DB transaction'
        return RULES
    monkeypatch.setattr('app.api.esi.refresh_access_token',AsyncMock(return_value='synthetic-access'))
    monkeypatch.setattr(source,'fetch_contacts',fetch)
    return env,token


def activate(e,token,base='/api/local-scans'):
    response=e.client.post(base+'/color-settings',json={'token_id':token.id})
    assert response.status_code==200,response.text
    return response.json()


def test_own_characters_persistence_colors_and_snapshot_privacy(mocked):
    e,token=mocked
    before=e.client.get('/api/local-scans/color-settings')
    assert 'no-store' in before.headers['cache-control']
    assert not before.json()['enabled'] and not before.json()['automatic_rules']
    assert {c['token_id'] for c in before.json()['characters']}=={token.id}
    settings=activate(e,token)
    assert settings['synced_at'].endswith('+00:00')
    assert settings['enabled'] and settings['source_name']=='Linked member' and settings['synced_at']
    assert e.client.get('/api/local-scans/color-settings').json()['automatic_rules']==RULES
    report=create(e)
    assert {p['name']:p['highlight_color'] for p in report['pilots']}=={'Alpha One':'orange','Beta Two':'gray','Gamma Three':'orange'}
    assert 'Linked member' not in str(report) and 'contact_colors' not in str(report)
    save(e,color='green')
    updated=create(e)
    assert next(p for p in updated['pilots'] if p['name']=='Alpha One')['highlight_color']=='green'
    save(e,'corporation','Red Corp','purple')
    assert next(p for p in create(e)['pilots'] if p['name']=='Alpha One')['highlight_color']=='purple'
    cleared=e.client.post('/api/local-scans/color-settings',json={'token_id':None}).json()
    assert not cleared['enabled'] and cleared['automatic_rules']==[]
    row=e.db.get(ScanColorSettings,e.users['member'].id)
    assert row.character_id is None and row.contact_colors==[]
    e.current[0]=None
    assert e.client.get('/api/local-scans/public/'+report['token']).json()['pilots']==report['pilots']
    assert e.client.get('/api/local-scans/color-settings').status_code==401


def test_even_admin_cannot_use_someone_elses_contacts(mocked):
    e,token=mocked
    for role in ('other','admin'):
        e.current[0]=e.users[role]
        assert e.client.post('/api/local-scans/color-settings',json={'token_id':token.id}).status_code==403
        assert e.client.get(f'/api/local-scans/color-settings/{token.id}/auth-url').status_code==403
        assert token.id not in {c['token_id'] for c in e.client.get('/api/local-scans/color-settings').json()['characters']}


def test_read_only_consent_for_intel_role_does_not_enable_collection(env,monkeypatch):
    e=env;e.current[0]=e.users['intel_analyst'];token=own_token(e,'intel_analyst',False)
    token.scopes+=' esi-fake.scope.v1';e.db.commit()
    assert source.CONTACT_SCOPE in allowed_scopes(e.db,e.current[0])
    assert not private_collection_enabled(e.db,e.current[0])
    assert requested_scopes(e.db,e.current[0],['publicData','esi-assets.read_assets.v1',source.CONTACT_SCOPE],'full')==['publicData']
    assert e.client.post('/api/local-scans/color-settings',json={'token_id':token.id}).status_code==409
    monkeypatch.setattr('app.api.esi.build_auth_url',lambda scopes,user,mode:{'scopes':scopes,'mode':mode})
    result=e.client.get(f'/api/local-scans/color-settings/{token.id}/auth-url').json()
    assert source.CONTACT_SCOPE in result['scopes']
    assert not any(s in result['scopes'] for s in ['esi-assets.read_assets.v1','esi-skills.read_skills.v1','esi-characters.write_contacts.v1','esi-fake.scope.v1'])
    char=e.db.get(EveCharacter,token.character_id)
    assert result['mode']==f'scan_contacts_{char.character_id}'
    source.validate_contacts_consent_character(e.db,e.current[0].id,result['mode'],char.character_id)
    with pytest.raises(HTTPException):source.validate_contacts_consent_character(e.db,e.current[0].id,result['mode'],char.character_id+1)
    assert not private_collection_enabled(e.db,e.current[0])


def test_failure_keeps_previous_cache_and_revocation_disables_use(mocked,monkeypatch):
    e,token=mocked;activate(e,token)
    monkeypatch.setattr(source,'fetch_contacts',AsyncMock(side_effect=ValueError('incomplete')))
    assert e.client.post('/api/local-scans/color-settings',json={'token_id':token.id}).status_code==502
    assert e.client.get('/api/local-scans/color-settings').json()['automatic_rules']==RULES
    token.revoked_at=datetime.now(timezone.utc);e.db.commit()
    result=e.client.get('/api/local-scans/color-settings').json()
    assert not result['enabled'] and result['source_unavailable'] and result['automatic_rules']==[]
    assert all(not p['highlighted'] for p in create(e)['pilots'])


def test_disable_during_refresh_cannot_be_overwritten(mocked,monkeypatch):
    e,token=mocked;activate(e,token)
    async def changed(access,eve_id):
        row=e.db.get(ScanColorSettings,e.users['member'].id)
        row.character_id=None;row.contact_colors=[];row.synced_at=None;row.revision+=1;e.db.commit()
        return RULES
    monkeypatch.setattr(source,'fetch_contacts',changed)
    assert e.client.post('/api/local-scans/color-settings',json={'token_id':token.id}).status_code==409
    assert not e.client.get('/api/local-scans/color-settings').json()['enabled']


@pytest.mark.parametrize('value,color',[(-10,'red'),(-5.1,'red'),(-5,'orange'),(-0.1,'orange'),(0,'gray'),(0.1,'light_blue'),(5,'light_blue'),(5.1,'blue'),(10,'blue')])
def test_standing_palette(value,color):
    assert source.standing_color(value)==color


def test_contact_reader_pages_and_discards_personal_contacts(monkeypatch):
    calls=[];closed=[]
    class Client:
        def __init__(self,access_token):assert access_token=='fixture'
        async def get_with_headers(self,path,params):
            calls.append((path,params))
            if params['page']==1:return ([{'contact_type':'character','contact_id':999,'standing':-10},{'contact_type':'corporation','contact_id':101,'standing':-5}],{'x-pages':'2'})
            return ([{'contact_type':'alliance','contact_id':201,'standing':10}],{'x-pages':'2'})
        async def close(self):closed.append(True)
    monkeypatch.setattr(source,'EsiClient',Client)
    rules=asyncio.run(source.fetch_contacts('fixture',9100))
    assert rules==[{'kind':'corporation','eve_id':101,'color':'orange'},{'kind':'alliance','eve_id':201,'color':'blue'}]
    assert [c[1]['page'] for c in calls]==[1,2] and closed==[True]


def test_dscan_settings_share_selected_character(scan_env,monkeypatch):
    e=scan_env;token=own_token(e)
    monkeypatch.setattr('app.api.esi.refresh_access_token',AsyncMock(return_value='fixture'))
    monkeypatch.setattr(source,'fetch_contacts',AsyncMock(return_value=RULES))
    assert activate(e,token,'/api/d-scans')['enabled']
    assert e.client.get('/api/local-scans/color-settings').json()['automatic_rules']==RULES


def test_source_payload_requires_explicit_selection_or_disable(env):
    assert env.client.post('/api/local-scans/color-settings',json={}).status_code==422


def test_dscan_consent_returns_to_dscan(scan_env,monkeypatch):
    e=scan_env;token=own_token(e)
    monkeypatch.setattr('app.api.esi.build_auth_url',lambda scopes,user,mode:{'scopes':scopes,'mode':mode})
    result=e.client.get(f'/api/d-scans/color-settings/{token.id}/auth-url').json()
    char=e.db.get(EveCharacter,token.character_id)
    assert result['mode']==f'scan_contacts_dscan_{char.character_id}'
    source.validate_contacts_consent_character(e.db,e.users['member'].id,result['mode'],char.character_id)
