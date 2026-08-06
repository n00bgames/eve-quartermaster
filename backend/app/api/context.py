from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import can_view_all_characters, get_current_user
from app.db.session import get_db
from app.models import (
    Asset,
    Blueprint,
    CharacterFitting,
    CharacterFittingItem,
    EveGroup,
    EveType,
    IndustryActivity,
    IndustryActivityInput,
    OwnershipEntity,
    User,
)
from app.services.blueprint_hover import active_blueprint_uses, blueprint_active_use
from app.services.permissions import ROLE_RANK, role_rank
from app.services.corporation_metadata import (
    asset_flag_name,
    asset_location_name,
    corporation_hangar_names,
)

router = APIRouter(prefix="/context", tags=["context"])


def can_view_owner_records(owner: OwnershipEntity | None, current_user: User, db: Session) -> bool:
    if owner is None:
        return False
    if role_rank(current_user, db) >= ROLE_RANK["officer"]:
        return True
    if owner.character and owner.character.owner_user_id == current_user.id:
        return True
    return bool(owner.character and owner.character.public_assets_visible and not owner.character.sync_opt_out)


def can_view_fitting(fitting: CharacterFitting, current_user: User, db: Session) -> bool:
    if can_view_all_characters(current_user, db):
        return True
    if fitting.character and fitting.character.owner_user_id == current_user.id:
        return True
    return bool(fitting.is_shared)


def owner_label(owner: OwnershipEntity | None) -> str:
    return owner.display_name if owner else "Unknown owner"


