import importlib.util
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.api import hypernet
from app.models import Base, EveType, HyperNetOffer, HyperNetOfferSnapshot, HyperNetParticipant, Location
from app.schemas.hypernet import HyperNetNodeMapUpdate, HyperNetOfferPatch
from app.services.hypernet_nodes import node_position_summary


class NodeMapTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[model.__table__ for model in
            (EveType, HyperNetOffer, HyperNetOfferSnapshot, HyperNetParticipant, Location)])
        self.db = Session(self.engine, expire_on_commit=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        now = datetime.now(timezone.utc)
        self.offer = HyperNetOffer(owner_user_id=1, seller_character_id=1, type_id=1,
            status="active", created_offer_at=now, expires_at=now + timedelta(days=3),
            total_nodes=16, nodes_sold=8, seller_owned_nodes=8, total_offer_price=100,
            final_profit=None, winner=None)
        self.db.add(self.offer)
        self.db.commit()
        self.user = SimpleNamespace(id=1)
        self.audit = Mock()
        for name, value in [("offer_options", lambda: ()), ("record_audit_event", self.audit),
                            ("serialize_offer", lambda row, **kwargs: {"node_map": row.node_map, "status": row.status})]:
            mocked = patch.object(hypernet, name, value)
            mocked.start()
            self.addCleanup(mocked.stop)

    def save(self, positions, winner=None, columns=4):
        return hypernet.update_hypernet_node_map(self.offer.id,
            HyperNetNodeMapUpdate(seeded_positions=positions, winning_position=winner, columns=columns), self.user, self.db)

    def test_persists_sorted_positions_without_altering_financials_or_progress(self):
        self.assertIsNone(self.offer.node_map)
        result = self.save([8, 2, 1], 8)
        self.db.expire(self.offer, ["node_map"])
        self.assertEqual(self.offer.node_map, {"columns": 4, "seeded_positions": [1, 2, 8], "winning_position": 8})
        self.assertEqual(result["node_map"], self.offer.node_map)
        self.assertEqual(self.offer.status, "active")
        self.assertEqual(self.offer.nodes_sold, 8)
        self.assertEqual(self.offer.seller_owned_nodes, 8)
        self.assertIsNone(self.offer.final_profit)
        self.assertIsNone(self.offer.winner)
        self.assertEqual(self.audit.call_args.kwargs["event_kind"], "hypernet_node_map_edited")
        self.assertIn("Before: None", self.audit.call_args.kwargs["body"])

    def test_ended_maps_can_be_corrected_and_cleared(self):
        for status in ["completed", "expired", "cancelled", "invalid"]:
            self.offer.status = status
            self.offer.winner = "external"
            self.offer.final_profit = 42
            self.db.commit()
            self.save([1, 3], 16, 8)
            self.save([], None)
            self.assertEqual(self.offer.node_map["seeded_positions"], [])
            self.assertIsNone(self.offer.node_map["winning_position"])
            self.assertEqual(self.offer.status, status)
            self.assertEqual(self.offer.winner, "external")
            self.assertEqual(self.offer.final_profit, 42)

    def test_out_of_offer_bounds_rejected_before_mutation(self):
        self.save([1], 2)
        for positions, winner in [([17], 1), ([1], 17)]:
            with self.assertRaises(HTTPException) as caught:
                self.save(positions, winner)
            self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.offer.node_map["seeded_positions"], [1])
        self.assertEqual(self.offer.node_map["winning_position"], 2)

    def test_other_user_cannot_read_or_write_map(self):
        with self.assertRaises(HTTPException) as caught:
            hypernet.update_hypernet_node_map(self.offer.id,
                HyperNetNodeMapUpdate(seeded_positions=[1]), SimpleNamespace(id=2), self.db)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertIsNone(self.offer.node_map)
        self.audit.assert_not_called()

    def test_resize_cannot_drop_a_recorded_position(self):
        self.save([16], None)
        with self.assertRaises(HTTPException):
            hypernet.patch_hypernet_offer(self.offer.id, HyperNetOfferPatch(total_nodes=8), self.user, self.db)
        self.save([], 16)
        with self.assertRaises(HTTPException):
            hypernet.patch_hypernet_offer(self.offer.id, HyperNetOfferPatch(total_nodes=8), self.user, self.db)
        self.assertEqual(self.offer.total_nodes, 16)

    def test_512_boundary_and_schema(self):
        self.offer.total_nodes = 512
        self.db.commit()
        self.save(list(range(1, 257)), 512, 16)
        self.assertEqual(len(self.offer.node_map["seeded_positions"]), 256)
        for body in [dict(seeded_positions=[1, 1]), dict(seeded_positions=[0]), dict(seeded_positions=[513]),
                     dict(seeded_positions=[1.5]), dict(seeded_positions=[True]), dict(seeded_positions=["2"]),
                     dict(seeded_positions=None), dict(seeded_positions=[], winning_position=0),
                     dict(seeded_positions=[], columns=3), dict(seeded_positions=[], unexpected=1)]:
            with self.assertRaises(ValidationError):
                HyperNetNodeMapUpdate(**body)


