from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.financial_analytics import combine_daily_series, corporation_daily_points, corporation_division_daily_points, daily_closing_points, distribution, wallet_statistics


def row(row_id: int, character_id: int, date: str, balance: float):
    return SimpleNamespace(id=row_id, character_id=character_id, recorded_at=datetime.fromisoformat(date).replace(tzinfo=timezone.utc), balance=balance)


def division_row(row_id: int, division: int, date: str, balance: float):
    return SimpleNamespace(id=row_id, division=division, recorded_at=datetime.fromisoformat(date).replace(tzinfo=timezone.utc), balance=balance)


class FinancialAnalyticsTests(unittest.TestCase):
    def test_daily_closing_uses_last_observation(self) -> None:
        points = daily_closing_points([row(1, 1, "2026-08-01T08:00:00", 100), row(2, 1, "2026-08-01T20:00:00", 140), row(3, 1, "2026-08-02T08:00:00", 120)])
        self.assertEqual(points, [{"date": "2026-08-01", "value": 140.0}, {"date": "2026-08-02", "value": 120.0}])

    def test_wallet_statistics_report_growth_and_extremes(self) -> None:
        stats = wallet_statistics([{"date": "2026-08-01", "value": 100}, {"date": "2026-08-02", "value": 160}, {"date": "2026-08-03", "value": 130}])
        self.assertEqual(stats["net_change"], 30)
        self.assertEqual(stats["percentage_growth"], 30)
        self.assertEqual(stats["largest_gain"], 60)
        self.assertEqual(stats["largest_loss"], -30)

    def test_corporation_points_sum_each_characters_daily_close(self) -> None:
        points = corporation_daily_points([row(1, 1, "2026-08-01T08:00:00", 100), row(2, 1, "2026-08-01T20:00:00", 150), row(3, 2, "2026-08-01T12:00:00", 50)])
        self.assertEqual(points, [{"date": "2026-08-01", "value": 200.0}])

    def test_corporation_points_carry_forward_unchanged_character_balances(self) -> None:
        points = corporation_daily_points([row(1, 1, "2026-08-01T08:00:00", 100), row(2, 2, "2026-08-01T12:00:00", 50), row(3, 1, "2026-08-02T08:00:00", 120)])
        self.assertEqual(points, [{"date": "2026-08-01", "value": 150.0}, {"date": "2026-08-02", "value": 170.0}])

    def test_corporation_divisions_sum_and_carry_forward(self) -> None:
        points = corporation_division_daily_points([division_row(1, 1, "2026-08-01T08:00:00", 1_000), division_row(2, 2, "2026-08-01T08:00:00", 500), division_row(3, 2, "2026-08-02T08:00:00", 700)])
        self.assertEqual(points, [{"date": "2026-08-01", "value": 1500.0}, {"date": "2026-08-02", "value": 1700.0}])

    def test_combined_series_carries_each_source_forward(self) -> None:
        points = combine_daily_series(
            [{"date": "2026-08-01", "value": 100}, {"date": "2026-08-03", "value": 120}],
            [{"date": "2026-08-02", "value": 500}],
        )
        self.assertEqual(points, [{"date": "2026-08-01", "value": 100.0}, {"date": "2026-08-02", "value": 600.0}, {"date": "2026-08-03", "value": 620.0}])

    def test_distribution_uses_median_and_average(self) -> None:
        self.assertEqual(distribution([10, 20, 90]), {"median": 20.0, "average": 40.0})


if __name__ == "__main__":
    unittest.main()
