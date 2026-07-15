from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import can_view_all_characters, get_current_user
from app.db.session import get_db
from app.models import CharacterFitting, CharacterFittingItem, CharacterJumpClone, EsiToken, EveCategory, EveCharacter, EveGroup, EveType, ImplantSet, ImplantSetImplant, JumpCloneImplant, User
from app.services.esi_client import EsiClient
from app.services.fitting_simulator import load_fitting_for_simulation, simulate_fitting
from app.services.permissions import can_view_section
from app.services.ship_capacity import resolved_ship_capacity

router = APIRouter(prefix="/fittings", tags=["fittings"])

FITTING_READ_SCOPE = "esi-fittings.read_fittings.v1"

FLAG_ORDER = [
    "LoSlot",
    "MedSlot",
    "HiSlot",
    "RigSlot",
    "SubSystemSlot",
    "ServiceSlot",
    "DroneBay",
    "FighterBay",
    "Cargo",
]
FLAG_LABELS = {
    "LoSlot": "Low slots",
    "MedSlot": "Medium slots",
    "HiSlot": "High slots",
    "RigSlot": "Rigs",
    "SubSystemSlot": "Subsystems",
    "ServiceSlot": "Services",
    "DroneBay": "Drones",
    "FighterBay": "Fighters",
    "Cargo": "Cargo",
}
SIMULATION_STATES = {"offline", "online", "active", "overheated"}
BAY_FLAGS = [
    "Cargo",
    "DroneBay",
    "FighterBay",
    "FuelBay",
    "FleetHangar",
    "ShipMaintenanceBay",
    "FleetMaintenanceBay",
    "InfrastructureBay",
    "OreHold",
    "MineralHold",
    "GasHold",
    "IceHold",
    "AmmoHold",
    "PlanetaryCommoditiesHold",
    "CommandCenterHold",
    "QuafeHold",
]
BAY_FLAG_LABELS = {
    "Cargo": "Cargo hold",
    "DroneBay": "Drone bay",
    "FighterBay": "Fighter hangar",
    "FuelBay": "Fuel bay",
    "FleetHangar": "Fleet hangar",
    "ShipMaintenanceBay": "Ship maintenance bay",
    "FleetMaintenanceBay": "Fleet maintenance bay",
    "InfrastructureBay": "Infrastructure bay",
    "OreHold": "Ore hold",
    "MineralHold": "Mineral hold",
    "GasHold": "Gas hold",
    "IceHold": "Ice hold",
    "AmmoHold": "Ammo hold",
    "PlanetaryCommoditiesHold": "PI hold",
    "CommandCenterHold": "Command center hold",
    "QuafeHold": "Quafe hold",
}

FITTED_SLOT_PREFIXES = {"HiSlot", "MedSlot", "LoSlot", "RigSlot", "SubSystemSlot", "ServiceSlot"}

DRAFT_FLAGS = [
    "HiSlot0",
    "HiSlot1",
    "HiSlot2",
    "HiSlot3",
    "HiSlot4",
    "HiSlot5",
    "HiSlot6",
    "HiSlot7",
    "MedSlot0",
    "MedSlot1",
    "MedSlot2",
    "MedSlot3",
    "MedSlot4",
    "MedSlot5",
    "MedSlot6",
    "MedSlot7",
    "LoSlot0",
    "LoSlot1",
    "LoSlot2",
    "LoSlot3",
    "LoSlot4",
    "LoSlot5",
    "LoSlot6",
    "LoSlot7",
    "RigSlot0",
    "RigSlot1",
    "RigSlot2",
    "SubSystemSlot0",
    "SubSystemSlot1",
    "SubSystemSlot2",
    "SubSystemSlot3",
    "ServiceSlot0",
    "ServiceSlot1",
    "ServiceSlot2",
    "ServiceSlot3",
    *BAY_FLAGS,
]

SECTION_SLOT_PREFIXES = ["LoSlot", "MedSlot", "HiSlot", "RigSlot", "SubSystemSlot", "ServiceSlot"]
QUANTITY_SUFFIX_RE = re.compile(r"\s+x\s*([0-9][0-9,]*)\s*$", re.IGNORECASE)
EFT_HEADER_RE = re.compile(r"^\[(?P<ship>[^,\]]+),\s*(?P<name>[^\]]+)\]\s*$")


def token_scopes(token: EsiToken) -> set[str]:
    return {scope.strip() for scope in (token.scopes or "").split() if scope.strip()}


def require_fittings_view(user: User, db: Session) -> None:
    if not can_view_section(user, "fittings", db):
        raise HTTPException(status_code=403, detail="Fittings permission is required")


