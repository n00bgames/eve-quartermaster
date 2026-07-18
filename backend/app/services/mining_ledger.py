from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import EveCharacter, EveSystem, EveType, MiningLedgerEntry, MiningOperation


def as_int(value: Any) -> int:
    text = str(value or "0").replace(",", "").strip()
    return int(float(text or 0))


def as_decimal(value: Any) -> Decimal:
    text = str(value or "0").replace(",", "").replace("ISK", "").strip()
    return Decimal(text or "0")


def parse_mined_at(value: Any) -> tuple[date, datetime | None]:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Timestamp is required")
    normalized = text.replace(".", "-").replace("/", "-").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.date(), parsed
    except ValueError:
        for pattern in ("%Y-%m-%d", "%m-%d-%Y"):
            try:
                parsed_date = datetime.strptime(normalized, pattern).date()
                return parsed_date, None
            except ValueError:
                continue
    raise ValueError(f"Unsupported timestamp: {text}")


def normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def parse_export(text: str) -> tuple[list[dict[str, str]], set[str]]:
    clean = text.strip().lstrip("\ufeff")
    if not clean:
        raise HTTPException(status_code=400, detail="Paste at least one mining ledger row.")
    first_line = clean.splitlines()[0]
    delimiter = "\t" if "\t" in first_line else ","
    reader = csv.DictReader(io.StringIO(clean), delimiter=delimiter)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="The mining ledger needs a header row.")
    header_map = {normalized_header(name): name for name in reader.fieldnames if name}
    required = {"timestamp", "oretype", "quantity", "solarsystem", "oretypeid", "solarsystemid"}
    missing = sorted(required - set(header_map))
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing mining ledger columns: {', '.join(missing)}")
    rows = []
    for raw in reader:
        if not any(str(value or "").strip() for value in raw.values()):
            continue
        rows.append({key: str(raw.get(source) or "").strip() for key, source in header_map.items()})
    return rows, set(header_map)


