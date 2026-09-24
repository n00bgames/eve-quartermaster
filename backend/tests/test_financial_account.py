from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.financial_analytics import financial_analytics
from app.core.config import get_settings
from app.models import Base, CharacterWalletJournalEntry, EveCharacter, EveCorporation, User
from app.services.financial_analytics import account_wallet_summary


def personal(character_id, points, balance, income=0, spending=0, timeline=None):
    return {
        "character_id": character_id, "character_name": f"Pilot {character_id}",
        "points": [{"date": day, "value": value} for day, value in points],
        "stats": {"current": balance, "income": income, "spending": spending},
        "timeline": timeline or [],
    }


def test_account_carries_forward_balances_and_recalculates_growth():
    result = account_wallet_summary([
        personal(1, [("2026-09-01", 100), ("2026-09-03", 130)], 130, 50, 20),
        personal(2, [("2026-09-01", 900), ("2026-09-02", 1000)], 1000, 100),
    ], days=30)
    assert [p["value"] for p in result["points"]] == [1000, 1100, 1130]
    assert result["stats"]["current"] == 1130
    assert result["stats"]["net_change"] == 130
    assert result["stats"]["percentage_growth"] == 13
    assert result["stats"]["largest_gain"] == 100
    assert result["stats"]["average_daily_growth"] == 65
    assert result["stats"]["income"] == 150
    assert result["stats"]["spending"] == 20


def test_internal_transfer_cancels_in_combined_balance_but_preserves_journal_totals():
    result = account_wallet_summary([
        personal(1, [("2026-09-01", 100), ("2026-09-02", 60)], 60, spending=40),
        personal(2, [("2026-09-01", 10), ("2026-09-02", 50)], 50, income=40),
    ], days=30)
    assert result["stats"]["net_change"] == 0
    assert result["stats"]["income"] == result["stats"]["spending"] == 40


def test_empty_and_missing_balances_are_not_claimed_as_known_zero():
    result = account_wallet_summary([], days=30)
    assert result["stats"]["current"] is None
    assert result["points"] == result["timeline"] == []
    result = account_wallet_summary([personal(1, [], None), personal(2, [], 0)], days=30)
    assert result["tracked_characters"] == 2
    assert result["wallets_with_balance"] == 1
    assert result["stats"]["current"] == 0


def test_global_timeline_selects_largest_events_and_identifies_character():
    rows = [personal(i, [], 0, timeline=[
        {"id": j, "amount": i * 100 + j, "occurred_at": f"2026-09-{j:02d}T12:00:00Z"}
        for j in range(1, 29)
    ]) for i in (1, 2)]
    result = account_wallet_summary(rows, days=30)
    assert len(result["timeline"]) == 30
    assert min(e["amount"] for e in result["timeline"]) == 127
    assert result["timeline"][0]["occurred_at"].startswith("2026-09-28")
    assert all(e["character_name"] == f"Pilot {e['character_id']}" for e in result["timeline"])


@patch("app.api.financial_analytics.require_financial_analytics")
@patch("app.api.financial_analytics.analytics_corporation_ids", return_value=[])
def test_account_only_includes_owned_enabled_characters_across_corporations(_corporations, _access):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="owner@example.invalid", display_name="Owner", role="admin")
        other = User(email="other@example.invalid", display_name="Other")
        corp = EveCorporation(corporation_id=1000049, name="Pator Tech School")
        db.add_all([user, other, corp])
        db.flush()
        chars = [
            EveCharacter(character_id=900001, name="Main", owner_user_id=user.id, current_wallet_balance=100),
            EveCharacter(character_id=900002, name="Neutral", owner_user_id=user.id, corporation_id=corp.id, current_wallet_balance=200),
            EveCharacter(character_id=900003, name="Other owner", owner_user_id=other.id, current_wallet_balance=9000),
            EveCharacter(character_id=900004, name="No history", owner_user_id=user.id, current_wallet_balance=9000, wallet_history_opt_out=True),
            EveCharacter(character_id=900005, name="No sync", owner_user_id=user.id, current_wallet_balance=9000, sync_opt_out=True),
        ]
        db.add_all(chars)
        db.flush()
        for character in chars:
            db.add(CharacterWalletJournalEntry(character_id=character.id, reference_id=123,
                occurred_at=datetime.now(timezone.utc), reference_type="bounty_prizes", amount=10))
        db.commit()
        with patch.object(get_settings(), "eqm_financial_analytics_engine", "python"):
            result = financial_analytics(days=30, current_user=user, db=db)
        assert result["account"]["tracked_characters"] == 2
        assert result["account"]["stats"]["current"] == 300
        assert result["account"]["stats"]["income"] == 20
        assert {e["character_name"] for e in result["account"]["timeline"]} == {"Main", "Neutral"}
        assert len(result["personal"]) == 2
    engine.dispose()
