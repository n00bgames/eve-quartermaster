from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.fittings import (esi_fitting_payload, fitting_copy_text, load_fighter_tube,
                              normalize_draft_fitting_items, update_fitting_item, validate_fighter_tube)
from app.models import (Base, CharacterFitting, CharacterFittingItem, CharacterSkill, EveCharacter,
                        EveDogmaAttribute, EveDogmaEffect, EveGroup, EveType, EveTypeDogmaAttribute,
                        EveTypeDogmaEffect, User)
from app.services.fitting_fighters import add_fighter_stats, compute_fighters, fighter_limits, normalized
from app.services.fitting_simulator import simulate_fitting

SOURCE = json.loads((Path(__file__).parent / "fixtures/fitting-fighters-sde.v1.json").read_text())
NAMES = {int(k): v["name"] for k, v in SOURCE["types"].items()}
DOGMA = {int(k): {normalized(SOURCE["attributes"][str(a["attributeID"])]): a["value"]
                  for a in v["dogmaAttributes"]} for k, v in SOURCE["dogma"].items()}
EFFECTS = {}
for key, row in SOURCE["dogma"].items():
    EFFECTS[int(key)] = []
    for ref in row["dogmaEffects"]:
        effect = SOURCE["effects"][str(ref["effectID"])]
        modifiers = [{**m,
                      "modified_attribute_name": SOURCE["attributes"].get(str(m.get("modifiedAttributeID"))),
                      "modifying_attribute_name": SOURCE["attributes"].get(str(m.get("modifyingAttributeID")))}
                     for m in effect["modifierInfo"]]
        EFFECTS[int(key)].append({"name": effect["name"], "modifier_info": modifiers})

SKILLS = {23069: 5, 32339: 5, 92398: 5, 24311: 5, 24312: 5, 24313: 5, 24314: 5}
SKILL_NAMES = {NAMES[k]: v for k, v in SKILLS.items()}


def item(type_id=40558, flag="FighterTube0", quantity=6, state="active", id=1):
    return SimpleNamespace(id=id, type_id=type_id, flag=flag, quantity=quantity, simulation_state=state,
                           charge_type_id=None, item_type=SimpleNamespace(name=NAMES[type_id]), charge_type=None)


def fitting(ship=24483, items=None):
    return SimpleNamespace(ship_type_id=ship, items=items if items is not None else [item()],
                           ship_type=SimpleNamespace(name=NAMES[ship]), name="Synthetic fighter fit", description="Synthetic fixture")


def evaluate(fit=None, **kwargs):
    return compute_fighters(fit or fitting(), DOGMA, NAMES, EFFECTS, SKILLS, SKILL_NAMES, **kwargs)


@pytest.mark.parametrize("ship,expected", [(24483, 4), (23913, 5), (3514, 5), (45647, 2), (45649, 2)])
def test_tube_counts_come_from_current_sde(ship, expected):
    assert fighter_limits(DOGMA[ship])["tubes"] == expected


def test_carrier_skill_fighters_and_racial_specialization_multiply_once():
    # Firbolg II: 124.5 damage x 6 fighters / 5 sec; Fighters V +25%,
    # Gallente Fighter Specialization V +10%, Minmatar Carrier V +25%.
    assert evaluate()["primary_dps"] == pytest.approx(124.5 * 6 / 5 * 1.25 * 1.1 * 1.25)


@pytest.mark.parametrize("ship_name, tubes", [("Archon", 4), ("Chimera", 4), ("Thanatos", 4),
    ("Nidhoggur", 4), ("Aeon", 5), ("Wyvern", 5), ("Hel", 5), ("Nyx", 5),
    ("Revenant", 5), ("Vendetta", 5), ("Caiman", 2), ("Komodo", 2)])
def test_all_carrier_families_and_guristas_hybrids_use_their_sde_tubes(ship_name, tubes):
    ship = next(k for k, name in NAMES.items() if name == ship_name)
    result = evaluate(fitting(ship))
    assert result["tube_count"] == tubes
    assert result["primary_dps"] > 0
    assert not result["warnings"]


def test_fighters_add_to_mixed_weapon_totals_without_replacing_other_damage():
    base = {"offense": {"turret_dps":100, "launcher_dps":500, "drone_dps":10,
                       "total_dps":610, "volley":900, "damage_types":dict.fromkeys(("em","thermal","kinetic","explosive"),25),
                       "weapon_count":3, "weapons":[], "max_range_m":100000}, "notes":[]}
    result = add_fighter_stats(base, fitting(), DOGMA, NAMES, EFFECTS, SKILLS, SKILL_NAMES)
    assert result["offense"]["total_dps"] == pytest.approx(610 + evaluate()["total_dps"])
    assert result["offense"]["launcher_dps"] == 500
    assert result["offense"]["turret_dps"] == 100
    assert result["offense"]["drone_dps"] == 10
    assert result["offense"]["weapon_count"] == 4
    assert result["offense"]["volley"] > 900
    assert result["offense"]["max_range_m"] == 100000


def test_revenant_applies_both_carrier_skill_bonuses():
    assert evaluate(fitting(3514))["primary_dps"] == pytest.approx(124.5 * 6 / 5 * 1.25 * 1.1 * 1.25 * 1.25)


