from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.api.analytics import daily_corporation_series


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


if __name__ == "__main__":
    unittest.main()