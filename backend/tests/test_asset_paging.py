from unittest.mock import patch
from sqlalchemy import event, select
from app.api.quartermaster import list_assets_page
from app.models import Asset, EveCharacter, OwnershipEntity, User
from app.models.enums import OwnerKind
from app.services.asset_visibility import visible_asset_rows
from tests.test_inventory_exports import InventoryExportTests


class AssetPagingTests(InventoryExportTests):
    def page(self, **changes):
        params = dict(all_records=False, page=1, page_size=25, sort_key="item", sort_direction="asc",
                      owner_kind=None, category="all", subtype=None, filter_key=None,
                      filter_value=None, filter_mode="exact", current_user=self.user, db=self.db)
        return list_assets_page(**{**params, **changes})

    def test_filter_in_sql_does_not_hydrate_nonmatching_inventory(self):
        self.db.add_all([Asset(ownership_entity_id=self.owner.id, type_id=62001, quantity=5) for _ in range(100)])
        self.db.commit()
        self.db.expire_all()
        loaded = []
        def track(_session, obj):
            if isinstance(obj, Asset): loaded.append(obj.id)
        event.listen(self.db, "loaded_as_persistent", track)
        result = self.page(filter_key="item", filter_value="does not exist", filter_mode="contains")
        self.assertEqual(result["total"], 0)
        self.assertEqual(loaded, [])

    def test_page_is_bounded_but_totals_cover_full_matching_set(self):
        self.db.add_all([Asset(ownership_entity_id=self.owner.id, type_id=62001, quantity=5) for _ in range(100)])
        self.db.commit()
        result = self.page(page=2)
        self.assertEqual(len(result["items"]), 25)
        self.assertEqual(result["total"], 102)
        self.assertEqual(result["total_quantity"], 503)
        self.assertEqual(result["type_count"], 1)

    def test_all_records_preserves_visibility_and_totals(self):
        other = User(email="hidden@example.test", display_name="Hidden", role="member")
        char = EveCharacter(character_id=90000002, name="Hidden", owner_user=other, public_assets_visible=False)
        owner = OwnershipEntity(owner_kind=OwnerKind.CHARACTER, character=char, display_name="Hidden")
        self.db.add(owner); self.db.flush()
        self.db.add(Asset(ownership_entity_id=owner.id, type_id=62001, quantity=999))
        self.db.commit()
        result = self.page(all_records=True)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["total_quantity"], 3)
        self.assertTrue(all(a["owner_name"] != "Hidden" for a in result["items"]))
        char.public_assets_visible = True; self.db.commit()
        self.assertEqual(self.page(all_records=True)["total_quantity"], 1002)
        char.sync_opt_out = True; self.db.commit()
        self.assertEqual(self.page(all_records=True)["total_quantity"], 3)
        self.user.role = "officer"; self.db.commit()
        self.assertEqual(self.page(all_records=True)["total_quantity"], 1002)

    def test_literal_contains_category_and_computed_location_parity(self):
        self.assertEqual(self.page(filter_key="item", filter_value="%", filter_mode="contains")["total"], 0)
        self.assertEqual(self.page(filter_key="item", filter_value="strategy", filter_mode="contains", category="ships", subtype="Cruiser")["total"], 2)
        self.assertEqual(self.page(category="drones")["total"], 0)
        self.assertEqual(self.page(filter_key="location", filter_value="Home", filter_mode="contains", sort_key="location")["total_quantity"], 3)

    def test_combined_role_resolution_is_constant_not_per_asset(self):
        with patch("app.services.asset_visibility.role_rank", return_value=1) as rank:
            visible_asset_rows(self.user, self.db)
            self.assertEqual(rank.call_count, 1)
