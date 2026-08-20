from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.esi import (
    CHARACTER_STANDINGS_SCOPES,
    can_force_sync_character_token,
    get_linked_token,
    refresh_access_token,
    require_scope,
    resolve_contact_names,
)
from app.db.session import get_db
from app.models import EsiSyncJob, User
from app.models.enums import SyncStatus
from app.services.audit import notify_if_other_user_synced_character
from app.services.analytics import create_snapshot
from app.services.esi_client import EsiClient
from app.services.standings import upsert_character_standings

router = APIRouter(prefix="/esi", tags=["esi"])


async def sync_character_standings_for_token(
    token_id: int,
    current_user: User,
    db: Session,
    *,
    allow_opt_out_override: bool = True,
) -> dict[str, Any]:
    token, character = get_linked_token(db, token_id)
    if not can_force_sync_character_token(token, character, current_user, db):
        raise HTTPException(status_code=403, detail="You can only sync characters you own or are permitted to administer")
    if character.sync_opt_out and (
        not allow_opt_out_override
        or (token.user_id != current_user.id and current_user.role not in {"host", "admin"})
    ):
        raise HTTPException(status_code=403, detail=f"{character.name} has opted out of Quartermaster sync")
    require_scope(token, CHARACTER_STANDINGS_SCOPES[0], f"Reading NPC standings for {character.name}")

    job = EsiSyncJob(
        token_id=token.id,
        sync_type="character_standings",
        status=SyncStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()

    try:
        access_token = await refresh_access_token(token)
        client = EsiClient(access_token=access_token)
        rows = await client.get(f"/characters/{character.character_id}/standings/") or []
        source_ids = {int(row["from_id"]) for row in rows if row.get("from_id") is not None}
        names = await resolve_contact_names(client, source_ids)
        counts = upsert_character_standings(db, character, rows, names)
        snapshot = create_snapshot(
            db,
            scope_type="character",
            scope_id=character.id,
            source="character_standings",
            message=f"Automatic standings snapshot for {character.name}",
        )
        now = datetime.now(timezone.utc)
        job.status = SyncStatus.SUCCESS
        job.finished_at = now
        job.message = (
            f"Synced {counts['total']} NPC standings "
            f"({counts['created']} added, {counts['updated']} refreshed, {counts['removed']} removed)."
        )
        notify_if_other_user_synced_character(
            db,
            sync_label="standings",
            actor_user=current_user,
            character=character,
            detail=f"{counts['total']} agent, corporation, and faction standings were refreshed.",
        )
        db.commit()
        return {
            "status": "synced",
            "character_name": character.name,
            "standing_count": counts["total"],
            "job_id": job.id,
            "snapshot_run_id": snapshot.id,
        }
    except Exception as exc:
        job.status = SyncStatus.FAILED
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise


@router.post("/sync/character-standings/{token_id:int}")
async def sync_character_standings(
    token_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await sync_character_standings_for_token(token_id, current_user, db)
