import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import hypernet
from app.models import Base, EveType, HyperNetOffer
from app.schemas.hypernet import HyperNetReconcileRequest


class HyperNetOfferCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[EveType.__table__, HyperNetOffer.__table__])
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.now = datetime.now(timezone.utc)
        self.user = SimpleNamespace(id=1)
        self.offer = HyperNetOffer(
            owner_user_id=1, seller_character_id=1, type_id=1, status="completed",
            created_offer_at=self.now - timedelta(days=1), expires_at=self.now + timedelta(days=2),
            completed_at=self.now, reconciled_at=self.now, total_offer_price=Decimal("5000000000"),
            total_nodes=512, nodes_sold=512, seller_owned_nodes=256, unique_participants=3,
            acquisition_cost=Decimal("3500000000"), hypercores_required=532,
            hypercore_unit_cost=Decimal("300000"), actual_hypercore_cost=Decimal("168698700"),
            payout=Decimal("4750000000"), final_profit=Decimal("-1418698700"),
            winner="external", item_outcome="transferred", notes="Original note",
        )
        self.db.add(self.offer)
        self.db.commit()
        self.audit = Mock()
        for name, replacement in [
            ("offer_options", lambda: ()),
            ("serialize_offer", lambda row, **kw: {"final_profit": row.final_profit, "status": row.status}),
            ("record_audit_event", self.audit),
        ]:
            mocked = patch.object(hypernet, name, replacement)
            mocked.start()
            self.addCleanup(mocked.stop)

    def edit(self, **changes):
        payload = dict(status=self.offer.status, reconciled_at=self.now, winner="external")
        payload.update(changes)
        return hypernet.edit_hypernet_reconciliation(
            self.offer.id, HyperNetReconcileRequest(**payload), self.user, self.db,
        )

    def test_zero_override_is_persisted_and_audited(self):
        self.edit(final_profit=0, note="Historical hull cost is estimated")
        self.assertEqual(self.db.get(HyperNetOffer, self.offer.id).final_profit, Decimal("0"))
        self.assertEqual(self.offer.status, "completed")
        self.assertEqual(self.offer.nodes_sold, 512)
        self.assertIn("Original note", self.offer.notes)
        self.assertEqual(self.audit.call_args.kwargs["event_kind"], "hypernet_offer_corrected")
        self.assertIn("-1418698700", self.audit.call_args.kwargs["body"])

    def test_clear_override_recalculates_with_corrected_cost_and_preserves_actual_cores(self):
        self.edit(acquisition_cost=2_000_000_000, final_profit=None)
        self.assertEqual(self.offer.final_profit, Decimal("81301300"))
        self.assertEqual(self.offer.actual_hypercore_cost, Decimal("168698700"))

    def test_corrected_winner_and_explicit_zero_inputs(self):
        self.edit(winner="seller", seller_owned_nodes=0, unique_participants=0,
                  actual_hypercore_cost=0, final_payout=0, final_market_value=0)
        self.assertEqual(self.offer.final_profit, Decimal("-3500000000"))
        self.assertEqual(self.offer.seller_owned_nodes, 0)
        self.assertEqual(self.offer.unique_participants, 0)
        self.assertEqual(self.offer.item_outcome, "retained")

    def test_expired_offer_recalculates_core_loss(self):
        self.offer.status = "expired"
        self.edit(winner="unknown", actual_hypercore_cost=125)
        self.assertEqual(self.offer.final_profit, Decimal("-125"))
        self.assertEqual(self.offer.item_outcome, "retained")

    def test_cancelled_offer_accepts_manual_result(self):
        self.offer.status = "cancelled"
        self.edit(winner="unknown", final_profit=-50)
        self.assertEqual(self.offer.final_profit, Decimal("-50"))

    def test_other_users_cannot_edit_offer(self):
        with self.assertRaises(HTTPException) as caught:
            hypernet.edit_hypernet_reconciliation(self.offer.id,
                HyperNetReconcileRequest(status="completed", winner="external", reconciled_at=self.now),
                SimpleNamespace(id=2), self.db)
        self.assertEqual(caught.exception.status_code, 404)

    def test_active_offer_and_status_change_rejected(self):
        with self.assertRaises(HTTPException):
            self.edit(status="expired")
        self.offer.status = "active"
        with self.assertRaises(HTTPException) as caught:
            self.edit(status="completed")
        self.assertEqual(caught.exception.status_code, 409)

    def test_invalid_counts_and_date_rejected_before_mutation(self):
        for changes in [dict(seller_owned_nodes=513), dict(reconciled_at=self.now-timedelta(days=2))]:
            with self.assertRaises(HTTPException):
                self.edit(**changes)
        self.assertEqual(self.offer.final_profit, Decimal("-1418698700"))
        self.audit.assert_not_called()

    def test_original_completion_endpoint_still_rejects_double_completion(self):
        with self.assertRaises(HTTPException) as caught:
            hypernet.reconcile_hypernet_offer(self.offer.id,
                HyperNetReconcileRequest(status="completed", winner="external", reconciled_at=self.now),
                self.user, self.db)
        self.assertEqual(caught.exception.status_code, 409)
