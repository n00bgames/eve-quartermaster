from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, inspect, create_engine, text
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.api import auth, esi, account_sso as sso
from app.core.config import get_settings
from app.core.security import create_session_token, decrypt_secret, encrypt_secret, generate_key, hash_password
from app.models import AccountSsoAttempt, EsiToken, EveCharacter, User, UserInvite, Asset, CharacterSkill
from app.services.permissions import assigned_roles
from tests.test_local_scan import env


@pytest.fixture
def login(env):
    settings=get_settings().model_copy(update={'frontend_url':'http://testserver','eve_sso_client_id':'test-client',
        'eve_sso_client_secret':'test-secret','token_encryption_key':generate_key(),
        'eve_sso_callback_url':'http://testserver/api/esi/auth/callback'})
    env.app.include_router(auth.router,prefix='/api')
    env.app.include_router(sso.router,prefix='/api')
    env.app.include_router(esi.router,prefix='/api')
    env.app.dependency_overrides.pop(auth.get_current_user)
    password=hash_password('test-password')
    for user in env.users.values():user.password_hash=password
    for token in env.db.scalars(select(EsiToken)):
        token.sso_owner_hash='original-owner'
        token.encrypted_refresh_token=encrypt_secret('existing-refresh',settings.token_encryption_key)
    env.db.commit()
    with patch.object(sso,'get_settings',return_value=settings), patch.object(auth,'get_settings',return_value=settings), \
         patch.object(esi,'get_settings',return_value=settings):
        env.settings=settings
        yield env


def start(login, **payload):
    response=login.client.post('/api/auth/sso/start',json=payload)
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='no-store'
    return parse_qs(urlsplit(response.json()['url']).query)['state'][0],response


def own(login, role='member'):
    char=login.db.scalar(select(EveCharacter).where(EveCharacter.owner_user_id==login.users[role].id))
    return char.character_id


def claims(eve_id=99001,owner='original-owner'):
    return {'sub':f'CHARACTER:EVE:{eve_id}','owner':owner,'name':'Example Invited Pilot','scp':['publicData']}


def finish(login,state,identity=None,payload=None,**query):
    body=payload or {'access_token':'mock-eve-access','refresh_token':'mock-eve-refresh','scope':'publicData','expires_in':1200}
    with patch.object(sso,'exchange',new=AsyncMock(return_value=(body, identity or claims()))):
        return login.client.get('/api/esi/auth/callback',params={'state':state,'code':'single-use-code',**query},follow_redirects=False)


def invite(login,email='new@example.test',roles=None):
    response=login.client.post('/api/auth/invites',json={'email':email,'roles':roles or ['quartermaster','intel_analyst']},
        headers={'Authorization':'Bearer '+create_session_token(login.users['admin'])})
    assert response.status_code==200,response.text
    return parse_qs(urlsplit(response.json()['invite_url']).query)['invite'][0]


def test_start_requests_only_identity_and_binds_pkce_to_browser(login):
    state,response=start(login)
    query=parse_qs(urlsplit(response.json()['url']).query)
    assert query['scope']==['publicData'] and query['code_challenge_method']==['S256']
    row=login.db.get(AccountSsoAttempt,sso.digest(state))
    verifier=decrypt_secret(row.encrypted_verifier,login.settings.token_encryption_key)
    import base64
    assert query['code_challenge']==[base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')]
    assert state not in str(row.__dict__) and verifier not in str(row.__dict__)
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
    assert login.client.post('/api/auth/sso/start',json={'role':'host'}).status_code==422


@pytest.mark.parametrize('remember',[False,True])
def test_existing_link_login_cookie_only_and_single_use(login,remember):
    state,_=start(login,remember_me=remember)
    browser=login.client.cookies.get(sso.FLOW_COOKIE)
    response=finish(login,state,claims(own(login)))
    assert response.status_code==303 and 'sso_status=signed_in' in response.headers['location']
    assert all(secret not in response.headers['location'] for secret in ['mock-eve-access','mock-eve-refresh','Bearer','eyJ'])
    me=login.client.get('/api/auth/me')
    assert me.status_code==200 and me.json()['id']==login.users['member'].id
    session_cookie=next(value for value in response.headers.get_list('set-cookie') if value.startswith(auth.REMEMBER_ME_COOKIE+'='))
    assert ('Max-Age=' in session_cookie)==remember
    assert 'HttpOnly' in session_cookie
    login.client.cookies.set(sso.FLOW_COOKIE,browser,path='/api')
    assert 'sso_error=' in finish(login,state,claims(own(login))).headers['location']


@pytest.mark.parametrize('invalid',['no_cookie','tampered','expired','cancelled'])
def test_invalid_attempt_never_exchanges_code(login,invalid):
    state,_=start(login)
    params={'state':state,'code':'single-use-code'}
    if invalid=='no_cookie':login.client.cookies.clear()
    if invalid=='tampered':params['state']=state+'x'
    if invalid=='expired':
        login.db.get(AccountSsoAttempt,sso.digest(state)).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);login.db.commit()
    if invalid=='cancelled':params={'state':state,'error':'access_denied'}
    with patch.object(sso,'exchange',new=AsyncMock()) as exchange:
        response=login.client.get('/api/esi/auth/callback',params=params,follow_redirects=False)
        assert 'sso_error=' in response.headers['location'] and exchange.await_count==0
    assert login.client.get('/api/auth/me').status_code==401


