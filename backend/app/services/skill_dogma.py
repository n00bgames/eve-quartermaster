from __future__ import annotations

import html
import re
from collections import defaultdict
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models import EveDogmaAttribute, EveDogmaEffect, EveGroup, EveType, EveTypeDogmaAttribute, EveTypeDogmaEffect
from app.services.sde_importer import SdeSource, localized_text


PERCENT_UNITS = {105, 109, 111, 121}
ATTRIBUTE_LABELS = {
    "cpuNeedBonus": "CPU need for weapon modules",
    "damageMultiplierBonus": "turret damage",
    "maxActiveDroneBonus": "active drones controlled",
    "maxFlightTimeBonus": "missile flight time",
}


def _plain_text(value: Any) -> str:
    raw = localized_text(value, "")
    without_tags = re.sub(r"<[^>]+>", "", raw)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _bonus_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, dict) or row.get("bonus") is None:
            continue
        text = _plain_text(row.get("bonusText"))
        if text:
            rows.append({
                "value": float(row["bonus"]),
                "unit_id": int(row["unitID"]) if row.get("unitID") is not None else None,
                "text": text,
                "importance": int(row.get("importance") or 0),
            })
    return sorted(rows, key=lambda item: (item["importance"], item["text"]))


@lru_cache(maxsize=2)
def _type_bonus_index(source_path: str) -> dict[int, dict[int, list[dict[str, Any]]]]:
    """Index typeBonus.yaml by skill type, then by affected item type."""
    source = SdeSource(source_path)
    try:
        try:
            data = source.load_yaml("type_bonuses")
        except FileNotFoundError:
            return {}
    finally:
        source.close()

    index: dict[int, dict[int, list[dict[str, Any]]]] = defaultdict(dict)
    for raw_affected_type_id, payload in data.items():
        skill_rows = payload.get("types") if isinstance(payload, dict) else None
        if not isinstance(skill_rows, dict):
            continue
        for raw_skill_type_id, bonuses in skill_rows.items():
            rows = _bonus_rows(bonuses)
            if rows:
                index[int(raw_skill_type_id)][int(raw_affected_type_id)] = rows
    return dict(index)


def _attribute_label(name: str, display_name: str | None) -> str:
    if display_name:
        return display_name
    if name in ATTRIBUTE_LABELS:
        return ATTRIBUTE_LABELS[name]
    label = re.sub(r"Bonus$", "", name)
    label = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", label)
    return label.replace("max ", "maximum ").strip().lower()


def _direct_bonus_text(label: str, value: float, unit_id: int | None) -> str:
    if unit_id in PERCENT_UNITS:
        if value < 0 and label.endswith(" reduction"):
            label = label.removesuffix(" reduction")
        return f"{'reduction to' if value < 0 else 'bonus to'} {label}"
    return label


def _attribute_map(db: Session, type_id: int) -> dict[str, tuple[EveTypeDogmaAttribute, EveDogmaAttribute]]:
    rows = db.execute(
        select(EveTypeDogmaAttribute, EveDogmaAttribute)
        .join(EveDogmaAttribute, EveDogmaAttribute.attribute_id == EveTypeDogmaAttribute.attribute_id)
        .where(EveTypeDogmaAttribute.type_id == type_id)
    ).all()
    return {attribute.name: (type_value, attribute) for type_value, attribute in rows}


def _effect_rows(db: Session, type_id: int) -> list[EveDogmaEffect]:
    return list(db.scalars(
        select(EveDogmaEffect)
        .join(EveTypeDogmaEffect, EveTypeDogmaEffect.effect_id == EveDogmaEffect.effect_id)
        .where(EveTypeDogmaEffect.type_id == type_id)
    ).all())


def _modifier_targets(effects: list[EveDogmaEffect], local_attribute_ids: set[int]) -> tuple[set[int], set[int], set[int]]:
    bonus_attribute_ids: set[int] = set()
    group_ids: set[int] = set()
    required_skill_ids: set[int] = set()
    for effect in effects:
        for modifier in effect.modifier_info or []:
            modified_id = modifier.get("modifiedAttributeID")
            if modifier.get("modifyingAttributeID") == 280 and modified_id in local_attribute_ids and effect.effect_id != 132:
                bonus_attribute_ids.add(int(modified_id))
            if modifier.get("groupID") is not None:
                group_ids.add(int(modifier["groupID"]))
            if modifier.get("skillTypeID") is not None:
                required_skill_ids.add(int(modifier["skillTypeID"]))
    return bonus_attribute_ids, group_ids, required_skill_ids


