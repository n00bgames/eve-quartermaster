from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.models import KillboardEntityName, KillboardSyncRun, Killmail, KillmailAttacker, KillmailDiscovery, KillmailItem, ZkillEnrichment
from app.services.killboard_settings import killboard_settings, update_killboard_settings
from app.services.metric_registry import metric_definition
from app.services.permissions import SECTION_DEFINITIONS


class FakeSettingsDb:
    def __init__(self) -> None:
        self.rows = {}

    def get(self, _model, key):
        return self.rows.get(key)

    def add(self, row) -> None:
        self.rows[row.key] = row


class KillboardFoundationTests(unittest.TestCase):
    def test_models_use_expected_tables(self) -> None:
        self.assertEqual(Killmail.__tablename__, "killmails")
        self.assertEqual(KillmailAttacker.__tablename__, "killmail_attackers")
        self.assertEqual(KillmailItem.__tablename__, "killmail_items")
        self.assertEqual(ZkillEnrichment.__tablename__, "zkill_enrichment")
        self.assertEqual(KillmailDiscovery.__tablename__, "killmail_discoveries")
        self.assertEqual(KillboardSyncRun.__tablename__, "killboard_sync_runs")
        self.assertEqual(KillboardEntityName.__tablename__, "killboard_entity_names")

    def test_module_is_registered_with_default_member_visibility(self) -> None:
        self.assertIn("killboard", SECTION_DEFINITIONS)
        self.assertIn("member", SECTION_DEFINITIONS["killboard"]["default_roles"])

    def test_defaults_are_safe_and_configurable(self) -> None:
        db = FakeSettingsDb()
        defaults = killboard_settings(db)
        self.assertTrue(defaults["enabled"])
        updated = update_killboard_settings(db, {"enabled": False, "lookback_days": 30, "sync_period_hours": 12, "request_delay_seconds": 1.5, "max_pages": 4})
        self.assertFalse(updated["enabled"])
        self.assertEqual(killboard_settings(db)["lookback_days"], 30)

    def test_invalid_settings_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "lookback_days"):
            update_killboard_settings(FakeSettingsDb(), {"lookback_days": 0})

    def test_combat_metrics_have_explicit_registry_contracts(self) -> None:
        for key in ("killboard.kills", "killboard.losses", "killboard.isk_destroyed", "killboard.isk_lost", "killboard.solo_kills", "killboard.final_blows"):
            definition = metric_definition(key)
            self.assertEqual(definition["category"], "Combat")
            self.assertEqual(definition["timeAggregation"], "latest")
            self.assertEqual(definition["valueKind"], "gauge")
            self.assertIn("period_delta", definition["supportedTransforms"])


if __name__ == "__main__":
    unittest.main()
