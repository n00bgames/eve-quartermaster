from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import EsiToken, EveCharacter, User
from app.services import journey
from app.services.journey_worker import SCOPES
from app.services.esi_scope_policy import effective_token_scopes
from app.services.permissions import can_view_section
from fastapi import HTTPException


def access(response:Response,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    response.headers['Cache-Control']='private, no-store'
    if not can_view_section(user,'navigation',db):
        raise HTTPException(403,'Navigation permission is required')
    return user


router=APIRouter(prefix='/journey',tags=['journey'],dependencies=[Depends(access)])


class SettingsInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled: bool
    interval_seconds: Literal[15,30,60,120,300]=15


def validate_consent_character(db,user_id,mode,eve_id):
    try: expected=int(mode.removeprefix('journey_'))
    except ValueError as exc: raise HTTPException(400,'Invalid journey authorization') from exc
    character=db.scalar(select(EveCharacter).where(EveCharacter.character_id==expected))
    if eve_id!=expected or character is None or character.owner_user_id!=user_id:
        raise HTTPException(403,'Authorize the same linked character selected for Journey')


@router.get('/settings')
def settings(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return journey.settings(db,user)


@router.get('/characters/{character_id}/auth-url')
def consent(character_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from app.api.esi import build_auth_url
    character=journey.own_character(db,user,character_id)
    token=db.scalar(select(EsiToken).where(EsiToken.user_id==user.id,EsiToken.character_id==character_id,EsiToken.revoked_at.is_(None))
        .order_by(EsiToken.created_at.desc(),EsiToken.id.desc()))
    # Eligibility is checked before consent, enrollment stays off until PATCH enabled.
    from app.services.esi_scope_policy import allowed_scopes
    if not SCOPES <= allowed_scopes(db,user): raise HTTPException(403,'Location access is unavailable for this account')
    return build_auth_url(sorted((effective_token_scopes(token,db) if token else set())|SCOPES|{'publicData'}),user,f'journey_{character.character_id}')


@router.patch('/characters/{character_id}')
def configure(character_id:int,payload:SettingsInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return journey.configure(db,user,character_id,payload.enabled,payload.interval_seconds)


@router.delete('/characters/{character_id}')
def clear(character_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return journey.clear_history(db,user,character_id)


@router.get('/characters/{character_id}/history')
def history(character_id:int,from_at:datetime|None=None,to_at:datetime|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return journey.history(db,user,character_id,*journey.window(from_at,to_at))


@router.get('/characters/{character_id}/context')
def context(character_id:int,from_at:datetime|None=None,to_at:datetime|None=None,system_id:int|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return journey.context(db,user,character_id,*journey.window(from_at,to_at),system_id)
