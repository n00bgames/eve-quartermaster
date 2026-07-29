import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.planetary_analytics import (
    _elapsed_days,
    _windowed_estimate,
    commodity_tier,
)


class PlanetaryAnalyticsTests(unittest.TestCase):
    def test_sde_groups_map_to_pi_tiers(self):
        expected = {
            1033: "P0",
            1042: "P1",
            1034: "P2",
            1040: "P3",
            1041: "P4",
        }
        for group_id, tier in expected.items():
            self.assertEqual(commodity_tier(SimpleNamespace(group_id=group_id)), tier)
        self.assertIsNone(commodity_tier(SimpleNamespace(group_id=999999)))

    def test_factory_elapsed_time_is_capped(self):
        now = datetime.now(timezone.utc)
        self.assertAlmostEqual(_elapsed_days(now - timedelta(hours=12), now), 0.5)
        self.assertEqual(_elapsed_days(now - timedelta(days=90), now), 30)

    def test_windowed_estimate_prorates_interval_at_cutoff(self):
        captured = datetime(2026, 7, 28, tzinfo=timezone.utc)
        row = SimpleNamespace(
            estimated_units_since_previous=100,
            interval_started_at=captured - timedelta(days=2),
            captured_at=captured,
        )
        self.assertAlmostEqual(
            _windowed_estimate(row, captured - timedelta(days=1)),
            50,
        )


if __name__ == "__main__":
    unittest.main()