def sample(total=16, columns=4, positions=(1, 2, 3, 4), winning=1, seeded=4, winner="seller", status="completed"):
    return SimpleNamespace(total_nodes=total, seller_owned_nodes=seeded, winner=winner, status=status,
        node_map={"columns": columns, "seeded_positions": list(positions), "winning_position": winning})


class NodeSummaryTests(unittest.TestCase):
    def test_win_and_seed_denominators_and_count_based_expectation(self):
        offers = [sample(), sample(positions=tuple(range(1, 9)), winning=16, seeded=8, winner="external")]
        group = node_position_summary(offers)["groups"][0]
        self.assertEqual(group["draws"], 2)
        self.assertEqual(group["complete_seed_maps"], 2)
        self.assertEqual(group["seeded_wins"], 1)
        self.assertEqual(group["expected_seeded_wins"], .75)
        self.assertEqual(group["positions"][0], {"position": 1, "wins": 1, "seeded": 2, "seeded_wins": 1})
        self.assertEqual(group["positions"][15]["wins"], 1)
        self.assertEqual(sum(row["wins"] for row in group["positions"]), group["draws"])

    def test_incomplete_conflicting_and_unresolved_records_are_separate(self):
        missing = sample(); missing.node_map = None
        data = node_position_summary([sample(seeded=8), sample(winner="external"),
            sample(status="active"), sample(status="expired"), sample(winning=None), missing])
        group = data["groups"][0]
        self.assertEqual(group["draws"], 2)
        self.assertEqual(group["complete_seed_maps"], 0)
        self.assertEqual(group["incomplete_seed_maps"], 1)
        self.assertEqual(group["outcome_conflicts"], 1)
        self.assertEqual(data["excluded"], {"not_completed": 2, "missing_winner": 1, "missing_map": 1})

    def test_layouts_do_not_mix_and_zero_seeding_is_valid(self):
        result = node_position_summary([sample(), sample(columns=8), sample(total=8),
            sample(total=512, columns=16, positions=(), seeded=0, winning=512, winner="external")])
        self.assertEqual(len(result["groups"]), 4)
        last = result["groups"][-1]
        self.assertEqual(last["complete_seed_maps"], 1)
        self.assertEqual(last["expected_seeded_wins"], 0)
        self.assertEqual(last["positions"][-1]["wins"], 1)
        self.assertEqual(node_position_summary([])["groups"], [])


class NodeMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_old_offers_as_untracked_and_downgrade(self):
        path = Path(__file__).parents[1] / "alembic/versions/0082_hypernet_node_positions.py"
        spec = importlib.util.spec_from_file_location("node_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine("sqlite+pysqlite:///:memory:")
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE hypernet_offers (id INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO hypernet_offers (id) VALUES (1)"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                self.assertIsNone(connection.execute(text("SELECT node_map FROM hypernet_offers WHERE id=1")).scalar())
                migration.downgrade()
            self.assertEqual([column["name"] for column in inspect(connection).get_columns("hypernet_offers")], ["id"])
