from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import ROLE_RANK, can_view_all_characters, get_current_user, require_role, serialize_user
from app.db.session import get_db
from app.models import EveCharacter, User

router = APIRouter(prefix="/characters", tags=["characters"])


def can_manage_characters(user: User) -> bool:
    return ROLE_RANK.get(user.role, -1) >= ROLE_RANK["director"]


def can_view_character_detail(viewer: User, character: EveCharacter) -> bool:
    if can_view_all_characters(viewer):
        return True
    if character.owner_user_id == viewer.id:
        return True
    if viewer.role == "officer" and character.owner_user and ROLE_RANK.get(character.owner_user.role, -1) < ROLE_RANK["officer"]:
        return True
    if viewer.role == "member" and character.public_assets_visible:
        return True
    return False


def serialize_character(character: EveCharacter, viewer: User) -> dict[str, Any]:
    detail = can_view_character_detail(viewer, character)
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
        "corporation_name": character.corporation.name if character.corporation else None,
        "alliance_name": character.alliance.name if character.alliance else None,
        "public_assets_visible": character.public_assets_visible,
        "last_synced_at": character.last_synced_at.isoformat() if character.last_synced_at else None,
    })
    data["can_manage"] = can_manage_characters(viewer) or character.owner_user_id == viewer.id
    data["can_assign"] = can_manage_characters(viewer)
    return data


@router.get("")
def list_characters(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    query = select(EveCharacter).options(
        selectinload(EveCharacter.owner_user),
        selectinload(EveCharacter.corporation),
        selectinload(EveCharacter.alliance),
    ).order_by(EveCharacter.name)
    if can_view_all_characters(current_user):
        characters = db.scalars(query).all()
    elif current_user.role == "officer":
        characters = db.scalars(query.join(User, EveCharacter.owner_user_id == User.id, isouter=True).where(or_(EveCharacter.owner_user_id == current_user.id, User.role.in_(["member", "view_only", "rookie"])))).all()
    elif current_user.role == "member":
        characters = db.scalars(query.where(or_(EveCharacter.owner_user_id == current_user.id, EveCharacter.public_assets_visible.is_(True)))).all()
    else:
        characters = db.scalars(query).all()
    return [serialize_character(character, current_user) for character in characters]


@router.get("/accounts")
def list_character_accounts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_role(current_user, "director")
    users = db.scalars(select(User).order_by(User.display_name)).all()
    return [serialize_user(user) for user in users]


@router.patch("/{character_id}")
def update_character(character_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    character = db.get(EveCharacter, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Character was not found")
    if "owner_user_id" in payload:
        require_role(current_user, "director")
        owner_user_id = payload.get("owner_user_id")
        if owner_user_id in (None, ""):
            character.owner_user_id = None
        else:
            owner = db.get(User, int(owner_user_id))
            if owner is None:
                raise HTTPException(status_code=404, detail="Account was not found")
            character.owner_user_id = owner.id
    if "public_assets_visible" in payload:
        if not can_manage_characters(current_user) and character.owner_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only change visibility for your own characters")
        character.public_assets_visible = bool(payload["public_assets_visible"])
    db.commit()
    db.refresh(character)
    character = db.scalar(select(EveCharacter).where(EveCharacter.id == character.id).options(selectinload(EveCharacter.owner_user), selectinload(EveCharacter.corporation), selectinload(EveCharacter.alliance)))
    return serialize_character(character, current_user)
