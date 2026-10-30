import asyncio
from types import SimpleNamespace
from datetime import datetime,timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api import client_links as links
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base,User,EveCharacter,EsiToken,EveType,Asset,Blueprint,OwnershipEntity
from app.models.enums import OwnerKind
from app.services.esi_scope_policy import allowed_scopes,private_collection_enabled,requested_scopes

@pytest.fixture
def env(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db=Session(engine,expire_on_commit=False)
    user=User(display_name='demo',email='demo@example.invalid',password_hash='not-a-login',role='member')
    other=User(display_name='other',email='other@example.invalid',password_hash='not-a-login',role='member')
    db.add_all([user,other]);db.flush()
    chars=[EveCharacter(character_id=90000000+i,name=f'Demo Pilot {i}',owner_user_id=u.id) for i,u in enumerate([user,user,other])]
    db.add_all(chars);db.flush()
    tokens=[EsiToken(user_id=c.owner_user_id,character_id=c.id,scopes='publicData'+(' '+links.UI_SCOPE if i!=1 else ''),encrypted_refresh_token='fixture') for i,c in enumerate(chars)]
    db.add_all(tokens)
    types=[EveType(type_id=100,name='Demo Blueprint'),EveType(type_id=101,name='A "Quoted" & <Item>')]
    db.add_all(types)
    owners=[OwnershipEntity(owner_kind=OwnerKind.CHARACTER,display_name=c.name,character_id=c.id) for c in [chars[0],chars[2]]]
    db.add_all(owners);db.flush()
    assets=[Asset(ownership_entity_id=o.id,type_id=100,eve_item_id=1000000000000001+i,quantity=1,is_singleton=True) for i,o in enumerate(owners)]
    db.add_all(assets);db.flush()
    bp=Blueprint(asset_id=assets[0].id,ownership_entity_id=owners[0].id,blueprint_type_id=100,material_efficiency=10,time_efficiency=20,is_copy=True,runs_remaining=7)
    db.add(bp);db.commit()
    calls=[]
    class Client:
        def __init__(self,access_token=None):pass
        async def post(self,path,payload):calls.append((path,payload))
        async def close(self):pass
    async def refresh(token):return 'synthetic-access'
    monkeypatch.setattr(links,'EsiClient',Client)
    monkeypatch.setattr('app.api.esi.refresh_access_token',refresh)
    app=FastAPI();app.include_router(links.router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:user
    with TestClient(app) as client:yield SimpleNamespace(db=db,user=user,other=other,chars=chars,tokens=tokens,owners=owners,assets=assets,bp=bp,calls=calls,client=client,app=app)
    db.close();engine.dispose()

def post(e,**kw):return e.client.post('/client-links/draft',json={'token_id':e.tokens[0].id,**kw})

def test_only_own_characters_and_revocations(env):
    e=env
    assert [c['can_open'] for c in e.client.get('/client-links/characters').json()['characters']]==[True,False]
    e.user.role='admin';e.db.commit()
    assert post(e,token_id=e.tokens[2].id,type_id=100).status_code==403
    e.chars[0].owner_user_id=e.other.id;e.db.commit()
    assert post(e,type_id=100).status_code==403
    e.chars[0].owner_user_id=e.user.id;e.tokens[0].revoked_at=datetime.now(timezone.utc);e.db.commit()
    assert post(e,type_id=100).status_code==404
    assert not e.calls

def test_no_scope_no_draft_and_no_private_consent_for_utilities(env,monkeypatch):
    e=env
    assert post(e,token_id=e.tokens[1].id,type_id=100).status_code==409
    for role in ['intel_analyst','quartermaster','fleet_commander']:
        e.user.role=role;e.db.commit()
        assert links.UI_SCOPE in allowed_scopes(e.db,e.user)
        assert not private_collection_enabled(e.db,e.user)
        assert requested_scopes(e.db,e.user,['publicData','esi-assets.read_assets.v1'],'full')==['publicData']
    monkeypatch.setattr('app.api.esi.build_auth_url',lambda scopes,user,mode:{'scopes':scopes,'mode':mode})
    response=e.client.get(f'/client-links/characters/{e.tokens[1].id}/auth-url')
    assert response.json()=={'scopes':[links.UI_SCOPE,'publicData'],'mode':f'client_ui_{e.chars[1].character_id}'}
    assert not e.calls

def test_consent_keeps_only_existing_permitted_scopes(env,monkeypatch):
    e=env;e.tokens[0].scopes+=' esi-assets.read_assets.v1 esi-fake.scope.v1';e.db.commit()
    monkeypatch.setattr('app.api.esi.build_auth_url',lambda scopes,user,mode:{'scopes':scopes})
    scopes=e.client.get(f'/client-links/characters/{e.tokens[0].id}/auth-url').json()['scopes']
    assert 'esi-assets.read_assets.v1' in scopes and 'esi-fake.scope.v1' not in scopes
    assert e.client.get(f'/client-links/characters/{e.tokens[2].id}/auth-url').status_code==403

def test_blueprint_instance_uses_server_details_and_exact_integer_id(env):
    e=env;r=post(e,blueprint_id=e.bp.id,type_id=101,name='forged')
    assert r.status_code==200 and r.json()['instance_link']
    path,body=e.calls[-1]
    assert path=='/ui/openwindow/newmail/' and body['recipients']==[e.chars[0].character_id]
    assert f'showinfo:100//{e.assets[0].eve_item_id}' in body['body']
    assert 'BPC · ME 10 · TE 20 · Runs remaining: 7' in body['body']
    e.bp.is_copy=False;e.bp.runs_remaining=None;e.db.commit()
    assert post(e,asset_id=e.assets[0].id).status_code==200
    assert 'BPO · ME 10 · TE 20' in e.calls[-1][1]['body']
    assert 'Runs remaining' not in e.calls[-1][1]['body']

def test_no_private_instance_disclosure_or_spoofing(env):
    e=env
    assert post(e,asset_id=e.assets[1].id).status_code==404
    assert post(e,blueprint_id=999).status_code==404
    for extra in [{'eve_item_id':123},{'recipients':[1]},{'body':'injected'},{'me':99}]:
        assert post(e,type_id=100,**extra).status_code==422
    assert not e.calls

def test_generic_links_escape_eve_html_and_use_exact_type_names(env):
    e=env
    assert post(e,name='a "quoted" & <item>').status_code==200
    body=e.calls[-1][1]['body']
    assert '<url=showinfo:101>A "Quoted" &amp; &lt;Item&gt;</url>' in body
    assert '&quot;' not in body and 'showinfo:101//' not in body
    assert post(e,name='unknown item').status_code==404
    assert post(e,type_id='100').status_code==422

def test_manual_blueprint_without_item_id_falls_back_and_support_is_unsent(env):
    e=env;e.bp.asset_id=None;e.db.commit()
    r=post(e,blueprint_id=e.bp.id)
    assert r.status_code==200 and not r.json()['instance_link']
    assert '<url=showinfo:100>' in e.calls[-1][1]['body']
    assert post(e,kind='support').status_code==200
    path,payload=e.calls[-1]
    assert payload['recipients']==[e.chars[0].character_id]
    assert 'showinfo:1377//502978494' in payload['body'] and '#ff00ff00' in payload['body']
    assert all(path=='/ui/openwindow/newmail/' for path,payload in e.calls)

def test_upstream_failure_rechecks_permission_and_does_not_retry(env,monkeypatch):
    from fastapi import HTTPException
    e=env
    class Fail:
        def __init__(self,access_token=None):pass
        async def close(self):pass
        async def post(self,path,payload):e.calls.append((path,payload));raise HTTPException(500,'unavailable')
    monkeypatch.setattr(links,'EsiClient',Fail)
    assert post(e,type_id=100).status_code==502 and len(e.calls)==1
    async def revoke(token):token.revoked_at=datetime.now(timezone.utc);return 'synthetic'
    monkeypatch.setattr('app.api.esi.refresh_access_token',revoke)
    assert post(e,type_id=100).status_code==404 and len(e.calls)==1


def test_preview_reads_canonical_instance_without_opening_game(env):
    e=env
    response=e.client.post('/client-links/preview',json={'blueprint_id':e.bp.id})
    assert response.status_code==200 and response.json()['instance_link']
    assert 'BPC · ME 10 · TE 20 · Runs remaining: 7' in response.json()['details']
    assert not e.calls

def test_real_auth_permits_quartermaster_drafts_but_not_other_mutations(env):
    from app.core.security import create_session_token
    e=env;e.user.role='quartermaster';e.db.commit()
    e.app.dependency_overrides.pop(get_current_user)
    e.client.headers['Authorization']='Bearer '+create_session_token(e.user)
    assert post(e,type_id=100).status_code==200
    assert e.client.post('/client-links/preview',json={'type_id':100}).status_code==200

def test_ui_consent_is_bound_to_selected_existing_character(env):
    from fastapi import HTTPException
    e=env;mode=f'client_ui_{e.chars[0].character_id}'
    links.validate_ui_consent_character(e.db,e.user.id,mode,e.chars[0].character_id)
    for uid,selected,eid in [(e.user.id,mode,e.chars[2].character_id),(e.other.id,mode,e.chars[0].character_id),(e.user.id,'client_ui_bad',e.chars[0].character_id)]:
        with pytest.raises(HTTPException):links.validate_ui_consent_character(e.db,uid,selected,eid)
    assert e.chars[0].owner_user_id==e.user.id
