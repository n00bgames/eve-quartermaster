from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CharacterStanding, EveCharacter

STANDING_SOURCE_TYPES = {"agent", "npc_corp", "faction"}


def serialize_character_standing(row: CharacterStanding) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_type": row.source_type,
        "source_eve_id": row.source_eve_id,
        "source_name": row.source_name,
        "standing": float(row.standing),
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
    }


def upsert_character_standings(
    db: Session,
    character: EveCharacter,
    rows: list[dict[str, Any]],
    names: dict[int, str],
    *,
    synced_at: datetime | None = None,
) -> dict[str, int]:
    now = synced_at or datetime.now(timezone.utc)
    existing = {
        (row.source_type, row.source_eve_id): row
        for row in db.scalars(
            select(CharacterStanding).where(CharacterStanding.character_id == character.id)
        ).all()
    }
    seen: set[tuple[str, int]] = set()
    created = 0
    updated = 0

    for payload in rows:
        source_type = str(payload.get("from_type") or "").strip()
        source_eve_id = int(payload.get("from_id") or 0)
        if source_type not in STANDING_SOURCE_TYPES or source_eve_id <= 0:
            continue
        key = (source_type, source_eve_id)
        if key in seen:
            continue
        seen.add(key)
        standing = existing.get(key)
        if standing is None:
            standing = CharacterStanding(
                character_id=character.id,
                source_type=source_type,
                source_eve_id=source_eve_id,
                source_name=names.get(source_eve_id, f"{source_type.replace('_', ' ').title()} {source_eve_id}"),
                standing=float(payload.get("standing") or 0),
                last_synced_at=now,
            )
            db.add(standing)
            created += 1
        else:
            standing.source_name = names.get(source_eve_id, standing.source_name)
            standing.standing = float(payload.get("standing") or 0)
            standing.last_synced_at = now
            updated += 1

    removed = 0
    for key, standing in existing.items():
        if key not in seen:
            db.delete(standing)
            removed += 1

    character.standings_synced_at = now
    character.last_synced_at = now
    return {"created": created, "updated": updated, "removed": removed, "total": len(seen)}
