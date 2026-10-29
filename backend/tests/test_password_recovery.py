from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import select, inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
from tests.test_local_scan import env
from app.api import auth, password_recovery as recovery
from app.core.config import get_settings
from app.core.security import hash_password, create_access_token, create_session_token, verify_password
from app.models import PasswordReset, RecoveryRateLimit, AuditEvent

@pytest.fixture
def app(env):
    env.app.include_router(auth.router,prefix='/api')
    env.app.include_router(recovery.router,prefix='/api')
    env.app.dependency_overrides.pop(auth.get_current_user)
    for user in env.users.values():user.password_hash=hash_password('initial-password')
    env.db.commit()
    return env

def headers(app,role='admin'):
    return {'Authorization':'Bearer '+create_session_token(app.users[role])}

def issue(app,role='member',**payload):
    result=app.client.post(f'/api/auth/users/{app.users[role].id}/recovery-link',headers=headers(app),json={'current_password':'initial-password',**payload})
    assert result.status_code==200,result.text
    assert result.headers['cache-control']=='no-store'
    return result.json()['url'].split('/')[-1]

def reset(app,token,password='new-password'):
    return app.client.post('/api/auth/password-reset',json={'token':token,'password':password})

def test_single_use_hash_only_and_session_revocation(app):
    bearer=headers(app,'member')
    legacy={'Authorization':'Bearer '+create_access_token(str(app.users['member'].id))}
    assert app.client.get('/api/auth/me',headers=legacy).status_code==200
    token=issue(app)
    row=app.db.scalar(select(PasswordReset))
    assert row.token_hash==hashlib.sha256(token.encode()).hexdigest()
    assert token not in repr(row.__dict__)
    assert app.client.get('/api/auth/me',headers=bearer).status_code==200
    app.client.cookies.set(auth.REMEMBER_ME_COOKIE,bearer['Authorization'][7:])
    result=reset(app,token)
    assert result.status_code==200,result.text
    assert 'Max-Age=0' in result.headers['set-cookie']
    assert reset(app,token).status_code==400
    for h in (bearer,legacy):assert app.client.get('/api/auth/me',headers=h).status_code==401
    assert app.client.post('/api/auth/login',json={'email':app.users['member'].email,'password':'initial-password'}).status_code==401
    login=app.client.post('/api/auth/login',json={'email':app.users['member'].email,'password':'new-password'})
    assert login.status_code==200
    assert app.client.get('/api/auth/me',headers={'Authorization':'Bearer '+login.json()['access_token']}).status_code==200
    assert app.db.scalar(select(AuditEvent).where(AuditEvent.event_kind=='password_reset'))

@pytest.mark.parametrize('invalidate',['expired','deleted','email','password','superseded'])
def test_invalidated_links(app,invalidate):
    token=issue(app);user=app.users['member'];row=app.db.scalar(select(PasswordReset))
    if invalidate=='expired':row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    if invalidate=='deleted':user.deleted_at=datetime.now(timezone.utc)
    if invalidate=='email':user.email='changed@example.test'
    if invalidate=='password':user.auth_version+=1
    app.db.commit()
    if invalidate=='superseded':issue(app)
    assert reset(app,token).status_code==400
    assert verify_password('initial-password',user.password_hash)

def test_admin_requires_password_permission_and_protects_host(app):
    url=f'/api/auth/users/{app.users["member"].id}/recovery-link'
    assert app.client.post(url,json={'current_password':'initial-password'}).status_code==401
    assert app.client.post(url,headers=headers(app,'member'),json={'current_password':'initial-password'}).status_code==403
    assert app.client.post(url,headers=headers(app),json={'current_password':'wrong'}).status_code==400
    assert app.client.post(f'/api/auth/users/{app.users["host"].id}/recovery-link',headers=headers(app),json={'current_password':'initial-password'}).status_code==403

def test_force_reset_rejects_login_and_old_session_then_recovers(app):
    old=headers(app,'member');token=issue(app,require_reset=True)
    assert app.client.get('/api/auth/me',headers=old).status_code==401
    assert app.client.post('/api/auth/login',json={'email':app.users['member'].email,'password':'initial-password'}).status_code==403
    assert reset(app,token).status_code==200
    assert not app.db.get(type(app.users['member']),app.users['member'].id).password_reset_required

