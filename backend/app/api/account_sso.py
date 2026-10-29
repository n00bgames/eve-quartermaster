"""Identity-only EVE SSO login and invitation acceptance.

Uses the existing registered ESI callback. No EVE/EQM access tokens appear in
frontend URLs. Character ownership is validated before an account session exists.
"""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api import auth
from app.api.password_recovery import limit
from app.core.config import get_settings
from app.core.security import create_session_token, decrypt_secret, encrypt_secret, hash_password
from app.db.session import get_db
from app.models import AccountSsoAttempt, EsiToken, EveCharacter, User, UserInvite
from app.services.eve_sso import validate_eve_access_token
from app.services.permissions import assign_roles, role_rank, ROLE_RANK

router = APIRouter(prefix='/auth/sso', tags=['account SSO'])
STATE_PREFIX = 'account.'
FLOW_COOKIE = 'eq_sso_browser'
FAILED = 'EVE sign-in could not be completed. Please start again.'
UNLINKED = 'This character is not linked to an active EQM account. Use an invite, or sign in with your password and link it first.'


class StartInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    invite_token: str | None = Field(default=None, min_length=32, max_length=128)
    remember_me: bool = False


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def active_invite(db, invite_id):
    at = datetime.now(timezone.utc)
    invite = db.scalar(select(UserInvite).where(UserInvite.id == invite_id,
        UserInvite.accepted_at.is_(None), UserInvite.revoked_at.is_(None),
        (UserInvite.expires_at.is_(None)) | (UserInvite.expires_at > at)).execution_options(populate_existing=True))
    if not invite:
        raise HTTPException(400, 'The invite is no longer available. Request a new invite.')
    inviter = db.get(User, invite.created_by_user_id, populate_existing=True)
    roles = invite.roles_json or [invite.role]
    if not inviter or inviter.deleted_at is not None or role_rank(inviter, db) < ROLE_RANK['admin']:
        raise HTTPException(400, 'The invite is no longer available. Request a new invite.')
    auth.requested_account_roles({'roles': roles}, inviter, db)
    return invite


