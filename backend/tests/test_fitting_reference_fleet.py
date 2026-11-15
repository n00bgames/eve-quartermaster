from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.fittings import parse_eft_fit
from app.core.config import get_settings
from app.models import (
    Base,
    CharacterFitting,
    CharacterFittingItem,
    CharacterSkill,
    EveCategory,
    EveCharacter,
    EveDogmaAttribute,
    EveDogmaEffect,
    EveGroup,
    EveType,
    EveTypeDogmaAttribute,
    EveTypeDogmaEffect,
)
from app.services.fitting_simulator import simulate_fitting
from tests.fitting_reference import (
    FIXTURE_ROOT,
    compute_reference_fixture,
    load_reference_fixture,
    metric_at_path,
    reference_fixture_paths,
)


REFERENCE_FIXTURES = reference_fixture_paths()
PYFA_DIR = FIXTURE_ROOT / "pyfa-all-v"
PYFA_EVIDENCE = FIXTURE_ROOT / "evidence" / "pyfa-all-v-2026-08-11.json"
SKILL_CATEGORY_ID = 16
ACTIVE_MODULES = {
    "10MN Afterburner II",
    "200mm Railgun II",
    "Medium Armor Repairer II",
    "Medium Shield Booster II",
    "Multispectrum Shield Hardener II",
    "Omnidirectional Tracking Link II",
    "Rapid Light Missile Launcher II",
}


@pytest.fixture(scope="module")
def pyfa_catalog() -> Iterator[Session]:
    catalog = json.loads((PYFA_DIR / "catalog.json").read_text(encoding="utf-8"))
    database = create_engine("sqlite://")
    models = (
        EveCategory, EveGroup, EveType, EveDogmaAttribute, EveDogmaEffect,
        EveTypeDogmaAttribute, EveTypeDogmaEffect, CharacterSkill,
    )
    Base.metadata.create_all(database, tables=[model.__table__ for model in models])
    with Session(database) as db:
        db.add_all(EveCategory(category_id=int(key), name=name) for key, name in catalog["categories"].items())
        for key, row in catalog["groups"].items():
            db.add(EveGroup(group_id=int(key), category_id=row["categoryID"], name=row["name"]))
        for key, name in catalog["attributes"].items():
            db.add(EveDogmaAttribute(attribute_id=int(key), name=name))
        for key, row in catalog["effects"].items():
            db.add(EveDogmaEffect(
                effect_id=int(key), name=row["name"], category_id=row.get("effectCategoryID"),
                modifier_info=row.get("modifierInfo"),
            ))
        for key, row in catalog["types"].items():
            type_id = int(key)
            group_id = row["groupID"]
            db.add(EveType(
                type_id=type_id, group_id=group_id, name=row["name"], volume=row.get("volume"),
                mass=row.get("mass"), capacity=row.get("capacity"),
            ))
            db.add_all(
                EveTypeDogmaAttribute(type_id=type_id, attribute_id=int(attr_id), value=value)
                for attr_id, value in row["dogmaAttributes"].items()
            )
            db.add_all(
                EveTypeDogmaEffect(type_id=type_id, effect_id=int(effect_id), is_default=default)
                for effect_id, default in row["dogmaEffects"].items()
            )
            if catalog["groups"][str(group_id)]["categoryID"] == SKILL_CATEGORY_ID:
                db.add(CharacterSkill(
                    character_id=1, skill_type_id=type_id, active_skill_level=5, trained_skill_level=5,
                ))
        db.commit()
        yield db
    database.dispose()


@pytest.fixture(scope="module")
def pyfa_recipes() -> dict[str, str]:
    text = (PYFA_DIR / "fits.eft").read_text(encoding="utf-8")
    return {recipe[1:recipe.index(",")]: recipe for recipe in re.split(r"\n\n(?=\[)", text)}


