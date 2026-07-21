from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, EveGroup, EveType, Note, NoteItem, User
from app.models.enums import OwnerKind
from app.services.asset_visibility import visible_asset_rows

NOTE_TYPES = {"freeform", "item_list"}
ITEM_STATUSES = {"needed", "planned", "purchased", "in_transit", "delivered", "skipped"}
COMPLETED_STATUSES = {"delivered", "skipped"}


def clean_note_type(value: Any) -> str:
    note_type = str(value or "freeform").strip().lower()
    if note_type not in NOTE_TYPES:
        raise HTTPException(status_code=400, detail="note_type must be freeform or item_list")
    return note_type


def clean_item_status(value: Any) -> str:
    status = str(value or "needed").strip().lower()
    if status not in ITEM_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid item status")
    return status


def clean_quantity(value: Any) -> int:
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Quantity must be a whole number") from None
    if quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")
    return quantity


def clean_title(value: Any) -> str:
    title = re.sub(r"\s+", " ", str(value or "").strip())
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    if len(title) > 255:
        raise HTTPException(status_code=400, detail="Title must be 255 characters or fewer")
    return title


def clean_tags(value: Any) -> list[str]:
    raw = value if isinstance(value, list) else str(value or "").split(",")
    tags: list[str] = []
    for entry in raw:
        tag = re.sub(r"\s+", " ", str(entry).strip())
        if tag and tag.casefold() not in {item.casefold() for item in tags}:
            tags.append(tag[:60])
    return tags[:20]


def get_owned_note(db: Session, note_id: int, user: User, include_deleted: bool = False) -> Note:
    query = (
        select(Note)
        .where(Note.id == note_id, Note.owner_user_id == user.id)
        .options(
            selectinload(Note.items).selectinload(NoteItem.item_type).selectinload(EveType.group).selectinload(EveGroup.category),
            selectinload(Note.destination_system),
            selectinload(Note.destination_location),
        )
    )
    if not include_deleted:
        query = query.where(Note.deleted_at.is_(None))
    note = db.scalar(query)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


def type_candidate(item_type: EveType) -> dict[str, Any]:
    group = item_type.group
    return {
        "type_id": item_type.type_id,
        "name": item_type.name,
        "group_name": group.name if group else None,
        "category_name": group.category.name if group and group.category else None,
        "volume": item_type.volume,
        "published": item_type.published,
    }


def type_candidates(db: Session, name: str, limit: int = 8) -> list[EveType]:
    normalized = re.sub(r"\s+", " ", name.strip())
    if not normalized:
        return []
    options = selectinload(EveType.group).selectinload(EveGroup.category)
    exact = list(db.scalars(select(EveType).where(func.lower(EveType.name) == normalized.casefold()).options(options).limit(limit)).all())
    if exact:
        return exact
    return list(
        db.scalars(
            select(EveType)
            .where(EveType.name.ilike(f"%{normalized}%"))
            .options(options)
            .order_by(EveType.published.desc(), EveType.name)
            .limit(limit)
        ).all()
    )


def resolve_item_name(db: Session, name: str) -> tuple[EveType | None, list[dict[str, Any]]]:
    candidates = type_candidates(db, name)
    exact = [item for item in candidates if item.name.casefold() == name.strip().casefold()]
    if len(exact) == 1:
        return exact[0], [type_candidate(item) for item in candidates]
    if not exact and len(candidates) == 1:
        return candidates[0], [type_candidate(candidates[0])]
    return None, [type_candidate(item) for item in candidates]


def effective_asset_location(asset: Asset):
    return asset.location or (asset.parent_asset.location if asset.parent_asset else None)


def owner_options(assets: list[Asset]) -> list[dict[str, Any]]:
    owners: dict[int, dict[str, Any]] = {}
    for asset in assets:
        owner = asset.ownership_entity
        if owner is None:
            continue
        owners[owner.id] = {
            "id": owner.id,
            "name": owner.display_name,
            "kind": owner.owner_kind.value,
        }
    return sorted(owners.values(), key=lambda row: str(row["name"]).casefold())


def apply_asset_scope(assets: list[Asset], scope: str, owner_ids: set[int]) -> list[Asset]:
    scoped = assets
    if scope in {OwnerKind.CHARACTER.value, OwnerKind.CORPORATION.value}:
        scoped = [asset for asset in scoped if asset.ownership_entity and asset.ownership_entity.owner_kind.value == scope]
    if owner_ids:
        scoped = [asset for asset in scoped if asset.ownership_entity_id in owner_ids]
    return scoped


