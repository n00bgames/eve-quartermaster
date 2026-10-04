import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import hypernet
from app.models import Base, HyperNetParticipation


class ItemBidHistoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[HyperNetParticipation.__table__])
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.user = SimpleNamespace(id=1)
        for name, value in [
            ("participation_options", lambda: ()),
            ("serialize_participation", lambda row: {"id": row.id, "character_id": row.character_id, "outcome": row.outcome}),
        ]:
            mocked = patch.object(hypernet, name, value)
            mocked.start()
            self.addCleanup(mocked.stop)

    def add_bid(self, outcome, spent, character=1, owner=1, item=10, prize=None):
        spent = Decimal(str(spent))
        prize = Decimal(str(prize)) if prize is not None else None
        row = HyperNetParticipation(
            user_id=owner, character_id=character, item_type_id=item, seller_name="Seller",
            total_nodes=8, nodes_purchased=1, node_price=spent, total_spent=spent,
            outcome=outcome, item_value_at_completion=prize,
            profit_loss=(prize - spent if outcome == "won" else -spent if outcome == "lost" else 0),
            created_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
        )
        self.db.add(row)
        self.db.flush()
        return row

    def history(self, character=None, item=10, offset=0, limit=50):
        return hypernet.hypernet_item_bid_history(type_id=item, character_id=character,
            offset=offset, limit=limit, user=self.user, db=self.db)

    def test_full_item_totals_and_outcome_accounting(self):
        self.add_bid("won", "10.25", prize="40.75")
        self.add_bid("lost", "20.50", character=2)
        self.add_bid("pending", 90)
        self.add_bid("expired", 70)
        self.add_bid("cancelled", 80)
        self.add_bid("lost", 999, item=11)
        self.add_bid("won", 1, owner=2, character=3, prize=9999)
        stats = self.history()["summary"]
        self.assertEqual(stats["total_bids"], 5)
        self.assertEqual(stats["won_bids"], 1)
        self.assertEqual(stats["lost_bids"], 1)
        self.assertEqual(stats["resolved_spend"], 30.75)
        self.assertEqual(stats["lost_spend"], 20.50)
        self.assertEqual(stats["won_profit"], 30.50)
        self.assertEqual(stats["item_value_won"], 40.75)
        self.assertEqual(stats["net_result"], 10)
        self.assertEqual(stats["pending_spend"], 90)
        self.assertEqual(stats["refunded_spend"], 150)
        self.assertEqual(stats["win_rate_percent"], 50)
        self.assertEqual(stats["roi_percent"], 32.52)
        self.assertEqual(self.history(1)["summary"]["net_result"], 30.50)
        self.assertEqual(self.history(2)["summary"]["net_result"], -20.50)
        self.assertEqual(self.history(3)["history"], [])
        self.assertEqual(self.history(item=11)["summary"]["lost_spend"], 999)

    def test_totals_include_records_beyond_board_limit_and_pages_do_not_overlap(self):
        for _ in range(505):
            self.add_bid("lost", 1)
        first = self.history(limit=50)
        second = self.history(offset=50, limit=50)
        last = self.history(offset=500, limit=50)
        self.assertEqual(first["summary"]["total_bids"], 505)
        self.assertEqual(first["summary"]["lost_spend"], 505)
        self.assertEqual(second["summary"], first["summary"])
        self.assertEqual(len(last["history"]), 5)
        self.assertFalse({row["id"] for row in first["history"]} & {row["id"] for row in second["history"]})
        self.assertGreater(first["history"][-1]["id"], second["history"][0]["id"])

    def test_empty_refund_only_and_zero_cost_have_no_fake_rates(self):
        empty = self.history()["summary"]
        self.assertEqual(empty["total_bids"], 0)
        self.assertEqual(empty["net_result"], 0)
        self.assertIsNone(empty["win_rate_percent"])
        self.assertIsNone(empty["roi_percent"])
        self.add_bid("expired", 50)
        self.assertIsNone(self.history()["summary"]["win_rate_percent"])
        self.add_bid("won", 0, prize=100)
        stats = self.history()["summary"]
        self.assertEqual(stats["net_result"], 100)
        self.assertEqual(stats["win_rate_percent"], 100)
        self.assertIsNone(stats["roi_percent"])


if __name__ == "__main__":
    unittest.main()