def test_caiman_role_bonus_two_tubes_no_carrier_skill_or_drone_interfacing_bonus():
    fit = fitting(45647, [item(), item(flag="FighterTube1", id=2)])
    result = evaluate(fit)
    assert result["total_dps"] == pytest.approx(2 * 124.5 * 6 / 5 * 1.25 * 1.1 * 2)
    assert compute_fighters(fit, DOGMA, NAMES, EFFECTS, {**SKILLS, 3436: 5},
                            {**SKILL_NAMES, "Drone Interfacing": 5})["total_dps"] == result["total_dps"]


@pytest.mark.parametrize("quantity", [1, 3, 6])
def test_partial_squadron_damage_scales_with_living_fighters(quantity):
    assert evaluate(fitting(items=[item(quantity=quantity)]))["total_dps"] == pytest.approx(evaluate()["total_dps"] * quantity / 6)


@pytest.mark.parametrize("flag,state", [("FighterBay", "active"), ("Cargo", "active"), ("FighterTube0", "online"), ("FighterTube0", "offline")])
def test_reserves_and_non_deployed_squadrons_deal_no_damage(flag, state):
    result = evaluate(fitting(items=[item(flag=flag, quantity=6, state=state)]))
    assert result["total_dps"] == 0
    assert result["weapons"] == []


def test_damage_amplifiers_stack_and_support_units_reduce_ability_cycle():
    fit = fitting(items=[item(), item(4405, "LoSlot0", 1, "online", 2),
                         item(4405, "LoSlot1", 1, "online", 3), item(24283, "HiSlot0", 1, "online", 4)])
    expected = evaluate()["primary_dps"] * 1.205 * (1 + .205 * .8708869) / .95
    assert evaluate(fit)["primary_dps"] == pytest.approx(expected)
    fit.items[-1].simulation_state = "offline"
    assert evaluate(fit)["primary_dps"] == pytest.approx(expected * .95)
    assert evaluate(fit, stats_item_ids=set())["primary_dps"] == pytest.approx(evaluate()["primary_dps"])


def test_salvo_is_optional_limited_ammo_burst_separate_from_primary():
    primary, burst = evaluate(), evaluate(include_salvos=True)
    assert primary["total_dps"] == primary["primary_dps"]
    assert primary["salvo_dps"] > 0
    assert burst["total_dps"] == pytest.approx(primary["primary_dps"] + primary["salvo_dps"])
    assert burst["weapons"][0]["volley"] > primary["weapons"][0]["volley"]


def test_superiority_micro_missiles_are_primary_and_ship_damage_is_reduced():
    fit = fitting(items=[item(40553, quantity=12)])
    anti_fighter = evaluate(fit, target_kind="fighter")
    anti_ship = evaluate(fit, target_kind="capital")
    assert anti_fighter["primary_dps"] > 0
    assert anti_fighter["salvo_dps"] == 0
    assert anti_ship["primary_dps"] == pytest.approx(anti_fighter["primary_dps"] * .05)
    assert evaluate(fit, target_kind="fighter", include_salvos=True)["total_dps"] == anti_fighter["total_dps"]


def test_heavy_fighter_skill_and_anti_capital_salvo_target_reduction():
    cyclops = next(k for k, name in NAMES.items() if name == "Cyclops I")
    fit = fitting(23913, [item(cyclops)])
    capital = evaluate(fit, target_kind="capital", include_salvos=True)
    small = evaluate(fit, target_kind="subcapital", include_salvos=True)
    assert capital["primary_dps"] == pytest.approx(366 * 6 / 5 * 1.25 * 1.25 * 1.5)
    assert small["salvo_dps"] == pytest.approx(capital["salvo_dps"] * .1)


def test_support_squadron_is_valid_but_does_not_invent_weapon_damage():
    siren = next(k for k, name in NAMES.items() if name == "Siren I")
    result = evaluate(fitting(items=[item(siren, quantity=3)]))
    assert result["tubes"][0]["valid"]
    assert result["total_dps"] == 0


@pytest.mark.parametrize("fit", [fitting(items=[item(quantity=7)]),
    fitting(items=[item(flag="FighterTube4")]), fitting(items=[item(), item(id=2)]),
    fitting(45647, [item(next(k for k, name in NAMES.items() if name == "Cyclops I"))])])
def test_invalid_size_tube_duplicate_or_class_never_add_damage(fit):
    result = evaluate(fit)
    assert result["total_dps"] == 0
    assert result["warnings"]


def test_more_active_light_squadrons_than_hull_limit_do_not_inflate_damage():
    fit = fitting(items=[item(flag=f"FighterTube{i}", id=i+1) for i in range(4)])
    result = evaluate(fit)
    assert result["deployed"]["light"] == 3
    assert result["total_dps"] == pytest.approx(evaluate()["total_dps"] * 3)
    assert len(result["warnings"]) == 1