@pytest.mark.parametrize('invalid',['owner','revoked','deleted','forced_reset','unlinked'])
def test_login_rejects_transfer_revocation_deleted_and_unlinked(login,invalid):
    eid=own(login);token=login.db.scalar(select(EsiToken).where(EsiToken.user_id==login.users['member'].id))
    identity=claims(eid)
    if invalid=='owner':identity['owner']='transferred-owner'
    if invalid=='revoked':token.revoked_at=datetime.now(timezone.utc)
    if invalid=='deleted':login.users['member'].deleted_at=datetime.now(timezone.utc)
    if invalid=='forced_reset':login.users['member'].password_reset_required=True
    if invalid=='unlinked':identity=claims(999999)
    login.db.commit();state,_=start(login)
    assert 'sso_error=' in finish(login,state,identity).headers['location']
    assert login.client.get('/api/auth/me').status_code==401


@pytest.mark.parametrize('legacy_owner',['original-owner','transferred-owner'])
def test_legacy_links_require_refresh_token_ownership_proof(login,legacy_owner):
    eid=own(login);token=login.db.scalar(select(EsiToken).where(EsiToken.user_id==login.users['member'].id))
    token.sso_owner_hash=None;login.db.commit();state,_=start(login)
    with patch.object(esi,'refresh_access_token',new=AsyncMock(return_value='old-access')) as refresh, \
         patch.object(sso,'validate_eve_access_token',new=AsyncMock(return_value=claims(eid,legacy_owner))):
        response=finish(login,state,claims(eid))
    assert refresh.await_count==1
    assert ('sso_status=signed_in' in response.headers['location'])==(legacy_owner=='original-owner')
    login.db.refresh(token)
    assert token.sso_owner_hash==('original-owner' if legacy_owner=='original-owner' else None)


def test_legacy_refresh_error_is_safe_and_does_not_set_session(login):
    token=login.db.scalar(select(EsiToken).where(EsiToken.user_id==login.users['member'].id));token.sso_owner_hash=None;login.db.commit()
    state,_=start(login)
    with patch.object(esi,'refresh_access_token',new=AsyncMock(side_effect=HTTPException(400,{'private':'upstream-secret'}))):
        response=finish(login,state,claims(own(login)))
    assert 'sso_error=' in response.headers['location'] and 'upstream-secret' not in response.headers['location']
    assert login.client.get('/api/auth/me').status_code==401


def test_invite_creates_sso_account_with_only_invited_roles_and_identity(login):
    token=invite(login)
    inspected=login.client.get('/api/auth/invites/'+token).json()
    assert set(inspected['roles'])=={'quartermaster','intel_analyst'}
    state,_=start(login,invite_token=token)
    response=finish(login,state)
    assert 'sso_status=signed_in' in response.headers['location'],response.headers
    me=login.client.get('/api/auth/me').json()
    assert set(me['roles'])=={'quartermaster','intel_analyst'} and me['main_character_id']==99001
    user=login.db.get(User,me['id']);char=login.db.scalar(select(EveCharacter).where(EveCharacter.character_id==99001))
    saved=login.db.scalar(select(EsiToken).where(EsiToken.user_id==user.id))
    assert saved.scopes=='publicData' and saved.sso_owner_hash=='original-owner' and char.owner_user_id==user.id
    assert login.db.scalar(select(func.count()).select_from(Asset))==0
    assert login.db.scalar(select(func.count()).select_from(CharacterSkill))==0
    assert login.client.post('/api/auth/invites/'+token+'/accept',json={'display_name':'Attacker','password':'test-password'}).status_code==404
    login.client.post('/api/auth/logout')
    state,_=start(login)
    assert 'sso_status=signed_in' in finish(login,state).headers['location']


