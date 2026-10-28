from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, EveCharacter, EveGroup, EveType, OwnershipEntity, User
from app.services.permissions import ROLE_RANK, role_rank


def can_view_owner_records(owner: OwnershipEntity | None, current_user: User, db: Session) -> bool:
    if role_rank(current_user, db) >= ROLE_RANK["officer"]:
        return True
    if owner is None or owner.character is None:
        return False
    character = owner.character
    if character.owner_user_id == current_user.id:
        return True
    return bool(character.public_assets_visible and not character.sync_opt_out)


def visible_owner_clause(current_user: User, db: Session):
    # Resolve combined account roles once per query, never once per inventory row.
    if role_rank(current_user, db) >= ROLE_RANK["officer"]:
        return True
    return OwnershipEntity.character.has(or_(
        EveCharacter.owner_user_id == current_user.id,
        (EveCharacter.public_assets_visible.is_(True) & EveCharacter.sync_opt_out.is_(False)),
    ))


def visible_asset_query(current_user: User, db: Session):
    return (
        select(Asset)
        .where(Asset.ownership_entity.has(visible_owner_clause(current_user, db)))
        .options(
            selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.character),
            selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.corporation),
            selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.alliance),
            selectinload(Asset.item_type).selectinload(EveType.group).selectinload(EveGroup.category),
            selectinload(Asset.location),
            selectinload(Asset.parent_asset).selectinload(Asset.location),
            selectinload(Asset.parent_asset).selectinload(Asset.parent_asset),
            selectinload(Asset.parent_asset).selectinload(Asset.item_type).selectinload(EveType.group).selectinload(EveGroup.category),
        )
        .order_by(Asset.updated_at.desc(), Asset.id.desc())
    )


def visible_asset_rows(current_user: User, db: Session, limit: int | None = None) -> list[Asset]:
    query = visible_asset_query(current_user, db)
    if limit is not None:
        query = query.limit(limit)
    return list(db.scalars(query).all())
