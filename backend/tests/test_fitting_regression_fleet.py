from types import SimpleNamespace

import pytest

from app.services.fitting_simulator import (
    ADVANCED_SPACESHIP_COMMAND_TYPE_ID,
    CAPACITOR_MANAGEMENT_TYPE_ID,
    CAPACITOR_SYSTEMS_OPERATION_TYPE_ID,
    EVASIVE_MANEUVERING_TYPE_ID,
    NAVIGATION_TYPE_ID,
    SPACESHIP_COMMAND_TYPE_ID,
    active_capacitor_use_per_second,
    compute_fitting_stats,
    is_drone_group,
    is_turret_group,
    item_effects_apply,
    item_resource_usage,
    normalize_attr,
    stacking_raw_multiplier,
)


FENRIR_ID = 20189
MINMATAR_FREIGHTER_ID = 20528
EXPANDED_CARGOHOLD_II_ID = 1319
INERTIAL_STABILIZERS_II_ID = 1405
REINFORCED_BULKHEADS_II_ID = 1335
ROGUE_EVASIVE_MANEUVERING_EM_705_ID = 16004
ROGUE_WARP_DRIVE_SPEED_WS_615_ID = 27114
LOW_GRADE_NOMAD_ALPHA_ID = 33947
LOW_GRADE_NOMAD_BETA_ID = 33948


def fitting_item(item_id: int, type_id: int, flag: str, name: str, state: str = "online") -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id,
        type_id=type_id,
        flag=flag,
        quantity=1,
        simulation_state=state,
        charge_type_id=None,
        item_type=SimpleNamespace(name=name),
    )


