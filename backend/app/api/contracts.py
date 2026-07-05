from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.api.esi import refresh_access_token, require_scope
from app.db.session import get_db
from app.models import EsiSyncJob, EsiToken, EveCharacter, EveContract, EveCorporation, User
from app.models.enums import SyncStatus
from app.services.contracts import ACTIVE_CONTRACT_STATUSES, fetch_contract_pages, serialize_contract, upsert_contract_rows
from app.services.esi_client import EsiClient
from app.services.permissions import ROLE_RANK, can_view_section, role_rank

router = APIRouter(prefix="/contracts", tags=["contracts"])
CHARACTER_CONTRACT_SCOPE = "esi-contracts.read_character_contracts.v1"
CORPORATION_CONTRACT_SCOPE = "esi-contracts.read_corporation_contracts.v1"


def require_contracts(current_user: User, db: Session) -> None:
    if not can_view_section(current_user, "contracts", db):
        raise HTTPException(status_code=403, detail="contracts permission is required")


def contract_token_payload(token: EsiToken, character: EveCharacter, owner: User, db: Session) -> dict[str, Any]:
    scopes = {scope.strip() for scope in (token.scopes or "").split() if scope.strip()}
    corporation = db.get(EveCorporation, character.corporation_id) if character.corporation_id else None
    return {
        "token_id": token.id,
        "character_id": character.character_id,
        "character_name": character.name,
        "user_id": token.user_id,
        "user_display_name": owner.display_name,
        "corporation_id": corporation.corporation_id if corporation else None,
        "corporation_name": corporation.name if corporation else None,
        "has_character_contract_scope": CHARACTER_CONTRACT_SCOPE in scopes,
        "has_corporation_contract_scope": CORPORATION_CONTRACT_SCOPE in scopes,
    }


@router.get("/tokens")
def contract_tokens(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_contracts(current_user, db)
    query = (
        select(EsiToken, EveCharacter, User)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .join(User, User.id == EsiToken.user_id)
        .where(EsiToken.revoked_at.is_(None))
        .order_by(EveCharacter.name)
    )
    if role_rank(current_user, db) < ROLE_RANK["director"]:
        query = query.where(EsiToken.user_id == current_user.id)
    return [contract_token_payload(token, character, owner, db) for token, character, owner in db.execute(query).all()]


@router.get("")
def list_contracts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_contracts(current_user, db)
    query = select(EveContract).options(selectinload(EveContract.character), selectinload(EveContract.corporation)).order_by(EveContract.date_issued.desc().nullslast(), EveContract.contract_id.desc())
    rank = role_rank(current_user, db)
    if rank < ROLE_RANK["officer"]:
        query = query.where(EveContract.owner_user_id == current_user.id, EveContract.scope_type == "character")
    elif rank < ROLE_RANK["director"]:
        query = query.where((EveContract.scope_type == "corporation") | ((EveContract.scope_type == "character") & (EveContract.owner_user_id == current_user.id)))
    return [serialize_contract(contract) for contract in db.scalars(query).all()]


@router.post("/sync/character/{token_id}")
async def sync_character_contracts(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_contracts(current_user, db)
    token = db.get(EsiToken, token_id)
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Linked character token was not found")
    if token.user_id != current_user.id and role_rank(current_user, db) < ROLE_RANK["director"]:
        raise HTTPException(status_code=403, detail="You can only sync your own character contracts")
    character = db.get(EveCharacter, token.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    require_scope(token, CHARACTER_CONTRACT_SCOPE, f"Syncing contracts for {character.name}")
    owner = db.get(User, token.user_id)
    job = EsiSyncJob(token_id=token.id, sync_type="character_contracts", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()
    try:
        access_token = await refresh_access_token(token)
        client = EsiClient(access_token=access_token)
        rows = await fetch_contract_pages(client, f"/characters/{character.character_id}/contracts/")
        synced = upsert_contract_rows(db, rows, scope_type="character", owner_user=owner, character=character)
        job.status = SyncStatus.SUCCESS
        job.message = f"Synced {synced} character contracts for {character.name}."
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "synced", "character_name": character.name, "contracts": synced, "active_contracts": sum(1 for row in rows if row.get("status") in ACTIVE_CONTRACT_STATUSES), "job_id": job.id}
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise


@router.post("/sync/corporation/{token_id}")
async def sync_corporation_contracts(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_contracts(current_user, db)
    if role_rank(current_user, db) < ROLE_RANK["officer"]:
        raise HTTPException(status_code=403, detail="officer role is required")
    token = db.get(EsiToken, token_id)
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Linked character token was not found")
    character = db.get(EveCharacter, token.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    corporation = db.get(EveCorporation, character.corporation_id) if character.corporation_id else None
    if corporation is None:
        raise HTTPException(status_code=400, detail="Linked character does not have a known corporation")
    require_scope(token, CORPORATION_CONTRACT_SCOPE, f"Syncing corporation contracts for {corporation.name}")
    job = EsiSyncJob(token_id=token.id, sync_type="corporation_contracts", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()
    try:
        access_token = await refresh_access_token(token)
        client = EsiClient(access_token=access_token)
        rows = await fetch_contract_pages(client, f"/corporations/{corporation.corporation_id}/contracts/")
        synced = upsert_contract_rows(db, rows, scope_type="corporation", corporation=corporation)
        job.status = SyncStatus.SUCCESS
        job.message = f"Synced {synced} corporation contracts for {corporation.name}."
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "synced", "corporation_name": corporation.name, "contracts": synced, "active_contracts": sum(1 for row in rows if row.get("status") in ACTIVE_CONTRACT_STATUSES), "job_id": job.id}
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise
