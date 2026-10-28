from pathlib import Path
import importlib.util
import pytest
from sqlalchemy import create_engine, inspect, select
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.api import auth
from app.models import User, RoleDefinition, RoleSectionPermission, UserSectionPermission, UserRoleAssignment, EsiToken
from app.services.permissions import assign_roles, assigned_roles, effective_permissions, quartermaster_read_only, role_rank, set_disabled_sections
from app.services.esi_scope_policy import is_utility_user, allowed_scopes, effective_token_scopes
from .test_local_scan import env


@pytest.fixture
def roles_env(env):
    env.app.include_router(auth.router,prefix='/api')
    env.users['host'].password_hash='fixture';env.users['admin'].password_hash='fixture';env.db.commit()
    env.current[0]=env.users['host']
    return env


def test_union_primary_compatibility_and_account_payload(roles_env):
    e=roles_env;user=e.users['member']
    r=e.client.patch(f'/api/auth/users/{user.id}',json={'roles':['quartermaster','intel_analyst']})
    assert r.status_code==200,r.text
    assert r.json()['roles']==['intel_analyst','quartermaster'] and r.json()['role']=='intel_analyst'
    p=effective_permissions(user,e.db)
    assert p['quartermaster'] and p['intel_reports'] and p['navigation'] and p['market']
    assert not p['assets'] and not p['skills'] and not quartermaster_read_only(user,e.db)
    assert is_utility_user(e.db,user)
    e.current[0]=user
    assert e.client.get('/api/auth/me').json()['roles']==['intel_analyst','quartermaster']
    assert e.client.get('/api/auth/permissions/effective').json()['utility_only'] is True
    e.current[0]=e.users['host']
    r=e.client.patch(f'/api/auth/users/{user.id}',json={'roles':['quartermaster','intel_analyst','member']})
    assert r.json()['role']=='member' and not is_utility_user(e.db,user)
    assert 'esi-assets.read_assets.v1' in allowed_scopes(e.db,user)


def test_user_and_global_denials_override_aggregate_allow(roles_env):
    e=roles_env;user=e.users['member'];assign_roles(e.db,user,['officer','intel_analyst']);e.db.commit()
    e.db.add(RoleSectionPermission(role='intel_analyst',section='intel_reports',can_view=False));e.db.commit()
    assert effective_permissions(user,e.db)['intel_reports']
    e.db.add(UserSectionPermission(user_id=user.id,section='intel_reports',can_view=False));e.db.commit()
    assert not effective_permissions(user,e.db)['intel_reports']
    set_disabled_sections(e.db,{'navigation'});e.db.commit()
    assert not effective_permissions(user,e.db)['navigation']


def test_removing_role_immediately_removes_its_grants_and_private_scopes(roles_env):
    e=roles_env;user=e.users['member'];token=e.db.scalar(select(EsiToken).where(EsiToken.user_id==user.id))
    assign_roles(e.db,user,['member','intel_analyst']);e.db.commit()
    assert 'esi-assets.read_assets.v1' in effective_token_scopes(token)
    assign_roles(e.db,user,['intel_analyst','quartermaster']);e.db.commit()
    assert 'esi-assets.read_assets.v1' not in effective_token_scopes(token)
    assert not effective_permissions(user,e.db)['skills']
    # A legacy single-role update replaces the complete assignment set.
    r=e.client.patch(f'/api/auth/users/{user.id}',json={'role':'member'})
    assert r.status_code==200 and r.json()['roles']==['member']
    assert e.db.scalars(select(UserRoleAssignment).where(UserRoleAssignment.user_id==user.id)).all()==[]


def test_custom_roles_participate_in_permission_and_rank_union(roles_env):
    e=roles_env;user=e.users['member']
    e.db.add(RoleDefinition(name='logistics_officer',display_name='Logistics Officer',base_role='officer'));e.db.commit()
    assign_roles(e.db,user,['logistics_officer','quartermaster']);e.db.commit()
    assert role_rank(user,e.db)==2 and role_rank(user)==2
    assert effective_permissions(user,e.db)['quartermaster'] and effective_permissions(user,e.db)['intel_reports']
    assert assigned_roles(user)==['logistics_officer','quartermaster']


@pytest.mark.parametrize('roles',[[],['not_a_role'],['host']])
def test_admin_cannot_grant_additional_host_or_invalid_roles(roles_env,roles):
    e=roles_env;e.current[0]=e.users['admin'];uid=e.users['member'].id
    expected=403 if roles==['host'] else 400
    r=e.client.patch(f'/api/auth/users/{uid}',json={'roles':roles})
    assert r.status_code==expected
    assert assigned_roles(e.users['member'],e.db)==['member']
    if roles==['host']:
        for route,payload in [('/api/auth/users',{'email':'new@test.invalid','password':'long-enough'}),('/api/auth/invites',{'email':'invite@test.invalid'})]:
            assert e.client.post(route,json={**payload,'roles':['member','host']}).status_code==403


def test_host_safeguards_apply_to_full_role_set(roles_env):
    e=roles_env;host=e.users['host']
    assert e.client.patch(f'/api/auth/users/{host.id}',json={'roles':['admin','member']}).status_code==400
    e.current[0]=e.users['admin']
    assert e.client.patch(f'/api/auth/users/{host.id}',json={'roles':['host','member']}).status_code==403
    assert e.client.patch(f'/api/auth/users/{host.id}',json={'display_name':'forbidden'}).status_code==403


def test_create_account_and_accept_multi_role_invite(roles_env):
    e=roles_env
    r=e.client.post('/api/auth/users',json={'email':'new-multi@test.invalid','password':'long-enough','display_name':'New multi','roles':['intel_analyst','quartermaster']})
    assert r.status_code==200 and r.json()['roles']==['intel_analyst','quartermaster']
    invite=e.client.post('/api/auth/invites',json={'email':'invite-multi@test.invalid','roles':['intel_analyst','quartermaster']})
    assert invite.status_code==200,invite.text
    assert invite.json()['roles']==['intel_analyst','quartermaster']
    token=invite.json()['invite_url'].split('invite=')[1]
    r=e.client.post('/api/auth/invites/'+token+'/accept',json={'display_name':'Invited multi','password':'long-enough'})
    assert r.status_code==200 and r.json()['user']['roles']==['intel_analyst','quartermaster']


def test_member_cannot_self_assign_additional_roles(roles_env):
    e=roles_env;e.current[0]=e.users['member']
    assert e.client.patch(f"/api/auth/users/{e.current[0].id}",json={'roles':['admin']}).status_code==403
    r=e.client.patch('/api/auth/me',json={'roles':['admin']})
    assert r.status_code==200 and r.json()['roles']==['member']


def test_multirole_migration_preserves_legacy_rows():
    file=Path(__file__).parents[1]/'alembic/versions/0091_multiple_account_roles.py'
    spec=importlib.util.spec_from_file_location('multirole_migration',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine('sqlite://')
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE users (id INTEGER PRIMARY KEY, role VARCHAR(40))')
        c.exec_driver_sql('CREATE TABLE user_invites (id INTEGER PRIMARY KEY, role VARCHAR(40))')
        c.exec_driver_sql("INSERT INTO users VALUES (1,'member')")
        c.exec_driver_sql("INSERT INTO user_invites VALUES (1,'officer')")
        module.op=Operations(MigrationContext.configure(c));module.upgrade()
        assert c.exec_driver_sql('SELECT role FROM users').scalar()=='member'
        assert c.exec_driver_sql('SELECT roles_json FROM user_invites').scalar() is None
        module.downgrade();assert 'user_role_assignments' not in inspect(c).get_table_names()
