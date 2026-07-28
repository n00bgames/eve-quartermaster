from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, EsiSyncJob, EsiToken, EveAlliance, EveCharacter, EveCorporation, OwnershipEntity, User
from app.models.enums import OwnerKind, SyncStatus
from app.services.analytics import analytics_corporation_ids, privileged_analytics_corporation_ids


class AnalyticsCorporationScopeTests(unittest.TestCase):
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
            ],
        )
        self.db = Session(self.engine)
        self.user = User(email="scope@example.com", display_name="Scope Tester", role="admin")
        self.db.add(self.user)
        self.db.flush()
        self.sequence = 0

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def add_corporation(
        self,
        name: str,
        *,
        sync_type: str,
        status: SyncStatus = SyncStatus.SUCCESS,
        revoked: bool = False,
        hidden: bool = False,
        excluded: bool = False,
    ) -> EveCorporation:
        self.sequence += 1
        corporation = EveCorporation(
            corporation_id=9_800_000 + self.sequence,
            name=name,
            hide_from_corporation_list=hidden,
            exclude_from_analytics=excluded,
        )
        self.db.add(corporation)
        self.db.flush()
        character = EveCharacter(
            character_id=90_000_000 + self.sequence,
            name=f"{name} Director",
            corporation_id=corporation.id,
            owner_user_id=self.user.id,
        )
        self.db.add(character)
        owner = OwnershipEntity(
            owner_kind=OwnerKind.CORPORATION,
            corporation_id=corporation.id,
            display_name=name,
        )
        self.db.add(owner)
        self.db.flush()
        token = EsiToken(
            user_id=self.user.id,
            character_id=character.id,
            scopes="esi-characters.read_corporation_roles.v1",
            encrypted_refresh_token="encrypted",
            revoked_at=datetime.now(timezone.utc) if revoked else None,
        )
        self.db.add(token)
        self.db.flush()
        self.db.add(EsiSyncJob(token_id=token.id, ownership_entity_id=owner.id, sync_type=sync_type, status=status))
        self.db.commit()
        return corporation

    def test_only_successful_corporation_sync_with_active_token_is_privileged(self) -> None:
        managed = self.add_corporation("Managed Corporation", sync_type="corporation_wallets")
        self.add_corporation("Discovered Corporation", sync_type="character_assets")
        self.add_corporation("Failed Corporation", sync_type="corporation_assets", status=SyncStatus.FAILED)
        self.add_corporation("Former Corporation", sync_type="corporation_blueprints", revoked=True)

        self.assertEqual(privileged_analytics_corporation_ids(self.db), {managed.id})
        self.assertEqual(analytics_corporation_ids(self.db), {managed.id})

    def test_visibility_flags_are_additional_restrictions(self) -> None:
        included = self.add_corporation("Included Corporation", sync_type="corporation_assets")
        hidden = self.add_corporation("Hidden Corporation", sync_type="corporation_blueprints", hidden=True)
        excluded = self.add_corporation("Excluded Corporation", sync_type="corporation_wallets", excluded=True)

        self.assertEqual(
            privileged_analytics_corporation_ids(self.db),
            {included.id, hidden.id, excluded.id},
        )
        self.assertEqual(analytics_corporation_ids(self.db), {included.id})


if __name__ == "__main__":
    unittest.main()
