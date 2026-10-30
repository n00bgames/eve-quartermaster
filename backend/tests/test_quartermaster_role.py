from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import auth, esi, planetary_industry, quartermaster, quartermaster_oversight, research_projects
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import (Asset, Base, Blueprint, EsiToken, EveCharacter, EveCorporation, EveType,
                        Location, OwnershipEntity, PlanetaryColony, PlanetaryPin, ResearchProject,
                        RoleDefinition, User, UserSectionPermission)
from app.models.enums import LocationKind, OwnerKind
from app.services import quartermaster_access as access
from app.services.permissions import effective_permissions, role_payload, role_rank

NOW = datetime.now(timezone.utc)


@pytest.fixture
def env():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    viewer = User(email='qm@test.invalid', display_name='Quartermaster', role='quartermaster')
    owner = User(email='owner@test.invalid', display_name='Owner', role='member')
    db.add_all([viewer, owner]); db.flush()
    corporations = [EveCorporation(corporation_id=98000000+i, name=f'Corp {i}', exclude_from_analytics=True) for i in range(3)]
    db.add_all(corporations); db.flush()
    characters = []
    for i, name in enumerate(['Private Pilot', 'Revoked Pilot', 'Opted Out Pilot', 'Unlinked Pilot', 'Transferred Pilot']):
        char = EveCharacter(character_id=90000000+i, name=name, owner_user_id=owner.id,
                            corporation_id=corporations[0].id, public_assets_visible=False, sync_opt_out=i == 2)
        db.add(char); db.flush(); characters.append(char)
        if i != 3:
            scopes = ' '.join(access.CHARACTER_SCOPES.values())
            db.add(EsiToken(user_id=viewer.id if i == 4 else owner.id, character_id=char.id,
                            scopes=scopes, encrypted_refresh_token='synthetic', revoked_at=NOW if i == 1 else None))
    corp_token = EsiToken(user_id=owner.id, character_id=characters[0].id,
                         scopes=' '.join(access.CORPORATION_SCOPES.values()), encrypted_refresh_token='synthetic')
    db.add(corp_token)
    bp_type = EveType(type_id=1000, name='Test Blueprint')
    box_type = EveType(type_id=1001, name='Station Container')
    db.add_all([bp_type, box_type]); db.flush()
    station = Location(eve_location_id=60000001, location_kind=LocationKind.STATION, name='Test Station')
    db.add(station); db.flush()
    owners = []
    for char in characters:
        row = OwnershipEntity(owner_kind=OwnerKind.CHARACTER, character_id=char.id, display_name=char.name)
        db.add(row); db.flush(); owners.append(row)
    for corp in corporations:
        row = OwnershipEntity(owner_kind=OwnerKind.CORPORATION, corporation_id=corp.id, display_name=corp.name)
        db.add(row); db.flush(); owners.append(row)
    for i, entity in enumerate(owners):
        container = Asset(ownership_entity_id=entity.id, eve_item_id=100000+i, type_id=box_type.type_id, quantity=1, location_id=station.id)
        db.add(container); db.flush()
        asset = Asset(ownership_entity_id=entity.id, eve_item_id=200000+i, type_id=bp_type.type_id, quantity=3 if i == 5 else 1,
                      parent_asset_id=container.id, location_flag='Hangar')
        db.add(asset); db.flush()
        db.add(Blueprint(ownership_entity_id=entity.id, asset_id=asset.id, blueprint_type_id=bp_type.type_id,
                         is_copy=i == 0, runs_remaining=17 if i == 0 else None, last_synced_at=NOW))
    jobs = [
        dict(job_id=1, character_id=characters[0].id, source_type='character'),
        dict(job_id=2, installer_character_id=characters[0].character_id, corporation_id=corporations[2].id, source_type='corporation'),
        dict(job_id=3, installer_character_id=99999999, corporation_id=corporations[0].id, source_type='corporation'),
        dict(job_id=4, installer_character_id=99999999, corporation_id=corporations[1].id, source_type='corporation'),
        dict(job_id=5, character_id=characters[1].id, source_type='character'),
    ]
    for row in jobs:
        db.add(ResearchProject(**row, activity_id=9, status='active', blueprint_type_id=bp_type.type_id, last_synced_at=NOW))
    db.add(ResearchProject(job_id=6, character_id=characters[0].id, source_type='character', activity_id=1, status='delivered', last_synced_at=NOW))
    for i, char in enumerate(characters):
        colony = PlanetaryColony(character_id=char.id, planet_id=40000000+i, planet_name=f'Planet {i}', num_pins=1, last_synced_at=NOW)
        db.add(colony); db.flush()
        db.add(PlanetaryPin(colony_id=colony.id, pin_id=70000+i, type_id=box_type.type_id, contents_json=[]))
    db.commit()
    access._GRANTS.clear()
    verifier = AsyncMock(return_value={'blueprints', 'jobs'})
    app = FastAPI()
    for router in [auth.router, quartermaster.router, quartermaster_oversight.router, research_projects.router, planetary_industry.router, esi.router]:
        app.include_router(router, prefix='/api')
    def database():
        try:
            yield db
        finally:
            db.rollback()
    app.dependency_overrides[get_db] = database
    token = create_access_token(str(viewer.id), {'role': 'host'})  # DB role must win over stale/forged claim.
    with patch.object(access, 'verify_corporation_access', verifier), TestClient(app, headers={'Authorization': f'Bearer {token}'}) as client:
        yield SimpleNamespace(db=db, viewer=viewer, owner=owner, characters=characters, corporations=corporations,
                              corp_token=corp_token, verifier=verifier, client=client)
    access._GRANTS.clear(); db.close(); engine.dispose()


