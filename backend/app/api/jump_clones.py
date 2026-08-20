from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import can_view_all_characters, get_current_user
from app.api.characters import can_sync_character_data, can_view_character_detail, visible_characters
from app.api.esi import apply_type_metadata, apply_type_names, get_linked_token, refresh_access_token, require_scope, token_scopes
from app.db.session import get_db
from app.models import CharacterJumpClone, EsiSyncJob, EsiToken, EveCharacter, EveStation, EveSystem, EveType, EveTypeDogmaAttribute, EveTypeDogmaEffect, ImplantSet, ImplantSetImplant, JumpCloneImplant, Location, User
from app.models.enums import SyncStatus
from app.services.esi_client import EsiClient
from app.services.permissions import can_view_section

router = APIRouter(prefix="/jump-clones", tags=["jump-clones"])

CLONE_SCOPE = "esi-clones.read_clones.v1"
IMPLANT_SCOPE = "esi-clones.read_implants.v1"


def iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def require_jump_clone_view(user: User, db: Session) -> None:
    if not (can_view_section(user, "jump_clones", db) or can_view_section(user, "characters", db)):
        raise HTTPException(status_code=403, detail="Jump clone permission is required")


def clean_type_ids(values: Any) -> list[int]:
    if not isinstance(values, list):
        raise HTTPException(status_code=400, detail="implant_type_ids must be a list")
    cleaned: list[int] = []
    for value in values:
        try:
            type_id = int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Implant type IDs must be integers") from exc
        if type_id > 0 and type_id not in cleaned:
            cleaned.append(type_id)
    return cleaned[:20]


def implant_slot(attrs: dict[str, Any] | None) -> int | None:
    if not attrs:
        return None
    for key in ("implantness", "boosterness"):
        value = attrs.get(key)
        if value is not None:
            return int(value)
    return None


def type_attrs(db: Session, type_ids: set[int]) -> dict[int, dict[str, float]]:
    if not type_ids:
        return {}
    from app.services.fitting_simulator import dogma_for_types

    return dogma_for_types(db, type_ids)


async def resolve_implant_types(db: Session, type_ids: set[int], access_token: str | None = None) -> None:
    if not type_ids:
        return
    client = EsiClient(access_token=access_token)
    await apply_type_names(client, db, type_ids)
    await apply_type_metadata(client, db, type_ids, max_fetch=100)


def serialize_implant_dogma(item_type: EveType | None) -> dict[str, Any]:
    if item_type is None:
        return {"attributes": [], "effects": []}
    attributes = sorted(
        [
            {
                "attribute_id": row.attribute_id,
                "name": row.attribute.name if row.attribute else f"Attribute {row.attribute_id}",
                "display_name": row.attribute.display_name if row.attribute else None,
                "description": row.attribute.description if row.attribute else None,
                "unit_id": row.attribute.unit_id if row.attribute else None,
                "value": row.value,
            }
            for row in item_type.dogma_attributes
        ],
        key=lambda row: ((row["display_name"] or row["name"]).lower(), row["attribute_id"]),
    )
    effects = sorted(
        [
            {
                "effect_id": row.effect_id,
                "name": row.effect.name if row.effect else f"Effect {row.effect_id}",
                "display_name": row.effect.display_name if row.effect else None,
                "description": row.effect.description if row.effect else None,
                "category_id": row.effect.category_id if row.effect else None,
                "is_default": row.is_default,
            }
            for row in item_type.dogma_effects
        ],
        key=lambda row: ((row["display_name"] or row["name"]).lower(), row["effect_id"]),
    )
    return {"attributes": attributes, "effects": effects}


def serialize_implant(type_id: int, item_type: EveType | None, slot: int | None = None) -> dict[str, Any]:
    return {
        "type_id": type_id,
        "name": item_type.name if item_type else f"Type {type_id}",
        "slot": slot,
        "group_name": item_type.group.name if item_type and item_type.group else None,
        "market_group_id": item_type.market_group_id if item_type else None,
        "dogma": serialize_implant_dogma(item_type),
    }


