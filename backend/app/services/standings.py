from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path, PurePosixPath
import re
from typing import Any
import zipfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import CharacterSkill, CharacterStanding, EveCharacter

STANDING_SOURCE_TYPES = {"agent", "npc_corp", "faction"}
STANDING_SKILL_TYPE_IDS = {
    "social": 3355,
    "diplomacy": 3357,
    "connections": 3359,
    "criminal_connections": 3361,
}

# Criminal Connections applies to positive standings with NPCs belonging to a
# faction that CONCORD considers criminal. These are the mission-bearing pirate
# factions represented by character standings.
CRIMINAL_FACTION_IDS = {
    500009,  # The Syndicate
    500010,  # Guristas Pirates
    500011,  # Angel Cartel
    500012,  # Blood Raider Covenant
    500019,  # Sansha's Nation
    500020,  # Serpentis
}

_TOP_LEVEL_ID = re.compile(r"^(\d+):\s*$")
_CORPORATION_ID = re.compile(r"^  corporationID:\s*(\d+)\s*$")
_FACTION_ID = re.compile(r"^  factionID:\s*(\d+)\s*$")


def _sde_lines(source_path: str, filename: str):
    path = Path(source_path)
    if path.is_dir():
        for candidate in (path / "fsd" / filename, path / filename):
            if candidate.exists():
                with candidate.open("r", encoding="utf-8") as handle:
                    yield from handle
                return
        raise FileNotFoundError(f"{filename} was not found under {source_path}")

    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            member = next(
                (name for name in archive.namelist() if PurePosixPath(name).name == filename),
                None,
            )
            if member is None:
                raise FileNotFoundError(f"{filename} was not found in {source_path}")
            with archive.open(member) as raw_handle:
                for raw_line in raw_handle:
                    yield raw_line.decode("utf-8")
            return

    raise FileNotFoundError(f"SDE source path was not found: {source_path}")


def _parse_child_id(source_path: str, filename: str, field_pattern: re.Pattern[str]) -> dict[int, int]:
    values: dict[int, int] = {}
    current_id: int | None = None
    for line in _sde_lines(source_path, filename):
        top_level = _TOP_LEVEL_ID.match(line)
        if top_level:
            current_id = int(top_level.group(1))
            continue
        if current_id is None:
            continue
        child = field_pattern.match(line)
        if child:
            values[current_id] = int(child.group(1))
    return values


@lru_cache(maxsize=4)
def npc_standing_affiliations(source_path: str | None = None) -> tuple[dict[int, int], dict[int, int]]:
    resolved_path = source_path or get_settings().sde_source_path
    try:
        corporation_factions = _parse_child_id(resolved_path, "npcCorporations.yaml", _FACTION_ID)
        agent_corporations = _parse_child_id(resolved_path, "npcCharacters.yaml", _CORPORATION_ID)
    except (FileNotFoundError, OSError, UnicodeError, zipfile.BadZipFile):
        return {}, {}
    return corporation_factions, agent_corporations


def character_standing_skill_levels(db: Session, character_id: int) -> dict[str, int]:
    by_type_id = {
        skill_type_id: int(active_level or 0)
        for skill_type_id, active_level in db.execute(
            select(CharacterSkill.skill_type_id, CharacterSkill.active_skill_level).where(
                CharacterSkill.character_id == character_id,
                CharacterSkill.skill_type_id.in_(STANDING_SKILL_TYPE_IDS.values()),
            )
        ).all()
    }
    return {
        name: max(0, min(5, by_type_id.get(type_id, 0)))
        for name, type_id in STANDING_SKILL_TYPE_IDS.items()
    }


def source_faction_id(
    source_type: str,
    source_eve_id: int,
    affiliations: tuple[dict[int, int], dict[int, int]],
) -> int | None:
    corporation_factions, agent_corporations = affiliations
    if source_type == "faction":
        return source_eve_id
    if source_type == "npc_corp":
        return corporation_factions.get(source_eve_id)
    if source_type == "agent":
        corporation_id = agent_corporations.get(source_eve_id)
        return corporation_factions.get(corporation_id) if corporation_id is not None else None
    return None


def effective_npc_standing(
    base_standing: float,
    source_type: str,
    source_eve_id: int,
    skill_levels: dict[str, int],
    affiliations: tuple[dict[int, int], dict[int, int]] | None = None,
) -> tuple[float, str | None, int]:
    skill_key: str | None = None
    if base_standing < 0:
        skill_key = "diplomacy"
    elif base_standing > 0:
        faction_id = source_faction_id(source_type, source_eve_id, affiliations or ({}, {}))
        skill_key = "criminal_connections" if faction_id in CRIMINAL_FACTION_IDS else "connections"

    skill_level = int(skill_levels.get(skill_key, 0)) if skill_key else 0
    if skill_level <= 0:
        return base_standing, None, 0

    modified = base_standing + ((10.0 - base_standing) * (0.04 * skill_level))
    skill_name = skill_key.replace("_", " ").title()
    return max(-10.0, min(10.0, modified)), skill_name, skill_level


def serialize_character_standing(
    row: CharacterStanding,
    *,
    skill_levels: dict[str, int] | None = None,
    affiliations: tuple[dict[int, int], dict[int, int]] | None = None,
) -> dict[str, Any]:
    base_standing = float(row.standing)
    modified_standing, modifier_skill, modifier_skill_level = effective_npc_standing(
        base_standing,
        row.source_type,
        row.source_eve_id,
        skill_levels or {},
        affiliations,
    )
    return {
        "id": row.id,
        "source_type": row.source_type,
        "source_eve_id": row.source_eve_id,
        "source_name": row.source_name,
        "standing": base_standing,
        "base_standing": base_standing,
        "modified_standing": modified_standing,
        "modifier_skill": modifier_skill,
        "modifier_skill_level": modifier_skill_level,
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