def get_report(env):
    response = env.client.get('/api/quartermaster-oversight')
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'private, no-store'
    return response.json()


def test_role_is_assignable_but_not_elevated(env):
    roles = {row['name']: row for row in role_payload(env.db)}
    assert roles['quartermaster']['display_name'] == 'Quartermaster'
    assert role_rank(env.viewer, env.db) == role_rank('view_only')
    assert not auth.can_view_all_characters(env.viewer, env.db)
    permissions = effective_permissions(env.viewer, env.db)
    assert permissions['quartermaster'] and not permissions['esi'] and not permissions['assets'] and not permissions['skills']
    assert env.client.get('/api/auth/permissions/effective').json()['read_only_quartermaster'] is True


def test_scoped_blueprints_counts_nested_locations_jobs_and_pi(env):
    data = get_report(env)
    assert data['summary'] == {'bpo': 3, 'bpc': 1, 'active_jobs': 3, 'colonies': 1}
    assert {row['owner_name'] for row in data['blueprints']} == {'Private Pilot', 'Corp 0'}
    copy = next(row for row in data['blueprints'] if row['is_copy'])
    assert copy['runs_remaining'] == 17 and copy['quantity'] == 1
    assert copy['location_name'] == 'Test Station'
    assert copy['location_resolution']['immediate_location_name'] == 'Station Container'
    assert {row['job_id'] for row in data['jobs']} == {1, 2, 3}
    assert all(row['activity_name'] == 'Reactions' for row in data['jobs'])
    assert [row['character_name'] for row in data['colonies']] == ['Private Pilot']
    assert len(data['colonies'][0]['pins']) == 1
    assert 'routes' in data['colonies'][0] and 'links' in data['colonies'][0]
    text = str(data)
    assert 'encrypted_refresh_token' not in text and 'token_id' not in text and 'wallet' not in text
    # The new role does not widen ordinary asset visibility.
    assert env.client.get('/api/quartermaster/blueprints').json() == []


def test_corporate_datasets_are_independently_verified(env):
    env.verifier.return_value = {'jobs'}
    data = get_report(env)
    assert {row['owner_name'] for row in data['blueprints']} == {'Private Pilot'}
    assert {row['job_id'] for row in data['jobs']} == {1, 2, 3}
    assert data['warnings']


def test_unavailable_corporate_verification_excludes_corp_not_character(env):
    env.verifier.side_effect = RuntimeError('Synthetic ESI outage')
    data = get_report(env)
    assert {row['owner_name'] for row in data['blueprints']} == {'Private Pilot'}
    assert {row['job_id'] for row in data['jobs']} == {1, 2}
    assert data['warnings']


@pytest.mark.parametrize('change', ['revoke', 'opt_out', 'transfer', 'delete_owner', 'remove_scopes'])
def test_live_local_revocation_wins_over_cached_corporate_grant(env, change):
    get_report(env)
    if change == 'revoke':
        for token in env.db.scalars(select(EsiToken).where(EsiToken.character_id == env.characters[0].id)):
            token.revoked_at = NOW
    elif change == 'opt_out': env.characters[0].sync_opt_out = True
    elif change == 'transfer': env.characters[0].owner_user_id = env.viewer.id
    elif change == 'delete_owner': env.owner.deleted_at = NOW
    else:
        for token in env.db.scalars(select(EsiToken).where(EsiToken.character_id == env.characters[0].id)):
            token.scopes = ''
    env.db.commit()
    data = get_report(env)
    assert data['summary'] == {'bpo': 0, 'bpc': 0, 'active_jobs': 0, 'colonies': 0}


