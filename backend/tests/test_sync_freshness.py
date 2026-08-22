from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.api.esi import CHARACTER_SYNC_KIND_BY_DATASET, CHARACTER_SYNC_REQUIRED_SCOPES, character_sync_token_work_items
from app.services.sync_freshness import CHARACTER_SYNC_DATASETS, SyncDataset, dataset_freshness


class SyncFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 12, 12, tzinfo=timezone.utc)
        self.dataset = SyncDataset("character_assets", "Assets", ("assets.read",), stale_after_hours=26)

    def job(self, status: str, age_hours: int) -> SimpleNamespace:
        return SimpleNamespace(id=7, status=status, finished_at=self.now - timedelta(hours=age_hours), started_at=None, created_at=self.now, message=None)

    def test_current_success_is_current(self) -> None:
        payload = dataset_freshness(self.dataset, granted_scopes={"assets.read"}, job=self.job("success", 2), now=self.now)
        self.assertEqual(payload["health"], "current")

    def test_old_success_is_stale(self) -> None:
        payload = dataset_freshness(self.dataset, granted_scopes={"assets.read"}, job=self.job("success", 27), now=self.now)
        self.assertEqual(payload["health"], "stale")

    def test_missing_scope_precedes_never_synced(self) -> None:
        payload = dataset_freshness(self.dataset, granted_scopes=set(), job=None, now=self.now)
        self.assertEqual(payload["health"], "missing_scope")
        self.assertEqual(payload["missing_scopes"], ["assets.read"])

    def test_privacy_disable_precedes_scope_and_job_state(self) -> None:
        payload = dataset_freshness(self.dataset, granted_scopes=set(), job=self.job("failed", 1), now=self.now, disabled_reason="Character sync disabled")
        self.assertEqual(payload["health"], "disabled")
        self.assertEqual(payload["disabled_reason"], "Character sync disabled")

    def test_running_job_is_active(self) -> None:
        payload = dataset_freshness(self.dataset, granted_scopes={"assets.read"}, job=self.job("running", 1), now=self.now)
        self.assertEqual(payload["health"], "active")

    def test_sync_all_covers_every_collected_character_dataset(self) -> None:
        registered_keys = {dataset.key for dataset in CHARACTER_SYNC_DATASETS}
        self.assertEqual(set(CHARACTER_SYNC_KIND_BY_DATASET), registered_keys)
        self.assertEqual(
            set(CHARACTER_SYNC_REQUIRED_SCOPES),
            {CHARACTER_SYNC_KIND_BY_DATASET[key] for key in registered_keys},
        )
        self.assertIn("jump_clones", CHARACTER_SYNC_REQUIRED_SCOPES)
        self.assertEqual(
            set(CHARACTER_SYNC_REQUIRED_SCOPES["jump_clones"]),
            {"esi-clones.read_clones.v1", "esi-clones.read_implants.v1"},
        )

    def test_sync_all_uses_newest_eligible_token_per_dataset(self) -> None:
        character = SimpleNamespace(
            id=4,
            sync_opt_out=False,
            wallet_history_opt_out=False,
            corporation_id=None,
        )
        asset_token = SimpleNamespace(id=11, scopes="esi-assets.read_assets.v1")
        clone_token = SimpleNamespace(
            id=10,
            scopes="esi-clones.read_clones.v1 esi-clones.read_implants.v1",
        )
        required = {
            "assets": ["esi-assets.read_assets.v1"],
            "jump_clones": ["esi-clones.read_clones.v1", "esi-clones.read_implants.v1"],
        }
        with patch("app.api.esi.can_force_sync_character_token", return_value=True):
            work_items, corporation_tokens, skipped = character_sync_token_work_items(
                [(asset_token, character), (clone_token, character)],
                SimpleNamespace(id=7),
                SimpleNamespace(),
                required,
                research_requested=False,
            )
        self.assertEqual(
            work_items,
            [
                {"token_id": 11, "sync_kind": "assets"},
                {"token_id": 10, "sync_kind": "jump_clones"},
            ],
        )
        self.assertEqual(corporation_tokens, {})
        self.assertEqual(skipped, 0)


if __name__ == "__main__":
    unittest.main()
