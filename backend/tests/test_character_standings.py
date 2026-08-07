from __future__ import annotations

from datetime import datetime, timezone
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, CharacterStanding, EveCharacter
from app.services.standings import effective_npc_standing, upsert_character_standings


class CharacterStandingPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[EveCharacter.__table__, CharacterStanding.__table__],
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_sync_upserts_names_and_removes_stale_sources(self) -> None:
        first_sync = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        second_sync = datetime(2026, 7, 27, 13, 0, tzinfo=timezone.utc)
        with Session(self.engine) as db:
            character = EveCharacter(character_id=90000001, name="Example Pilot")
            db.add(character)
            db.flush()

            first = upsert_character_standings(
                db,
                character,
                [
                    {"from_id": 500001, "from_type": "faction", "standing": 4.25},
                    {"from_id": 1000001, "from_type": "npc_corp", "standing": -1.5},
                ],
                {500001: "Example Faction", 1000001: "Example Corporation"},
                synced_at=first_sync,
            )
            db.commit()
            self.assertEqual(first, {"created": 2, "updated": 0, "removed": 0, "total": 2})

            second = upsert_character_standings(
                db,
                character,
                [
                    {"from_id": 500001, "from_type": "faction", "standing": 5.0},
                    {"from_id": 3000001, "from_type": "agent", "standing": 2.1},
                ],
                {500001: "Renamed Faction", 3000001: "Example Agent"},
                synced_at=second_sync,
            )
            db.commit()

            saved = db.scalars(
                select(CharacterStanding).order_by(CharacterStanding.source_type)
            ).all()
            self.assertEqual(second, {"created": 1, "updated": 1, "removed": 1, "total": 2})
            self.assertEqual([row.source_type for row in saved], ["agent", "faction"])
            self.assertEqual(saved[1].source_name, "Renamed Faction")
            self.assertEqual(float(saved[1].standing), 5.0)
            self.assertEqual(
                character.standings_synced_at.replace(tzinfo=timezone.utc),
                second_sync,
            )

    def test_invalid_and_duplicate_rows_are_ignored(self) -> None:
        with Session(self.engine) as db:
            character = EveCharacter(character_id=90000002, name="Another Pilot")
            db.add(character)
            db.flush()
            result = upsert_character_standings(
                db,
                character,
                [
                    {"from_id": 500002, "from_type": "faction", "standing": 1.0},
                    {"from_id": 500002, "from_type": "faction", "standing": 9.0},
                    {"from_id": 0, "from_type": "agent", "standing": 2.0},
                    {"from_id": 44, "from_type": "player", "standing": 3.0},
                ],
                {},
            )
            db.commit()
            self.assertEqual(result["total"], 1)
            self.assertEqual(db.query(CharacterStanding).count(), 1)



class CharacterStandingModifierTests(unittest.TestCase):
    def test_connections_modifies_positive_non_pirate_standing(self) -> None:
        modified, skill, level = effective_npc_standing(
            5.0,
            "faction",
            500001,
            {"connections": 3},
        )
        self.assertAlmostEqual(modified, 5.6)
        self.assertEqual((skill, level), ("Connections", 3))

    def test_diplomacy_modifies_negative_standing(self) -> None:
        modified, skill, level = effective_npc_standing(
            -5.0,
            "npc_corp",
            1000002,
            {"diplomacy": 4},
        )
        self.assertAlmostEqual(modified, -2.6)
        self.assertEqual((skill, level), ("Diplomacy", 4))

    def test_criminal_connections_uses_sde_faction_affiliation(self) -> None:
        modified, skill, level = effective_npc_standing(
            2.0,
            "agent",
            3000001,
            {"connections": 5, "criminal_connections": 5},
            ({1000001: 500010}, {3000001: 1000001}),
        )
        self.assertAlmostEqual(modified, 3.6)
        self.assertEqual((skill, level), ("Criminal Connections", 5))

    def test_social_does_not_change_current_standing(self) -> None:
        modified, skill, level = effective_npc_standing(
            0.0,
            "faction",
            500001,
            {"social": 5, "connections": 5, "diplomacy": 5},
        )
        self.assertEqual(modified, 0.0)
        self.assertEqual((skill, level), (None, 0))
if __name__ == "__main__":
    unittest.main()
