"""Fighter squadrons, separate from drone bandwidth and the base stats engines.

SDE ability damage is per fighter. A hangar stack is inventory, not a deployed
squadron. Tube flags persist in EQM drafts; EFT/ESI exports flatten them to the
fighter bay because saved EVE fittings cannot express our deployment state.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any

TUBE_PREFIX = "FighterTube"
TUBE_FLAGS = tuple(f"{TUBE_PREFIX}{i}" for i in range(10))
CLASSES = {"light": "fighterLightSlots", "support": "fighterSupportSlots", "heavy": "fighterHeavySlots"}
DAMAGE_TYPES = ("em", "thermal", "kinetic", "explosive")
ABILITY_SUFFIXES = ("EM", "Therm", "Kin", "Exp")
ABILITIES = (
    ("primary", "Attack missile", "fighterAbilityAttackMissile", "RangeOptimal"),
    ("primary", "Attack turret", "fighterAbilityAttackTurret", "RangeOptimal"),
    ("salvo", "Missile salvo", "fighterAbilityMissiles", "Range"),
)
STACKING = (1.0, .8708869, .5705831, .2829552, .1059926, .0299912, .0064102)


def normalized(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def attributes(raw: dict[str, float]) -> dict[str, float]:
    return {normalized(k): float(v) for k, v in raw.items()}


def value(attrs: dict[str, float], name: str, default: float = 0.0) -> float:
    result = attrs.get(normalized(name), default)
    return float(result) if math.isfinite(float(result)) else default


def fighter_class(attrs: dict[str, float]) -> str | None:
    return next((kind for kind in CLASSES if value(attrs, f"fighterSquadronIs{kind}") > 0), None)


def required_skills(attrs: dict[str, float]) -> set[int]:
    return {int(value(attrs, f"requiredSkill{i}")) for i in range(1, 7) if value(attrs, f"requiredSkill{i}") > 0}


def fighter_limits(ship_attrs: dict[str, float]) -> dict[str, int]:
    attrs = attributes(ship_attrs)
    return {"tubes": max(0, min(10, int(value(attrs, "fighterTubes")))),
            **{kind: max(0, int(value(attrs, attr))) for kind, attr in CLASSES.items()}}


def _stack(multipliers: list[float]) -> float:
    result = 1.0
    for i, multiplier in enumerate(sorted(multipliers, key=lambda v: abs(v - 1), reverse=True)):
        result *= 1 + (multiplier - 1) * (STACKING[i] if i < len(STACKING) else 0)
    return result


def _hull_skill(source: str, skills_by_name: dict[str, int]) -> int:
    match = re.match(r"shipbonus(?:supercarrier|carrier)([acgm])\d", source)
    if not match:
        return 1  # Role/generic modifiers are independent of trained hull skill.
    race = {"a": "Amarr", "c": "Caldari", "g": "Gallente", "m": "Minmatar"}[match[1]]
    return skills_by_name.get(normalized(f"{race} Carrier"), 0)


def fighter_modifiers(fitting: Any, fighter_attrs: dict[str, float], dogma: dict[int, dict[str, float]],
                      effects: dict[int, list[dict[str, Any]]], skill_levels: dict[int, int],
                      skill_names: dict[str, int], stats_item_ids: set[int] | None = None,
                      implant_type_ids: set[int] | None = None) -> dict[str, float]:
    """Evaluate owner-required-skill effects only on the matching fighter.

    Hull and trained-skill bonuses multiply independently. Fitted damage and
    cycle-time bonuses stack by their target attribute, with one penalty per
    physical module (not per effect or ability).
    """
    required = required_skills(fighter_attrs)
    targets = {normalized(prefix + suffix) for _, _, prefix, _ in ABILITIES for suffix in ("DamageMultiplier", "Duration")}
    result = {target: 1.0 for target in targets}
    penalized: dict[str, list[float]] = defaultdict(list)
    skill_names = {normalized(k): v for k, v in skill_names.items()}
    sources = [(fitting.ship_type_id, "hull", 1, 1)]
    sources += [(type_id, "skill", max(0, min(5, level)), 1) for type_id, level in skill_levels.items() if level > 0]
    for item in fitting.items:
        if not re.match(r"^(HiSlot|MedSlot|LoSlot|RigSlot|SubSystemSlot|ServiceSlot)\d+$", item.flag):
            continue
        if (stats_item_ids is not None and int(item.id or 0) not in stats_item_ids) or getattr(item, "simulation_state", "online") == "offline":
            continue
        sources.append((item.type_id, "module", 1, max(1, int(item.quantity or 1))))
    sources += [(type_id, "implant", 1, 1) for type_id in implant_type_ids or set()]
    for type_id, source_kind, level, quantity in sources:
        source_attrs = attributes(dogma.get(type_id, {}))
        seen: set[tuple[Any, ...]] = set()
        for effect in effects.get(type_id, []):
            for modifier in effect.get("modifier_info", []):
                if modifier.get("func") != "OwnerRequiredSkillModifier" or modifier.get("domain") != "charID":
                    continue
                if int(modifier.get("skillTypeID") or 0) not in required:
                    continue
                target = normalized(str(modifier.get("modified_attribute_name") or ""))
                source = normalized(str(modifier.get("modifying_attribute_name") or ""))
                operation = int(modifier.get("operation", -1))
                key = (target, source, operation)
                if target not in targets or not source or key in seen or source not in source_attrs:
                    continue
                seen.add(key)
                source_value = source_attrs[source]
                factor = _hull_skill(source, skill_names) if source_kind == "hull" else level
                if operation == 6:
                    multiplier = 1 + source_value * factor / 100
                elif operation == 4:
                    multiplier = source_value
                else:
                    continue
                if source_kind == "module":
                    penalized[target].extend([max(.01, multiplier)] * quantity)
                else:
                    result[target] *= max(.01, multiplier)
    for target, multipliers in penalized.items():
        result[target] *= _stack(multipliers)
    return result


def compute_fighters(fitting: Any, dogma: dict[int, dict[str, float]], names: dict[int, str],
                     effects: dict[int, list[dict[str, Any]]], skill_levels: dict[int, int],
                     skill_names: dict[str, int], *, include_salvos: bool = False,
                     stats_item_ids: set[int] | None = None, implant_type_ids: set[int] | None = None,
                     target_kind: str = "capital") -> dict[str, Any]:
    limits = fighter_limits(dogma.get(fitting.ship_type_id, {}))
    items = sorted((item for item in fitting.items if item.flag.startswith(TUBE_PREFIX)), key=lambda i: (i.flag, int(i.id or 0)))
    occupied = Counter(item.flag for item in items)
    deployed: Counter[str] = Counter()
    tubes: list[dict[str, Any]] = []
    weapons: list[dict[str, Any]] = []
    warnings: list[str] = []
    primary_dps = salvo_dps = 0.0
    for item in items:
        attrs = attributes(dogma.get(item.type_id, {}))
        kind = fighter_class(attrs)
        max_size = max(0, int(value(attrs, "fighterSquadronMaxSize")))
        size = int(item.quantity or 0)
        state = getattr(item, "simulation_state", "online") or "online"
        active = state == "active"
        match = re.fullmatch(r"FighterTube([0-9])", item.flag)
        index = int(match[1]) if match else -1
        reason = None
        if index < 0 or index >= limits["tubes"]:
            reason = "This hull has no such fighter tube."
        elif occupied[item.flag] != 1:
            reason = "Multiple squadrons occupy the same tube."
        elif kind is None or max_size == 0 or 23069 not in required_skills(attrs):
            reason = "Fighter squadron SDE attributes are missing or this is not a fighter."
        elif not 1 <= size <= max_size:
            reason = f"Squadron must contain 1–{max_size} fighters."
        elif state not in {"offline", "online", "active"}:
            reason = "Fighters cannot overheat. Choose loaded or deployed."
        elif limits[kind] == 0:
            reason = f"This hull cannot deploy {kind} fighters."
        elif active and deployed[kind] >= limits[kind]:
            reason = f"The {kind} fighter squadron limit is exceeded."
        if active and not reason and kind:
            deployed[kind] += 1
        abilities = []
        modifiers = fighter_modifiers(fitting, attrs, dogma, effects, skill_levels, skill_names,
                                      stats_item_ids, implant_type_ids) if not reason else {}
        damage_profile = dict.fromkeys(DAMAGE_TYPES, 0.0)
        tube_primary = tube_salvo = tube_volley = 0.0
        for ability_kind, label, prefix, range_suffix in ABILITIES:
            # Superiority fighters' micro missiles are their unlimited PRIMARY
            # weapon; the same attribute family is a charged salvo on attackers.
            superiority = value(attrs, "fighterSquadronRole") == 1
            if superiority and prefix == "fighterAbilityMissiles":
                ability_kind, label = "primary", "Micro Missile Swarm"
            base = [value(attrs, prefix + "Damage" + suffix) for suffix in ABILITY_SUFFIXES]
            cycle = value(attrs, prefix + "Duration") / 1000
            if not any(base) or cycle <= 0:
                continue
            damage_multiplier = value(attrs, prefix + "DamageMultiplier", 1) * modifiers.get(normalized(prefix + "DamageMultiplier"), 1)
            # CCP SDE default target resistance attributes 2189/2244. These are
            # target-class reductions, independent of signature/velocity falloff.
            resistance = int(value(attrs, "fighterAbilityMissilesResistanceID")) if prefix == "fighterAbilityMissiles" else 0
            if resistance == 2189 and target_kind != "fighter":
                damage_multiplier *= .05
            elif resistance == 2244 and target_kind in {"subcapital", "fighter"}:
                damage_multiplier *= .1
            cycle *= modifiers.get(normalized(prefix + "Duration"), 1)
            profile = {kind: amount * size * damage_multiplier for kind, amount in zip(DAMAGE_TYPES, base)}
            volley = sum(profile.values())
            dps = volley / cycle if active and not reason else 0.0
            if ability_kind == "primary":
                tube_primary += dps
            else:
                tube_salvo += dps
            selected = ability_kind == "primary" or include_salvos
            if active and not reason and selected:
                tube_volley += volley
                for damage_type in DAMAGE_TYPES:
                    damage_profile[damage_type] += profile[damage_type]
            abilities.append({"kind": ability_kind, "name": label, "dps": dps, "cycle_seconds": cycle,
                              "volley": volley if active and not reason else 0, "selected": selected,
                              "range_m": value(attrs, prefix + range_suffix) or None,
                              "explosion_radius_m": value(attrs, prefix + "ExplosionRadius") or None,
                              "explosion_velocity_m_s": value(attrs, prefix + "ExplosionVelocity") or None})
        tube = {"index": index, "flag": item.flag, "item_id": item.id, "type_id": item.type_id,
                "name": names.get(item.type_id, f"Type {item.type_id}"), "fighter_class": kind,
                "size": size, "max_size": max_size, "state": state, "active": active,
                "valid": reason is None, "warning": reason, "abilities": abilities,
                "primary_dps": tube_primary, "salvo_dps": tube_salvo,
                "dps": tube_primary + (tube_salvo if include_salvos else 0)}
        tubes.append(tube)
        if reason:
            warnings.append(f"{item.flag}: {reason} No damage counted.")
        primary_dps += tube_primary
        salvo_dps += tube_salvo
        if active and not reason and abilities:
            weapons.append({"item_id": item.id, "type_id": item.type_id, "name": tube["name"],
                            "group": f"{kind.title()} fighter squadron", "slot_flag": item.flag, "quantity": size,
                            "state": state, "overheated": False, "dps": tube["dps"], "volley": tube_volley,
                            "damage_types": damage_profile, "range_m": max((a["range_m"] or 0 for a in abilities if a["selected"]), default=0) or None})
    if items and not effects.get(fitting.ship_type_id):
        warnings.append("Hull fighter bonus effect metadata is unavailable; fighter damage may omit hull bonuses. Refresh SDE dogma effects.")
    return {"tube_count": limits["tubes"], "limits": {k: v for k, v in limits.items() if k != "tubes"},
            "deployed": dict(deployed), "tubes": tubes, "primary_dps": primary_dps,
            "salvo_dps": salvo_dps, "total_dps": primary_dps + (salvo_dps if include_salvos else 0),
            "include_salvos": include_salvos, "target_kind": target_kind, "warnings": warnings, "weapons": weapons}


def add_fighter_stats(stats: dict[str, Any], fitting: Any, dogma: dict[int, dict[str, float]],
                      names: dict[int, str], effects: dict[int, list[dict[str, Any]]],
                      skill_levels: dict[int, int], skill_names: dict[str, int], **options: Any) -> dict[str, Any]:
    """Enrich either base engine with one authoritative fighter calculation."""
    fighters = compute_fighters(fitting, dogma, names, effects, skill_levels, skill_names, **options)
    if not fighters["tube_count"] and not fighters["tubes"]:
        return stats
    offense = stats["offense"]
    stats["fighters"] = {k: v for k, v in fighters.items() if k != "weapons"}
    offense["fighter_dps"] = fighters["total_dps"]
    offense["total_dps"] += fighters["total_dps"]
    offense["weapons"].extend(fighters["weapons"])
    offense["weapon_count"] += len(fighters["weapons"])
    for row in fighters["weapons"]:
        offense["volley"] += row["volley"]
        for damage_type in DAMAGE_TYPES:
            offense.setdefault("damage_types", dict.fromkeys(DAMAGE_TYPES, 0.0))[damage_type] += row["damage_types"][damage_type]
        if row.get("range_m"):
            offense["max_range_m"] = max(offense.get("max_range_m") or 0, row["range_m"])
    stats["notes"].extend(fighters["warnings"])
    stats["notes"].append("Fighter DPS uses deployed tube squadrons only, at full application before target resists. Salvo DPS is optional limited-ammo burst, not indefinitely sustainable DPS. Hangar reserves and support abilities add no weapon damage.")
    return stats
