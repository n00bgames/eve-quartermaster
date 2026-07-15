from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user, require_role, serialize_user
from app.db.session import get_db
from app.models import (
    Asset,
    Blueprint,
    CharacterFitting,
    CharacterSkill,
    CharacterSkillQueueEntry,
    EsiToken,
    EveCharacter,
    EveContract,
    EveCategory,
    IndustryActivity,
    EveGroup,
    EveType,
    OwnershipEntity,
    User,
)
from app.models.enums import ActivityKind, OwnerKind
from app.models.navigation import SystemIndustrialKillObservation, SystemPvpKillObservation
from app.services.contracts import serialize_contract
from app.services.permissions import ROLE_RANK, can_view_section, role_rank

router = APIRouter(prefix="/characters", tags=["characters"])

ASSET_SCOPE = "esi-assets.read_assets.v1"
SKILL_SCOPES = ["esi-skills.read_skills.v1", "esi-skills.read_skillqueue.v1"]
FITTING_SCOPE = "esi-fittings.read_fittings.v1"
CONTRACT_SCOPE = "esi-contracts.read_character_contracts.v1"
CLONE_SCOPES = ["esi-clones.read_clones.v1", "esi-clones.read_implants.v1"]


def iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def can_manage_characters(user: User, db: Session) -> bool:
    return role_rank(user, db) >= ROLE_RANK["director"]


def can_view_character_detail(viewer: User, character: EveCharacter, db: Session) -> bool:
    viewer_rank = role_rank(viewer, db)
    if viewer_rank >= ROLE_RANK["director"]:
        return True
    if character.owner_user_id == viewer.id:
        return True
    if viewer_rank >= ROLE_RANK["officer"] and character.owner_user and role_rank(character.owner_user, db) < ROLE_RANK["officer"]:
        return True
    return False


def can_sync_character_data(viewer: User, character: EveCharacter, token: EsiToken, db: Session) -> bool:
    if token.user_id == viewer.id:
        return True
    if role_rank(viewer, db) < ROLE_RANK["officer"]:
        return False
    if not can_view_character_detail(viewer, character, db):
        return False
    if character.sync_opt_out and viewer.role != "admin":
        return False
    return True


def visible_characters(current_user: User, db: Session) -> list[EveCharacter]:
    query = (
        select(EveCharacter)
        .where(
            or_(
                EveCharacter.owner_user_id.is_not(None),
                exists().where(EsiToken.character_id == EveCharacter.id, EsiToken.revoked_at.is_(None)),
                exists().where(
                    OwnershipEntity.owner_kind == OwnerKind.CHARACTER,
                    OwnershipEntity.character_id == EveCharacter.id,
                ),
            )
        )
        .options(
            selectinload(EveCharacter.owner_user),
            selectinload(EveCharacter.corporation),
            selectinload(EveCharacter.alliance),
        )
        .order_by(EveCharacter.name)
    )
    characters = db.scalars(query).all()
    return [character for character in characters if can_view_character_detail(current_user, character, db)]


def serialize_character(character: EveCharacter, viewer: User, db: Session) -> dict[str, Any]:
    detail = can_view_character_detail(viewer, character, db)
    data: dict[str, Any] = {
        "id": character.id,
        "name": character.name,
        "portrait_url": character.portrait_url,
        "security_status": character.security_status,
        "can_view_detail": detail,
    }
    if not detail:
        return data
    data.update(
        {
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
            "last_synced_at": iso(character.last_synced_at),
        }
    )
    data["can_manage"] = can_manage_characters(viewer, db) or character.owner_user_id == viewer.id
    data["can_assign"] = can_manage_characters(viewer, db)
    return data


def owner_for_character(db: Session, character: EveCharacter) -> OwnershipEntity | None:
    return db.scalar(
        select(OwnershipEntity).where(
            OwnershipEntity.owner_kind == OwnerKind.CHARACTER,
            OwnershipEntity.character_id == character.id,
        )
    )