@router.post('/start')
def start(payload: StartInput, request: Request, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    if not all((settings.eve_sso_client_id, settings.eve_sso_client_secret, settings.token_encryption_key)):
        raise HTTPException(503, 'EVE SSO is not configured. Contact your EQM administrator.')
    ip = request.client.host if request.client else 'unknown'
    if not limit(db, 'account-sso:'+ip, 60):
        raise HTTPException(429, 'Too many EVE sign-in attempts. Please retry later.')
    invite = None
    if payload.invite_token:
        invite = db.scalar(select(UserInvite).where(UserInvite.token_hash == auth.hash_invite_token(payload.invite_token)))
        invite = active_invite(db, invite.id if invite else None)
    at = datetime.now(timezone.utc)
    db.execute(delete(AccountSsoAttempt).where(AccountSsoAttempt.expires_at < at).execution_options(synchronize_session=False))
    state = STATE_PREFIX + secrets.token_urlsafe(32)
    browser = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    db.add(AccountSsoAttempt(token_hash=digest(state), browser_hash=digest(browser),
        encrypted_verifier=encrypt_secret(verifier, settings.token_encryption_key),
        invite_id=invite.id if invite else None, remember_me=payload.remember_me, expires_at=at+timedelta(minutes=10)))
    db.commit()
    response.set_cookie(FLOW_COOKIE, browser, max_age=600, httponly=True,
        secure=settings.frontend_url.startswith('https://'), samesite='lax', path=settings.api_prefix or '/')
    response.headers['Cache-Control'] = 'no-store'
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    query = urlencode({'response_type':'code', 'client_id':settings.eve_sso_client_id,
        'redirect_uri':settings.eve_sso_callback_url, 'scope':'publicData', 'state':state,
        'code_challenge':challenge, 'code_challenge_method':'S256'})
    return {'url':'https://login.eveonline.com/v2/oauth/authorize/?'+query}


def identity(claims):
    subject = claims.get('sub', '')
    owner = claims.get('owner')
    if not isinstance(subject, str) or not re.fullmatch(r'CHARACTER:EVE:[1-9][0-9]*', subject):
        raise HTTPException(400, FAILED)
    if not isinstance(owner, str) or not owner or not owner.isascii() or len(owner) > 128:
        raise HTTPException(400, FAILED)
    return int(subject.rsplit(':', 1)[1]), owner


async def exchange(code, verifier):
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        response = await client.post('https://login.eveonline.com/v2/oauth/token',
            auth=httpx.BasicAuth(settings.eve_sso_client_id, settings.eve_sso_client_secret),
            data={'grant_type':'authorization_code','code':code,'code_verifier':verifier,
                  'redirect_uri':settings.eve_sso_callback_url, 'client_id':settings.eve_sso_client_id})
    if response.status_code != 200:
        raise HTTPException(400, FAILED)
    payload = response.json()
    claims = await validate_eve_access_token(payload['access_token'])
    return payload, claims


async def existing_account(db, eve_id, owner_hash):
    from app.api.esi import refresh_access_token
    tokens = list(db.scalars(select(EsiToken).join(EveCharacter, EveCharacter.id == EsiToken.character_id).where(
        EveCharacter.character_id == eve_id, EveCharacter.owner_user_id == EsiToken.user_id,
        EsiToken.revoked_at.is_(None))))
    if len(tokens) != 1:
        raise HTTPException(403, UNLINKED)
    token = tokens[0]
    user = db.get(User, token.user_id, populate_existing=True)
    if not user or user.deleted_at is not None or user.password_reset_required:
        raise HTTPException(403, UNLINKED)
    version, token_id, user_id = user.auth_version, token.id, user.id
    if not token.sso_owner_hash:
        # Legacy links require proof from their own existing refresh token. An ID
        # match alone would let a transferred character unlock its former account.
        old_claims = await validate_eve_access_token(await refresh_access_token(token))
        old_id, old_hash = identity(old_claims)
        if old_id != eve_id or not hmac.compare_digest(old_hash, owner_hash):
            raise HTTPException(403, UNLINKED)
        token.sso_owner_hash = old_hash
        db.commit()  # Persist any rotated refresh token before issuing a session.
    db.expire_all()
    token = db.get(EsiToken, token_id)
    user = db.get(User, user_id)
    character = db.get(EveCharacter, token.character_id) if token else None
    if (not token or token.revoked_at or token.user_id != user_id or not character
        or character.owner_user_id != user_id or not user or user.deleted_at
        or user.password_reset_required or user.auth_version != version
        or not token.sso_owner_hash or not hmac.compare_digest(token.sso_owner_hash, owner_hash)):
        raise HTTPException(403, UNLINKED)
    return user


async def invited_account(db, invite_id, payload, claims, eve_id, owner_hash):
    from app.api.esi import ensure_owner
    from app.models.enums import OwnerKind
    invite = active_invite(db, invite_id)
    # Never merge an invite into an existing account or steal a linked character.
    if db.scalar(select(User.id).where(User.email == invite.email)):
        raise HTTPException(409, 'An account already exists for this invite. Sign in and link your character there.')
    character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == eve_id))
    if character and (character.owner_user_id is not None or db.scalar(select(EsiToken.id).where(EsiToken.character_id == character.id, EsiToken.revoked_at.is_(None)))):
        raise HTTPException(409, 'This character is already linked. Sign in to its EQM account instead.')
    granted = payload.get('scope') or claims.get('scp') or []
    scopes = set(granted.split() if isinstance(granted, str) else granted)
    if scopes - {'publicData'} or not payload.get('refresh_token'):
        raise HTTPException(400, 'EVE did not return the identity-only authorization. Start again.')
    name = claims.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise HTTPException(400, FAILED)
    # An unknown random password preserves existing account/admin invariants.
    # No usable password is given to the browser; recovery can establish one later.
    password_hash = await run_in_threadpool(hash_password, secrets.token_urlsafe(48))
    db.expire_all()
    invite = active_invite(db, invite_id)
    auth.claim_invite(db, invite)
    user = User(email=invite.email, display_name=name, role=invite.role, password_hash=password_hash, main_character_id=eve_id)
    db.add(user); db.flush()
    assign_roles(db, user, invite.roles_json or [invite.role])
    # Serialize competing invitation/link callbacks for this character.
    character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == eve_id).with_for_update().execution_options(populate_existing=True))
    if character and character.owner_user_id is not None:
        raise HTTPException(409, 'This character is already linked. Sign in to its EQM account instead.')
    if character is None:
        character = EveCharacter(character_id=eve_id, name=name)
        db.add(character)
    character.name = name; character.owner_user_id = user.id
    db.flush()
    ensure_owner(db, OwnerKind.CHARACTER, name, character_id=character.id)
    settings = get_settings()
    db.add(EsiToken(user_id=user.id, character_id=character.id, scopes='publicData', sso_owner_hash=owner_hash,
        encrypted_refresh_token=encrypt_secret(payload['refresh_token'], settings.token_encryption_key),
        access_token_expires_at=datetime.now(timezone.utc)+timedelta(seconds=int(payload.get('expires_in',1200)))))
    invite.accepted_by_user_id = user.id
    db.commit(); db.refresh(user)
    return user


