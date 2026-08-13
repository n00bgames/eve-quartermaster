from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import (
    Base,
    EsiSyncJob,
    EsiToken,
    EveAlliance,
    EveCharacter,
    EveCorporation,
    OwnershipEntity,
    ResearchProject,
    User,
)
from app.models.enums import OwnerKind, SyncStatus
from app.services.research_projects import (
    scoped_corporation_research_rows,
    upsert_research_projects,
    visible_research_project_filter,
)


class ResearchProjectScopeTests(unittest.TestCase):
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
                EsiToken.__table__,
                EsiSyncJob.__table__,
                ResearchProject.__table__,
            ],
        )
        self.db = Session(self.engine)
        self.user = User(email="research-scope@example.com", display_name="Research Scope", role="admin")
        self.db.add(self.user)
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def add_corporation(self, name: str, *, included: bool) -> EveCorporation:
        sequence = len(self.db.scalars(select(EveCorporation.id)).all()) + 1
        corporation = EveCorporation(corporation_id=9_900_000 + sequence, name=name)
        self.db.add(corporation)
        self.db.flush()
        owner = OwnershipEntity(
            owner_kind=OwnerKind.CORPORATION,
            corporation_id=corporation.id,
            display_name=name,
        )
        self.db.add(owner)
        self.db.flush()
        if included:
            director = EveCharacter(
                character_id=99_000_000 + sequence,
                name=f"{name} Director",
                corporation_id=corporation.id,
                owner_user_id=self.user.id,
            )
            self.db.add(director)
            self.db.flush()
            token = self.add_token(director)
            self.db.add(
                EsiSyncJob(
                    token_id=token.id,
                    ownership_entity_id=owner.id,
                    sync_type="corporation_blueprints",
                    status=SyncStatus.SUCCESS,
                )
            )
        self.db.flush()
        return corporation

    def add_token(self, character: EveCharacter, *, revoked: bool = False) -> EsiToken:
        token = EsiToken(
            user_id=self.user.id,
            character_id=character.id,
            scopes="esi-industry.read_character_jobs.v1",
            encrypted_refresh_token="encrypted",
            revoked_at=datetime.now(timezone.utc) if revoked else None,
        )
        self.db.add(token)
        self.db.flush()
        return token

    def add_project(
        self,
        job_id: int,
        *,
        source_type: str,
        corporation: EveCorporation | None = None,
        character: EveCharacter | None = None,
        installer_character_id: int | None = None,
    ) -> ResearchProject:
        project = ResearchProject(
            job_id=job_id,
            character_id=character.id if character else None,
            corporation_id=corporation.id if corporation else None,
            source_type=source_type,
            installer_character_id=installer_character_id,
            activity_id=4,
            status="active",
            last_synced_at=datetime.now(timezone.utc),
        )
        self.db.add(project)
        self.db.flush()
        return project

    def test_excluded_corporation_queue_keeps_linked_installer_jobs(self) -> None:
        included = self.add_corporation("Included Industry Corporation", included=True)
        excluded = self.add_corporation("Excluded Industry Corporation", included=False)
        linked_pilot = EveCharacter(
            character_id=99_100_001,
            name="Linked Pilot",
            corporation_id=excluded.id,
            owner_user_id=self.user.id,
        )
        stale_pilot = EveCharacter(
            character_id=99_100_002,
            name="Stale Pilot",
            corporation_id=excluded.id,
            owner_user_id=self.user.id,
        )
        self.db.add_all([linked_pilot, stale_pilot])
        self.db.flush()
        self.add_token(linked_pilot)
        self.add_token(stale_pilot, revoked=True)

        character_job = self.add_project(1, source_type="character", character=linked_pilot)
        linked_corporation_job = self.add_project(
            2,
            source_type="corporation",
            corporation=excluded,
            installer_character_id=linked_pilot.character_id,
        )
        included_corporation_job = self.add_project(3, source_type="corporation", corporation=included)
        excluded_corporation_job = self.add_project(4, source_type="corporation", corporation=excluded)
        stale_installer_job = self.add_project(
            5,
            source_type="corporation",
            corporation=excluded,
            installer_character_id=stale_pilot.character_id,
        )
        self.db.commit()

        visible_ids = set(
            self.db.scalars(
                select(ResearchProject.id).where(visible_research_project_filter(self.db))
            ).all()
        )

        self.assertEqual(
            visible_ids,
            {
                character_job.id,
                linked_corporation_job.id,
                included_corporation_job.id,
            },
        )
        self.assertNotIn(excluded_corporation_job.id, visible_ids)
        self.assertNotIn(stale_installer_job.id, visible_ids)

        scoped_rows, linked_only = scoped_corporation_research_rows(
            self.db,
            excluded.id,
            [
                {"job_id": 10, "installer_id": linked_pilot.character_id},
                {"job_id": 11, "installer_id": stale_pilot.character_id},
                {"job_id": 12, "installer_id": 999_999_999},
            ],
        )
        self.assertTrue(linked_only)
        self.assertEqual(scoped_rows, [{"job_id": 10, "installer_id": linked_pilot.character_id}])

        included_rows, linked_only = scoped_corporation_research_rows(
            self.db,
            included.id,
            [{"job_id": 13, "installer_id": 999_999_999}],
        )
        self.assertFalse(linked_only)
        self.assertEqual(included_rows, [{"job_id": 13, "installer_id": 999_999_999}])

    def test_industry_sync_retains_manufacturing_jobs(self) -> None:
        pilot = EveCharacter(
            character_id=99_200_001,
            name="Manufacturing Pilot",
            owner_user_id=self.user.id,
        )
        self.db.add(pilot)
        self.db.flush()

        synced, active = upsert_research_projects(
            self.db,
            pilot.id,
            [
                {
                    "job_id": 9001,
                    "installer_id": pilot.character_id,
                    "activity_id": 1,
                    "status": "active",
                    "blueprint_id": 10_001,
                    "blueprint_type_id": None,
                    "product_type_id": None,
                    "runs": 12,
                },
                {"job_id": 9002, "activity_id": 9, "status": "active"},
            ],
        )

        project = self.db.scalar(select(ResearchProject).where(ResearchProject.job_id == 9001))
        self.assertEqual((synced, active), (1, 1))
        self.assertIsNotNone(project)
        self.assertEqual(project.activity_id, 1)
        self.assertEqual(project.runs, 12)
        self.assertIsNone(self.db.scalar(select(ResearchProject).where(ResearchProject.job_id == 9002)))


if __name__ == "__main__":
    unittest.main()
