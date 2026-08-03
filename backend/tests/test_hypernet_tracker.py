from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.schemas.hypernet import HyperNetOfferCreate, HyperNetSnapshotCreate
from app.services.hypernet import data_source, offer_financials, progress_metrics, seeded_node_scenario


class HyperNetFinancialTests(unittest.TestCase):
    def test_eight_node_marshal_offer_calculates_fee_profit_and_break_even(self) -> None:
        result = offer_financials(
            total_offer_price=Decimal("12000000000"),
            total_nodes=8,
            hypercores_required=16,
            hypercore_unit_cost=Decimal("5000000"),
            acquisition_cost=Decimal("9000000000"),
            desired_profit=Decimal("1000000000"),
        )

        self.assertEqual(result["node_price"], Decimal("1500000000.00"))
        self.assertEqual(result["completion_fee"], Decimal("600000000.00"))
        self.assertEqual(result["hypercore_cost"], Decimal("80000000.00"))
        self.assertEqual(result["payout_after_fee"], Decimal("11400000000.00"))
        self.assertEqual(result["net_proceeds"], Decimal("11320000000.00"))
        self.assertEqual(result["profit"], Decimal("2320000000.00"))
        self.assertEqual(result["break_even_offer_price"], Decimal("9557894736.84"))
        self.assertEqual(result["minimum_offer_for_target_profit"], Decimal("10610526315.79"))

    def test_seeded_nodes_are_separate_from_organic_sales_and_preserve_retained_item(self) -> None:
        scenario = seeded_node_scenario(
            total_nodes=8,
            seller_owned_nodes=2,
            node_price=Decimal("1500000000"),
            acquisition_cost=Decimal("9000000000"),
            hypercore_cost=Decimal("80000000"),
            payout_after_fee=Decimal("11400000000"),
            current_jita_sell=Decimal("9500000000"),
        )

        self.assertEqual(scenario["seller_win_probability_percent"], Decimal("25.00"))
        self.assertEqual(scenario["seller_node_spend"], Decimal("3000000000.00"))
        self.assertEqual(scenario["cash_result_if_external_wins"], Decimal("-680000000.00"))
        self.assertTrue(scenario["seller_wins_item_retained"])
        self.assertEqual(scenario["seller_win_mark_to_jita_result"], Decimal("8820000000.00"))

    def test_progress_snapshot_detects_first_organic_node(self) -> None:
        created = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
        snapshots = [
            SimpleNamespace(id=1, captured_at=created, nodes_sold=0, seller_owned_nodes=0),
            SimpleNamespace(id=2, captured_at=created + timedelta(hours=2), nodes_sold=1, seller_owned_nodes=1),
            SimpleNamespace(id=3, captured_at=created + timedelta(hours=4), nodes_sold=2, seller_owned_nodes=1),
        ]

        result = progress_metrics(created_at=created, total_nodes=8, snapshots=snapshots)

        self.assertEqual(result["hours_to_first_organic_node"], 4)
        self.assertEqual(result["organic_nodes_per_hour"], 0.25)
        self.assertEqual(result["estimated_hours_to_completion"], 24)

    def test_manual_source_is_explicit_and_future_provider_safe(self) -> None:
        source = data_source("manual")
        self.assertEqual(source.key, "manual")
        self.assertEqual(source.reference(" HYPERNET-REF "), "HYPERNET-REF")
        with self.assertRaises(ValueError):
            data_source("esi")


class HyperNetSchemaTests(unittest.TestCase):
    def test_offer_requires_timezone_and_valid_progress(self) -> None:
        created = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
        offer = HyperNetOfferCreate(
            seller_character_id=1,
            type_id=44996,
            quantity=1,
            total_offer_price=12_000_000_000,
            total_nodes=8,
            nodes_sold=1,
            seller_owned_nodes=0,
            hypercores_required=16,
            hypercore_unit_cost=5_000_000,
            acquisition_cost=9_000_000_000,
            created_offer_at=created,
            expires_at=created + timedelta(days=3),
        )
        self.assertEqual(offer.total_nodes, 8)
        self.assertEqual(offer.nodes_sold, 1)

    def test_snapshot_rejects_seeded_nodes_above_total_sold(self) -> None:
        with self.assertRaises(ValueError):
            HyperNetSnapshotCreate(
                captured_at=datetime.now(timezone.utc),
                nodes_sold=1,
                seller_owned_nodes=2,
            )


if __name__ == "__main__":
    unittest.main()
