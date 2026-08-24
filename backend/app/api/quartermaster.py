from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    Asset,
    Blueprint,
    EveAlliance,
    EveCategory,
    EveCharacter,
    EveCorporation,
    EveGroup,
    EveType,
    IndustryActivity,
    IndustryActivityInput,
    Location,
    OwnershipEntity,
    ProcurementSource,
    ResearchProject,
    User,
)
from app.models.enums import ActivityKind, AssetSource, LocationKind, OwnerKind, ProcurementKind
from app.services.asset_visibility import can_view_owner_records, visible_asset_rows
from app.services.blueprint_hover import active_blueprint_uses, blueprint_active_use, project_blueprint_metadata, research_use_payload
from app.services.blueprint_locations import load_blueprint_asset_hierarchy, resolve_blueprint_location
from app.services.research_projects import ACTIVE_RESEARCH_STATUSES
from app.services.corporation_metadata import (
    asset_flag_name,
    asset_location_name,
    corporation_hangar_names,
)

router = APIRouter(prefix="/quartermaster", tags=["quartermaster"], dependencies=[Depends(get_current_user)])

RESEARCH_BLUEPRINT_ACTIVITY_IDS = frozenset({3, 4, 5})
EXPORT_SCHEMA_VERSION = "eqm.inventory.v2"
EXPORT_APP_VERSION = "0.1.21.3-beta"


