"""Describe weapon systems using SDE bonuses and fitted module groups."""
from sqlalchemy import select

from app.models import EveGroup
from app.services import fitting_simulator as simulator


def weapon_family(name: str, *, bonus: bool = False) -> str | None:
    key = name.casefold()
    for match, label in (
        ("hybrid", "Hybrid turrets"),
        ("projectile", "Projectile turrets"),
        ("energy turret", "Laser turrets"),
        ("energy weapon", "Laser turrets"),
        ("precursor weapon", "Entropic disintegrators"),
        ("vorton", "Vorton projectors"),
        ("breacher", "Breacher pods"),
        ("doomsday", "Doomsdays"),
        ("super weapon", "Doomsdays"),
        ("bomb launcher", "Bomb launchers"),
        ("launcher bomb", "Bomb launchers"),
        ("rocket", "Rockets"),
        ("torpedo", "Torpedoes"),
        ("cruise missile", "Cruise missiles"),
        ("launcher cruise", "Cruise missiles"),
        ("launcher xl cruise", "XL cruise missiles"),
        ("rapid heavy", "Rapid heavy missiles"),
        ("rapid light", "Rapid light missiles"),
        ("heavy assault", "Heavy assault missiles"),
        ("heavy missile", "Heavy missiles"),
        ("launcher heavy", "Heavy missiles"),
        ("light missile", "Light missiles"),
        ("launcher light", "Light missiles"),
        ("missile launcher", "Missiles"),
        ("combat drone", "Combat drones"),
        ("fighter", "Fighters"),
    ):
        if match in key:
            return label
    if not bonus and "smartbomb" in key:
        return "Smartbombs"
    return None


def hull_weapons(db, type_id: int, attributes: dict) -> dict:
    effects = simulator.dogma_effects_for_types(db, {type_id})
    modifiers = [
        modifier
        for effect in effects.get(type_id, [])
        for modifier in effect["modifier_info"]
    ]
    skills = simulator.type_names(db, {m["skillTypeID"] for m in modifiers if m.get("skillTypeID")})
    group_ids = {m["groupID"] for m in modifiers if m.get("groupID")}
    groups = dict(db.execute(select(EveGroup.group_id, EveGroup.name).where(EveGroup.group_id.in_(group_ids))).all()) if group_ids else {}
    families = set()
    for modifier in modifiers:
        skill = skills.get(modifier.get("skillTypeID"), "")
        group = groups.get(modifier.get("groupID"), "")
        if (skill == "Drones" or "drone operation" in skill.casefold() or "sentry drone" in skill.casefold()) and modifier.get("modified_attribute_name") == "damagemultiplier":
            families.add("Combat drones")
        family = weapon_family(group, bonus=True) or weapon_family(skill, bonus=True)
        if family:
            families.add(family)

    options = [
        label for attribute, label in (
            ("turretSlotsLeft", "Turret hardpoints"),
            ("launcherSlotsLeft", "Launcher hardpoints"),
            ("droneBandwidth", "Drone bandwidth"),
            ("fighterCapacity", "Fighter hangar"),
        ) if (attributes.get(attribute) or 0) > 0
    ]
    return {"bonused": sorted(families), "mounts": options, "effects_loaded": bool(effects)}


def fitted_weapon_family(name: str, group: str) -> str | None:
    key = name.casefold()
    if "smartbomb" in key:
        return "Smartbombs"
    for term, label in (
        ("blaster", "Blasters"),
        ("railgun", "Railguns"),
        ("autocannon", "Autocannons"),
        ("artillery", "Artillery"),
        ("pulse laser", "Pulse lasers"),
        ("beam laser", "Beam lasers"),
    ):
        if term in key and weapon_family(group) in {"Hybrid turrets", "Projectile turrets", "Laser turrets"}:
            return label
    return weapon_family(group)