def fenrir_stats(
    items: list[SimpleNamespace],
    navigation_level: int = 0,
    evasive_maneuvering_level: int = 4,
    implant_type_ids: set[int] | None = None,
) -> dict:
    fitting = SimpleNamespace(ship_type_id=FENRIR_ID, items=items)
    dogma = {
        FENRIR_ID: {
            "capacity": 435_000.0,
            "lowSlots": 3.0,
            "hp": 78_000.0,
            "agility": 0.0625,
            "advancedAgility": 1.0,
            "maxVelocity": 81.0,
            "signatureRadius": 10_385.0,
            "warpSpeedMultiplier": 1.5,
            "capacitorCapacity": 3_000.0,
            "rechargeRate": 184_800.0,
            "requiredSkill2": MINMATAR_FREIGHTER_ID,
            "freighterBonusM1": 5.0,
            "freighterBonusM2": 5.0,
            "cpuNeedBonus": -100.0,
        },
        EXPANDED_CARGOHOLD_II_ID: {
            "cargoCapacityMultiplier": 1.275,
            "maxVelocityModifier": 0.82,
            "structureHPMultiplier": 0.77,
        },
        INERTIAL_STABILIZERS_II_ID: {
            "agilityMultiplier": -20.0,
            "signatureRadiusBonus": 11.0,
        },
        REINFORCED_BULKHEADS_II_ID: {
            "cargoCapacityMultiplier": 0.89,
            "structureHPMultiplier": 1.25,
            "agilityMultiplier": 5.0,
            "cpu": 40.0,
            "power": 1.0,
        },
        SPACESHIP_COMMAND_TYPE_ID: {"agilityBonus": -2.0},
        EVASIVE_MANEUVERING_TYPE_ID: {"agilityBonus": -5.0},
        ADVANCED_SPACESHIP_COMMAND_TYPE_ID: {"agilityBonus": -5.0},
        CAPACITOR_MANAGEMENT_TYPE_ID: {"capacitorCapacityBonus": 5.0},
        CAPACITOR_SYSTEMS_OPERATION_TYPE_ID: {"capRechargeBonus": -5.0},
        ROGUE_EVASIVE_MANEUVERING_EM_705_ID: {"agilityBonus": -5.0},
        ROGUE_WARP_DRIVE_SPEED_WS_615_ID: {"WarpSBonus": 15.0},
        LOW_GRADE_NOMAD_ALPHA_ID: {"agilityBonus": -1.0, "implantSetThukker": 1.025},
        LOW_GRADE_NOMAD_BETA_ID: {"agilityBonus": -2.0, "implantSetThukker": 1.025},
    }
    dogma = {
        type_id: {normalize_attr(attribute_name): value for attribute_name, value in attributes.items()}
        for type_id, attributes in dogma.items()
    }
    names = {
        FENRIR_ID: "Fenrir",
        EXPANDED_CARGOHOLD_II_ID: "Expanded Cargohold II",
        INERTIAL_STABILIZERS_II_ID: "Inertial Stabilizers II",
        REINFORCED_BULKHEADS_II_ID: "Reinforced Bulkheads II",
        ROGUE_EVASIVE_MANEUVERING_EM_705_ID: "Eifyr and Co. 'Rogue' Evasive Maneuvering EM-705",
        ROGUE_WARP_DRIVE_SPEED_WS_615_ID: "Eifyr and Co. 'Rogue' Warp Drive Speed WS-615",
        LOW_GRADE_NOMAD_ALPHA_ID: "Low-grade Nomad Alpha",
        LOW_GRADE_NOMAD_BETA_ID: "Low-grade Nomad Beta",
    }
    groups = {
        EXPANDED_CARGOHOLD_II_ID: "Expanded Cargohold",
        INERTIAL_STABILIZERS_II_ID: "Inertial Stabilizer",
        REINFORCED_BULKHEADS_II_ID: "Reinforced Bulkhead",
    }
    group_ids = {
        ROGUE_EVASIVE_MANEUVERING_EM_705_ID: 747,
        ROGUE_WARP_DRIVE_SPEED_WS_615_ID: 747,
        LOW_GRADE_NOMAD_ALPHA_ID: 300,
        LOW_GRADE_NOMAD_BETA_ID: 300,
    }
    direct_agility_effect = {
        "effect_id": 395,
        "modifier_info": [{
            "domain": "shipID",
            "func": "ItemModifier",
            "modified_attribute_name": "agility",
            "modifying_attribute_name": "agilitybonus",
            "operation": 6,
        }],
    }
    nomad_set_effect = {
        "effect_id": 3496,
        "modifier_info": [{
            "domain": "charID",
            "func": "LocationGroupModifier",
            "groupID": 300,
            "modified_attribute_name": "agilitybonus",
            "modifying_attribute_name": "implantsetthukker",
            "operation": 0,
        }],
    }
    dogma_effects = {
        ROGUE_EVASIVE_MANEUVERING_EM_705_ID: [direct_agility_effect],
        ROGUE_WARP_DRIVE_SPEED_WS_615_ID: [{
            "effect_id": 856,
            "modifier_info": [{
                "domain": "shipID",
                "func": "ItemModifier",
                "modified_attribute_name": "warpspeedmultiplier",
                "modifying_attribute_name": "warpsbonus",
                "operation": 6,
            }],
        }],
        LOW_GRADE_NOMAD_ALPHA_ID: [direct_agility_effect, nomad_set_effect],
        LOW_GRADE_NOMAD_BETA_ID: [direct_agility_effect, nomad_set_effect],
    }
    return compute_fitting_stats(
        fitting,
        dogma,
        names,
        groups,
        {
            NAVIGATION_TYPE_ID: navigation_level,
            MINMATAR_FREIGHTER_ID: 4,
            SPACESHIP_COMMAND_TYPE_ID: 5,
            EVASIVE_MANEUVERING_TYPE_ID: evasive_maneuvering_level,
            ADVANCED_SPACESHIP_COMMAND_TYPE_ID: 5,
            CAPACITOR_MANAGEMENT_TYPE_ID: 5,
            CAPACITOR_SYSTEMS_OPERATION_TYPE_ID: 5,
        },
        {},
        {},
        435_000.0,
        ship_mass=820_000_000.0,
        dogma_effects=dogma_effects,
        implant_type_ids=implant_type_ids or set(),
        type_group_ids=group_ids,
    )


def cargo_capacity(stats: dict) -> float:
    return next(row["capacity"] for row in stats["cargo_bays"] if row["key"] == "Cargo")


def test_fenrir_cargo_uses_sde_hull_skill_and_module_multipliers() -> None:
    base = fenrir_stats([])
    one_expander = fenrir_stats([
        fitting_item(1, EXPANDED_CARGOHOLD_II_ID, "LoSlot0", "Expanded Cargohold II"),
    ])
    two_expanders = fenrir_stats([
        fitting_item(1, EXPANDED_CARGOHOLD_II_ID, "LoSlot0", "Expanded Cargohold II"),
        fitting_item(2, EXPANDED_CARGOHOLD_II_ID, "LoSlot1", "Expanded Cargohold II"),
    ])

    expected_base = 435_000.0 * 1.20
    assert cargo_capacity(base) == pytest.approx(expected_base)
    assert cargo_capacity(one_expander) == pytest.approx(expected_base * 1.275)
    assert cargo_capacity(two_expanders) == pytest.approx(expected_base * 1.275 * 1.275)
    assert cargo_capacity(two_expanders) == pytest.approx(848_576.25)
    assert two_expanders["defense"]["structure_hp"] == pytest.approx(78_000.0 * 0.77 * 0.77)


