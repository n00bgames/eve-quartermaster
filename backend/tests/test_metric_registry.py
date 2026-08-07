from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.analytics import add_metric
from app.services.metric_registry import METRIC_CATALOG, aggregate_metric_values, derive_metric_series, derived_metric_definition, metric_definition, validate_metric_registry


class FakeDb:
    def __init__(self) -> None:
        self.rows = []

    def add(self, row) -> None:
        self.rows.append(row)


class MetricRegistryTests(unittest.TestCase):
    def test_every_metric_has_an_explicit_aggregation_contract(self) -> None:
        validate_metric_registry()
        for definition in METRIC_CATALOG:
            self.assertIn(definition["timeAggregation"], definition["supportedAggregations"])
            self.assertIn("entityAggregation", definition)
            self.assertIn("valueKind", definition)
            self.assertIn("privacy", definition)

    def test_wallet_balance_supports_gauge_analysis(self) -> None:
        definition = metric_definition("character_wallet.balance")
        self.assertEqual(definition["timeAggregation"], "latest")
        self.assertIn("delta", definition["supportedAggregations"])
        self.assertIn("average", definition["supportedAggregations"])
        self.assertIn("daily_delta", definition["supportedTransforms"])
        self.assertIn("rolling_average", definition["supportedTransforms"])

    def test_wallet_metrics_declare_virtual_derivatives(self) -> None:
        definition = metric_definition("character_wallet.balance")
        derived = {item["metric"]: item for item in definition["derivedMetrics"]}
        self.assertEqual(set(derived), {"character_wallet.delta.daily", "character_wallet.delta.weekly", "character_wallet.growth.percent", "character_wallet.rolling_average_30d"})
        self.assertFalse(derived["character_wallet.delta.daily"]["materialized"])
        self.assertEqual(derived_metric_definition("character_wallet.delta.weekly")["windowDays"], 7)

    def test_wallet_derivatives_are_calculated_without_stored_rows(self) -> None:
        points = [
            {"date": "2026-07-01", "value": 100},
            {"date": "2026-07-02", "value": 140},
            {"date": "2026-07-08", "value": 200},
        ]
        derived = derive_metric_series("character_wallet.balance", points)
        self.assertEqual([point["value"] for point in derived["character_wallet.delta.daily"]], [40, 60])
        self.assertEqual(derived["character_wallet.delta.weekly"], [{"date": "2026-07-08", "value": 100.0}])
        self.assertEqual(derived["character_wallet.growth.percent"][-1]["value"], 100)
        self.assertEqual(derived["character_wallet.rolling_average_30d"][-1]["value"], 440 / 3)

    def test_common_aggregations_are_centralized(self) -> None:
        values = [100, 140, 130]
        self.assertEqual(aggregate_metric_values(values, "latest"), 130)
        self.assertEqual(aggregate_metric_values(values, "delta"), 30)
        self.assertEqual(aggregate_metric_values(values, "average"), 370 / 3)
        self.assertEqual(aggregate_metric_values(values, "max"), 140)
        self.assertEqual(aggregate_metric_values(values, "sum"), 370)
        self.assertEqual(sum(row["count"] for row in aggregate_metric_values(values, "histogram", histogram_bins=2)["bins"]), 3)

    def test_snapshot_writer_uses_registered_version(self) -> None:
        db = FakeDb()
        add_metric(db, SimpleNamespace(id=44), owner_type="corporation", owner_id=7, owner_name="Example Corp", metric_key="wallet.balance", metric_value=123)
        self.assertEqual(db.rows[0].metric_version, metric_definition("wallet.balance")["version"])

    def test_snapshot_writer_rejects_unregistered_metrics(self) -> None:
        with self.assertRaisesRegex(ValueError, "is not registered"):
            add_metric(FakeDb(), SimpleNamespace(id=44), owner_type="character", owner_id=9, owner_name="Example Pilot", metric_key="mystery.value", metric_value=1)


if __name__ == "__main__":
    unittest.main()