@pytest.mark.parametrize('invalid',['revoked','expired','accepted','inviter_demoted','role_deleted'])
def test_invite_is_revalidated_after_eve_authorization(login,invalid):
    token=invite(login);state,_=start(login,invite_token=token)
    row=login.db.scalar(select(UserInvite).where(UserInvite.token_hash==auth.hash_invite_token(token)))
    if invalid=='revoked':row.revoked_at=datetime.now(timezone.utc)
    if invalid=='expired':row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    if invalid=='accepted':row.accepted_at=datetime.now(timezone.utc)
    if invalid=='inviter_demoted':login.users['admin'].role='member'
    if invalid=='role_deleted':row.roles_json=['no-longer-existing']
    login.db.commit()
    assert 'sso_error=' in finish(login,state).headers['location']
    assert not login.db.scalar(select(User).where(User.email=='new@example.test'))


@pytest.mark.parametrize('collision',['character','email','excess_scopes','missing_owner'])
def test_invites_cannot_take_over_accounts_or_collect_extra_data(login,collision):
    token=invite(login);state,_=start(login,invite_token=token)
    identity=claims();payload={'access_token':'mock-access','refresh_token':'mock-refresh','scope':'publicData'}
    if collision=='character':identity=claims(own(login))
    if collision=='email':login.db.add(User(email='new@example.test',display_name='Existing',role='member',password_hash='existing'));login.db.commit()
    if collision=='excess_scopes':payload['scope']='publicData esi-assets.read_assets.v1'
    if collision=='missing_owner':identity.pop('owner')
    assert 'sso_error=' in finish(login,state,identity,payload).headers['location']
    assert login.client.get('/api/auth/me').status_code==401
    assert login.db.scalar(select(UserInvite).where(UserInvite.token_hash==auth.hash_invite_token(token))).accepted_at is None


def test_password_invitation_still_works_and_claim_is_single_use(login):
    token=invite(login)
    response=login.client.post('/api/auth/invites/'+token+'/accept',json={'display_name':'Password User','password':'new-password'})
    assert response.status_code==200,response.text
    assert set(response.json()['user']['roles'])=={'quartermaster','intel_analyst'}
    assert login.client.post('/api/auth/sso/start',json={'invite_token':token}).status_code==400


def test_sso_migration_roundtrip():
    path=Path(__file__).resolve().parents[1]/'alembic/versions/0098_account_sso.py'
    spec=importlib.util.spec_from_file_location('sso_migration',path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        for name in ('users','user_invites','esi_tokens'):connection.execute(text(f'CREATE TABLE {name} (id INTEGER PRIMARY KEY)'))
        with Operations.context(MigrationContext.configure(connection)):migration.upgrade()
        assert 'sso_owner_hash' in {c['name'] for c in inspect(connection).get_columns('esi_tokens')}
        assert 'account_sso_attempts' in inspect(connection).get_table_names()
        with Operations.context(MigrationContext.configure(connection)):migration.downgrade()
        assert 'account_sso_attempts' not in inspect(connection).get_table_names()


def test_exchange_sends_pkce_and_validates_eve_token(login):
    import asyncio
    response=type('Response',(),{'status_code':200,'json':lambda self:{'access_token':'verified-upstream'}})()
    client=AsyncMock();client.post.return_value=response
    with patch.object(sso.httpx,'AsyncClient') as factory, patch.object(sso,'validate_eve_access_token',new=AsyncMock(return_value=claims())) as validate:
        factory.return_value.__aenter__.return_value=client
        payload,identity=asyncio.run(sso.exchange('one-use-code','private-pkce-verifier'))
    validate.assert_awaited_once_with('verified-upstream')
    sent=client.post.call_args.kwargs['data']
    assert sent['code']=='one-use-code' and sent['code_verifier']=='private-pkce-verifier'
    assert sent['redirect_uri']==login.settings.eve_sso_callback_url and sent['client_id']==login.settings.eve_sso_client_id


@pytest.mark.parametrize('change',['revoke','retire','auth_version'])
def test_legacy_login_rechecks_account_after_external_refresh(login,change):
    token=login.db.scalar(select(EsiToken).where(EsiToken.user_id==login.users['member'].id));token.sso_owner_hash=None;login.db.commit()
    state,_=start(login);eid=own(login)
    async def refresh(row):
        if change=='revoke':row.revoked_at=datetime.now(timezone.utc)
        if change=='retire':login.users['member'].deleted_at=datetime.now(timezone.utc)
        if change=='auth_version':login.users['member'].auth_version+=1
        login.db.commit()
        return 'old-access'
    with patch.object(esi,'refresh_access_token',new=refresh), patch.object(sso,'validate_eve_access_token',new=AsyncMock(return_value=claims(eid))):
        response=finish(login,state,claims(eid))
    assert 'sso_error=' in response.headers['location']
    assert login.client.get('/api/auth/me').status_code==401
