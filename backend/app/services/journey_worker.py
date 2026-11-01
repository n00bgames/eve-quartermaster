"""Bounded private location sampler. Short DB leases, no transaction during ESI waits."""
import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import logging
import re
from uuid import uuid4

import httpx
from sqlalchemy import or_, select, update
from app.db.session import SessionLocal
from app.models import EveCharacter, EsiToken, User
from app.models.journey import JourneyTracker, JourneyVisit
from app.services.esi_client import EsiClient, USER_AGENT
from app.services.esi_scope_policy import effective_token_scopes
from app.services.permissions import can_view_section
from app.domain.intel import utc

SCOPES = {'esi-location.read_location.v1', 'esi-location.read_online.v1'}
_task = None
_access = {}  # bounded transient bearer cache, never persisted or included in responses/logs
_online = {}


def now():
    return datetime.now(timezone.utc)


def character_token(db, user_id, character_id):
    user = db.get(User, user_id, populate_existing=True)
    character = db.get(EveCharacter, character_id, populate_existing=True)
    if not user or user.deleted_at or not character or character.owner_user_id != user_id or not can_view_section(user, 'navigation', db):
        return None
    tokens = db.scalars(select(EsiToken).where(EsiToken.user_id == user_id, EsiToken.character_id == character_id,
        EsiToken.revoked_at.is_(None)).order_by(EsiToken.created_at.desc(), EsiToken.id.desc())).all()
    return next((t for t in tokens if SCOPES <= effective_token_scopes(t, db)), None)


def claim(db, tracker_id, lease, at):
    result = db.execute(update(JourneyTracker).where(JourneyTracker.id == tracker_id, JourneyTracker.enabled.is_(True),
        or_(JourneyTracker.next_poll_at.is_(None), JourneyTracker.next_poll_at <= at),
        or_(JourneyTracker.lease_until.is_(None), JourneyTracker.lease_until <= at))
        .values(lease_token=lease, lease_until=at + timedelta(seconds=90)))
    db.commit()
    return result.rowcount == 1


def owned(db, tracker_id, lease):
    return db.scalar(select(JourneyTracker).where(JourneyTracker.id == tracker_id,
        JourneyTracker.lease_token == lease, JourneyTracker.enabled.is_(True), JourneyTracker.lease_until > now())
        .with_for_update().execution_options(populate_existing=True))


def cache_seconds(headers, default):
    """Honor remaining Cache-Control lifetime; Expires is a legacy fallback only."""
    try:
        if any(value in headers.get('cache-control', '').lower() for value in ('no-store', 'no-cache')):
            return 0
        match = re.search(r'(?:^|,)\s*(?:s-maxage|max-age)\s*=\s*"?(\d+)', headers.get('cache-control', ''), re.I)
        if match:
            return max(0, int(match[1]) - int(headers.get('age', '0')))
        if headers.get('expires'):
            return max(0, (parsedate_to_datetime(headers['expires']) - now()).total_seconds())
    except (ValueError, TypeError, OverflowError):
        pass
    return default


