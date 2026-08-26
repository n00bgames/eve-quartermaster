from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.api.bounty_analytics import can_view_all_pilots
from app.services.bounty_analytics import build_bounty_ticks, leaderboard, summarize_ticks, timeline


def journal(
    reference_id: int,
    *,
    character_id: int = 1,
    character_eve_id: int = 90000001,
    character_name: str = "Pilot One",
    occurred_at: str = "2026-08-18T04:30:29+00:00",
    amount: str = "950",
    tax: str | None = "50",
    tax_receiver_id: int | None = 98000001,
    corporation_eve_id_at_import: int | None = 98000001,
    corporation_name_at_import: str | None = "Example Corporation",
):
    return SimpleNamespace(
        id=reference_id,
        character_id=character_id,
        character=SimpleNamespace(id=character_id, character_id=character_eve_id, name=character_name),
        reference_id=reference_id,
        occurred_at=datetime.fromisoformat(occurred_at),
        reference_type="bounty_prizes",
        amount=Decimal(amount),
        tax=Decimal(tax) if tax is not None else None,
        tax_receiver_id=tax_receiver_id,
        corporation_eve_id_at_import=corporation_eve_id_at_import,
        corporation_name_at_import=corporation_name_at_import,
        context_id=30000001,
        description="Pilot One got bounty prizes for killing pirates",
        reason=None,
    )


class BountyAnalyticsTests(unittest.TestCase):
    def test_host_and_admin_roles_can_view_all_enrolled_pilots(self) -> None:
        for role in ("host", "admin"):
            with self.subTest(role=role), patch("app.api.bounty_analytics.base_role_for", return_value=role):
                self.assertTrue(can_view_all_pilots(SimpleNamespace(), SimpleNamespace(role=role)))

    def test_non_admin_roles_remain_account_scoped(self) -> None:
        for role in ("director", "officer", "member", "view_only"):
            with self.subTest(role=role), patch("app.api.bounty_analytics.base_role_for", return_value=role):
                self.assertFalse(can_view_all_pilots(SimpleNamespace(), SimpleNamespace(role=role)))

    def test_tick_groups_only_exact_pilot_and_authoritative_timestamp(self) -> None:
        rows = [
            journal(101, amount="950", tax="50"),
            journal(102, amount="1900", tax="100"),
            journal(103, occurred_at="2026-08-18T04:30:30+00:00", amount="475", tax="25"),
        ]
        ticks = build_bounty_ticks(rows, tax_receiver_names={98000001: "Example Corporation"})
        self.assertEqual(len(ticks), 2)
        grouped = next(row for row in ticks if row["source_entry_count"] == 2)
        self.assertEqual(grouped["reference_ids"], [101, 102])
        self.assertEqual(grouped["net_isk"], Decimal("2850"))
        self.assertEqual(grouped["corporate_tax_isk"], Decimal("150"))
        self.assertEqual(grouped["gross_isk"], Decimal("3000"))

    def test_authoritative_tax_reconciliation(self) -> None:
        tick = build_bounty_ticks([journal(101, amount="950", tax="50")])[0]
        self.assertEqual(tick["gross_isk"] - tick["corporate_tax_isk"], tick["net_isk"])
        self.assertEqual(tick["effective_tax_rate"], Decimal("5"))

    def test_missing_tax_keeps_net_and_marks_tax_and_gross_unknown(self) -> None:
        tick = build_bounty_ticks([journal(101, amount="950", tax=None, tax_receiver_id=None)])[0]
        self.assertEqual(tick["net_isk"], Decimal("950"))
        self.assertIsNone(tick["corporate_tax_isk"])
        self.assertIsNone(tick["gross_isk"])
        self.assertEqual(tick["tax_status"], "unknown")
        summary = summarize_ticks([tick])
        self.assertFalse(summary["tax_coverage_complete"])
        self.assertIsNone(summary["corporate_tax_isk"])
        self.assertIsNone(summary["effective_tax_rate"])
        self.assertEqual(summary["known_corporate_tax_isk"], Decimal("0"))

    def test_leaderboard_is_traceable_to_reference_ids(self) -> None:
        ticks = build_bounty_ticks([
            journal(101, amount="950", tax="50"),
            journal(102, occurred_at="2026-08-18T05:00:00+00:00", amount="1900", tax="100"),
        ])
        rows = leaderboard(ticks)
        self.assertEqual(rows[0]["net_isk"], Decimal("2850"))
        self.assertEqual(rows[0]["reference_ids"], [102, 101])
        self.assertEqual(sum(tick["net_isk"] for tick in ticks if tick["tick_id"] in rows[0]["tick_ids"]), rows[0]["net_isk"])

    def test_mixed_tax_coverage_does_not_publish_partial_effective_rate(self) -> None:
        ticks = build_bounty_ticks([
            journal(101, amount="950", tax="50"),
            journal(102, occurred_at="2026-08-18T05:00:00+00:00", amount="1900", tax=None, tax_receiver_id=None),
        ])
        summary = summarize_ticks(ticks)
        self.assertFalse(summary["tax_coverage_complete"])
        self.assertEqual(summary["known_corporate_tax_isk"], Decimal("50"))
        self.assertIsNone(summary["corporate_tax_isk"])
        self.assertIsNone(summary["gross_isk"])
        self.assertIsNone(summary["effective_tax_rate"])

    def test_daily_timeline_uses_reporting_timezone_but_returns_utc_buckets(self) -> None:
        ticks = build_bounty_ticks([
            journal(101, occurred_at="2026-08-18T04:30:00+00:00"),
            journal(102, occurred_at="2026-08-18T06:30:00+00:00"),
        ])
        points = timeline(ticks, "daily", "America/Chicago")
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["bucket_start"], datetime(2026, 8, 17, 5, tzinfo=timezone.utc))
        self.assertEqual(points[1]["bucket_start"], datetime(2026, 8, 18, 5, tzinfo=timezone.utc))

    def test_non_bounty_wallet_income_is_excluded(self) -> None:
        row = journal(101)
        row.reference_type = "agent_mission_reward"
        self.assertEqual(build_bounty_ticks([row]), [])


if __name__ == "__main__":
    unittest.main()
