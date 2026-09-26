from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api import hypernet
from app.schemas.hypernet import HyperNetParticipationPatch, HyperNetParticipationResolve


def bid_fixture(outcome="pending"):
    return SimpleNamespace(
        id=12, character_id=7, character=SimpleNamespace(name="Buyer"),
        item_type_id=99, item_type=SimpleNamespace(name="Prize", group=None),
        seller_name="Seller", location_id=None, location=None,
        location_name_snapshot="Station", external_offer_reference="offer-reference",
        total_nodes=8, nodes_purchased=2, node_price=Decimal("50000000"),
        total_spent=Decimal("100000000"), outcome=outcome,
        won=None, item_value_at_completion=None, profit_loss=None,
        created_at=datetime(2026, 9, 20, tzinfo=timezone.utc), completed_at=None,
        notes="Original purchase notes",
    )


class ExpiredBidTests(unittest.TestCase):
    def setUp(self):
        self.engine = patch("app.services.hypernet_economics_engine._engine", return_value=("python", "", 1))
        self.engine.start()
        self.addCleanup(self.engine.stop)
        self.user = SimpleNamespace(id=1)
        self.db = MagicMock()

    def test_resolve_expired_preserves_history_and_records_full_refund(self):
        row = bid_fixture()
        completed = row.created_at + timedelta(days=3)
        with patch.object(hypernet, "owned_participation", return_value=row), patch.object(hypernet, "record_audit_event") as audit:
            result = hypernet.resolve_hypernet_participation(
                row.id, HyperNetParticipationResolve(outcome="expired", completed_at=completed, notes="Offer expired"),
                user=self.user, db=self.db,
            )
        self.assertEqual(result["outcome"], "expired")
        self.assertEqual(result["profit_loss"], 0)
        self.assertIsNone(result["won"])
        self.assertIsNone(result["item_value_at_completion"])
        self.assertEqual(result["total_spent"], 100000000)
        self.assertEqual(result["nodes_purchased"], 2)
        self.assertEqual(result["external_offer_reference"], "offer-reference")
        self.assertEqual(result["created_at"], row.created_at.isoformat())
        self.assertEqual(result["completed_at"], completed.isoformat())
        self.assertEqual(result["notes"], "Original purchase notes\n\nOffer expired")
        self.db.commit.assert_called_once()
        audit.assert_called_once()

    def test_correct_won_or_lost_bid_to_expired_and_reopen(self):
        for outcome in ("won", "lost"):
            with self.subTest(outcome=outcome):
                row = bid_fixture(outcome)
                row.completed_at = row.created_at + timedelta(days=3)
                row.won = outcome == "won"
                row.item_value_at_completion = Decimal("1000000000") if row.won else None
                row.profit_loss = Decimal("900000000") if row.won else Decimal("-100000000")
                with patch.object(hypernet, "owned_participation", return_value=row), patch.object(hypernet, "record_audit_event"):
                    result = hypernet.patch_hypernet_participation(
                        row.id, HyperNetParticipationPatch(outcome="expired"), user=self.user, db=self.db,
                    )
                    self.assertEqual(result["profit_loss"], 0)
                    self.assertIsNone(result["won"])
                    self.assertIsNone(result["item_value_at_completion"])
                    self.assertEqual(result["total_spent"], 100000000)
                    reopened = hypernet.patch_hypernet_participation(
                        row.id, HyperNetParticipationPatch(outcome="pending"), user=self.user, db=self.db,
                    )
                self.assertIsNone(reopened["completed_at"])
                self.assertIsNone(reopened["profit_loss"])
                self.assertEqual(reopened["notes"], "Original purchase notes")

    def summary(self, bids):
        offers_result = MagicMock()
        offers_result.unique.return_value.all.return_value = []
        bids_result = MagicMock()
        bids_result.all.return_value = bids
        self.db.scalars.side_effect = [offers_result, bids_result]
        return hypernet.hypernet_summary(user=self.user, db=self.db)

    def test_expired_bid_does_not_change_any_summary_metric(self):
        pending = bid_fixture()
        won = bid_fixture("won")
        won.item_value_at_completion = Decimal("400000000")
        won.profit_loss = Decimal("300000000")
        lost = bid_fixture("lost")
        lost.profit_loss = Decimal("-100000000")
        baseline = self.summary([pending, won, lost])
        expired = bid_fixture("expired")
        expired.profit_loss = Decimal("0")
        self.assertEqual(self.summary([pending, won, lost, expired]), baseline)
        metrics = baseline["participation"]
        self.assertEqual(metrics["active_spend"], 100000000)
        self.assertEqual(metrics["win_rate_percent"], 50)
        self.assertEqual(metrics["expected_wins"], 0.5)
        self.assertEqual(metrics["return_on_spend_percent"], 100)
        self.assertEqual(self.summary([expired]), self.summary([]))

    def test_expired_filter_preserves_serialized_bid_history(self):
        row = bid_fixture("expired")
        row.completed_at = row.created_at + timedelta(days=3)
        row.profit_loss = Decimal("0")
        self.db.scalars.return_value.unique.return_value.all.return_value = [row]
        result = hypernet.list_hypernet_participations(outcome="expired", limit=100, user=self.user, db=self.db)
        self.assertEqual(result[0]["id"], row.id)
        self.assertEqual(result[0]["outcome"], "expired")
        query = self.db.scalars.call_args.args[0].compile()
        self.assertIn("expired", query.params.values())
        self.assertIn(self.user.id, query.params.values())


if __name__ == "__main__":
    unittest.main()
