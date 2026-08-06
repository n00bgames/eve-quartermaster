from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.blueprint_hover import blueprint_active_use, research_use_payload


class BlueprintHoverTests(unittest.TestCase):
    def test_active_research_use_is_concise_and_complete(self) -> None:
        project = SimpleNamespace(
            status="active",
            activity_id=4,
            job_id=991,
            runs=3,
            facility_name="Example Engineering Complex",
            character=SimpleNamespace(name="Example Pilot"),
            installer_name=None,
            start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 8, 2, tzinfo=timezone.utc),
        )
        payload = research_use_payload(project)
        self.assertTrue(payload["active"])
        self.assertEqual(payload["activity"], "Material Efficiency")
        self.assertEqual(payload["facility"], "Example Engineering Complex")
        self.assertEqual(payload["installer"], "Example Pilot")

    def test_blueprint_use_is_matched_by_immutable_item_id(self) -> None:
        blueprint = SimpleNamespace(asset=SimpleNamespace(eve_item_id=12345))
        use = {12345: {"active": True, "activity": "Copying"}}
        self.assertEqual(blueprint_active_use(blueprint, use), use[12345])

    def test_blueprint_without_esi_item_id_is_available(self) -> None:
        blueprint = SimpleNamespace(asset=None)
        self.assertIsNone(blueprint_active_use(blueprint, {}))


if __name__ == "__main__":
    unittest.main()
