from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, SrpRequest, SrpRequestEvent, User
from app.services.srp import authoritative_loss_value
from app.services.srp_analytics import build_analytics, detailed_csv, filtered_rows
from alembic.config import Config
from alembic.script import ScriptDirectory


def loss(user_id: int, when: datetime, *, value: str | None, doctrine: str = "Shield Line",
         status: str = "approved", disposition: str = "operational") -> SrpRequest:
    return SrpRequest(requesting_user_id=user_id, character_id=1, fitting_id=1, character_name_snapshot="Pilot",
        fitting_name_snapshot="Fit v1", ship_name_snapshot="Caracal", ship_group_name_snapshot="Cruiser",
        doctrine_name_snapshot=doctrine, operation_name_snapshot="Home Defense", loss_date=when.date(),
        loss_time=when.time(), loss_occurred_at=when, entered_timezone="UTC", status=status,
        record_disposition=disposition, valuation_status="estimated" if value else "pending",
        submission_estimated_loss_value=Decimal(value) if value else None,
        authoritative_loss_value=Decimal(value) if value else None, requested_reimbursement_amount=Decimal("50.00"))


class TestSrpAnalytics:
    def setup_method(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine); self.db = Session(self.engine)
        self.user = User(email="pilot@srp.test", display_name="Pilot", role="member")
        self.other = User(email="other@srp.test", display_name="Other", role="member")
        self.db.add_all([self.user, self.other]); self.db.flush()
        # SQLite does not enforce these FKs unless PRAGMA is enabled, allowing this focused aggregation fixture.
        self.rows = [
            loss(self.user.id, datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc), value="100.00"),
            loss(self.user.id, datetime(2026, 8, 3, 23, 59, tzinfo=timezone.utc), value="300.00"),
            loss(self.user.id, datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc), value=None, doctrine="Armor Line"),
            loss(self.user.id, datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc), value="900.00", disposition="duplicate"),
            loss(self.other.id, datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc), value="500.00"),
        ]
        self.db.add_all(self.rows); self.db.commit()

    def teardown_method(self) -> None:
        self.db.close(); self.engine.dispose()

    def test_counts_totals_unknowns_boundaries_and_averages(self) -> None:
        rows = filtered_rows(self.db, user_id=self.user.id, manager=False, date_from=date(2026, 8, 1), date_to=date(2026, 8, 3))
        report = build_analytics(self.db, rows, date_from=date(2026, 8, 1), date_to=date(2026, 8, 3),
                                 reporting_timezone="UTC", applied_filters={}, user_id=self.user.id, manager=False)
        assert report["summary"]["loss_count"] == 3
        assert report["summary"]["total_isk_lost"] == "400.00"
        assert report["summary"]["average_isk_per_loss"] == "133.33"
        assert report["summary"]["average_isk_per_calendar_day"] == "133.33"
        assert report["summary"]["average_isk_per_active_loss_day"] == "200.00"
        assert report["quality"]["unvalued_count"] == 1
        assert report["quality"]["excluded_record_count"] == 1

    def test_doctrine_snapshots_are_grouped_without_live_doctrine(self) -> None:
        rows = filtered_rows(self.db, user_id=self.user.id, manager=False)
        report = build_analytics(self.db, rows, date_from=None, date_to=None, reporting_timezone="UTC",
                                 applied_filters={}, user_id=self.user.id, manager=False)
        shield = next(item for item in report["breakdowns"]["doctrines"] if item["label"] == "Shield Line")
        assert shield["loss_count"] == 2
        assert shield["total_isk"] == "400.00"

    def test_authoritative_precedence(self) -> None:
        row = self.rows[0]
        row.killmail_total_loss_value = Decimal("200"); row.valuation_status = "verified"
        row.verified_loss_value = Decimal("300"); row.manual_valuation_override = Decimal("400")
        assert authoritative_loss_value(row) == Decimal("400")
        row.manual_valuation_override = None
        assert authoritative_loss_value(row) == Decimal("300")
        row.verified_loss_value = None
        assert authoritative_loss_value(row) == Decimal("200")

    def test_audit_event_and_csv_exact_values(self) -> None:
        row = self.rows[0]
        event = SrpRequestEvent(request_id=row.id, event_type="approved", actor_user_id=self.user.id,
                                old_values={"status":"under_review"}, new_values={"status":"approved"})
        self.db.add(event); self.db.commit()
        assert self.db.query(SrpRequestEvent).filter_by(request_id=row.id).count() == 1
        exported = detailed_csv([row])
        assert "authoritative_loss_isk" in exported
        assert "100.00" in exported

    def test_manager_and_member_visibility_are_isolated(self) -> None:
        member_rows = filtered_rows(self.db, user_id=self.user.id, manager=False)
        manager_rows = filtered_rows(self.db, user_id=self.user.id, manager=True)
        assert len(member_rows) == 3
        assert len(manager_rows) == 4

    def test_reporting_timezone_bucketing(self) -> None:
        rows = filtered_rows(self.db, user_id=self.user.id, manager=False)
        report = build_analytics(self.db, rows[:1], date_from=None, date_to=None, reporting_timezone="America/Chicago",
                                 applied_filters={}, user_id=self.user.id, manager=False)
        assert report["time_series"][0]["bucket"] == "2026-07-31"


def test_migration_graph_has_doctrine_fittings_as_single_head() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0069_doctrine_skill_plans"]
