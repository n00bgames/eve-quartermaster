"""Opt-in, own-character organization contacts for automatic scan colors."""
import asyncio
import math
import httpx
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.models import EsiToken, EveCharacter, User
from app.models.local_scan import ScanColorSettings
from app.services.esi_client import EsiClient
from app.services.esi_scope_policy import effective_token_scopes
from app.services.permissions import can_view_section

CONTACT_SCOPE = 'esi-characters.read_contacts.v1'
_syncing = set()


def standing_color(standing):
    if standing < -5: return 'red'
    if standing < 0: return 'orange'
    if standing > 5: return 'blue'
    if standing > 0: return 'light_blue'
    return 'gray'


def own_character_tokens(db, user):
    rows = db.execute(select(EsiToken, EveCharacter).join(EveCharacter, EveCharacter.id == EsiToken.character_id).where(
        EsiToken.user_id == user.id, EveCharacter.owner_user_id == user.id, EsiToken.revoked_at.is_(None)
    ).order_by(EveCharacter.name, EsiToken.id.desc())).all()
    by_character = {}
    for token, character in rows:
        current = by_character.get(character.id)
        can_read = CONTACT_SCOPE in effective_token_scopes(token, db)
        if current is None or (can_read and not current['can_read']):
            by_character[character.id] = {'id': character.id, 'character_id': character.character_id,
                'token_id': token.id, 'name': character.name, 'can_read': can_read}
    return list(by_character.values())


def settings_payload(db, user):
    row = db.get(ScanColorSettings, user.id, populate_existing=True)
    characters = own_character_tokens(db, user)
    selected = next((c for c in characters if row and c['id'] == row.character_id), None)
    enabled = bool(selected and selected['can_read'] and row and row.synced_at)
    return {'characters': [{k:v for k,v in c.items() if k != 'id'} for c in characters],
        'selected_token_id': selected['token_id'] if selected else None,
        'enabled': enabled, 'source_unavailable': bool(row and row.character_id and not enabled),
        'source_name': selected['name'] if selected else None,
        'synced_at': row.synced_at.replace(tzinfo=row.synced_at.tzinfo or timezone.utc).isoformat() if row and row.synced_at else None,
        'automatic_rules': row.contact_colors if enabled else [], 'revision': row.revision if row else 0}


def automatic_rules(db, user):
    # Never reuse contacts after unlink, token revocation or permission loss.
    row = db.get(ScanColorSettings, user.id, populate_existing=True)
    if not row or not row.character_id or not row.synced_at: return []
    character = db.get(EveCharacter, row.character_id, populate_existing=True)
    if not character or character.owner_user_id != user.id: return []
    tokens = db.scalars(select(EsiToken).where(EsiToken.user_id == user.id,
        EsiToken.character_id == character.id, EsiToken.revoked_at.is_(None)))
    return row.contact_colors if any(CONTACT_SCOPE in effective_token_scopes(t, db) for t in tokens) else []


def validate_contacts_consent_character(db, user_id, mode, eve_id):
    try: expected = int(mode.removeprefix('scan_contacts_').removeprefix('dscan_'))
    except ValueError as exc: raise HTTPException(400, 'Invalid scan-contacts authorization') from exc
    character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == expected))
    user = db.get(User, user_id, populate_existing=True)
    if not user or user.deleted_at or not any(can_view_section(user, s, db) for s in ('local_scan','dscan')):
        raise HTTPException(403, 'Scan permission is required')
    if eve_id != expected or not character or character.owner_user_id != user_id:
        raise HTTPException(403, 'Authorize the same linked character selected in EQM')


def consent_url(db, user, token_id, view="local"):
    from app.api.client_links import own_token
    from app.api.esi import build_auth_url
    token, character = own_token(db, user, token_id)
    scopes = effective_token_scopes(token, db) | {'publicData', CONTACT_SCOPE}
    prefix = 'scan_contacts_dscan_' if view == 'dscan' else 'scan_contacts_'
    return build_auth_url(sorted(scopes), user, f'{prefix}{character.character_id}')


