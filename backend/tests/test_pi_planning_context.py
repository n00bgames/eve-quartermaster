"""Exercise the real database serializer, not a mocked planning context."""
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, CharacterSkill, EveCharacter, EveType, EvePlanetSchematic, EvePlanetSchematicInput, PlanetaryColony, PlanetaryPin
from app.schemas.pi_planner import PlanetChoice
from app.services.pi_planning_context import build_context
from tests.test_pi_planner import SCHEMATICS


def test_context_from_database_uses_active_skills_and_normalizes_esi_planets():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        commodities = {i["type_id"]: i for r in SCHEMATICS for i in [r["output"], *r["inputs"]]}
        db.add_all(EveType(type_id=t, name=i["name"], volume=i["volume"]) for t, i in commodities.items())
        for r in SCHEMATICS:
            db.add(EvePlanetSchematic(schematic_id=r["id"], name=r["name"], cycle_time=r["cycle_time"], output_type_id=r["output"]["type_id"], output_quantity=r["output"]["quantity"], inputs=[EvePlanetSchematicInput(type_id=i["type_id"], quantity=i["quantity"]) for i in r["inputs"]]))
        pilot = EveCharacter(id=1, character_id=10001, name="Visible pilot", skills_synced_at=now)
        private = EveCharacter(id=2, character_id=10002, name="Other pilot")
        db.add_all([pilot, private, CharacterSkill(character_id=1, skill_type_id=2505, active_skill_level=4, trained_skill_level=5)])
        db.add(PlanetaryColony(id=1, character_id=1, planet_id=90001, planet_name="Existing", planet_type="storm", upgrade_level=4, last_synced_at=now, pins=[PlanetaryPin(pin_id=1, type_id=3060, extractor_product_type_id=2268, install_time=now-timedelta(hours=24), expiry_time=now+timedelta(hours=24), extractor_cycle_time=1800, extractor_qty_per_cycle=6965, extractor_heads_json=[{"head_id":0}], contents_json=[{"type_id":3645,"amount":50}])]))
        db.add(PlanetaryColony(id=2, character_id=1, planet_id=90002, planet_name="Incomplete metadata", planet_type=None, upgrade_level=0, last_synced_at=now))
        db.add(PlanetaryColony(id=3, character_id=2, planet_id=90003, planet_name="Hidden", planet_type="storm", upgrade_level=0, last_synced_at=now))
        db.commit()
        value = build_context(db, [pilot])
        assert len(value["catalog"]) == 83
        assert value["pilots"][0]["ccu"] == 4  # Active, not trained level.
        assert value["pilots"][0]["ic"] == 0   # Synced but not trained.
        assert len(value["pilots"][0]["colonies"]) == 2  # Unknown type still occupies a slot.
        assert len(value["planets"]) == 1
        candidate = PlanetChoice.model_validate(value["planets"][0])
        assert candidate.planet_type == "Storm"
        assert candidate.yields[0].units_per_head_hour > 0
        assert value["baseline"]["observed_inventory"] == {3645:50}
        assert value["baseline"]["colonies"] == 2
    engine.dispose()