@pytest.fixture(scope="module")
def pyfa_captures() -> dict[str, dict[str, Any]]:
    evidence = json.loads(PYFA_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["source"]["externally_verified"]
    return {capture["name"]: capture for capture in evidence["captures"]}


def simulate_pyfa_fit(db: Session, recipe: str, active_flight: str | None) -> dict[str, Any]:
    ship, fit_name, parsed_items, warnings = parse_eft_fit(db, recipe)
    assert not warnings, warnings
    fitting = CharacterFitting(id=1, character_id=1, ship_type_id=ship.type_id, name=fit_name)
    for item_id, row in enumerate(parsed_items, start=1):
        item_type = db.get(EveType, row["type_id"])
        if row["flag"].startswith("DroneBay"):
            row["simulation_state"] = "active" if item_type.name == active_flight else "offline"
        elif item_type.name in ACTIVE_MODULES:
            row["simulation_state"] = "active"
        fitting.items.append(CharacterFittingItem(id=item_id, item_type=item_type, **row))
    pilot = EveCharacter(id=1, name="All V")
    return simulate_fitting(db, fitting, pilot)


@pytest.mark.parametrize("fixture_path", REFERENCE_FIXTURES, ids=lambda path: path.stem)
def test_fitting_reference_fixture(fixture_path) -> None:
    fixture = load_reference_fixture(fixture_path)
    result = compute_reference_fixture(fixture)

    for expectation in fixture["expected"]:
        actual = metric_at_path(result, expectation["path"])
        assert actual == pytest.approx(
            float(expectation["value"]),
            abs=float(expectation.get("absolute_tolerance", 0.0)),
            rel=float(expectation.get("relative_tolerance", 1e-6)),
        ), f"{fixture_path.name}: {expectation['path']}"


def test_reference_fleet_contains_at_least_one_fixture() -> None:
    assert REFERENCE_FIXTURES, "Add at least one fitting reference fixture"


# (EQM path, Pyfa capture path, absolute tolerance in EQM units)
PYFA_METRICS = (
    ("resources.cpu.used", "resources.cpu_used_tf", 0.051),
    ("resources.cpu.capacity", "resources.cpu_capacity_tf", 0.051),
    ("resources.powergrid.capacity", "resources.powergrid_capacity_mw", 0.501),
    ("resources.calibration.used", "resources.calibration_used", 0),
    ("resources.calibration.capacity", "resources.calibration_capacity", 0),
    ("stats.cargo_bays[key=DroneBay].used", "resources.drone_bay_used_m3", 0),
    ("stats.cargo_bays[key=DroneBay].capacity", "resources.drone_bay_capacity_m3", 0),
    ("stats.cargo_bays[key=Cargo].capacity", "targeting_and_movement.cargo_m3", 0),
    ("stats.capacitor.capacity", "capacitor.capacity_gj", 5),
    ("stats.targeting.max_targets", "targeting_and_movement.max_targets", 0),
    ("stats.targeting.scan_resolution", "targeting_and_movement.scan_resolution_mm", 0.501),
    ("stats.targeting.sensor_strength", "targeting_and_movement.sensor_strength", 0.051),
    ("stats.mobility.max_velocity", "targeting_and_movement.max_velocity_m_s", 0.501),
    ("stats.mobility.align_time", "targeting_and_movement.align_time_s", 0.00501),
    ("stats.mobility.signature_radius", "targeting_and_movement.signature_radius_m", 0.501),
    ("stats.mobility.warp_speed", "targeting_and_movement.warp_speed_au_s", 0.051),
)


@pytest.mark.parametrize("engine", ["python", "rust"])
@pytest.mark.parametrize(("ship", "fit_name", "weapon"), [
    ("Moa", "EQM Reference 01 - Rail Moa", "turret_dps"),
    ("Caracal", "EQM Reference 02 - Rapid Light Caracal", "launcher_dps"),
    ("Vexor", "EQM Reference 03 - Active Armor Vexor", "turret_dps"),
], ids=["moa", "caracal", "vexor"])
def test_pyfa_reference_fit(
    engine, ship, fit_name, weapon, pyfa_catalog, pyfa_recipes, pyfa_captures, monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "eqm_fitting_engine", engine)
    monkeypatch.setattr(settings, "eqm_fitting_stats_engine", engine)
    capture = pyfa_captures[fit_name]
    active_capture = capture["drone_active_capture"]
    active_flight = active_capture["active_flight"].split("x ", 1)[1]
    idle = simulate_pyfa_fit(pyfa_catalog, pyfa_recipes[ship], active_flight=None)
    active = simulate_pyfa_fit(pyfa_catalog, pyfa_recipes[ship], active_flight)

    for result, expected in ((idle, capture["offense"]), (active, active_capture)):
        assert result["resource_engine_used"] == engine, result["notes"]
        assert result["stats_engine_used"] == engine, result["notes"]
        assert result["status"] == "pass", result["summary"]
        offense = result["stats"]["offense"]
        assert offense[weapon] == pytest.approx(expected["weapon_dps"], abs=0.501, rel=0)
        assert offense["drone_dps"] == pytest.approx(expected["drone_dps"], abs=0.501, rel=0)
        assert offense["total_dps"] == pytest.approx(expected["total_dps"], abs=0.501, rel=0)
        assert offense["volley"] == pytest.approx(expected["volley"], abs=1, rel=0)

    for actual_path, reference_path, tolerance in PYFA_METRICS:
        assert metric_at_path(idle, actual_path) == pytest.approx(
            metric_at_path(capture, reference_path), abs=tolerance, rel=0,
        ), actual_path

    stats = idle["stats"]
    movement = capture["targeting_and_movement"]
    assert stats["targeting"]["targeting_range"] / 1000 == pytest.approx(movement["targeting_range_km"], abs=0.051, rel=0)
    assert stats["targeting"]["drone_control_range_m"] / 1000 == movement["drone_control_range_km"]
    assert stats["capacitor"]["stable"] is (capture["capacitor"]["stable_percent"] > 0)

    # The captures and pinned SDE differ on some fitted resistances and powergrid values.
    # The fixture README records the excluded comparisons.
    for layer in ("shield", "armor", "structure"):
        if ship == "Vexor" and layer == "armor":
            continue
        for damage_type, expected in capture["defense"][f"{layer}_resists_percent"].items():
            if layer == "shield" and damage_type == "em" and ship != "Vexor":
                continue
            assert stats["defense"][f"{layer}_resists"][damage_type] * 100 == pytest.approx(
                expected, abs=0.051, rel=0,
            ), f"{layer} {damage_type} resistance"

    if ship != "Vexor":
        assert idle["resources"]["powergrid"]["used"] == pytest.approx(
            capture["resources"]["powergrid_used_mw"], abs=0.5, rel=0,
        )
