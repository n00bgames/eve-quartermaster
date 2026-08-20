from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

from app.api.esi import CONTACT_SYNC_JOB_MESSAGE_PREFIX, build_contact_plan, contact_sync_job_payload, parse_contact_sync_payload
from app.models.enums import SyncStatus
from app.services.esi_client import EsiClient


class ContactSyncExactMatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = [
            {"contact_id": 10, "contact_type": "character", "standing": 5.0, "is_watched": True},
            {"contact_id": 20, "contact_type": "corporation", "standing": -5.0, "is_watched": False},
        ]
        self.target = [
            {"contact_id": 10, "contact_type": "character", "standing": 0.0, "is_watched": False},
            {"contact_id": 30, "contact_type": "alliance", "standing": 10.0, "is_watched": False},
        ]

    def test_normal_sync_never_deletes_destination_only_contacts(self) -> None:
        plan = build_contact_plan(self.source, self.target, overwrite_existing=False)

        self.assertEqual([row["contact_id"] for row in plan["create"]], [20])
        self.assertEqual(plan["update"], [])
        self.assertEqual(plan["delete"], [])
        self.assertEqual([row["contact_id"] for row in plan["skip"]], [10])

    def test_exact_match_creates_updates_and_deletes_to_match_source(self) -> None:
        plan = build_contact_plan(self.source, self.target, overwrite_existing=False, exact_match=True)

        self.assertEqual([row["contact_id"] for row in plan["create"]], [20])
        self.assertEqual([row["contact_id"] for row in plan["update"]], [10])
        self.assertEqual([row["contact_id"] for row in plan["delete"]], [30])
        self.assertEqual(plan["skip"], [])

    def test_exact_match_payload_forces_existing_contact_updates(self) -> None:
        source, targets, overwrite, exact_match = parse_contact_sync_payload(
            {"source_token_id": 1, "target_token_ids": [1, 2, 3], "overwrite_existing": False, "exact_match": True}
        )

        self.assertEqual(source, 1)
        self.assertEqual(targets, [2, 3])
        self.assertTrue(overwrite)
        self.assertTrue(exact_match)


class EsiDeleteClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_sends_contact_ids_as_query_parameters(self) -> None:
        client = EsiClient(access_token="test-token")
        client.request = AsyncMock(return_value=(None, httpx.Headers()))

        result = await client.delete("/characters/123/contacts/", params={"contact_ids": [10, 20]})

        self.assertIsNone(result)
        client.request.assert_awaited_once_with(
            "DELETE",
            "/characters/123/contacts/",
            params={"contact_ids": [10, 20]},
        )


class ContactSyncJobPayloadTests(unittest.TestCase):
    def test_queued_job_payload_exposes_resumable_progress(self) -> None:
        now = datetime.now(timezone.utc)
        job = SimpleNamespace(
            id=42,
            status=SyncStatus.RUNNING,
            created_at=now,
            finished_at=None,
            message=CONTACT_SYNC_JOB_MESSAGE_PREFIX + '{"source_character_name":"Source Pilot","exact_match":true,"total_count":3,"processed_count":1,"success_count":1,"failed_count":0,"current_character_name":"Target Two","created":8,"updated":2,"deleted":5,"targets":[],"errors":[],"updated_at":"2026-08-18T09:00:00+00:00"}',
        )

        payload = contact_sync_job_payload(job)

        self.assertEqual(payload["job_id"], "42")
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["processed_count"], 1)
        self.assertEqual(payload["current_character_name"], "Target Two")
        self.assertEqual(payload["deleted"], 5)
        self.assertTrue(payload["exact_match"])


if __name__ == "__main__":
    unittest.main()