def type_metadata(prefix: str, item_type: EveType | None) -> dict[str, Any]:
    group = item_type.group if item_type else None
    category = group.category if group else None
    return {
        f"{prefix}_group_id": group.group_id if group else None,
        f"{prefix}_group_name": group.name if group else None,
        f"{prefix}_category_id": category.category_id if category else None,
        f"{prefix}_category_name": category.name if category else None,
        f"{prefix}_market_group_id": item_type.market_group_id if item_type else None,
    }


def item_family(item_type: EveType | None, fallback_name: str | None = None) -> str:
    group_name = (item_type.group.name if item_type and item_type.group else "").lower()
    category_name = (item_type.group.category.name if item_type and item_type.group and item_type.group.category else "").lower()
    fallback = (fallback_name or "").lower()
    if category_name == "ship":
        return "ships"
    if category_name == "charge":
        return "ammunition"
    if category_name in {"drone", "fighter"} or "drone" in group_name or "fighter" in group_name:
        return "drones"
    if "rig" in group_name:
        return "rigs"
    if "reaction" in group_name or "reaction formula" in fallback or " reaction " in fallback:
        return "reactions"
    if "r.a.m" in group_name or "ram" in group_name or "r.a.m" in fallback or "ram-" in fallback:
        return "ram"
    if category_name == "blueprint":
        return "blueprints"
    return "other"


def inventory_subtype(item_type: EveType | None, fallback_name: str | None = None) -> str | None:
    if item_type and item_type.group:
        return item_type.group.name
    fallback = (fallback_name or "").lower()
    if "reaction formula" in fallback:
        return "Reaction Formula"
    if "r.a.m" in fallback or "ram-" in fallback:
        return "R.A.M."
    return None


def blueprint_type_ids_for_capital_construction(db: Session) -> set[int]:
    capital_ship_type_ids = set(db.scalars(
        select(EveType.type_id)
        .join(EveType.group)
        .join(EveGroup.category)
        .where(
            (EveCategory.name == "Ship") & EveGroup.name.in_([
                "Capital Industrial Ship", "Carrier", "Dreadnought", "Force Auxiliary",
                "Freighter", "Jump Freighter", "Supercarrier", "Titan",
            ])
        )
    ).all())
    capital_related_type_ids = set(capital_ship_type_ids)
    capital_related_type_ids.update(db.scalars(
        select(EveType.type_id)
        .join(EveType.group)
        .where(EveGroup.name.ilike("%Capital%"))
    ).all())
    if not capital_related_type_ids:
        return set()
    capital_activities = db.scalars(
        select(IndustryActivity)
        .where(IndustryActivity.product_type_id.in_(capital_related_type_ids))
        .options(selectinload(IndustryActivity.inputs))
    ).all()
    related_product_ids: set[int] = set(capital_related_type_ids - capital_ship_type_ids)
    for activity in capital_activities:
        related_product_ids.update(input_row.input_type_id for input_row in activity.inputs)
    related_product_ids.difference_update(capital_ship_type_ids)
    if not related_product_ids:
        return set()
    return set(db.scalars(select(IndustryActivity.blueprint_type_id).where(IndustryActivity.product_type_id.in_(related_product_ids))).all())


def blueprint_product_type_fallbacks(db: Session, blueprint_type_ids: set[int]) -> dict[int, EveType]:
    if not blueprint_type_ids:
        return {}
    rows = db.scalars(
        select(IndustryActivity)
        .where(IndustryActivity.blueprint_type_id.in_(blueprint_type_ids))
        .where(IndustryActivity.activity_kind.in_([ActivityKind.MANUFACTURING, ActivityKind.REACTION]))
        .where(IndustryActivity.product_type_id.is_not(None))
        .order_by(IndustryActivity.blueprint_type_id, IndustryActivity.activity_kind)
    ).all()
    product_type_ids = {row.product_type_id for row in rows if row.product_type_id}
    product_types = {
        item_type.type_id: item_type
        for item_type in db.scalars(
            select(EveType)
            .where(EveType.type_id.in_(product_type_ids))
            .options(selectinload(EveType.group).selectinload(EveGroup.category))
        ).all()
    } if product_type_ids else {}
    fallbacks: dict[int, EveType] = {}
    for row in rows:
        if row.blueprint_type_id in fallbacks or row.product_type_id not in product_types:
            continue
        fallbacks[row.blueprint_type_id] = product_types[row.product_type_id]
    return fallbacks