def operation_for_entry(
    operations: Iterable[MiningOperation],
    character_id: int,
    system_id: int,
    mined_date: date,
) -> MiningOperation | None:
    day_start = datetime.combine(mined_date, time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(mined_date, time.max, tzinfo=timezone.utc)
    for operation in operations:
        participant_ids = {row.character_id for row in operation.participants}
        if character_id not in participant_ids:
            continue
        if operation.solar_system_id and operation.solar_system_id != system_id:
            continue
        if operation.start_at <= day_end and operation.end_at >= day_start:
            return operation
    return None


def relevant_operations(db: Session, character_id: int) -> list[MiningOperation]:
    return list(db.scalars(
        select(MiningOperation)
        .options(selectinload(MiningOperation.participants))
        .where(MiningOperation.participants.any(character_id=character_id))
        .order_by(MiningOperation.start_at.desc())
    ).all())


def lookup_static_data(db: Session, type_ids: set[int], system_ids: set[int]) -> tuple[dict[int, EveType], dict[int, EveSystem]]:
    types = {row.type_id: row for row in db.scalars(select(EveType).where(EveType.type_id.in_(type_ids))).all()}
    systems = {row.system_id: row for row in db.scalars(select(EveSystem).where(EveSystem.system_id.in_(system_ids))).all()}
    missing_types = sorted(type_ids - set(types))
    missing_systems = sorted(system_ids - set(systems))
    if missing_types or missing_systems:
        details = []
        if missing_types:
            details.append(f"ore type IDs {', '.join(map(str, missing_types[:8]))}")
        if missing_systems:
            details.append(f"solar system IDs {', '.join(map(str, missing_systems[:8]))}")
        raise HTTPException(status_code=409, detail=f"Import the current SDE before loading {', '.join(details)}.")
    return types, systems


def existing_entries(db: Session, character_id: int, dates: set[date]) -> dict[tuple[date, int, int], MiningLedgerEntry]:
    if not dates:
        return {}
    rows = db.scalars(
        select(MiningLedgerEntry).where(
            MiningLedgerEntry.character_id == character_id,
            MiningLedgerEntry.mined_date.in_(dates),
        )
    ).all()
    return {(row.mined_date, row.ore_type_id, row.solar_system_id): row for row in rows}


def import_detailed_ledger(db: Session, character: EveCharacter, text: str, operation_id: int | None = None) -> dict[str, Any]:
    rows, headers = parse_export(text)
    parsed = []
    errors = []
    for index, row in enumerate(rows, start=2):
        try:
            mined_date, mined_at = parse_mined_at(row["timestamp"])
            parsed.append({**row, "mined_date": mined_date, "mined_at": mined_at, "type_id": as_int(row["oretypeid"]), "system_id": as_int(row["solarsystemid"])})
        except (ValueError, ArithmeticError) as exc:
            errors.append(f"Row {index}: {exc}")
    if errors:
        raise HTTPException(status_code=400, detail={"message": "Mining ledger import contains invalid rows.", "errors": errors[:20]})

    types, systems = lookup_static_data(db, {row["type_id"] for row in parsed}, {row["system_id"] for row in parsed})
    existing = existing_entries(db, character.id, {row["mined_date"] for row in parsed})
    operations = relevant_operations(db, character.id)
    explicit_operation = db.get(MiningOperation, operation_id) if operation_id else None
    now = datetime.now(timezone.utc)
    imported = updated = 0
    residue_reported = "residuequantity" in headers or "residuevolume" in headers

    for row in parsed:
        key = (row["mined_date"], row["type_id"], row["system_id"])
        entry = existing.get(key)
        if entry is None:
            entry = MiningLedgerEntry(character_id=character.id, mined_date=row["mined_date"], ore_type_id=row["type_id"], solar_system_id=row["system_id"], last_synced_at=now)
            db.add(entry)
            existing[key] = entry
            imported += 1
        else:
            updated += 1
        type_row = types[row["type_id"]]
        system_row = systems[row["system_id"]]
        quantity = as_int(row.get("quantity"))
        residue_quantity = as_int(row.get("residuequantity"))
        unit_volume = Decimal(str(type_row.volume or 0))
        entry.mined_at = row["mined_at"]
        entry.ore_type_name = row.get("oretype") or type_row.name
        entry.solar_system_name = row.get("solarsystem") or system_row.name
        entry.quantity = quantity
        entry.residue_quantity = residue_quantity
        entry.volume = as_decimal(row.get("volume")) if row.get("volume") else Decimal(quantity) * unit_volume
        entry.residue_volume = as_decimal(row.get("residuevolume")) if row.get("residuevolume") else Decimal(residue_quantity) * unit_volume
        entry.estimated_price = as_decimal(row.get("estprice"))
        entry.estimated_residue_price = as_decimal(row.get("estresidueprice"))
        entry.has_residue_data = residue_reported
        entry.source = "import"
        entry.last_synced_at = now
        matched = explicit_operation or operation_for_entry(operations, character.id, row["system_id"], row["mined_date"])
        if matched:
            entry.operation_id = matched.id
    db.commit()
    return {"character_name": character.name, "imported": imported, "updated": updated, "row_count": len(parsed), "residue_reported": residue_reported}


def upsert_esi_ledger(db: Session, character: EveCharacter, rows: list[dict[str, Any]], market_prices: dict[int, float]) -> dict[str, Any]:
    parsed = [{**row, "mined_date": date.fromisoformat(str(row["date"])), "type_id": int(row["type_id"]), "system_id": int(row["solar_system_id"])} for row in rows]
    if not parsed:
        return {"character_name": character.name, "synced": 0, "preserved_history": True}
    types, systems = lookup_static_data(db, {row["type_id"] for row in parsed}, {row["system_id"] for row in parsed})
    existing = existing_entries(db, character.id, {row["mined_date"] for row in parsed})
    operations = relevant_operations(db, character.id)
    now = datetime.now(timezone.utc)
    inserted = updated = detailed_preserved = 0
    for row in parsed:
        key = (row["mined_date"], row["type_id"], row["system_id"])
        entry = existing.get(key)
        if entry and entry.source == "import":
            entry.last_synced_at = now
            detailed_preserved += 1
            continue
        if entry is None:
            entry = MiningLedgerEntry(character_id=character.id, mined_date=row["mined_date"], ore_type_id=row["type_id"], solar_system_id=row["system_id"], last_synced_at=now)
            db.add(entry)
            existing[key] = entry
            inserted += 1
        else:
            updated += 1
        type_row = types[row["type_id"]]
        system_row = systems[row["system_id"]]
        quantity = int(row.get("quantity") or 0)
        unit_volume = Decimal(str(type_row.volume or 0))
        unit_price = Decimal(str(market_prices.get(row["type_id"], 0)))
        entry.ore_type_name = type_row.name
        entry.solar_system_name = system_row.name
        entry.quantity = quantity
        entry.residue_quantity = 0
        entry.volume = Decimal(quantity) * unit_volume
        entry.residue_volume = 0
        entry.estimated_price = Decimal(quantity) * unit_price
        entry.estimated_residue_price = 0
        entry.has_residue_data = False
        entry.source = "esi"
        entry.last_synced_at = now
        matched = operation_for_entry(operations, character.id, row["system_id"], row["mined_date"])
        if matched and entry.operation_id is None:
            entry.operation_id = matched.id
    db.commit()
    return {"character_name": character.name, "synced": len(parsed), "inserted": inserted, "updated": updated, "detailed_rows_preserved": detailed_preserved, "preserved_history": True}
