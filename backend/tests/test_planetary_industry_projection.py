from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.services.planetary_industry import (
    extractor_cycle_output,
    extractor_program_projection,
)


class PlanetaryIndustryProjectionTests(unittest.TestCase):
    def test_ccp_extractor_formula_regression(self) -> None:
        self.assertEqual(
            extractor_cycle_output(
                cycle_index=0,
                cycle_time=3600,
                quantity_per_cycle=1000,
                decay_factor=0.012,
                noise_factor=0.8,
            ),
            6337,
        )

    def test_program_and_remaining_output_are_projected_per_cycle(self) -> None:
        installed = datetime(2026, 7, 1, tzinfo=timezone.utc)
        projection = extractor_program_projection(
            install_time=installed,
            expiry_time=installed + timedelta(days=1),
            cycle_time=3600,
            quantity_per_cycle=1000,
            now=installed + timedelta(hours=12),
        )

        self.assertEqual(projection["cycle_count"], 24)
        self.assertEqual(projection["program_output"], 71899)
        self.assertEqual(projection["average_daily_output"], 71899)
        self.assertEqual(projection["remaining_output"], 30603)

    def test_incomplete_program_data_returns_zero_projection(self) -> None:
        projection = extractor_program_projection(
            install_time=None,
            expiry_time=None,
            cycle_time=None,
            quantity_per_cycle=None,
        )

        self.assertEqual(projection["cycle_count"], 0)
        self.assertEqual(projection["program_output"], 0)
        self.assertEqual(projection["remaining_output"], 0)


if __name__ == "__main__":
    unittest.main()
