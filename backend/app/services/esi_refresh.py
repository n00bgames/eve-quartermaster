"""Persist OAuth rotations independently of a caller's long-running sync.

Never leave an esi_tokens UPDATE pending in a session that will await ESI. A
second refresh (including Journey) can otherwise block the API's event loop
while the first coroutine needs that same event loop to finish and commit.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from weakref import WeakValueDictionary

import httpx
from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, object_session
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret
from app.models import EsiToken, EveCharacter, User
from app.services.esi_scope_policy import effective_token_scopes


# Keep locks only while a refresh is running or waiting for that authorization.
_refresh_locks = WeakValueDictionary()


@dataclass(frozen=True)
class RefreshSnapshot:
    token_id: int
    user_id: int
    character_id: int
    character_owner_id: int | None
    encrypted: str
    scopes: frozenset[str]


def snapshot(bind, token_id: int) -> RefreshSnapshot:
    with Session(bind, expire_on_commit=False) as db:
        token = db.get(EsiToken, token_id)
        user = db.get(User, token.user_id) if token else None
        character = db.get(EveCharacter, token.character_id) if token else None
        if not token or token.revoked_at or not user or user.deleted_at or not character:
            raise HTTPException(409, "This character authorization is no longer available. Re-link through EVE SSO.")
        scopes = effective_token_scopes(token, db)
        if not scopes:
            raise HTTPException(403, "This account's role does not permit the stored ESI scopes. Re-link with utility scopes.")
        return RefreshSnapshot(token.id, token.user_id, token.character_id, character.owner_user_id, token.encrypted_refresh_token, frozenset(scopes))


def persist(bind, original: RefreshSnapshot, encrypted: str, expires: datetime) -> None:
    try:
        with Session(bind, expire_on_commit=False) as db:
            # Only hold this lock for local validation and commit. NOWAIT also
            # bounds contention with an old process or an explicit unlink.
            # SQLAlchemy's key_share=True without read=True is PostgreSQL's
            # FOR NO KEY UPDATE: compatible with a sync-job FK's KEY SHARE.
            token = db.scalar(select(EsiToken).where(EsiToken.id == original.token_id).with_for_update(nowait=True, key_share=True))
            user = db.get(User, original.user_id)
            character = db.get(EveCharacter, original.character_id)
            if (not token or token.revoked_at or token.user_id != original.user_id
                    or token.character_id != original.character_id or token.encrypted_refresh_token != original.encrypted
                    or not user or user.deleted_at or not character or character.owner_user_id != original.character_owner_id):
                raise HTTPException(409, "Character authorization changed during refresh. Check its status before retrying.")
            if not original.scopes.issubset(effective_token_scopes(token, db)):
                raise HTTPException(403, "Character access changed during refresh. Re-link with the permitted scopes.")
            token.encrypted_refresh_token = encrypted
            token.access_token_expires_at = expires
            db.commit()
    except DBAPIError as exc:
        # No SQL text, bound credential values or upstream body in a job error.
        raise HTTPException(503, "Character authorization is busy. Please retry shortly.", headers={"Retry-After": "5"}) from exc


async def refresh_access_token(token: EsiToken) -> str:
    db = object_session(token)
    identity = inspect(token).identity
    if db is None or identity is None:
        raise HTTPException(409, "Load the character authorization before refreshing it")
    bind = db.get_bind().engine  # Even a connection-bound caller needs a separate transaction.
    token_id = int(identity[0])
    lock = _refresh_locks.setdefault((asyncio.get_running_loop(), bind, token_id), asyncio.Lock())
    async with lock:
        access, encrypted, expires = await _exchange_and_persist(bind, token_id)
        # Synchronize the caller without making the rotated secret dirty again.
        set_committed_value(token, "encrypted_refresh_token", encrypted)
        set_committed_value(token, "access_token_expires_at", expires)
        return access


async def _exchange_and_persist(bind, token_id: int) -> tuple[str, str, datetime]:
    # Both database phases run off the API loop, in separate short sessions.
    # The caller's pending inventory/job/contact edits are never committed here.
    # Read after acquiring the lock so a waiting caller uses the saved rotation.
    original = await asyncio.to_thread(snapshot, bind, token_id)
    settings = get_settings()
    try:
        refresh = decrypt_secret(original.encrypted, settings.token_encryption_key)
    except ValueError as exc:
        raise HTTPException(409, {"message": "This character's stored ESI authorization can no longer be decrypted. Re-link the character through EVE SSO, then try syncing again.", "code": "esi_token_reauthorization_required"}) from exc
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        response = await client.post("https://login.eveonline.com/v2/oauth/token",
            auth=httpx.BasicAuth(settings.eve_sso_client_id, settings.eve_sso_client_secret),
            data={"grant_type": "refresh_token", "refresh_token": refresh, "scope": " ".join(sorted(original.scopes))},
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": "eve-quartermaster/2.3.0 (+https://github.com/n00bgames/eve-quartermaster)"})
    if response.status_code >= 400:
        raise HTTPException(response.status_code, "EVE SSO refresh failed. Check the character authorization before retrying.")
    try:
        payload = response.json()
        access = payload["access_token"]
        if not isinstance(access, str) or not access:
            raise ValueError("Missing access token")
        encrypted = encrypt_secret(payload["refresh_token"], settings.token_encryption_key) if payload.get("refresh_token") else original.encrypted
        expires = datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 1200)))
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(502, "EVE SSO returned an invalid token response.") from exc
    await asyncio.to_thread(persist, bind, original, encrypted, expires)
    return access, encrypted, expires