def clone_location_context(db: Session, clone: CharacterJumpClone) -> dict[str, Any]:
    if clone.location_id is None:
        return {"location_name": None, "system_id": None, "system_name": None}
    try:
        location_id = int(clone.location_id)
    except (TypeError, ValueError):
        return {"location_name": None, "system_id": None, "system_name": None}

    station: EveStation | None = None
    system: EveSystem | None = None
    if 0 < location_id <= 2_147_483_647:
        location_type = (clone.location_type or "").lower()
        if location_type == "station":
            station = db.get(EveStation, location_id)
            if station and station.system_id:
                system = db.get(EveSystem, station.system_id)
        elif location_type in {"solar_system", "system"}:
            system = db.get(EveSystem, location_id)
        else:
            station = db.get(EveStation, location_id)
            if station and station.system_id:
                system = db.get(EveSystem, station.system_id)
            else:
                system = db.get(EveSystem, location_id)

    stored_location = db.scalar(select(Location).where(Location.eve_location_id == location_id))
    stored_name = stored_location.name if stored_location and not stored_location.name.startswith("Location ") else None
    return {
        "location_name": (station.name if station and station.name else None) or stored_name or (system.name if system else None),
        "system_id": station.system_id if station else (system.system_id if system else stored_location.system_id if stored_location else None),
        "system_name": system.name if system else None,
    }


def serialize_clone(db: Session, clone: CharacterJumpClone) -> dict[str, Any]:
    implants = sorted(clone.implants, key=lambda row: (row.slot is None, row.slot or 99, row.implant_type.name if row.implant_type else str(row.type_id)))
    location_context = clone_location_context(db, clone)
    return {
        "id": clone.id,
        "character_id": clone.character_id,
        "clone_kind": clone.clone_kind,
        "jump_clone_id": clone.jump_clone_id,
        "name": clone.name or ("Active clone" if clone.clone_kind == "active_clone" else f"Jump clone {clone.jump_clone_id}"),
        "location_id": clone.location_id,
        "location_type": clone.location_type,
        **location_context,
        "last_synced_at": iso(clone.last_synced_at),
        "implants": [serialize_implant(row.type_id, row.implant_type, row.slot) for row in implants],
    }


def serialize_implant_set(row: ImplantSet) -> dict[str, Any]:
    implants = sorted(row.implants, key=lambda item: (item.slot is None, item.slot or 99, item.implant_type.name if item.implant_type else str(item.type_id)))
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "character_id": row.character_id,
        "character_name": row.character.name if row.character else None,
        "owner_user_id": row.owner_user_id,
        "owner_display_name": row.owner_user.display_name if row.owner_user else None,
        "is_shared": row.is_shared,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
        "implants": [serialize_implant(item.type_id, item.implant_type, item.slot) for item in implants],
        "can_manage": True,
    }


def jump_clone_tokens_payload(db: Session, viewer: User, character_ids: set[int]) -> list[dict[str, Any]]:
    if not character_ids:
        return []
    rows = db.execute(
        select(EsiToken, EveCharacter)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.revoked_at.is_(None), EsiToken.character_id.in_(character_ids))
        .order_by(EveCharacter.name)
    ).all()
    payload: list[dict[str, Any]] = []
    for token, character in rows:
        scopes = token_scopes(token)
        payload.append(
            {
                "token_id": token.id,
                "character_id": character.id,
                "character_name": character.name,
                "can_sync": can_sync_character_data(viewer, character, token, db),
                "has_clone_scope": CLONE_SCOPE in scopes,
                "has_implant_scope": IMPLANT_SCOPE in scopes,
                "missing_scopes": [scope for scope in (CLONE_SCOPE, IMPLANT_SCOPE) if scope not in scopes],
            }
        )
    return payload