def test_fenrir_only_applies_online_modules_in_valid_fitting_slots() -> None:
    cargo_expander = fitting_item(1, EXPANDED_CARGOHOLD_II_ID, "Cargo", "Expanded Cargohold II")
    offline_expander = fitting_item(2, EXPANDED_CARGOHOLD_II_ID, "LoSlot0", "Expanded Cargohold II", "offline")
    stats = fenrir_stats([cargo_expander, offline_expander])

    assert cargo_capacity(stats) == pytest.approx(435_000.0 * 1.20)
    assert stats["defense"]["structure_hp"] == pytest.approx(78_000.0)


def test_fenrir_inertial_stabilizer_and_expander_penalties_are_derived() -> None:
    stats = fenrir_stats([
        fitting_item(1, EXPANDED_CARGOHOLD_II_ID, "LoSlot0", "Expanded Cargohold II"),
        fitting_item(2, INERTIAL_STABILIZERS_II_ID, "LoSlot1", "Inertial Stabilizers II"),
    ])

    expected_inertia = 0.0625 * 0.90 * 0.80 * 0.75 * 0.80
    expected_align = 1.38629436112 * 820_000_000.0 * expected_inertia / 1_000_000.0

    assert stats["mobility"]["signature_radius"] == pytest.approx(10_385.0 * 1.11)
    assert stats["mobility"]["max_velocity"] == pytest.approx(81.0 * 1.20 * 0.82)
    assert stats["mobility"]["mass"] == pytest.approx(820_000_000.0)
    assert stats["mobility"]["align_time"] == pytest.approx(expected_align)
    assert stats["mobility"]["align_time"] == pytest.approx(30.69, abs=0.01)


def test_fenrir_bulkhead_uses_dogma_cargo_structure_and_role_cpu_modifiers() -> None:
    item = fitting_item(1, REINFORCED_BULKHEADS_II_ID, "LoSlot0", "Reinforced Bulkheads II")
    stats = fenrir_stats([item])
    usage = item_resource_usage(
        item,
        {normalize_attr("cpu"): 40.0, normalize_attr("power"): 1.0},
        "Reinforced Bulkhead",
        {},
        {normalize_attr("cpuNeedBonus"): -100.0},
    )

    assert cargo_capacity(stats) == pytest.approx(435_000.0 * 1.20 * 0.89)
    assert stats["defense"]["structure_hp"] == pytest.approx(78_000.0 * 1.25)
    assert usage["cpu"] == pytest.approx(0.0)
    assert usage["powergrid"] == pytest.approx(1.0)


def test_fenrir_velocity_skill_and_navigation_are_separate_multipliers() -> None:
    stats = fenrir_stats([], navigation_level=5)

    assert stats["mobility"]["max_velocity"] == pytest.approx(81.0 * 1.25 * 1.20)


def test_fenrir_capacitor_uses_imported_character_skill_bonuses() -> None:
    stats = fenrir_stats([])

    assert stats["capacitor"]["capacity"] == pytest.approx(3_750.0)
    assert stats["capacitor"]["recharge_time"] == pytest.approx(138.6)
    assert stats["capacitor"]["peak_recharge"] == pytest.approx(67.64069264)

def test_selected_direct_mobility_implants_apply_from_dogma_effects() -> None:
    stats = fenrir_stats(
        [],
        implant_type_ids={ROGUE_EVASIVE_MANEUVERING_EM_705_ID, ROGUE_WARP_DRIVE_SPEED_WS_615_ID},
    )
    base_inertia = 0.0625 * 0.90 * 0.80 * 0.75
    expected_align = 1.38629436112 * 820_000_000.0 * base_inertia * 0.95 / 1_000_000.0

    assert stats["mobility"]["align_time"] == pytest.approx(expected_align)
    assert stats["mobility"]["warp_speed"] == pytest.approx(1.5 * 1.15)
    assert stats["mobility"]["implant_modifiers_applied"] == 2


def test_nomad_set_bonus_amplifies_selected_nomad_agility_effects() -> None:
    stats = fenrir_stats(
        [],
        implant_type_ids={LOW_GRADE_NOMAD_ALPHA_ID, LOW_GRADE_NOMAD_BETA_ID},
    )
    set_strength = 1.025 * 1.025
    implant_multiplier = (1 - 0.01 * set_strength) * (1 - 0.02 * set_strength)
    base_inertia = 0.0625 * 0.90 * 0.80 * 0.75
    expected_align = 1.38629436112 * 820_000_000.0 * base_inertia * implant_multiplier / 1_000_000.0

    assert stats["mobility"]["align_time"] == pytest.approx(expected_align)
    assert stats["mobility"]["implant_modifiers_applied"] == 2