def can_view_fitting(user: User, fitting: CharacterFitting, db: Session) -> bool:
    if can_view_all_characters(user, db):
        return True
    if fitting.character and fitting.character.owner_user_id == user.id:
        return True
    return fitting.is_shared


def can_manage_fitting(user: User, fitting: CharacterFitting, db: Session) -> bool:
    return can_view_all_characters(user, db) or bool(fitting.character and fitting.character.owner_user_id == user.id)


def require_manageable_draft(user: User, fitting: CharacterFitting, db: Session) -> None:
    if not can_manage_fitting(user, fitting, db):
        raise HTTPException(status_code=403, detail="You can only edit your own fittings")
    if not fitting.is_draft:
        raise HTTPException(status_code=400, detail="Create an editable draft before changing fitting items")


def slot_prefix(flag: str) -> str:
    normalized = flag.lower()
    for prefix in [*FLAG_ORDER, *BAY_FLAGS]:
        if flag.startswith(prefix):
            return prefix
    if "cargo" in normalized:
        return "Cargo"
    return "Other"


def normalize_flag(flag: str) -> str:
    candidate = str(flag or "").strip()
    if candidate in DRAFT_FLAGS:
        return candidate
    prefix = slot_prefix(candidate)
    if prefix in set(BAY_FLAGS):
        return prefix
    if prefix in FLAG_ORDER:
        match = re.search(r"(\d+)$", candidate)
        index = int(match.group(1)) if match else 0
        return f"{prefix}{index}"
    return "Cargo"


def get_type_with_group(db: Session, type_id: int) -> EveType | None:
    return db.scalar(
        select(EveType)
        .options(selectinload(EveType.group).selectinload(EveGroup.category))
        .where(EveType.type_id == type_id)
    )


def fitting_slot_index(flag: str) -> int:
    match = re.search(r"(\d+)$", str(flag or ""))
    return int(match.group(1)) if match else 0


def fitting_item_quantity_for_flag(flag: str, quantity: int) -> int:
    return 1 if slot_prefix(flag) in FITTED_SLOT_PREFIXES else max(1, int(quantity or 1))


def normalize_item_flag_for_type(item_type: EveType, requested_flag: str) -> str:
    flag = normalize_flag(requested_flag)
    requested_prefix = slot_prefix(flag)
    if requested_prefix in set(BAY_FLAGS):
        return flag
    if requested_prefix in FITTED_SLOT_PREFIXES:
        inferred_prefix = fitting_slot_prefix_for_type(item_type, requested_prefix)
        if inferred_prefix in FITTED_SLOT_PREFIXES:
            return normalize_flag(f"{inferred_prefix}{fitting_slot_index(flag)}")
    return flag


def next_free_fitting_flag(fitting: CharacterFitting, requested_flag: str, ignore_item_id: int | None = None) -> str:
    flag = normalize_flag(requested_flag)
    prefix = slot_prefix(flag)
    if prefix not in FITTED_SLOT_PREFIXES:
        return flag
    used = {item.flag for item in fitting.items if item.id != ignore_item_id and slot_prefix(item.flag) == prefix}
    if flag not in used:
        return flag
    for index in range(8):
        candidate = normalize_flag(f"{prefix}{index}")
        if candidate not in used:
            return candidate
    return flag


def normalize_draft_fitting_items(db: Session, fitting: CharacterFitting) -> bool:
    if not fitting.is_draft:
        return False
    changed = False
    for item in sorted(fitting.items, key=lambda row: (row.flag, row.id or 0)):
        item_type = get_type_with_group(db, item.type_id)
        if item_type is None:
            continue
        original_flag = item.flag
        original_quantity = item.quantity
        if slot_prefix(item.flag) in FITTED_SLOT_PREFIXES:
            corrected_flag = normalize_item_flag_for_type(item_type, item.flag)
            item.flag = next_free_fitting_flag(fitting, corrected_flag, item.id)
        item.quantity = fitting_item_quantity_for_flag(item.flag, item.quantity)
        changed = changed or item.flag != original_flag or item.quantity != original_quantity
    if changed:
        fitting.updated_at = datetime.now(timezone.utc)
    return changed