def serialize_asset(asset: Asset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "ownership_entity_id": asset.ownership_entity_id,
        "owner_name": asset.ownership_entity.display_name if asset.ownership_entity else "Unknown",
        "owner_kind": asset.ownership_entity.owner_kind.value if asset.ownership_entity else None,
        "type_id": asset.type_id,
        "type_name": asset.item_type.name if asset.item_type else f"Type {asset.type_id}",
        "quantity": asset.quantity,
        "location_name": asset.location.name if asset.location else None,
        "location_id": asset.location.eve_location_id if asset.location else None,
        "location_flag": asset.location_flag,
        "source": asset.source.value if hasattr(asset.source, "value") else str(asset.source),
        "last_synced_at": iso(asset.last_synced_at),
        "parent_asset_item_id": asset.parent_asset.eve_item_id if asset.parent_asset else None,
        "parent_asset_type_name": asset.parent_asset.item_type.name if asset.parent_asset and asset.parent_asset.item_type else None,
        "inventory_family": item_family(asset.item_type, asset.item_type.name if asset.item_type else None),
        "inventory_subtype": inventory_subtype(asset.item_type, asset.item_type.name if asset.item_type else None),
        **type_metadata("type", asset.item_type),
    }


def serialize_blueprint(
    blueprint: Blueprint,
    capital_blueprint_type_ids: set[int] | None = None,
    product_type_fallback: EveType | None = None,
) -> dict[str, Any]:
    product_type = blueprint.product_type or product_type_fallback
    family = item_family(product_type, blueprint.blueprint_type.name if blueprint.blueprint_type else None)
    return {
        "id": blueprint.id,
        "owner_name": blueprint.ownership_entity.display_name if blueprint.ownership_entity else "Unknown",
        "blueprint_type_id": blueprint.blueprint_type_id,
        "blueprint_type_name": blueprint.blueprint_type.name if blueprint.blueprint_type else f"Type {blueprint.blueprint_type_id}",
        "product_type_id": blueprint.product_type_id or (product_type.type_id if product_type else None),
        "product_type_name": product_type.name if product_type else None,
        "material_efficiency": blueprint.material_efficiency,
        "time_efficiency": blueprint.time_efficiency,
        "runs_remaining": blueprint.runs_remaining,
        "is_copy": blueprint.is_copy,
        "location_name": blueprint.location.name if blueprint.location else None,
        "location_id": blueprint.location.eve_location_id if blueprint.location else None,
        "last_synced_at": iso(blueprint.last_synced_at),
        "inventory_family": family,
        "inventory_subtype": inventory_subtype(product_type, blueprint.blueprint_type.name if blueprint.blueprint_type else None),
        "capital_construction_related": blueprint.blueprint_type_id in (capital_blueprint_type_ids or set()) and family not in {"reactions", "ram"},
        **type_metadata("blueprint", blueprint.blueprint_type),
        **type_metadata("product", product_type),
    }

def serialize_fitting(fitting: CharacterFitting) -> dict[str, Any]:
    return {
        "id": fitting.id,
        "name": fitting.name,
        "ship_type_id": fitting.ship_type_id,
        "ship_type_name": fitting.ship_type.name if fitting.ship_type else f"Type {fitting.ship_type_id}",
        "is_shared": fitting.is_shared,
        "is_draft": fitting.is_draft,
        "last_synced_at": iso(fitting.last_synced_at),
        "updated_at": iso(fitting.updated_at),
    }


def serialize_kill_observation(row: SystemPvpKillObservation | SystemIndustrialKillObservation) -> dict[str, Any]:
    return {
        "killmail_id": row.killmail_id,
        "killmail_time": iso(row.killmail_time),
        "zkb_url": row.zkb_url,
        "total_value": to_float(row.total_value),
        "victim_hull": row.victim_hull,
        "victim_character_name": row.victim_character_name,
        "victim_corporation_name": row.victim_corporation_name,
        "victim_alliance_name": row.victim_alliance_name,
        "final_blow_character_name": row.final_blow_character_name,
        "final_blow_corporation_name": row.final_blow_corporation_name,
        "final_blow_alliance_name": row.final_blow_alliance_name,
        "final_blow_ship_type_name": row.final_blow_ship_type_name,
        "attacker_count": row.attacker_count,
        "location_name": row.location_name,
        "smartbomb_used": row.smartbomb_used,
        "war_id": row.war_id,
        "is_wardec": row.war_id is not None,
    }


