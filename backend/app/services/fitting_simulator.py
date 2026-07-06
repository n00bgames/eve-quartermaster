from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CharacterFitting, CharacterFittingItem, CharacterSkill, EveCharacter, EveDogmaAttribute, EveDogmaEffect, EveGroup, EveType, EveTypeDogmaAttribute, EveTypeDogmaEffect

FITTED_SLOT_PREFIXES = {"HiSlot", "MedSlot", "LoSlot", "RigSlot", "SubSystemSlot", "ServiceSlot"}
CPU_MANAGEMENT_TYPE_ID = 3426
POWER_GRID_MANAGEMENT_TYPE_ID = 3413
WEAPON_UPGRADES_TYPE_ID = 3318
ADVANCED_WEAPON_UPGRADES_TYPE_ID = 11207
MINING_UPGRADES_TYPE_ID = 22578
SHIELD_UPGRADES_TYPE_ID = 3425
SHIELD_MANAGEMENT_TYPE_ID = 3416
MECHANICS_TYPE_ID = 3392
HULL_UPGRADES_TYPE_ID = 3394
NAVIGATION_TYPE_ID = 3449
MISSILE_LAUNCHER_OPERATION_TYPE_ID = 3319
TORPEDOES_TYPE_ID = 3325
CRUISE_MISSILES_TYPE_ID = 3326
WARHEAD_UPGRADES_TYPE_ID = 20315
RAPID_LAUNCH_TYPE_ID = 21071
CRUISE_MISSILE_SPECIALIZATION_TYPE_ID = 20212
TORPEDO_SPECIALIZATION_TYPE_ID = 20213
DAMAGE_ATTRS = ("emDamage", "thermalDamage", "kineticDamage", "explosiveDamage")
DAMAGE_TYPES = ("em", "thermal", "kinetic", "explosive")
RESISTANCE_ATTRS = {
    "shield": (
        ("shieldEmDamageResonance",),
        ("shieldThermalDamageResonance",),
        ("shieldKineticDamageResonance",),
        ("shieldExplosiveDamageResonance",),
    ),
    "armor": (
        ("armorEmDamageResonance",),
        ("armorThermalDamageResonance",),
        ("armorKineticDamageResonance",),
        ("armorExplosiveDamageResonance",),
    ),
    "structure": (
        ("hullEmDamageResonance", "emDamageResonance"),
        ("hullThermalDamageResonance", "thermalDamageResonance"),
        ("hullKineticDamageResonance", "kineticDamageResonance"),
        ("hullExplosiveDamageResonance", "explosiveDamageResonance"),
    ),
}
STACKING_PENALTIES = (1.0, 0.8708869, 0.5705831, 0.2829552, 0.1059926, 0.0299912, 0.0064102)
RESISTANCE_BONUS_ATTRS = {
    "em": ("emDamageResistanceBonus", "shieldEmDamageResistanceBonus", "armorEmDamageResistanceBonus"),
    "thermal": ("thermalDamageResistanceBonus", "shieldThermalDamageResistanceBonus", "armorThermalDamageResistanceBonus"),
    "kinetic": ("kineticDamageResistanceBonus", "shieldKineticDamageResistanceBonus", "armorKineticDamageResistanceBonus"),
    "explosive": ("explosiveDamageResistanceBonus", "shieldExplosiveDamageResistanceBonus", "armorExplosiveDamageResistanceBonus"),
}
SLOT_CAPACITY_ATTRS = {
    "HiSlot": ("hiSlots", "High slots"),
    "MedSlot": ("medSlots", "Medium slots"),
    "LoSlot": ("lowSlots", "Low slots"),
    "RigSlot": ("rigSlots", "Rigs"),
    "SubSystemSlot": ("subSystemSlot", "Subsystems"),
    "ServiceSlot": ("serviceSlots", "Services"),
}


