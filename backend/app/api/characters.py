from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user, require_role, serialize_user
from app.db.session import get_db
from app.models import EveCharacter, User
from app.services.permissions import ROLE_RANK, can_view_section, role_rank

router = APIRouter(prefix="/characters", tags=["characters"])


def can_manage_characters(user: User, db: Session) -> bool:
    return role_rank(user, db) >= ROLE_RANK["director"]


def can_view_character_detail(viewer: User, character: EveCharacter, db: Session) -> bool:
    if role_rank(viewer, db) >= ROLE_RANK["director"]:
        return True
    if character.owner_user_id == viewer.id:
        return True
    if role_rank(viewer, db) >= ROLE_RANK["officer"] and character.owner_user and role_rank(character.owner_user, db) < ROLE_RANK["officer"]:
        return True
    if role_rank(viewer, db) >= ROLE_RANK["member"] and character.public_assets_visible:
        return True
    return False


def serialize_character(character: EveCharacter, viewer: User, db: Session) -> dict[str, Any]:
    detail = can_view_character_detail(viewer, character, db)
    data: dict[str, Any] = {
        "id": character.id,
        "name": character.name,
        "can_view_detail": detail,
    }
    if not detail or viewer.role == "view_only":
        return data
    data.update({
        "character_id": character.character_id,
        "owner_user_id": character.owner_user_id,
        "owner_display_name": character.owner_user.display_name if character.owner_user else None,
        "owner_role": character.owner_user.role if character.owner_user else None,
        "corporation_id": character.corporation.corporation_id if character.corporation else None,
        "corporation_name": character.corporation.name if character.corporation else None,
        "alliance_id": character.alliance.alliance_id if character.alliance else None,
        "alliance_name": character.alliance.name if character.alliance else None,
        "public_assets_visible": character.public_assets_visible,
        "sync_opt_out": character.sync_opt_out,
        "last_synced_at": character.last_synced_at.isoformat() if character.last_synced_at else None,
    })
    data["can_manage"] = can_manage_characters(viewer, db) or character.owner_user_id == viewer.id
    data["can_assign"] = can_manage_characters(viewer, db)
    return data


@router.get("")
def list_characters(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    query = select(EveCharacter).options(
        selectinload(EveCharacter.owner_user),
        selectinload(EveCharacter.corporation),
        selectinload(EveCharacter.alliance),
    ).order_by(EveCharacter.name)
    if role_rank(current_user, db) >= ROLE_RANK["director"]:
        characters = db.scalars(query).all()
    elif role_rank(current_user, db) >= ROLE_RANK["officer"]:
        characters = db.scalars(query.join(User, EveCharacter.owner_user_id == User.id, isouter=True).where(or_(EveCharacter.owner_user_id == current_user.id, User.role.in_(["member", "view_only", "rookie"])))).all()
    elif role_rank(current_user, db) >= ROLE_RANK["member"]:
        characters = db.scalars(query.where(or_(EveCharacter.owner_user_id == current_user.id, EveCharacter.public_assets_visible.is_(True)))).all()
    else:
        characters = db.scalars(query).all()
    return [serialize_character(character, current_user, db) for character in characters]




@router.get("/roster")
def list_roster(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    if not can_view_section(current_user, "roster", db):
        raise HTTPException(status_code=403, detail="Roster permission is required")
    characters = db.scalars(
        select(EveCharacter)
        .where(EveCharacter.owner_user_id.is_not(None))
        .options(
            selectinload(EveCharacter.corporation),
            selectinload(EveCharacter.alliance),
        )
        .order_by(EveCharacter.name)
    ).all()
    corporations: dict[str, dict[str, Any]] = {}
    for character in characters:
        corp = character.corporation
        alliance = character.alliance
        key = str(corp.id) if corp else "unknown"
        if key not in corporations:
            corporations[key] = {
                "corporation_id": corp.corporation_id if corp else None,
                "corporation_name": corp.name if corp else "Unknown corporation",
                "ticker": corp.ticker if corp else None,
                "alliance_id": alliance.alliance_id if alliance else None,
                "alliance_name": alliance.name if alliance else None,
                "member_count": corp.member_count if corp else None,
                "characters": [],
            }
        corporations[key]["characters"].append(
            {
                "character_id": character.character_id,
                "name": character.name,
                "portrait_url": character.portrait_url,
            }
        )
    return sorted(
        corporations.values(),
        key=lambda corp: (str(corp.get("alliance_name") or ""), str(corp.get("corporation_name") or "")),
    )

@router.get("/accounts")
def list_character_accounts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_role(current_user, "director", db)
    users = db.scalars(select(User).order_by(User.display_name)).all()
    return [serialize_user(user) for user in users]


@router.patch("/{character_id}")
def update_character(character_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    character = db.get(EveCharacter, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Character was not found")
    if "owner_user_id" in payload:
        require_role(current_user, "director", db)
        owner_user_id = payload.get("owner_user_id")
        if owner_user_id in (None, ""):
            character.owner_user_id = None
        else:
            owner = db.get(User, int(owner_user_id))
            if owner is None:
                raise HTTPException(status_code=404, detail="Account was not found")
            character.owner_user_id = owner.id
    if "public_assets_visible" in payload:
        if not can_manage_characters(current_user, db) and character.owner_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only change visibility for your own characters")
        character.public_assets_visible = bool(payload["public_assets_visible"])
    if "sync_opt_out" in payload:
        if character.owner_user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="You can only change sync privacy for your own characters")
        character.sync_opt_out = bool(payload["sync_opt_out"])
    db.commit()
    db.refresh(character)
    character = db.scalar(select(EveCharacter).where(EveCharacter.id == character.id).options(selectinload(EveCharacter.owner_user), selectinload(EveCharacter.corporation), selectinload(EveCharacter.alliance)))
    return serialize_character(character, current_user, db)