async def refresh_access(encrypted):
    # The standard sync refresher needs an attached ORM session. This minimal,
    # journey-only refresh deliberately runs after our DB session is closed.
    from app.core.config import get_settings
    from app.core.security import decrypt_secret, encrypt_secret
    settings = get_settings()
    secret = decrypt_secret(encrypted, settings.token_encryption_key)
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.post('https://login.eveonline.com/v2/oauth/token',
            auth=httpx.BasicAuth(settings.eve_sso_client_id, settings.eve_sso_client_secret),
            data={'grant_type': 'refresh_token', 'refresh_token': secret, 'scope': ' '.join(sorted(SCOPES))},
            headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    response.raise_for_status()
    payload = response.json()
    rotated = encrypt_secret(payload['refresh_token'], settings.token_encryption_key) if payload.get('refresh_token') else encrypted
    return payload['access_token'], rotated, now() + timedelta(seconds=max(30, int(payload.get('expires_in', 1200)) - 60))


async def fetch_sample(access, eve_id, key):
    client = EsiClient(access_token=access)
    try:
        cached = _online.get(key)
        if not cached or cached[1] <= now():
            online, headers = await asyncio.wait_for(client.get_with_headers(f'/characters/{eve_id}/online/'), 15)
            if not isinstance(online, dict) or type(online.get('online')) is not bool:
                raise ValueError('Malformed online response')
            cached = (online['online'], now() + timedelta(seconds=cache_seconds(headers, 60)))
            if len(_online) >= 1000:
                _online.clear()
            _online[key] = cached
        if not cached[0]:
            return None, max(15, (cached[1] - now()).total_seconds())
        location, headers = await asyncio.wait_for(client.get_with_headers(f'/characters/{eve_id}/location/'), 15)
        sid = location.get('solar_system_id') if isinstance(location, dict) else None
        if type(sid) is not int or sid <= 0:
            raise ValueError('Malformed location response')
        # Store solar system only, not station/structure IDs or exact coordinates.
        return sid, cache_seconds(headers, 5)
    finally:
        await client.close()


def observe(db, tracker, system_id, at):
    if tracker.last_seen_at and at <= utc(tracker.last_seen_at):
        return
    previous = db.get(JourneyVisit, tracker.current_visit_id) if tracker.current_visit_id else None
    if previous and (previous.tracker_id != tracker.id or (at - utc(previous.last_seen_at)).total_seconds() > max(90, tracker.interval_seconds * 3)):
        previous = None
    if previous and previous.system_id == system_id:
        # Clock regressions/repeated delivery never extend or duplicate a sample.
        if at > utc(previous.last_seen_at):
            previous.last_seen_at = at
            previous.samples += 1
    else:
        visit = JourneyVisit(tracker_id=tracker.id, system_id=system_id, first_seen_at=at, last_seen_at=at,
            samples=1, gap_before=previous is None)
        db.add(visit); db.flush(); tracker.current_visit_id = visit.id
    tracker.last_seen_at = at


async def poll(tracker_id, factory=SessionLocal, fetch=fetch_sample, refresh=refresh_access):
    lease = str(uuid4())
    with factory() as db:
        if not claim(db, tracker_id, lease, now()):
            return
        tracker = owned(db, tracker_id, lease)
        token = character_token(db, tracker.user_id, tracker.character_id) if tracker else None
        if not token:
            if tracker:
                tracker.state = 'authorization_needed'; tracker.enabled = False; tracker.current_visit_id = None
                tracker.lease_token = None; tracker.lease_until = None
                db.commit()
            return
        token_id, encrypted = token.id, token.encrypted_refresh_token
        user_id, character_id = tracker.user_id, tracker.character_id
        eve_id = db.get(EveCharacter, tracker.character_id).character_id
    try:
        fingerprint = sha256(encrypted.encode()).hexdigest()
        cached = _access.get(token_id)
        if not cached or cached[0] != fingerprint or cached[2] <= now():
            access, rotated, expires = await asyncio.wait_for(refresh(encrypted), 25)
            with factory() as db:
                # OAuth rotation is credential maintenance even if collection was
                # paused in flight. Preserve it without reviving a revoked token,
                # crossing an ownership change or overwriting a newer credential.
                token = db.get(EsiToken, token_id, populate_existing=True)
                character = db.get(EveCharacter, character_id, populate_existing=True)
                user = db.get(User, user_id, populate_existing=True)
                if not token or token.revoked_at or token.user_id != user_id or token.character_id != character_id or not character or character.owner_user_id != user_id or not user or user.deleted_at:
                    return
                saved = db.execute(update(EsiToken).where(EsiToken.id == token_id,
                    EsiToken.encrypted_refresh_token == encrypted, EsiToken.revoked_at.is_(None))
                    .values(encrypted_refresh_token=rotated, access_token_expires_at=expires))
                db.commit()
                if saved.rowcount != 1:
                    return
                tracker = owned(db, tracker_id, lease)
                token = character_token(db, user_id, character_id) if tracker else None
                if not tracker or not token or token.id != token_id:
                    return  # Consent/ownership must still permit collecting location.
                db.commit()
            fingerprint = sha256(rotated.encode()).hexdigest()
            if len(_access) >= 1000:
                _access.clear()
            _access[token_id] = (fingerprint, access, expires)
        else:
            access = cached[1]
        # Existing transport handles error budgets/rate limits; outer timeout also bounds waiting.
        system_id, delay = await asyncio.wait_for(fetch(access, eve_id, (token_id, fingerprint)), 35)
        at = now()
        with factory() as db:
            tracker = owned(db, tracker_id, lease)
            token = character_token(db, tracker.user_id, tracker.character_id) if tracker else None
            if not tracker or not token or token.id != token_id or sha256(token.encrypted_refresh_token.encode()).hexdigest() != fingerprint:
                return
            tracker.checked_at = at; tracker.failures = 0
            tracker.state = 'tracking' if system_id is not None else 'offline'
            if system_id is not None:
                observe(db, tracker, system_id, at)
            else:
                tracker.current_visit_id = None
            tracker.next_poll_at = at + timedelta(seconds=max(tracker.interval_seconds, min(86400, delay)))
            tracker.lease_token = None; tracker.lease_until = None
            db.commit()
    except asyncio.CancelledError:
        raise  # Lease expiry recovers an interrupted sampler after restart.
    except Exception as error:
        # Never log response bodies, credentials, systems or character names.
        logging.getLogger(__name__).warning('Journey sampler interrupted (%s)', type(error).__name__)
        _access.pop(token_id, None)
        with factory() as db:
            tracker = owned(db, tracker_id, lease)
            if tracker:
                terminal = isinstance(error, httpx.HTTPStatusError) and error.response.status_code in {400,401,403}
                terminal = terminal or getattr(error, 'status_code', None) in {401,403}
                tracker.failures += 1; tracker.checked_at = now(); tracker.state = 'authorization_needed' if terminal else 'unavailable'
                if terminal: tracker.enabled = False
                tracker.current_visit_id = None
                tracker.next_poll_at = now() + timedelta(seconds=min(1800, 30 * 2 ** min(tracker.failures, 6)))
                tracker.lease_token = None; tracker.lease_until = None
                db.commit()


async def worker_loop():
    while True:
        try:
            with SessionLocal() as db:
                ids = db.scalars(select(JourneyTracker.id).where(JourneyTracker.enabled.is_(True),
                    or_(JourneyTracker.next_poll_at.is_(None), JourneyTracker.next_poll_at <= now()),
                    or_(JourneyTracker.lease_until.is_(None), JourneyTracker.lease_until <= now()))
                    .order_by(JourneyTracker.next_poll_at, JourneyTracker.id).limit(4)).all()
            if ids:
                await asyncio.gather(*(poll(i, factory=SessionLocal, fetch=fetch_sample, refresh=refresh_access) for i in ids))
            await asyncio.sleep(.5 if len(ids)==4 else 2)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).warning('Journey scheduler unavailable; retrying')
            await asyncio.sleep(10)


def start_journey_worker():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(worker_loop())


async def stop_journey_worker():
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
    _access.clear(); _online.clear()
