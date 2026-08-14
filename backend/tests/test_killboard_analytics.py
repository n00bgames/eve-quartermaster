from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (Base, EveCharacter, EveConstellation, EveCorporation, EveRegion, EveSystem, EveType,
                        KillboardEntityName, Killmail, KillmailAttacker, SnapshotMetric, User, ZkillEnrichment)
from app.services.killboard_analytics import available_scopes, build_killboard_analytics
from app.services.killboard_snapshots import snapshot_killboard_targets
from app.services.killboard_sync import sync_targets_for_user


class KillboardAnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            user = User(email="pilot@example.test", display_name="Pilot", role="member")
            corp = EveCorporation(corporation_id=98000001, name="Example Corporation", ticker="EX")
            enemy_corp = EveCorporation(corporation_id=98000002, name="Dangerous Acquaintances", ticker="DGR")
            db.add_all([user, corp, enemy_corp])
            db.flush()
            db.add_all([
                EveCharacter(character_id=90000001, name="Example Pilot", corporation_id=corp.id, owner_user_id=user.id),
                EveCharacter(character_id=90000002, name="Recurring Opponent", corporation_id=enemy_corp.id),
                EveType(type_id=587, name="Rifter"), EveType(type_id=24698, name="Drake"),
                EveRegion(region_id=10000002, name="The Forge"),
                EveConstellation(constellation_id=20000020, region_id=10000002, name="Kimotoro"),
                EveSystem(system_id=30000142, constellation_id=20000020, name="Jita", security_status=0.9),
            ])
            db.flush()
            now = datetime.now(timezone.utc)
            kill = Killmail(killmail_id=1, killmail_hash="one", killmail_time=now - timedelta(days=1), solar_system_id=30000142,
                            victim_character_id=90000002, victim_corporation_id=98000002, victim_ship_type_id=24698,
                            damage_taken=1000, canonical_esi_payload={})
            loss = Killmail(killmail_id=2, killmail_hash="two", killmail_time=now - timedelta(days=2), solar_system_id=30000142,
                            victim_character_id=90000001, victim_corporation_id=98000001, victim_ship_type_id=587,
                            damage_taken=500, canonical_esi_payload={})
            db.add_all([kill, loss])
            db.flush()
            db.add_all([
                KillmailAttacker(killmail_id=1, attacker_index=0, character_id=90000001, corporation_id=98000001,
                                 ship_type_id=587, damage_done=750, final_blow=True),
                KillmailAttacker(killmail_id=1, attacker_index=1, character_id=None, corporation_id=1000125,
                                 damage_done=250, final_blow=False),
                KillmailAttacker(killmail_id=2, attacker_index=0, character_id=90000002, corporation_id=98000002,
                                 ship_type_id=24698, damage_done=500, final_blow=True),
                ZkillEnrichment(killmail_id=1, estimated_total_value=200_000_000, points=20, solo=False, npc=False, awox=False,
                                zkill_url="https://zkillboard.com/kill/1/", raw_enrichment_payload={}),
                ZkillEnrichment(killmail_id=2, estimated_total_value=50_000_000, points=10, solo=True, npc=False, awox=False,
                                zkill_url="https://zkillboard.com/kill/2/", raw_enrichment_payload={}),
            ])
            db.commit()

    def test_account_summary_and_rankings(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            data = build_killboard_analytics(db, user, days=30)
            self.assertEqual(data["summary"]["kills"], 1)
            self.assertEqual(data["summary"]["losses"], 1)
            self.assertEqual(data["summary"]["final_blows"], 1)
            self.assertEqual(data["summary"]["damage_contribution_percent"], 75)
            self.assertEqual(data["summary"]["efficiency"], 80)
            self.assertEqual(data["hulls"]["most_used"][0]["name"], "Rifter")
            self.assertEqual(data["hulls"]["most_killed"][0]["name"], "Drake")
            self.assertEqual(data["hulls"]["most_lost"][0]["name"], "Rifter")
            self.assertEqual(data["geography"]["regions"][0]["name"], "The Forge")
            self.assertEqual(data["opponents"][0]["name"], "Recurring Opponent")
            self.assertEqual(data["recent"][0]["zkill_url"], "https://zkillboard.com/kill/1/")

    def test_account_scope_cannot_be_impersonated(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            with self.assertRaises(PermissionError):
                build_killboard_analytics(db, user, scope_type="account", scope_id=user.id + 1)

    def test_external_opponent_uses_public_entity_name_cache(self) -> None:
        with Session(self.engine) as db:
            db.add(KillboardEntityName(eve_id=90000003, category="character", name="Translated Opponent", resolution_status="resolved"))
            db.add(KillmailAttacker(killmail_id=2, attacker_index=1, character_id=90000003, damage_done=1, final_blow=False))
            db.commit()
            user = db.query(User).filter_by(email="pilot@example.test").one()
            data = build_killboard_analytics(db, user, days=30)
            self.assertIn("Translated Opponent", {row["name"] for row in data["opponents"]})

    def test_scope_and_sync_targets_translate_internal_corporation_keys(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            scopes = available_scopes(db, user)
            self.assertIn(("corporation", 98000001), {(row["scope_type"], row["scope_id"]) for row in scopes})
            targets = sync_targets_for_user(db, user, scope="corporations")
            self.assertIn(("corporation", 98000001), {(row["owner_type"], row["owner_id"]) for row in targets})

    def test_completed_sync_totals_use_existing_snapshot_registry(self) -> None:
        with Session(self.engine) as db:
            user = db.query(User).filter_by(email="pilot@example.test").one()
            run = snapshot_killboard_targets(db, user, [{"owner_type": "character", "owner_id": 90000001, "owner_name": "Example Pilot"}])
            db.commit()
            metrics = {row.metric_key: float(row.metric_value) for row in db.query(SnapshotMetric).filter_by(snapshot_run_id=run.id).all()}
            self.assertEqual(run.source, "killboard_sync")
            self.assertEqual(metrics["killboard.kills"], 1)
            self.assertEqual(metrics["killboard.losses"], 1)
            self.assertEqual(metrics["killboard.isk_destroyed"], 200_000_000)


if __name__ == "__main__":
    unittest.main()
