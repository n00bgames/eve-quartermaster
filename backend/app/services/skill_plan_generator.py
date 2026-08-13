from __future__ import annotations

from collections import deque
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CharacterFitting, CharacterFittingItem, EveType
from app.services.fitting_simulator import dogma_for_types, required_skills_from_attrs


def merge_requirement(target: dict[int, dict[str, Any]], skill_type_id: int, level: int, source: str) -> bool:
    existing = target.get(skill_type_id)
    if existing is None:
        target[skill_type_id] = {"skill_type_id": skill_type_id, "target_level": level, "introduced_by": [source]}
        return True
    changed = level > existing["target_level"]
    existing["target_level"] = max(existing["target_level"], level)
    if source not in existing["introduced_by"]:
        existing["introduced_by"].append(source)
    return changed


def generate_fitting_skill_plan(db: Session, fitting_id: int) -> dict[str, Any]:
    fitting = db.scalar(
        select(CharacterFitting).options(
            selectinload(CharacterFitting.ship_type),
            selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.item_type),
            selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.charge_type),
        ).where(CharacterFitting.id == fitting_id)
    )
    if fitting is None:
        raise ValueError("Fitting not found")
    source_types: list[tuple[int, str]] = [(fitting.ship_type_id, f"Hull: {fitting.ship_type.name if fitting.ship_type else fitting.ship_type_id}")]
    for item in fitting.items:
        source_types.append((item.type_id, f"{item.flag}: {item.item_type.name if item.item_type else item.type_id}"))
        if item.charge_type_id:
            source_types.append((item.charge_type_id, f"Charge/script: {item.charge_type.name if item.charge_type else item.charge_type_id}"))
    dogma = dogma_for_types(db, {type_id for type_id, _ in source_types})
    requirements: dict[int, dict[str, Any]] = {}
    queue: deque[tuple[int, int, str]] = deque()
    for type_id, source in source_types:
        for requirement in required_skills_from_attrs(dogma.get(type_id, {})):
            queue.append((requirement["skill_type_id"], requirement["required_level"], source))
    expanded_at: dict[int, int] = {}
    while queue:
        skill_id, level, source = queue.popleft()
        merge_requirement(requirements, skill_id, level, source)
        if expanded_at.get(skill_id, 0) >= level:
            continue
        expanded_at[skill_id] = level
        skill_dogma = dogma_for_types(db, {skill_id}).get(skill_id, {})
        for prerequisite in required_skills_from_attrs(skill_dogma):
            queue.append((prerequisite["skill_type_id"], prerequisite["required_level"], f"Prerequisite for skill {skill_id}"))
    names = {row.type_id: row.name for row in db.scalars(select(EveType).where(EveType.type_id.in_(requirements))).all()}
    entries = sorted(requirements.values(), key=lambda row: names.get(row["skill_type_id"], str(row["skill_type_id"])).lower())
    for order, entry in enumerate(entries):
        entry["skill_name"] = names.get(entry["skill_type_id"], f"Type {entry['skill_type_id']}")
        entry["sort_order"] = order
    return {
        "fitting_id": fitting.id,
        "fitting_name": fitting.name,
        "entries": entries,
        "data_source": "Imported EVE SDE type dogma attributes",
        "complete": bool(dogma),
        "warnings": [] if dogma else ["No SDE dogma requirements were available; no requirements were fabricated."],
    }
