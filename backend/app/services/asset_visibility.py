from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, EveGroup, EveType, OwnershipEntity, User
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


def visible_asset_rows(current_user: User, db: Session) -> list[Asset]:
    assets = db.scalars(
        select(Asset)
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
    ).all()
    return [asset for asset in assets if can_view_owner_records(asset.ownership_entity, current_user, db)]
