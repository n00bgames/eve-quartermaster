from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import ROLE_RANK, get_current_user
from app.db.session import get_db
from app.models import Asset, EsiSyncJob, EsiToken, EveAlliance, EveCharacter, EveCorporation, OwnershipEntity, User
from app.models.enums import OwnerKind

router = APIRouter(prefix="/corporations", tags=["corporations"])
CORPORATION_ASSET_SCOPE = "esi-assets.read_corporation_assets.v1"


def token_scope_set(token: EsiToken) -> set[str]:
    return {scope.strip() for scope in (token.scopes or "").split() if scope.strip()}


def require_corporation_view(user: User) -> None:
    if ROLE_RANK.get(user.role, -1) < ROLE_RANK["officer"]:
        raise HTTPException(status_code=403, detail="officer role is required")


def can_sync_corporation(user: User) -> bool:
    return ROLE_RANK.get(user.role, -1) >= ROLE_RANK["director"]


def serialize_corporation(corp: EveCorporation, current_user: User, db: Session) -> dict[str, Any]:
    owner = db.scalar(select(OwnershipEntity).where(OwnershipEntity.owner_kind == OwnerKind.CORPORATION, OwnershipEntity.corporation_id == corp.id))
    latest_job = None
    asset_rows = 0
    if owner:
        asset_rows = db.scalar(select(func.count()).select_from(Asset).where(Asset.ownership_entity_id == owner.id)) or 0
        latest_job = db.scalar(
            select(EsiSyncJob)
            .where(EsiSyncJob.ownership_entity_id == owner.id, EsiSyncJob.sync_type == "corporation_assets")
            .order_by(EsiSyncJob.finished_at.desc().nullslast(), EsiSyncJob.created_at.desc())
            .limit(1)
        )

    alliance = db.get(EveAlliance, corp.alliance_id) if corp.alliance_id else None
    token_rows = db.execute(
        select(EsiToken, EveCharacter, User)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .join(User, User.id == EsiToken.user_id)
        .where(EsiToken.revoked_at.is_(None), EveCharacter.corporation_id == corp.id)
        .order_by(EveCharacter.name)
    ).all()
    eligible_tokens = []
    for token, character, user in token_rows:
        has_scope = CORPORATION_ASSET_SCOPE in token_scope_set(token)
        visible_token = token.user_id == current_user.id or can_sync_corporation(current_user)
        if not visible_token:
            continue
        eligible_tokens.append(
            {
                "token_id": token.id,
                "character_name": character.name,
                "user_display_name": user.display_name,
                "has_corporation_asset_scope": has_scope,
                "can_sync": has_scope and can_sync_corporation(current_user),
            }
        )

    return {
        "id": corp.id,
        "corporation_id": corp.corporation_id,
        "name": corp.name,
        "ticker": corp.ticker,
        "alliance_name": alliance.name if alliance else None,
        "ceo_character_eve_id": corp.ceo_character_eve_id,
        "last_synced_at": corp.last_synced_at.isoformat() if corp.last_synced_at else None,
        "asset_rows": asset_rows,
        "last_asset_sync_at": (latest_job.finished_at or latest_job.started_at or latest_job.created_at).isoformat() if latest_job else None,
        "last_asset_sync_status": latest_job.status.value if latest_job else None,
        "last_asset_sync_message": latest_job.message if latest_job else None,
        "eligible_tokens": eligible_tokens,
    }


@router.get("")
def list_corporations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_corporation_view(current_user)
    corporations = db.scalars(select(EveCorporation).order_by(EveCorporation.name)).all()
    return [serialize_corporation(corp, current_user, db) for corp in corporations]
