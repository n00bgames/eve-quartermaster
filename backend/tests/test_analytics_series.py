from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.api.analytics import change_breakdown, daily_corporation_series, standing_movement_rows


class AnalyticsSeriesTests(unittest.TestCase):
    def test_daily_series_keeps_latest_observation_per_corporation(self) -> None:
        rows = [
            SimpleNamespace(corporation_id=2, corporation_name="Beta", recorded_at=datetime(2026, 7, 29, 9, tzinfo=timezone.utc), wallet_balance=Decimal("20")),
            SimpleNamespace(corporation_id=1, corporation_name="Alpha", recorded_at=datetime(2026, 7, 29, 8, tzinfo=timezone.utc), wallet_balance=Decimal("10")),
            SimpleNamespace(corporation_id=1, corporation_name="Alpha", recorded_at=datetime(2026, 7, 29, 21, tzinfo=timezone.utc), wallet_balance=Decimal("15")),
            SimpleNamespace(corporation_id=2, corporation_name="Beta", recorded_at=datetime(2026, 7, 30, 10, tzinfo=timezone.utc), wallet_balance=Decimal("25")),
        ]

        self.assertEqual(
            daily_corporation_series(rows, "wallet_balance"),
            [
                {"date": "2026-07-29", "corporation_id": 1, "corporation_name": "Alpha", "value": 15.0},
                {"date": "2026-07-29", "corporation_id": 2, "corporation_name": "Beta", "value": 20.0},
                {"date": "2026-07-30", "corporation_id": 2, "corporation_name": "Beta", "value": 25.0},
            ],
        )

    def test_pre_range_baseline_is_rendered_at_the_range_start(self) -> None:
        rows = [
            SimpleNamespace(corporation_id=1, corporation_name="Alpha", recorded_at=datetime(2026, 7, 20, 8, tzinfo=timezone.utc), wallet_balance=Decimal("10")),
            SimpleNamespace(corporation_id=1, corporation_name="Alpha", recorded_at=datetime(2026, 8, 3, 8, tzinfo=timezone.utc), wallet_balance=Decimal("15")),
        ]
        self.assertEqual(
            daily_corporation_series(rows, "wallet_balance", datetime(2026, 8, 1, tzinfo=timezone.utc)),
            [
                {"date": "2026-08-01", "corporation_id": 1, "corporation_name": "Alpha", "value": 10.0},
                {"date": "2026-08-03", "corporation_id": 1, "corporation_name": "Alpha", "value": 15.0},
            ],
        )

    def test_change_breakdown_separates_onboarding_from_organic_growth(self) -> None:
        rows = [
            SimpleNamespace(id=1, character_id=10, character_name="Existing", recorded_at=datetime(2026, 7, 20, tzinfo=timezone.utc), total_skill_points=100),
            SimpleNamespace(id=2, character_id=10, character_name="Existing", recorded_at=datetime(2026, 8, 3, tzinfo=timezone.utc), total_skill_points=110),
            SimpleNamespace(id=3, character_id=20, character_name="New", recorded_at=datetime(2026, 8, 2, tzinfo=timezone.utc), total_skill_points=200),
            SimpleNamespace(id=4, character_id=20, character_name="New", recorded_at=datetime(2026, 8, 4, tzinfo=timezone.utc), total_skill_points=205),
            SimpleNamespace(id=5, character_id=30, character_name="Unchanged", recorded_at=datetime(2026, 7, 25, tzinfo=timezone.utc), total_skill_points=50),
        ]
        result = change_breakdown(
            rows,
            key="character_id",
            value_attr="total_skill_points",
            name_attr="character_name",
            cutoff=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(result["current"], 365)
        self.assertEqual(result["organic_delta"], 15)
        self.assertEqual(result["coverage_delta"], 200)
        self.assertEqual(result["total_delta"], 215)
        self.assertEqual(result["newly_tracked_count"], 1)
        self.assertEqual(result["newly_tracked"][0]["name"], "New")

    def test_standing_movement_ranks_net_corporation_and_faction_changes(self) -> None:
        cutoff = datetime(2026, 8, 1, tzinfo=timezone.utc)

        def row(row_id: int, series: str, recorded_at: datetime, value: str, source_type: str, source_id: int, source_name: str):
            return SimpleNamespace(
                id=row_id,
                series_key=series,
                recorded_at=recorded_at,
                metric_value=Decimal(value),
                dimensions_json={"source_type": source_type, "source_eve_id": source_id, "source_name": source_name},
            )

        rows = [
            row(1, "corp-a-pilot-1", datetime(2026, 7, 31, tzinfo=timezone.utc), "1.00", "npc_corp", 10, "Caldari Navy"),
            row(2, "corp-a-pilot-1", datetime(2026, 8, 5, tzinfo=timezone.utc), "1.50", "npc_corp", 10, "Caldari Navy"),
            row(3, "corp-a-pilot-2", datetime(2026, 7, 30, tzinfo=timezone.utc), "2.00", "npc_corp", 10, "Caldari Navy"),
            row(4, "corp-a-pilot-2", datetime(2026, 8, 6, tzinfo=timezone.utc), "2.25", "npc_corp", 10, "Caldari Navy"),
            row(5, "corp-b", datetime(2026, 7, 30, tzinfo=timezone.utc), "1.00", "npc_corp", 20, "Republic Fleet"),
            row(6, "corp-b", datetime(2026, 8, 6, tzinfo=timezone.utc), "0.40", "npc_corp", 20, "Republic Fleet"),
            row(7, "faction-a", datetime(2026, 7, 30, tzinfo=timezone.utc), "-1.00", "faction", 30, "Amarr Empire"),
            row(8, "faction-a", datetime(2026, 8, 7, tzinfo=timezone.utc), "-1.30", "faction", 30, "Amarr Empire"),
            # This source was first observed inside the window and is coverage, not movement.
            row(9, "new-faction", datetime(2026, 8, 2, tzinfo=timezone.utc), "4.00", "faction", 40, "Newly Tracked"),
            row(10, "new-faction", datetime(2026, 8, 8, tzinfo=timezone.utc), "4.50", "faction", 40, "Newly Tracked"),
        ]

        result = standing_movement_rows(rows, cutoff)
        self.assertEqual(result["corporations"]["gains"], [{"id": 10, "name": "Caldari Navy", "delta": 0.75}])
        self.assertEqual(result["corporations"]["losses"], [{"id": 20, "name": "Republic Fleet", "delta": 0.6}])
        self.assertEqual(result["factions"]["losses"], [{"id": 30, "name": "Amarr Empire", "delta": 0.3}])
        self.assertEqual(result["factions"]["gains"], [])


if __name__ == "__main__":
    unittest.main()
