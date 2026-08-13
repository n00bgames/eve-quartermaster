from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, Blueprint, EveType, Location, OwnershipEntity, User
from app.models.enums import LocationKind
from app.services.asset_visibility import can_view_owner_records
from app.services.corporation_metadata import asset_flag_name


CANONICAL_LOCATION_KINDS = {LocationKind.STATION, LocationKind.STRUCTURE}


def _asset_options() -> tuple[Any, ...]:
    return (
        selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.character),
        selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.corporation),
        selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.alliance),
        selectinload(Asset.item_type),
        selectinload(Asset.location),
    )


def load_blueprint_asset_hierarchy(db: Session, blueprints: Iterable[Blueprint], max_depth: int = 32) -> dict[int, Asset]:
    """Batch-load blueprint assets and their ancestors without loading the full asset table."""
    assets = {
        blueprint.asset.id: blueprint.asset
        for blueprint in blueprints
        if blueprint.asset is not None
    }
    pending = {
        asset.parent_asset_id
        for asset in assets.values()
        if asset.parent_asset_id is not None and asset.parent_asset_id not in assets
    }
    depth = 0
    while pending and depth < max_depth:
        rows = list(db.scalars(select(Asset).options(*_asset_options()).where(Asset.id.in_(pending))).all())
        if not rows:
            break
        assets.update({row.id: row for row in rows})
        pending = {
            row.parent_asset_id
            for row in rows
            if row.parent_asset_id is not None and row.parent_asset_id not in assets
        }
        depth += 1
    return assets


def _resolved_location(location: Location | None) -> tuple[Location | None, bool]:
    if location is None:
        return None, False
    current = location
    visited: set[int] = set()
    traversed = False
    while current.parent is not None and current.id not in visited and current.location_kind not in CANONICAL_LOCATION_KINDS:
        visited.add(current.id)
        current = current.parent
        traversed = True
    return current, traversed


def _usable_location(location: Location | None) -> bool:
    return bool(
        location
        and location.eve_location_id is not None
        and location.name
        and not location.name.startswith("Location ")
    )


def resolve_blueprint_location(
    *,
    blueprint: Blueprint | None,
    active_use: dict[str, Any] | None,
    asset_hierarchy: dict[int, Asset],
    current_user: User,
    db: Session,
    hangar_names: dict[tuple[int, str], str],
) -> dict[str, Any]:
    """Resolve immediate inventory placement and the canonical station/structure."""
    active = active_use or {}
    if active.get("active") and active.get("facility") and active.get("facility_id"):
        return {
            "immediate_location_id": active["facility_id"],
            "immediate_location_name": active["facility"],
            "root_location_id": active["facility_id"],
            "root_location_name": active["facility"],
            "container_id": None,
            "parent_container_id": None,
            "location_flag": None,
            "location_flag_name": None,
            "location_resolution_status": "resolved",
        }

    asset = blueprint.asset if blueprint is not None else None
    if asset is None:
        fallback, traversed = _resolved_location(blueprint.location if blueprint is not None else None)
        if _usable_location(fallback):
            return {
                "immediate_location_id": fallback.eve_location_id,
                "immediate_location_name": fallback.name,
                "root_location_id": fallback.eve_location_id,
                "root_location_name": fallback.name,
                "container_id": None,
                "parent_container_id": None,
                "location_flag": None,
                "location_flag_name": None,
                "location_resolution_status": "resolved_via_parent" if traversed else "resolved",
            }
        return _unresolved_location("unresolved")

    flag_name = asset_flag_name(asset, hangar_names)
    if asset.parent_asset_id is None:
        immediate = asset.location or blueprint.location
        root, traversed = _resolved_location(immediate)
        if _usable_location(root):
            return {
                "immediate_location_id": immediate.eve_location_id if immediate else None,
                "immediate_location_name": immediate.name if immediate else None,
                "root_location_id": root.eve_location_id,
                "root_location_name": root.name,
                "container_id": None,
                "parent_container_id": None,
                "location_flag": asset.location_flag,
                "location_flag_name": flag_name,
                "location_resolution_status": "resolved_via_parent" if traversed else "resolved",
            }
        return _unresolved_location("unresolved", asset.location_flag, flag_name)

    immediate_parent = asset_hierarchy.get(asset.parent_asset_id)
    if immediate_parent is None:
        return _unresolved_location("unresolved", asset.location_flag, flag_name)
    if not can_view_owner_records(immediate_parent.ownership_entity, current_user, db):
        return _unresolved_location("inaccessible", asset.location_flag, flag_name)

    immediate_name = immediate_parent.item_type.name if immediate_parent.item_type else "Container"
    parent_container = asset_hierarchy.get(immediate_parent.parent_asset_id) if immediate_parent.parent_asset_id else None
    current: Asset | None = immediate_parent
    visited: set[int] = set()
    while current is not None and current.id not in visited:
        visited.add(current.id)
        if not can_view_owner_records(current.ownership_entity, current_user, db):
            return _unresolved_location("inaccessible", asset.location_flag, flag_name)
        root, _ = _resolved_location(current.location)
        if _usable_location(root):
            return {
                "immediate_location_id": immediate_parent.eve_item_id,
                "immediate_location_name": immediate_name,
                "root_location_id": root.eve_location_id,
                "root_location_name": root.name,
                "container_id": immediate_parent.eve_item_id,
                "parent_container_id": parent_container.eve_item_id if parent_container else None,
                "location_flag": asset.location_flag,
                "location_flag_name": flag_name,
                "location_resolution_status": "resolved_via_parent",
            }
        if current.parent_asset_id is None:
            break
        current = asset_hierarchy.get(current.parent_asset_id)

    fallback, _ = _resolved_location(blueprint.location)
    if _usable_location(fallback):
        return {
            "immediate_location_id": immediate_parent.eve_item_id,
            "immediate_location_name": immediate_name,
            "root_location_id": fallback.eve_location_id,
            "root_location_name": fallback.name,
            "container_id": immediate_parent.eve_item_id,
            "parent_container_id": parent_container.eve_item_id if parent_container else None,
            "location_flag": asset.location_flag,
            "location_flag_name": flag_name,
            "location_resolution_status": "resolved_via_parent",
        }
    return _unresolved_location("unresolved", asset.location_flag, flag_name)


def _unresolved_location(status: str, location_flag: str | None = None, flag_name: str | None = None) -> dict[str, Any]:
    return {
        "immediate_location_id": None,
        "immediate_location_name": None,
        "root_location_id": None,
        "root_location_name": None,
        "container_id": None,
        "parent_container_id": None,
        "location_flag": location_flag,
        "location_flag_name": flag_name,
        "location_resolution_status": status,
    }