def asset_freshness(assets: list[Asset]) -> dict[str, Any]:
    synced = [asset.last_synced_at for asset in assets if asset.last_synced_at]
    latest = max(synced) if synced else None
    oldest = min(synced) if synced else None
    stale = latest is None or (datetime.now(timezone.utc) - latest).total_seconds() > 86400
    kinds = sorted({asset.ownership_entity.owner_kind.value for asset in assets if asset.ownership_entity})
    return {
        "available": bool(assets),
        "latest_synced_at": latest.isoformat() if latest else None,
        "oldest_synced_at": oldest.isoformat() if oldest else None,
        "stale": stale,
        "scope_kinds": kinds,
        "asset_stacks": len(assets),
    }


def item_asset_context(note: Note, item: NoteItem, assets: list[Asset]) -> dict[str, Any]:
    if item.type_id is None:
        return {"at_destination": 0, "elsewhere": 0, "remaining": item.requested_quantity, "locations": []}
    matching = [asset for asset in assets if asset.type_id == item.type_id]
    at_destination: list[Asset] = []
    elsewhere: list[Asset] = []
    for asset in matching:
        location = effective_asset_location(asset)
        is_destination = False
        if note.destination_location_id is not None:
            is_destination = bool(location and location.id == note.destination_location_id)
        elif note.destination_system_id is not None:
            is_destination = bool(location and location.system_id == note.destination_system_id)
        if is_destination:
            at_destination.append(asset)
        else:
            elsewhere.append(asset)
    destination_qty = sum(max(asset.quantity, 0) for asset in at_destination)
    elsewhere_qty = sum(max(asset.quantity, 0) for asset in elsewhere)
    grouped: dict[tuple[str, str, bool], int] = {}
    for asset in matching:
        location = effective_asset_location(asset)
        key = (
            asset.ownership_entity.display_name if asset.ownership_entity else "Unknown owner",
            location.name if location else "Unknown location",
            asset in at_destination,
        )
        grouped[key] = grouped.get(key, 0) + max(asset.quantity, 0)
    locations = [
        {"owner_name": key[0], "location_name": key[1], "at_destination": key[2], "quantity": quantity}
        for key, quantity in sorted(grouped.items(), key=lambda row: (not row[0][2], row[0][0].casefold(), row[0][1].casefold()))
    ]
    return {
        "at_destination": destination_qty,
        "elsewhere": elsewhere_qty,
        "remaining": max(item.requested_quantity - destination_qty, 0),
        "locations": locations,
    }


def serialize_item(note: Note, item: NoteItem, assets: list[Asset]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    item_type = item.item_type
    group = item_type.group if item_type else None
    return {
        "id": item.id,
        "type_id": item.type_id,
        "name": item_type.name if item_type else item.canonical_name,
        "original_text": item.original_text,
        "requested_quantity": item.requested_quantity,
        "status": item.status,
        "sort_order": item.sort_order,
        "completed": item.status in COMPLETED_STATUSES,
        "volume": item_type.volume if item_type else None,
        "group_name": group.name if group else None,
        "category_name": group.category.name if group and group.category else None,
        "asset_context": item_asset_context(note, item, assets),
        "candidates": candidates,
    }


def summary_for(note: Note, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "item_count": len(items),
        "requested_units": sum(int(item["requested_quantity"]) for item in items),
        "remaining_units": sum(int(item["asset_context"]["remaining"]) for item in items),
        "completed_items": sum(1 for item in items if item["completed"]),
        "unresolved_items": sum(1 for item in items if item["type_id"] is None),
    }


def serialize_note(note: Note, assets: list[Asset] | None = None, include_items: bool = False, db: Session | None = None) -> dict[str, Any]:
    payload = {
        "id": note.id,
        "note_type": note.note_type,
        "title": note.title,
        "body": note.body,
        "tags": note.tags or [],
        "destination_system_id": note.destination_system_id,
        "destination_system_name": note.destination_system.name if note.destination_system else None,
        "destination_security_status": note.destination_system.security_status if note.destination_system else None,
        "destination_location_id": note.destination_location_id,
        "destination_location_name": note.destination_location.name if note.destination_location else None,
        "source_market_hub_key": note.source_market_hub_key,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
        "deleted_at": note.deleted_at.isoformat() if note.deleted_at else None,
        "item_count": len(note.items),
        "item_names": [item.item_type.name if item.item_type else item.canonical_name for item in note.items],
    }
    if include_items:
        scoped_assets = assets or []
        item_payloads = [serialize_item(note, item, scoped_assets) for item in note.items]
        if db is not None:
            for row, item in zip(item_payloads, note.items):
                if item.type_id is None:
                    _, row["candidates"] = resolve_item_name(db, item.canonical_name)
        payload["items"] = item_payloads
        payload["summary"] = summary_for(note, item_payloads)
    return payload