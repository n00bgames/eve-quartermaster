from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import EveCharacter, EveCorporation, User
from app.services.permissions import ROLE_RANK, role_rank


def visible_analytics_character_ids(current_user: User, db: Session) -> set[int] | None:
    if role_rank(current_user, db) >= ROLE_RANK["director"]:
        return None
    characters = db.scalars(select(EveCharacter).options(selectinload(EveCharacter.owner_user))).all()
    viewer_rank = role_rank(current_user, db)
    return {
        character.id
        for character in characters
        if character.owner_user_id == current_user.id
        or (
            viewer_rank >= ROLE_RANK["officer"]
            and character.owner_user is not None
            and role_rank(character.owner_user, db) < ROLE_RANK["officer"]
        )
    }


def analytics_scope_options(current_user: User, db: Session) -> list[dict[str, object]]:
    visible_ids = visible_analytics_character_ids(current_user, db)
    query = select(EveCorporation).join(EveCharacter, EveCharacter.corporation_id == EveCorporation.id).distinct()
    if visible_ids is not None:
        if not visible_ids:
            return []
        query = query.where(EveCharacter.id.in_(visible_ids))
    corporations = db.scalars(query.order_by(EveCorporation.name)).all()
    return [{"id": int(corporation.id), "name": corporation.name, "ticker": corporation.ticker} for corporation in corporations]


def resolve_analytics_character_scope(
    current_user: User,
    db: Session,
    *,
    scope: str,
    corporation_id: int | None,
) -> tuple[set[int] | None, list[dict[str, object]]]:
    options = analytics_scope_options(current_user, db)
    visible_ids = visible_analytics_character_ids(current_user, db)
    if scope == "all":
        return visible_ids, options
    if scope == "mine":
        owned_ids = set(db.scalars(select(EveCharacter.id).where(EveCharacter.owner_user_id == current_user.id)).all())
        return owned_ids if visible_ids is None else owned_ids & visible_ids, options
    if scope != "corporation":
        raise HTTPException(status_code=400, detail="Analytics scope must be all, mine, or corporation")
    if corporation_id is None:
        raise HTTPException(status_code=400, detail="corporation_id is required for corporation analytics scope")
    accessible_corporation_ids = {int(option["id"]) for option in options}
    if corporation_id not in accessible_corporation_ids:
        raise HTTPException(status_code=403, detail="That corporation is not available in your analytics scope")
    selected_ids = set(
        db.scalars(select(EveCharacter.id).where(EveCharacter.corporation_id == corporation_id)).all()
    )
    return selected_ids if visible_ids is None else selected_ids & visible_ids, options
