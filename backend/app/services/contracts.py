from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import EveCharacter, EveContract, EveCorporation, EveStation, EveSystem, Location, User
from app.services.esi_client import EsiClient

ACTIVE_CONTRACT_STATUSES = {"outstanding", "in_progress"}
MAX_POSTGRES_INTEGER = 2_147_483_647


def parse_esi_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def money(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def contract_location_name(db: Session, location_id: int | None) -> str | None:
    if location_id is None:
        return None
    local_location = db.scalar(select(Location).where(Location.eve_location_id == location_id).limit(1))
    if local_location:
        return local_location.name
    if location_id > MAX_POSTGRES_INTEGER:
        return f"Structure {location_id}"
    station = db.get(EveStation, location_id)
    if station:
        return station.name
    system = db.get(EveSystem, location_id)
    if system:
        return system.name
    return f"Location {location_id}"


async def fetch_contract_pages(client: EsiClient, path: str) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    page = 1
    while True:
        payload, headers = await client.get_with_headers(path, params={"page": page})
        rows = payload or []
        contracts.extend(rows)
        try:
            pages = int(headers.get("x-pages", "1"))
        except ValueError:
            pages = 1
        if page >= pages or not rows:
            break
        page += 1
    return contracts


def upsert_contract_rows(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    scope_type: str,
    owner_user: User | None = None,
    character: EveCharacter | None = None,
    corporation: EveCorporation | None = None,
) -> int:
    now = datetime.now(timezone.utc)
    seen_ids: set[int] = set()
    synced = 0
    for row in rows:
        contract_id = int(row["contract_id"])
        seen_ids.add(contract_id)
        contract_query = select(EveContract).where(
            EveContract.contract_id == contract_id,
            EveContract.scope_type == scope_type,
        )
        if character is not None:
            contract_query = contract_query.where(EveContract.character_id == character.id)
        if corporation is not None:
            contract_query = contract_query.where(EveContract.corporation_id == corporation.id)
        contract = db.scalar(contract_query)
        if contract is None:
            contract = EveContract(contract_id=contract_id, scope_type=scope_type)
            db.add(contract)
        contract.scope_type = scope_type
        contract.owner_user_id = owner_user.id if owner_user else None
        contract.character_id = character.id if character else None
        contract.corporation_id = corporation.id if corporation else None
        contract.issuer_id = row.get("issuer_id")
        contract.issuer_corporation_id = row.get("issuer_corporation_id")
        contract.assignee_id = row.get("assignee_id")
        contract.acceptor_id = row.get("acceptor_id")
        contract.for_corporation = bool(row.get("for_corporation", False))
        contract.contract_type = row.get("type")
        contract.status = row.get("status")
        contract.title = row.get("title")
        contract.availability = row.get("availability")
        contract.date_issued = parse_esi_datetime(row.get("date_issued"))
        contract.date_expired = parse_esi_datetime(row.get("date_expired"))
        contract.date_accepted = parse_esi_datetime(row.get("date_accepted"))
        contract.date_completed = parse_esi_datetime(row.get("date_completed"))
        contract.start_location_id = row.get("start_location_id")
        contract.end_location_id = row.get("end_location_id")
        contract.start_location_name = contract_location_name(db, row.get("start_location_id"))
        contract.end_location_name = contract_location_name(db, row.get("end_location_id"))
        contract.price = money(row.get("price"))
        contract.reward = money(row.get("reward"))
        contract.collateral = money(row.get("collateral"))
        contract.buyout = money(row.get("buyout"))
        contract.volume = money(row.get("volume"))
        contract.days_to_complete = row.get("days_to_complete")
        contract.raw_json = json.dumps(row, sort_keys=True)
        contract.last_synced_at = now
        synced += 1

    cleanup = delete(EveContract).where(EveContract.scope_type == scope_type)
    if character is not None:
        cleanup = cleanup.where(EveContract.character_id == character.id)
    if corporation is not None:
        cleanup = cleanup.where(EveContract.corporation_id == corporation.id)
    if seen_ids:
        cleanup = cleanup.where(~EveContract.contract_id.in_(seen_ids))
    db.execute(cleanup)
    db.flush()
    return synced


def serialize_contract(contract: EveContract) -> dict[str, Any]:
    return {
        "id": contract.id,
        "contract_id": contract.contract_id,
        "scope_type": contract.scope_type,
        "owner_user_id": contract.owner_user_id,
        "character_id": contract.character.character_id if contract.character else None,
        "character_name": contract.character.name if contract.character else None,
        "corporation_id": contract.corporation.corporation_id if contract.corporation else None,
        "corporation_name": contract.corporation.name if contract.corporation else None,
        "issuer_id": contract.issuer_id,
        "issuer_corporation_id": contract.issuer_corporation_id,
        "assignee_id": contract.assignee_id,
        "acceptor_id": contract.acceptor_id,
        "for_corporation": contract.for_corporation,
        "contract_type": contract.contract_type,
        "status": contract.status,
        "title": contract.title,
        "availability": contract.availability,
        "date_issued": contract.date_issued.isoformat() if contract.date_issued else None,
        "date_expired": contract.date_expired.isoformat() if contract.date_expired else None,
        "date_accepted": contract.date_accepted.isoformat() if contract.date_accepted else None,
        "date_completed": contract.date_completed.isoformat() if contract.date_completed else None,
        "start_location_id": contract.start_location_id,
        "end_location_id": contract.end_location_id,
        "start_location_name": contract.start_location_name,
        "end_location_name": contract.end_location_name,
        "price": float(contract.price) if contract.price is not None else None,
        "reward": float(contract.reward) if contract.reward is not None else None,
        "collateral": float(contract.collateral) if contract.collateral is not None else None,
        "buyout": float(contract.buyout) if contract.buyout is not None else None,
        "volume": float(contract.volume) if contract.volume is not None else None,
        "days_to_complete": contract.days_to_complete,
        "last_synced_at": contract.last_synced_at.isoformat() if contract.last_synced_at else None,
    }
