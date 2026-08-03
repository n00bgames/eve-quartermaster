from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.models import SnapshotRun
from app.services.analytics import create_snapshot, recent_automatic_snapshot


class AnalyticsSnapshotOptimizationTests(unittest.TestCase):
    def test_character_skill_sync_only_snapshots_requested_character(self) -> None:
        db = MagicMock()
        with (
            patch("app.services.analytics.recent_automatic_snapshot", return_value=None),
            patch("app.services.analytics.snapshot_character_skills") as snapshot_skills,
            patch("app.services.analytics.snapshot_character_assets") as snapshot_assets,
            patch("app.services.analytics.snapshot_corporations") as snapshot_corporations,
            patch("app.services.analytics.snapshot_blueprints") as snapshot_blueprints,
        ):
            run = create_snapshot(
                db,
                scope_type="character",
                scope_id=42,
                source="character_skills",
            )

        snapshot_skills.assert_called_once_with(db, run, {42})
        snapshot_assets.assert_not_called()
        snapshot_corporations.assert_not_called()
        snapshot_blueprints.assert_not_called()
        self.assertEqual(run.schema_version, 2)
        self.assertEqual(run.status, "success")

    def test_character_asset_sync_only_snapshots_requested_characters_assets(self) -> None:
        db = MagicMock()
        with (
            patch("app.services.analytics.recent_automatic_snapshot", return_value=None),
            patch("app.services.analytics.snapshot_character_skills") as snapshot_skills,
            patch("app.services.analytics.snapshot_character_assets") as snapshot_assets,
            patch("app.services.analytics.snapshot_corporations") as snapshot_corporations,
            patch("app.services.analytics.snapshot_blueprints") as snapshot_blueprints,
        ):
            run = create_snapshot(
                db,
                scope_type="character",
                scope_id=7,
                source="character_assets",
            )

        snapshot_assets.assert_called_once_with(db, run, 7)
        snapshot_skills.assert_not_called()
        snapshot_corporations.assert_not_called()
        snapshot_blueprints.assert_not_called()

    def test_corporation_blueprint_sync_keeps_detail_but_limits_corporation_snapshot(self) -> None:
        db = MagicMock()
        with (
            patch("app.services.analytics.recent_automatic_snapshot", return_value=None),
            patch("app.services.analytics.snapshot_character_skills") as snapshot_skills,
            patch("app.services.analytics.snapshot_character_assets") as snapshot_assets,
            patch("app.services.analytics.snapshot_corporations") as snapshot_corporations,
            patch("app.services.analytics.snapshot_blueprints") as snapshot_blueprints,
        ):
            run = create_snapshot(
                db,
                scope_type="corporation",
                scope_id=99,
                source="corporation_blueprints",
            )

        snapshot_corporations.assert_called_once_with(db, run, {99})
        snapshot_blueprints.assert_called_once_with(db, run)
        snapshot_skills.assert_not_called()
        snapshot_assets.assert_not_called()

    def test_recent_automatic_snapshot_is_reused_without_writing(self) -> None:
        db = MagicMock()
        existing = SnapshotRun(
            id=123,
            scope_type="character",
            scope_id=7,
            source="character_assets",
            status="success",
            schema_version=2,
        )
        with (
            patch("app.services.analytics.recent_automatic_snapshot", return_value=existing),
            patch("app.services.analytics.snapshot_character_assets") as snapshot_assets,
        ):
            result = create_snapshot(
                db,
                scope_type="character",
                scope_id=7,
                source="character_assets",
            )

        self.assertIs(result, existing)
        db.add.assert_not_called()
        db.flush.assert_not_called()
        snapshot_assets.assert_not_called()

    def test_recent_snapshot_query_uses_the_coalescing_window(self) -> None:
        db = MagicMock()
        expected = SnapshotRun(id=5, schema_version=2)
        db.scalar.return_value = expected
        now = datetime.now(timezone.utc)

        result = recent_automatic_snapshot(
            db,
            scope_type="corporation",
            scope_id=17,
            source="corporation_wallets",
            now=now,
        )

        self.assertIs(result, expected)
        statement = db.scalar.call_args.args[0]
        rendered = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("snapshot_runs.started_at >=", rendered)
        self.assertIn(str((now - timedelta(minutes=60)).year), rendered)
        self.assertIn("snapshot_runs.schema_version >= 2", rendered)


if __name__ == "__main__":
    unittest.main()
