import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.hypernet import hypernet_type_search
from app.models import Base, EveCategory, EveGroup, EveType


class HyperNetTypeSearchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[
            EveCategory.__table__, EveGroup.__table__, EveType.__table__,
        ])
        self.db = Session(self.engine)
        self.db.add(EveCategory(category_id=6, name="Ship"))
        self.db.add(EveGroup(group_id=902, category_id=6, name="Jump Freighter"))
        self.db.add(EveType(type_id=28844, name="Rhea", group_id=902, published=True))
        self.db.add(EveType(type_id=28845, name="Rhea Blueprint", published=True))
        self.db.add(EveType(type_id=90000, name="Rhea Internal Test", published=False))
        # These substring matches sort before Rhea and previously filled the cap.
        self.db.add_all([
            EveType(type_id=1000 + i, name=f"Capital Warhead Test {i:02}", published=True)
            for i in range(20)
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_exact_ship_survives_result_limit_and_keeps_metadata(self):
        rows = hypernet_type_search(q="  rHeA  ", limit=12, _=None, db=self.db)
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0], {
            "type_id": 28844, "name": "Rhea", "group": "Jump Freighter", "category": "Ship",
        })
        self.assertEqual(rows[1]["name"], "Rhea Blueprint")
        self.assertNotIn(90000, [row["type_id"] for row in rows])

    def test_prefix_ship_survives_single_result_limit(self):
        rows = hypernet_type_search(q="rhe", limit=1, _=None, db=self.db)
        self.assertEqual([row["name"] for row in rows], ["Rhea"])

    def test_substring_search_still_finds_nonprefix_matches(self):
        rows = hypernet_type_search(q="arhead", limit=30, _=None, db=self.db)
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["name"], "Capital Warhead Test 00")

    def test_unknown_name_returns_empty_list(self):
        self.assertEqual(hypernet_type_search(q="not an eve item", limit=12, _=None, db=self.db), [])


if __name__ == "__main__":
    unittest.main()
