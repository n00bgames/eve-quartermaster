from __future__ import annotations

import unittest
from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import Base, Killmail, KillmailAttacker, KillmailDiscovery, KillmailItem, ZkillEnrichment
from app.services.killboard_sync import KILLBOARD_USER_AGENT, ZkillDiscoveryClient, discovery_identity, flatten_items, upsert_killmail, validate_canonical_payload


def canonical_payload(*, damage: int = 700) -> dict:
    return {
        "killmail_id": 12345,
        "killmail_time": "2026-08-14T12:00:00Z",
        "solar_system_id": 30000142,
        "victim": {
            "character_id": 90000001,
            "corporation_id": 98000001,
            "ship_type_id": 24698,
            "damage_taken": damage,
            "items": [
                {"item_type_id": 34, "flag": 5, "quantity_destroyed": 4, "singleton": 0},
                {"item_type_id": 17366, "flag": 5, "quantity_dropped": 1, "singleton": 1, "items": [
                    {"item_type_id": 35, "flag": 89, "quantity_dropped": 8, "singleton": 0}
                ]},
            ],
        },
        "attackers": [
            {"character_id": 90000002, "corporation_id": 98000002, "ship_type_id": 587, "weapon_type_id": 2048, "damage_done": damage, "final_blow": True, "security_status": -1.25}
        ],
    }


class KillboardSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_discovery_identity_uses_zkill_hash(self) -> None:
        self.assertEqual(discovery_identity({"killmail_id": 42, "zkb": {"hash": "abc"}}), (42, "abc"))

    def test_nested_items_are_flattened_with_parent_index(self) -> None:
        rows = flatten_items(canonical_payload()["victim"]["items"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[2]["parent_item_index"], 1)

    def test_canonical_upsert_normalizes_and_deduplicates(self) -> None:
        with Session(self.engine) as db:
            row, created = upsert_killmail(
                db, killmail_id=12345, killmail_hash="hash-one", esi_payload=canonical_payload(),
                zkill_payload={"zkb": {"hash": "hash-one", "totalValue": 125000000, "points": 17, "solo": True}},
                owner_type="character", owner_id=90000002, feed="kills",
            )
            db.commit()
            self.assertTrue(created)
            self.assertEqual(row.damage_taken, 700)
            self.assertEqual(db.scalar(select(func.count()).select_from(KillmailAttacker)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(KillmailItem)), 3)
            self.assertEqual(db.scalar(select(func.count()).select_from(KillmailDiscovery)), 1)
            self.assertEqual(float(db.get(ZkillEnrichment, 12345).estimated_total_value), 125000000)

            _, created_again = upsert_killmail(
                db, killmail_id=12345, killmail_hash="hash-one", esi_payload=canonical_payload(damage=800),
                zkill_payload={"zkb": {"hash": "hash-one", "totalValue": 130000000}},
                owner_type="character", owner_id=90000002, feed="kills",
            )
            db.commit()
            self.assertFalse(created_again)
            self.assertEqual(db.get(Killmail, 12345).damage_taken, 800)
            self.assertEqual(db.scalar(select(func.count()).select_from(KillmailAttacker)), 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(KillmailItem)), 3)
            self.assertEqual(db.scalar(select(func.count()).select_from(KillmailDiscovery)), 1)

    def test_invalid_payload_does_not_mutate_existing_record(self) -> None:
        with Session(self.engine) as db:
            upsert_killmail(
                db, killmail_id=12345, killmail_hash="good", esi_payload=canonical_payload(),
                zkill_payload={"zkb": {"hash": "good"}}, owner_type="character", owner_id=90000002, feed="kills",
            )
            db.commit()
            with self.assertRaisesRegex(ValueError, "attacker"):
                upsert_killmail(
                    db, killmail_id=12345, killmail_hash="bad", esi_payload={"killmail_time": "2026-08-14T12:00:00Z", "solar_system_id": 30000142, "victim": {}},
                    zkill_payload={}, owner_type="character", owner_id=90000002, feed="kills",
                )
            self.assertEqual(db.get(Killmail, 12345).killmail_hash, "good")
            self.assertEqual(db.scalar(select(func.count()).select_from(KillmailAttacker)), 1)

    def test_validation_accepts_missing_character_for_npc_victim(self) -> None:
        payload = canonical_payload()
        payload["victim"].pop("character_id")
        _, timestamp, system_id = validate_canonical_payload(payload)
        self.assertEqual(timestamp, datetime(2026, 8, 14, 12, tzinfo=timezone.utc))
        self.assertEqual(system_id, 30000142)


class ZkillClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_request_is_identified_compressed_and_trailing_slashed(self) -> None:
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["user_agent"] = request.headers.get("user-agent", "")
            seen["encoding"] = request.headers.get("accept-encoding", "")
            return httpx.Response(200, json=[])

        async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = ZkillDiscoveryClient(request_delay_seconds=0.01, client=async_client)
        try:
            self.assertEqual(await client.fetch_page("character", 90000001, "kills", 1), [])
        finally:
            await async_client.aclose()
        self.assertTrue(seen["url"].endswith("/kills/characterID/90000001/page/1/"))
        self.assertEqual(seen["user_agent"], KILLBOARD_USER_AGENT)
        self.assertIn("gzip", seen["encoding"])
        self.assertGreaterEqual(client.request_delay_seconds, 0.2)


if __name__ == "__main__":
    unittest.main()