async def refresh_public_type_metadata(db: Session, type_ids: set[int], max_fetch: int = 80) -> int:
    client = EsiClient()
    refreshed = 0
    for type_id in sorted(type_ids):
        if refreshed >= max_fetch:
            break
        item_type = db.get(EveType, type_id)
        if item_type is None:
            item_type = EveType(type_id=type_id, name=f"Type {type_id}")
            db.add(item_type)
            db.flush()
        if item_type.group_id is not None and item_type.capacity is not None and item_type.volume is not None:
            continue
        try:
            payload = await client.get(f"/universe/types/{type_id}/", params={"language": "en"})
        except HTTPException:
            continue
        item_type.name = payload.get("name", item_type.name)
        item_type.description = payload.get("description")
        item_type.group_id = payload.get("group_id")
        item_type.volume = payload.get("volume")
        item_type.packaged_volume = payload.get("packaged_volume")
        item_type.capacity = payload.get("capacity")
        item_type.market_group_id = payload.get("market_group_id")
        item_type.published = bool(payload.get("published", True))
        refreshed += 1
    return refreshed

def clean_eft_name(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def find_type_by_name(db: Session, name: str) -> EveType | None:
    cleaned = clean_eft_name(name)
    if not cleaned:
        return None
    return db.scalar(
        select(EveType)
        .options(selectinload(EveType.group).selectinload(EveGroup.category))
        .where(func.lower(EveType.name) == cleaned.lower())
        .order_by(EveType.published.desc(), EveType.name)
        .limit(1)
    )


def parse_eft_item_line(line: str) -> tuple[str, str | None, int]:
    item_part, charge_part = (line.split(",", 1) + [""])[:2] if "," in line else (line, "")
    quantity = 1
    quantity_match = QUANTITY_SUFFIX_RE.search(item_part)
    if quantity_match:
        quantity = max(1, int(quantity_match.group(1).replace(",", "")))
        item_part = QUANTITY_SUFFIX_RE.sub("", item_part)
    elif not charge_part:
        quantity_match = QUANTITY_SUFFIX_RE.search(line)
        if quantity_match:
            quantity = max(1, int(quantity_match.group(1).replace(",", "")))
            item_part = QUANTITY_SUFFIX_RE.sub("", line)
    return clean_eft_name(item_part), clean_eft_name(charge_part) or None, quantity


def fitting_slot_prefix_for_type(row: EveType, section_prefix: str | None) -> str:
    group_name = (row.group.name if row.group else "") or ""
    category_name = (row.group.category.name if row.group and row.group.category else "") or ""
    haystack = f"{row.name} {group_name} {category_name}".lower()
    high_tokens = ["launcher", "turret", "smartbomb", "cynosural", "probe launcher", "cloak", "salvager", "tractor beam", "mining laser", "strip miner"]
    mid_tokens = ["shield", "propulsion", "afterburner", "microwarpdrive", "capacitor booster", "target painter", "stasis webifier", "warp disrupt", "warp scram", "tracking computer", "guidance computer", "sensor booster", "ecm", "scanner", "analyzer"]
    low_tokens = ["armor", "damage control", "ballistic control", "gyrostabilizer", "heat sink", "magnetic field", "reactor control", "power diagnostic", "capacitor power relay", "nanofiber", "inertia", "overdrive", "cargohold", "drone damage", "tracking enhancer", "weapon upgrade", "mining laser upgrade", "co-processor", "signal amplifier"]
    if category_name in {"Drone", "Fighter"} or "drone" in haystack:
        return "DroneBay" if category_name != "Fighter" and "fighter" not in haystack else "FighterBay"
    if category_name == "Charge":
        return "Cargo"
    if category_name == "Ship Modifications" or "rig" in group_name.lower():
        return "RigSlot"
    if category_name == "Module":
        if any(token in haystack for token in high_tokens):
            return "HiSlot"
        if any(token in haystack for token in low_tokens):
            return "LoSlot"
        if any(token in haystack for token in mid_tokens):
            return "MedSlot"
        if section_prefix in {"LoSlot", "MedSlot", "HiSlot", "SubSystemSlot", "ServiceSlot"}:
            return section_prefix
        return "HiSlot"
    return "Cargo"


def next_import_flag(prefix: str, counters: dict[str, int]) -> str:
    if prefix in set(BAY_FLAGS):
        return prefix
    index = counters.get(prefix, 0)
    counters[prefix] = index + 1
    return normalize_flag(f"{prefix}{index}")


def parse_eft_fit(db: Session, text: str) -> tuple[EveType, str, list[dict[str, Any]], list[str]]:
    raw_lines = [line.strip() for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    header_index = next((index for index, line in enumerate(raw_lines) if line.startswith("[") and line.endswith("]")), None)
    if header_index is None:
        raise HTTPException(status_code=400, detail="Paste an EFT-style fit that starts with [Ship, Fitting name]")
    header_match = EFT_HEADER_RE.match(raw_lines[header_index])
    if not header_match:
        raise HTTPException(status_code=400, detail="The fitting header should look like [Ship, Fitting name]")
    ship_name = clean_eft_name(header_match.group("ship"))
    fitting_name = clean_eft_name(header_match.group("name")) or f"Imported {ship_name}"
    ship_type = find_type_by_name(db, ship_name)
    if ship_type is None:
        raise HTTPException(status_code=400, detail=f"Ship type '{ship_name}' was not found in the SDE")

    sections: list[list[str]] = []
    current: list[str] = []
    for line in raw_lines[header_index + 1:]:
        if not line or line.startswith("#"):
            if current:
                sections.append(current)
                current = []
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        current.append(line)
    if current:
        sections.append(current)

    parsed_items: list[dict[str, Any]] = []
    warnings: list[str] = []
    counters: dict[str, int] = {}
    for section_index, section in enumerate(sections):
        section_prefix = SECTION_SLOT_PREFIXES[section_index] if section_index < len(SECTION_SLOT_PREFIXES) else None
        for line in section:
            item_name, charge_name, quantity = parse_eft_item_line(line)
            if not item_name:
                continue
            item_type = find_type_by_name(db, item_name)
            if item_type is None:
                warnings.append(f"Skipped unknown item: {item_name}")
                continue
            charge_type = find_type_by_name(db, charge_name) if charge_name else None
            if charge_name and charge_type is None:
                warnings.append(f"Skipped unknown charge for {item_name}: {charge_name}")
            prefix = fitting_slot_prefix_for_type(item_type, section_prefix)
            fitted_quantity = quantity if prefix in FITTED_SLOT_PREFIXES else 1
            for _ in range(fitted_quantity):
                parsed_items.append({
                    "type_id": item_type.type_id,
                    "charge_type_id": charge_type.type_id if charge_type else None,
                    "flag": next_import_flag(prefix, counters),
                    "quantity": 1 if prefix in FITTED_SLOT_PREFIXES else quantity,
                    "simulation_state": "online",
                })
    if not parsed_items:
        raise HTTPException(status_code=400, detail="No recognizable fitting items were found in the pasted text")
    return ship_type, fitting_name, parsed_items, warnings


def fitting_query(fitting_id: int) -> Any:
    return (
        select(CharacterFitting)
        .where(CharacterFitting.id == fitting_id)
        .options(
            selectinload(CharacterFitting.character).selectinload(EveCharacter.owner_user),
            selectinload(CharacterFitting.ship_type),
            selectinload(CharacterFitting.source_fitting),
            selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.item_type),
            selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.charge_type),
        )
    )


