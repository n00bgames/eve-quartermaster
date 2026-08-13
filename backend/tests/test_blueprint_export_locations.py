from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.quartermaster import export_blueprints, list_blueprints
from app.models import (
    Asset, Base, Blueprint, BlueprintSnapshot, EveAlliance, EveCategory, EveCharacter, EveCorporation,
    EveGroup, EveType, IndustryActivity, IndustryActivityInput, Location, OwnershipEntity, ResearchProject,
    SnapshotRun, User,
)
from app.models.enums import ActivityKind, LocationKind, OwnerKind


class BlueprintExportLocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__, EveAlliance.__table__, EveCorporation.__table__, EveCharacter.__table__, OwnershipEntity.__table__,
                EveCategory.__table__, EveGroup.__table__, EveType.__table__, Location.__table__, Asset.__table__, Blueprint.__table__,
                IndustryActivity.__table__, IndustryActivityInput.__table__, SnapshotRun.__table__, BlueprintSnapshot.__table__, ResearchProject.__table__,
            ],
        )
        self.db = Session(self.engine)
        self.user = User(email="location@example.test", display_name="Location Pilot", role="member")
        self.character = EveCharacter(character_id=90_000_201, name="Location Pilot", owner_user=self.user)
        self.owner = OwnershipEntity(owner_kind=OwnerKind.CHARACTER, character=self.character, display_name=self.character.name)
        category = EveCategory(category_id=9, name="Blueprint")
        group = EveGroup(group_id=9002, name="Ship Blueprint", category=category)
        self.blueprint_type = EveType(type_id=1101, name="Location Test Blueprint", group=group)
        self.container_type = EveType(type_id=1102, name="Station Container")
        self.office_type = EveType(type_id=1103, name="Office")
        self.db.add_all([self.user, self.character, self.owner, self.blueprint_type, self.container_type, self.office_type])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def add_blueprint(self, item_id: int, *, location: Location | None = None, parent: Asset | None = None, flag: str = "Hangar") -> Blueprint:
        asset = Asset(
            ownership_entity_id=self.owner.id, eve_item_id=item_id, type_id=self.blueprint_type.type_id, quantity=1,
            location_id=location.id if location else None, parent_asset_id=parent.id if parent else None,
            location_flag=flag, is_singleton=True, is_blueprint_copy=True,
        )
        self.db.add(asset)
        self.db.flush()
        blueprint = Blueprint(
            asset_id=asset.id, ownership_entity_id=self.owner.id, blueprint_type_id=self.blueprint_type.type_id,
            material_efficiency=10, time_efficiency=20, runs_remaining=5, is_copy=True,
            location_id=location.id if location else None,
        )
        self.db.add(blueprint)
        self.db.flush()
        return blueprint

    def export_rows(self, privacy: dict | None = None) -> tuple[dict, list[dict]]:
        result = export_blueprints(
            {"format": "json", "scope": "all", "privacy": privacy or {}},
            current_user=self.user,
            db=self.db,
        )
        payload = json.loads(result["content"])
        return payload, payload["records"]

    def test_blueprint_directly_in_station(self) -> None:
        station = Location(location_kind=LocationKind.STATION, eve_location_id=60_000_321, name="Direct Station")
        self.db.add(station); self.db.flush(); self.add_blueprint(70_001, location=station); self.db.commit()

        payload, rows = self.export_rows()
        row = rows[0]
        self.assertEqual(row["immediate_location_id"], "60000321")
        self.assertEqual(row["root_location_id"], "60000321")
        self.assertEqual(row["location_resolution_status"], "resolved")
        self.assertEqual(payload["resolved_location_records"], 1)
        self.assertEqual(payload["unresolved_location_records"], 0)

    def test_blueprint_directly_in_upwell_structure(self) -> None:
        structure = Location(location_kind=LocationKind.STRUCTURE, eve_location_id=1_000_000_000_321, name="Upwell Forge")
        self.db.add(structure); self.db.flush(); self.add_blueprint(70_002, location=structure); self.db.commit()

        _, rows = self.export_rows()
        self.assertEqual(rows[0]["root_location_name"], "Upwell Forge")
        self.assertEqual(rows[0]["root_location_id"], "1000000000321")
        self.assertEqual(rows[0]["location_resolution_status"], "resolved")

    def test_blueprint_nested_in_container_resolves_root(self) -> None:
        station = Location(location_kind=LocationKind.STATION, eve_location_id=60_000_322, name="Nested Station")
        self.db.add(station); self.db.flush()
        office = Asset(ownership_entity_id=self.owner.id, eve_item_id=80_001, type_id=self.office_type.type_id, quantity=1, location_id=station.id)
        self.db.add(office); self.db.flush()
        container = Asset(ownership_entity_id=self.owner.id, eve_item_id=80_002, type_id=self.container_type.type_id, quantity=1, parent_asset_id=office.id)
        self.db.add(container); self.db.flush(); self.add_blueprint(70_003, parent=container); self.db.commit()

        _, rows = self.export_rows()
        row = rows[0]
        self.assertEqual(row["immediate_location_id"], "80002")
        self.assertEqual(row["immediate_location_name"], "Station Container")
        self.assertEqual(row["root_location_id"], "60000322")
        self.assertEqual(row["container_id"], "80002")
        self.assertEqual(row["parent_container_id"], "80001")
        self.assertEqual(row["location_resolution_status"], "resolved_via_parent")

    def test_blueprint_in_corporation_division_keeps_flag_and_root(self) -> None:
        station = Location(location_kind=LocationKind.STATION, eve_location_id=60_000_323, name="Corporation Station")
        self.db.add(station); self.db.flush(); self.add_blueprint(70_004, location=station, flag="CorpSAG3"); self.db.commit()

        _, rows = self.export_rows()
        row = rows[0]
        self.assertEqual(row["root_location_name"], "Corporation Station")
        self.assertEqual(row["location_flag"], "CorpSAG3")
        self.assertEqual(row["location_resolution_status"], "resolved")

    def test_blueprint_currently_in_industry_job_uses_facility(self) -> None:
        blueprint = self.add_blueprint(70_005)
        self.db.add(ResearchProject(
            job_id=88_001, character_id=self.character.id, source_type="character", activity_id=4,
            blueprint_id=70_005, blueprint_type_id=self.blueprint_type.type_id, facility_id=60_000_324,
            facility_name="Research Facility", status="active", runs=1, start_date=datetime.now(timezone.utc), last_synced_at=datetime.now(timezone.utc),
        ))
        self.db.commit()

        _, rows = self.export_rows()
        row = rows[0]
        self.assertEqual(row["root_location_id"], "60000324")
        self.assertEqual(row["root_location_name"], "Research Facility")
        self.assertEqual(row["industry_job_id"], "88001")
        self.assertEqual(row["location_resolution_status"], "resolved")

    def test_blueprint_with_inaccessible_parent_is_classified(self) -> None:
        other_user = User(email="private-parent@example.test", display_name="Private", role="member")
        other_character = EveCharacter(character_id=90_000_202, name="Private Parent", owner_user=other_user, public_assets_visible=False)
        other_owner = OwnershipEntity(owner_kind=OwnerKind.CHARACTER, character=other_character, display_name=other_character.name)
        station = Location(location_kind=LocationKind.STATION, eve_location_id=60_000_325, name="Private Station")
        self.db.add_all([other_user, other_character, other_owner, station]); self.db.flush()
        parent = Asset(ownership_entity_id=other_owner.id, eve_item_id=80_003, type_id=self.container_type.type_id, quantity=1, location_id=station.id)
        self.db.add(parent); self.db.flush(); self.add_blueprint(70_006, parent=parent); self.db.commit()

        payload, rows = self.export_rows()
        row = rows[0]
        self.assertEqual(row["location_resolution_status"], "inaccessible")
        self.assertIsNone(row["root_location_id"])
        self.assertNotIn("Private Station", json.dumps(row))
        self.assertEqual(payload["unresolved_location_records"], 1)
        self.assertEqual(payload["unresolved_location_percentage"], 100.0)

    def test_privacy_anonymized_location_is_distinct_from_unresolved(self) -> None:
        station = Location(location_kind=LocationKind.STATION, eve_location_id=60_000_326, name="Secret Station")
        self.db.add(station); self.db.flush(); self.add_blueprint(70_007, location=station); self.db.commit()

        payload, rows = self.export_rows({"include_location_ids": False, "include_location_names": False})
        row = rows[0]
        self.assertEqual(row["location_resolution_status"], "anonymized")
        self.assertIsNone(row["root_location_id"])
        self.assertIsNone(row["root_location_name"])
        self.assertEqual(payload["resolved_location_records"], 1)
        self.assertEqual(payload["unresolved_location_records"], 0)

    def test_blueprint_ui_uses_same_canonical_root_location(self) -> None:
        station = Location(location_kind=LocationKind.STATION, eve_location_id=60_000_327, name="UI Station")
        self.db.add(station); self.db.flush()
        container = Asset(ownership_entity_id=self.owner.id, eve_item_id=80_004, type_id=self.container_type.type_id, quantity=1, location_id=station.id)
        self.db.add(container); self.db.flush(); self.add_blueprint(70_008, parent=container); self.db.commit()

        ui_row = list_blueprints(current_user=self.user, db=self.db)[0]
        _, export_rows = self.export_rows()
        self.assertEqual(ui_row["location_id"], 60_000_327)
        self.assertEqual(ui_row["location_name"], "UI Station")
        self.assertEqual(export_rows[0]["root_location_name"], ui_row["location_name"])


if __name__ == "__main__":
    unittest.main()
