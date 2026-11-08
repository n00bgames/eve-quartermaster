"""Owned structures: authorization boundaries, partial ESI and timer semantics."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import structures as api
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, EsiToken, EveCharacter, EveCorporation, EveSystem, EveType, User, UserSectionPermission
from app.services import structures as service
from app.services.esi_scope_policy import allowed_scopes


UPWELL={"structure_id":1000000000001,"type_id":35832,"system_id":30000142,"corporation_id":101,"profile_id":1,"state":"hull_reinforce","name":"Demo Keep","state_timer_end":"2026-11-09T12:00:00Z","fuel_expires":"2026-11-20T00:00:00Z","reinforce_hour":0,"next_reinforce_hour":1,"services":[{"name":"Market","state":"online"}]}
POS={"starbase_id":1000000000002,"type_id":12235,"system_id":30000142,"moon_id":40000001,"state":"reinforced","reinforced_until":"2026-11-09T09:00:00Z","unanchor_at":"2026-11-08T09:00:00Z"}


class Source:
    def __init__(self):
        self.calls=[];self.fail={};self.upwell=[UPWELL];self.pos=[POS];self.corporation_id=101
        self.fuels=[{"type_id":4247,"quantity":1234},{"type_id":16275,"quantity":0}]
    async def close(self):pass
    async def get(self,path,params=None):
        self.calls.append((path,params));return {"corporation_id":self.corporation_id}
    async def get_with_headers(self,path,params=None):
        self.calls.append((path,params))
        if path in self.fail:raise HTTPException(self.fail[path],"private upstream detail")
        if path.endswith('/structures/'):value=self.upwell
        elif path.endswith('/starbases/'):value=self.pos
        else:value={"fuels":self.fuels,"allow_corporation_members":True,"attack_if_at_war":False,"fuel_bay_view":"starbase_fuel_technician_role"}
        return value,httpx.Headers({"date":"Sun, 08 Nov 2026 10:00:00 GMT","x-pages":"1","cache-control":"max-age=3600"})


@pytest.fixture
def env(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);db=Session(engine,expire_on_commit=False)
    users={role:User(email=role+'@invalid.test',display_name=role,role=role) for role in ('director','admin','member')}
    db.add_all(users.values());db.flush()
    corp=EveCorporation(corporation_id=101,name='Demo Corporation');db.add(corp);db.flush()
    tokens={};characters={}
    for index,(role,user) in enumerate(users.items()):
        character=EveCharacter(character_id=90000001+index,name='Demo '+role,owner_user_id=user.id,corporation_id=corp.id)
        db.add(character);db.flush();characters[role]=character
        token=EsiToken(user_id=user.id,character_id=character.id,scopes='publicData '+' '.join(service.SCOPES),encrypted_refresh_token='fixture')
        db.add(token);db.flush();tokens[role]=token
    db.add_all([EveSystem(system_id=30000142,name='Demo System'),EveType(type_id=4247,name='Amarr Fuel Block'),EveType(type_id=16275,name='Strontium Clathrates')]);db.commit()
    source=Source();monkeypatch.setattr(api,'EsiClient',lambda **kwargs:source)
    refresh=AsyncMock(return_value='transient-fixture');monkeypatch.setattr(api,'refresh_access_token',refresh)
    current=[users['director']];app=FastAPI();app.include_router(api.router,prefix='/api')
    app.dependency_overrides[get_current_user]=lambda:current[0]
    def database():
        try:yield db
        finally:db.rollback()
    app.dependency_overrides[get_db]=database
    with TestClient(app) as client:yield SimpleNamespace(client=client,db=db,current=current,users=users,tokens=tokens,characters=characters,source=source,refresh=refresh)
    db.close();engine.dispose()


def path(e,suffix=''):return f'/api/structures/tokens/{e.tokens["director"].id}'+suffix


def test_links_own_only_and_scope_eligibility(env):
    data=env.client.get('/api/structures/links');assert data.status_code==200
    assert data.headers['cache-control']=='private, no-store'
    assert data.json()['characters']==[{"token_id":env.tokens['director'].id,"character_name":"Demo director","corporation_name":"Demo Corporation","upwell_authorized":True,"pos_authorized":True}]
    assert not env.source.calls and not env.refresh.called


def test_overview_both_kinds_and_exact_fields(env):
    r=env.client.get(path(env));assert r.status_code==200,r.text;data=r.json()
    assert data['complete'] and len(data['rows'])==2 and data['corporation']['id']==101
    up=next(row for row in data['rows'] if row['kind']=='upwell');pos=next(row for row in data['rows'] if row['kind']=='pos')
    assert up['state_timer_end']==UPWELL['state_timer_end'] and up['reinforce_hour']==0
    assert up['services']==UPWELL['services'] and up['fuel_expires']==UPWELL['fuel_expires']
    assert pos['reinforced_until']==POS['reinforced_until'] and pos['unanchor_at']==POS['unanchor_at']
    assert 'fuel_expires' not in pos and 'unanchors_at' not in pos
    assert data['sources'][0]['pages'][0]['response_date'].endswith('GMT')
    assert not env.db.new and not env.db.dirty
    assert env.client.get(path(env)).headers['cache-control']=='private, no-store'


@pytest.mark.parametrize('role',['member','admin'])
def test_staff_cannot_use_other_accounts_tokens(env,role):
    env.current[0]=env.users[role]
    expected=403 if role=='member' else 404
    for suffix in ('','/auth-url',f'/pos/{POS["starbase_id"]}'):
        assert env.client.get(path(env,suffix)).status_code==expected
    assert not env.refresh.called and not env.source.calls


def test_disabled_section_revocation_transfer_and_missing_scopes(env):
    e=env;e.db.add(UserSectionPermission(user_id=e.users['director'].id,section='structures',can_view=False));e.db.commit()
    assert e.client.get(path(e)).status_code==403
    e.db.query(UserSectionPermission).delete();e.db.commit()
    e.tokens['director'].revoked_at=__import__('datetime').datetime.now();e.db.commit()
    assert e.client.get(path(e)).status_code==404
    e.tokens['director'].revoked_at=None;e.characters['director'].owner_user_id=e.users['member'].id;e.db.commit()
    assert e.client.get(path(e)).status_code==404
    e.characters['director'].owner_user_id=e.users['director'].id;e.tokens['director'].scopes='publicData';e.db.commit()
    assert e.client.get(path(e)).status_code==409 and not e.refresh.called


@pytest.mark.parametrize('status',[401,403,420,429,500])
def test_failed_source_does_not_hide_other_source_or_claim_empty(env,status):
    env.source.fail['/corporations/101/structures/']=status
    r=env.client.get(path(env));assert r.status_code==200;data=r.json()
    assert not data['complete'] and len(data['rows'])==1
    assert data['sources'][0]['status']!='ok' and data['sources'][1]['status']=='ok'
    assert 'private upstream' not in str(data)


def test_missing_pos_scope_and_empty_lists_are_different(env):
    env.tokens['director'].scopes=service.UPWELL_SCOPE;env.db.commit();env.source.upwell=[]
    data=env.client.get(path(env)).json()
    assert data['sources'][1]['status']=='missing_scope' and not data['complete'] and data['rows']==[]
    env.tokens['director'].scopes=' '.join(service.SCOPES);env.db.commit();env.source.pos=[]
    data=env.client.get(path(env)).json();assert data['complete'] and data['rows']==[]


def test_current_corporation_is_used_instead_of_stale_link(env):
    env.source.corporation_id=202
    data=env.client.get(path(env)).json();assert data['corporation']['id']==202
    assert all('/corporations/101/' not in call[0] for call in env.source.calls)


def test_pos_fuels_zero_quantity_and_server_derived_system(env):
    r=env.client.get(path(env,f'/pos/{POS["starbase_id"]}'));assert r.status_code==200,r.text
    assert r.json()['fuels']==[{"type_id":4247,"name":"Amarr Fuel Block","quantity":1234},{"type_id":16275,"name":"Strontium Clathrates","quantity":0}]
    assert env.source.calls[-1][1]=={'system_id':30000142}
    assert env.client.get(path(env,'/pos/999')).status_code==404
    assert not any('/starbases/999/' in call[0] for call in env.source.calls)


@pytest.mark.parametrize('fuels',[None,[]])
def test_unknown_fuel_and_empty_fuel_preserved(env,fuels):
    env.source.fuels=fuels
    r=env.client.get(path(env,f'/pos/{POS["starbase_id"]}'));assert r.status_code==200,r.text
    assert r.json()['fuels']==fuels


def test_paginated_all_or_nothing_and_dedup():
    calls=[]
    async def get(path,params):
        calls.append(params['page']);return ([UPWELL] if params['page']==1 else [UPWELL,{**UPWELL,'structure_id':1000000000003}]),httpx.Headers({'x-pages':'2'})
    client=SimpleNamespace(get_with_headers=get)
    rows,meta=asyncio.run(service.pages(client,'/corporations/101/structures/'))
    assert calls==[1,2] and len(rows)==2 and len(meta)==2
    async def failed(path,params):
        if params['page']==2:raise HTTPException(503,'failure')
        return [UPWELL],httpx.Headers({'x-pages':'2'})
    client.get_with_headers=failed
    source=asyncio.run(service.fetch_source(client,101,'upwell',service.SCOPES))
    assert source['rows']==[] and source['status']=='error'


def test_consent_preserves_granted_scopes_and_checks_character(env,monkeypatch):
    from app.api import esi
    monkeypatch.setattr(esi,'build_auth_url',lambda scopes,user,mode:{'scopes':scopes,'mode':mode})
    env.tokens['director'].scopes+=' esi-assets.read_assets.v1';env.db.commit()
    r=env.client.get(path(env,'/auth-url'));assert r.status_code==200,r.text
    assert set(r.json()['scopes'])==service.SCOPES|{'publicData','esi-assets.read_assets.v1'}
    mode=r.json()['mode'];assert mode=='owned_structures_'+str(env.characters['director'].character_id)
    api.validate_consent_character(env.db,env.users['director'].id,mode,env.characters['director'].character_id)
    with pytest.raises(HTTPException):api.validate_consent_character(env.db,env.users['director'].id,mode,999)
    assert service.POS_SCOPE not in allowed_scopes(env.db,env.users['member'])


def test_navigation_accepts_structure_module():
    from app.api.appearance import PreferencesPatch
    PreferencesPatch(revision=0,navigation=[{'id':'industry','name':'Industry','modules':['structures','corporations']}])