def load_fitting_or_404(db: Session, fitting_id: int) -> CharacterFitting:
    fitting = db.scalar(fitting_query(fitting_id))
    if fitting is None:
        raise HTTPException(status_code=404, detail="Fitting was not found")
    return fitting


def fitting_copy_text(fitting: CharacterFitting) -> str:
    ship_name = fitting.ship_type.name if fitting.ship_type else f"Type {fitting.ship_type_id}"
    lines = [f"[{ship_name}, {fitting.name}]", ""]
    grouped: dict[str, list[CharacterFittingItem]] = {}
    for item in fitting.items:
        grouped.setdefault(slot_prefix(item.flag), []).append(item)

    for group in [*FLAG_ORDER, *[flag for flag in BAY_FLAGS if flag not in FLAG_ORDER], "Other"]:
        items = grouped.get(group, [])
        if not items:
            continue
        if lines[-1] != "":
            lines.append("")
        if group == "Other":
            lines.append("# Other")
        for item in sorted(items, key=lambda row: (row.flag, row.item_type.name if row.item_type else str(row.type_id))):
            item_name = item.item_type.name if item.item_type else f"Type {item.type_id}"
            charge_name = item.charge_type.name if item.charge_type else None
            if group in {*BAY_FLAGS, "Other"} or item.quantity > 1:
                lines.append(f"{item_name} x{item.quantity}")
            elif charge_name:
                lines.append(f"{item_name}, {charge_name}")
            else:
                lines.append(item_name)
    return "\n".join(lines).strip() + "\n"


def fitting_summary(fitting: CharacterFitting) -> dict[str, int]:
    summary = {label: 0 for label in [*FLAG_LABELS.values(), *BAY_FLAG_LABELS.values()]}
    summary["Other"] = 0
    for item in fitting.items:
        label = BAY_FLAG_LABELS.get(slot_prefix(item.flag), FLAG_LABELS.get(slot_prefix(item.flag), "Other"))
        summary[label] = summary.get(label, 0) + item.quantity
    return {key: value for key, value in summary.items() if value > 0}