async def fetch_contacts(access, character_id):
    client = EsiClient(access_token=access)
    contacts = []
    try:
        page = 1
        while True:
            rows, headers = await client.get_with_headers(f'/characters/{character_id}/contacts/', params={'page':page})
            if not isinstance(rows, list): raise ValueError('Invalid contacts response')
            pages = int(headers.get('x-pages','1'))
            if not 1 <= pages <= 100 or len(contacts) + len(rows) > 100000:
                raise ValueError('Contact response exceeds supported bounds')
            contacts.extend(rows)
            if page >= pages: break
            if not rows: raise ValueError('Incomplete contacts response')
            page += 1
        rules = {}
        for row in contacts:
            if not isinstance(row, dict): raise ValueError('Invalid contact row')
            if row.get('contact_type') not in ('corporation','alliance'): continue
            eve_id, standing = int(row['contact_id']), float(row['standing'])
            if eve_id <= 0 or not math.isfinite(standing) or not -10 <= standing <= 10:
                raise ValueError('Invalid organization standing')
            rules[(row['contact_type'],eve_id)] = {'kind':row['contact_type'],'eve_id':eve_id,'color':standing_color(standing)}
        return list(rules.values())
    finally:
        await client.close()


async def set_source(db, user, token_id, section):
    from app.api.client_links import own_token
    from app.api.esi import refresh_access_token
    user_id = user.id
    if token_id is not None and (user_id in _syncing or len(_syncing) >= 4):
        raise HTTPException(429, 'A standings refresh is already running or the queue is busy; retry shortly')
    existing = db.get(ScanColorSettings, user_id)
    revision = existing.revision if existing else 0
    if token_id is None:
        db.scalar(select(User).where(User.id == user_id).with_for_update())
        row = db.get(ScanColorSettings, user_id, populate_existing=True)
        if row is None: row = ScanColorSettings(user_id=user_id, revision=0); db.add(row)
        row.character_id = None; row.contact_colors = []; row.synced_at = None; row.revision += 1
        db.commit()
        return settings_payload(db, user)
    _syncing.add(user_id)
    try:
        token, character = own_token(db, user, token_id)
        if CONTACT_SCOPE not in effective_token_scopes(token, db):
            raise HTTPException(409, 'Enable read-only contact access for this character first')
        internal_character_id, eve_id = character.id, character.character_id
        try:
            access = await asyncio.wait_for(refresh_access_token(token), timeout=40)
        except asyncio.TimeoutError as exc:
            raise HTTPException(502, 'Character authorization timed out. Your previous standings colors were kept.') from exc
        db.commit()  # Persist refresh-token rotation and release DB before contact paging.
        try:
            rules = await asyncio.wait_for(fetch_contacts(access, eve_id), timeout=60)
        except (asyncio.TimeoutError, ValueError, TypeError, KeyError, HTTPException, httpx.RequestError) as exc:
            raise HTTPException(502, 'Could not refresh organization contacts. Your previous source and colors were kept; retry shortly.') from exc
        db.expire_all()
        user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
        if not user or user.deleted_at or not can_view_section(user, section, db):
            raise HTTPException(403, 'Scan permission is no longer available')
        token, character = own_token(db, user, token_id)
        if character.id != internal_character_id or CONTACT_SCOPE not in effective_token_scopes(token, db):
            raise HTTPException(403, 'Character contact access changed; no new colors were saved')
        row = db.get(ScanColorSettings, user_id, populate_existing=True)
        if (row.revision if row else 0) != revision:
            raise HTTPException(409, 'Your standings source changed during refresh. Reload settings and try again.')
        if row is None: row = ScanColorSettings(user_id=user_id, revision=0); db.add(row)
        row.character_id = internal_character_id; row.contact_colors = rules
        row.synced_at = datetime.now(timezone.utc); row.revision += 1
        db.commit()
        return settings_payload(db, user)
    finally:
        _syncing.discard(user_id)
