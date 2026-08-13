from types import SimpleNamespace

from app.api.fittings import charge_type_is_compatible, fitting_slot_prefix_for_type
from app.services.fitting_simulator import charge_is_compatible_with_module, normalize_attr


def item_type(name: str, group: str, category: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        group=SimpleNamespace(name=group, category=SimpleNamespace(name=category)),
    )


def test_drone_named_modules_remain_in_their_fitting_sections() -> None:
    assert fitting_slot_prefix_for_type(
        item_type("Drone Damage Amplifier II", "Drone Damage Modules", "Module"),
        "LoSlot",
    ) == "LoSlot"
    assert fitting_slot_prefix_for_type(
        item_type("Omnidirectional Tracking Link II", "Drone Tracking Modules", "Module"),
        "MedSlot",
    ) == "MedSlot"
    assert fitting_slot_prefix_for_type(
        item_type("Drone Link Augmentor II", "Drone Control Range Module", "Module"),
        "HiSlot",
    ) == "HiSlot"


def test_actual_drones_and_fighters_import_to_bays() -> None:
    assert fitting_slot_prefix_for_type(
        item_type("Hammerhead II", "Combat Drone", "Drone"),
        "LoSlot",
    ) == "DroneBay"
    assert fitting_slot_prefix_for_type(
        item_type("Firbolg II", "Light Fighter", "Fighter"),
        "HiSlot",
    ) == "FighterBay"


def test_heavy_pulse_laser_accepts_medium_t2_crystals_only() -> None:
    module_type = SimpleNamespace(type_id=3520, group_id=53, name="Heavy Pulse Laser II")
    scorch_m = SimpleNamespace(type_id=12818, group_id=375, name="Scorch M")
    conflagration_l = SimpleNamespace(type_id=12816, group_id=375, name="Conflagration L")
    metadata = {
        3520: {"charge_size": 2, "compatible_charge_group_ids": [86, 375]},
        12818: {"charge_size": 2, "compatible_charge_group_ids": []},
        12816: {"charge_size": 3, "compatible_charge_group_ids": []},
    }

    assert charge_type_is_compatible(module_type, scorch_m, metadata)
    assert not charge_type_is_compatible(module_type, conflagration_l, metadata)


def test_simulator_recognizes_advanced_laser_crystal_group_and_size() -> None:
    module_attrs = {
        normalize_attr("chargeSize"): 2.0,
        normalize_attr("chargeGroup1"): 86.0,
        normalize_attr("chargeGroup2"): 375.0,
    }
    scorch_m_attrs = {normalize_attr("chargeSize"): 2.0}
    scorch_s_attrs = {normalize_attr("chargeSize"): 1.0}

    assert charge_is_compatible_with_module(
        "Heavy Pulse Laser II",
        "Energy Weapon",
        "Scorch M",
        "Advanced Pulse Laser Crystal",
        module_attrs,
        scorch_m_attrs,
        375,
    )
    assert not charge_is_compatible_with_module(
        "Heavy Pulse Laser II",
        "Energy Weapon",
        "Scorch S",
        "Advanced Pulse Laser Crystal",
        module_attrs,
        scorch_s_attrs,
        375,
    )
