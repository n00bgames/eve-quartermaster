from types import SimpleNamespace

import pytest

from app.services.fitting_simulator import (
    ADVANCED_SPACESHIP_COMMAND_TYPE_ID,
    CAPACITOR_MANAGEMENT_TYPE_ID,
    CAPACITOR_SYSTEMS_OPERATION_TYPE_ID,
    EVASIVE_MANEUVERING_TYPE_ID,
    NAVIGATION_TYPE_ID,
    SPACESHIP_COMMAND_TYPE_ID,
    compute_fitting_stats,
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
