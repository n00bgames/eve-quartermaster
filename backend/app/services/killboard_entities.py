from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EveAlliance, EveCharacter, EveCorporation, KillboardEntityName, Killmail, KillmailAttacker
from app.services.esi_client import EsiClient


class NameClient(Protocol):
    async def post(self, path: str, payload: Any, params: dict[str, Any] | None = None) -> Any: ...


ENTITY_COLUMNS = {
    "character": (Killmail.victim_character_id, KillmailAttacker.character_id),
    "corporation": (Killmail.victim_corporation_id, KillmailAttacker.corporation_id),
    "alliance": (Killmail.victim_alliance_id, KillmailAttacker.alliance_id),
    "faction": (Killmail.victim_faction_id, KillmailAttacker.faction_id),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _all_killboard_entity_ids(db: Session) -> dict[str, set[int]]:
    result: dict[str, set[int]] = defaultdict(set)
    victim_rows = db.execute(select(
        Killmail.victim_character_id,
        Killmail.victim_corporation_id,
        Killmail.victim_alliance_id,
        Killmail.victim_faction_id,
    )).all()
    attacker_rows = db.execute(select(
        KillmailAttacker.character_id,
        KillmailAttacker.corporation_id,
        KillmailAttacker.alliance_id,
        KillmailAttacker.faction_id,
    )).all()
    for row in victim_rows:
        for category, value in zip(ENTITY_COLUMNS, row, strict=True):
            if value:
                result[category].add(int(value))
    for row in attacker_rows:
        for category, value in zip(ENTITY_COLUMNS, row, strict=True):
            if value:
                result[category].add(int(value))
    return result


def unresolved_killboard_entity_ids(db: Session, *, limit: int = 900) -> list[tuple[int, str]]:
    ids_by_category = _all_killboard_entity_ids(db)
    tracked = {
        "character": set(db.scalars(select(EveCharacter.character_id).where(EveCharacter.character_id.in_(ids_by_category["character"]))).all()) if ids_by_category["character"] else set(),
        "corporation": set(db.scalars(select(EveCorporation.corporation_id).where(EveCorporation.corporation_id.in_(ids_by_category["corporation"]))).all()) if ids_by_category["corporation"] else set(),
        "alliance": set(db.scalars(select(EveAlliance.alliance_id).where(EveAlliance.alliance_id.in_(ids_by_category["alliance"]))).all()) if ids_by_category["alliance"] else set(),
        "faction": set(),
    }
    all_ids = {value for values in ids_by_category.values() for value in values}
    cached = {row.eve_id: row for row in db.scalars(select(KillboardEntityName).where(KillboardEntityName.eve_id.in_(all_ids))).all()} if all_ids else {}
    now = utc_now()
    result: list[tuple[int, str]] = []
    for category in ("character", "corporation", "alliance", "faction"):
        for eve_id in sorted(ids_by_category[category] - tracked[category]):
            row = cached.get(eve_id)
            attempted = row.last_attempt_at if row else None
            if attempted is not None and attempted.tzinfo is None:
                attempted = attempted.replace(tzinfo=timezone.utc)
            retry_after = timedelta(days=30 if row and row.resolution_status == "resolved" else 7)
            if row is not None and attempted is not None and attempted > now - retry_after:
                continue
            result.append((eve_id, category))
            if len(result) >= max(1, min(10_000, limit)):
                return result
    return result


def cached_killboard_name_maps(db: Session, ids_by_category: dict[str, set[int]]) -> dict[str, dict[int, str]]:
    all_ids = {value for values in ids_by_category.values() for value in values}
    result: dict[str, dict[int, str]] = {category: {} for category in ENTITY_COLUMNS}
    if not all_ids:
        return result
    rows = db.scalars(select(KillboardEntityName).where(
        KillboardEntityName.eve_id.in_(all_ids),
        KillboardEntityName.resolution_status == "resolved",
        KillboardEntityName.name.is_not(None),
    )).all()
    for row in rows:
        if row.category in result and row.eve_id in ids_by_category.get(row.category, set()) and row.name:
            result[row.category][int(row.eve_id)] = row.name
    return result


async def refresh_killboard_entity_names(
    db: Session,
    *,
    client: NameClient | None = None,
    limit: int = 900,
) -> dict[str, int]:
    candidates = unresolved_killboard_entity_ids(db, limit=limit)
    if not candidates:
        return {"requested": 0, "resolved": 0, "unavailable": 0}
    owns_client = client is None
    name_client = client or EsiClient()
    category_hints = {eve_id: category for eve_id, category in candidates}
    resolved: dict[int, tuple[str, str]] = {}
    unavailable: set[int] = set()

    async def resolve_chunk(ids: list[int]) -> None:
        try:
            payload = await name_client.post("/universe/names/", ids)
        except HTTPException as exc:
            if exc.status_code in {400, 404} and len(ids) > 1:
                midpoint = len(ids) // 2
                await resolve_chunk(ids[:midpoint])
                await resolve_chunk(ids[midpoint:])
            elif exc.status_code in {400, 404}:
                unavailable.update(ids)
            return
        except Exception:
            return
        returned: set[int] = set()
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict) or item.get("id") is None or not item.get("name"):
                    continue
                eve_id = int(item["id"])
                category = str(item.get("category") or category_hints.get(eve_id) or "unknown").lower()
                resolved[eve_id] = (category, str(item["name"]))
                returned.add(eve_id)
        unavailable.update(set(ids) - returned)

    try:
        candidate_ids = [eve_id for eve_id, _category in candidates]
        for offset in range(0, len(candidate_ids), 900):
            await resolve_chunk(candidate_ids[offset:offset + 900])
    finally:
        if owns_client:
            await name_client.close()

    now = utc_now()
    for eve_id, (category, name) in resolved.items():
        row = db.get(KillboardEntityName, eve_id)
        if row is None:
            row = KillboardEntityName(eve_id=eve_id, category=category)
            db.add(row)
        row.category = category
        row.name = name
        row.resolution_status = "resolved"
        row.last_attempt_at = now
        row.resolved_at = now
    for eve_id in unavailable - set(resolved):
        row = db.get(KillboardEntityName, eve_id)
        if row is None:
            row = KillboardEntityName(eve_id=eve_id, category=category_hints.get(eve_id, "unknown"))
            db.add(row)
        row.name = None
        row.resolution_status = "unavailable"
        row.last_attempt_at = now
    db.commit()
    return {"requested": len(candidates), "resolved": len(resolved), "unavailable": len(unavailable - set(resolved))}