def test_stacking_penalty_helper_remains_for_penalized_ship_attributes() -> None:
    assert stacking_raw_multiplier([0.9, 0.9]) == pytest.approx(0.9 * (1 + (0.9 - 1) * 0.8708869))


def test_sde_weapon_and_drone_groups_are_classified_without_false_positives() -> None:
    assert is_turret_group("Hybrid Weapon")
    assert is_turret_group("Projectile Weapon")
    assert is_turret_group("Energy Weapon")
    assert is_drone_group("Combat Drone")
    assert not is_drone_group("Drone Control Range Module")
    assert not is_drone_group("Drone Damage Module")


def test_active_modules_require_running_state_while_passive_modules_only_require_online() -> None:
    afterburner = fitting_item(1, 10, "MedSlot0", "10MN Afterburner II", "online")
    expander = fitting_item(2, EXPANDED_CARGOHOLD_II_ID, "LoSlot0", "Expanded Cargohold II", "online")

    assert not item_effects_apply(afterburner, {"speedfactor": 135.0}, "Afterburner", "10MN Afterburner II")
    afterburner.simulation_state = "active"
    assert item_effects_apply(afterburner, {"speedfactor": 135.0}, "Afterburner", "10MN Afterburner II")
    assert item_effects_apply(expander, {"cargocapacitymultiplier": 1.275}, "Expanded Cargohold", "Expanded Cargohold II")


def test_common_targeting_skills_apply_to_range_scan_resolution_and_matching_sensor() -> None:
    ship_id = 900_001
    fitting = SimpleNamespace(ship_type_id=ship_id, items=[])
    dogma = {
        ship_id: {
            "maxTargetRange": 55_000.0,
            "scanResolution": 260.0,
            "scanGravimetricStrength": 17.0,
            "maxVelocity": 190.0,
        },
    }
    dogma = {
        type_id: {normalize_attr(attribute_name): value for attribute_name, value in attributes.items()}
        for type_id, attributes in dogma.items()
    }

    stats = compute_fitting_stats(
        fitting,
        dogma,
        {ship_id: "Reference Cruiser"},
        {},
        {},
        {
            "Long Range Targeting": 5,
            "Signature Analysis": 5,
            "Gravimetric Sensor Compensation": 5,
        },
        {},
    )

    assert stats["targeting"]["targeting_range"] == pytest.approx(68_750.0)
    assert stats["targeting"]["scan_resolution"] == pytest.approx(325.0)
    assert stats["targeting"]["sensor_strength"] == pytest.approx(20.4)


def test_afterburner_velocity_uses_thrust_mass_and_acceleration_control() -> None:
    ship_id = 900_002
    afterburner_id = 900_003
    afterburner = fitting_item(1, afterburner_id, "MedSlot0", "10MN Afterburner II", "active")
    fitting = SimpleNamespace(ship_type_id=ship_id, items=[afterburner])
    dogma = {
        ship_id: {"maxVelocity": 190.0, "medSlots": 1.0},
        afterburner_id: {"speedFactor": 135.0, "speedBoostFactor": 15_000_000.0, "massAddition": 5_000_000.0},
    }
    dogma = {
        type_id: {normalize_attr(attribute_name): value for attribute_name, value in attributes.items()}
        for type_id, attributes in dogma.items()
    }

    stats = compute_fitting_stats(
        fitting,
        dogma,
        {ship_id: "Moa", afterburner_id: "10MN Afterburner II"},
        {afterburner_id: "Afterburner"},
        {NAVIGATION_TYPE_ID: 5},
        {"Acceleration Control": 5},
        {},
        ship_mass=12_000_000.0,
    )

    expected = 190.0 * 1.25 * (1 + 1.35 * 1.25 * 15_000_000.0 / 17_000_000.0)
    assert stats["mobility"]["max_velocity"] == pytest.approx(expected)