async def callback(request, db, state, code=None, error=None):
    settings = get_settings()
    response = None
    try:
        at = datetime.now(timezone.utc)
        attempt = db.scalar(select(AccountSsoAttempt).where(AccountSsoAttempt.token_hash == digest(state),
            AccountSsoAttempt.consumed_at.is_(None), AccountSsoAttempt.expires_at > at))
        browser = request.cookies.get(FLOW_COOKIE, '')
        if not attempt or not browser or not hmac.compare_digest(attempt.browser_hash, digest(browser)):
            raise HTTPException(400, FAILED)
        claimed = db.execute(update(AccountSsoAttempt).where(AccountSsoAttempt.token_hash == attempt.token_hash,
            AccountSsoAttempt.consumed_at.is_(None), AccountSsoAttempt.expires_at > at).values(consumed_at=at).execution_options(synchronize_session="fetch"))
        if claimed.rowcount != 1:
            raise HTTPException(400, FAILED)
        verifier = decrypt_secret(attempt.encrypted_verifier, settings.token_encryption_key)
        invite_id, remember = attempt.invite_id, attempt.remember_me
        db.commit()
        if error or not code:
            raise HTTPException(400, 'EVE sign-in was cancelled. You can try again.')
        payload, claims = await exchange(code, verifier)
        eve_id, owner_hash = identity(claims)
        user = await invited_account(db, invite_id, payload, claims, eve_id, owner_hash) if invite_id else await existing_account(db, eve_id, owner_hash)
        token = create_session_token(user, {'role':user.role, 'remember_me':remember},
            expires_minutes=settings.remember_me_days*24*60 if remember else None)
        response = RedirectResponse(settings.frontend_url.rstrip('/')+'/?sso_status=signed_in', status_code=303)
        response.set_cookie(auth.REMEMBER_ME_COOKIE, token, httponly=True,
            max_age=settings.remember_me_days*24*60*60 if remember else None,
            secure=settings.frontend_url.startswith('https://'), samesite='lax', path=settings.api_prefix or '/')
    except (HTTPException, httpx.HTTPError, ValueError, KeyError, IntegrityError) as exc:
        db.rollback()
        message = str(exc.detail) if isinstance(exc, HTTPException) and isinstance(exc.detail, str) and exc.detail in {FAILED,UNLINKED,
            'EVE sign-in was cancelled. You can try again.',
            'The invite is no longer available. Request a new invite.',
            'An account already exists for this invite. Sign in and link your character there.',
            'This character is already linked. Sign in to its EQM account instead.',
            'EVE did not return the identity-only authorization. Start again.'} else FAILED
        response = RedirectResponse(settings.frontend_url.rstrip('/')+'/?'+urlencode({'sso_error':message}),status_code=303)
    response.delete_cookie(FLOW_COOKIE, path=settings.api_prefix or '/', httponly=True,
        secure=settings.frontend_url.startswith('https://'), samesite='lax')
    response.headers.update({'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer'})
    return response