def build_skill_dogma(db: Session, skill_type_id: int) -> dict[str, Any] | None:
    skill = db.scalar(select(EveType).where(EveType.type_id == skill_type_id))
    if skill is None:
        return None

    attributes = _attribute_map(db, skill_type_id)
    effects = _effect_rows(db, skill_type_id)
    local_attribute_ids = {row.attribute_id for row, _ in attributes.values()}
    bonus_attribute_ids, target_group_ids, target_skill_ids = _modifier_targets(effects, local_attribute_ids)

    prerequisites: list[dict[str, Any]] = []
    prerequisite_ids: list[int] = []
    for slot in range(1, 7):
        required = attributes.get(f"requiredSkill{slot}")
        if required is None:
            continue
        required_type_id = int(required[0].value)
        level_row = attributes.get(f"requiredSkill{slot}Level")
        prerequisite_ids.append(required_type_id)
        prerequisites.append({
            "type_id": required_type_id,
            "name": f"Type {required_type_id}",
            "level": int(level_row[0].value) if level_row is not None else 1,
        })
    if prerequisite_ids:
        names = {row.type_id: row.name for row in db.scalars(select(EveType).where(EveType.type_id.in_(prerequisite_ids))).all()}
        for prerequisite in prerequisites:
            prerequisite["name"] = names.get(prerequisite["type_id"], prerequisite["name"])

    direct_bonuses: list[dict[str, Any]] = []
    for type_value, attribute in attributes.values():
        if attribute.attribute_id not in bonus_attribute_ids:
            continue
        label = _attribute_label(attribute.name, attribute.display_name)
        direct_bonuses.append({
            "value": float(type_value.value),
            "unit_id": attribute.unit_id,
            "text": _direct_bonus_text(label, float(type_value.value), attribute.unit_id),
            "attribute_id": attribute.attribute_id,
            "attribute_name": attribute.name,
        })

    affected_bonus_rows = _type_bonus_index(get_settings().sde_source_path).get(skill_type_id, {})
    affected_type_ids = set(affected_bonus_rows)
    affected_types = {
        row.type_id: row
        for row in db.scalars(
            select(EveType)
            .options(selectinload(EveType.group).selectinload(EveGroup.category))
            .where(EveType.type_id.in_(affected_type_ids))
        ).all()
    } if affected_type_ids else {}

    bonus_profiles: list[dict[str, Any]] = []
    affected: list[dict[str, Any]] = []
    affected_categories: set[str] = set()
    for affected_type_id, bonuses in affected_bonus_rows.items():
        item = affected_types.get(affected_type_id)
        group = item.group if item else None
        category = group.category if group else None
        item_name = item.name if item else f"Type {affected_type_id}"
        group_name = group.name if group else None
        category_name = category.name if category else None
        affected.append({"type_id": affected_type_id, "name": item_name, "group_name": group_name, "category_name": category_name})
        if category_name or group_name:
            affected_categories.add(" · ".join(part for part in (category_name, group_name) if part))
        bonus_profiles.append({
            "affected_type_id": affected_type_id,
            "affected_type_name": item_name,
            "group_name": group_name,
            "category_name": category_name,
            "bonuses": bonuses,
        })

    if target_group_ids:
        for group in db.scalars(select(EveGroup).where(EveGroup.group_id.in_(target_group_ids))).all():
            affected_categories.add(group.name)
    if target_skill_ids:
        for target_skill in db.scalars(select(EveType).where(EveType.type_id.in_(target_skill_ids))).all():
            affected_categories.add(f"Items requiring {target_skill.name}")
    if any(modifier.get("domain") == "charID" for effect in effects for modifier in (effect.modifier_info or [])):
        affected_categories.add("Character-wide effects")

    primary = attributes.get("primaryAttribute")
    secondary = attributes.get("secondaryAttribute")
    attribute_reference_ids = [int(row[0].value) for row in (primary, secondary) if row is not None]
    reference_names = {
        row.attribute_id: row.display_name or _attribute_label(row.name, None).title()
        for row in db.scalars(select(EveDogmaAttribute).where(EveDogmaAttribute.attribute_id.in_(attribute_reference_ids))).all()
    } if attribute_reference_ids else {}
    rank = attributes.get("skillTimeConstant")
    return {
        "type_id": skill.type_id,
        "name": skill.name,
        "description": _plain_text(skill.description),
        "rank": float(rank[0].value) if rank is not None else None,
        "primary_attribute": reference_names.get(int(primary[0].value)) if primary is not None else None,
        "secondary_attribute": reference_names.get(int(secondary[0].value)) if secondary is not None else None,
        "prerequisites": prerequisites,
        "direct_bonuses": sorted(direct_bonuses, key=lambda item: item["text"]),
        "bonus_profiles": sorted(bonus_profiles, key=lambda item: item["affected_type_name"]),
        "affected": sorted(affected, key=lambda item: item["name"]),
        "affected_categories": sorted(affected_categories),
        "dogma_effect_ids": sorted(effect.effect_id for effect in effects),
    }