@pytest.mark.parametrize('method,path,payload', [
    ('post', '/api/quartermaster/owners', {'display_name': 'No', 'owner_kind': 'manual_group'}),
    ('post', '/api/quartermaster/blueprints', {}),
    ('post', '/api/research-projects/queue', {}),
    ('post', '/api/esi/sync/characters/all?sync_kind=research', {}),
    ('post', '/api/planetary-industry/sync/1', {}),
    ('post', '/api/auth/roles', {'name': 'No'}),
])
def test_direct_mutations_and_sync_denied_even_with_host_claim(env, method, path, payload):
    response = getattr(env.client, method)(path, json=payload)
    assert response.status_code == 403, response.text
    assert 'view-only' in response.text


def test_custom_based_role_inherits_read_only_and_login_logout_still_work(env):
    env.db.add(RoleDefinition(name='supply_observer', display_name='Supply Observer', base_role='quartermaster'))
    env.viewer.role = 'supply_observer'; env.db.commit()
    assert get_report(env)['read_only'] is True
    assert env.client.post('/api/quartermaster/owners', json={}).status_code == 403
    assert env.client.post('/api/auth/logout').status_code == 200


def test_section_disabled_and_ordinary_member_cannot_read_all_owners(env):
    env.viewer.role = 'member'; env.db.commit()
    assert env.client.get('/api/quartermaster-oversight').status_code == 403
    env.viewer.role = 'quartermaster'
    env.db.add(UserSectionPermission(user_id=env.viewer.id, section='quartermaster', can_view=False)); env.db.commit()
    assert env.client.get('/api/quartermaster-oversight').status_code == 403


def test_corporate_probe_requires_current_affiliation_and_successful_real_dataset_read():
    character = SimpleNamespace(character_id=90000001, corporation=SimpleNamespace(corporation_id=98000001))
    token = SimpleNamespace(scopes=' '.join(access.CORPORATION_SCOPES.values()))
    async def get(path, params=None):
        if path.endswith('/characters/90000001/'): return {'corporation_id': 98000001}
        if path.endswith('/blueprints/'): return []
        raise RuntimeError('jobs denied')
    import asyncio
    with patch('app.api.esi.refresh_access_token', AsyncMock(return_value='synthetic')), patch('app.services.esi_client.EsiClient') as source:
        source.return_value.get = AsyncMock(side_effect=get)
        source.return_value.close = AsyncMock()
        assert asyncio.run(access.verify_corporation_access(token, character)) == {'blueprints'}
        source.return_value.get = AsyncMock(return_value={'corporation_id': 98000002})
        assert asyncio.run(access.verify_corporation_access(token, character)) == set()

def test_sync_all_is_the_only_refresh_exception_and_deduplicates(env):
    from app.services import quartermaster_sync as sync
    sync.JOBS.clear()
    with patch.object(sync, 'schedule') as schedule:
        response = env.client.post('/api/quartermaster-oversight/sync', json={'dataset': 'wallet', 'token_id': 9999})
        assert response.status_code == 202, response.text
        job = response.json()
        assert job['total_count'] == 5
        assert 'work' not in job and 'user_id' not in job and 'token_id' not in str(job)
        again = env.client.post('/api/quartermaster-oversight/sync', json={})
        assert again.json()['job_id'] == job['job_id']
        assert schedule.call_count == 2
        assert env.client.get('/api/quartermaster-oversight/sync').json()['job_id'] == job['job_id']
        assert env.client.get('/api/quartermaster-oversight/sync/' + job['job_id']).status_code == 200
        assert {item['dataset'] for item in sync.JOBS[job['job_id']]['work']} == {'blueprints', 'jobs', 'planets', 'corporation_blueprints', 'corporation_jobs'}
    sync.JOBS.clear()


def test_sync_worker_continues_failures_and_uses_only_allowed_datasets(env):
    import asyncio
    from app.services import quartermaster_sync as sync
    sync.JOBS.clear()
    job = sync.enqueue(env.db, env.viewer)
    seen = []
    async def fake(db, actor, token, character, item):
        seen.append(item['dataset'])
        if item['dataset'] == 'jobs': raise RuntimeError('Synthetic failure')
        return {'status': 'synced', 'warnings': []}
    with patch.object(sync, 'sync_dataset', AsyncMock(side_effect=fake)):
        asyncio.run(sync.run(job['job_id'], factory=lambda: Session(env.db.bind, expire_on_commit=False)))
    assert set(seen) == {'blueprints', 'jobs', 'planets', 'corporation_blueprints', 'corporation_jobs'}
    assert job['processed_count'] == 5 and job['success_count'] == 4 and job['failed_count'] == 1
    assert job['status'] == 'partial' and job['errors']
    sync.JOBS.clear()


