from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, EsiSyncJob, EsiToken, EveAlliance, EveCharacter, EveCorporation, OwnershipEntity, User
from app.models.enums import OwnerKind, SyncStatus
from app.services.analytics import analytics_corporation_ids, privileged_analytics_corporation_ids
from app.services.analytics_scope import apply_anonymous_analytics_privacy, resolve_analytics_character_scope


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

    def test_pilot_scope_filters_owned_and_accessible_corporation_characters(self) -> None:
        corporation = EveCorporation(corporation_id=9_900_001, name="Scope Pilots", ticker="SCP")
        outsider_corporation = EveCorporation(corporation_id=9_900_002, name="Other Pilots", ticker="OTH")
        member = User(email="member@example.com", display_name="Member", role="member")
        outsider = User(email="outsider@example.com", display_name="Outsider", role="member")
        self.db.add_all([corporation, outsider_corporation, member, outsider])
        self.db.flush()
        owned = EveCharacter(character_id=91_000_001, name="Owned", corporation_id=corporation.id, owner_user_id=member.id)
        alt = EveCharacter(character_id=91_000_002, name="Alt", corporation_id=corporation.id, owner_user_id=member.id)
        hidden = EveCharacter(character_id=91_000_003, name="Hidden", corporation_id=outsider_corporation.id, owner_user_id=outsider.id)
        self.db.add_all([owned, alt, hidden])
        self.db.commit()

        mine, options = resolve_analytics_character_scope(member, self.db, scope="mine", corporation_id=None)
        corporation_scope, _ = resolve_analytics_character_scope(
            member,
            self.db,
            scope="corporation",
            corporation_id=corporation.id,
        )

        self.assertEqual(mine, {owned.id, alt.id})
        self.assertEqual(corporation_scope, {owned.id, alt.id})
        self.assertEqual(options, {
            "corporations": [{"id": corporation.id, "name": corporation.name, "ticker": corporation.ticker}],
            "alliances": [],
        })

    def test_director_is_limited_to_owned_affiliations_and_alliance_scope(self) -> None:
        alliance = EveAlliance(alliance_id=9_900_100, name="Scope Alliance", ticker="SCA")
        self.db.add(alliance)
        self.db.flush()
        corporation = EveCorporation(corporation_id=9_900_101, name="Director Corp", ticker="DIR", alliance_id=alliance.id)
        allied_corporation = EveCorporation(corporation_id=9_900_102, name="Allied Corp", ticker="ALLY", alliance_id=alliance.id)
        outside_corporation = EveCorporation(corporation_id=9_900_103, name="Outside Corp", ticker="OUT")
        director = User(email="director@example.com", display_name="Director", role="director")
        member = User(email="allied@example.com", display_name="Allied", role="member")
        self.db.add_all([corporation, allied_corporation, outside_corporation, director, member])
        self.db.flush()
        owned = EveCharacter(character_id=92_000_001, name="Owned Director", corporation_id=corporation.id, alliance_id=alliance.id, owner_user_id=director.id)
        ally = EveCharacter(character_id=92_000_002, name="Alliance Member", corporation_id=allied_corporation.id, alliance_id=alliance.id, owner_user_id=member.id)
        outsider = EveCharacter(character_id=92_000_003, name="Outside Member", corporation_id=outside_corporation.id, owner_user_id=member.id)
        self.db.add_all([owned, ally, outsider])
        self.db.commit()

        alliance_scope, options = resolve_analytics_character_scope(
            director, self.db, scope="alliance", corporation_id=None, alliance_id=alliance.id
        )

        self.assertEqual(alliance_scope, {owned.id, ally.id})
        self.assertEqual({row["id"] for row in options["corporations"]}, {corporation.id, allied_corporation.id})
        self.assertEqual(options["alliances"], [{"id": alliance.id, "name": alliance.name, "ticker": alliance.ticker}])

    def test_opted_out_pilots_require_global_minimum_cohort(self) -> None:
        corporation = EveCorporation(corporation_id=9_900_200, name="Privacy Corp", ticker="PRV")
        self.db.add(corporation)
        self.db.flush()
        rows = [
            EveCharacter(character_id=93_000_000 + index, name=f"Private {index}", corporation_id=corporation.id, sync_opt_out=True)
            for index in range(1, 4)
        ]
        self.db.add_all(rows)
        self.db.commit()
        ids = {row.id for row in rows}

        global_ids, anonymous = apply_anonymous_analytics_privacy(self.user, self.db, scope="all", character_ids=ids)
        corporation_ids, corporation_anonymous = apply_anonymous_analytics_privacy(self.user, self.db, scope="corporation", character_ids=ids)

        self.assertEqual(global_ids, ids)
        self.assertEqual(anonymous, ids)
        self.assertEqual(corporation_ids, set())
        self.assertEqual(corporation_anonymous, set())


if __name__ == "__main__":
    unittest.main()