def skill_category_summary(db: Session, character: EveCharacter, limit: int | None = None) -> list[dict[str, Any]]:
    skills = db.scalars(
        select(CharacterSkill)
        .where(CharacterSkill.character_id == character.id)
        .options(selectinload(CharacterSkill.skill_type).selectinload(EveType.group).selectinload(EveGroup.category))
    ).all()
    buckets: dict[str, dict[str, Any]] = {}
    for skill in skills:
        group = skill.skill_type.group if skill.skill_type and skill.skill_type.group else None
        category = group.category if group and group.category else None
        name = group.name if group else (category.name if category and category.name != "Skill" else "Uncategorized")
        bucket = buckets.setdefault(name, {"name": name, "skill_points": 0, "skill_count": 0})
        bucket["skill_points"] += skill.skillpoints_in_skill
        bucket["skill_count"] += 1
    rows = sorted(buckets.values(), key=lambda item: (-item["skill_points"], item["name"]))
    return rows[:limit] if limit else rows


def count_character_assets(db: Session, owner: OwnershipEntity | None) -> dict[str, Any]:
    if owner is None:
        return {"asset_rows": 0, "asset_units": 0, "ship_units": 0, "blueprints": 0, "bpos": 0, "bpcs": 0}
    asset_rows = db.scalar(select(func.count(Asset.id)).where(Asset.ownership_entity_id == owner.id)) or 0
    asset_units = db.scalar(select(func.coalesce(func.sum(Asset.quantity), 0)).where(Asset.ownership_entity_id == owner.id)) or 0
    ship_units = db.scalar(
        select(func.coalesce(func.sum(Asset.quantity), 0))
        .join(EveType, EveType.type_id == Asset.type_id)
        .join(EveGroup, EveGroup.group_id == EveType.group_id, isouter=True)
        .where(Asset.ownership_entity_id == owner.id, EveGroup.category_id == 6)
    ) or 0
    blueprints = db.scalars(select(Blueprint).where(Blueprint.ownership_entity_id == owner.id)).all()
    return {
        "asset_rows": int(asset_rows),
        "asset_units": int(asset_units),
        "ship_units": int(ship_units),
        "blueprints": len(blueprints),
        "bpos": sum(1 for blueprint in blueprints if not blueprint.is_copy),
        "bpcs": sum(1 for blueprint in blueprints if blueprint.is_copy),
    }


def character_summary_payload(db: Session, character: EveCharacter) -> dict[str, Any]:
    owner = owner_for_character(db, character)
    assets = count_character_assets(db, owner)
    queue_count = db.scalar(select(func.count(CharacterSkillQueueEntry.id)).where(CharacterSkillQueueEntry.character_id == character.id)) or 0
    fittings = db.scalar(select(func.count(CharacterFitting.id)).where(CharacterFitting.character_id == character.id)) or 0
    contracts = db.scalar(select(func.count(EveContract.id)).where(EveContract.character_id == character.id)) or 0
    return {
        "character": {
            "id": character.id,
            "character_id": character.character_id,
            "name": character.name,
            "portrait_url": character.portrait_url,
            "security_status": character.security_status,
            "corporation_name": character.corporation.name if character.corporation else None,
            "alliance_name": character.alliance.name if character.alliance else None,
            "owner_display_name": character.owner_user.display_name if character.owner_user else None,
            "owner_role": character.owner_user.role if character.owner_user else None,
        },
        "total_skill_points": character.total_skill_points or 0,
        "unallocated_skill_points": character.unallocated_skill_points or 0,
        "skills_synced_at": iso(character.skills_synced_at),
        "queue_count": int(queue_count),
        "skill_categories": skill_category_summary(db, character, limit=8),
        "asset_rows": assets["asset_rows"],
        "asset_units": assets["asset_units"],
        "ship_units": assets["ship_units"],
        "blueprints": assets["blueprints"],
        "bpos": assets["bpos"],
        "bpcs": assets["bpcs"],
        "fittings": int(fittings),
        "contracts": int(contracts),
    }