def test_generic_requests_rate_limit_and_no_lockout(app):
    settings=get_settings()
    with patch.object(settings,'smtp_host','smtp.example.test'),patch.object(settings,'smtp_from','eqm@example.test'),patch.object(recovery,'deliver') as deliver:
        results=[app.client.post('/api/auth/password-recovery',json={'email':email}) for email in [app.users['member'].email,'missing@example.test',app.users['member'].email,app.users['member'].email]]
        assert all(r.status_code==202 and r.json()==results[0].json() for r in results)
        assert deliver.call_count==2
        assert not app.users['member'].password_reset_required
        for _ in range(12):app.client.post('/api/auth/password-recovery',json={'email':app.users['other'].email})
        assert deliver.call_count==4
        assert all('@' not in r.bucket for r in app.db.scalars(select(RecoveryRateLimit)))

def test_without_smtp_returns_generic_no_secret(app):
    settings=get_settings()
    with patch.object(settings,'smtp_host',''):
        response=app.client.post('/api/auth/password-recovery',json={'email':app.users['member'].email})
    assert response.status_code==202 and 'token' not in response.text and 'url' not in response.text
    assert not app.db.scalar(select(PasswordReset))

@pytest.mark.parametrize('role',['member','quartermaster','intel_analyst'])
def test_profile_password_rotates_sessions_for_utility_roles(app,role):
    old=headers(app,role)
    assert app.client.patch('/api/auth/me',headers=old,json={'password':'updated-password','current_password':'initial-password'}).status_code==200
    assert app.client.get('/api/auth/me',headers=old).status_code==401

def test_admin_direct_password_change_cancels_link(app):
    token=issue(app);old=headers(app,'member')
    response=app.client.patch(f'/api/auth/users/{app.users["member"].id}',headers=headers(app),json={'password':'updated-password'})
    assert response.status_code==200,response.text
    assert reset(app,token).status_code==400
    assert app.client.get('/api/auth/me',headers=old).status_code==401

def test_sso_state_is_not_a_session(app):
    token=create_access_token(str(app.users['member'].id),{'kind':'eve_sso'})
    assert app.client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401

def test_migration_roundtrip(app):
    engine=app.db.get_bind();app.db.commit()
    path=Path(__file__).parents[1]/'alembic/versions/0096_password_recovery.py'
    spec=importlib.util.spec_from_file_location('recovery_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.downgrade()
            assert 'password_resets' not in inspect(connection).get_table_names()
            module.upgrade()
            assert 'password_resets' in inspect(connection).get_table_names()
            assert {'auth_version','password_reset_required'}<={c['name'] for c in inspect(connection).get_columns('users')}


def test_atomic_password_versions_with_stale_sessions(app):
    from sqlalchemy.orm import Session
    from app.core.security import replace_account_password
    from app.models import User
    user=app.users['member']
    with Session(app.db.get_bind(),expire_on_commit=False) as other:
        stale=other.get(User,user.id)
        assert stale.auth_version==0
        replace_account_password(app.db,user,'first-password');app.db.commit()
        first=create_session_token(user)
        replace_account_password(other,stale,'second-password');other.commit()
        assert stale.auth_version==2
    app.db.expire_all()
    assert app.client.get('/api/auth/me',headers={'Authorization':'Bearer '+first}).status_code==401

def test_invalid_password_leaves_link_usable(app):
    token=issue(app)
    assert reset(app,token,'short').status_code==422
    assert reset(app,token).status_code==200

def test_invalid_frontend_url_does_not_enumerate_accounts(app):
    settings=get_settings()
    with patch.object(settings,'frontend_url','javascript:invalid'),patch.object(settings,'smtp_host','smtp.example.test'),patch.object(settings,'smtp_from','eqm@example.test'):
        known=app.client.post('/api/auth/password-recovery',json={'email':app.users['member'].email})
        unknown=app.client.post('/api/auth/password-recovery',json={'email':'missing@example.test'})
    assert known.status_code==unknown.status_code==202 and known.json()==unknown.json()
    assert not app.db.scalar(select(PasswordReset))

def test_required_reset_does_not_allow_self_lockout(app):
    result=app.client.post(f'/api/auth/users/{app.users["admin"].id}/recovery-link',headers=headers(app),json={'current_password':'initial-password','require_reset':True})
    assert result.status_code==400 and not app.users['admin'].password_reset_required
