from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.api.battle_reports import public_share, revoke_share
from app.models import Base, BattleReportShare, EveAlliance, EveCharacter, EveConstellation, EveCorporation, EveGroup, EveRegion, EveSystem, EveType, Killmail, KillmailAttacker, User, ZkillEnrichment
from app.services.battle_reports import available_report_pilots, battle_report_history, build_latest_battle_report


class BattleReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            user = User(email="pilot@example.test", display_name="Pilot", role="member")
            other_user = User(email="other@example.test", display_name="Other", role="member")
            friendly = EveCorporation(corporation_id=98000001, name="Friendly Corp", ticker="FRND")
            hostile = EveCorporation(corporation_id=98000002, name="Hostile Corp", ticker="HOST")
            friendly_alliance = EveAlliance(alliance_id=99000001, name="Friendly Alliance", ticker="FRND")
            hostile_alliance = EveAlliance(alliance_id=99000002, name="Hostile Alliance", ticker="HOST")
            db.add_all([user, other_user, friendly, hostile, friendly_alliance, hostile_alliance])
            db.flush()
            db.add_all([
                EveCharacter(character_id=90000001, name="Selected Pilot", corporation_id=friendly.id, owner_user_id=user.id),
                EveCharacter(character_id=90000002, name="Wingmate", corporation_id=friendly.id, owner_user_id=user.id),
                EveCharacter(character_id=90000003, name="Opponent", corporation_id=hostile.id, owner_user_id=other_user.id),
                EveGroup(group_id=25, name="Frigate"), EveGroup(group_id=419, name="Combat Battlecruiser"), EveGroup(group_id=485, name="Dreadnought"),
                EveType(type_id=587, group_id=25, name="Rifter"), EveType(type_id=24698, group_id=419, name="Drake"), EveType(type_id=19720, group_id=485, name="Revelation"),
                EveRegion(region_id=10000002, name="The Forge"),
                EveConstellation(constellation_id=20000020, region_id=10000002, name="Kimotoro"),
                EveSystem(system_id=30000142, constellation_id=20000020, name="Jita", security_status=0.9),
                EveSystem(system_id=30000144, constellation_id=20000020, name="Perimeter", security_status=1.0),
            ])
            db.flush()
            base = datetime.now(timezone.utc).replace(microsecond=0)
            first = Killmail(killmail_id=1, killmail_hash="one", killmail_time=base - timedelta(minutes=10), solar_system_id=30000142,
                             victim_character_id=90000003, victim_corporation_id=98000002, victim_ship_type_id=24698,
                             damage_taken=1000, canonical_esi_payload={})
            second = Killmail(killmail_id=2, killmail_hash="two", killmail_time=base, solar_system_id=30000142,
                              victim_character_id=90000002, victim_corporation_id=98000001, victim_ship_type_id=587,
                              damage_taken=500, canonical_esi_payload={})
            unrelated = Killmail(killmail_id=3, killmail_hash="three", killmail_time=base - timedelta(minutes=5), solar_system_id=30000142,
                                 victim_character_id=90000999, victim_corporation_id=98000999, victim_ship_type_id=587,
                                 damage_taken=10, canonical_esi_payload={})
            remote = Killmail(killmail_id=4, killmail_hash="four", killmail_time=base - timedelta(hours=2), solar_system_id=30000144,
                              victim_character_id=90000001, victim_corporation_id=98000001, victim_alliance_id=99000001, victim_ship_type_id=19720,
                              damage_taken=1000, canonical_esi_payload={})
            db.add_all([first, second, unrelated, remote])
            db.flush()
            db.add_all([
                KillmailAttacker(killmail_id=1, attacker_index=0, character_id=90000001, corporation_id=98000001, ship_type_id=587, damage_done=700, final_blow=True),
                KillmailAttacker(killmail_id=1, attacker_index=1, character_id=90000002, corporation_id=98000001, ship_type_id=587, damage_done=300, final_blow=False),
                KillmailAttacker(killmail_id=2, attacker_index=0, character_id=90000003, corporation_id=98000002, ship_type_id=24698, damage_done=500, final_blow=True),
                KillmailAttacker(killmail_id=3, attacker_index=0, character_id=90000888, corporation_id=98000888, ship_type_id=587, damage_done=10, final_blow=True),
                KillmailAttacker(killmail_id=4, attacker_index=0, character_id=90000003, corporation_id=98000002, alliance_id=99000002, ship_type_id=24698, damage_done=900, final_blow=True),
                KillmailAttacker(killmail_id=4, attacker_index=1, character_id=90000002, corporation_id=98000001, ship_type_id=587, damage_done=100, final_blow=False),
                ZkillEnrichment(killmail_id=1, estimated_total_value=200_000_000, zkill_url="https://zkillboard.com/kill/1/", raw_enrichment_payload={}),
                ZkillEnrichment(killmail_id=2, estimated_total_value=50_000_000, zkill_url="https://zkillboard.com/kill/2/", raw_enrichment_payload={}),
                ZkillEnrichment(killmail_id=3, estimated_total_value=1_000_000, zkill_url="https://zkillboard.com/kill/3/", raw_enrichment_payload={}),
            ])
            db.commit()

    def test_latest_report_groups_connected_activity_and_assigns_sides(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            data = build_latest_battle_report(db, user, character_id=90000001, gap_minutes=15)
            report = data["report"]
            self.assertIsNotNone(report)
            self.assertEqual(report["seed_killmail_id"], 1)
            self.assertEqual(report["killmail_count"], 2)
            self.assertEqual(report["estimated_total_value"], 250_000_000)
            self.assertNotIn(3, {row["killmail_id"] for row in report["timeline"]})
            selected = next(team for team in report["teams"] if team["side"] == 0)
            opposing = next(team for team in report["teams"] if team["side"] == 1)
            self.assertEqual(selected["ships_lost"], 1)
            self.assertEqual(opposing["ships_lost"], 1)
            self.assertEqual(selected["efficiency"], 80)
            self.assertEqual(selected["organizations"][0]["organization_type"], "corporation")
            self.assertEqual(selected["organizations"][0]["organization_id"], 98000001)
            drake = next(row for row in report["composition"] if row["ship_type_id"] == 24698)
            self.assertEqual(drake["ship_group_name"], "Combat Battlecruiser")
            selected_pilot = next(row for row in report["participants"] if row["character_id"] == 90000001)
            self.assertEqual(selected_pilot["ships"][0]["type_id"], 587)
            self.assertEqual(report["timeline"][0]["victim_corporation_id"], 98000002)

    def test_gap_prevents_old_activity_from_joining_latest_report(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            report = build_latest_battle_report(db, user, character_id=90000001, gap_minutes=60)["report"]
            self.assertEqual(report["killmail_count"], 2)
            self.assertEqual({row["system_name"] for row in report["systems"]}, {"Jita"})

    def test_history_exposes_stable_previous_and_next_engagement_seeds(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            history = battle_report_history(db, user, character_id=90000001, gap_minutes=15)
            self.assertEqual([row["seed_killmail_id"] for row in history["reports"]], [1, 4])
            self.assertEqual(history["total_reports"], 2)
            previous = build_latest_battle_report(db, user, character_id=90000001, gap_minutes=15, seed_killmail_id=4)["report"]
            self.assertEqual(previous["seed_killmail_id"], 4)
            self.assertEqual({row["system_name"] for row in previous["systems"]}, {"Perimeter"})
            previous_pilots = {row["character_id"]: row["side"] for row in previous["participants"]}
            self.assertEqual(previous_pilots[90000001], 0)
            self.assertEqual(previous_pilots[90000002], 0)
            self.assertEqual(previous_pilots[90000003], 1)
            with self.assertRaises(LookupError):
                build_latest_battle_report(db, user, character_id=90000001, seed_killmail_id=2)

    def test_manual_pilot_classification_rebuilds_report_totals(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            report = build_latest_battle_report(
                db,
                user,
                character_id=90000001,
                gap_minutes=15,
                side_overrides={90000001: 2, 90000003: 2},
            )["report"]
            participants = {row["character_id"]: row for row in report["participants"]}
            self.assertEqual(participants[90000001]["side"], 0)
            self.assertEqual(participants[90000003]["side"], 2)
            self.assertEqual(next(row for row in report["timeline"] if row["killmail_id"] == 1)["victim_side"], 2)
            self.assertEqual(next(row for row in report["composition"] if row["ship_type_id"] == 24698)["side"], 2)
            self.assertEqual(report["side_overrides"], {90000003: 2})

            organization_report = build_latest_battle_report(
                db,
                user,
                character_id=90000001,
                gap_minutes=15,
                organization_overrides={("corporation", 98000002): 2},
            )["report"]
            organization_participants = {row["character_id"]: row for row in organization_report["participants"]}
            self.assertEqual(organization_participants[90000003]["side"], 2)
            self.assertEqual(organization_report["organization_overrides"], [
                {"organization_type": "corporation", "organization_id": 98000002, "side": 2},
            ])

    @patch("app.services.battle_report_engine.get_settings")
    def test_complete_battle_report_matches_rust_in_shadow_mode(self, settings) -> None:
        settings.return_value = SimpleNamespace(
            eqm_battle_report_engine="shadow",
            eqm_core_binary="/usr/local/bin/eqm-core",
            eqm_core_timeout_seconds=5.0,
        )
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            data = build_latest_battle_report(db, user, character_id=90000001, gap_minutes=15)
            self.assertEqual(data["engine_used"], "python-shadow")
            self.assertTrue(data["engine_shadow_match"])

    def test_member_only_sees_owned_pilots(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            self.assertEqual({row["character_id"] for row in available_report_pilots(db, user)}, {90000001, 90000002})
            with self.assertRaises(PermissionError):
                build_latest_battle_report(db, user, character_id=90000003)

    def test_public_snapshot_is_immutable_and_revocable(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            snapshot = build_latest_battle_report(db, user, character_id=90000001)
            row = BattleReportShare(
                share_token="unguessable-test-token",
                created_by_user_id=user.id,
                selected_character_id=90000001,
                selected_character_name="Selected Pilot",
                report_payload=snapshot,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            shared = public_share(row.share_token, db=db)
            self.assertEqual(shared["report"]["seed_killmail_id"], 1)
            self.assertEqual(shared["share"]["view_count"], 1)

            source_row = db.get(Killmail, 1)
            source_row.damage_taken = 999_999
            db.commit()
            unchanged = public_share(row.share_token, db=db)
            self.assertEqual(unchanged["report"]["seed_killmail_id"], 1)

            revoke_share(row.id, current_user=user, db=db)
            with self.assertRaises(HTTPException) as error:
                public_share(row.share_token, db=db)
            self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