@router.get("")
def list_jump_clones(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_jump_clone_view(current_user, db)
    characters = visible_characters(current_user, db)
    character_ids = {character.id for character in characters}
    clone_rows = db.scalars(
        select(CharacterJumpClone)
        .where(CharacterJumpClone.character_id.in_(character_ids) if character_ids else False)
        .options(
            selectinload(CharacterJumpClone.implants).selectinload(JumpCloneImplant.implant_type),
            selectinload(CharacterJumpClone.character),
        )
        .order_by(CharacterJumpClone.character_id, CharacterJumpClone.clone_kind, CharacterJumpClone.jump_clone_id)
    ).all()
    set_query = (
        select(ImplantSet)
        .where(or_(ImplantSet.owner_user_id == current_user.id, ImplantSet.is_shared.is_(True)))
        .options(
            selectinload(ImplantSet.owner_user),
            selectinload(ImplantSet.character),
            selectinload(ImplantSet.implants).selectinload(ImplantSetImplant.implant_type),
        )
        .order_by(ImplantSet.name)
    )
    if can_view_all_characters(current_user, db):
        set_query = (
            select(ImplantSet)
            .options(
                selectinload(ImplantSet.owner_user),
                selectinload(ImplantSet.character),
                selectinload(ImplantSet.implants).selectinload(ImplantSetImplant.implant_type),
            )
            .order_by(ImplantSet.name)
        )
    custom_sets = db.scalars(set_query).all()
    sets = [serialize_implant_set(row) for row in custom_sets]
    for row, payload in zip(custom_sets, sets):
        payload["can_manage"] = row.owner_user_id == current_user.id or can_view_all_characters(current_user, db)
    return {
        "characters": [
            {
                "id": character.id,
                "character_id": character.character_id,
                "name": character.name,
                "portrait_url": character.portrait_url,
                "owner_display_name": character.owner_user.display_name if character.owner_user else None,
                "sync_opt_out": character.sync_opt_out,
            }
            for character in characters
        ],
        "clones": [serialize_clone(db, row) for row in clone_rows],
        "custom_sets": sets,
        "sync_tokens": jump_clone_tokens_payload(db, current_user, character_ids),
    }


async def sync_jump_clones_for_token(
    token_id: int,
    current_user: User,
    db: Session,
    *,
    allow_opt_out_override: bool = True,
) -> dict[str, Any]:
    require_jump_clone_view(current_user, db)
    token, character = get_linked_token(db, token_id)
    if not can_sync_character_data(current_user, character, token, db):
        raise HTTPException(status_code=403, detail="You cannot sync jump clones for this character")
    if character.sync_opt_out and not allow_opt_out_override:
        return {"status": "skipped", "character_name": character.name, "reason": "Character opted out"}
    require_scope(token, CLONE_SCOPE, f"Reading jump clones for {character.name}")
    require_scope(token, IMPLANT_SCOPE, f"Reading implants for {character.name}")

    job = EsiSyncJob(token_id=token.id, sync_type="character_jump_clones", status=SyncStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db.add(job)
    db.flush()
    access_token = await refresh_access_token(token)
    client = EsiClient(access_token=access_token)
    try:
        clone_payload = await client.get(f"/characters/{character.character_id}/clones/")
        active_implants = await client.get(f"/characters/{character.character_id}/implants/")
        all_type_ids = {int(type_id) for type_id in active_implants or []}
        for clone in clone_payload.get("jump_clones", []) or []:
            all_type_ids.update(int(type_id) for type_id in clone.get("implants", []) or [])
        await resolve_implant_types(db, all_type_ids, access_token)
        attrs = type_attrs(db, all_type_ids)

        db.execute(delete(CharacterJumpClone).where(CharacterJumpClone.character_id == character.id))
        now = datetime.now(timezone.utc)
        active = CharacterJumpClone(
            character_id=character.id,
            clone_kind="active_clone",
            jump_clone_id=0,
            name="Active clone",
            last_synced_at=now,
        )
        db.add(active)
        db.flush()
        for type_id in sorted(int(type_id) for type_id in active_implants or []):
            db.add(JumpCloneImplant(clone_id=active.id, type_id=type_id, slot=implant_slot(attrs.get(type_id))))

        for index, clone in enumerate(clone_payload.get("jump_clones", []) or [], start=1):
            jump_clone_id = int(clone.get("jump_clone_id") or index)
            row = CharacterJumpClone(
                character_id=character.id,
                clone_kind="jump_clone",
                jump_clone_id=jump_clone_id,
                name=f"Jump clone {jump_clone_id}",
                location_id=clone.get("location_id"),
                location_type=clone.get("location_type"),
                last_synced_at=now,
            )
            db.add(row)
            db.flush()
            for type_id in sorted(int(type_id) for type_id in clone.get("implants", []) or []):
                db.add(JumpCloneImplant(clone_id=row.id, type_id=type_id, slot=implant_slot(attrs.get(type_id))))

        character.last_synced_at = now
        job.status = SyncStatus.SUCCESS
        job.finished_at = now
        job.message = f"Synced jump clones and implants for {character.name}."
        db.commit()
        return {"status": "synced", "character_id": character.id, "character_name": character.name, "implant_count": len(all_type_ids), "job_id": job.id}
    except Exception as exc:
        db.rollback()
        job = EsiSyncJob(token_id=token.id, sync_type="character_jump_clones", status=SyncStatus.FAILED, started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc), message=str(exc))
        db.add(job)
        db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Jump clone sync failed for {character.name}. Previously synced clone data was preserved.",
        ) from exc


