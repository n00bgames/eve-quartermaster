import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import hypernet
from app.models import Base, EsiToken, EveCharacter, EveType, HyperNetOffer, HyperNetOfferSnapshot, HyperNetParticipant, Location
from app.schemas.hypernet import HyperNetOfferPatch


class HyperNetOfferEditTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[row.__table__ for row in
            (EveType, HyperNetOffer, HyperNetOfferSnapshot, HyperNetParticipant, Location, EveCharacter, EsiToken)])
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.now = datetime.now(timezone.utc)
        self.user = SimpleNamespace(id=1)
        self.offer = HyperNetOffer(
            owner_user_id=1, seller_character_id=1, type_id=1, status="active",
            created_offer_at=self.now, expires_at=self.now + timedelta(days=3),
            total_offer_price=Decimal("160000000"), total_nodes=8, nodes_sold=8,
            seller_owned_nodes=8, unique_participants=1, acquisition_cost=Decimal("110000000"),
            hypercores_required=16, hypercore_unit_cost=Decimal("300000"), desired_profit=0,
        )
        self.offer.snapshots = [HyperNetOfferSnapshot(captured_at=self.now, nodes_sold=8,
            seller_owned_nodes=8, unique_participants=1, source="manual", created_by_user_id=1)]
        self.offer.participants = [HyperNetParticipant(participant_name="Seller", nodes_owned=8,
            is_seller=True, first_seen_at=self.now, last_seen_at=self.now)]
        self.db.add(self.offer)
        self.db.commit()
        self.audit = Mock()
        self.real_serialize = hypernet.serialize_offer
        for name, replacement in [
            ("offer_options", lambda: ()),
            ("serialize_offer", lambda row, **kw: hypernet.offer_calculations(row)),
            ("record_audit_event", self.audit),
        ]:
            mocked = patch.object(hypernet, name, replacement)
            mocked.start()
            self.addCleanup(mocked.stop)

    def edit(self, **changes):
        return hypernet.patch_hypernet_offer(self.offer.id, HyperNetOfferPatch(**changes), self.user, self.db)

    def test_eight_to_sixteen_preserves_progress_and_recalculates(self):
        result = self.edit(total_nodes=16)
        self.assertEqual(self.offer.total_nodes, 16)
        self.assertEqual(self.offer.nodes_sold, 8)
        self.assertEqual(self.offer.seller_owned_nodes, 8)
        self.assertEqual(self.offer.snapshots[0].nodes_sold, 8)
        self.assertEqual(self.offer.participants[0].nodes_owned, 8)
        self.assertEqual(result["financials"]["node_price"], 10_000_000)
        self.assertEqual(result["seeded_scenario"]["seller_win_probability_percent"], 50)
        self.assertEqual(result["seeded_scenario"]["seller_node_spend"], 80_000_000)
        self.assertEqual(self.audit.call_args.kwargs["event_kind"], "hypernet_offer_edited")
        self.assertIn("'total_nodes': '8'", self.audit.call_args.kwargs["body"])
        self.assertIn("'total_nodes': '16'", self.audit.call_args.kwargs["body"])

    def test_incorrectly_full_offer_returns_to_active(self):
        self.offer.status = "awaiting_reconciliation"
        self.edit(total_nodes=16)
        self.assertEqual(self.offer.status, "active")

    def test_reducing_capacity_to_sold_count_requires_reconciliation(self):
        self.offer.total_nodes = 16
        self.edit(total_nodes=8)
        self.assertEqual(self.offer.status, "awaiting_reconciliation")

    def test_draft_stays_draft(self):
        self.offer.status = "draft"
        self.edit(total_nodes=16)
        self.assertEqual(self.offer.status, "draft")

    def test_economic_corrections_preserve_explicit_zero(self):
        self.edit(total_offer_price=148_000_000, hypercores_required=0,
                  hypercore_unit_cost=0, acquisition_cost=0, desired_profit=-10, quantity=2, notes=None)
        self.assertEqual(self.offer.payout, Decimal("140600000"))
        self.assertEqual(self.offer.completion_fee, Decimal("7400000"))
        self.assertEqual(self.offer.hypercores_required, 0)
        self.assertEqual(self.offer.acquisition_cost, 0)
        self.assertEqual(self.offer.quantity, 2)

    def test_invalid_capacity_and_expiry_rejected_before_mutation(self):
        for changes in [dict(total_nodes=4), dict(expires_at=self.now)]:
            with self.assertRaises(HTTPException) as caught:
                self.edit(total_offer_price=1, **changes)
            self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.offer.total_offer_price, 160_000_000)
        self.audit.assert_not_called()

    def test_historical_and_participant_counts_bound_capacity(self):
        for relation in [self.offer.snapshots[0], self.offer.participants[0]]:
            field = "nodes_sold" if isinstance(relation, HyperNetOfferSnapshot) else "nodes_owned"
            setattr(relation, field, 20)
            with self.assertRaises(HTTPException):
                self.edit(total_nodes=16)
            setattr(relation, field, 8)

    def test_other_users_cannot_edit(self):
        with self.assertRaises(HTTPException) as caught:
            hypernet.patch_hypernet_offer(self.offer.id, HyperNetOfferPatch(total_nodes=16),
                                         SimpleNamespace(id=2), self.db)
        self.assertEqual(caught.exception.status_code, 404)

    def test_ended_offers_rejected(self):
        for status in ["completed", "expired", "cancelled", "invalid"]:
            self.offer.status = status
            with self.assertRaises(HTTPException) as caught:
                self.edit(total_nodes=16)
            self.assertEqual(caught.exception.status_code, 409)

    def test_invalid_schema_inputs(self):
        for changes in [dict(total_nodes=0), dict(total_nodes=513), dict(total_nodes=8.5),
                        dict(seller_character_id=None), dict(seller_character_id=0), dict(seller_character_id=1.5),
                        dict(total_nodes=None), dict(total_offer_price=None), dict(expires_at=None),
                        dict(hypercores_required=-1), dict(quantity=0), dict(total_offer_price=-1)]:
            with self.assertRaises(ValidationError):
                HyperNetOfferPatch(**changes)

    def test_location_selection_replaces_loaded_relationship_and_is_audited(self):
        old = Location(name="Old station", eve_location_id=60000001)
        new = Location(name="Jita IV - Moon 4 - Caldari Navy Assembly Plant", eve_location_id=60003760)
        self.db.add_all([old, new])
        self.db.flush()
        self.offer.location = old
        self.offer.location_name_snapshot = old.name
        self.db.commit()
        self.edit(location_id=new.id, location_name="Untrusted display label")
        self.assertEqual(self.offer.location_id, new.id)
        self.assertEqual(self.offer.location.name, new.name)
        self.assertEqual(self.offer.location_name_snapshot, new.name)
        self.assertIn("Old station", self.audit.call_args.kwargs["body"])
        self.assertIn(new.name, self.audit.call_args.kwargs["body"])

    def test_manual_location_detaches_existing_link_and_can_be_cleared(self):
        location = Location(name="Old station", eve_location_id=60000001)
        self.db.add(location)
        self.offer.location = location
        self.db.commit()
        self.edit(location_name="  Manually entered station  ")
        self.assertIsNone(self.offer.location_id)
        self.assertIsNone(self.offer.location)
        self.assertEqual(self.offer.location_name_snapshot, "Manually entered station")
        self.edit(location_id=None, location_name=None)
        self.assertIsNone(self.offer.location_name_snapshot)

    def test_unrelated_edits_preserve_location(self):
        self.offer.location_name_snapshot = "SDE station"
        self.edit(total_nodes=16)
        self.assertEqual(self.offer.location_name_snapshot, "SDE station")

    def test_invalid_location_rejected_before_other_changes(self):
        with self.assertRaises(HTTPException) as caught:
            self.edit(location_id=9999, total_nodes=16)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.offer.total_nodes, 8)
        self.audit.assert_not_called()

    def character(self, id, owner=1, linked=True):
        row = EveCharacter(id=id, character_id=90000 + id, name=f"Pilot {id}", owner_user_id=owner)
        self.db.add(row)
        if linked:
            self.db.add(EsiToken(user_id=owner, character_id=id, scopes="", encrypted_refresh_token="test"))
        self.db.commit()
        return row

    def test_seller_correction_refreshes_loaded_identity_and_preserves_observations(self):
        old = self.character(1)
        new = self.character(2)
        self.offer.seller_character = old
        self.offer.participants[0].character_id = old.id
        self.offer.node_map = {"columns": 4, "seeded_positions": [1, 2], "winning_position": None}
        self.db.commit()
        original_cost = self.offer.acquisition_cost
        with patch.object(hypernet, "serialize_offer", self.real_serialize):
            result = self.edit(seller_character_id=new.id)
        self.assertEqual(result["seller"], {"id": new.id, "character_id": new.character_id, "name": new.name})
        self.assertEqual(self.offer.owner_user_id, 1)
        self.assertEqual(self.offer.acquisition_cost, original_cost)
        self.assertEqual(self.offer.nodes_sold, 8)
        self.assertEqual(self.offer.seller_owned_nodes, 8)
        self.assertEqual(self.offer.participants[0].character_id, old.id)
        self.assertEqual(self.offer.participants[0].participant_name, "Seller")
        self.assertEqual(len(self.offer.snapshots), 1)
        self.assertEqual(self.offer.node_map["seeded_positions"], [1, 2])
        self.assertIn("'seller_character_id': '1'", self.audit.call_args.kwargs["body"])
        self.assertIn("'seller_character_id': '2'", self.audit.call_args.kwargs["body"])
        self.assertEqual(hypernet.list_hypernet_offers(seller_character_id=1, limit=10, user=self.user, db=self.db), [])
        self.assertEqual(len(hypernet.list_hypernet_offers(seller_character_id=2, limit=10, user=self.user, db=self.db)), 1)

    def test_invalid_seller_rejected_before_mutations(self):
        self.character(2, owner=2)
        self.character(3, linked=False)
        for id in [2, 3, 9999]:
            with self.assertRaises(HTTPException) as caught:
                self.edit(seller_character_id=id, total_nodes=16)
            self.assertEqual(caught.exception.status_code, 400)
            self.assertEqual(self.offer.seller_character_id, 1)
            self.assertEqual(self.offer.total_nodes, 8)
        self.audit.assert_not_called()

    def test_retaining_unlinked_current_seller_does_not_block_other_edits(self):
        self.character(1, linked=False)
        self.edit(seller_character_id=1, total_nodes=16)
        self.assertEqual(self.offer.seller_character_id, 1)
        self.assertEqual(self.offer.total_nodes, 16)

    def test_seller_only_correction_still_requires_offer_ownership(self):
        self.character(2)
        with self.assertRaises(HTTPException) as caught:
            hypernet.patch_hypernet_offer(self.offer.id, HyperNetOfferPatch(seller_character_id=2),
                                         SimpleNamespace(id=2), self.db)
        self.assertEqual(caught.exception.status_code, 404)
