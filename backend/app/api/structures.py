"""Viewer-authorized read-only structure dashboard and explicit SSO consent."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import EsiToken, EveCharacter, EveCorporation, User
from app.services import structures as service
from app.services.esi_client import EsiClient
from app.services.esi_refresh import refresh_access_token
from app.services.esi_scope_policy import allowed_scopes, effective_token_scopes
from app.services.permissions import can_view_section


def access(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    if not can_view_section(user, "structures", db):
        raise HTTPException(403, "Structures permission is required")
    return user


router = APIRouter(prefix="/structures", tags=["structures"], dependencies=[Depends(access)])


def own_token(db, user, token_id):
    token = db.get(EsiToken, token_id)
    character = db.get(EveCharacter, token.character_id) if token else None
    if (not token or token.revoked_at or token.user_id != user.id or not character
            or character.owner_user_id != user.id):
        raise HTTPException(404, "Linked character was not found")
    return token, character


def validate_consent_character(db, user_id, mode, eve_id):
    try:
        expected = int(mode.removeprefix("owned_structures_"))
    except ValueError as exc:
        raise HTTPException(400, "Invalid Structures authorization") from exc
    character = db.scalar(select(EveCharacter).where(EveCharacter.character_id == expected))
    if eve_id != expected or character is None or character.owner_user_id != user_id:
        raise HTTPException(403, "Authorize the same linked character selected for Structures")


@router.get("/links")
def links(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(EsiToken, EveCharacter).join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.user_id == user.id, EveCharacter.owner_user_id == user.id, EsiToken.revoked_at.is_(None))
        .order_by(EveCharacter.name, EsiToken.id.desc())).all()
    result, seen = [], set()
    for token, character in rows:
        if character.id in seen:
            continue
        seen.add(character.id)
        corp = db.get(EveCorporation, character.corporation_id) if character.corporation_id else None
        scopes = effective_token_scopes(token, db)
        result.append({"token_id": token.id, "character_name": character.name,
                       "corporation_name": corp.name if corp else "Corporation not linked",
                       "upwell_authorized": service.UPWELL_SCOPE in scopes,
                       "pos_authorized": service.POS_SCOPE in scopes})
    return {"characters": result}


@router.get("/tokens/{token_id}/auth-url")
def consent(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.api.esi import build_auth_url
    token, character = own_token(db, user, token_id)
    if not service.SCOPES <= allowed_scopes(db, user):
        raise HTTPException(403, "Structure collection is unavailable for this account")
    scopes = effective_token_scopes(token, db) | service.SCOPES | {"publicData"}
    return build_auth_url(sorted(scopes), user, f"owned_structures_{character.character_id}")


@router.get("/tokens/{token_id}")
async def overview(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token, character = own_token(db, user, token_id)
    scopes = effective_token_scopes(token, db)
    if not scopes & service.SCOPES:
        raise HTTPException(409, "Reauthorize this character for Structures first")
    client = EsiClient(access_token=await refresh_access_token(token))
    try:
        return await service.overview(client, db, character, scopes)
    finally:
        await client.close()


@router.get("/tokens/{token_id}/pos/{starbase_id}")
async def pos_detail(token_id: int, starbase_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token, character = own_token(db, user, token_id)
    if service.POS_SCOPE not in effective_token_scopes(token, db):
        raise HTTPException(409, "Reauthorize this character for POS access first")
    client = EsiClient(access_token=await refresh_access_token(token))
    try:
        return await service.pos_detail(client, db, character, starbase_id)
    finally:
        await client.close()


# Manual records use the same section gate without requiring a character token.
from app.api.manual_pos import router as manual_pos_router
router.include_router(manual_pos_router)