def serialize_fitting(fitting: CharacterFitting, current_user: User, db: Session) -> dict[str, Any]:
    character = fitting.character
    ship_type = fitting.ship_type
    items = sorted(fitting.items, key=lambda item: (FLAG_ORDER.index(slot_prefix(item.flag)) if slot_prefix(item.flag) in FLAG_ORDER else 99, item.flag, item.item_type.name if item.item_type else str(item.type_id)))
    return {
        "id": fitting.id,
        "eve_fitting_id": fitting.eve_fitting_id,
        "source_fitting_id": fitting.source_fitting_id,
        "source_fitting_name": fitting.source_fitting.name if fitting.source_fitting else None,
        "name": fitting.name,
        "description": fitting.description,
        "ship_type_id": fitting.ship_type_id,
        "ship_type_name": ship_type.name if ship_type else f"Type {fitting.ship_type_id}",
        "ship_capacity": resolved_ship_capacity(fitting.ship_type_id, ship_type.name if ship_type else None, ship_type.capacity if ship_type else None),
        "character_id": character.id if character else None,
        "character_eve_id": character.character_id if character else None,
        "character_name": character.name if character else "Unknown character",
        "owner_user_id": character.owner_user_id if character else None,
        "owner_display_name": character.owner_user.display_name if character and character.owner_user else None,
        "is_shared": fitting.is_shared,
        "is_draft": fitting.is_draft,
        "can_manage": can_manage_fitting(current_user, fitting, db),
        "last_synced_at": fitting.last_synced_at.isoformat() if fitting.last_synced_at else None,
        "updated_at": fitting.updated_at.isoformat() if fitting.updated_at else None,
        "summary": fitting_summary(fitting),
        "copy_text": fitting_copy_text(fitting),
        "items": [
            {
                "id": item.id,
                "type_id": item.type_id,
                "type_name": item.item_type.name if item.item_type else f"Type {item.type_id}",
                "charge_type_id": item.charge_type_id,
                "charge_type_name": item.charge_type.name if item.charge_type else None,
                "flag": item.flag,
                "quantity": item.quantity,
                "simulation_state": item.simulation_state or "online",
                "slot_group": BAY_FLAG_LABELS.get(slot_prefix(item.flag), FLAG_LABELS.get(slot_prefix(item.flag), "Other")),
                "volume": item.item_type.volume if item.item_type else None,
            }
            for item in items
        ],
    }


@router.get("")
def list_fittings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_fittings_view(current_user, db)
    query = (
        select(CharacterFitting)
        .options(
            selectinload(CharacterFitting.character).selectinload(EveCharacter.owner_user),
            selectinload(CharacterFitting.ship_type),
            selectinload(CharacterFitting.source_fitting),
            selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.item_type),
            selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.charge_type),
        )
        .order_by(CharacterFitting.is_draft.desc(), CharacterFitting.name)
    )
    if not can_view_all_characters(current_user, db):
        query = query.join(EveCharacter, CharacterFitting.character_id == EveCharacter.id).where(
            or_(EveCharacter.owner_user_id == current_user.id, CharacterFitting.is_shared.is_(True))
        )
    fittings = db.scalars(query).all()
    normalized_any = any(normalize_draft_fitting_items(db, fitting) for fitting in fittings)
    if normalized_any:
        db.commit()

    token_query = (
        select(EsiToken, EveCharacter)
        .join(EveCharacter, EveCharacter.id == EsiToken.character_id)
        .where(EsiToken.revoked_at.is_(None))
        .order_by(EveCharacter.name)
    )
    if not can_view_all_characters(current_user, db):
        token_query = token_query.where(EsiToken.user_id == current_user.id)
    tokens = db.execute(token_query).all()
    sync_tokens = [
        {
            "token_id": token.id,
            "character_id": character.id,
            "character_name": character.name,
            "has_fitting_scope": FITTING_READ_SCOPE in token_scopes(token),
            "can_sync": token.user_id == current_user.id or can_view_all_characters(current_user, db),
        }
        for token, character in tokens
    ]
    return {"fittings": [serialize_fitting(fitting, current_user, db) for fitting in fittings], "sync_tokens": sync_tokens, "editable_flags": DRAFT_FLAGS}


def serialize_fitting_picker_type(row: EveType) -> dict[str, Any]:
    return {
        "type_id": row.type_id,
        "name": row.name,
        "group_id": row.group_id,
        "group_name": row.group.name if row.group else None,
        "category_name": row.group.category.name if row.group and row.group.category else None,
        "volume": row.volume,
        "published": row.published,
    }


