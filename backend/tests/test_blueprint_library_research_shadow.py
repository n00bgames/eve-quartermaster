from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.quartermaster import export_blueprints, list_blueprints, missing_blueprints
from app.models import (
    Asset,
    Base,
    Blueprint,
    BlueprintSnapshot,
    EveAlliance,
    EveCategory,
    EveCharacter,
    EveCorporation,
    EveGroup,
    EveType,
    IndustryActivity,
    IndustryActivityInput,
    Location,
    OwnershipEntity,
    ResearchProject,
    SnapshotRun,
    User,
)
from app.models.enums import ActivityKind, OwnerKind


class BlueprintLibraryResearchShadowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                EveAlliance.__table__,
                EveCorporation.__table__,
                EveCharacter.__table__,
                OwnershipEntity.__table__,
                EveCategory.__table__,
                EveGroup.__table__,
                EveType.__table__,
                Location.__table__,
                Asset.__table__,
                Blueprint.__table__,
                IndustryActivity.__table__,
                IndustryActivityInput.__table__,
                SnapshotRun.__table__,
                BlueprintSnapshot.__table__,
                ResearchProject.__table__,
            ],
        )
        self.db = Session(self.engine)
        self.user = User(email="pilot@example.test", display_name="Pilot", role="member")
        self.character = EveCharacter(
            character_id=90_000_101,
            name="Research Pilot",
            owner_user=self.user,
        )
        self.owner = OwnershipEntity(
            owner_kind=OwnerKind.CHARACTER,
            character=self.character,
            display_name=self.character.name,
        )
        blueprint_category = EveCategory(category_id=9, name="Blueprint")
        blueprint_group = EveGroup(group_id=9001, name="Fighter Blueprint", category=blueprint_category)
        product_category = EveCategory(category_id=87, name="Fighter")
        product_group = EveGroup(group_id=8701, name="Light Fighter", category=product_category)
        self.blueprint_type = EveType(type_id=1001, name="Test Fighter I Blueprint", group=blueprint_group)
        self.product_type = EveType(type_id=2001, name="Test Fighter I", group=product_group)
        self.db.add_all([
            self.user,
            self.character,
            self.owner,
            self.blueprint_type,
            self.product_type,
        ])
        self.db.flush()
        self.db.add(
            IndustryActivity(
                blueprint_type_id=self.blueprint_type.type_id,
                activity_kind=ActivityKind.MANUFACTURING,
                product_type_id=self.product_type.type_id,
                product_quantity=1,
            )
        )
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def add_active_project(self, item_id: int = 55_001) -> ResearchProject:
        project = ResearchProject(
            job_id=77_001,
            character_id=self.character.id,
            source_type="character",
            activity_id=4,
            blueprint_id=item_id,
            blueprint_type_id=self.blueprint_type.type_id,
            facility_id=60_000_001,
            facility_name="Research Station",
            status="active",
            runs=1,
            last_synced_at=datetime.now(timezone.utc),
        )
        self.db.add(project)
        self.db.flush()
        return project

    def add_prior_snapshot(self, item_id: int = 55_001) -> None:
        run = SnapshotRun(source="test", status="success")
        self.db.add(run)
        self.db.flush()
        self.db.add(
            BlueprintSnapshot(
                snapshot_run_id=run.id,
                ownership_entity_id=self.owner.id,
                owner_name=self.owner.display_name,
                blueprint_item_id=item_id,
                blueprint_type_id=self.blueprint_type.type_id,
                blueprint_type_name=self.blueprint_type.name,
                material_efficiency=2,
                time_efficiency=4,
                is_copy=False,
            )
        )

    def test_active_research_job_restores_missing_blueprint_to_library(self) -> None:
        project = self.add_active_project()
        self.add_prior_snapshot()
        self.db.commit()

        rows = list_blueprints(current_user=self.user, db=self.db)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], -project.id)
        self.assertEqual(row["blueprint_type_name"], self.blueprint_type.name)
        self.assertEqual(row["product_type_name"], self.product_type.name)
        self.assertEqual(row["owner_name"], self.character.name)
        self.assertEqual(row["inventory_state"], "in_research")
        self.assertTrue(row["research_shadow"])
        self.assertEqual(row["material_efficiency"], 2)
        self.assertEqual(row["time_efficiency"], 4)
        self.assertEqual(row["active_use"]["activity"], "Material Efficiency")
        self.assertEqual(row["location_name"], "Research Station")

        missing = missing_blueprints(q="Test Fighter", limit_per_category=80, current_user=self.user, db=self.db)
        self.assertEqual(missing["total_missing"], 0)
        self.assertEqual(missing["owned_bpos"], 1)

    def test_current_inventory_blueprint_is_not_duplicated_by_research_job(self) -> None:
        asset = Asset(
            ownership_entity_id=self.owner.id,
            eve_item_id=55_001,
            type_id=self.blueprint_type.type_id,
            quantity=1,
        )
        self.db.add(asset)
        self.db.flush()
        self.db.add(
            Blueprint(
                asset_id=asset.id,
                ownership_entity_id=self.owner.id,
                blueprint_type_id=self.blueprint_type.type_id,
                material_efficiency=6,
                time_efficiency=10,
            )
        )
        self.add_active_project()
        self.db.commit()

        rows = list_blueprints(current_user=self.user, db=self.db)

        self.assertEqual(len(rows), 1)
        self.assertNotIn("research_shadow", rows[0])
        self.assertEqual(rows[0]["active_use"]["activity"], "Material Efficiency")

    def test_export_includes_research_blueprint_ids_metadata_and_exact_json_ids(self) -> None:
        project = self.add_active_project(item_id=9_007_199_254_740_993)
        self.add_prior_snapshot(item_id=9_007_199_254_740_993)
        self.db.commit()

        result = export_blueprints(
            payload={"format": "json", "scope": "all", "privacy": {"include_owner_ids": True, "include_location_ids": True}},
            current_user=self.user,
            db=self.db,
        )

        payload = __import__("json").loads(result["content"])
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(payload["schema_version"], "eqm.inventory.v2")
        self.assertEqual(payload["records"][0]["item_id"], "9007199254740993")
        self.assertEqual(payload["records"][0]["blueprint_type_id"], str(self.blueprint_type.type_id))
        self.assertEqual(payload["records"][0]["industry_job_id"], str(project.job_id))
        self.assertIn("generated_at_utc", payload)

    def test_export_current_filter_and_privacy_controls(self) -> None:
        self.add_active_project()
        self.add_prior_snapshot()
        self.db.commit()

        empty = export_blueprints(
            payload={"format": "csv", "scope": "filtered", "filters": {"kind": "bpc"}},
            current_user=self.user,
            db=self.db,
        )
        self.assertEqual(empty["row_count"], 0)

        private = export_blueprints(
            payload={
                "format": "json",
                "scope": "all",
                "privacy": {"include_owner_ids": False, "include_location_ids": False, "include_location_names": False, "exclude_owner_names": True},
                "location_aliases": {"Research Station": "Home Industry"},
            },
            current_user=self.user,
            db=self.db,
        )
        row = __import__("json").loads(private["content"])["records"][0]
        self.assertIsNone(row["owner_id"])
        self.assertIsNone(row["owner_name"])
        self.assertIsNone(row["location_id"])
        self.assertIsNone(row["location_name"])
        self.assertEqual(row["location_alias"], "Home Industry")


if __name__ == "__main__":
    unittest.main()
