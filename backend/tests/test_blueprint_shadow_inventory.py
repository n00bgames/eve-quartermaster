from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    Base,
    Blueprint,
    BlueprintSnapshot,
    EsiSyncJob,
    EsiToken,
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EveType,
    OwnershipEntity,
    ResearchProject,
    SnapshotRun,
    User,
)
from app.models.enums import OwnerKind
from app.services.analytics import scoped_blueprint_records


class BlueprintShadowInventoryTests(unittest.TestCase):
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
                EveType.__table__,
                Asset.__table__,
                Blueprint.__table__,
                SnapshotRun.__table__,
                BlueprintSnapshot.__table__,
                ResearchProject.__table__,
                EsiToken.__table__,
                EsiSyncJob.__table__,
            ],
        )
        self.db = Session(self.engine)
        self.character = EveCharacter(character_id=90_000_001, name="Research Pilot")
        self.owner = OwnershipEntity(
            owner_kind=OwnerKind.CHARACTER,
            character=self.character,
            display_name=self.character.name,
        )
        self.blueprint_type = EveType(type_id=1001, name="Test Blueprint")
        self.db.add_all([self.character, self.owner, self.blueprint_type])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def add_project(self, item_id: int, job_id: int) -> ResearchProject:
        project = ResearchProject(
            job_id=job_id,
            character_id=self.character.id,
            source_type="character",
            activity_id=4,
            blueprint_id=item_id,
            blueprint_type_id=self.blueprint_type.type_id,
            status="active",
            runs=1,
            last_synced_at=datetime.now(timezone.utc),
        )
        self.db.add(project)
        self.db.flush()
        return project

    def test_active_job_overlays_inventory_blueprint_without_double_counting(self) -> None:
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
                material_efficiency=8,
                time_efficiency=16,
            )
        )
        project = self.add_project(55_001, 77_001)
        self.db.commit()

        records = scoped_blueprint_records(self.db)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["inventory_state"], "in_production")
        self.assertEqual(records[0]["research_job_id"], project.job_id)
        self.assertEqual(records[0]["material_efficiency"], 8)

    def test_job_restores_blueprint_missing_from_inventory(self) -> None:
        project = self.add_project(55_002, 77_002)
        self.db.commit()

        records = scoped_blueprint_records(self.db)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["item_id"], project.blueprint_id)
        self.assertEqual(records[0]["inventory_state"], "in_production")
        self.assertFalse(records[0]["is_copy"])

    def test_invention_jobs_are_not_treated_as_permanent_blueprints(self) -> None:
        project = self.add_project(55_003, 77_003)
        project.activity_id = 8
        self.db.commit()

        self.assertEqual(scoped_blueprint_records(self.db), [])


if __name__ == "__main__":
    unittest.main()