def normalize_attr(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def slot_prefix(flag: str) -> str:
    normalized = flag.lower()
    for prefix in ["HiSlot", "MedSlot", "LoSlot", "RigSlot", "SubSystemSlot", "ServiceSlot", "DroneBay", "FighterBay", "Cargo"]:
        if flag.startswith(prefix):
            return prefix
    if "cargo" in normalized:
        return "Cargo"
    return "Other"


def item_state(item: CharacterFittingItem) -> str:
    state = str(getattr(item, "simulation_state", None) or "online").lower()
    return state if state in {"offline", "online", "active", "overheated"} else "online"


def item_is_online(item: CharacterFittingItem) -> bool:
    return item_state(item) != "offline"


def item_is_running(item: CharacterFittingItem) -> bool:
    return item_state(item) in {"active", "overheated"}


def item_is_overheated(item: CharacterFittingItem, global_heat: bool, attrs: dict[str, float]) -> bool:
    if not item_is_online(item):
        return False
    if item_state(item) == "overheated":
        return True
    heat_attrs = (
        "overloadRofBonus",
        "overloadDamageModifier",
        "overloadSpeedFactorBonus",
        "overloadHardeningBonus",
        "overloadRangeBonus",
        "overloadDurationBonus",
        "overloadArmorDamageAmount",
        "overloadShieldBonus",
    )
    return bool(item_is_running(item) and global_heat and any(attr_value(attrs, name) is not None for name in heat_attrs))


def dogma_for_types(db: Session, type_ids: set[int]) -> dict[int, dict[str, float]]:
    if not type_ids:
        return {}
    rows = db.execute(
        select(EveTypeDogmaAttribute.type_id, EveDogmaAttribute.name, EveTypeDogmaAttribute.value)
        .join(EveDogmaAttribute, EveDogmaAttribute.attribute_id == EveTypeDogmaAttribute.attribute_id)
        .where(EveTypeDogmaAttribute.type_id.in_(type_ids))
    ).all()
    result: dict[int, dict[str, float]] = {}
    for type_id, name, value in rows:
        result.setdefault(int(type_id), {})[normalize_attr(str(name))] = float(value)
    return result


def dogma_effects_for_types(db: Session, type_ids: set[int]) -> dict[int, list[dict[str, Any]]]:
    if not type_ids:
        return {}
    rows = db.execute(
        select(
            EveTypeDogmaEffect.type_id,
            EveDogmaEffect.effect_id,
            EveDogmaEffect.name,
            EveDogmaEffect.category_id,
            EveTypeDogmaEffect.is_default,
            EveDogmaEffect.modifier_info,
        )
        .join(EveDogmaEffect, EveDogmaEffect.effect_id == EveTypeDogmaEffect.effect_id)
        .where(EveTypeDogmaEffect.type_id.in_(type_ids))
    ).all()
    attribute_ids: set[int] = set()
    for *_, modifier_info in rows:
        for modifier in modifier_info or []:
            if not isinstance(modifier, dict):
                continue
            for key in ("modifiedAttributeID", "modifyingAttributeID"):
                value = modifier.get(key)
                if value is not None:
                    attribute_ids.add(int(value))

    attribute_names: dict[int, str] = {}
    if attribute_ids:
        name_rows = db.execute(select(EveDogmaAttribute.attribute_id, EveDogmaAttribute.name).where(EveDogmaAttribute.attribute_id.in_(attribute_ids))).all()
        attribute_names = {int(attribute_id): normalize_attr(str(name)) for attribute_id, name in name_rows}

    result: dict[int, list[dict[str, Any]]] = {}
    for type_id, effect_id, name, category_id, is_default, modifier_info in rows:
        normalized_modifiers: list[dict[str, Any]] = []
        for modifier in modifier_info or []:
            if not isinstance(modifier, dict):
                continue
            normalized = dict(modifier)
            modified_attribute_id = normalized.get("modifiedAttributeID")
            modifying_attribute_id = normalized.get("modifyingAttributeID")
            if modified_attribute_id is not None:
                normalized["modified_attribute_name"] = attribute_names.get(int(modified_attribute_id))
            if modifying_attribute_id is not None:
                normalized["modifying_attribute_name"] = attribute_names.get(int(modifying_attribute_id))
            normalized_modifiers.append(normalized)
        result.setdefault(int(type_id), []).append({
            "effect_id": int(effect_id),
            "name": str(name),
            "category_id": int(category_id) if category_id is not None else None,
            "is_default": bool(is_default),
            "modifier_info": normalized_modifiers,
        })
    return result


def attr_value(attrs: dict[str, float], *names: str) -> float | None:
    for name in names:
        value = attrs.get(normalize_attr(name))
        if value is not None:
            return value
    return None


def character_skill_levels(db: Session, character_id: int) -> dict[int, int]:
    rows = db.execute(
        select(CharacterSkill.skill_type_id, CharacterSkill.active_skill_level, CharacterSkill.trained_skill_level)
        .where(CharacterSkill.character_id == character_id)
    ).all()
    return {int(skill_id): int(active_level if active_level is not None else trained_level or 0) for skill_id, active_level, trained_level in rows}


def character_skill_levels_by_name(db: Session, character_id: int) -> dict[str, int]:
    rows = db.execute(
        select(EveType.name, CharacterSkill.active_skill_level, CharacterSkill.trained_skill_level)
        .select_from(CharacterSkill)
        .join(EveType, EveType.type_id == CharacterSkill.skill_type_id)
        .where(CharacterSkill.character_id == character_id)
    ).all()
    return {
        str(name): int(active_level if active_level is not None else trained_level or 0)
        for name, active_level, trained_level in rows
        if name
    }


def type_names(db: Session, type_ids: set[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    rows = db.execute(select(EveType.type_id, EveType.name).where(EveType.type_id.in_(type_ids))).all()
    return {int(type_id): str(name) for type_id, name in rows}


def type_group_names(db: Session, type_ids: set[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    rows = db.execute(
        select(EveType.type_id, EveGroup.name)
        .join(EveGroup, EveGroup.group_id == EveType.group_id)
        .where(EveType.type_id.in_(type_ids))
    ).all()
    return {int(type_id): str(name or "") for type_id, name in rows}


def skill_level(skill_levels: dict[int, int], skill_type_id: int) -> int:
    return max(0, min(5, int(skill_levels.get(skill_type_id, 0) or 0)))


def named_skill_level(skill_name_levels: dict[str, int], *names: str) -> int:
    normalized_levels = {normalize_attr(name): level for name, level in skill_name_levels.items()}
    return max((max(0, min(5, int(normalized_levels.get(normalize_attr(name), 0) or 0))) for name in names), default=0)


def ship_resource_capacity(ship_attrs: dict[str, float], skill_levels: dict[int, int]) -> dict[str, dict[str, float | bool | None]]:
    cpu_capacity = attr_value(ship_attrs, "cpuOutput")
    powergrid_capacity = attr_value(ship_attrs, "powerOutput")
    calibration_capacity = attr_value(ship_attrs, "upgradeCapacity")
    if cpu_capacity is not None:
        cpu_capacity *= 1 + 0.05 * skill_level(skill_levels, CPU_MANAGEMENT_TYPE_ID)
    if powergrid_capacity is not None:
        powergrid_capacity *= 1 + 0.05 * skill_level(skill_levels, POWER_GRID_MANAGEMENT_TYPE_ID)
    return {
        "cpu": {"used": 0.0, "capacity": cpu_capacity},
        "powergrid": {"used": 0.0, "capacity": powergrid_capacity},
        "calibration": {"used": 0.0, "capacity": calibration_capacity},
    }


def is_weapon_group(group_name: str) -> bool:
    normalized = group_name.lower()
    return "turret" in normalized or "launcher" in normalized or "smartbomb" in normalized


def module_is_passive(item: CharacterFittingItem, attrs: dict[str, float], group_name: str, item_name: str) -> bool:
    slot = slot_prefix(item.flag)
    family = f"{item_name} {group_name}".lower()
    if slot in {"RigSlot", "SubSystemSlot"}:
        return True
    if any(keyword in family for keyword in ("launcher", "turret", "smartbomb", "bomb launcher", "bastion", "siege", "triage", "industrial core", "shield booster", "armor repair", "hull repair", "capacitor booster", "afterburner", "microwarpdrive", "micro jump", "target painter", "webifier", "warp disrupt", "warp scramb", "tracking computer", "sensor booster", "guidance computer", "omnidirectional tracking", "remote ")):
        return False
    if attr_value(attrs, "capacitorNeed", "capacitorNeedHidden") not in (None, 0):
        return False
    if cycle_seconds(attrs) is not None and any(keyword in family for keyword in ("hardener", "invulnerability", "reactive", "field", "booster", "repairer", "propulsion")):
        return False
    return True


def item_effects_apply(item: CharacterFittingItem, attrs: dict[str, float], group_name: str, item_name: str) -> bool:
    return item_is_online(item) and (item_is_running(item) or module_is_passive(item, attrs, group_name, item_name))


def is_mining_upgrade_group(group_name: str) -> bool:
    return "mining upgrade" in group_name.lower()


def is_shield_extender_group(group_name: str) -> bool:
    return "shield extender" in group_name.lower()


def required_skills_from_attrs(attrs: dict[str, float]) -> list[dict[str, int]]:
    required: list[dict[str, int]] = []
    for index in range(1, 7):
        skill_id = attr_value(attrs, f"requiredSkill{index}")
        if skill_id is None or int(skill_id) <= 0:
            continue
        level = attr_value(attrs, f"requiredSkill{index}Level", f"requiredSkillLevel{index}")
        required.append({"skill_type_id": int(skill_id), "required_level": int(level or 1)})
    return required


def required_skill_type_ids(dogma: dict[int, dict[str, float]]) -> set[int]:
    skill_ids: set[int] = set()
    for attrs in dogma.values():
        for requirement in required_skills_from_attrs(attrs):
            skill_ids.add(requirement["skill_type_id"])
    return skill_ids


def item_resource_usage(item: CharacterFittingItem, attrs: dict[str, float], group_name: str, skill_levels: dict[int, int]) -> dict[str, float]:
    slot = slot_prefix(item.flag)
    if slot not in FITTED_SLOT_PREFIXES or not item_is_online(item):
        return {"cpu": 0.0, "powergrid": 0.0, "calibration": 0.0}
    quantity = max(1, int(item.quantity or 1))
    cpu = float(attr_value(attrs, "cpu") or 0)
    powergrid = float(attr_value(attrs, "power", "powergridUsage") or 0)
    if is_weapon_group(group_name):
        cpu *= max(0.0, 1 - 0.05 * skill_level(skill_levels, WEAPON_UPGRADES_TYPE_ID))
        powergrid *= max(0.0, 1 - 0.02 * skill_level(skill_levels, ADVANCED_WEAPON_UPGRADES_TYPE_ID))
    if is_mining_upgrade_group(group_name):
        cpu *= max(0.0, 1 - 0.05 * skill_level(skill_levels, MINING_UPGRADES_TYPE_ID))
    if is_shield_extender_group(group_name):
        powergrid *= max(0.0, 1 - 0.05 * skill_level(skill_levels, SHIELD_UPGRADES_TYPE_ID))
    return {
        "cpu": cpu * quantity,
        "powergrid": powergrid * quantity,
        "calibration": float(attr_value(attrs, "upgradeCost") or 0) * quantity if slot == "RigSlot" else 0.0,
    }



def safe_number(value: float | None, default: float = 0.0) -> float:
    return float(value) if value is not None else default


def dogma_multiplier(value: float | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    if number == 0:
        return None
    if abs(number) > 2:
        return 1 + number / 100.0
    return number


def stacking_raw_multiplier(values: list[float]) -> float:
    useful = [float(value) for value in values if value and value > 0 and abs(float(value) - 1.0) > 0.0001]
    useful.sort(key=lambda value: abs(value - 1.0), reverse=True)
    result = 1.0
    for index, value in enumerate(useful):
        penalty = STACKING_PENALTIES[index] if index < len(STACKING_PENALTIES) else 0.0
        result *= 1 + (value - 1.0) * penalty
    return result


def stacking_multiplier(values: list[float]) -> float:
    multipliers = [dogma_multiplier(value) for value in values]
    return stacking_raw_multiplier([value for value in multipliers if value is not None])


def percent_bonus_multiplier(values: list[float]) -> float:
    return stacking_raw_multiplier([1 + float(value) / 100.0 for value in values if value])


def module_quantity(item: CharacterFittingItem) -> int:
    return max(1, int(item.quantity or 1))


def damage_profile(attrs: dict[str, float]) -> dict[str, float]:
    return {label: float(attr_value(attrs, attr_name) or 0.0) for label, attr_name in zip(DAMAGE_TYPES, DAMAGE_ATTRS)}


def scale_damage_profile(profile: dict[str, float], multiplier: float) -> dict[str, float]:
    return {label: float(profile.get(label, 0.0)) * multiplier for label in DAMAGE_TYPES}


def add_damage_profile(total: dict[str, float], profile: dict[str, float]) -> None:
    for label in DAMAGE_TYPES:
        total[label] = total.get(label, 0.0) + float(profile.get(label, 0.0))


def damage_amount(attrs: dict[str, float]) -> float:
    return sum(damage_profile(attrs).values())


def weapon_range(
    attrs: dict[str, float],
    charge_attrs: dict[str, float],
    group_name: str,
    *,
    missile_velocity_multiplier: float = 1.0,
    missile_flight_time_multiplier: float = 1.0,
    missile_range_multiplier: float = 1.0,
    turret_range_multiplier: float = 1.0,
) -> dict[str, float | None]:
    range_multiplier = dogma_multiplier(attr_value(charge_attrs, "rangeMultiplier", "maxRangeBonus")) or 1.0
    if is_launcher_group(group_name):
        velocity = attr_value(charge_attrs, "maxVelocity", "entityCruiseSpeed", "velocity")
        flight_ms = attr_value(charge_attrs, "explosionDelay", "duration", "flightTime")
        if velocity and flight_ms:
            effective_velocity = float(velocity) * missile_velocity_multiplier
            effective_flight_s = float(flight_ms) / 1000.0 * missile_flight_time_multiplier
            range_m = effective_velocity * effective_flight_s * range_multiplier * missile_range_multiplier
        else:
            effective_velocity = None
            effective_flight_s = None
            range_m = None
        return {
            "range_m": range_m,
            "optimal_m": range_m,
            "falloff_m": None,
            "missile_velocity_m_s": effective_velocity,
            "missile_flight_time_s": effective_flight_s,
        }
    optimal = attr_value(attrs, "maxRange", "optimalRange")
    falloff = attr_value(attrs, "falloff", "falloffRange")
    total_range_multiplier = range_multiplier * turret_range_multiplier
    optimal_m = float(optimal) * total_range_multiplier if optimal else None
    falloff_m = float(falloff) * total_range_multiplier if falloff else None
    range_m = (optimal_m or 0.0) + (falloff_m or 0.0) if optimal_m or falloff_m else None
    return {"range_m": range_m, "optimal_m": optimal_m, "falloff_m": falloff_m}


def drone_control_range_m(
    skill_name_levels: dict[str, int],
    additive_bonus_m: float = 0.0,
    multipliers: list[float] | None = None,
    base_range_m: float | None = None,
) -> float:
    base_range = 20_000.0 if base_range_m is None else float(base_range_m)
    effective_range_m = (
        base_range
        + 5_000.0 * named_skill_level(skill_name_levels, "Drone Avionics", "Scout Drone Operation")
        + 3_000.0 * named_skill_level(skill_name_levels, "Advanced Drone Avionics", "Electronic Warfare Drone Interfacing")
    )
    return (effective_range_m + additive_bonus_m) * stacking_raw_multiplier(multipliers or [])


def drone_detail_stats(
    attrs: dict[str, float],
    skill_name_levels: dict[str, int],
    quantity: int,
    cycle: float | None,
    control_range_m: float,
) -> dict[str, float | None]:
    velocity = attr_value(attrs, "maxVelocity", "entityCruiseSpeed", "orbitVelocity")
    if velocity is not None:
        velocity = float(velocity) * (1 + 0.05 * named_skill_level(skill_name_levels, "Drone Navigation"))

    repair_amount = (
        safe_number(attr_value(attrs, "shieldBonus", "shieldTransferAmount", "shieldBoostAmount"))
        + safe_number(attr_value(attrs, "armorDamageAmount", "armorHPRepaired", "armorHpRepaired", "armorTransferAmount"))
        + safe_number(attr_value(attrs, "structureDamageAmount", "hullDamageAmount", "hullRepairAmount", "structureTransferAmount"))
    )
    repair_hps = repair_amount * quantity / cycle if repair_amount > 0 and cycle else None

    mining_amount = attr_value(attrs, "miningAmount", "miningYield", "harvestAmount")
    if mining_amount is not None:
        mining_amount = float(mining_amount) * quantity * (1 + 0.05 * named_skill_level(skill_name_levels, "Mining Drone Operation"))

    ecm_strength = max(
        safe_number(attr_value(attrs, "scanRadarStrengthBonus", "radarStrengthBonus")),
        safe_number(attr_value(attrs, "scanLadarStrengthBonus", "ladarStrengthBonus")),
        safe_number(attr_value(attrs, "scanMagnetometricStrengthBonus", "magnetometricStrengthBonus")),
        safe_number(attr_value(attrs, "scanGravimetricStrengthBonus", "gravimetricStrengthBonus")),
        safe_number(attr_value(attrs, "ecmStrength", "ewarStrength")),
    )

    return {
        "velocity_m_s": velocity,
        "control_range_m": control_range_m,
        "repair_hps": repair_hps,
        "mining_yield": mining_amount,
        "salvage_bonus": attr_value(attrs, "accessDifficultyBonus", "salvageAccessBonus", "salvageBonus"),
        "ecm_strength": ecm_strength if ecm_strength > 0 else None,
        "scramble_strength": attr_value(attrs, "warpScrambleStrength", "warpScrambleMaxStrength"),
    }


def resonance_profile(attrs: dict[str, float], layer: str) -> dict[str, float]:
    names = RESISTANCE_ATTRS[layer]
    labels = ("em", "thermal", "kinetic", "explosive")
    result: dict[str, float] = {}
    for label, candidates in zip(labels, names):
        resonance = attr_value(attrs, *candidates)
        result[label] = max(0.01, min(1.0, float(resonance))) if resonance is not None else 1.0
    return result


def resistance_profile_from_resonance(resonances: dict[str, float]) -> dict[str, float]:
    return {label: max(0.0, min(1.0, 1.0 - float(resonance))) for label, resonance in resonances.items()}


def resistance_profile(attrs: dict[str, float], layer: str) -> dict[str, float]:
    return resistance_profile_from_resonance(resonance_profile(attrs, layer))


def omni_ehp(hitpoints: float, resists: dict[str, float]) -> float:
    if hitpoints <= 0:
        return 0.0
    average_damage_taken = sum(max(0.01, 1.0 - value) for value in resists.values()) / max(1, len(resists))
    return hitpoints / average_damage_taken


def cycle_seconds(attrs: dict[str, float]) -> float | None:
    cycle_ms = attr_value(attrs, "speed", "duration", "activationTime")
    if cycle_ms is None or cycle_ms <= 0:
        return None
    return float(cycle_ms) / 1000.0


def is_launcher_group(group_name: str) -> bool:
    return "launcher" in group_name.lower()


def is_turret_group(group_name: str) -> bool:
    return "turret" in group_name.lower()


def is_drone_group(group_name: str) -> bool:
    normalized = group_name.lower()
    return "drone" in normalized or "fighter" in normalized


def charge_kind(name: str, group_name: str) -> str:
    haystack = f"{name} {group_name}".lower()
    if "light missile" in haystack:
        return "light missile"
    if "heavy assault missile" in haystack:
        return "heavy assault missile"
    if "heavy missile" in haystack:
        return "heavy missile"
    if "cruise missile" in haystack:
        return "cruise missile"
    if "torpedo" in haystack:
        return "torpedo"
    if "rocket" in haystack:
        return "rocket"
    if "missile" in haystack:
        return "missile"
    if "hybrid" in haystack or "charge" in haystack:
        return "hybrid charge"
    if "projectile" in haystack or "ammo" in haystack:
        return "projectile ammo"
    if "frequency crystal" in haystack or "crystal" in haystack:
        return "frequency crystal"
    if "bomb" in haystack:
        return "bomb"
    return "charge"


def charge_is_compatible_with_module(module_name: str, module_group: str, charge_name: str, charge_group: str) -> bool:
    module_text = f"{module_name} {module_group}".lower()
    charge_text = f"{charge_name} {charge_group}".lower()
    charge_is_xl = bool(re.search(r"(^|\s)xl(\s|$)", charge_text)) or "extra large" in charge_text
    module_is_xl = bool(re.search(r"(^|\s)xl(\s|$)", module_text)) or "capital" in module_text or "citadel" in module_text
    if "script" in charge_text:
        return bool(re.search(r"tracking computer|tracking link|sensor booster|remote sensor|guidance computer|guidance enhancer|missile guidance|omnidirectional tracking|warp disruption field", module_text))
    if "capacitor booster" in module_text or "ancillary shield booster" in module_text:
        return "cap booster" in charge_text or "capacitor booster" in charge_text
    if "rapid light" in module_text or "light missile" in module_text:
        return not charge_is_xl and "light missile" in charge_text
    if "heavy assault" in module_text:
        return not charge_is_xl and "heavy assault missile" in charge_text
    if "heavy missile" in module_text:
        return not charge_is_xl and "heavy missile" in charge_text and "assault" not in charge_text
    if "cruise" in module_text:
        return "cruise missile" in charge_text and charge_is_xl == module_is_xl
    if "torpedo" in module_text:
        return "torpedo" in charge_text and charge_is_xl == module_is_xl
    if "rocket" in module_text:
        return not charge_is_xl and "rocket" in charge_text
    if "launcher" in module_text:
        return not charge_is_xl and ("missile" in charge_text or "rocket" in charge_text or "torpedo" in charge_text)
    if "laser" in module_text:
        return "frequency crystal" in charge_text
    if "railgun" in module_text or "blaster" in module_text or "hybrid" in module_text:
        return "hybrid charge" in charge_text
    if "autocannon" in module_text or "artillery" in module_text or "projectile" in module_text:
        return "projectile ammo" in charge_text
    return False


def module_requires_skill(attrs: dict[str, float], skill_type_id: int) -> bool:
    for index in range(1, 7):
        value = attr_value(attrs, f"requiredSkill{index}")
        if value is not None and int(value) == skill_type_id:
            return True
    return False


def missile_charge_skill_id(kind: str) -> int | None:
    if "torpedo" in kind:
        return TORPEDOES_TYPE_ID
    if "cruise missile" in kind:
        return CRUISE_MISSILES_TYPE_ID
    return None


def missile_skill_damage_multiplier(kind: str, skill_levels: dict[int, int]) -> float:
    multiplier = 1 + 0.02 * skill_level(skill_levels, WARHEAD_UPGRADES_TYPE_ID)
    charge_skill_id = missile_charge_skill_id(kind)
    if charge_skill_id in {TORPEDOES_TYPE_ID, CRUISE_MISSILES_TYPE_ID}:
        multiplier *= 1 + 0.05 * skill_level(skill_levels, charge_skill_id)
    return multiplier


def missile_skill_rof_multiplier(kind: str, module_attrs: dict[str, float], skill_levels: dict[int, int]) -> float:
    multiplier = max(0.01, 1 - 0.02 * skill_level(skill_levels, MISSILE_LAUNCHER_OPERATION_TYPE_ID))
    multiplier *= max(0.01, 1 - 0.03 * skill_level(skill_levels, RAPID_LAUNCH_TYPE_ID))
    if "torpedo" in kind and module_requires_skill(module_attrs, TORPEDO_SPECIALIZATION_TYPE_ID):
        multiplier *= max(0.01, 1 - 0.02 * skill_level(skill_levels, TORPEDO_SPECIALIZATION_TYPE_ID))
    if "cruise missile" in kind and module_requires_skill(module_attrs, CRUISE_MISSILE_SPECIALIZATION_TYPE_ID):
        multiplier *= max(0.01, 1 - 0.02 * skill_level(skill_levels, CRUISE_MISSILE_SPECIALIZATION_TYPE_ID))
    return multiplier


def missile_skill_velocity_multiplier(skill_name_levels: dict[str, int]) -> float:
    return 1 + 0.1 * named_skill_level(skill_name_levels, "Missile Projection")


def missile_skill_flight_time_multiplier(skill_name_levels: dict[str, int]) -> float:
    return 1 + 0.1 * named_skill_level(skill_name_levels, "Missile Bombardment")


def ship_skill_bonus_level(attr_name: str, skill_name_levels: dict[str, int]) -> int:
    normalized = normalize_attr(attr_name)
    if "cb" in normalized or "caldari" in normalized:
        return named_skill_level(skill_name_levels, "Caldari Battleship")
    if "ab" in normalized or "amarr" in normalized:
        return named_skill_level(skill_name_levels, "Amarr Battleship")
    if "gb" in normalized or "gallente" in normalized:
        return named_skill_level(skill_name_levels, "Gallente Battleship")
    if "mb" in normalized or "minmatar" in normalized:
        return named_skill_level(skill_name_levels, "Minmatar Battleship")
    return 0


def per_level_bonus_multiplier(value: float | None, level: int) -> float:
    if value is None or level <= 0:
        return 1.0
    return max(0.01, 1 + float(value) / 100.0 * level)


def ship_missile_velocity_multiplier(ship_attrs: dict[str, float], kind: str, skill_name_levels: dict[str, int]) -> float:
    if not ("torpedo" in kind or "cruise missile" in kind):
        return 1.0
    multiplier = 1.0
    for attr_name in ("shipBonusCB", "shipBonusCB3", "shipBonusCBC1", "shipBonusCBC2"):
        value = attr_value(ship_attrs, attr_name)
        if value is None:
            continue
        # The Golem/Raven family uses Caldari Battleship bonus slots for missile projection.
        # Full hull-bonus fidelity will come from importing Dogma effects; this preserves the common missile path now.
        if normalize_attr(attr_name) == "shipbonuscb":
            multiplier *= per_level_bonus_multiplier(value, ship_skill_bonus_level(attr_name, skill_name_levels))
    direct_bonus = attr_value(ship_attrs, "missileVelocityBonus", "missileVelocityMultiplier")
    direct_multiplier = dogma_multiplier(direct_bonus)
    if direct_multiplier:
        multiplier *= direct_multiplier
    return multiplier


def ship_shield_boost_multiplier(ship_attrs: dict[str, float], skill_name_levels: dict[str, int]) -> float:
    multiplier = 1.0
    value = attr_value(ship_attrs, "shipBonus2CB")
    if value is not None:
        multiplier *= per_level_bonus_multiplier(value, named_skill_level(skill_name_levels, "Caldari Battleship"))
    direct_multiplier = dogma_multiplier(attr_value(ship_attrs, "shieldBoostMultiplier", "shieldBoostBonus", "shieldBoosterBonus"))
    if direct_multiplier:
        multiplier *= direct_multiplier
    return multiplier


def ship_missile_damage_multiplier(ship_attrs: dict[str, float], kind: str, skill_name_levels: dict[str, int]) -> float:
    multiplier = 1.0
    if "torpedo" in kind or "cruise missile" in kind:
        role_bonus = attr_value(ship_attrs, "eliteBonusViolatorsRole1")
        if role_bonus:
            multiplier *= 1 + float(role_bonus) / 100.0
        marauder_bonus = attr_value(ship_attrs, "eliteBonusViolators1")
        if marauder_bonus:
            multiplier *= per_level_bonus_multiplier(marauder_bonus, named_skill_level(skill_name_levels, "Caldari Marauder", "Marauders"))
    return multiplier


def matching_charge(module_name: str, module_group: str, charges: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not charges:
        return None
    module_haystack = f"{module_name} {module_group}".lower()
    if len(charges) == 1:
        return charges[0]
    preferred: list[str] = []
    if "rapid light missile" in module_haystack or "light missile" in module_haystack:
        preferred.append("light missile")
    if "heavy assault missile" in module_haystack:
        preferred.append("heavy assault missile")
    if "heavy missile" in module_haystack:
        preferred.append("heavy missile")
    if "cruise missile" in module_haystack:
        preferred.append("cruise missile")
    if "torpedo" in module_haystack:
        preferred.append("torpedo")
    if "rocket" in module_haystack:
        preferred.append("rocket")
    if "missile" in module_haystack:
        preferred.append("missile")
    if "hybrid" in module_haystack or "railgun" in module_haystack or "blaster" in module_haystack:
        preferred.append("hybrid charge")
    if "projectile" in module_haystack or "autocannon" in module_haystack or "artillery" in module_haystack:
        preferred.append("projectile ammo")
    if "laser" in module_haystack:
        preferred.append("frequency crystal")
    compatible_charges = [charge for charge in charges if charge_is_compatible_with_module(module_name, module_group, charge["name"], charge["group"])]
    if not compatible_charges:
        return None
    for kind in preferred:
        for charge in compatible_charges:
            if charge["kind"] == kind:
                return charge
    return compatible_charges[0]


def infer_resistance_layer(group_name: str, item_name: str, attrs: dict[str, float]) -> str | None:
    haystack = f"{group_name} {item_name}".lower()
    if any(attr_value(attrs, name) is not None for names in RESISTANCE_ATTRS["shield"] for name in names):
        return "shield"
    if any(attr_value(attrs, name) is not None for names in RESISTANCE_ATTRS["armor"] for name in names):
        return "armor"
    if any(attr_value(attrs, name) is not None for names in RESISTANCE_ATTRS["structure"] for name in names):
        return "structure"
    if "shield" in haystack:
        return "shield"
    if "armor" in haystack or "energized" in haystack or "plating" in haystack:
        return "armor"
    if "hull" in haystack or "damage control" in haystack:
        return "structure"
    return None


def direct_resonance_attr_names(layer: str, damage_type: str) -> tuple[str, ...]:
    index = ("em", "thermal", "kinetic", "explosive").index(damage_type)
    return RESISTANCE_ATTRS[layer][index]


def resistance_bonus_multiplier(values: list[float]) -> float:
    multipliers: list[float] = []
    for value in values:
        if value is None or float(value) == 0:
            continue
        number = float(value)
        if abs(number) > 2:
            multipliers.append(max(0.01, 1 - abs(number) / 100.0))
        else:
            multipliers.append(max(0.01, 1 - abs(1.0 - number)))
    return stacking_raw_multiplier(multipliers)


def collect_resistance_modifiers(attrs: dict[str, float], layer: str | None) -> tuple[dict[str, list[float]], dict[str, dict[str, list[float]]]]:
    layer_bonus = {damage: [] for damage in DAMAGE_TYPES}
    direct = {layer_name: {damage: [] for damage in DAMAGE_TYPES} for layer_name in RESISTANCE_ATTRS}
    for raw_name, value in attrs.items():
        name = normalize_attr(raw_name)
        if value is None:
            continue
        for damage_type in DAMAGE_TYPES:
            if damage_type not in name:
                continue
            if "resistancebonus" in name and layer:
                layer_bonus[damage_type].append(float(value))
            if "resonance" in name:
                target_layers = [layer] if layer else []
                if "shield" in name:
                    target_layers = ["shield"]
                elif "armor" in name:
                    target_layers = ["armor"]
                elif "hull" in name or "structure" in name:
                    target_layers = ["structure"]
                elif not target_layers:
                    target_layers = ["shield", "armor", "structure"]
                for target_layer in target_layers:
                    if target_layer in direct:
                        direct[target_layer][damage_type].append(float(value))
    return layer_bonus, direct


def apply_resistance_modifiers(
    resonances: dict[str, dict[str, float]],
    layer_bonus_mods: dict[str, dict[str, list[float]]],
    direct_resonance_mods: dict[str, dict[str, list[float]]],
) -> None:
    for layer, by_damage in direct_resonance_mods.items():
        for damage_type, values in by_damage.items():
            resonances[layer][damage_type] *= stacking_multiplier(values)
    for layer, by_damage in layer_bonus_mods.items():
        for damage_type, values in by_damage.items():
            resonances[layer][damage_type] *= resistance_bonus_multiplier(values)
    for layer in resonances:
        for damage_type in resonances[layer]:
            resonances[layer][damage_type] = max(0.01, min(1.0, resonances[layer][damage_type]))



def capacitor_charge_gj(attrs: dict[str, float]) -> float:
    return max(0.0, safe_number(attr_value(attrs, "capacitorBonus", "capacitorCapacityBonus", "capBonus")))


def capacitor_recharge_at_percent(capacity: float, recharge_seconds: float, percent: float) -> float:
    fraction = max(0.0, min(1.0, percent / 100.0))
    if capacity <= 0 or recharge_seconds <= 0 or fraction <= 0:
        return 0.0
    return (10.0 * capacity / recharge_seconds) * ((fraction ** 0.5) - fraction)


def capacitor_stable_percent(capacity: float, recharge_seconds: float, drain_per_second: float) -> float | None:
    if drain_per_second <= 0:
        return 100.0
    peak = capacity / recharge_seconds * 2.5 if capacity > 0 and recharge_seconds > 0 else 0.0
    if peak <= 0 or drain_per_second > peak:
        return None
    low = 25.0
    high = 100.0
    for _ in range(40):
        mid = (low + high) / 2.0
        if capacitor_recharge_at_percent(capacity, recharge_seconds, mid) >= drain_per_second:
            low = mid
        else:
            high = mid
    return max(0.0, min(100.0, low))


def capacitor_depletion_seconds(capacity: float, recharge_seconds: float, drain_per_second: float) -> float | None:
    if capacity <= 0 or drain_per_second <= 0:
        return None
    capacitor = capacity
    elapsed = 0.0
    step = 1.0
    # Eight hours is long enough to read as practically stable for this first-pass simulator.
    while capacitor > 0 and elapsed < 28_800:
        percent = capacitor / capacity * 100.0
        recharge = capacitor_recharge_at_percent(capacity, recharge_seconds, percent) if recharge_seconds > 0 else 0.0
        capacitor += (recharge - drain_per_second) * step
        elapsed += step
    return elapsed if capacitor <= 0 else None


def active_capacitor_use_per_second(items: list[CharacterFittingItem], dogma: dict[int, dict[str, float]], names: dict[int, str]) -> tuple[float, list[dict[str, Any]]]:
    total = 0.0
    rows: list[dict[str, Any]] = []
    for item in items:
        if not item_is_running(item):
            continue
        attrs = dogma.get(item.type_id, {})
        cap_need = attr_value(attrs, "capacitorNeed", "capacitorNeedHidden")
        cycle = cycle_seconds(attrs)
        if not cycle:
            continue
        gross_per_second = max(0.0, float(cap_need or 0.0)) / cycle * module_quantity(item)
        charge_attrs = dogma.get(int(item.charge_type_id), {}) if getattr(item, "charge_type_id", None) else {}
        injected_per_second = 0.0
        if "capacitor booster" in names.get(item.type_id, f"Type {item.type_id}").lower():
            injected_per_second = capacitor_charge_gj(charge_attrs) / cycle * module_quantity(item)
        per_second = gross_per_second - injected_per_second
        if abs(per_second) <= 0.0001:
            continue
        total += per_second
        rows.append({
            "name": names.get(item.type_id, f"Type {item.type_id}"),
            "gj_per_second": per_second,
            "cycle_seconds": cycle,
            "quantity": module_quantity(item),
        })
    rows.sort(key=lambda row: abs(row["gj_per_second"]), reverse=True)
    return max(0.0, total), rows[:8]


def compute_fitting_stats(
    fitting: CharacterFitting,
    dogma: dict[int, dict[str, float]],
    names: dict[int, str],
    group_names: dict[int, str],
    skill_levels: dict[int, int],
    skill_name_levels: dict[str, int],
    heat: bool = False,
) -> dict[str, Any]:
    ship_attrs = dogma.get(fitting.ship_type_id, {})
    shield_hp = safe_number(attr_value(ship_attrs, "shieldCapacity")) * (1 + 0.05 * skill_level(skill_levels, SHIELD_MANAGEMENT_TYPE_ID))
    armor_hp = safe_number(attr_value(ship_attrs, "armorHP")) * (1 + 0.05 * skill_level(skill_levels, HULL_UPGRADES_TYPE_ID))
    structure_hp = safe_number(attr_value(ship_attrs, "hp", "structureHP")) * (1 + 0.05 * skill_level(skill_levels, MECHANICS_TYPE_ID))
    shield_recharge_ms = attr_value(ship_attrs, "shieldRechargeRate")

    fitted_items = [item for item in fitting.items if slot_prefix(item.flag) in FITTED_SLOT_PREFIXES]
    active_fitted_items = [item for item in fitted_items if item_is_online(item)]
    bay_items = [item for item in fitting.items if slot_prefix(item.flag) in {"DroneBay", "FighterBay"}]
    cargo_items = [item for item in fitting.items if slot_prefix(item.flag) == "Cargo"]

    shield_hp_pct_mods: list[float] = []
    armor_hp_pct_mods: list[float] = []
    structure_hp_pct_mods: list[float] = []
    missile_damage_mods: list[float] = []
    missile_rof_mods: list[float] = []
    missile_velocity_mods: list[float] = []
    missile_flight_time_mods: list[float] = []
    missile_range_mods: list[float] = []
    turret_damage_mods: list[float] = []
    turret_rof_mods: list[float] = []
    turret_range_mods: list[float] = []
    drone_damage_mods: list[float] = []
    drone_control_bonus_m = 0.0
    drone_control_multipliers: list[float] = []
    velocity_multipliers: list[float] = []
    signature_multipliers: list[float] = []
    capacitor_multipliers: list[float] = []
    shield_repair_hps = 0.0
    armor_repair_hps = 0.0
    structure_repair_hps = 0.0
    shield_repair_multipliers: list[float] = []
    armor_repair_multipliers: list[float] = []
    structure_repair_multipliers: list[float] = []
    mass_addition = 0.0
    agility_multipliers: list[float] = []
    resonances = {
        "shield": resonance_profile(ship_attrs, "shield"),
        "armor": resonance_profile(ship_attrs, "armor"),
        "structure": resonance_profile(ship_attrs, "structure"),
    }
    layer_bonus_mods = {layer: {damage: [] for damage in ("em", "thermal", "kinetic", "explosive")} for layer in resonances}
    direct_resonance_mods = {layer: {damage: [] for damage in ("em", "thermal", "kinetic", "explosive")} for layer in resonances}

    for item in active_fitted_items:
        attrs = dogma.get(item.type_id, {})
        qty = module_quantity(item)
        group = group_names.get(item.type_id, "")
        name = names.get(item.type_id, f"Type {item.type_id}")
        if not item_effects_apply(item, attrs, group, name):
            continue
        overheated = item_is_overheated(item, heat, attrs)
        item_family = f"{name} {group}".lower()
        is_shield_family = "shield" in item_family
        is_prop_family = "afterburner" in item_family or "microwarpdrive" in item_family or "propulsion" in item_family
        capacity_bonus = attr_value(attrs, "capacityBonus", "shieldBonus")
        if capacity_bonus and is_shield_family:
            shield_hp += float(capacity_bonus) * qty
        shield_hp += safe_number(attr_value(attrs, "shieldCapacityBonusAdd")) * qty
        armor_hp += safe_number(attr_value(attrs, "armorHPBonusAdd", "armorHpBonusAdd")) * qty
        structure_hp += safe_number(attr_value(attrs, "hpBonusAdd", "structureHitpointBonusAdd")) * qty
        shield_pct = attr_value(attrs, "shieldCapacityBonus", "shieldCapacityBonus2")
        if shield_pct:
            shield_hp_pct_mods.extend([float(shield_pct)] * qty)
        armor_pct = attr_value(attrs, "armorHPBonus", "armorHpBonus")
        if armor_pct:
            armor_hp_pct_mods.extend([float(armor_pct)] * qty)
        structure_pct = attr_value(attrs, "hpBonus", "structureHitpointBonus")
        if structure_pct:
            structure_hp_pct_mods.extend([float(structure_pct)] * qty)

        missile_damage = attr_value(attrs, "missileDamageMultiplierBonus", "missileDamageMultiplier")
        if missile_damage:
            missile_damage_mods.extend([float(missile_damage)] * qty)
        bastion_missile_rof = dogma_multiplier(attr_value(attrs, "bastionMissileROFBonus"))
        if bastion_missile_rof:
            missile_rof_mods.extend([bastion_missile_rof] * qty)
        bastion_turret_rof = dogma_multiplier(attr_value(attrs, "bastionTurretROFBonus"))
        if bastion_turret_rof:
            turret_rof_mods.extend([bastion_turret_rof] * qty)
        for velocity_attr in ("missileVelocityBonus", "missileVelocityMultiplier", "missileVelocityBonusBonus"):
            velocity_multiplier = dogma_multiplier(attr_value(attrs, velocity_attr))
            if velocity_multiplier:
                missile_velocity_mods.extend([velocity_multiplier] * qty)
        for flight_attr in ("explosionDelayBonus", "flightTimeBonus", "explosionDelayBonusBonus"):
            flight_multiplier = dogma_multiplier(attr_value(attrs, flight_attr))
            if flight_multiplier:
                missile_flight_time_mods.extend([flight_multiplier] * qty)
        range_bonus = dogma_multiplier(attr_value(attrs, "maxRangeBonus", "rangeBonus", "rangeMultiplier"))
        if range_bonus:
            if "bastion" in item_family or "tracking computer" in item_family or "range" in item_family:
                turret_range_mods.extend([range_bonus] * qty)
            if "guidance computer" in item_family or "guidance enhancer" in item_family or "missile guidance" in item_family:
                missile_range_mods.extend([range_bonus] * qty)
        damage_bonus = attr_value(attrs, "damageMultiplierBonus")
        if damage_bonus:
            turret_damage_mods.extend([float(damage_bonus)] * qty)
        drone_bonus = attr_value(attrs, "droneDamageBonus", "droneDamageMultiplierBonus")
        if drone_bonus:
            drone_damage_mods.extend([float(drone_bonus)] * qty)
        drone_range_bonus = attr_value(attrs, "droneRangeBonus", "droneControlRangeBonus", "droneControlDistanceBonus")
        if drone_range_bonus:
            drone_control_bonus_m += float(drone_range_bonus) * qty
        drone_range_multiplier = dogma_multiplier(attr_value(attrs, "droneRangeMultiplier", "droneControlRangeMultiplier"))
        if drone_range_multiplier:
            drone_control_multipliers.extend([drone_range_multiplier] * qty)
        speed_multiplier = attr_value(attrs, "speedMultiplier")
        if speed_multiplier and overheated:
            overload_rof = attr_value(attrs, "overloadRofBonus")
            if overload_rof:
                speed_multiplier *= max(0.01, 1 + float(overload_rof) / 100.0)
        if speed_multiplier:
            if missile_damage or "ballistic" in f"{name} {group}".lower():
                missile_rof_mods.extend([float(speed_multiplier)] * qty)
            elif damage_bonus or "heat sink" in f"{name} {group}".lower() or "gyrostabilizer" in f"{name} {group}".lower() or "magnetic field" in f"{name} {group}".lower():
                turret_rof_mods.extend([float(speed_multiplier)] * qty)

        speed_factor = attr_value(attrs, "speedFactor", "maxVelocityBonus")
        if speed_factor and is_prop_family:
            heated_speed_factor = float(speed_factor) + (float(attr_value(attrs, "overloadSpeedFactorBonus") or 0.0) if overheated else 0.0)
            velocity_multipliers.extend([1 + heated_speed_factor / 100.0] * qty)
        signature_bonus = attr_value(attrs, "signatureRadiusBonus")
        if signature_bonus and is_prop_family:
            signature_multipliers.extend([1 + float(signature_bonus) / 100.0] * qty)
        mass_addition += safe_number(attr_value(attrs, "massAddition")) * qty if is_prop_family else 0.0
        agility_multiplier = dogma_multiplier(attr_value(attrs, "agilityMultiplier"))
        if agility_multiplier:
            agility_multipliers.extend([agility_multiplier] * qty)
        cap_multiplier = dogma_multiplier(attr_value(attrs, "capacitorCapacityMultiplier", "capacitorCapacityBonus"))
        if cap_multiplier:
            capacitor_multipliers.extend([cap_multiplier] * qty)

        repair_cycle = cycle_seconds(attrs)
        if repair_cycle:
            shield_repair = attr_value(attrs, "shieldBonus", "shieldBoostAmount")
            if shield_repair and "shield booster" in item_family:
                shield_repair_hps += float(shield_repair) / repair_cycle * qty
            armor_repair = attr_value(attrs, "armorDamageAmount", "armorHPRepaired", "armorHpRepaired")
            if armor_repair and ("armor repair" in item_family or "ancillary armor" in item_family):
                armor_repair_hps += float(armor_repair) / repair_cycle * qty
            structure_repair = attr_value(attrs, "structureDamageAmount", "hullDamageAmount", "hullRepairAmount")
            if structure_repair and ("hull repair" in item_family or "structure repair" in item_family):
                structure_repair_hps += float(structure_repair) / repair_cycle * qty
        shield_repair_multiplier = dogma_multiplier(attr_value(attrs, "shieldBoostMultiplier", "shieldBoostBonus", "shieldBoosterBonus"))
        if shield_repair_multiplier:
            shield_repair_multipliers.extend([shield_repair_multiplier] * qty)
        armor_repair_multiplier = dogma_multiplier(attr_value(attrs, "armorRepairMultiplier", "armorRepairAmountBonus", "armorRepairerAmountBonus", "armorDamageAmountBonus"))
        if armor_repair_multiplier:
            armor_repair_multipliers.extend([armor_repair_multiplier] * qty)
        structure_repair_multiplier = dogma_multiplier(attr_value(attrs, "structureRepairMultiplier", "hullRepairMultiplier"))
        if structure_repair_multiplier:
            structure_repair_multipliers.extend([structure_repair_multiplier] * qty)

        layer = infer_resistance_layer(group, name, attrs)
        collected_bonus_mods, collected_direct_mods = collect_resistance_modifiers(attrs, layer)
        hardening = 1 + (float(attr_value(attrs, "overloadHardeningBonus") or 0.0) / 100.0 if overheated else 0.0)
        for damage_type, values in collected_bonus_mods.items():
            if layer and values:
                layer_bonus_mods[layer][damage_type].extend([float(value) * hardening for value in values for _ in range(qty)])
        for layer_name, by_damage in collected_direct_mods.items():
            for damage_type, values in by_damage.items():
                if values:
                    direct_resonance_mods[layer_name][damage_type].extend([float(value) for value in values for _ in range(qty)])

    shield_hp *= percent_bonus_multiplier(shield_hp_pct_mods)
    armor_hp *= percent_bonus_multiplier(armor_hp_pct_mods)
    structure_hp *= percent_bonus_multiplier(structure_hp_pct_mods)
    shield_repair_hps *= stacking_raw_multiplier(shield_repair_multipliers) * ship_shield_boost_multiplier(ship_attrs, skill_name_levels)
    armor_repair_hps *= stacking_raw_multiplier(armor_repair_multipliers)
    structure_repair_hps *= stacking_raw_multiplier(structure_repair_multipliers)
    apply_resistance_modifiers(resonances, layer_bonus_mods, direct_resonance_mods)
    shield_resists = resistance_profile_from_resonance(resonances["shield"])
    armor_resists = resistance_profile_from_resonance(resonances["armor"])
    structure_resists = resistance_profile_from_resonance(resonances["structure"])
    shield_ehp = omni_ehp(shield_hp, shield_resists)
    armor_ehp = omni_ehp(armor_hp, armor_resists)
    structure_ehp = omni_ehp(structure_hp, structure_resists)

    def charge_row(type_id: int) -> dict[str, Any] | None:
        attrs = dogma.get(type_id, {})
        profile = damage_profile(attrs)
        damage = sum(profile.values())
        name = names.get(type_id, f"Type {type_id}")
        group = group_names.get(type_id, "")
        if damage <= 0 and "script" not in f"{name} {group}".lower():
            return None
        return {"type_id": type_id, "name": name, "group": group, "damage": damage, "damage_types": profile, "attrs": attrs, "kind": charge_kind(name, group)}

    charges: list[dict[str, Any]] = []
    for item in cargo_items:
        row = charge_row(item.type_id)
        if row:
            charges.append(row)

    missile_damage_multiplier = stacking_multiplier(missile_damage_mods)
    missile_rof_multiplier = stacking_raw_multiplier(missile_rof_mods)
    missile_velocity_multiplier = stacking_raw_multiplier(missile_velocity_mods) * missile_skill_velocity_multiplier(skill_name_levels)
    missile_flight_time_multiplier = stacking_raw_multiplier(missile_flight_time_mods) * missile_skill_flight_time_multiplier(skill_name_levels)
    missile_range_multiplier = stacking_raw_multiplier(missile_range_mods)
    turret_damage_multiplier = stacking_multiplier(turret_damage_mods)
    turret_rof_multiplier = stacking_raw_multiplier(turret_rof_mods)
    turret_range_multiplier = stacking_raw_multiplier(turret_range_mods)
    drone_damage_multiplier = stacking_multiplier(drone_damage_mods) * (1 + 0.1 * named_skill_level(skill_name_levels, "Drone Interfacing"))
    drone_control_range = drone_control_range_m(
        skill_name_levels,
        drone_control_bonus_m,
        drone_control_multipliers,
        base_range_m=attr_value(ship_attrs, "droneControlDistance"),
    )

    turret_dps = 0.0
    launcher_dps = 0.0
    drone_dps = 0.0
    volley = 0.0
    weapon_rows: list[dict[str, Any]] = []
    offense_damage_types = {label: 0.0 for label in DAMAGE_TYPES}
    for item in active_fitted_items:
        attrs = dogma.get(item.type_id, {})
        group = group_names.get(item.type_id, "")
        if not (is_launcher_group(group) or is_turret_group(group) or "smartbomb" in group.lower()):
            continue
        name = names.get(item.type_id, f"Type {item.type_id}")
        if not item_effects_apply(item, attrs, group, name):
            continue
        explicit_charge = charge_row(item.charge_type_id) if getattr(item, "charge_type_id", None) else None
        if explicit_charge and not charge_is_compatible_with_module(name, group, explicit_charge["name"], explicit_charge["group"]):
            explicit_charge = None
        charge = explicit_charge if explicit_charge else matching_charge(name, group, charges)
        kind = charge["kind"] if charge else charge_kind(name, group)
        base_profile = charge["damage_types"] if charge else damage_profile(attrs)
        base_damage = sum(base_profile.values())
        damage_multiplier = safe_number(attr_value(attrs, "damageMultiplier"), 1.0) or 1.0
        cycle = cycle_seconds(attrs)
        fitted_damage_multiplier = missile_damage_multiplier if is_launcher_group(group) else turret_damage_multiplier
        fitted_rof_multiplier = missile_rof_multiplier if is_launcher_group(group) else turret_rof_multiplier
        overheated = item_is_overheated(item, heat, attrs)
        if overheated:
            overload_damage = attr_value(attrs, "overloadDamageModifier")
            if overload_damage:
                fitted_damage_multiplier *= max(0.01, 1 + float(overload_damage) / 100.0)
            overload_rof = attr_value(attrs, "overloadRofBonus")
            if overload_rof:
                fitted_rof_multiplier *= max(0.01, 1 + float(overload_rof) / 100.0)
        if is_launcher_group(group):
            fitted_damage_multiplier *= missile_skill_damage_multiplier(kind, skill_levels)
            fitted_damage_multiplier *= ship_missile_damage_multiplier(ship_attrs, kind, skill_name_levels)
            fitted_rof_multiplier *= missile_skill_rof_multiplier(kind, attrs, skill_levels)
        total_damage_multiplier = damage_multiplier * fitted_damage_multiplier * module_quantity(item)
        item_damage_types = scale_damage_profile(base_profile, total_damage_multiplier)
        item_volley = base_damage * total_damage_multiplier
        item_dps = item_volley / (cycle * fitted_rof_multiplier) if cycle and fitted_rof_multiplier > 0 else 0.0
        if item_volley > 0:
            add_damage_profile(offense_damage_types, item_damage_types)
        if is_launcher_group(group):
            launcher_dps += item_dps
        elif is_turret_group(group):
            turret_dps += item_dps
        volley += item_volley
        charge_attrs = charge["attrs"] if charge else {}
        weapon_rows.append({
            "item_id": item.id,
            "type_id": item.type_id,
            "name": name,
            "group": group,
            "slot_flag": item.flag,
            "quantity": module_quantity(item),
            "dps": item_dps,
            "volley": item_volley,
            "charge_name": charge["name"] if charge else None,
            "damage_types": item_damage_types,
            "state": item_state(item),
            "overheated": overheated,
            **weapon_range(
                attrs,
                charge_attrs,
                group,
                missile_velocity_multiplier=missile_velocity_multiplier * ship_missile_velocity_multiplier(ship_attrs, kind, skill_name_levels),
                missile_flight_time_multiplier=missile_flight_time_multiplier,
                missile_range_multiplier=missile_range_multiplier,
                turret_range_multiplier=turret_range_multiplier,
            ),
        })

    for item in bay_items:
        attrs = dogma.get(item.type_id, {})
        group = group_names.get(item.type_id, "")
        if not is_drone_group(group):
            continue
        base_damage = damage_amount(attrs)
        damage_multiplier = safe_number(attr_value(attrs, "damageMultiplier"), 1.0) or 1.0
        cycle = cycle_seconds(attrs)
        total_damage_multiplier = damage_multiplier * drone_damage_multiplier * module_quantity(item)
        item_damage_types = scale_damage_profile(damage_profile(attrs), total_damage_multiplier)
        item_volley = base_damage * total_damage_multiplier
        item_dps = item_volley / cycle if cycle else 0.0
        drone_dps += item_dps
        volley += item_volley
        if item_volley > 0:
            add_damage_profile(offense_damage_types, item_damage_types)
        weapon_rows.append({
            "item_id": item.id,
            "type_id": item.type_id,
            "name": names.get(item.type_id, f"Type {item.type_id}"),
            "group": group,
            "slot_flag": item.flag,
            "quantity": module_quantity(item),
            "dps": item_dps,
            "volley": item_volley,
            "charge_name": None,
            "damage_types": item_damage_types,
            "state": "online",
            "overheated": False,
            "range_m": attr_value(attrs, "maxRange"),
            "optimal_m": attr_value(attrs, "maxRange"),
            "falloff_m": None,
            **drone_detail_stats(attrs, skill_name_levels, module_quantity(item), cycle, drone_control_range),
        })

    max_velocity = attr_value(ship_attrs, "maxVelocity")
    if max_velocity is not None:
        max_velocity *= 1 + 0.05 * skill_level(skill_levels, NAVIGATION_TYPE_ID)
        max_velocity *= stacking_raw_multiplier(velocity_multipliers)
    mass = attr_value(ship_attrs, "mass")
    if mass is not None:
        mass = float(mass) + mass_addition
    inertia = attr_value(ship_attrs, "agility", "inertiaModifier")
    if inertia is not None:
        inertia = float(inertia) * stacking_raw_multiplier(agility_multipliers)
    align_time = None
    if mass and inertia:
        align_time = 1.38629436112 * float(mass) * float(inertia) / 1_000_000.0
    capacitor_capacity = attr_value(ship_attrs, "capacitorCapacity")
    if capacitor_capacity is not None:
        capacitor_capacity = float(capacitor_capacity) * stacking_raw_multiplier(capacitor_multipliers)
    capacitor_recharge_ms = attr_value(ship_attrs, "rechargeRate", "capacitorRechargeRate")
    capacitor_peak_recharge = None
    capacitor_recharge_seconds = float(capacitor_recharge_ms) / 1000.0 if capacitor_recharge_ms else None
    if capacitor_capacity and capacitor_recharge_seconds:
        capacitor_peak_recharge = float(capacitor_capacity) / capacitor_recharge_seconds * 2.5
    capacitor_draw, capacitor_modules = active_capacitor_use_per_second(active_fitted_items, dogma, names)
    stable_percent = None
    depletion_seconds = None
    cap_stable = False
    if capacitor_capacity and capacitor_recharge_seconds:
        stable_percent = capacitor_stable_percent(float(capacitor_capacity), capacitor_recharge_seconds, capacitor_draw)
        cap_stable = stable_percent is not None
        if stable_percent is None:
            depletion_seconds = capacitor_depletion_seconds(float(capacitor_capacity), capacitor_recharge_seconds, capacitor_draw)
    elif capacitor_draw <= 0:
        cap_stable = True
        stable_percent = 100.0
    shield_peak_recharge = None
    if shield_hp and shield_recharge_ms:
        shield_peak_recharge = shield_hp / (float(shield_recharge_ms) / 1000.0) * 2.5
    signature_radius = attr_value(ship_attrs, "signatureRadius")
    if signature_radius is not None:
        signature_radius = float(signature_radius) * stacking_raw_multiplier(signature_multipliers)
        for item in active_fitted_items:
            signature_radius += safe_number(attr_value(dogma.get(item.type_id, {}), "signatureRadiusAdd")) * module_quantity(item)

    return {
        "offense": {
            "turret_dps": turret_dps,
            "launcher_dps": launcher_dps,
            "drone_dps": drone_dps,
            "total_dps": turret_dps + launcher_dps + drone_dps,
            "volley": volley,
            "damage_types": offense_damage_types,
            "weapon_count": len(weapon_rows),
            "max_range_m": max((float(row["range_m"]) for row in weapon_rows if row.get("range_m") is not None), default=None),
            "weapons": sorted(weapon_rows, key=lambda row: row["dps"], reverse=True)[:80],
        },
        "defense": {
            "shield_hp": shield_hp,
            "armor_hp": armor_hp,
            "structure_hp": structure_hp,
            "ehp": shield_ehp + armor_ehp + structure_ehp,
            "shield_ehp": shield_ehp,
            "armor_ehp": armor_ehp,
            "structure_ehp": structure_ehp,
            "shield_resists": shield_resists,
            "armor_resists": armor_resists,
            "structure_resists": structure_resists,
            "shield_peak_recharge": shield_peak_recharge,
            "active_tank_hps": shield_repair_hps + armor_repair_hps + structure_repair_hps,
            "shield_repair_hps": shield_repair_hps,
            "armor_repair_hps": armor_repair_hps,
            "structure_repair_hps": structure_repair_hps,
        },
        "mobility": {
            "max_velocity": max_velocity,
            "warp_speed": attr_value(ship_attrs, "warpSpeedMultiplier", "baseWarpSpeed"),
            "align_time": align_time,
            "signature_radius": signature_radius,
            "mass": mass,
        },
        "capacitor": {
            "capacity": capacitor_capacity,
            "recharge_time": capacitor_recharge_seconds,
            "peak_recharge": capacitor_peak_recharge,
            "draw_per_second": capacitor_draw,
            "stable": cap_stable,
            "stable_percent": stable_percent,
            "depletion_seconds": depletion_seconds,
            "modules": capacitor_modules,
        },
        "targeting": {
            "max_targets": attr_value(ship_attrs, "maxLockedTargets"),
            "targeting_range": attr_value(ship_attrs, "maxTargetRange"),
            "scan_resolution": attr_value(ship_attrs, "scanResolution"),
            "sensor_strength": max(
                safe_number(attr_value(ship_attrs, "scanRadarStrength")),
                safe_number(attr_value(ship_attrs, "scanLadarStrength")),
                safe_number(attr_value(ship_attrs, "scanMagnetometricStrength")),
                safe_number(attr_value(ship_attrs, "scanGravimetricStrength")),
            ),
            "drone_control_range_m": drone_control_range,
        },
        "notes": [
            f"Combat stats are SDE-derived {'hot' if heat else 'cold'} estimates with common fitted module modifiers, missile character skills, selected hull role bonuses, capacitor draw, and stacking penalties. Implants, script effect modifiers, and full effect-graph coverage are still being refined.",
        ],
    }

def simulate_fitting(db: Session, fitting: CharacterFitting, character: EveCharacter, heat: bool = False) -> dict[str, Any]:
    type_ids = {fitting.ship_type_id, *(item.type_id for item in fitting.items), *(item.charge_type_id for item in fitting.items if getattr(item, "charge_type_id", None))}
    dogma = dogma_for_types(db, type_ids)
    dogma_effects = dogma_effects_for_types(db, type_ids)
    names = type_names(db, type_ids | required_skill_type_ids(dogma))
    group_names = type_group_names(db, type_ids)
    skill_levels = character_skill_levels(db, character.id)
    skill_name_levels = character_skill_levels_by_name(db, character.id)
    ship_attrs = dogma.get(fitting.ship_type_id, {})
    dogma_loaded = bool(ship_attrs) or any(dogma.get(item.type_id) for item in fitting.items)
    dogma_effects_loaded = bool(dogma_effects.get(fitting.ship_type_id)) or any(dogma_effects.get(item.type_id) for item in fitting.items)

    slot_usage: dict[str, int] = {prefix: 0 for prefix in SLOT_CAPACITY_ATTRS}
    resources = ship_resource_capacity(ship_attrs, skill_levels)

    required_skill_rows: list[dict[str, Any]] = []
    seen_requirements: set[tuple[int, int, int]] = set()

    def add_requirements(source_type_id: int, source_name: str, attrs: dict[str, float], source_kind: str) -> None:
        for requirement in required_skills_from_attrs(attrs):
            skill_id = requirement["skill_type_id"]
            required_level = requirement["required_level"]
            trained_level = skill_levels.get(skill_id, 0)
            key = (source_type_id, skill_id, required_level)
            if key in seen_requirements:
                continue
            seen_requirements.add(key)
            required_skill_rows.append({
                "source_type_id": source_type_id,
                "source_name": source_name,
                "source_kind": source_kind,
                "skill_type_id": skill_id,
                "skill_name": names.get(skill_id, f"Type {skill_id}"),
                "required_level": required_level,
                "trained_level": trained_level,
                "met": trained_level >= required_level,
            })

    add_requirements(fitting.ship_type_id, names.get(fitting.ship_type_id, f"Type {fitting.ship_type_id}"), ship_attrs, "ship")

    item_checks: list[dict[str, Any]] = []
    for item in fitting.items:
        slot = slot_prefix(item.flag)
        item_attrs = dogma.get(item.type_id, {})
        if slot in slot_usage:
            slot_usage[slot] += max(1, int(item.quantity or 1))
        usage = item_resource_usage(item, item_attrs, group_names.get(item.type_id, ""), skill_levels)
        resources["cpu"]["used"] += usage["cpu"]
        resources["powergrid"]["used"] += usage["powergrid"]
        resources["calibration"]["used"] += usage["calibration"]
        item_name = names.get(item.type_id, f"Type {item.type_id}")
        add_requirements(item.type_id, item_name, item_attrs, "module")
        item_checks.append({
            "item_id": item.id,
            "type_id": item.type_id,
            "type_name": item_name,
            "flag": item.flag,
            "slot_group": slot,
            "quantity": item.quantity,
            "simulation_state": item_state(item),
            "charge_type_id": item.charge_type_id,
            "charge_type_name": names.get(item.charge_type_id) if item.charge_type_id else None,
            "cpu": usage["cpu"],
            "powergrid": usage["powergrid"],
            "calibration": usage["calibration"],
            "dogma_loaded": bool(item_attrs),
            "group_name": group_names.get(item.type_id),
        })

    slots = []
    for prefix, (attr_name, label) in SLOT_CAPACITY_ATTRS.items():
        capacity_value = attr_value(ship_attrs, attr_name)
        capacity = int(capacity_value) if capacity_value is not None else None
        used = slot_usage[prefix]
        slots.append({"key": prefix, "label": label, "used": used, "capacity": capacity, "ok": capacity is None or used <= capacity})

    for row in resources.values():
        row["ok"] = row["capacity"] is None or row["used"] <= float(row["capacity"] or 0)
        if row["capacity"]:
            row["percent"] = min(999.0, row["used"] / float(row["capacity"]) * 100)
        else:
            row["percent"] = None

    missing_skills = [row for row in required_skill_rows if not row["met"]]
    slot_failures = [row for row in slots if not row["ok"]]
    resource_failures = [key for key, row in resources.items() if not row["ok"]]
    status = "pass" if dogma_loaded and not missing_skills and not slot_failures and not resource_failures else "warning" if dogma_loaded else "unknown"

    notes = [] if dogma_loaded else ["Dogma attributes are not imported yet. Import the SDE dogma section before relying on simulation checks."]
    if dogma_loaded and not dogma_effects_loaded:
        notes.append("Dogma effects are not imported yet. Re-import SDE dogma to unlock effect-graph based simulation passes.")
    stats = compute_fitting_stats(fitting, dogma, names, group_names, skill_levels, skill_name_levels, heat=heat) if dogma_loaded else None

    return {
        "fitting_id": fitting.id,
        "character_id": character.id,
        "character_name": character.name,
        "dogma_loaded": dogma_loaded,
        "dogma_effects_loaded": dogma_effects_loaded,
        "status": status,
        "summary": {
            "missing_skills": len(missing_skills),
            "slot_issues": len(slot_failures),
            "resource_issues": len(resource_failures),
        },
        "resources": resources,
        "slots": slots,
        "requirements": sorted(required_skill_rows, key=lambda row: (not row["met"], row["source_kind"], row["source_name"], row["skill_name"])),
        "items": item_checks,
        "stats": stats,
        "heat": heat,
        "notes": notes + (stats.get("notes", []) if stats else []),
    }


def load_fitting_for_simulation(db: Session, fitting_id: int) -> CharacterFitting | None:
    return db.scalar(
        select(CharacterFitting)
        .where(CharacterFitting.id == fitting_id)
        .options(
            selectinload(CharacterFitting.character),
            selectinload(CharacterFitting.ship_type),
            selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.item_type),
            selectinload(CharacterFitting.items).selectinload(CharacterFittingItem.charge_type),
        )
    )