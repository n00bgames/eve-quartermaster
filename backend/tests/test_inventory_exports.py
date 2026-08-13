from __future__ import annotations

import csv
import io
import json
import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.quartermaster import export_assets
from app.models import Asset, Base, EveCategory, EveCharacter, EveGroup, EveType, Location, OwnershipEntity, User
from app.models.enums import OwnerKind


class InventoryExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__, EveCharacter.__table__, OwnershipEntity.__table__, EveCategory.__table__,
                EveGroup.__table__, EveType.__table__, Location.__table__, Asset.__table__,
            ],
        )
        self.db = Session(self.engine)
        self.user = User(email="exporter@example.test", display_name="Exporter", role="member")
        self.character = EveCharacter(character_id=90_000_001, name='Pilot, "Quoted"', owner_user=self.user)
        self.owner = OwnershipEntity(owner_kind=OwnerKind.CHARACTER, character=self.character, display_name=self.character.name)
        category = EveCategory(category_id=6, name="Ship")
        group = EveGroup(group_id=25, name="Cruiser", category=category)
        item_type = EveType(type_id=62_001, name="Strategy Cruiser", group=group, volume=101000, packaged_volume=10000, market_group_id=80, published=True)
        location = Location(name="Home, Structure", eve_location_id=1_000_000_000_012)
        self.db.add_all([self.user, self.character, self.owner, item_type, location])
        self.db.flush()
        self.db.add_all([
            Asset(
                ownership_entity_id=self.owner.id, eve_item_id=9_007_199_254_740_993, type_id=item_type.type_id,
                quantity=1, location_id=location.id, is_singleton=True, last_synced_at=datetime.now(timezone.utc),
            ),
            Asset(ownership_entity_id=self.owner.id, eve_item_id=8_002, type_id=item_type.type_id, quantity=2, location_id=location.id, is_singleton=False),
        ])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_asset_json_preserves_unsafe_ids_as_strings(self) -> None:
        result = export_assets({"format": "json", "scope": "all"}, current_user=self.user, db=self.db)
        payload = json.loads(result["content"])
        unsafe = next(row for row in payload["records"] if row["item_id"] == "9007199254740993")
        self.assertEqual(unsafe["location_id"], "1000000000012")
        self.assertEqual(unsafe["owner_id"], str(self.character.character_id))
        self.assertEqual(unsafe["packaged_or_assembled"], "assembled")
        self.assertEqual(unsafe["volume_each_m3"], 101000)
        self.assertNotIn("token", result["content"].lower())

    def test_asset_csv_exports_all_filtered_rows_with_correct_quoting(self) -> None:
        result = export_assets(
            {"format": "csv", "scope": "filtered", "filters": {"packaged_or_assembled": "packaged"}},
            current_user=self.user,
            db=self.db,
        )
        rows = list(csv.DictReader(io.StringIO(result["content"].lstrip("\ufeff"))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["owner_name"], 'Pilot, "Quoted"')
        self.assertEqual(rows[0]["location_name"], "Home, Structure")
        self.assertEqual(rows[0]["packaged_or_assembled"], "packaged")
        self.assertEqual(rows[0]["total_volume_m3"], "20000.0")

    def test_export_all_ignores_active_filters_and_hashes_sensitive_ids(self) -> None:
        result = export_assets(
            {
                "format": "json", "scope": "all", "filters": {"packaged_or_assembled": "packaged"},
                "privacy": {"hash_ids": True, "exclude_owner_names": True, "include_location_names": False},
                "location_aliases": {"1000000000012": "Home Industry"},
            },
            current_user=self.user,
            db=self.db,
        )
        rows = json.loads(result["content"])["records"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(str(row["item_id"]).startswith("sha256:") for row in rows))
        self.assertTrue(all(str(row["owner_id"]).startswith("sha256:") for row in rows))
        self.assertTrue(all(row["location_alias"] == "Home Industry" for row in rows))
        self.assertTrue(all(row["owner_name"] is None and row["location_name"] is None for row in rows))

    def test_export_never_includes_an_inaccessible_characters_assets(self) -> None:
        other_user = User(email="private@example.test", display_name="Private", role="member")
        other_character = EveCharacter(character_id=90_000_002, name="Private Pilot", owner_user=other_user, public_assets_visible=False)
        other_owner = OwnershipEntity(owner_kind=OwnerKind.CHARACTER, character=other_character, display_name=other_character.name)
        self.db.add_all([other_user, other_character, other_owner])
        self.db.flush()
        self.db.add(Asset(ownership_entity_id=other_owner.id, eve_item_id=8_003, type_id=62_001, quantity=99))
        self.db.commit()

        result = export_assets({"format": "json", "scope": "all"}, current_user=self.user, db=self.db)
        rows = json.loads(result["content"])["records"]

        self.assertEqual(len(rows), 2)
        self.assertNotIn("Private Pilot", result["content"])
        self.assertNotIn("8003", result["content"])


if __name__ == "__main__":
    unittest.main()
