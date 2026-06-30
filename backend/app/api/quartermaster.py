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
from app.services.permissions import ROLE_RANK, role_rank

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


def can_view_owner_records(owner: OwnershipEntity | None, current_user: User, db: Session) -> bool:
    if role_rank(current_user, db) >= ROLE_RANK["officer"]:
        return True
    if owner is None or owner.character is None:
        return False
    character = owner.character
    if character.owner_user_id == current_user.id:
        return True
    return bool(character.public_assets_visible and not character.sync_opt_out)


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


@router.get("/assets")
def list_assets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    assets = db.scalars(
        select(Asset)
        .options(
            selectinload(Asset.ownership_entity).selectinload(OwnershipEntity.character),
            selectinload(Asset.item_type),
            selectinload(Asset.location),
            selectinload(Asset.parent_asset).selectinload(Asset.item_type),
        )
        .order_by(Asset.updated_at.desc(), Asset.id.desc())
    ).all()
    results = []
    for asset in assets:
        if not can_view_owner_records(asset.ownership_entity, current_user, db):
            continue
        parent_type_name = asset.parent_asset.item_type.name if asset.parent_asset and asset.parent_asset.item_type else None
        if asset.location:
            location_name = asset.location.name
        elif asset.parent_asset:
            location_name = f"Inside {parent_type_name or 'item'} {asset.parent_asset.eve_item_id}"
        else:
            location_name = None
        results.append(
            row_dict(
                asset,
                {
                    "owner_name": asset.ownership_entity.display_name if asset.ownership_entity else None,
                    "owner_kind": asset.ownership_entity.owner_kind.value if asset.ownership_entity else None,
                    "type_name": asset.item_type.name if asset.item_type else None,
                    "location_name": location_name,
                    "parent_asset_item_id": asset.parent_asset.eve_item_id if asset.parent_asset else None,
                    "parent_asset_type_name": parent_type_name,
                },
            )
        )
    return results


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


@router.get("/blueprints")
def list_blueprints(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    blueprints = db.scalars(
        select(Blueprint)
        .options(
            selectinload(Blueprint.ownership_entity).selectinload(OwnershipEntity.character),
            selectinload(Blueprint.blueprint_type),
            selectinload(Blueprint.product_type),
            selectinload(Blueprint.location),
        )
        .order_by(Blueprint.id.desc())
    ).all()
    return [
        row_dict(
            blueprint,
            {
                "owner_name": blueprint.ownership_entity.display_name if blueprint.ownership_entity else None,
                "blueprint_type_name": blueprint.blueprint_type.name if blueprint.blueprint_type else None,
                "product_type_name": blueprint.product_type.name if blueprint.product_type else None,
                "location_name": blueprint.location.name if blueprint.location else None,
            },
        )
        for blueprint in blueprints
        if can_view_owner_records(blueprint.ownership_entity, current_user, db)
    ]


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