@pytest.mark.parametrize('revoke', ['actor_role', 'token', 'opt_out'])
def test_sync_worker_rechecks_authorization_at_execution(env, revoke):
    import asyncio
    from app.services import quartermaster_sync as sync
    sync.JOBS.clear()
    job = sync.enqueue(env.db, env.viewer)
    if revoke == 'actor_role': env.viewer.role = 'member'
    elif revoke == 'opt_out': env.characters[0].sync_opt_out = True
    else:
        for token in env.db.scalars(select(EsiToken).where(EsiToken.character_id == env.characters[0].id)):
            token.revoked_at = NOW
    env.db.commit()
    with patch.object(sync, 'sync_dataset', AsyncMock()) as handler:
        asyncio.run(sync.run(job['job_id'], factory=lambda: Session(env.db.bind, expire_on_commit=False)))
        handler.assert_not_called()
    assert job['skipped_count'] == 5 and job['success_count'] == 0
    sync.JOBS.clear()


def test_sync_job_status_is_private_to_the_initiator(env):
    from app.services import quartermaster_sync as sync
    sync.JOBS.clear()
    job = sync.enqueue(env.db, env.viewer)
    job['user_id'] = env.owner.id
    assert env.client.get('/api/quartermaster-oversight/sync/' + job['job_id']).status_code == 404
    assert env.client.post('/api/quartermaster-oversight/sync', json={}).status_code == 409
    sync.JOBS.clear()


def test_blueprint_sync_fetches_relevant_feeds_and_prunes_stale_esi_rows(env):
    import asyncio
    from app.services import quartermaster_sync as sync
    from app.models.enums import AssetSource
    private_owner = env.db.scalar(select(OwnershipEntity).where(OwnershipEntity.character_id == env.characters[0].id))
    manual = Blueprint(ownership_entity_id=private_owner.id, blueprint_type_id=1000, source=AssetSource.MANUAL)
    env.db.add(manual)
    env.db.add(EsiToken(user_id=env.owner.id, character_id=env.characters[0].id,
                       scopes='esi-assets.read_assets.v1', encrypted_refresh_token='synthetic'))
    env.db.commit()
    primary = env.db.scalar(select(EsiToken).where(EsiToken.character_id == env.characters[0].id, EsiToken.scopes.like('%read_blueprints%')))
    fresh = [{'item_id': 200099, 'type_id': 1000, 'location_id': 60000001,
              'location_flag': 'Hangar', 'quantity': 2, 'runs': -1}]
    with patch('app.api.esi.refresh_access_token', AsyncMock(return_value='synthetic')), \
         patch('app.services.esi_client.EsiClient') as source, \
         patch('app.api.esi.fetch_all_blueprint_pages', AsyncMock(return_value=fresh)) as blueprints, \
         patch('app.api.esi.fetch_all_asset_pages', AsyncMock(return_value=[])) as assets, \
         patch('app.api.esi.apply_type_names', AsyncMock(return_value=0)), \
         patch('app.api.esi.apply_location_names', AsyncMock(return_value=0)):
        source.return_value.close = AsyncMock()
        result = asyncio.run(sync.sync_dataset(env.db, env.viewer, primary, env.characters[0],
                           {'dataset': 'blueprints', 'owner_id': env.characters[0].id, 'label': 'Private Pilot'}))
        assert result['status'] == 'synced' and not result['warnings']
        assert blueprints.await_args.args[1] == '/characters/90000000/blueprints/'
        assert assets.await_args.args[1] == '/characters/90000000/assets/'
    rows = env.db.scalars(select(Blueprint).where(Blueprint.ownership_entity_id == private_owner.id)).all()
    assert len(rows) == 2 and manual in rows
    fresh_row = next(row for row in rows if row.source == AssetSource.ESI)
    assert fresh_row.asset.eve_item_id == 200099 and fresh_row.asset.quantity == 2


def test_reaction_jobs_are_imported_instead_of_silently_dropped(env):
    from app.services.research_projects import upsert_research_projects
    count, active = upsert_research_projects(env.db, env.characters[0].id,
                    [{'job_id': 7001, 'activity_id': 9, 'status': 'active', 'installer_id': 90000000}])
    assert count == active == 1
    assert env.db.scalar(select(ResearchProject).where(ResearchProject.job_id == 7001)).activity_id == 9