def character_tokens_payload(db: Session, viewer: User, character: EveCharacter) -> list[dict[str, Any]]:
    tokens = db.scalars(select(EsiToken).where(EsiToken.character_id == character.id, EsiToken.revoked_at.is_(None)).order_by(EsiToken.created_at.desc())).all()
    payload = []
    for token in tokens:
        scopes = {scope.strip() for scope in (token.scopes or "").split() if scope.strip()}
        owner = db.get(User, token.user_id)
        payload.append(
            {
                "token_id": token.id,
                "linked_user_id": token.user_id,
                "linked_user_display_name": owner.display_name if owner else "Unknown account",
                "can_sync": can_sync_character_data(viewer, character, token, db),
                "has_asset_scope": ASSET_SCOPE in scopes,
                "has_skill_scope": all(scope in scopes for scope in SKILL_SCOPES),
                "has_fitting_scope": FITTING_SCOPE in scopes,
                "has_contract_scope": CONTRACT_SCOPE in scopes,
                "has_clone_scope": all(scope in scopes for scope in CLONE_SCOPES),
                "missing_scopes": [scope for scope in [ASSET_SCOPE, *SKILL_SCOPES, FITTING_SCOPE, CONTRACT_SCOPE, *CLONE_SCOPES] if scope not in scopes],
                "linked_at": iso(token.created_at),
            }
        )
    return payload


def character_kill_history(db: Session, character: EveCharacter) -> dict[str, Any]:
    combined_model = SystemPvpKillObservation
    kills = db.scalars(
        select(combined_model)
        .where(combined_model.final_blow_character_id == character.character_id)
        .order_by(combined_model.killmail_time.desc())
        .limit(10)
    ).all()
    losses = db.scalars(
        select(combined_model)
        .where(combined_model.victim_character_id == character.character_id)
        .order_by(combined_model.killmail_time.desc())
        .limit(10)
    ).all()
    kills_count = db.scalar(select(func.count(combined_model.id)).where(combined_model.final_blow_character_id == character.character_id)) or 0
    losses_count = db.scalar(select(func.count(combined_model.id)).where(combined_model.victim_character_id == character.character_id)) or 0
    isk_destroyed = db.scalar(select(func.coalesce(func.sum(combined_model.total_value), 0)).where(combined_model.final_blow_character_id == character.character_id)) or 0
    isk_lost = db.scalar(select(func.coalesce(func.sum(combined_model.total_value), 0)).where(combined_model.victim_character_id == character.character_id)) or 0
    return {
        "kills_count": int(kills_count),
        "losses_count": int(losses_count),
        "isk_destroyed": to_float(isk_destroyed),
        "isk_lost": to_float(isk_lost),
        "kills": [serialize_kill_observation(row) for row in kills],
        "losses": [serialize_kill_observation(row) for row in losses],
    }


