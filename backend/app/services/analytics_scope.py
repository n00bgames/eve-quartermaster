from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import EveAlliance, EveCharacter, EveCorporation, User
from app.services.permissions import ROLE_RANK, role_rank


def _owned_affiliations(current_user: User, db: Session) -> tuple[set[int], set[int]]:
    rows = db.execute(
        select(EveCharacter.corporation_id, EveCharacter.alliance_id).where(
            EveCharacter.owner_user_id == current_user.id
        )
    ).all()
    return (
        {int(corporation_id) for corporation_id, _ in rows if corporation_id is not None},
        {int(alliance_id) for _, alliance_id in rows if alliance_id is not None},
    )


def visible_analytics_character_ids(current_user: User, db: Session) -> set[int]:
    viewer_rank = role_rank(current_user, db)
    if viewer_rank >= ROLE_RANK["admin"]:
        return set(db.scalars(select(EveCharacter.id)).all())
    characters = db.scalars(select(EveCharacter).options(selectinload(EveCharacter.owner_user))).all()
    if viewer_rank >= ROLE_RANK["director"]:
        corporation_ids, alliance_ids = _owned_affiliations(current_user, db)
        return {
            character.id
            for character in characters
            if (
                character.owner_user_id == current_user.id
                or character.corporation_id in corporation_ids
                or (character.alliance_id is not None and character.alliance_id in alliance_ids)
            )
        }
    return {
        character.id
        for character in characters
        if (
            character.owner_user_id == current_user.id
            or (
                viewer_rank >= ROLE_RANK["officer"]
                and character.owner_user is not None
                and role_rank(character.owner_user, db) < ROLE_RANK["officer"]
            )
        )
    }


def analytics_scope_options(current_user: User, db: Session) -> dict[str, list[dict[str, object]]]:
    visible_ids = visible_analytics_character_ids(current_user, db)
    if not visible_ids:
        return {"corporations": [], "alliances": []}
    corporations = db.scalars(
        select(EveCorporation)
        .join(EveCharacter, EveCharacter.corporation_id == EveCorporation.id)
        .where(EveCharacter.id.in_(visible_ids))
        .distinct()
        .order_by(EveCorporation.name)
    ).all()
    alliances = db.scalars(
        select(EveAlliance)
        .join(EveCharacter, EveCharacter.alliance_id == EveAlliance.id)
        .where(EveCharacter.id.in_(visible_ids))
        .distinct()
        .order_by(EveAlliance.name)
    ).all()
    return {
        "corporations": [{"id": int(row.id), "name": row.name, "ticker": row.ticker} for row in corporations],
        "alliances": [{"id": int(row.id), "name": row.name, "ticker": row.ticker} for row in alliances],
    }


def resolve_analytics_character_scope(
    current_user: User,
    db: Session,
    *,
    scope: str,
    corporation_id: int | None,
    alliance_id: int | None = None,
) -> tuple[set[int], dict[str, list[dict[str, object]]]]:
    options = analytics_scope_options(current_user, db)
    visible_ids = visible_analytics_character_ids(current_user, db)
    if scope == "all":
        return visible_ids, options
    if scope == "mine":
        owned_ids = set(db.scalars(select(EveCharacter.id).where(
            EveCharacter.owner_user_id == current_user.id,
        )).all())
        return owned_ids & visible_ids, options
    if scope == "corporation":
        if corporation_id is None:
            raise HTTPException(status_code=400, detail="corporation_id is required for corporation analytics scope")
        accessible_ids = {int(option["id"]) for option in options["corporations"]}
        if corporation_id not in accessible_ids:
            raise HTTPException(status_code=403, detail="That corporation is not available in your analytics scope")
        selected_ids = set(db.scalars(select(EveCharacter.id).where(EveCharacter.corporation_id == corporation_id)).all())
        return selected_ids & visible_ids, options
    if scope == "alliance":
        if alliance_id is None:
            raise HTTPException(status_code=400, detail="alliance_id is required for alliance analytics scope")
        accessible_ids = {int(option["id"]) for option in options["alliances"]}
        if alliance_id not in accessible_ids:
            raise HTTPException(status_code=403, detail="That alliance is not available in your analytics scope")
        selected_ids = set(db.scalars(select(EveCharacter.id).where(EveCharacter.alliance_id == alliance_id)).all())
        return selected_ids & visible_ids, options
    raise HTTPException(status_code=400, detail="Analytics scope must be all, mine, corporation, or alliance")


def apply_anonymous_analytics_privacy(
    current_user: User,
    db: Session,
    *,
    scope: str,
    character_ids: set[int],
    minimum_cohort: int = 3,
) -> tuple[set[int], set[int]]:
    """Return aggregate-visible IDs and the subset that must never be identified.

    Ordinary sync opt-outs may contribute only to a sufficiently large global
    cohort. Keeping them out of affiliation drilldowns prevents simple
    subtraction of corporation/alliance totals from revealing an individual.
    """
    anonymous_ids = set(db.scalars(select(EveCharacter.id).where(
        EveCharacter.id.in_(character_ids),
        EveCharacter.sync_opt_out.is_(True),
    )).all()) if character_ids else set()
    may_aggregate = (
        scope == "all"
        and role_rank(current_user, db) >= ROLE_RANK["admin"]
        and len(anonymous_ids) >= minimum_cohort
    )
    if not may_aggregate:
        return character_ids - anonymous_ids, set()
    return character_ids, anonymous_ids