def top_rows(rows: dict[str, dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    return sorted(rows.values(), key=lambda row: row["quantity"], reverse=True)[:limit]



def summarize_assets_by_type(assets: list[Asset], hangar_names: dict[tuple[int, str], str]) -> dict[int, dict[str, Any]]:
    summaries: dict[int, dict[str, Any]] = {}
    for asset in assets:
        summary = summaries.setdefault(
            asset.type_id,
            {
                "type_id": asset.type_id,
                "quantity": 0,
                "stacks": 0,
                "locations": {},
            },
        )
        summary["quantity"] += asset.quantity
        summary["stacks"] += 1
        owner_name = owner_label(asset.ownership_entity)
        location_name = asset_location_name(asset) or "Unknown location"
        location_flag = asset_flag_name(asset, hangar_names)
        location_key = f"{owner_name.lower()}|{location_name.lower()}|{location_flag or ''}"
        location = summary["locations"].setdefault(
            location_key,
            {
                "owner": owner_name,
                "location": location_name,
                "flag": location_flag,
                "quantity": 0,
            },
        )
        location["quantity"] += asset.quantity
    return summaries


def fitting_payload(fitting: CharacterFitting, quantity: int | None = None, flags: set[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": fitting.id,
        "name": fitting.name,
        "ship_type_name": fitting.ship_type.name if fitting.ship_type else None,
        "character_name": fitting.character.name if fitting.character else None,
        "is_shared": fitting.is_shared,
        "is_draft": fitting.is_draft,
    }
    if quantity is not None:
        payload["quantity"] = quantity
    if flags:
        payload["flags"] = sorted(flags)
    return payload


def blueprint_payload(blueprint: Blueprint, active_use: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": blueprint.id,
        "owner_name": owner_label(blueprint.ownership_entity),
        "blueprint_type_name": blueprint.blueprint_type.name if blueprint.blueprint_type else f"Type {blueprint.blueprint_type_id}",
        "product_type_name": blueprint.product_type.name if blueprint.product_type else None,
        "material_efficiency": blueprint.material_efficiency,
        "time_efficiency": blueprint.time_efficiency,
        "runs_remaining": blueprint.runs_remaining,
        "is_copy": blueprint.is_copy,
        "location_name": blueprint.location.name if blueprint.location else None,
        "active_use": active_use,
    }

@router.post("/assets-summary")
def assets_summary(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    type_ids: set[int] = set()
    for value in payload.get("type_ids", []):
        try:
            type_id = int(value)
        except (TypeError, ValueError):
            continue
        if type_id > 0:
            type_ids.add(type_id)
    if len(type_ids) > 80:
        raise HTTPException(status_code=400, detail="At most 80 item types can be summarized at once.")
    if not type_ids:
        return {"items": []}

    assets = db.scalars(
        select(Asset)
        .where(Asset.type_id.in_(type_ids))
        .options(
            selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.character),
            selectinload(Asset.location),
            selectinload(Asset.parent_asset).selectinload(Asset.item_type),
        )
    ).all()
    visible_assets = [asset for asset in assets if can_view_owner_records(asset.ownership_entity, current_user, db)]
    hangar_names = corporation_hangar_names(db, visible_assets)
    summaries = summarize_assets_by_type(visible_assets, hangar_names)
    return {
        "items": [
            {
                "type_id": type_id,
                "quantity": int(summaries.get(type_id, {}).get("quantity", 0)),
                "stacks": int(summaries.get(type_id, {}).get("stacks", 0)),
                "locations": top_rows(summaries.get(type_id, {}).get("locations", {}), limit=6),
            }
            for type_id in sorted(type_ids)
        ]
    }

@router.get("/item/{type_id}")
def item_context(type_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    item_type = db.scalar(
        select(EveType)
        .where(EveType.type_id == type_id)
        .options(selectinload(EveType.group).selectinload(EveGroup.category))
    )
    if item_type is None:
        raise HTTPException(status_code=404, detail="Item type not found")

    assets = db.scalars(
        select(Asset)
        .where(Asset.type_id == type_id)
        .options(
            selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.character),
            selectinload(Asset.location),
            selectinload(Asset.parent_asset).selectinload(Asset.item_type),
        )
    ).all()
    visible_assets = [asset for asset in assets if can_view_owner_records(asset.ownership_entity, current_user, db)]

    hangar_names = corporation_hangar_names(db, visible_assets)
    owner_totals: dict[str, dict[str, Any]] = {}
    location_totals: dict[str, dict[str, Any]] = {}
    for asset in visible_assets:
        owner_name = owner_label(asset.ownership_entity)
        owner_key = owner_name.lower()
        owner_row = owner_totals.setdefault(
            owner_key,
            {
                "owner_name": owner_name,
                "owner_kind": asset.ownership_entity.owner_kind.value if asset.ownership_entity else None,
                "quantity": 0,
                "stacks": 0,
            },
        )
        owner_row["quantity"] += asset.quantity
        owner_row["stacks"] += 1

        location_name = asset_location_name(asset) or "Unknown location"
        location_flag = asset_flag_name(asset, hangar_names)
        location_key = f"{owner_name.lower()}|{location_name.lower()}|{location_flag or ''}"
        location_row = location_totals.setdefault(
            location_key,
            {
                "owner_name": owner_name,
                "location_name": location_name,
                "location_flag": location_flag,
                "quantity": 0,
                "stacks": 0,
            },
        )
        location_row["quantity"] += asset.quantity
        location_row["stacks"] += 1

    fittings = db.scalars(
        select(CharacterFitting)
        .where(
            or_(
                CharacterFitting.ship_type_id == type_id,
                CharacterFitting.items.any(CharacterFittingItem.type_id == type_id),
                CharacterFitting.items.any(CharacterFittingItem.charge_type_id == type_id),
            )
        )
        .options(
            selectinload(CharacterFitting.character),
            selectinload(CharacterFitting.ship_type),
            selectinload(CharacterFitting.items),
        )
    ).all()
    visible_fittings = [fitting for fitting in fittings if can_view_fitting(fitting, current_user, db)]
    ship_fittings = [fitting_payload(fitting) for fitting in visible_fittings if fitting.ship_type_id == type_id]
    used_by = []
    for fitting in visible_fittings:
        quantity = 0
        flags: set[str] = set()
        for item in fitting.items:
            if item.type_id == type_id or item.charge_type_id == type_id:
                quantity += item.quantity
                flags.add(item.flag)
        if quantity:
            used_by.append(fitting_payload(fitting, quantity=quantity, flags=flags))

    blueprints = db.scalars(
        select(Blueprint)
        .where(or_(Blueprint.blueprint_type_id == type_id, Blueprint.product_type_id == type_id))
        .options(
            selectinload(Blueprint.ownership_entity).selectinload(OwnershipEntity.character),
            selectinload(Blueprint.blueprint_type),
            selectinload(Blueprint.product_type),
            selectinload(Blueprint.location),
            selectinload(Blueprint.asset),
        )
    ).all()
    visible_blueprints = [blueprint for blueprint in blueprints if can_view_owner_records(blueprint.ownership_entity, current_user, db)]
    owned_blueprints = [blueprint for blueprint in visible_blueprints if blueprint.blueprint_type_id == type_id]
    product_blueprints = [blueprint for blueprint in visible_blueprints if blueprint.product_type_id == type_id]
    blueprint_uses = active_blueprint_uses(db, visible_blueprints)

    activities = db.scalars(
        select(IndustryActivity)
        .where(
            or_(
                IndustryActivity.product_type_id == type_id,
                IndustryActivity.inputs.any(IndustryActivityInput.input_type_id == type_id),
            )
        )
        .options(selectinload(IndustryActivity.inputs))
        .limit(24)
    ).all()
    related_type_ids = {activity.blueprint_type_id for activity in activities}
    related_type_ids.update(activity.product_type_id for activity in activities if activity.product_type_id)
    for activity in activities:
        related_type_ids.update(input_row.input_type_id for input_row in activity.inputs)
    related_names = {
        row.type_id: row.name
        for row in db.scalars(select(EveType).where(EveType.type_id.in_(related_type_ids))).all()
    } if related_type_ids else {}

    produced_by = []
    used_in = []
    for activity in activities:
        activity_payload = {
            "id": activity.id,
            "activity_kind": activity.activity_kind.value,
            "blueprint_type_id": activity.blueprint_type_id,
            "blueprint_type_name": related_names.get(activity.blueprint_type_id, f"Type {activity.blueprint_type_id}"),
            "product_type_name": related_names.get(activity.product_type_id) if activity.product_type_id else None,
            "product_quantity": activity.product_quantity,
        }
        if activity.product_type_id == type_id:
            produced_by.append(activity_payload)
        for input_row in activity.inputs:
            if input_row.input_type_id == type_id:
                used_in.append({**activity_payload, "required_quantity": input_row.quantity})

    return {
        "item": {
            "type_id": item_type.type_id,
            "name": item_type.name,
            "group_name": item_type.group.name if item_type.group else None,
            "category_name": item_type.group.category.name if item_type.group and item_type.group.category else None,
            "volume": item_type.volume,
            "packaged_volume": item_type.packaged_volume,
            "capacity": item_type.capacity,
            "market_group_id": item_type.market_group_id,
        },
        "owned": {
            "quantity": sum(asset.quantity for asset in visible_assets),
            "stacks": len(visible_assets),
            "owners": top_rows(owner_totals),
            "locations": top_rows(location_totals),
        },
        "fittings": {
            "total_ship_fittings": len(ship_fittings),
            "total_used_by": len(used_by),
            "ship_fittings": ship_fittings[:6],
            "used_by": sorted(used_by, key=lambda row: row["quantity"], reverse=True)[:8],
        },
        "blueprints": {
            "owned_blueprints": len(owned_blueprints),
            "bpos": sum(1 for blueprint in owned_blueprints if not blueprint.is_copy),
            "bpcs": sum(1 for blueprint in owned_blueprints if blueprint.is_copy),
            "products_owned": sum(asset.quantity for asset in visible_assets),
            "owned_blueprints_sample": [blueprint_payload(blueprint, blueprint_active_use(blueprint, blueprint_uses)) for blueprint in owned_blueprints[:6]],
            "product_blueprints": [blueprint_payload(blueprint, blueprint_active_use(blueprint, blueprint_uses)) for blueprint in product_blueprints[:6]],
        },
        "industry": {
            "produced_by": produced_by[:6],
            "used_by": used_in[:8],
        },
    }
