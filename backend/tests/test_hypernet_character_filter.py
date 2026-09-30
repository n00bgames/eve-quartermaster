import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import hypernet
from app.models import Base, EsiToken, EveCharacter, HyperNetOffer, HyperNetParticipation
from app.services.hypernet import offer_financials, seeded_node_scenario


class HyperNetCharacterFilterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[
            EveCharacter.__table__, EsiToken.__table__,
            HyperNetOffer.__table__, HyperNetParticipation.__table__,
        ])
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.user = SimpleNamespace(id=1)
        now = datetime.now(timezone.utc)
        self.characters = [
            EveCharacter(id=i, character_id=9000+i, name=f"Pilot {i}", owner_user_id=owner)
            for i, owner in [(1, 1), (2, 1), (3, 2), (4, 1), (5, 2)]
        ]
        self.offers = []
        self.bids = []
        for character, owner, amount in [(1, 1, 100), (2, 1, 200), (3, 2, 900)]:
            for status in ["active", "completed"]:
                self.offers.append(HyperNetOffer(
                    owner_user_id=owner, seller_character_id=character, type_id=1,
                    status=status, created_offer_at=now, expires_at=now + timedelta(hours=character),
                    total_offer_price=amount, total_nodes=16, nodes_sold=6, seller_owned_nodes=6,
                    final_profit=Decimal(amount) if status == "completed" else None,
                ))
            for outcome in ["pending", "lost", "expired"]:
                self.bids.append(HyperNetParticipation(
                    user_id=owner, character_id=character, item_type_id=1, seller_name="Seller",
                    total_nodes=16, nodes_purchased=2, node_price=amount / 2,
                    total_spent=amount, outcome=outcome,
                    profit_loss=-amount if outcome == "lost" else None,
                    created_at=now,
                ))
        self.db.add_all(self.characters + self.offers + self.bids)
        self.db.commit()
        # Exercise real ownership/filter SQL while keeping unrelated serialization out of this fixture.
        for name, replacement in [
            ("offer_options", lambda: ()), ("participation_options", lambda: ()),
            ("serialize_offer", lambda row: {"id": row.id, "character_id": row.seller_character_id}),
            ("serialize_participation", lambda row: {"id": row.id, "character_id": row.character_id}),
            ("offer_calculations", lambda row: {
                "financials": {key: float(row.total_offer_price) for key in
                    ["payout_after_fee", "hypercore_cost", "net_proceeds", "profit"]},
                "seeded_scenario": {
                    "capital_tied_up": float(row.total_offer_price),
                    "seller_node_spend": float(row.total_offer_price) * .375,
                    "cash_result_if_external_wins": float(row.total_offer_price) * .625,
                },
                "progress": {"hours_to_first_organic_node": row.seller_character_id},
            }),
        ]:
            mocked = patch.object(hypernet, name, replacement)
            mocked.start()
            self.addCleanup(mocked.stop)

    def summary(self, character_id=None):
        return hypernet.hypernet_summary(user=self.user, db=self.db, character_id=character_id)

    def test_all_characters_and_individual_seller_and_buyer_metrics(self):
        all_stats = self.summary()
        self.assertEqual(all_stats["active_offers"], 2)
        self.assertEqual(all_stats["gross_offer_value"], 300)
        self.assertEqual(all_stats["lifetime_profit"], 300)
        self.assertEqual(all_stats["participation"]["active_spend"], 300)
        self.assertEqual(all_stats["participation"]["resolved_bids"], 2)
        for character, amount in [(1, 100), (2, 200)]:
            stats = self.summary(character)
            self.assertEqual(stats["active_offers"], 1)
            self.assertEqual(stats["gross_offer_value"], amount)
            self.assertEqual(stats["lifetime_profit"], amount)
            self.assertEqual(stats["average_hours_to_first_node"], character)
            self.assertEqual(stats["next_expiring_offer"]["character_id"], character)
            self.assertEqual(stats["participation"]["active_spend"], amount)
            self.assertEqual(stats["participation"]["realized_profit_loss"], -amount)
            self.assertEqual(stats["participation"]["resolved_bids"], 1)
            self.assertEqual(stats["combined_lifetime_result"], 0)
            self.assertEqual(stats["active_seller_node_spend"], amount * .375)
            self.assertEqual(stats["active_external_winner_result"], amount * .625)

    def test_empty_and_foreign_character_cannot_expose_another_users_records(self):
        for character in [3, 4, 999]:
            stats = self.summary(character)
            self.assertEqual(stats["active_offers"], 0)
            self.assertEqual(stats["lifetime_profit"], 0)
            self.assertEqual(stats["participation"]["active_spend"], 0)
            self.assertIsNone(stats["next_expiring_offer"])
            self.assertEqual(stats["active_seller_node_spend"], 0)
            self.assertEqual(stats["active_external_winner_result"], 0)
            self.assertEqual(hypernet.list_hypernet_offers(
                seller_character_id=character, limit=100, user=self.user, db=self.db), [])
            self.assertEqual(hypernet.list_hypernet_participations(
                character_id=character, limit=100, user=self.user, db=self.db), [])

    def test_lists_combine_character_with_existing_status_filters(self):
        offers = hypernet.list_hypernet_offers(
            status="active", seller_character_id=2, limit=100, user=self.user, db=self.db)
        bids = hypernet.list_hypernet_participations(
            outcome="expired", character_id=2, limit=100, user=self.user, db=self.db)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["character_id"], 2)
        self.assertEqual(len(bids), 1)
        self.assertEqual(bids[0]["character_id"], 2)

    def test_active_risk_matches_vindicator_and_injector_costs(self):
        for row, price, cost, cores, core_price in [
            (self.offers[0], 1430000000, 902100000, 152, 306100),
            (self.offers[2], 995000000, 739000000, 106, 304600),
        ]:
            row.total_offer_price = Decimal(price)
            row.acquisition_cost = Decimal(cost)
            row.hypercores_required = cores
            row.hypercore_unit_cost = Decimal(core_price)
        self.db.flush()

        def calculate(row):
            financials = offer_financials(
                total_offer_price=row.total_offer_price, total_nodes=row.total_nodes,
                hypercores_required=row.hypercores_required, hypercore_unit_cost=row.hypercore_unit_cost,
                acquisition_cost=row.acquisition_cost,
            )
            scenario = seeded_node_scenario(
                total_nodes=row.total_nodes, seller_owned_nodes=row.seller_owned_nodes,
                node_price=financials["node_price"], acquisition_cost=row.acquisition_cost,
                hypercore_cost=financials["hypercore_cost"], payout_after_fee=financials["payout_after_fee"],
            )
            return {"financials": financials, "seeded_scenario": scenario,
                    "progress": {"hours_to_first_organic_node": None}}

        with patch.object(hypernet, "offer_calculations", calculate):
            result = self.summary()
            self.assertEqual(result["estimated_profit"], Decimal("583835200"))
            self.assertEqual(result["active_seller_node_spend"], Decimal("909375000"))
            self.assertEqual(result["active_external_winner_result"], Decimal("-325539800"))
            self.assertEqual(self.summary(1)["active_external_winner_result"], Decimal("-126377200"))
            self.assertEqual(self.summary(2)["active_external_winner_result"], Decimal("-199162600"))
            # With no self-purchases, the outside-winner result equals the unseeded profit.
            self.offers[0].seller_owned_nodes = 0
            self.offers[2].seller_owned_nodes = 0
            self.db.flush()
            unseeded = self.summary()
            self.assertEqual(unseeded["active_seller_node_spend"], 0)
            self.assertEqual(unseeded["active_external_winner_result"], unseeded["estimated_profit"])

    def test_filter_choices_include_history_without_active_esi_tokens(self):
        # Character 2 has been unlinked/transferred; the user's recorded history remains accessible.
        self.characters[1].owner_user_id = None
        self.db.commit()
        meta = hypernet.hypernet_meta(user=self.user, db=self.db)
        self.assertEqual([row["id"] for row in meta["filter_characters"]], [1, 2, 4])
        self.assertEqual(meta["seller_characters"], [])


if __name__ == "__main__":
    unittest.main()