@router.get("")
def list_characters(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [serialize_character(character, current_user, db) for character in visible_characters(current_user, db)]


@router.get("/summary/{eve_character_id}")
def get_character_hover_summary(eve_character_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if role_rank(current_user, db) < ROLE_RANK["member"]:
        raise HTTPException(status_code=403, detail="member role is required")
    character = db.scalar(
        select(EveCharacter)
        .where(EveCharacter.character_id == eve_character_id)
        .options(selectinload(EveCharacter.owner_user), selectinload(EveCharacter.corporation), selectinload(EveCharacter.alliance))
    )
    if character is None:
        raise HTTPException(status_code=404, detail="Character was not found")
    if not can_view_character_detail(current_user, character, db):
        raise HTTPException(status_code=403, detail="Character details are hidden by role policy")
    return character_summary_payload(db, character)


@router.get("/dossier/{character_id}")
def get_character_dossier(character_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    character = db.scalar(
        select(EveCharacter)
        .where(EveCharacter.id == character_id)
        .options(selectinload(EveCharacter.owner_user), selectinload(EveCharacter.corporation), selectinload(EveCharacter.alliance))
    )
    if character is None:
        raise HTTPException(status_code=404, detail="Character was not found")
    if not can_view_character_detail(current_user, character, db):
        raise HTTPException(status_code=403, detail="Character details are hidden by role policy")
    owner = owner_for_character(db, character)
    asset_query = (
        select(Asset)
        .where(Asset.ownership_entity_id == owner.id if owner else False)
        .options(selectinload(Asset.ownership_entity), selectinload(Asset.item_type).selectinload(EveType.group).selectinload(EveGroup.category), selectinload(Asset.location), selectinload(Asset.parent_asset).selectinload(Asset.item_type).selectinload(EveType.group).selectinload(EveGroup.category))
        .order_by(desc(Asset.quantity), Asset.id)
        .limit(50)
    )
    blueprint_query = (
        select(Blueprint)
        .where(Blueprint.ownership_entity_id == owner.id if owner else False)
        .options(selectinload(Blueprint.ownership_entity), selectinload(Blueprint.blueprint_type).selectinload(EveType.group).selectinload(EveGroup.category), selectinload(Blueprint.product_type).selectinload(EveType.group).selectinload(EveGroup.category), selectinload(Blueprint.location))
        .order_by(Blueprint.blueprint_type_id, Blueprint.id)
        .limit(50)
    )
    fittings_query = (
        select(CharacterFitting)
        .where(CharacterFitting.character_id == character.id)
        .options(selectinload(CharacterFitting.ship_type))
        .order_by(CharacterFitting.name)
        .limit(30)
    )
    contracts_query = (
        select(EveContract)
        .where(EveContract.character_id == character.id)
        .options(selectinload(EveContract.character), selectinload(EveContract.corporation))
        .order_by(EveContract.date_issued.desc().nullslast(), EveContract.contract_id.desc())
        .limit(30)
    )
    summary = character_summary_payload(db, character)
    capital_blueprint_type_ids = blueprint_type_ids_for_capital_construction(db)
    blueprint_rows = db.scalars(blueprint_query).all() if owner else []
    blueprint_product_fallbacks = blueprint_product_type_fallbacks(db, {blueprint.blueprint_type_id for blueprint in blueprint_rows})
    return {
        "character": serialize_character(character, current_user, db),
        "summary": summary,
        "sync_tokens": character_tokens_payload(db, current_user, character),
        "skills": {
            "categories": skill_category_summary(db, character),
            "queue": [
                {
                    "id": entry.id,
                    "queue_position": entry.queue_position,
                    "skill_type_id": entry.skill_type_id,
                    "skill_name": entry.skill_type.name if entry.skill_type else f"Type {entry.skill_type_id}",
                    "finished_level": entry.finished_level,
                    "finish_date": iso(entry.finish_date),
                }
                for entry in db.scalars(select(CharacterSkillQueueEntry).where(CharacterSkillQueueEntry.character_id == character.id).options(selectinload(CharacterSkillQueueEntry.skill_type)).order_by(CharacterSkillQueueEntry.queue_position)).all()
            ],
        },
        "assets": [serialize_asset(asset) for asset in db.scalars(asset_query).all()] if owner else [],
        "blueprints": [serialize_blueprint(blueprint, capital_blueprint_type_ids, blueprint_product_fallbacks.get(blueprint.blueprint_type_id)) for blueprint in blueprint_rows],
        "fittings": [serialize_fitting(fitting) for fitting in db.scalars(fittings_query).all()],
        "contracts": [serialize_contract(contract) for contract in db.scalars(contracts_query).all()],
        "kill_history": character_kill_history(db, character),
        "permissions": {
            "public_assets_visible": character.public_assets_visible,
            "sync_opt_out": character.sync_opt_out,
            "can_manage": can_manage_characters(current_user, db) or character.owner_user_id == current_user.id,
            "can_assign": can_manage_characters(current_user, db),
        },
    }


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
                "security_status": character.security_status,
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
    character = db.scalar(
        select(EveCharacter)
        .where(EveCharacter.id == character.id)
        .options(selectinload(EveCharacter.owner_user), selectinload(EveCharacter.corporation), selectinload(EveCharacter.alliance))
    )
    return serialize_character(character, current_user, db)
