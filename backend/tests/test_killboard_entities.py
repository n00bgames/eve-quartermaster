from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, KillboardEntityName, Killmail, KillmailAttacker
from app.services.killboard_entities import cached_killboard_name_maps, refresh_killboard_entity_names


class FakeNameClient:
    async def post(self, path: str, payload: list[int], params=None):
        assert path == "/universe/names/"
        names = {
            91000001: ("character", "Public Victim"),
            91000002: ("character", "Public Attacker"),
            98000001: ("corporation", "Victim Corporation"),
            98000002: ("corporation", "Attacker Corporation"),
        }
        return [{"id": eve_id, "category": names[eve_id][0], "name": names[eve_id][1]} for eve_id in payload]


class KillboardEntityResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add(Killmail(
                killmail_id=77, killmail_hash="hash", killmail_time=datetime.now(timezone.utc), solar_system_id=30000142,
                victim_character_id=91000001, victim_corporation_id=98000001, damage_taken=100, canonical_esi_payload={},
            ))
            db.flush()
            db.add(KillmailAttacker(
                killmail_id=77, attacker_index=0, character_id=91000002,
                corporation_id=98000002, damage_done=100, final_blow=True,
            ))
            db.commit()

    async def test_missing_public_entities_are_resolved_and_cached_in_one_batch(self) -> None:
        with Session(self.engine) as db:
            result = await refresh_killboard_entity_names(db, client=FakeNameClient())
            self.assertEqual(result, {"requested": 4, "resolved": 4, "unavailable": 0})
            self.assertEqual(db.get(KillboardEntityName, 91000002).name, "Public Attacker")
            maps = cached_killboard_name_maps(db, {
                "character": {91000001, 91000002}, "corporation": {98000001, 98000002},
                "alliance": set(), "faction": set(),
            })
            self.assertEqual(maps["character"][91000001], "Public Victim")
            self.assertEqual(maps["corporation"][98000002], "Attacker Corporation")

            second = await refresh_killboard_entity_names(db, client=FakeNameClient())
            self.assertEqual(second["requested"], 0)


if __name__ == "__main__":
    unittest.main()