def test_eft_and_esi_flatten_loaded_squadrons_into_fighter_inventory():
    fit = fitting(items=[item(), item(flag="FighterBay", quantity=12, id=2)])
    assert esi_fitting_payload(fit)["items"] == [{"flag": "FighterBay", "quantity": 18, "type_id": 40558}]
    text = fitting_copy_text(fit)
    assert "Firbolg II x6" in text and "Firbolg II x12" in text
    assert "FighterTube" not in text


@pytest.fixture
def database(monkeypatch):
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "eqm_fitting_engine", "python")
    monkeypatch.setattr(settings, "eqm_fitting_stats_engine", "python")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="fighter-test@example.invalid", display_name="Synthetic Pilot", role="admin")
        db.add(user); db.flush()
        character = EveCharacter(character_id=90000001, name="Synthetic Pilot", owner_user_id=user.id)
        db.add(character); db.flush()
        for key, name in SOURCE["groups"].items():
            db.add(EveGroup(group_id=int(key), name=name, published=True))
        for key, row in SOURCE["types"].items():
            db.add(EveType(type_id=int(key), name=row["name"], group_id=row["group_id"], published=True,
                           volume=row.get("volume"), mass=row.get("mass"), capacity=row.get("capacity")))
        for key, name in SOURCE["attributes"].items():
            db.add(EveDogmaAttribute(attribute_id=int(key), name=name))
        for key, row in SOURCE["effects"].items():
            db.add(EveDogmaEffect(effect_id=int(key), name=row["name"], category_id=row["effectCategoryID"], modifier_info=row["modifierInfo"]))
        db.flush()
        for key, row in SOURCE["dogma"].items():
            db.add_all(EveTypeDogmaAttribute(type_id=int(key), attribute_id=a["attributeID"], value=a["value"]) for a in row["dogmaAttributes"])
            db.add_all(EveTypeDogmaEffect(type_id=int(key), effect_id=e["effectID"], is_default=e["isDefault"]) for e in row["dogmaEffects"])
        db.add_all(CharacterSkill(character_id=character.id, skill_type_id=k, trained_skill_level=v, active_skill_level=v, skillpoints_in_skill=0) for k,v in SKILLS.items())
        fit = CharacterFitting(character_id=character.id, ship_type_id=24483, name="Synthetic carrier", is_draft=True)
        db.add(fit); db.commit()
        yield db, user, character, fit
    engine.dispose()


def test_loading_and_unloading_reserves_preserves_stock_and_tube_position(database):
    db, user, character, fit = database
    reserve = CharacterFittingItem(fitting_id=fit.id, type_id=40558, flag="FighterBay", quantity=15, simulation_state="online")
    db.add(reserve); db.commit()
    result = load_fighter_tube(fit.id, 2, {"source_item_id": reserve.id}, user, db)
    assert sum(row["quantity"] for row in result["items"]) == 15
    tube = next(row for row in result["items"] if row["flag"] == "FighterTube2")
    assert tube["quantity"] == 6
    assert not normalize_draft_fitting_items(db, fit)
    sim = simulate_fitting(db, fit, character)
    assert sim["stats"]["offense"]["fighter_dps"] == pytest.approx(evaluate()["total_dps"])
    assert sim["stats"]["offense"]["drone_dps"] == 0
    assert sim["stats"]["offense"]["total_dps"] == sim["stats"]["offense"]["fighter_dps"]
    bay = next(row for row in sim["stats"]["cargo_bays"] if row["key"] == "FighterBay")
    assert bay["used"] == SOURCE["types"]["40558"]["volume"] * 15
    result = update_fitting_item(fit.id, tube["id"], {"flag":"FighterBay", "simulation_state":"online"}, user, db)
    assert sum(row["quantity"] for row in result["items"] if row["flag"] == "FighterBay") == 15
    assert simulate_fitting(db, fit, character)["stats"]["offense"]["fighter_dps"] == 0


def test_loading_occupied_tube_or_foreign_reserve_refuses_without_inventory_change(database):
    db, user, _, fit = database
    load_fighter_tube(fit.id, 0, {"type_id":40558}, user, db)
    with pytest.raises(HTTPException) as error:
        load_fighter_tube(fit.id, 0, {"type_id":40558}, user, db)
    assert error.value.status_code == 400
    with pytest.raises(HTTPException):
        load_fighter_tube(fit.id, 1, {"source_item_id":999999}, user, db)
    assert len(fit.items) == 1


def test_simulated_fighter_total_is_preserved_when_rust_supplies_base_stats(database, monkeypatch):
    db, user, character, fit = database
    load_fighter_tube(fit.id, 0, {"type_id":40558}, user, db)
    python = simulate_fitting(db, fit, character)
    def rust_base(*, payload, python_result, **_):
        result = copy.deepcopy(python_result)
        assert "fighters" not in result
        assert result["offense"]["drone_dps"] == 0
        result.update(engine_used="rust", engine_requested="rust")
        return result
    monkeypatch.setattr("app.services.fitting_simulator.evaluate_fitting_stats_with_engine", rust_base)
    rust = simulate_fitting(db, fit, character)
    assert rust["stats_engine_used"] == "rust"
    assert rust["stats"]["offense"] == python["stats"]["offense"]
    assert rust["stats"]["fighters"] == python["stats"]["fighters"]
