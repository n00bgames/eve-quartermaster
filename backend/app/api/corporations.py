from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Asset, Blueprint, CorporationWalletDivision, EsiSyncJob, EsiToken, EveAlliance, EveCharacter, EveCorporation, OwnershipEntity, User
from app.models.enums import OwnerKind
from app.services.permissions import ROLE_RANK, can_view_section, role_rank

router = APIRouter(prefix="/corporations", tags=["corporations"])
CORPORATION_ASSET_SCOPE = "esi-assets.read_corporation_assets.v1"
CORPORATION_BLUEPRINT_SCOPE = "esi-corporations.read_blueprints.v1"
CORPORATION_WALLET_SCOPE = "esi-wallet.read_corporation_wallets.v1"
STALE_AFTER = timedelta(hours=24)


def token_scope_set(token: EsiToken) -> set[str]:
    return {scope.strip() for scope in (token.scopes or "").split() if scope.strip()}


def require_corporation_view(user: User, db: Session) -> None:
    if not can_view_section(user, "corporations", db):
        raise HTTPException(status_code=403, detail="Corporations permission is required")


def can_sync_corporation(user: User, db: Session) -> bool:
    return role_rank(user, db) >= ROLE_RANK["director"]


def job_time(job: EsiSyncJob | None) -> datetime | None:
    if job is None:
        return None
    return job.finished_at or job.started_at or job.created_at


def is_stale(sync_time: datetime | None) -> bool:
    if sync_time is None:
        return True
    return sync_time < datetime.now(timezone.utc) - STALE_AFTER


def serialize_corporation(corp: EveCorporation, current_user: User, db: Session) -> dict[str, Any]:
    owner = db.scalar(select(OwnershipEntity).where(OwnershipEntity.owner_kind == OwnerKind.CORPORATION, OwnershipEntity.corporation_id == corp.id))
    latest_asset_job = None
    latest_blueprint_job = None
    latest_wallet_job = None
    asset_rows = 0
    blueprint_rows = 0
    if owner:
        asset_rows = db.scalar(select(func.count()).select_from(Asset).where(Asset.ownership_entity_id == owner.id)) or 0
        blueprint_rows = db.scalar(select(func.count()).select_from(Blueprint).where(Blueprint.ownership_entity_id == owner.id)) or 0
        latest_asset_job = db.scalar(
            select(EsiSyncJob)
            .where(EsiSyncJob.ownership_entity_id == owner.id, EsiSyncJob.sync_type == "corporation_assets")
            .order_by(EsiSyncJob.finished_at.desc().nullslast(), EsiSyncJob.created_at.desc())
            .limit(1)
        )
        latest_blueprint_job = db.scalar(
            select(EsiSyncJob)
            .where(EsiSyncJob.ownership_entity_id == owner.id, EsiSyncJob.sync_type == "corporation_blueprints")
            .order_by(EsiSyncJob.finished_at.desc().nullslast(), EsiSyncJob.created_at.desc())
            .limit(1)
        )
        latest_wallet_job = db.scalar(
            select(EsiSyncJob)
            .where(EsiSyncJob.ownership_entity_id == owner.id, EsiSyncJob.sync_type == "corporation_wallets")
            .order_by(EsiSyncJob.finished_at.desc().nullslast(), EsiSyncJob.created_at.desc())
            .limit(1)
        )

    alliance = db.get(EveAlliance, corp.alliance_id) if corp.alliance_id else None
    ceo = db.scalar(select(EveCharacter).where(EveCharacter.character_id == corp.ceo_character_eve_id)) if corp.ceo_character_eve_id else None
    asset_sync_time = job_time(latest_asset_job)
    blueprint_sync_time = job_time(latest_blueprint_job)
    wallet_sync_time = job_time(latest_wallet_job)
    wallet_divisions = db.scalars(select(CorporationWalletDivision).where(CorporationWalletDivision.corporation_id == corp.id).order_by(CorporationWalletDivision.division)).all()
    token_rows = db.execute(
        select(EsiToken, EveCharacter, User)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .join(User, User.id == EsiToken.user_id)
        .where(EsiToken.revoked_at.is_(None), EveCharacter.corporation_id == corp.id)
        .order_by(EveCharacter.name)
    ).all()
    eligible_tokens = []
    for token, character, user in token_rows:
        scopes = token_scope_set(token)
        has_asset_scope = CORPORATION_ASSET_SCOPE in scopes
        has_blueprint_scope = CORPORATION_BLUEPRINT_SCOPE in scopes
        has_wallet_scope = CORPORATION_WALLET_SCOPE in scopes
        visible_token = token.user_id == current_user.id or can_sync_corporation(current_user, db)
        if not visible_token:
            continue
        eligible_tokens.append(
            {
                "token_id": token.id,
                "character_name": character.name,
                "user_display_name": user.display_name,
                "has_corporation_asset_scope": has_asset_scope,
                "can_sync": has_asset_scope and can_sync_corporation(current_user, db),
                "has_corporation_blueprint_scope": has_blueprint_scope,
                "can_sync_blueprints": has_blueprint_scope and can_sync_corporation(current_user, db),
                "has_corporation_wallet_scope": has_wallet_scope,
                "can_sync_wallets": has_wallet_scope and can_sync_corporation(current_user, db),
            }
        )

    return {
        "id": corp.id,
        "corporation_id": corp.corporation_id,
        "name": corp.name,
        "ticker": corp.ticker,
        "alliance_name": alliance.name if alliance else None,
        "ceo_character_eve_id": corp.ceo_character_eve_id,
        "ceo_character_name": ceo.name if ceo else None,
        "member_count": corp.member_count,
        "last_synced_at": corp.last_synced_at.isoformat() if corp.last_synced_at else None,
        "asset_rows": asset_rows,
        "blueprint_rows": blueprint_rows,
        "last_asset_sync_at": asset_sync_time.isoformat() if asset_sync_time else None,
        "last_asset_sync_status": latest_asset_job.status.value if latest_asset_job else None,
        "last_asset_sync_message": latest_asset_job.message if latest_asset_job else None,
        "asset_sync_stale": is_stale(asset_sync_time),
        "last_blueprint_sync_at": blueprint_sync_time.isoformat() if blueprint_sync_time else None,
        "last_blueprint_sync_status": latest_blueprint_job.status.value if latest_blueprint_job else None,
        "last_blueprint_sync_message": latest_blueprint_job.message if latest_blueprint_job else None,
        "blueprint_sync_stale": is_stale(blueprint_sync_time),
        "last_wallet_sync_at": wallet_sync_time.isoformat() if wallet_sync_time else None,
        "last_wallet_sync_status": latest_wallet_job.status.value if latest_wallet_job else None,
        "last_wallet_sync_message": latest_wallet_job.message if latest_wallet_job else None,
        "wallet_sync_stale": is_stale(wallet_sync_time),
        "wallet_divisions": [
            {
                "division": wallet.division,
                "balance": float(wallet.balance),
                "last_synced_at": wallet.last_synced_at.isoformat() if wallet.last_synced_at else None,
            }
            for wallet in wallet_divisions
        ],
        "eligible_tokens": eligible_tokens,
    }


@router.get("")
def list_corporations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_corporation_view(current_user, db)
    corporations = db.scalars(select(EveCorporation).order_by(EveCorporation.name)).all()
    return [serialize_corporation(corp, current_user, db) for corp in corporations]










