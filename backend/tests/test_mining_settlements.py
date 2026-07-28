from __future__ import annotations

import unittest
from decimal import Decimal

from app.services.mining_settlements import (
    SettlementValidationError,
    calculate_settlement,
    normalize_percentage,
)


def rows(values: tuple[int, ...] = (600, 400)) -> list[dict]:
    return [
        {
            "character_id": index + 1,
            "character_name": f"Miner {index + 1}",
            "ore_type_name": "Veldspar",
            "quantity": value * 10,
            "volume": value * 2,
            "estimated_price": value,
        }
        for index, value in enumerate(values)
    ]


def payload(**patch) -> dict:
    base = {
        "contribution_basis": "estimated_raw_value",
        "price_source": "jita_split",
        "outputs": [
            {
                "type_id": 34,
                "type_name": "Tritanium",
                "quantity": 100,
                "unit_price": 10,
                "price_source": "jita_split",
                "price_overridden": False,
            }
        ],
        "reserve": {"method": "none", "value": 0},
        "deductions": [],
        "participants": [],
    }
    base.update(patch)
    return base


class PercentageNormalizationTests(unittest.TestCase):
    def test_decimal_percentage(self):
        self.assertEqual(normalize_percentage("0.10"), Decimal("0.1000000000"))

    def test_whole_number_percentage(self):
        self.assertEqual(normalize_percentage("10"), Decimal("0.1000000000"))

    def test_percentage_over_100_is_rejected(self):
        with self.assertRaises(SettlementValidationError):
            normalize_percentage("101")