def iso_utc(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def owner_eve_id(owner: OwnershipEntity | None) -> int | None:
    if owner is None:
        return None
    if owner.owner_kind == OwnerKind.CHARACTER and owner.character:
        return owner.character.character_id
    if owner.owner_kind == OwnerKind.CORPORATION and owner.corporation:
        return owner.corporation.corporation_id
    if owner.owner_kind == OwnerKind.ALLIANCE and owner.alliance:
        return owner.alliance.alliance_id
    return None


def export_id(value: Any) -> str | None:
    """Identifiers are strings in JSON so 64-bit EVE IDs survive JavaScript consumers."""
    return None if value in (None, "") else str(value)


def privacy_id(value: Any, *, include_exact: bool, hash_ids: bool, user_id: int, domain: str) -> str | None:
    if value in (None, ""):
        return None
    if hash_ids:
        secret = get_settings().auth_secret_key.encode("utf-8")
        message = f"export:{user_id}:{domain}:{value}".encode("utf-8")
        return f"sha256:{hmac.new(secret, message, hashlib.sha256).hexdigest()}"
    return export_id(value) if include_exact else None


def location_alias(aliases: dict[str, Any], location_id: Any, location_name: Any) -> str | None:
    for key in (export_id(location_id), str(location_name or "").strip() or None):
        if key and key in aliases and str(aliases[key]).strip():
            return str(aliases[key]).strip()
    return None


def export_payload(kind: str, file_format: str, rows: list[dict[str, Any]], generated_at: datetime, fieldnames: list[str] | None = None, extra_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    generated_text = iso_utc(generated_at)
    stamp = generated_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    metadata = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at_utc": generated_text,
        "application_version": EXPORT_APP_VERSION,
        "record_type": kind,
        "record_count": len(rows),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    normalized = [{**metadata, **row} for row in rows]
    if file_format == "json":
        content = json.dumps({**metadata, "records": normalized}, ensure_ascii=False, indent=2)
        mime_type = "application/json;charset=utf-8"
    else:
        output = io.StringIO(newline="")
        csv_fields = list(metadata) + (fieldnames or list(rows[0]) if rows else fieldnames or [])
        writer = csv.DictWriter(output, fieldnames=csv_fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(normalized)
        content = "\ufeff" + output.getvalue()
        mime_type = "text/csv;charset=utf-8"
    return {
        "filename": f"eve-{kind}-{stamp}.{file_format}",
        "mime_type": mime_type,
        "content": content,
        "row_count": len(rows),
        **metadata,
    }


def export_options(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    options = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    raw_aliases = payload.get("location_aliases") if isinstance(payload.get("location_aliases"), dict) else {}
    aliases = {
        str(key).strip(): str(value).strip()
        for key, value in raw_aliases.items()
        if str(key).strip() and str(value).strip()
    }
    if len(aliases) > 500:
        raise HTTPException(status_code=400, detail="location_aliases may contain at most 500 entries")
    if any(len(key) > 255 or len(value) > 255 for key, value in aliases.items()):
        raise HTTPException(status_code=400, detail="location alias keys and values must be 255 characters or fewer")
    return options, aliases


def serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "value"):
        return value.value
    return value


def row_dict(model: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {column.name: serialize(getattr(model, column.name)) for column in model.__table__.columns}
    if extra:
        data.update(extra)
    return data


def get_or_404(db: Session, model: Any, object_id: int) -> Any:
    item = db.get(model, object_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} {object_id} was not found")
    return item


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


def is_capital_construction_type(item_type: EveType | None) -> bool:
    if item_type is None or item_type.group is None:
        return False
    group_name = item_type.group.name.lower()
    category_name = item_type.group.category.name.lower() if item_type.group.category else ""
    capital_terms = ["capital", "dreadnought", "carrier", "force auxiliary", "supercarrier", "titan", "freighter", "jump freighter"]
    if any(term in group_name for term in capital_terms):
        return True
    return category_name == "ship" and any(term in group_name for term in capital_terms)


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

@router.get("/summary")
def summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    assets = db.scalars(
        select(Asset)
        .options(selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.character))
    ).all()
    blueprints = db.scalars(
        select(Blueprint)
        .options(selectinload(Blueprint.ownership_entity).selectinload(OwnershipEntity.character))
    ).all()
    visible_assets = [asset for asset in assets if can_view_owner_records(asset.ownership_entity, current_user, db)]
    visible_blueprints = [blueprint for blueprint in blueprints
        if can_view_owner_records(blueprint.ownership_entity, current_user, db)]
    asset_units = sum(asset.quantity for asset in visible_assets)
    return {
        "owners": db.scalar(select(func.count()).select_from(OwnershipEntity)) or 0,
        "locations": db.scalar(select(func.count()).select_from(Location)) or 0,
        "types": db.scalar(select(func.count()).select_from(EveType)) or 0,
        "asset_stacks": len(visible_assets),
        "asset_units": asset_units,
        "blueprints": len(visible_blueprints),
        "industry_activities": db.scalar(select(func.count()).select_from(IndustryActivity)) or 0,
    }

@router.get("/owners")
def list_owners(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    owners = db.scalars(select(OwnershipEntity).order_by(OwnershipEntity.display_name)).all()
    return [row_dict(owner) for owner in owners]


@router.post("/owners")
def create_owner(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    display_name = payload.get("display_name")
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name is required")
    owner_kind = OwnerKind(payload.get("owner_kind", OwnerKind.MANUAL_GROUP.value))
    owner = OwnershipEntity(owner_kind=owner_kind, display_name=display_name, notes=payload.get("notes"))
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return row_dict(owner)


@router.get("/types")
def list_types(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    types = db.scalars(select(EveType).order_by(EveType.name).limit(250)).all()
    return [row_dict(item_type) for item_type in types]


@router.post("/types")
def create_type(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    for field in ["type_id", "name"]:
        if payload.get(field) in (None, ""):
            raise HTTPException(status_code=400, detail=f"{field} is required")
    item_type = EveType(
        type_id=int(payload["type_id"]),
        name=payload["name"],
        group_id=payload.get("group_id"),
        volume=payload.get("volume"),
        packaged_volume=payload.get("packaged_volume"),
        capacity=payload.get("capacity"),
        market_group_id=payload.get("market_group_id"),
        published=bool(payload.get("published", True)),
    )
    db.add(item_type)
    db.commit()
    db.refresh(item_type)
    return row_dict(item_type)


@router.get("/locations")
def list_locations(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    locations = db.scalars(select(Location).order_by(Location.name)).all()
    return [row_dict(location) for location in locations]


@router.post("/locations")
def create_location(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="name is required")
    location = Location(
        name=payload["name"],
        location_kind=LocationKind(payload.get("location_kind", LocationKind.UNKNOWN.value)),
        eve_location_id=payload.get("eve_location_id"),
        system_id=payload.get("system_id"),
        parent_location_id=payload.get("parent_location_id"),
        source=AssetSource(payload.get("source", AssetSource.MANUAL.value)),
        notes=payload.get("notes"),
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return row_dict(location)



def serialize_asset(asset: Asset, hangar_names: dict[tuple[int, str], str] | None = None) -> dict[str, Any]:
    parent_type_name = asset.parent_asset.item_type.name if asset.parent_asset and asset.parent_asset.item_type else None
    return row_dict(
        asset,
        {
            "owner_name": asset.ownership_entity.display_name if asset.ownership_entity else None,
            "owner_kind": asset.ownership_entity.owner_kind.value if asset.ownership_entity else None,
            "type_name": asset.item_type.name if asset.item_type else None,
            "location_name": asset_location_name(asset),
            "location_id": asset.location.eve_location_id if asset.location else None,
            "location_flag_name": asset_flag_name(asset, hangar_names or {}),
            "parent_asset_item_id": asset.parent_asset.eve_item_id if asset.parent_asset else None,
            "parent_asset_type_name": parent_type_name,
            "inventory_family": item_family(asset.item_type, asset.item_type.name if asset.item_type else None),
            "inventory_subtype": inventory_subtype(asset.item_type, asset.item_type.name if asset.item_type else None),
            **type_metadata("type", asset.item_type),
        },
    )


def asset_sort_value(asset: Asset, key: str, hangar_names: dict[tuple[int, str], str] | None = None) -> Any:
    if key == "owner":
        return asset.ownership_entity.display_name if asset.ownership_entity else ""
    if key == "quantity":
        return asset.quantity or 0
    if key == "location":
        return asset_location_name(asset) or ""
    if key == "flag":
        return asset_flag_name(asset, hangar_names or {}) or ""
    return asset.item_type.name if asset.item_type else ""


def asset_filter_value(asset: Asset, key: str, hangar_names: dict[tuple[int, str], str] | None = None) -> str:
    return str(asset_sort_value(asset, key, hangar_names) or "-")


def asset_matches_query(asset: Asset, owner_kind: str | None, category: str, subtype: str | None, filter_key: str | None, filter_value: str | None, filter_mode: str, hangar_names: dict[tuple[int, str], str] | None = None) -> bool:
    if owner_kind and (not asset.ownership_entity or asset.ownership_entity.owner_kind.value != owner_kind):
        return False
    family = item_family(asset.item_type, asset.item_type.name if asset.item_type else None)
    capital_related = is_capital_construction_type(asset.item_type)
    if category and category != "all":
        if category == "capital-construction":
            if not capital_related:
                return False
        elif family != category:
            return False
    if subtype and inventory_subtype(asset.item_type, asset.item_type.name if asset.item_type else None) != subtype:
        return False
    if filter_key and filter_value:
        value = asset_filter_value(asset, filter_key, hangar_names)
        if filter_mode == "contains":
            return filter_value.lower() in value.lower()
        return value == filter_value
    return True


def asset_matches_export_filters(asset: Asset, filters: dict[str, Any], aliases: dict[str, Any], hangar_names: dict[tuple[int, str], str]) -> bool:
    if not asset_matches_query(
        asset,
        filters.get("owner_kind") or None,
        filters.get("category") or "all",
        filters.get("subtype") or None,
        filters.get("filter_key") or None,
        filters.get("filter_value") or None,
        filters.get("filter_mode") or "exact",
        hangar_names,
    ):
        return False
    owner = asset.ownership_entity
    checks = {
        "owner_id": owner_eve_id(owner),
        "location_id": asset.location.eve_location_id if asset.location else None,
        "group_id": asset.item_type.group_id if asset.item_type else None,
        "type_id": asset.type_id,
        "container_id": asset.parent_asset.eve_item_id if asset.parent_asset else None,
    }
    for key, actual in checks.items():
        expected = filters.get(key)
        if expected not in (None, "") and str(actual) != str(expected):
            return False
    location_name = asset_location_name(asset)
    alias = location_alias(aliases, checks["location_id"], location_name)
    if filters.get("location_alias") and str(filters["location_alias"]).lower() != str(alias or "").lower():
        return False
    if filters.get("singleton") is not None and bool(asset.is_singleton) != bool(filters["singleton"]):
        return False
    if filters.get("packaged_or_assembled") and ("assembled" if asset.is_singleton else "packaged") != filters["packaged_or_assembled"]:
        return False
    is_blueprint = item_family(asset.item_type, asset.item_type.name if asset.item_type else None) == "blueprints"
    if filters.get("is_blueprint") is not None and is_blueprint != bool(filters["is_blueprint"]):
        return False
    marketable = bool(asset.item_type and asset.item_type.market_group_id is not None and asset.item_type.published)
    if filters.get("marketable") is not None and marketable != bool(filters["marketable"]):
        return False
    return True


def asset_export_row(asset: Asset, options: dict[str, Any], aliases: dict[str, Any], hangar_names: dict[tuple[int, str], str], current_user: User) -> dict[str, Any]:
    owner = asset.ownership_entity
    item_type = asset.item_type
    location_id = asset.location.eve_location_id if asset.location else None
    location_name = asset_location_name(asset)
    alias = location_alias(aliases, location_id, location_name)
    hash_ids = bool(options.get("hash_ids", False))
    include_owner_ids = bool(options.get("include_owner_ids", True))
    include_location_ids = bool(options.get("include_location_ids", True))
    include_location_names = bool(options.get("include_location_names", True))
    packaged = not bool(asset.is_singleton)
    unit_volume = (item_type.packaged_volume if packaged and item_type and item_type.packaged_volume is not None else item_type.volume if item_type else None)
    marketable = bool(item_type and item_type.market_group_id is not None and item_type.published)
    return {
        "item_id": privacy_id(asset.eve_item_id, include_exact=True, hash_ids=hash_ids, user_id=current_user.id, domain="item"),
        "type_id": export_id(asset.type_id),
        "type_name": item_type.name if item_type else None,
        "quantity": int(asset.quantity),
        "singleton": bool(asset.is_singleton),
        "packaged_or_assembled": "packaged" if packaged else "assembled",
        "is_blueprint": item_family(item_type, item_type.name if item_type else None) == "blueprints",
        "is_blueprint_copy": asset.is_blueprint_copy,
        "marketable": marketable,
        "location_id": privacy_id(location_id, include_exact=include_location_ids, hash_ids=hash_ids, user_id=current_user.id, domain="location"),
        "location_name": location_name if include_location_names else None,
        "location_alias": alias,
        "location_flag": asset.location_flag,
        "location_flag_name": asset_flag_name(asset, hangar_names),
        "container_id": privacy_id(asset.parent_asset.eve_item_id if asset.parent_asset else None, include_exact=include_location_ids, hash_ids=hash_ids, user_id=current_user.id, domain="container"),
        "parent_container_id": privacy_id(asset.parent_asset.parent_asset.eve_item_id if asset.parent_asset and asset.parent_asset.parent_asset else None, include_exact=include_location_ids, hash_ids=hash_ids, user_id=current_user.id, domain="container"),
        "owner_type": owner.owner_kind.value if owner else None,
        "owner_id": privacy_id(owner_eve_id(owner), include_exact=include_owner_ids, hash_ids=hash_ids, user_id=current_user.id, domain="owner"),
        "owner_name": None if options.get("exclude_owner_names") else owner.display_name if owner else None,
        "category_id": export_id(item_type.group.category_id if item_type and item_type.group else None),
        "category_name": item_type.group.category.name if item_type and item_type.group and item_type.group.category else None,
        "group_id": export_id(item_type.group_id if item_type else None),
        "group_name": item_type.group.name if item_type and item_type.group else None,
        "market_group_id": export_id(item_type.market_group_id if item_type else None),
        "volume_each_m3": unit_volume,
        "total_volume_m3": float(unit_volume) * int(asset.quantity) if unit_volume is not None else None,
        "estimated_unit_price_isk": None,
        "estimated_total_value_isk": None,
        "price_source": "unavailable",
        "price_region_id": None,
        "price_timestamp_utc": None,
        "source": asset.source.value if hasattr(asset.source, "value") else str(asset.source),
        "last_synced_at_utc": iso_utc(asset.last_synced_at),
    }


@router.get("/assets")
def list_assets(limit: int = Query(250, ge=1, le=1000), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = visible_asset_rows(current_user, db)[:limit]
    hangar_names = corporation_hangar_names(db, rows)
    return [serialize_asset(asset, hangar_names) for asset in rows]


@router.get("/assets-page")
def list_assets_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=25, le=500),
    sort_key: str = Query("item", pattern="^(item|owner|quantity|location|flag)$"),
    sort_direction: str = Query("asc", pattern="^(asc|desc)$"),
    owner_kind: str | None = Query(None, pattern="^(character|corporation|alliance|manual_group)$"),
    category: str = Query("all"),
    subtype: str | None = Query(None),
    filter_key: str | None = Query(None, pattern="^(item|owner|location|flag)$"),
    filter_value: str | None = Query(None),
    filter_mode: str = Query("exact", pattern="^(exact|contains)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    visible_rows = visible_asset_rows(current_user, db)
    hangar_names = corporation_hangar_names(db, visible_rows)
    rows = [
        asset
        for asset in visible_rows
        if asset_matches_query(asset, owner_kind, category, subtype, filter_key, filter_value, filter_mode, hangar_names)
    ]
    rows.sort(
        key=lambda asset: asset_sort_value(asset, sort_key, hangar_names),
        reverse=sort_direction == "desc",
    )
    total = len(rows)
    start = (page - 1) * page_size
    return {
        "items": [serialize_asset(asset, hangar_names) for asset in rows[start:start + page_size]],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/assets-export")
def export_assets(
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    file_format = str(payload.get("format") or "csv").lower()
    scope = str(payload.get("scope") or "filtered").lower()
    if file_format not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail="format must be csv or json")
    if scope not in {"filtered", "all"}:
        raise HTTPException(status_code=400, detail="scope must be filtered or all")
    options, aliases = export_options(payload)
    filters = payload.get("filters") if scope == "filtered" and isinstance(payload.get("filters"), dict) else {}
    visible_rows = visible_asset_rows(current_user, db)
    hangar_names = corporation_hangar_names(db, visible_rows)
    rows = [asset for asset in visible_rows if asset_matches_export_filters(asset, filters, aliases, hangar_names)]
    sort_key = str(filters.get("sort_key") or "item")
    if sort_key not in {"item", "owner", "quantity", "location", "flag"}:
        sort_key = "item"
    rows.sort(key=lambda asset: asset_sort_value(asset, sort_key, hangar_names), reverse=filters.get("sort_direction") == "desc")
    export_rows = [asset_export_row(asset, options, aliases, hangar_names, current_user) for asset in rows]
    fields = list(export_rows[0]) if export_rows else []
    if not rows:
        fields = [
            "item_id", "type_id", "type_name", "quantity", "singleton", "packaged_or_assembled", "is_blueprint", "is_blueprint_copy", "marketable",
            "location_id", "location_name", "location_alias", "location_flag", "location_flag_name", "container_id", "parent_container_id", "owner_type", "owner_id", "owner_name",
            "category_id", "category_name", "group_id", "group_name", "market_group_id", "volume_each_m3", "total_volume_m3", "estimated_unit_price_isk",
            "estimated_total_value_isk", "price_source", "price_region_id", "price_timestamp_utc", "source", "last_synced_at_utc",
        ]
    return export_payload("assets", file_format, export_rows, datetime.now(timezone.utc), fields)


@router.post("/assets")
def create_asset(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    for field in ["ownership_entity_id", "type_id", "quantity"]:
        if payload.get(field) in (None, ""):
            raise HTTPException(status_code=400, detail=f"{field} is required")
    get_or_404(db, OwnershipEntity, int(payload["ownership_entity_id"]))
    type_id = int(payload["type_id"])
    if db.get(EveType, type_id) is None:
        raise HTTPException(status_code=400, detail="type_id must reference an existing EVE type")
    if payload.get("location_id"):
        get_or_404(db, Location, int(payload["location_id"]))
    asset = Asset(
        ownership_entity_id=int(payload["ownership_entity_id"]),
        eve_item_id=payload.get("eve_item_id"),
        type_id=type_id,
        quantity=int(payload["quantity"]),
        location_id=payload.get("location_id"),
        parent_asset_id=payload.get("parent_asset_id"),
        location_flag=payload.get("location_flag"),
        is_singleton=bool(payload.get("is_singleton", False)),
        is_blueprint_copy=payload.get("is_blueprint_copy"),
        source=AssetSource(payload.get("source", AssetSource.MANUAL.value)),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return row_dict(asset)


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


def active_research_blueprint_projects(db: Session) -> list[ResearchProject]:
    return list(db.scalars(
        select(ResearchProject)
        .options(
            selectinload(ResearchProject.blueprint_type),
            selectinload(ResearchProject.character),
            selectinload(ResearchProject.corporation),
        )
        .where(
            ResearchProject.activity_id.in_(RESEARCH_BLUEPRINT_ACTIVITY_IDS),
            ResearchProject.status.in_(ACTIVE_RESEARCH_STATUSES),
            ResearchProject.blueprint_id.is_not(None),
            ResearchProject.blueprint_type_id.is_not(None),
        )
        .order_by(ResearchProject.id.desc())
    ).all())


def research_project_owner(project: ResearchProject, owners: list[OwnershipEntity]) -> OwnershipEntity | None:
    if project.source_type == "corporation":
        return next((owner for owner in owners if owner.owner_kind == OwnerKind.CORPORATION and owner.corporation_id == project.corporation_id), None)
    return next((owner for owner in owners if owner.owner_kind == OwnerKind.CHARACTER and owner.character_id == project.character_id), None)

def blueprint_rows(current_user: User, db: Session) -> list[dict[str, Any]]:
    capital_blueprint_type_ids = blueprint_type_ids_for_capital_construction(db)
    blueprints = db.scalars(
        select(Blueprint)
        .options(
            selectinload(Blueprint.ownership_entity).selectinload(OwnershipEntity.character),
            selectinload(Blueprint.ownership_entity).selectinload(OwnershipEntity.corporation),
            selectinload(Blueprint.ownership_entity).selectinload(OwnershipEntity.alliance),
            selectinload(Blueprint.blueprint_type),
            selectinload(Blueprint.product_type).selectinload(EveType.group).selectinload(EveGroup.category),
            selectinload(Blueprint.location),
            selectinload(Blueprint.asset).selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.character),
            selectinload(Blueprint.asset).selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.corporation),
            selectinload(Blueprint.asset).selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.alliance),
            selectinload(Blueprint.asset).selectinload(Asset.item_type),
            selectinload(Blueprint.asset).selectinload(Asset.location),
        )
        .order_by(Blueprint.id.desc())
    ).all()
    research_projects = active_research_blueprint_projects(db)
    all_blueprint_type_ids = {blueprint.blueprint_type_id for blueprint in blueprints}
    all_blueprint_type_ids.update(int(project.blueprint_type_id) for project in research_projects if project.blueprint_type_id is not None)
    product_fallbacks = blueprint_product_type_fallbacks(db, all_blueprint_type_ids)
    blueprint_uses = active_blueprint_uses(db, blueprints)
    asset_hierarchy = load_blueprint_asset_hierarchy(db, blueprints)
    hangar_names = corporation_hangar_names(db, list(asset_hierarchy.values()))
    owners = list(db.scalars(
        select(OwnershipEntity).options(
            selectinload(OwnershipEntity.character),
            selectinload(OwnershipEntity.corporation),
            selectinload(OwnershipEntity.alliance),
        )
    ).all())
    visible_inventory_item_ids = {
        int(blueprint.asset.eve_item_id)
        for blueprint in blueprints
        if blueprint.asset is not None
        and blueprint.asset.eve_item_id is not None
        and can_view_owner_records(blueprint.ownership_entity, current_user, db)
    }
    project_metadata = project_blueprint_metadata(db, research_projects)
    results = []
    for blueprint in blueprints:
        if not can_view_owner_records(blueprint.ownership_entity, current_user, db):
            continue
        product_type = blueprint.product_type or product_fallbacks.get(blueprint.blueprint_type_id)
        family = item_family(product_type, blueprint.blueprint_type.name if blueprint.blueprint_type else None)
        active_use = blueprint_active_use(blueprint, blueprint_uses)
        resolved_location = resolve_blueprint_location(
            blueprint=blueprint,
            active_use=active_use,
            asset_hierarchy=asset_hierarchy,
            current_user=current_user,
            db=db,
            hangar_names=hangar_names,
        )
        results.append(
            row_dict(
                blueprint,
                {
                    "owner_name": blueprint.ownership_entity.display_name if blueprint.ownership_entity else None,
                    "owner_type": blueprint.ownership_entity.owner_kind.value if blueprint.ownership_entity else None,
                    "owner_eve_id": owner_eve_id(blueprint.ownership_entity),
                    "item_id": blueprint.asset.eve_item_id if blueprint.asset else None,
                    "blueprint_type_name": blueprint.blueprint_type.name if blueprint.blueprint_type else None,
                    "product_type_id": blueprint.product_type_id or (product_type.type_id if product_type else None),
                    "product_type_name": product_type.name if product_type else None,
                    "location_name": resolved_location["root_location_name"],
                    "location_id": resolved_location["root_location_id"],
                    "location_resolution": resolved_location,
                    "active_use": active_use,
                    "inventory_family": family,
                    "inventory_subtype": inventory_subtype(product_type, blueprint.blueprint_type.name if blueprint.blueprint_type else None),
                    "capital_construction_related": blueprint.blueprint_type_id in capital_blueprint_type_ids and family not in {"reactions", "ram"},
                    **type_metadata("blueprint", blueprint.blueprint_type),
                    **type_metadata("product", product_type),
                },
            )
        )
    seen_shadow_item_ids: set[int] = set()
    for project in research_projects:
        if project.blueprint_id is None or project.blueprint_type_id is None:
            continue
        item_id = int(project.blueprint_id)
        if item_id in visible_inventory_item_ids or item_id in seen_shadow_item_ids:
            continue
        owner = research_project_owner(project, owners)
        if owner is None or not can_view_owner_records(owner, current_user, db):
            continue
        seen_shadow_item_ids.add(item_id)
        metadata = project_metadata.get(project.id, {})
        blueprint_type = project.blueprint_type
        product_type = product_fallbacks.get(int(project.blueprint_type_id))
        family = item_family(product_type, blueprint_type.name if blueprint_type else None)
        results.append({
            "id": -project.id,
            "asset_id": None,
            "owner_name": owner.display_name,
            "owner_type": owner.owner_kind.value,
            "owner_eve_id": owner_eve_id(owner),
            "item_id": item_id,
            "blueprint_type_id": int(project.blueprint_type_id),
            "blueprint_type_name": blueprint_type.name if blueprint_type else f"Type {project.blueprint_type_id}",
            "product_type_id": product_type.type_id if product_type else None,
            "product_type_name": product_type.name if product_type else None,
            "material_efficiency": int(metadata.get("material_efficiency") or 0),
            "time_efficiency": int(metadata.get("time_efficiency") or 0),
            "runs_remaining": metadata.get("runs_remaining"),
            "is_copy": bool(metadata.get("is_copy")) if metadata.get("is_copy") is not None else False,
            "location_name": metadata.get("blueprint_location_name") or project.facility_name,
            "location_id": project.facility_id,
            "location_resolution": {
                "immediate_location_id": project.facility_id,
                "immediate_location_name": metadata.get("blueprint_location_name") or project.facility_name,
                "root_location_id": project.facility_id,
                "root_location_name": project.facility_name or metadata.get("blueprint_location_name"),
                "container_id": None,
                "parent_container_id": None,
                "location_flag": None,
                "location_flag_name": None,
                "location_resolution_status": "resolved" if project.facility_id and project.facility_name else "unresolved",
            },
            "last_synced_at": project.last_synced_at.isoformat() if project.last_synced_at else None,
            "active_use": research_use_payload(project),
            "inventory_state": "in_research",
            "research_shadow": True,
            "inventory_family": family,
            "inventory_subtype": inventory_subtype(product_type, blueprint_type.name if blueprint_type else None),
            "capital_construction_related": int(project.blueprint_type_id) in capital_blueprint_type_ids and family not in {"reactions", "ram"},
            **type_metadata("blueprint", blueprint_type),
            **type_metadata("product", product_type),
        })
    return results


@router.get("/blueprints")
def list_blueprints(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in row.items() if key not in {"owner_eve_id", "item_id"}}
        for row in blueprint_rows(current_user, db)
    ]


def blueprint_matches_export_filters(row: dict[str, Any], filters: dict[str, Any], aliases: dict[str, Any]) -> bool:
    kind = str(filters.get("kind") or "all")
    if kind == "bpo" and row.get("is_copy"):
        return False
    if kind == "bpc" and not row.get("is_copy"):
        return False
    if filters.get("owner") and str(row.get("owner_name")) != str(filters["owner"]):
        return False
    family = str(row.get("inventory_family") or "other")
    category = str(filters.get("category") or "all")
    if category == "capital-construction":
        if not row.get("capital_construction_related"):
            return False
    elif category != "all" and family != category:
        return False
    if filters.get("subtype") and str(row.get("inventory_subtype") or "") != str(filters["subtype"]):
        return False
    alias = location_alias(aliases, row.get("location_id"), row.get("location_name"))
    if filters.get("location_alias") and str(filters["location_alias"]).lower() != str(alias or "").lower():
        return False
    search = str(filters.get("search") or "").strip().lower()
    if search:
        haystack = " ".join(str(value) for value in [
            row.get("blueprint_type_name"), row.get("product_type_name"), row.get("owner_name"),
            row.get("location_name"), row.get("product_category_name"), row.get("product_group_name"),
            "BPC" if row.get("is_copy") else "BPO", "in research" if row.get("research_shadow") else "",
            (row.get("active_use") or {}).get("activity"), f"ME {row.get('material_efficiency')}", f"TE {row.get('time_efficiency')}",
        ] if value is not None).lower()
        if search not in haystack:
            return False
    return True


def blueprint_export_row(row: dict[str, Any], options: dict[str, Any], aliases: dict[str, Any], current_user: User) -> dict[str, Any]:
    active = row.get("active_use") if isinstance(row.get("active_use"), dict) else {}
    hash_ids = bool(options.get("hash_ids", False))
    include_owner_ids = bool(options.get("include_owner_ids", True))
    include_location_ids = bool(options.get("include_location_ids", True))
    include_location_names = bool(options.get("include_location_names", True))
    resolution = row.get("location_resolution") if isinstance(row.get("location_resolution"), dict) else {}
    immediate_location_id = resolution.get("immediate_location_id", row.get("location_id"))
    immediate_location_name = resolution.get("immediate_location_name", row.get("location_name"))
    root_location_id = resolution.get("root_location_id", row.get("location_id"))
    root_location_name = resolution.get("root_location_name", row.get("location_name"))
    status = str(resolution.get("location_resolution_status") or "unresolved")
    location_is_anonymized = status in {"resolved", "resolved_via_parent"} and (
        hash_ids or not include_location_ids or not include_location_names
    )
    exported_status = "anonymized" if location_is_anonymized else status
    alias = location_alias(aliases, root_location_id, root_location_name) or location_alias(aliases, immediate_location_id, immediate_location_name)
    return {
        "item_id": privacy_id(row.get("item_id"), include_exact=True, hash_ids=hash_ids, user_id=current_user.id, domain="item"),
        "blueprint_type_id": export_id(row.get("blueprint_type_id")),
        "blueprint_type_name": row.get("blueprint_type_name"),
        "product_type_id": export_id(row.get("product_type_id")),
        "product_type_name": row.get("product_type_name"),
        "blueprint_kind": "BPC" if row.get("is_copy") else "BPO",
        "is_copy": bool(row.get("is_copy")),
        "material_efficiency": row.get("material_efficiency"),
        "time_efficiency": row.get("time_efficiency"),
        "runs_remaining": row.get("runs_remaining"),
        "location_id": privacy_id(root_location_id, include_exact=include_location_ids, hash_ids=hash_ids, user_id=current_user.id, domain="location"),
        "location_name": root_location_name if include_location_names else None,
        "immediate_location_id": privacy_id(immediate_location_id, include_exact=include_location_ids, hash_ids=hash_ids, user_id=current_user.id, domain="immediate_location"),
        "immediate_location_name": immediate_location_name if include_location_names else None,
        "root_location_id": privacy_id(root_location_id, include_exact=include_location_ids, hash_ids=hash_ids, user_id=current_user.id, domain="location"),
        "root_location_name": root_location_name if include_location_names else None,
        "location_alias": alias,
        "location_flag": resolution.get("location_flag"),
        "location_flag_name": resolution.get("location_flag_name"),
        "container_id": privacy_id(resolution.get("container_id"), include_exact=include_location_ids, hash_ids=hash_ids, user_id=current_user.id, domain="container"),
        "parent_container_id": privacy_id(resolution.get("parent_container_id"), include_exact=include_location_ids, hash_ids=hash_ids, user_id=current_user.id, domain="container"),
        "location_resolution_status": exported_status,
        "owner_type": row.get("owner_type"),
        "owner_id": privacy_id(row.get("owner_eve_id"), include_exact=include_owner_ids, hash_ids=hash_ids, user_id=current_user.id, domain="owner"),
        "owner_name": None if options.get("exclude_owner_names") else row.get("owner_name"),
        "inventory_state": row.get("inventory_state") or ("in_use" if active.get("active") else "available"),
        "research_shadow": bool(row.get("research_shadow", False)),
        "active": bool(active.get("active", False)),
        "active_activity": active.get("activity"),
        "active_status": active.get("status"),
        "industry_job_id": export_id(active.get("job_id")),
        "industry_job_runs": active.get("runs"),
        "industry_facility": active.get("facility"),
        "industry_installer": None if options.get("exclude_owner_names") else active.get("installer"),
        "industry_start_date_utc": iso_utc(active.get("start_date")),
        "industry_end_date_utc": iso_utc(active.get("end_date")),
        "inventory_family": row.get("inventory_family"),
        "inventory_subtype": row.get("inventory_subtype"),
        "capital_construction_related": bool(row.get("capital_construction_related", False)),
        "blueprint_category_id": export_id(row.get("blueprint_category_id")),
        "blueprint_category_name": row.get("blueprint_category_name"),
        "blueprint_group_id": export_id(row.get("blueprint_group_id")),
        "blueprint_group_name": row.get("blueprint_group_name"),
        "product_category_id": export_id(row.get("product_category_id")),
        "product_category_name": row.get("product_category_name"),
        "product_group_id": export_id(row.get("product_group_id")),
        "product_group_name": row.get("product_group_name"),
        "product_market_group_id": export_id(row.get("product_market_group_id")),
        "last_synced_at_utc": iso_utc(row.get("last_synced_at")),
    }


@router.post("/blueprints-export")
def export_blueprints(
    payload: dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    file_format = str(payload.get("format") or "csv").lower()
    scope = str(payload.get("scope") or "filtered").lower()
    if file_format not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail="format must be csv or json")
    if scope not in {"filtered", "all"}:
        raise HTTPException(status_code=400, detail="scope must be filtered or all")
    options, aliases = export_options(payload)
    filters = payload.get("filters") if scope == "filtered" and isinstance(payload.get("filters"), dict) else {}
    rows = [row for row in blueprint_rows(current_user, db) if blueprint_matches_export_filters(row, filters, aliases)]
    sort_key = str(filters.get("sort_key") or "name")
    def sort_value(row: dict[str, Any]) -> Any:
        if sort_key == "me":
            return (row.get("material_efficiency") or 0, row.get("blueprint_type_name") or "")
        if sort_key == "te":
            return (row.get("time_efficiency") or 0, row.get("blueprint_type_name") or "")
        return (row.get("blueprint_type_name") or "",)
    rows.sort(key=sort_value, reverse=filters.get("sort_direction") == "desc")
    export_rows = [blueprint_export_row(row, options, aliases, current_user) for row in rows]
    resolved_locations = sum(
        1 for row in rows
        if (row.get("location_resolution") or {}).get("location_resolution_status") in {"resolved", "resolved_via_parent"}
    )
    unresolved_locations = len(rows) - resolved_locations
    location_quality = {
        "total_records": len(rows),
        "resolved_location_records": resolved_locations,
        "unresolved_location_records": unresolved_locations,
        "unresolved_location_percentage": round((unresolved_locations / len(rows)) * 100, 4) if rows else 0.0,
    }
    fields = list(export_rows[0]) if export_rows else [
        "item_id", "blueprint_type_id", "blueprint_type_name", "product_type_id", "product_type_name", "blueprint_kind", "is_copy", "material_efficiency", "time_efficiency",
        "runs_remaining", "location_id", "location_name", "immediate_location_id", "immediate_location_name", "root_location_id", "root_location_name", "location_alias",
        "location_flag", "location_flag_name", "container_id", "parent_container_id", "location_resolution_status", "owner_type", "owner_id", "owner_name", "inventory_state", "research_shadow", "active", "active_activity",
        "active_status", "industry_job_id", "industry_job_runs", "industry_facility", "industry_installer", "industry_start_date_utc", "industry_end_date_utc", "inventory_family",
        "inventory_subtype", "capital_construction_related", "blueprint_category_id", "blueprint_category_name", "blueprint_group_id", "blueprint_group_name", "product_category_id",
        "product_category_name", "product_group_id", "product_group_name", "product_market_group_id", "last_synced_at_utc",
    ]
    return export_payload("blueprints", file_format, export_rows, datetime.now(timezone.utc), fields, location_quality)


@router.get("/missing-blueprints")
def missing_blueprints(
    q: str | None = Query(default=None),
    limit_per_category: int = Query(default=80, ge=5, le=250),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    owned_blueprints = db.scalars(
        select(Blueprint)
        .options(selectinload(Blueprint.ownership_entity).selectinload(OwnershipEntity.character))
    ).all()
    owned_bpo_type_ids = {
        blueprint.blueprint_type_id
        for blueprint in owned_blueprints
        if not blueprint.is_copy and can_view_owner_records(blueprint.ownership_entity, current_user, db)
    }
    owners = list(db.scalars(select(OwnershipEntity).options(selectinload(OwnershipEntity.character))).all())
    for project in active_research_blueprint_projects(db):
        owner = research_project_owner(project, owners)
        if owner is not None and project.blueprint_type_id is not None and can_view_owner_records(owner, current_user, db):
            owned_bpo_type_ids.add(int(project.blueprint_type_id))
    invention_blueprint_type_ids = set(db.scalars(
        select(IndustryActivity.product_type_id)
        .where(IndustryActivity.activity_kind == ActivityKind.INVENTION)
        .where(IndustryActivity.product_type_id.is_not(None))
    ).all())
    activities = db.scalars(
        select(IndustryActivity)
        .where(IndustryActivity.activity_kind == ActivityKind.MANUFACTURING)
        .where(IndustryActivity.product_type_id.is_not(None))
        .order_by(IndustryActivity.blueprint_type_id)
    ).all()
    type_ids = {activity.blueprint_type_id for activity in activities}
    type_ids.update(activity.product_type_id for activity in activities if activity.product_type_id)
    types_by_id = {
        item_type.type_id: item_type
        for item_type in db.scalars(
            select(EveType)
            .where(EveType.type_id.in_(type_ids))
            .options(selectinload(EveType.group).selectinload(EveGroup.category))
        ).all()
    } if type_ids else {}
    capital_blueprint_type_ids = blueprint_type_ids_for_capital_construction(db)
    search_text = q.strip().lower() if q else ""
    buckets: dict[str, dict[str, Any]] = {}
    seen_missing: set[int] = set()
    for activity in activities:
        if activity.blueprint_type_id in owned_bpo_type_ids or activity.blueprint_type_id in invention_blueprint_type_ids or activity.blueprint_type_id in seen_missing:
            continue
        blueprint_type = types_by_id.get(activity.blueprint_type_id)
        product_type = types_by_id.get(activity.product_type_id) if activity.product_type_id else None
        if blueprint_type is None:
            continue
        search_haystack = " ".join(
            value for value in [
                blueprint_type.name,
                product_type.name if product_type else None,
                product_type.group.name if product_type and product_type.group else None,
                product_type.group.category.name if product_type and product_type.group and product_type.group.category else None,
            ] if value
        ).lower()
        if search_text and search_text not in search_haystack:
            continue
        family = item_family(product_type, blueprint_type.name)
        is_capital_chain = activity.blueprint_type_id in capital_blueprint_type_ids
        if is_capital_chain:
            category_name = "Capital construction"
        elif family == "reactions":
            category_name = "Reactions"
        elif family == "ram":
            category_name = "RAM"
        elif family == "drones":
            category_name = "Drones/Fighters"
        else:
            category_name = product_type.group.category.name if product_type and product_type.group and product_type.group.category else "Uncategorized"
        product_category_name = product_type.group.category.name if product_type and product_type.group and product_type.group.category else category_name
        group_name = inventory_subtype(product_type, blueprint_type.name) or "Uncategorized"
        bucket = buckets.setdefault(category_name, {"category_name": category_name, "total_count": 0, "items": []})
        bucket["total_count"] += 1
        if len(bucket["items"]) < limit_per_category:
            bucket["items"].append({
                "blueprint_type_id": activity.blueprint_type_id,
                "blueprint_type_name": blueprint_type.name,
                "product_type_id": activity.product_type_id,
                "product_type_name": product_type.name if product_type else None,
                "product_group_name": group_name,
                "product_category_name": product_category_name,
                "inventory_family": family,
                "inventory_subtype": inventory_subtype(product_type, blueprint_type.name) or group_name,
                "capital_construction_related": is_capital_chain,
            })
        seen_missing.add(activity.blueprint_type_id)
    categories = sorted(buckets.values(), key=lambda row: (0 if row["category_name"] == "Capital construction" else 1, -row["total_count"], row["category_name"]))
    return {
        "total_missing": sum(category["total_count"] for category in categories),
        "owned_bpos": len(owned_bpo_type_ids),
        "categories": categories,
    }

@router.post("/blueprints")
def create_blueprint(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    for field in ["ownership_entity_id", "blueprint_type_id"]:
        if payload.get(field) in (None, ""):
            raise HTTPException(status_code=400, detail=f"{field} is required")
    get_or_404(db, OwnershipEntity, int(payload["ownership_entity_id"]))
    blueprint_type_id = int(payload["blueprint_type_id"])
    if db.get(EveType, blueprint_type_id) is None:
        raise HTTPException(status_code=400, detail="blueprint_type_id must reference an existing EVE type")
    product_type_id = payload.get("product_type_id")
    if product_type_id and db.get(EveType, int(product_type_id)) is None:
        raise HTTPException(status_code=400, detail="product_type_id must reference an existing EVE type")
    blueprint = Blueprint(
        ownership_entity_id=int(payload["ownership_entity_id"]),
        blueprint_type_id=blueprint_type_id,
        product_type_id=product_type_id,
        material_efficiency=int(payload.get("material_efficiency", 0)),
        time_efficiency=int(payload.get("time_efficiency", 0)),
        runs_remaining=payload.get("runs_remaining"),
        is_copy=bool(payload.get("is_copy", False)),
        location_id=payload.get("location_id"),
        source=AssetSource(payload.get("source", AssetSource.MANUAL.value)),
    )
    db.add(blueprint)
    db.commit()
    db.refresh(blueprint)
    return row_dict(blueprint)


@router.get("/industry-activities")
def list_industry_activities(
    q: str | None = Query(default=None),
    activity_kind: ActivityKind | None = Query(default=None),
    limit: int = Query(default=250, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    include_inputs: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(IndustryActivity).options(selectinload(IndustryActivity.inputs)).order_by(IndustryActivity.id)
    if activity_kind is not None:
        query = query.where(IndustryActivity.activity_kind == activity_kind)
    if q:
        matching_type_ids = select(EveType.type_id).where(EveType.name.ilike(f"%{q.strip()}%"))
        query = query.where(
            IndustryActivity.blueprint_type_id.in_(matching_type_ids)
            | IndustryActivity.product_type_id.in_(matching_type_ids)
        )
    activities = db.scalars(query.offset(offset).limit(limit)).all()

    type_ids: set[int] = set()
    for activity in activities:
        type_ids.add(activity.blueprint_type_id)
        if activity.product_type_id:
            type_ids.add(activity.product_type_id)
        if include_inputs:
            type_ids.update(input_row.input_type_id for input_row in activity.inputs)
    type_names = {
        item_type.type_id: item_type.name
        for item_type in db.scalars(select(EveType).where(EveType.type_id.in_(type_ids))).all()
    } if type_ids else {}

    results = []
    for activity in activities:
        inputs = []
        if include_inputs:
            inputs = [
                row_dict(input_row, {"input_type_name": type_names.get(input_row.input_type_id)})
                for input_row in activity.inputs
            ]
        results.append(
            row_dict(
                activity,
                {
                    "blueprint_type_name": type_names.get(activity.blueprint_type_id),
                    "product_type_name": type_names.get(activity.product_type_id) if activity.product_type_id else None,
                    "inputs": inputs,
                },
            )
        )
    return results


@router.post("/industry-activities")
def create_industry_activity(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    for field in ["blueprint_type_id", "activity_kind"]:
        if payload.get(field) in (None, ""):
            raise HTTPException(status_code=400, detail=f"{field} is required")
    activity = IndustryActivity(
        blueprint_type_id=int(payload["blueprint_type_id"]),
        activity_kind=ActivityKind(payload["activity_kind"]),
        product_type_id=payload.get("product_type_id"),
        product_quantity=int(payload.get("product_quantity", 1)),
        time_seconds=payload.get("time_seconds"),
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return row_dict(activity)


@router.post("/industry-activity-inputs")
def create_industry_activity_input(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    for field in ["activity_id", "input_type_id", "quantity"]:
        if payload.get(field) in (None, ""):
            raise HTTPException(status_code=400, detail=f"{field} is required")
    activity_input = IndustryActivityInput(
        activity_id=int(payload["activity_id"]),
        input_type_id=int(payload["input_type_id"]),
        quantity=int(payload["quantity"]),
        consume_type=payload.get("consume_type", "consumed"),
    )
    db.add(activity_input)
    db.commit()
    db.refresh(activity_input)
    return row_dict(activity_input)


@router.post("/dev/seed")
def seed_dev_data(db: Session = Depends(get_db)) -> dict[str, Any]:
    if db.scalar(select(func.count()).select_from(EveType)):
        return {"status": "already_seeded"}

    user = User(email="quartermaster@example.local", display_name="Quartermaster", role="admin")
    db.add(user)
    db.add_all([
        EveCategory(category_id=4, name="Material"),
        EveCategory(category_id=6, name="Ship"),
        EveCategory(category_id=9, name="Blueprint"),
        EveGroup(group_id=18, category_id=4, name="Mineral"),
        EveGroup(group_id=28, category_id=6, name="Industrial"),
        EveGroup(group_id=1044, category_id=9, name="Mining Barge Blueprint"),
        EveType(type_id=34, group_id=18, name="Tritanium", volume=0.01, published=True),
        EveType(type_id=35, group_id=18, name="Pyerite", volume=0.01, published=True),
        EveType(type_id=36, group_id=18, name="Mexallon", volume=0.01, published=True),
        EveType(type_id=17478, group_id=28, name="Retriever", volume=150000.0, packaged_volume=3750.0, published=True),
        EveType(type_id=17479, group_id=1044, name="Retriever Blueprint", volume=0.01, published=True),
    ])
    db.flush()

    alliance = EveAlliance(alliance_id=99000001, name="Example Alliance", ticker="EXA")
    db.add(alliance)
    db.flush()
    corp = EveCorporation(corporation_id=98000001, name="Example Industrial Corp", ticker="EIC", alliance_id=alliance.id)
    db.add(corp)
    db.flush()
    character = EveCharacter(character_id=90000001, name="Main Industrialist", corporation_id=corp.id, alliance_id=alliance.id, owner_user_id=user.id)
    db.add(character)
    db.flush()

    char_owner = OwnershipEntity(owner_kind=OwnerKind.CHARACTER, character_id=character.id, display_name="Main Industrialist")
    corp_owner = OwnershipEntity(owner_kind=OwnerKind.CORPORATION, corporation_id=corp.id, display_name="Example Industrial Corp")
    db.add_all([char_owner, corp_owner])
    db.flush()

    home = Location(location_kind=LocationKind.STRUCTURE, name="Home Industry Structure", source=AssetSource.MANUAL, notes="Replace with your real structure after ESI auth.")
    jita = Location(location_kind=LocationKind.STATION, eve_location_id=60003760, name="Jita IV - Moon 4 - Caldari Navy Assembly Plant", source=AssetSource.SDE)
    db.add_all([home, jita])
    db.flush()

    db.add_all([
        Asset(ownership_entity_id=char_owner.id, type_id=34, quantity=250000, location_id=home.id, location_flag="Hangar", source=AssetSource.MANUAL),
        Asset(ownership_entity_id=char_owner.id, type_id=35, quantity=60000, location_id=home.id, location_flag="Hangar", source=AssetSource.MANUAL),
        Asset(ownership_entity_id=corp_owner.id, type_id=17478, quantity=3, location_id=home.id, location_flag="CorpSAG1", is_singleton=True, source=AssetSource.MANUAL),
    ])
    blueprint = Blueprint(ownership_entity_id=char_owner.id, blueprint_type_id=17479, product_type_id=17478, material_efficiency=10, time_efficiency=20, is_copy=False, location_id=home.id, source=AssetSource.MANUAL)
    db.add(blueprint)
    activity = IndustryActivity(blueprint_type_id=17479, activity_kind=ActivityKind.MANUFACTURING, product_type_id=17478, product_quantity=1, time_seconds=7200)
    db.add(activity)
    db.flush()
    db.add_all([
        IndustryActivityInput(activity_id=activity.id, input_type_id=34, quantity=200000),
        IndustryActivityInput(activity_id=activity.id, input_type_id=35, quantity=50000),
        IndustryActivityInput(activity_id=activity.id, input_type_id=36, quantity=15000),
        ProcurementSource(type_id=34, source_type=ProcurementKind.STOCKPILE, preferred_location_id=home.id, priority=1, notes="Use local stock first."),
        ProcurementSource(type_id=35, source_type=ProcurementKind.BUY, preferred_location_id=jita.id, estimated_unit_price=13.40, priority=2),
    ])
    db.commit()
    return {"status": "seeded"}
