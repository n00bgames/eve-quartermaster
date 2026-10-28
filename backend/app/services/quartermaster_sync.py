"""Limited background refresh for Quartermaster-visible ESI datasets only."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import delete, select
from app.db.session import SessionLocal
from app.models import Asset, Blueprint, EsiSyncJob, EsiToken, EveCharacter, User
from app.models.enums import AssetSource, OwnerKind, SyncStatus
from app.services.permissions import can_view_section
from app.services.quartermaster_access import authenticated_rows, CHARACTER_SCOPES, CORPORATION_SCOPES

JOBS: dict[str, dict] = {}
TASKS: set[asyncio.Task] = set()


def eligible(db, actor, token, character, dataset):
    if not actor or actor.deleted_at is not None or not can_view_section(actor, 'quartermaster', db):
        return False
    if not token or not character or token.revoked_at or character.sync_opt_out or token.user_id != character.owner_user_id:
        return False
    owner = db.get(User, character.owner_user_id)
    scope = (CORPORATION_SCOPES if dataset.startswith('corporation_') else CHARACTER_SCOPES).get(dataset.removeprefix('corporation_'))
    return bool(owner and owner.deleted_at is None and scope and scope in token.scopes.split())


def work_items(db):
    grouped = {}
    for token, character in authenticated_rows(db):
        for dataset, scope in CHARACTER_SCOPES.items():
            if scope in token.scopes.split():
                key = (dataset, character.id)
                item = grouped.setdefault(key, {'dataset': dataset, 'owner_id': character.id, 'label': character.name, 'token_ids': []})
                item['token_ids'].append(token.id)
        if character.corporation_id is not None:
            for dataset, scope in CORPORATION_SCOPES.items():
                if scope in token.scopes.split():
                    key = ('corporation_' + dataset, character.corporation_id)
                    item = grouped.setdefault(key, {'dataset': key[0], 'owner_id': character.corporation_id,
                                                   'label': character.corporation.name, 'token_ids': []})
                    item['token_ids'].append(token.id)
    return list(grouped.values())


def payload(job):
    return {key: value for key, value in job.items() if key not in {'user_id', 'work', 'scheduled'}}


def enqueue(db, user):
    for job in JOBS.values():
        if job['status'] in {'queued', 'running'}:
            if job['user_id'] == user.id:
                return job
            raise HTTPException(409, 'A Quartermaster Sync All is already running. Refresh the view when it finishes.')
    items = work_items(db)
    if not items:
        raise HTTPException(400, 'No eligible blueprint, industry, or planetary authorizations are available')
    for key in list(JOBS)[:-20]:
        JOBS.pop(key, None)
    job = {'job_id': uuid4().hex, 'user_id': user.id, 'status': 'queued', 'work': items,
           'total_count': len(items), 'processed_count': 0, 'success_count': 0, 'failed_count': 0,
           'skipped_count': 0, 'current': None, 'errors': [], 'warnings': [],
           'started_at': datetime.now(timezone.utc).isoformat(), 'finished_at': None}
    JOBS[job['job_id']] = job
    from app.services.audit import record_audit_event
    record_audit_event(db, event_kind='sync', title='Quartermaster Sync All requested', actor_user=user,
                       body=f"{len(items)} blueprint, industry and planetary refresh tasks; unrelated datasets excluded")
    db.commit()
    return job


def schedule(job_id):
    if JOBS[job_id].get('scheduled'):
        return
    JOBS[job_id]['scheduled'] = True
    task = asyncio.create_task(run(job_id))
    TASKS.add(task)
    task.add_done_callback(TASKS.discard)


async def sync_dataset(db, actor, token, character, item):
    """All feed URLs and import functions come from this fixed allowlist."""
    from app.api import esi
    from app.api.planetary_industry import sync_planetary_industry_for_token
    from app.services.esi_client import EsiClient
    from app.services.research_projects import fetch_character_industry_jobs, fetch_corporation_industry_jobs, upsert_research_projects, resolve_installer_names

    dataset = item['dataset']
    if dataset == 'planets':
        return await sync_planetary_industry_for_token(token.id, actor, db, allow_opt_out_override=False, quartermaster_sync=True)
    corporation = dataset.startswith('corporation_')
    kind = dataset.removeprefix('corporation_')
    client = EsiClient(await esi.refresh_access_token(token))
    db.commit()
    try:
        if corporation:
            # Recheck affiliation at execution, regardless of prior display cache.
            corp = character.corporation
            profile = await client.get(f'/characters/{character.character_id}/')
            if corp is None or character.corporation_id != item['owner_id'] or profile.get('corporation_id') != corp.corporation_id:
                raise HTTPException(403, 'Corporate affiliation changed')
            owner = esi.ensure_owner(db, OwnerKind.CORPORATION, corp.name, corporation_id=corp.id)
            base = f'/corporations/{corp.corporation_id}'
        else:
            owner = esi.ensure_owner(db, OwnerKind.CHARACTER, character.name, character_id=character.id)
            base = f'/characters/{character.character_id}'
        db.commit()
        warnings = []
        if kind == 'blueprints':
            # ESI itself enforces corporate read roles. Fetch this protected feed
            # before importing anything; a scope string alone is insufficient.
            rows = await esi.fetch_all_blueprint_pages(client, base + '/blueprints/')
            assets_scope = 'esi-assets.read_corporation_assets.v1' if corporation else 'esi-assets.read_assets.v1'
            asset_tokens = [(candidate, pilot) for candidate, pilot in authenticated_rows(db)
                            if assets_scope in candidate.scopes.split()
                            and (pilot.corporation_id == item['owner_id'] if corporation else pilot.id == item['owner_id'])]
            locations_refreshed = False
            for asset_token, pilot in asset_tokens:
                location_client = client
                try:
                    if asset_token.id != token.id:
                        location_client = EsiClient(await esi.refresh_access_token(asset_token))
                        db.commit()
                    if corporation:
                        affiliation = await location_client.get(f'/characters/{pilot.character_id}/')
                        if affiliation.get('corporation_id') != corp.corporation_id:
                            continue
                    assets = await esi.fetch_all_asset_pages(location_client, base + '/assets/')
                    await esi.apply_type_names(location_client, db, {int(row['type_id']) for row in assets})
                    location_types = esi.asset_location_types(assets)
                    await esi.apply_location_names(location_client, db, set(location_types), location_types)
                    esi.upsert_asset_rows(db, owner, assets)
                    if corporation:
                        await esi.sync_corporation_divisions(location_client, db, corp)
                    locations_refreshed = True
                    break
                except Exception:
                    db.rollback()
                finally:
                    if location_client is not client:
                        await location_client.close()
            if not locations_refreshed:
                warnings.append('Asset location access is missing or unavailable; some container locations may remain stale or unresolved.')
            await esi.apply_type_names(client, db, {int(row['type_id']) for row in rows})
            existing_locations = {int(row['location_id']) for row in rows if row.get('location_id')}
            # Existing containers are resolved by upsert_blueprint_rows.
            await esi.apply_location_names(client, db, existing_locations, {key: 'unknown' for key in existing_locations})
            count = esi.upsert_blueprint_rows(db, owner, rows)
            live_ids = {int(row['item_id']) for row in rows}
            stale = select(Asset.id).where(Asset.ownership_entity_id == owner.id, Asset.eve_item_id.not_in(live_ids))
            db.execute(delete(Blueprint).where(Blueprint.ownership_entity_id == owner.id, Blueprint.source == AssetSource.ESI, Blueprint.asset_id.in_(stale)))
            for row in rows:
                asset = db.scalar(select(Asset).where(Asset.ownership_entity_id == owner.id, Asset.eve_item_id == int(row['item_id'])))
                if asset is not None:
                    asset.quantity = max(1, int(row.get('quantity', 1)))
        elif kind == 'jobs':
            rows = await (fetch_corporation_industry_jobs(client, corp.corporation_id) if corporation else fetch_character_industry_jobs(client, character.character_id))
            await esi.apply_type_names(client, db, {int(row[key]) for row in rows for key in ('blueprint_type_id', 'product_type_id') if row.get(key)})
            facility_ids = {int(row.get('facility_id') or row.get('station_id')) for row in rows if row.get('facility_id') or row.get('station_id')}
            await esi.apply_location_names(client, db, facility_ids, {key: 'unknown' for key in facility_ids})
            names = await resolve_installer_names(client, rows)
            count, _active = upsert_research_projects(db, None if corporation else character.id, rows,
                            corporation_id=corp.id if corporation else None,
                            source_type='corporation' if corporation else 'character', installer_names=names)
            # Both feeds include all current jobs. Do not keep an old active
            # record alive forever after it disappears from a successful read.
            from app.models import ResearchProject
            from app.services.research_projects import ACTIVE_RESEARCH_STATUSES
            reported_ids = {int(row['job_id']) for row in rows}
            owner_clause = ResearchProject.corporation_id == corp.id if corporation else ResearchProject.character_id == character.id
            stale_jobs = db.scalars(select(ResearchProject).where(
                ResearchProject.source_type == ('corporation' if corporation else 'character'), owner_clause,
                ResearchProject.status.in_(ACTIVE_RESEARCH_STATUSES), ResearchProject.job_id.not_in(reported_ids),
            )).all()
            for project in stale_jobs:
                project.status = 'no_longer_reported'
                project.last_synced_at = datetime.now(timezone.utc)
        else:
            raise ValueError('Unsupported Quartermaster dataset')
        now = datetime.now(timezone.utc)
        db.add(EsiSyncJob(token_id=token.id, ownership_entity_id=owner.id, sync_type=f'quartermaster_{dataset}',
                         status=SyncStatus.SUCCESS, started_at=now, finished_at=now,
                         message=f'Refreshed {count} {kind} records for {item["label"]}.'))
        db.commit()
        return {'status': 'synced', 'warnings': warnings}
    finally:
        await client.close()


async def run(job_id, factory=None):
    job = JOBS[job_id]
    job['status'] = 'running'
    try:
        for item in job['work']:
            job['current'] = f'{item["label"]} · {item["dataset"].replace("_", " ")}'
            success, attempted = False, False
            for token_id in item['token_ids']:
                with (factory or SessionLocal)() as db:
                    actor, token = db.get(User, job['user_id']), db.get(EsiToken, token_id)
                    character = db.get(EveCharacter, token.character_id) if token else None
                    if not eligible(db, actor, token, character, item['dataset']):
                        continue
                    if not item['dataset'].startswith('corporation_') and character.id != item['owner_id']:
                        continue
                    attempted = True
                    try:
                        result = await sync_dataset(db, actor, token, character, item)
                        job['warnings'].extend(f'{item["label"]}: {text}' for text in result.get('warnings', []))
                        success = result.get('status') != 'skipped'
                        if success:
                            break
                    except Exception:
                        db.rollback()
                        now = datetime.now(timezone.utc)
                        db.add(EsiSyncJob(token_id=token.id, sync_type=f'quartermaster_{item["dataset"]}',
                                         status=SyncStatus.FAILED, started_at=now, finished_at=now,
                                         message='Quartermaster refresh failed; an alternate authorization will be tried if available.'))
                        db.commit()
            job['processed_count'] += 1
            if success: job['success_count'] += 1
            elif attempted:
                job['failed_count'] += 1
                job['errors'].append(f'{job["current"]}: refresh failed or corporate access was denied. Other datasets will continue.')
            else: job['skipped_count'] += 1
        job['status'] = 'complete' if job['failed_count'] == 0 else 'partial'
    except Exception:
        job['status'] = 'failed'
        job['errors'].append('Sync worker stopped unexpectedly; completed datasets remain available.')
    finally:
        job['current'] = None
        job['finished_at'] = datetime.now(timezone.utc).isoformat()
        job['errors'] = job['errors'][-30:]
        job['warnings'] = sorted(set(job['warnings']))[-30:]
