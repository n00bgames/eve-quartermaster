from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import EveGroup, EveStation, EveSystem, EveType, Location, Note, NoteItem, User
from app.models.enums import AssetSource, LocationKind
from app.services.asset_visibility import visible_asset_rows
from app.services.item_lines import parse_item_lines
from app.services.market import appraise_market, list_market_hubs
from app.services.notes import (
    COMPLETED_STATUSES,
    apply_asset_scope,
    asset_freshness,
    clean_item_status,
    clean_note_type,
    clean_quantity,
    clean_tags,
    clean_title,
    get_owned_note,
    item_asset_context,
    owner_options,
    resolve_item_name,
    serialize_note,
    type_candidate,
)
from app.services.permissions import can_view_section

router = APIRouter(prefix="/notes", tags=["notes"])


def require_notes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not can_view_section(current_user, "notes", db):
        raise HTTPException(status_code=403, detail="Notes & Lists access is required")
    return current_user


def note_query():
    return select(Note).options(
        selectinload(Note.items).selectinload(NoteItem.item_type).selectinload(EveType.group).selectinload(EveGroup.category),
        selectinload(Note.destination_system),
        selectinload(Note.destination_location),
    )


def parse_owner_ids(value: str | None) -> set[int]:
    if not value:
        return set()
    try:
        return {int(entry) for entry in value.split(",") if entry.strip()}
    except ValueError:
        raise HTTPException(status_code=400, detail="owner_ids must be comma-separated integers") from None


def detail_payload(
    note: Note,
    user: User,
    db: Session,
    asset_scope: str = "all",
    owner_ids: set[int] | None = None,
) -> dict[str, Any]:
    if asset_scope not in {"all", "character", "corporation"}:
        raise HTTPException(status_code=400, detail="asset_scope must be all, character, or corporation")
    visible = visible_asset_rows(user, db)
    scoped = apply_asset_scope(visible, asset_scope, owner_ids or set())
    payload = serialize_note(note, scoped, include_items=True, db=db)
    payload["asset_scope"] = {
        "selected": asset_scope,
        "selected_owner_ids": sorted(owner_ids or set()),
        "owners": owner_options(visible),
        "freshness": asset_freshness(scoped),
    }
    return payload


def reload_note(db: Session, note_id: int, user: User, include_deleted: bool = False) -> Note:
    db.expire_all()
    return get_owned_note(db, note_id, user, include_deleted)


def update_destination(note: Note, payload: dict[str, Any], db: Session) -> None:
    if "destination_system_id" in payload:
        raw_system_id = payload.get("destination_system_id")
        note.destination_system_id = int(raw_system_id) if raw_system_id not in (None, "") else None
        if note.destination_system_id is not None and db.get(EveSystem, note.destination_system_id) is None:
            raise HTTPException(status_code=400, detail="Destination system is not in the imported SDE")
    if "destination_location_id" in payload:
        raw_location_id = payload.get("destination_location_id")
        note.destination_location_id = int(raw_location_id) if raw_location_id not in (None, "") else None
        if note.destination_location_id is not None and db.get(Location, note.destination_location_id) is None:
            raise HTTPException(status_code=400, detail="Destination location was not found")
    if payload.get("destination_eve_location_id"):
        eve_location_id = int(payload["destination_eve_location_id"])
        location = db.scalar(select(Location).where(Location.eve_location_id == eve_location_id).limit(1))
        if location is None:
            station = db.get(EveStation, eve_location_id)
            if station is None:
                raise HTTPException(status_code=400, detail="That station is not in the imported SDE")
            location = Location(
                location_kind=LocationKind.STATION,
                eve_location_id=station.station_id,
                name=station.name or f"Station {station.station_id}",
                system_id=station.system_id,
                source=AssetSource.SDE,
            )
            db.add(location)
            db.flush()
        note.destination_location_id = location.id
        note.destination_system_id = location.system_id
    if note.destination_location_id:
        location = db.get(Location, note.destination_location_id)
        if location and note.destination_system_id and location.system_id and location.system_id != note.destination_system_id:
            note.destination_location_id = None