def test_corporate_sync_checks_current_affiliation_before_importing(env):
    import asyncio
    from fastapi import HTTPException
    from app.services import quartermaster_sync as sync
    with patch('app.api.esi.refresh_access_token', AsyncMock(return_value='synthetic')), \
         patch('app.services.esi_client.EsiClient') as source, \
         patch('app.api.esi.fetch_all_blueprint_pages', AsyncMock()) as fetch:
        source.return_value.get = AsyncMock(return_value={'corporation_id': 12345})
        source.return_value.close = AsyncMock()
        with pytest.raises(HTTPException) as error:
            asyncio.run(sync.sync_dataset(env.db, env.viewer, env.corp_token, env.characters[0],
                        {'dataset': 'corporation_blueprints', 'owner_id': env.corporations[0].id, 'label': 'Corp 0'}))
        assert error.value.status_code == 403
        fetch.assert_not_called()


def test_planetary_refresh_capability_is_internal_and_dataset_scoped(env):
    import asyncio
    from fastapi import HTTPException
    primary = env.db.scalar(select(EsiToken).where(EsiToken.character_id == env.characters[0].id, EsiToken.scopes.like('%manage_planets%')))
    with pytest.raises(HTTPException):
        asyncio.run(planetary_industry.sync_planetary_industry_for_token(primary.id, env.viewer, env.db, allow_opt_out_override=False))
    with patch.object(planetary_industry, 'refresh_access_token', AsyncMock(return_value='synthetic')), \
         patch.object(planetary_industry, 'EsiClient') as source:
        source.return_value.get = AsyncMock(return_value=[])
        value = asyncio.run(planetary_industry.sync_planetary_industry_for_token(primary.id, env.viewer, env.db,
                            allow_opt_out_override=False, quartermaster_sync=True))
        assert value['status'] == 'synced' and value['colony_count'] == 0
        source.return_value.get.assert_awaited_once_with('/characters/90000000/planets/')


def test_successful_job_refresh_reconciles_only_its_own_feed(env):
    import asyncio
    from app.services import quartermaster_sync as sync
    primary = env.db.scalar(select(EsiToken).where(EsiToken.character_id == env.characters[0].id, EsiToken.scopes.like('%read_character_jobs%')))
    with patch('app.api.esi.refresh_access_token', AsyncMock(return_value='synthetic')), \
         patch('app.services.esi_client.EsiClient') as source, \
         patch('app.services.research_projects.fetch_character_industry_jobs', AsyncMock(return_value=[])), \
         patch('app.services.research_projects.fetch_corporation_industry_jobs', AsyncMock(return_value=[])), \
         patch('app.services.research_projects.resolve_installer_names', AsyncMock(return_value={})), \
         patch('app.api.esi.apply_type_names', AsyncMock(return_value=0)), \
         patch('app.api.esi.apply_location_names', AsyncMock(return_value=0)):
        source.return_value.close = AsyncMock()
        source.return_value.get = AsyncMock(return_value={'corporation_id': env.corporations[0].corporation_id})
        asyncio.run(sync.sync_dataset(env.db, env.viewer, primary, env.characters[0],
                    {'dataset': 'jobs', 'owner_id': env.characters[0].id, 'label': 'Private Pilot'}))
        assert env.db.scalar(select(ResearchProject).where(ResearchProject.job_id == 1)).status == 'no_longer_reported'
        assert env.db.scalar(select(ResearchProject).where(ResearchProject.job_id == 2)).status == 'active'
        asyncio.run(sync.sync_dataset(env.db, env.viewer, env.corp_token, env.characters[0],
                    {'dataset': 'corporation_jobs', 'owner_id': env.corporations[0].id, 'label': 'Corp 0'}))
        assert env.db.scalar(select(ResearchProject).where(ResearchProject.job_id == 3)).status == 'no_longer_reported'
        assert env.db.scalar(select(ResearchProject).where(ResearchProject.job_id == 4)).status == 'active'


@pytest.mark.parametrize('role', ['officer', 'director'])
def test_existing_staff_roles_do_not_automatically_gain_global_oversight(env, role):
    env.viewer.role = role
    env.db.commit()
    assert not effective_permissions(env.viewer, env.db)['quartermaster']
    assert env.client.get('/api/quartermaster-oversight').status_code == 403
    assert env.client.post('/api/quartermaster-oversight/sync', json={}).status_code == 403


def test_personal_profile_remains_a_quartermaster_utility(env):
    response=env.client.patch("/api/auth/me",json={"display_name":"My own display name"})
    assert response.status_code==200
    assert response.json()["display_name"]=="My own display name"