class SettlementCalculationTests(unittest.TestCase):
    def test_gross_refined_value(self):
        result = calculate_settlement(rows(), payload())
        self.assertEqual(result["gross_value"], Decimal("1000.00"))
        self.assertEqual(result["participant_payout_total"], Decimal("1000.00"))

    def test_flat_reserve(self):
        result = calculate_settlement(rows(), payload(reserve={"method": "flat_isk", "value": 100}))
        self.assertEqual(result["reserve_value"], Decimal("100.00"))
        self.assertEqual(result["distributable_value"], Decimal("900.00"))

    def test_percentage_reserve(self):
        result = calculate_settlement(rows(), payload(reserve={"method": "percentage", "value": 10}))
        self.assertEqual(result["reserve_value"], Decimal("100.00"))

    def test_multiple_miners_use_value_weight(self):
        result = calculate_settlement(rows(), payload())
        payouts = {row["display_name"]: row["payout_isk"] for row in result["participants"]}
        self.assertEqual(payouts, {"Miner 1": Decimal("600"), "Miner 2": Decimal("400")})

    def test_volume_basis_changes_weights(self):
        custom_rows = rows()
        custom_rows[0]["volume"] = 10
        custom_rows[1]["volume"] = 90
        result = calculate_settlement(custom_rows, payload(contribution_basis="volume"))
        payouts = {row["display_name"]: row["payout_isk"] for row in result["participants"]}
        self.assertEqual(payouts, {"Miner 1": Decimal("100"), "Miner 2": Decimal("900")})

    def test_fixed_participant_payout(self):
        support = {
            "source": "manual",
            "display_name": "Fleet Booster",
            "role": "Booster",
            "compensation_method": "fixed_percentage",
            "compensation_value": 10,
        }
        result = calculate_settlement(rows(), payload(participants=[support]))
        payouts = {row["display_name"]: row["payout_isk"] for row in result["participants"]}
        self.assertEqual(payouts["Fleet Booster"], Decimal("100.00"))
        self.assertEqual(payouts["Miner 1"], Decimal("540"))
        self.assertEqual(payouts["Miner 2"], Decimal("360"))

    def test_manual_share_participant(self):
        support = {
            "source": "manual",
            "display_name": "Scout",
            "role": "Scout",
            "compensation_method": "shares",
            "compensation_value": "1",
        }
        result = calculate_settlement(rows((500, 500)), payload(participants=[support]))
        payouts = {row["display_name"]: row["payout_isk"] for row in result["participants"]}
        self.assertEqual(payouts["Scout"], Decimal("333.33"))
        self.assertEqual(sum(payouts.values()), Decimal("1000.00"))

    def test_mixed_fixed_and_weighted_payouts(self):
        participants = [
            {
                "source": "manual",
                "display_name": "Security",
                "role": "Security",
                "compensation_method": "fixed_percentage",
                "compensation_value": "5",
            },
            {
                "source": "manual",
                "display_name": "Hauler",
                "role": "Hauler",
                "compensation_method": "shares",
                "compensation_value": "0.5",
            },
        ]
        result = calculate_settlement(rows((500, 500)), payload(participants=participants))
        self.assertEqual(result["fixed_payout_total"], Decimal("50.00"))
        self.assertEqual(result["share_pool_value"], Decimal("950.00"))
        self.assertEqual(result["participant_payout_total"], Decimal("1000.00"))
        self.assertEqual(result["unallocated_remainder"], Decimal("0.00"))

    def test_zero_share_weight_is_rejected(self):
        overrides = [
            {"source": "ledger", "character_id": 1, "compensation_method": "shares", "compensation_value": 0, "share_weight_overridden": True},
            {"source": "ledger", "character_id": 2, "compensation_method": "shares", "compensation_value": 0, "share_weight_overridden": True},
        ]
        with self.assertRaisesRegex(SettlementValidationError, "share weight is zero"):
            calculate_settlement(rows(), payload(participants=overrides))

    def test_fixed_percentages_over_100_are_rejected(self):
        support = [
            {"source": "manual", "display_name": "A", "role": "Scout", "compensation_method": "fixed_percentage", "compensation_value": 60},
            {"source": "manual", "display_name": "B", "role": "Security", "compensation_method": "fixed_percentage", "compensation_value": 50},
        ]
        with self.assertRaisesRegex(SettlementValidationError, "cannot exceed 100%"):
            calculate_settlement(rows(), payload(participants=support))

    def test_deductions_exceeding_gross_are_rejected(self):
        deductions = [{"deduction_type": "hauling", "description": "Hauling", "calculation_method": "flat_isk", "value": 1200}]
        with self.assertRaisesRegex(SettlementValidationError, "cannot exceed gross"):
            calculate_settlement(rows(), payload(deductions=deductions))

    def test_missing_price_warns_without_losing_output(self):
        output = [{**payload()["outputs"][0], "unit_price": 0}]
        result = calculate_settlement(rows(), payload(outputs=output))
        self.assertEqual(result["gross_value"], Decimal("0.00"))
        self.assertTrue(any("no unit price" in warning for warning in result["warnings"]))

    def test_manual_price_override_warns(self):
        output = [{**payload()["outputs"][0], "price_overridden": True}]
        result = calculate_settlement(rows(), payload(outputs=output))
        self.assertTrue(any("overridden unit price" in warning for warning in result["warnings"]))

    def test_rounding_reconciles_to_the_cent(self):
        result = calculate_settlement(rows((1, 1, 1)), payload())
        payouts = [row["payout_isk"] for row in result["participants"]]
        self.assertEqual(payouts, [Decimal("333.34"), Decimal("333.33"), Decimal("333.33")])
        self.assertEqual(sum(payouts), Decimal("1000.00"))
        self.assertEqual(result["unallocated_remainder"], Decimal("0.00"))

    def test_mineral_mode_allocates_whole_units(self):
        result = calculate_settlement(rows(), payload(settlement_mode="minerals"))
        payouts = {
            row["display_name"]: row["mineral_payouts"][0]["quantity"]
            for row in result["participants"]
        }
        self.assertEqual(result["settlement_mode"], "minerals")
        self.assertEqual(payouts, {"Miner 1": 60, "Miner 2": 40})
        self.assertEqual(result["outputs"][0]["distributed_quantity"], 100)
        self.assertEqual(result["outputs"][0]["retained_quantity"], 0)

    def test_mineral_mode_retains_reserve_proportionally(self):
        result = calculate_settlement(
            rows(),
            payload(settlement_mode="minerals", reserve={"method": "percentage", "value": 10}),
        )
        payouts = {
            row["display_name"]: row["mineral_payouts"][0]["quantity"]
            for row in result["participants"]
        }
        self.assertEqual(payouts, {"Miner 1": 54, "Miner 2": 36})
        self.assertEqual(result["outputs"][0]["distributed_quantity"], 90)
        self.assertEqual(result["outputs"][0]["retained_quantity"], 10)

    def test_mineral_rounding_is_deterministic_and_reconciles(self):
        output = [{**payload()["outputs"][0], "quantity": 10}]
        result = calculate_settlement(
            rows((1, 1, 1)),
            payload(settlement_mode="minerals", outputs=output),
        )
        payouts = [row["mineral_payouts"][0]["quantity"] for row in result["participants"]]
        self.assertEqual(payouts, [4, 3, 3])
        self.assertEqual(sum(payouts), result["outputs"][0]["distributed_quantity"])

    def test_unpriced_minerals_can_still_be_split(self):
        output = [{**payload()["outputs"][0], "quantity": 11, "unit_price": 0}]
        result = calculate_settlement(
            rows((1, 1)),
            payload(settlement_mode="minerals", outputs=output),
        )
        payouts = [row["mineral_payouts"][0]["quantity"] for row in result["participants"]]
        self.assertEqual(payouts, [6, 5])
        self.assertEqual([row["payout_ratio"] for row in result["participants"]], [Decimal("0.5000000000")] * 2)

    def test_duplicate_outputs_are_rejected(self):
        duplicate = payload()["outputs"] * 2
        with self.assertRaisesRegex(SettlementValidationError, "appears more than once"):
            calculate_settlement(rows(), payload(outputs=duplicate))

    def test_negative_output_is_rejected(self):
        output = [{**payload()["outputs"][0], "quantity": -1}]
        with self.assertRaisesRegex(SettlementValidationError, "cannot be negative"):
            calculate_settlement(rows(), payload(outputs=output))


if __name__ == "__main__":
    unittest.main()