def test_afterburner_capacitor_applies_both_cap_skills_and_cycle_skill() -> None:
    ship_id = 900_004
    afterburner_id = 900_005
    fuel_conservation_id = 900_006
    afterburner_skill_id = 900_007
    afterburner = fitting_item(1, afterburner_id, "MedSlot0", "10MN Afterburner II", "active")
    fitting = SimpleNamespace(ship_type_id=ship_id, items=[afterburner])
    dogma = {
        ship_id: {"capacitorCapacity": 1_000.0, "rechargeRate": 200_000.0, "medSlots": 1.0},
        afterburner_id: {"capacitorNeed": 90.0, "duration": 10_000.0},
        fuel_conservation_id: {"capNeedBonus": -10.0},
        afterburner_skill_id: {"capNeedBonus": -10.0, "durationBonus": -5.0},
    }
    dogma = {
        type_id: {normalize_attr(attribute_name): value for attribute_name, value in attributes.items()}
        for type_id, attributes in dogma.items()
    }

    stats = compute_fitting_stats(
        fitting,
        dogma,
        {
            ship_id: "Reference Cruiser",
            afterburner_id: "10MN Afterburner II",
            fuel_conservation_id: "Fuel Conservation",
            afterburner_skill_id: "Afterburner",
        },
        {afterburner_id: "Propulsion Module"},
        {},
        {"Fuel Conservation": 5, "Afterburner": 5},
        {},
    )

    # 90 GJ * 50% * 50% over a 10 s cycle shortened by 25% = 3 GJ/s.
    assert stats["capacitor"]["draw_per_second"] == pytest.approx(3.0)
    assert stats["capacitor"]["modules"][0]["cycle_seconds"] == pytest.approx(7.5)


def test_shield_booster_repair_amount_is_not_added_to_shield_capacity() -> None:
    ship_id = 900_008
    booster_id = 900_009
    booster = fitting_item(1, booster_id, "MedSlot0", "Medium Shield Booster II", "active")
    fitting = SimpleNamespace(ship_type_id=ship_id, items=[booster])
    dogma = {
        ship_id: {"shieldCapacity": 1_000.0, "medSlots": 1.0},
        booster_id: {"shieldBonus": 104.0, "duration": 3_000.0},
    }
    dogma = {
        type_id: {normalize_attr(attribute_name): value for attribute_name, value in attributes.items()}
        for type_id, attributes in dogma.items()
    }

    stats = compute_fitting_stats(
        fitting,
        dogma,
        {ship_id: "Reference Cruiser", booster_id: "Medium Shield Booster II"},
        {booster_id: "Shield Booster"},
        {},
        {},
        {},
    )

    assert stats["defense"]["shield_hp"] == pytest.approx(1_000.0)
    assert stats["defense"]["shield_repair_hps"] == pytest.approx(104.0 / 3.0)


def test_turret_capacitor_draw_uses_applicable_hull_rate_of_fire_bonus() -> None:
    railgun_id = 900_010
    railgun_group_id = 900_011
    railgun = fitting_item(1, railgun_id, "HiSlot0", "200mm Railgun II", "active")
    dogma = {railgun_id: {normalize_attr("capacitorNeed"): 4.5, normalize_attr("speed"): 4_000.0}}
    hull_weapon_rules = [{
        "target": "speed",
        "multiplier": 0.75,
        "group_id": railgun_group_id,
        "required_skill_id": None,
    }]

    draw, modules = active_capacitor_use_per_second(
        [railgun],
        dogma,
        {railgun_id: "200mm Railgun II"},
        {railgun_id: "Hybrid Weapon"},
        {},
        {},
        hull_weapon_rules,
        {railgun_id: railgun_group_id},
    )

    assert draw == pytest.approx(1.5)
    assert modules[0]["cycle_seconds"] == pytest.approx(3.0)


def test_multiple_cap_rechargers_use_sde_stackable_multiplier_without_penalty() -> None:
    ship_id = 900_012
    recharger_id = 900_013
    fitting = SimpleNamespace(
        ship_type_id=ship_id,
        items=[
            fitting_item(1, recharger_id, "MedSlot0", "Cap Recharger II"),
            fitting_item(2, recharger_id, "MedSlot1", "Cap Recharger II"),
        ],
    )
    dogma = {
        ship_id: {"capacitorCapacity": 1_000.0, "rechargeRate": 100_000.0, "medSlots": 2.0},
        recharger_id: {"capacitorRechargeRateMultiplier": 0.8},
    }
    dogma = {
        type_id: {normalize_attr(attribute_name): value for attribute_name, value in attributes.items()}
        for type_id, attributes in dogma.items()
    }

    stats = compute_fitting_stats(
        fitting,
        dogma,
        {ship_id: "Reference Cruiser", recharger_id: "Cap Recharger II"},
        {recharger_id: "Capacitor Recharger"},
        {},
        {},
        {},
    )

    assert stats["capacitor"]["recharge_time"] == pytest.approx(64.0)