@router.get("/item-search")
def search_fitting_items(q: str = Query("", min_length=1), limit: int = 25, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_fittings_view(current_user, db)
    cleaned = q.strip()
    if not cleaned:
        return []
    rows = db.scalars(
        select(EveType)
        .options(selectinload(EveType.group).selectinload(EveGroup.category))
        .where(EveType.name.ilike(f"%{cleaned}%"))
        .order_by(EveType.name)
        .limit(max(1, min(limit, 80)))
    ).all()
    return [serialize_fitting_picker_type(row) for row in rows]


@router.get("/item-catalog")
def fitting_item_catalog(bucket: str = Query("Modules"), limit: int = 8000, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    require_fittings_view(current_user, db)
    normalized = bucket.strip().lower()
    bucket_conditions = {
        "modules": [EveCategory.name == "Module"],
        "rigs": [EveCategory.name == "Ship Modifications", EveGroup.name.ilike("%Rig%")],
        "ammo": [EveCategory.name == "Charge"],
        "drones": [EveCategory.name.in_(["Drone", "Fighter"])],
    }
    conditions = bucket_conditions.get(normalized)
    if conditions is None:
        if normalized == "other":
            return []
        raise HTTPException(status_code=400, detail="Unknown fitting catalog bucket")
    rows = db.scalars(
        select(EveType)
        .join(EveGroup, EveType.group_id == EveGroup.group_id)
        .join(EveCategory, EveGroup.category_id == EveCategory.category_id)
        .options(selectinload(EveType.group).selectinload(EveGroup.category))
        .where(EveType.published.is_(True), EveGroup.published.is_(True), EveCategory.published.is_(True), or_(*conditions))
        .order_by(EveGroup.name, EveType.name)
        .limit(max(1, min(limit, 12000)))
    ).all()
    return [serialize_fitting_picker_type(row) for row in rows]




@router.post("/import-text")
async def import_fitting_text(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_fittings_view(current_user, db)
    character_id = int(payload.get("character_id") or 0)
    character = db.get(EveCharacter, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Choose a character before importing the fitting")
    if not can_view_all_characters(current_user, db) and character.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only import fittings for your own characters")
    ship_type, fitting_name, parsed_items, warnings = parse_eft_fit(db, str(payload.get("text") or ""))
    refreshed_types = await refresh_public_type_metadata(db, {ship_type.type_id, *(int(item["type_id"]) for item in parsed_items), *(int(item["charge_type_id"]) for item in parsed_items if item.get("charge_type_id") is not None)})
    if refreshed_types:
        db.flush()
        ship_type = db.get(EveType, ship_type.type_id) or ship_type
    now = datetime.now(timezone.utc)
    draft = CharacterFitting(
        character_id=character.id,
        eve_fitting_id=None,
        source_fitting_id=None,
        name=fitting_name[:255],
        description="Imported from EFT clipboard text.",
        ship_type_id=ship_type.type_id,
        is_shared=False,
        is_draft=True,
        updated_at=now,
    )
    db.add(draft)
    db.flush()
    for item in parsed_items:
        db.add(CharacterFittingItem(fitting_id=draft.id, **item))
    db.commit()
    return {"fitting": serialize_fitting(load_fitting_or_404(db, draft.id), current_user, db), "warnings": warnings}


@router.patch("/{fitting_id}")
def update_fitting(fitting_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_fittings_view(current_user, db)
    fitting = load_fitting_or_404(db, fitting_id)
    if not can_manage_fitting(current_user, fitting, db):
        raise HTTPException(status_code=403, detail="You can only edit your own fittings")
    if "is_shared" in payload:
        fitting.is_shared = bool(payload["is_shared"])
    if fitting.is_draft and "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Draft name is required")
        fitting.name = name[:255]
    fitting.updated_at = datetime.now(timezone.utc)
    db.commit()
    return serialize_fitting(load_fitting_or_404(db, fitting.id), current_user, db)


@router.post("/{fitting_id}/draft")
def create_fitting_draft(fitting_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_fittings_view(current_user, db)
    source = load_fitting_or_404(db, fitting_id)
    if not can_view_fitting(current_user, source, db):
        raise HTTPException(status_code=403, detail="You cannot view this fitting")
    if not can_manage_fitting(current_user, source, db):
        raise HTTPException(status_code=403, detail="You can only draft your own fittings")
    draft = CharacterFitting(
        character_id=source.character_id,
        eve_fitting_id=None,
        source_fitting_id=source.id,
        name=f"{source.name} Draft",
        description=source.description,
        ship_type_id=source.ship_type_id,
        is_shared=False,
        is_draft=True,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(draft)
    db.flush()
    for item in source.items:
        db.add(CharacterFittingItem(
            fitting_id=draft.id,
            type_id=item.type_id,
            charge_type_id=item.charge_type_id,
            flag=item.flag,
            quantity=item.quantity,
            simulation_state=item.simulation_state or "online",
        ))
    db.commit()
    return serialize_fitting(load_fitting_or_404(db, draft.id), current_user, db)


@router.post("/{fitting_id}/items")
def add_fitting_item(fitting_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_fittings_view(current_user, db)
    fitting = load_fitting_or_404(db, fitting_id)
    require_manageable_draft(current_user, fitting, db)
    type_id = int(payload.get("type_id") or 0)
    item_type = get_type_with_group(db, type_id)
    if item_type is None:
        raise HTTPException(status_code=400, detail="Item type was not found in the SDE")
    quantity = max(1, int(payload.get("quantity") or 1))
    flag = normalize_item_flag_for_type(item_type, str(payload.get("flag") or "Cargo"))
    flag = next_free_fitting_flag(fitting, flag)
    quantity = fitting_item_quantity_for_flag(flag, quantity)
    charge_type_id = payload.get("charge_type_id")
    if charge_type_id in {"", 0, "0"}:
        charge_type_id = None
    if charge_type_id is not None:
        charge_type_id = int(charge_type_id)
        if db.get(EveType, charge_type_id) is None:
            raise HTTPException(status_code=400, detail="Charge type was not found in the SDE")
    simulation_state = str(payload.get("simulation_state") or "online").strip().lower()
    if simulation_state not in SIMULATION_STATES:
        raise HTTPException(status_code=400, detail="Unknown simulation state")
    db.add(CharacterFittingItem(fitting_id=fitting.id, type_id=type_id, charge_type_id=charge_type_id, flag=flag, quantity=quantity, simulation_state=simulation_state))
    fitting.updated_at = datetime.now(timezone.utc)
    db.commit()
    return serialize_fitting(load_fitting_or_404(db, fitting.id), current_user, db)


@router.patch("/{fitting_id}/items/{item_id}")
def update_fitting_item(fitting_id: int, item_id: int, payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_fittings_view(current_user, db)
    fitting = load_fitting_or_404(db, fitting_id)
    if not can_manage_fitting(current_user, fitting, db):
        raise HTTPException(status_code=403, detail="You can only edit your own fittings")
    item = db.get(CharacterFittingItem, item_id)
    if item is None or item.fitting_id != fitting.id:
        raise HTTPException(status_code=404, detail="Fitting item was not found")
    structural_update = any(key in payload for key in {"type_id", "flag", "quantity"})
    if structural_update and not fitting.is_draft:
        raise HTTPException(status_code=400, detail="Create an editable draft before changing fitting items")
    if "type_id" in payload:
        type_id = int(payload.get("type_id") or 0)
        if get_type_with_group(db, type_id) is None:
            raise HTTPException(status_code=400, detail="Item type was not found in the SDE")
        item.type_id = type_id
    if "quantity" in payload:
        item.quantity = max(1, int(payload.get("quantity") or 1))
    item_type = get_type_with_group(db, item.type_id)
    if item_type is None:
        raise HTTPException(status_code=400, detail="Item type was not found in the SDE")
    if "flag" in payload or "type_id" in payload:
        requested_flag = str(payload.get("flag") or item.flag)
        item.flag = next_free_fitting_flag(fitting, normalize_item_flag_for_type(item_type, requested_flag), item.id)
    item.quantity = fitting_item_quantity_for_flag(item.flag, item.quantity)
    if "charge_type_id" in payload:
        charge_type_id = payload.get("charge_type_id")
        if charge_type_id in {None, "", 0, "0"}:
            item.charge_type_id = None
        else:
            charge_type_id = int(charge_type_id)
            if db.get(EveType, charge_type_id) is None:
                raise HTTPException(status_code=400, detail="Charge type was not found in the SDE")
            item.charge_type_id = charge_type_id
    if "simulation_state" in payload:
        simulation_state = str(payload.get("simulation_state") or "online").strip().lower()
        if simulation_state not in SIMULATION_STATES:
            raise HTTPException(status_code=400, detail="Unknown simulation state")
        item.simulation_state = simulation_state
    fitting.updated_at = datetime.now(timezone.utc)
    db.commit()
    return serialize_fitting(load_fitting_or_404(db, fitting.id), current_user, db)


@router.delete("/{fitting_id}/items/{item_id}")
def delete_fitting_item(fitting_id: int, item_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_fittings_view(current_user, db)
    fitting = load_fitting_or_404(db, fitting_id)
    require_manageable_draft(current_user, fitting, db)
    item = db.get(CharacterFittingItem, item_id)
    if item is None or item.fitting_id != fitting.id:
        raise HTTPException(status_code=404, detail="Fitting item was not found")
    db.delete(item)
    fitting.updated_at = datetime.now(timezone.utc)
    db.commit()
    return serialize_fitting(load_fitting_or_404(db, fitting.id), current_user, db)



def serialize_sim_implant(type_id: int, item_type: EveType | None, slot: int | None = None) -> dict[str, Any]:
    return {
        "type_id": type_id,
        "name": item_type.name if item_type else f"Type {type_id}",
        "slot": slot,
    }


def simulation_implant_context(db: Session, current_user: User, target_character: EveCharacter, implant_set_id: int | None = None, jump_clone_id: int | None = None) -> tuple[set[int], dict[str, Any] | None]:
    if implant_set_id and jump_clone_id:
        raise HTTPException(status_code=400, detail="Choose either a custom implant set or a synced jump clone, not both")
    if implant_set_id:
        row = db.scalar(
            select(ImplantSet)
            .where(ImplantSet.id == implant_set_id)
            .options(selectinload(ImplantSet.implants).selectinload(ImplantSetImplant.implant_type))
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Implant set was not found")
        if row.owner_user_id != current_user.id and not row.is_shared and not can_view_all_characters(current_user, db):
            raise HTTPException(status_code=403, detail="You cannot use that implant set")
        implants = sorted(row.implants, key=lambda item: (item.slot is None, item.slot or 99, item.implant_type.name if item.implant_type else str(item.type_id)))
        return {implant.type_id for implant in implants}, {
            "source": "custom_set",
            "id": row.id,
            "name": row.name,
            "implant_count": len(implants),
            "implants": [serialize_sim_implant(implant.type_id, implant.implant_type, implant.slot) for implant in implants],
        }
    if jump_clone_id:
        clone = db.scalar(
            select(CharacterJumpClone)
            .where(CharacterJumpClone.id == jump_clone_id)
            .options(selectinload(CharacterJumpClone.implants).selectinload(JumpCloneImplant.implant_type))
        )
        if clone is None:
            raise HTTPException(status_code=404, detail="Jump clone was not found")
        if clone.character_id != target_character.id:
            raise HTTPException(status_code=400, detail="That jump clone belongs to a different character")
        implants = sorted(clone.implants, key=lambda item: (item.slot is None, item.slot or 99, item.implant_type.name if item.implant_type else str(item.type_id)))
        return {implant.type_id for implant in implants}, {
            "source": clone.clone_kind,
            "id": clone.id,
            "name": clone.name or ("Active clone" if clone.clone_kind == "active_clone" else f"Jump clone {clone.jump_clone_id}"),
            "implant_count": len(implants),
            "implants": [serialize_sim_implant(implant.type_id, implant.implant_type, implant.slot) for implant in implants],
        }
    return set(), None

@router.get("/{fitting_id}/simulation")
def simulate_saved_fitting(fitting_id: int, character_id: int | None = None, heat: bool = False, implant_set_id: int | None = None, jump_clone_id: int | None = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_fittings_view(current_user, db)
    fitting = load_fitting_for_simulation(db, fitting_id)
    if fitting is None:
        raise HTTPException(status_code=404, detail="Fitting was not found")
    if not can_view_fitting(current_user, fitting, db):
        raise HTTPException(status_code=403, detail="You cannot view this fitting")
    if normalize_draft_fitting_items(db, fitting):
        db.commit()
        fitting = load_fitting_for_simulation(db, fitting_id)
        if fitting is None:
            raise HTTPException(status_code=404, detail="Fitting was not found")

    target_character = fitting.character if character_id is None else db.get(EveCharacter, character_id)
    if target_character is None:
        raise HTTPException(status_code=404, detail="Character was not found")
    if not can_view_all_characters(current_user, db) and target_character.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only simulate against your own characters")
    implant_type_ids, implant_context = simulation_implant_context(db, current_user, target_character, implant_set_id=implant_set_id, jump_clone_id=jump_clone_id)
    return simulate_fitting(db, fitting, target_character, heat=heat, implant_type_ids=implant_type_ids, implant_context=implant_context)
