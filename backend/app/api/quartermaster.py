from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
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
    User,
)
from app.models.enums import ActivityKind, AssetSource, LocationKind, OwnerKind, ProcurementKind
from app.services.asset_visibility import can_view_owner_records, visible_asset_rows
from app.services.blueprint_hover import active_blueprint_uses, blueprint_active_use
from app.services.corporation_metadata import (
    asset_flag_name,
    asset_location_name,
    corporation_hangar_names,
)

router = APIRouter(prefix="/quartermaster", tags=["quartermaster"], dependencies=[Depends(get_current_user)])


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

@router.get("/blueprints")
def list_blueprints(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    capital_blueprint_type_ids = blueprint_type_ids_for_capital_construction(db)
    blueprints = db.scalars(
        select(Blueprint)
        .options(
            selectinload(Blueprint.ownership_entity).selectinload(OwnershipEntity.character),
            selectinload(Blueprint.blueprint_type),
            selectinload(Blueprint.product_type).selectinload(EveType.group).selectinload(EveGroup.category),
            selectinload(Blueprint.location),
            selectinload(Blueprint.asset),
        )
        .order_by(Blueprint.id.desc())
    ).all()
    product_fallbacks = blueprint_product_type_fallbacks(db, {blueprint.blueprint_type_id for blueprint in blueprints})
    blueprint_uses = active_blueprint_uses(db, blueprints)
    results = []
    for blueprint in blueprints:
        if not can_view_owner_records(blueprint.ownership_entity, current_user, db):
            continue
        product_type = blueprint.product_type or product_fallbacks.get(blueprint.blueprint_type_id)
        family = item_family(product_type, blueprint.blueprint_type.name if blueprint.blueprint_type else None)
        results.append(
            row_dict(
                blueprint,
                {
                    "owner_name": blueprint.ownership_entity.display_name if blueprint.ownership_entity else None,
                    "blueprint_type_name": blueprint.blueprint_type.name if blueprint.blueprint_type else None,
                    "product_type_id": blueprint.product_type_id or (product_type.type_id if product_type else None),
                    "product_type_name": product_type.name if product_type else None,
                    "location_name": blueprint.location.name if blueprint.location else None,
                    "location_id": blueprint.location.eve_location_id if blueprint.location else None,
                    "active_use": blueprint_active_use(blueprint, blueprint_uses),
                    "inventory_family": family,
                    "inventory_subtype": inventory_subtype(product_type, blueprint.blueprint_type.name if blueprint.blueprint_type else None),
                    "capital_construction_related": blueprint.blueprint_type_id in capital_blueprint_type_ids and family not in {"reactions", "ram"},
                    **type_metadata("blueprint", blueprint.blueprint_type),
                    **type_metadata("product", product_type),
                },
            )
        )
    return results


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