@router.post("/sync/{token_id:int}")
async def sync_jump_clones(token_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    return await sync_jump_clones_for_token(token_id, current_user, db)


def require_set_access(row: ImplantSet, current_user: User, db: Session) -> None:
    if row.owner_user_id != current_user.id and not can_view_all_characters(current_user, db):
        raise HTTPException(status_code=403, detail="You can only edit your own implant sets")


async def update_set_implants(db: Session, row: ImplantSet, type_ids: list[int]) -> None:
    await resolve_implant_types(db, set(type_ids))
    attrs = type_attrs(db, set(type_ids))
    db.execute(delete(ImplantSetImplant).where(ImplantSetImplant.set_id == row.id))
    for type_id in type_ids:
        db.add(ImplantSetImplant(set_id=row.id, type_id=type_id, slot=implant_slot(attrs.get(type_id))))


@router.post("/sets")
async def create_implant_set(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_jump_clone_view(current_user, db)
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Set name is required")
    character_id = payload.get("character_id")
    if character_id in {"", 0, "0"}:
        character_id = None
    if character_id is not None:
        character = db.get(EveCharacter, int(character_id))
        if character is None or not can_view_character_detail(current_user, character, db):
            raise HTTPException(status_code=404, detail="Character was not found")
        character_id = character.id
    row = ImplantSet(owner_user_id=current_user.id, character_id=character_id, name=name[:255], description=str(payload.get("description") or "").strip() or None, is_shared=bool(payload.get("is_shared")))
    db.add(row)
    db.flush()
    await update_set_implants(db, row, clean_type_ids(payload.get("implant_type_ids", [])))
    db.commit()
    row = db.scalar(
        select(ImplantSet)
        .where(ImplantSet.id == row.id)
        .options(selectinload(ImplantSet.owner_user), selectinload(ImplantSet.character), selectinload(ImplantSet.implants).selectinload(ImplantSetImplant.implant_type))
    )
    return serialize_implant_set(row)


@router.patch("/sets/{set_id:int}")
async def update_implant_set(set_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_jump_clone_view(current_user, db)
    row = db.get(ImplantSet, set_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Implant set was not found")
    require_set_access(row, current_user, db)
    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Set name is required")
        row.name = name[:255]
    if "description" in payload:
        row.description = str(payload.get("description") or "").strip() or None
    if "is_shared" in payload:
        row.is_shared = bool(payload["is_shared"])
    if "character_id" in payload:
        character_id = payload.get("character_id")
        row.character_id = None if character_id in {None, "", 0, "0"} else int(character_id)
    if "implant_type_ids" in payload:
        await update_set_implants(db, row, clean_type_ids(payload.get("implant_type_ids", [])))
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    row = db.scalar(
        select(ImplantSet)
        .where(ImplantSet.id == row.id)
        .options(selectinload(ImplantSet.owner_user), selectinload(ImplantSet.character), selectinload(ImplantSet.implants).selectinload(ImplantSetImplant.implant_type))
    )
    return serialize_implant_set(row)


@router.delete("/sets/{set_id:int}")
def delete_implant_set(set_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_jump_clone_view(current_user, db)
    row = db.get(ImplantSet, set_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Implant set was not found")
    require_set_access(row, current_user, db)
    db.delete(row)
    db.commit()
    return {"status": "deleted", "id": set_id}