@router.get("")
def list_notes(
    search: str | None = None,
    note_type: str | None = Query(None, pattern="^(freeform|item_list)$"),
    tag: str | None = None,
    include_deleted: bool = False,
    user: User = Depends(require_notes),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = note_query().where(Note.owner_user_id == user.id)
    query = query.where(Note.deleted_at.is_not(None) if include_deleted else Note.deleted_at.is_(None))
    if note_type:
        query = query.where(Note.note_type == note_type)
    rows = list(db.scalars(query.order_by(Note.updated_at.desc(), Note.id.desc())).all())
    if search:
        needle = search.casefold()
        rows = [row for row in rows if needle in row.title.casefold() or needle in (row.body or "").casefold()]
    if tag:
        needle = tag.casefold()
        rows = [row for row in rows if any(needle == str(value).casefold() for value in (row.tags or []))]
    return [serialize_note(row) for row in rows]


@router.post("")
def create_note(payload: dict[str, Any], user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = Note(
        owner_user_id=user.id,
        note_type=clean_note_type(payload.get("note_type")),
        title=clean_title(payload.get("title")),
        body=str(payload.get("body") or "") or None,
        tags=clean_tags(payload.get("tags")),
        source_market_hub_key=str(payload.get("source_market_hub_key") or "") or None,
    )
    update_destination(note, payload, db)
    db.add(note)
    db.commit()
    return detail_payload(reload_note(db, note.id, user), user, db)


@router.get("/search/types")
def search_types(
    q: str = Query(..., min_length=2),
    limit: int = Query(12, ge=1, le=30),
    _: User = Depends(require_notes),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(EveType)
        .where(EveType.name.ilike(f"%{q.strip()}%"))
        .options(selectinload(EveType.group).selectinload(EveGroup.category))
        .order_by(EveType.published.desc(), EveType.name)
        .limit(limit)
    ).all()
    return [type_candidate(row) for row in rows]


@router.get("/search/systems")
def search_systems(
    q: str = Query(..., min_length=2),
    limit: int = Query(12, ge=1, le=30),
    _: User = Depends(require_notes),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = db.scalars(select(EveSystem).where(EveSystem.name.ilike(f"%{q.strip()}%")).order_by(EveSystem.name).limit(limit)).all()
    return [
        {"system_id": row.system_id, "name": row.name, "security_status": row.security_status, "security_class": row.security_class}
        for row in rows
    ]


@router.get("/search/locations")
def search_locations(
    system_id: int,
    _: User = Depends(require_notes),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    known = list(db.scalars(select(Location).where(Location.system_id == system_id).order_by(Location.name)).all())
    known_by_eve_id = {row.eve_location_id: row for row in known if row.eve_location_id}
    rows = [
        {
            "id": row.id,
            "eve_location_id": row.eve_location_id,
            "name": row.name,
            "kind": row.location_kind.value,
            "source": row.source.value,
        }
        for row in known
    ]
    for station in db.scalars(select(EveStation).where(EveStation.system_id == system_id).order_by(EveStation.name, EveStation.station_id)).all():
        if station.station_id not in known_by_eve_id:
            rows.append({"id": None, "eve_location_id": station.station_id, "name": station.name or f"Station {station.station_id}", "kind": "station", "source": "sde"})
    return rows


@router.get("/market-hubs")
def note_market_hubs(_: User = Depends(require_notes), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return list_market_hubs(db)


@router.get("/{note_id}")
def get_note(
    note_id: int,
    asset_scope: str = "all",
    owner_ids: str | None = None,
    user: User = Depends(require_notes),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return detail_payload(get_owned_note(db, note_id, user), user, db, asset_scope, parse_owner_ids(owner_ids))


@router.patch("/{note_id}")
def update_note(note_id: int, payload: dict[str, Any], user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    if "title" in payload:
        note.title = clean_title(payload.get("title"))
    if "note_type" in payload:
        note.note_type = clean_note_type(payload.get("note_type"))
    if "body" in payload:
        note.body = str(payload.get("body") or "") or None
    if "tags" in payload:
        note.tags = clean_tags(payload.get("tags"))
    if "source_market_hub_key" in payload:
        note.source_market_hub_key = str(payload.get("source_market_hub_key") or "") or None
    update_destination(note, payload, db)
    db.commit()
    return detail_payload(reload_note(db, note.id, user), user, db)


@router.delete("/{note_id}")
def delete_note(note_id: int, user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    note.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "deleted", "id": note.id}


@router.post("/{note_id}/restore")
def restore_note(note_id: int, user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user, include_deleted=True)
    note.deleted_at = None
    db.commit()
    return detail_payload(reload_note(db, note.id, user), user, db)


@router.post("/{note_id}/duplicate")
def duplicate_note(note_id: int, user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    source = get_owned_note(db, note_id, user)
    clone = Note(
        owner_user_id=user.id,
        note_type=source.note_type,
        title=clean_title(f"{source.title} copy"),
        body=source.body,
        tags=list(source.tags or []),
        destination_system_id=source.destination_system_id,
        destination_location_id=source.destination_location_id,
        source_market_hub_key=source.source_market_hub_key,
    )
    db.add(clone)
    db.flush()
    for item in source.items:
        db.add(NoteItem(
            note_id=clone.id,
            type_id=item.type_id,
            original_text=item.original_text,
            canonical_name=item.canonical_name,
            requested_quantity=item.requested_quantity,
            status=item.status,
            sort_order=item.sort_order,
        ))
    db.commit()
    return detail_payload(reload_note(db, clone.id, user), user, db)


@router.post("/{note_id}/items/parse")
def import_items(note_id: int, payload: dict[str, Any], user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    if note.note_type != "item_list":
        raise HTTPException(status_code=400, detail="Items can only be added to an item list")
    rows, duplicates = parse_item_lines(str(payload.get("text") or ""), bool(payload.get("merge_duplicates", False)))
    if not rows:
        raise HTTPException(status_code=400, detail="Paste at least one item line")
    next_order = (db.scalar(select(func.max(NoteItem.sort_order)).where(NoteItem.note_id == note.id)) or -1) + 1
    imported = []
    for offset, row in enumerate(rows):
        item_type, candidates = resolve_item_name(db, row.name)
        item = NoteItem(
            note_id=note.id,
            type_id=item_type.type_id if item_type else None,
            original_text=row.original_text,
            canonical_name=item_type.name if item_type else row.name,
            requested_quantity=row.quantity,
            status="needed",
            sort_order=next_order + offset,
        )
        db.add(item)
        imported.append({"line_number": row.line_number, "name": row.name, "resolved": item_type is not None, "candidates": candidates})
    db.commit()
    return {"duplicates": duplicates, "imported": imported, "note": detail_payload(reload_note(db, note.id, user), user, db)}


@router.post("/{note_id}/items")
def create_item(note_id: int, payload: dict[str, Any], user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    name = str(payload.get("name") or "").strip()
    item_type = db.get(EveType, int(payload["type_id"])) if payload.get("type_id") else None
    if item_type is None and name:
        item_type, _ = resolve_item_name(db, name)
    if not name and item_type is None:
        raise HTTPException(status_code=400, detail="Item name is required")
    order = (db.scalar(select(func.max(NoteItem.sort_order)).where(NoteItem.note_id == note.id)) or -1) + 1
    item = NoteItem(
        note_id=note.id,
        type_id=item_type.type_id if item_type else None,
        original_text=name or item_type.name,
        canonical_name=item_type.name if item_type else name,
        requested_quantity=clean_quantity(payload.get("requested_quantity", 1)),
        status=clean_item_status(payload.get("status")),
        sort_order=order,
    )
    db.add(item)
    db.commit()
    return detail_payload(reload_note(db, note.id, user), user, db)


@router.patch("/{note_id}/items/{item_id}")
def update_item(note_id: int, item_id: int, payload: dict[str, Any], user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    item = next((row for row in note.items if row.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if "type_id" in payload:
        item_type = db.get(EveType, int(payload["type_id"])) if payload.get("type_id") else None
        if payload.get("type_id") and item_type is None:
            raise HTTPException(status_code=400, detail="EVE type was not found")
        item.type_id = item_type.type_id if item_type else None
        if item_type:
            item.canonical_name = item_type.name
    if "requested_quantity" in payload:
        item.requested_quantity = clean_quantity(payload.get("requested_quantity"))
    if "status" in payload:
        item.status = clean_item_status(payload.get("status"))
    if "name" in payload and not item.type_id:
        item.canonical_name = str(payload.get("name") or "").strip() or item.canonical_name
    db.commit()
    return detail_payload(reload_note(db, note.id, user), user, db)


@router.delete("/{note_id}/items/{item_id}")
def delete_item(note_id: int, item_id: int, user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    item = next((row for row in note.items if row.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return detail_payload(reload_note(db, note.id, user), user, db)


@router.post("/{note_id}/items/bulk-status")
def bulk_status(note_id: int, payload: dict[str, Any], user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    ids = {int(value) for value in payload.get("item_ids", [])}
    status = clean_item_status(payload.get("status"))
    for item in note.items:
        if item.id in ids:
            item.status = status
    db.commit()
    return detail_payload(reload_note(db, note.id, user), user, db)


@router.post("/{note_id}/items/reorder")
def reorder_items(note_id: int, payload: dict[str, Any], user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    ids = [int(value) for value in payload.get("item_ids", [])]
    existing = {item.id: item for item in note.items}
    if set(ids) != set(existing):
        raise HTTPException(status_code=400, detail="Reorder must include every item exactly once")
    for index, item_id in enumerate(ids):
        existing[item_id].sort_order = index
    db.commit()
    return detail_payload(reload_note(db, note.id, user), user, db)


@router.delete("/{note_id}/items/completed")
def clear_completed(note_id: int, user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    for item in list(note.items):
        if item.status in COMPLETED_STATUSES:
            db.delete(item)
    db.commit()
    return detail_payload(reload_note(db, note.id, user), user, db)


@router.post("/{note_id}/price")
async def price_items(note_id: int, payload: dict[str, Any], user: User = Depends(require_notes), db: Session = Depends(get_db)) -> dict[str, Any]:
    note = get_owned_note(db, note_id, user)
    ids = {int(value) for value in payload.get("item_ids", [])}
    quantity_mode = str(payload.get("quantity_mode") or "remaining")
    if quantity_mode not in {"remaining", "requested"}:
        raise HTTPException(status_code=400, detail="quantity_mode must be remaining or requested")
    scoped = apply_asset_scope(
        visible_asset_rows(user, db),
        str(payload.get("asset_scope") or "all"),
        {int(value) for value in payload.get("owner_ids", [])},
    )
    lines = []
    for item in note.items:
        if item.id not in ids or item.type_id is None:
            continue
        quantity = item.requested_quantity
        if quantity_mode == "remaining":
            quantity = item_asset_context(note, item, scoped)["remaining"]
        if quantity > 0:
            lines.append(f"{item.item_type.name} x{quantity}")
    if not lines:
        raise HTTPException(status_code=400, detail="Select at least one resolved item with quantity remaining")
    hubs = payload.get("hubs")
    result = await appraise_market(db, "\n".join(lines), hubs if isinstance(hubs, list) else None)
    result["priced_at"] = datetime.now(timezone.utc).isoformat()
    result["quantity_mode"] = quantity_mode
    return result