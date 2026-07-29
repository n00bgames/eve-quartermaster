from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.api.esi import asset_location_types
from app.models.enums import OwnerKind
from app.services.corporation_metadata import asset_flag_name, asset_location_name


class CorporationMetadataTests(unittest.TestCase):
    def test_external_item_location_is_treated_as_structure(self) -> None:
        payload = [
            {
                "item_id": 1_054_340_166_687,
                "location_id": 1_037_082_250_829,
                "location_type": "item",
                "type_id": 27,
            },
            {
                "item_id": 1_040_406_503_319,
                "location_id": 1_054_340_166_687,
                "location_type": "item",
                "type_id": 34,
            },
        ]

        self.assertEqual(
            asset_location_types(payload),
            {1_037_082_250_829: "structure"},
        )

    def test_nested_item_locations_are_not_misclassified_as_structures(self) -> None:
        payload = [
            {
                "item_id": 1_021_337_002_376,
                "location_id": 60_006_328,
                "location_type": "station",
                "type_id": 1_735,
            },
            {
                "item_id": 1_020_949_132_686,
                "location_id": 1_021_337_002_376,
                "location_type": "item",
                "type_id": 34,
            },
        ]

        self.assertEqual(
            asset_location_types(payload),
            {60_006_328: "station"},
        )

    def test_corporation_hangar_flag_uses_configured_division_name(self) -> None:
        asset = SimpleNamespace(
            location_flag="CorpSAG2",
            ownership_entity=SimpleNamespace(
                owner_kind=OwnerKind.CORPORATION,
                corporation_id=17,
            ),
        )

        self.assertEqual(
            asset_flag_name(asset, {(17, "CorpSAG2"): "Minerals and Melt"}),
            "Minerals and Melt",
        )

    def test_non_corporation_asset_keeps_raw_flag(self) -> None:
        asset = SimpleNamespace(
            location_flag="Cargo",
            ownership_entity=SimpleNamespace(
                owner_kind=OwnerKind.CHARACTER,
                corporation_id=None,
            ),
        )

        self.assertEqual(asset_flag_name(asset, {}), "Cargo")


    def test_unknown_corporation_division_keeps_raw_flag(self) -> None:
        asset = SimpleNamespace(
            location_flag="CorpSAG7",
            ownership_entity=SimpleNamespace(
                owner_kind=OwnerKind.CORPORATION,
                corporation_id=17,
            ),
        )

        self.assertEqual(asset_flag_name(asset, {}), "CorpSAG7")

    def test_nested_asset_uses_parent_station_and_container_type(self) -> None:
        office = SimpleNamespace(
            id=31,
            eve_item_id=1_054_340_166_687,
            item_type=SimpleNamespace(name="Office"),
            location=SimpleNamespace(name="Hahda VII - Moon 1 - Factory"),
            parent_asset=None,
        )
        asset = SimpleNamespace(
            location=SimpleNamespace(
                name="Location 1054340166687",
                eve_location_id=1_054_340_166_687,
            ),
            parent_asset=office,
        )

        self.assertEqual(
            asset_location_name(asset),
            "Hahda VII - Moon 1 - Factory - Office",
        )

    def test_unresolved_parent_is_explicitly_labeled(self) -> None:
        container = SimpleNamespace(
            id=41,
            eve_item_id=1_021_337_002_376,
            item_type=SimpleNamespace(name="Station Container"),
            location=None,
            parent_asset=None,
        )
        asset = SimpleNamespace(location=None, parent_asset=container)

        self.assertEqual(
            asset_location_name(asset),
            "Unresolved item 1021337002376 - Station Container",
        )


if __name__ == "__main__":
    unittest.main()
