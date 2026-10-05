from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.analytics import analytics_metric_rows, character_history_rows, start_cutoff
from app.api.financial_analytics import character_wallet_history, personal_wallet_payload
from app.core.config import get_settings
from app.models import Base, CharacterSkillSnapshot, CharacterWalletSnapshot, CharacterWalletJournalEntry, EveCharacter, EveCorporation, SnapshotMetric
from app.services.financial_analytics import account_wallet_summary
from app.services.planetary_analytics import _windowed_estimate


def test_all_time_queries_include_history_older_than_ten_years():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    old = datetime.now(timezone.utc) - timedelta(days=5000)
    with Session(engine) as db:
        character = EveCharacter(id=1, character_id=9001, name="Pilot", owner_user_id=1)
        db.add(character)
        db.add_all([
            SnapshotMetric(snapshot_run_id=1, owner_type="character", owner_id=1, metric_key="test", metric_value=10, recorded_at=old),
            CharacterSkillSnapshot(snapshot_run_id=1, character_id=1, character_eve_id=9001, character_name="Pilot", total_skill_points=100, recorded_at=old),
            CharacterWalletSnapshot(snapshot_run_id=1, character_id=1, character_eve_id=9001, character_name="Pilot", balance=100, recorded_at=old),
            CharacterWalletJournalEntry(character_id=1, reference_id=1, reference_type="market_transaction", amount=-20, occurred_at=old),
        ])
        db.commit()
        assert len(analytics_metric_rows(db, 0)) == 1
        assert analytics_metric_rows(db, 3660) == []
        assert len(character_history_rows(db, 0, {1}, categorized=False)) == 1
        assert character_history_rows(db, 0, {2}, categorized=False) == []
        assert len(character_wallet_history(db, 1, start_cutoff(0))) == 1
        with patch.object(get_settings(), "eqm_financial_analytics_engine", "python"):
            personal = personal_wallet_payload(db, character, start_cutoff(0))
        assert personal["stats"]["spending"] == 20
        assert personal["history_days"] >= 5000
        account = account_wallet_summary([personal], days=0)
        assert account["stats"]["spending_velocity"] == 20 / personal["history_days"]
    engine.dispose()


def test_all_time_has_no_cutoff_cap_and_pi_estimates_are_not_prorated():
    from types import SimpleNamespace
    assert start_cutoff(0) == datetime.min.replace(tzinfo=timezone.utc)
    row = SimpleNamespace(estimated_units_since_previous=100, interval_started_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
                          captured_at=datetime(2000, 1, 2, tzinfo=timezone.utc))
    assert _windowed_estimate(row, start_cutoff(0)) == 100
