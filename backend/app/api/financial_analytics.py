from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import CharacterWalletJournalEntry, CharacterWalletSnapshot, CorporationWalletDivision, CorporationWalletSnapshot, EveCharacter, EveCorporation, User
from app.services.analytics import analytics_corporation_ids
from app.services.financial_analytics import combine_daily_series, corporation_daily_points, corporation_division_daily_points, daily_closing_points, distribution, wallet_statistics
from app.services.financial_analytics_engine import evaluate_financial_analytics_with_engine
from app.services.permissions import ROLE_RANK, can_view_section, role_rank


router = APIRouter(prefix="/analytics/financial", tags=["analytics"])


EVENT_LABELS = {
    "market_transaction": "Market transaction",
    "contract_price": "Contract purchase",
    "contract_reward": "Contract payout",
    "contract_collateral": "Contract collateral",
    "contract_sales_tax": "Contract sales tax",
    "industry_job_tax": "Industry investment",
    "market_escrow": "Market escrow",
    "transaction_tax": "Transaction tax",
    "brokers_fee": "Broker fee",
    "player_donation": "Player transfer",
    "corporation_account_withdrawal": "Corporation withdrawal",
    "corporation_account_deposit": "Corporation deposit",
    "bounty_prizes": "Bounty payout",
    "project_discovery_reward": "Project Discovery reward",
    "insurance": "Insurance payment",
}


def require_financial_analytics(current_user: User, db: Session) -> None:
    if not can_view_section(current_user, "analytics", db):
        raise HTTPException(status_code=403, detail="analytics section access is required")


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def engine_iso(value: datetime) -> str:
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat()


def financial_event_label(row: CharacterWalletJournalEntry) -> str:
    if row.reference_type == "market_transaction" and row.item_name:
        return f"{'Purchased' if row.is_buy else 'Sold'} {row.item_name}"
    return EVENT_LABELS.get(row.reference_type, row.reference_type.replace("_", " ").title())


def character_wallet_history(db: Session, character_id: int, cutoff: datetime) -> list[CharacterWalletSnapshot]:
    rows = list(
        db.scalars(
            select(CharacterWalletSnapshot)
            .where(CharacterWalletSnapshot.character_id == character_id, CharacterWalletSnapshot.recorded_at >= cutoff)
            .order_by(CharacterWalletSnapshot.recorded_at, CharacterWalletSnapshot.id)
        ).all()
    )
    baseline = db.scalar(
        select(CharacterWalletSnapshot)
        .where(CharacterWalletSnapshot.character_id == character_id, CharacterWalletSnapshot.recorded_at < cutoff)
        .order_by(CharacterWalletSnapshot.recorded_at.desc(), CharacterWalletSnapshot.id.desc())
        .limit(1)
    )
    return ([baseline] if baseline else []) + rows


def corporation_character_wallet_history(db: Session, corporation_id: int, character_ids: set[int], cutoff: datetime) -> list[CharacterWalletSnapshot]:
    if not character_ids:
        return []
    ranked = select(
        CharacterWalletSnapshot.id.label("id"),
        func.row_number().over(
            partition_by=CharacterWalletSnapshot.character_id,
            order_by=(CharacterWalletSnapshot.recorded_at.desc(), CharacterWalletSnapshot.id.desc()),
        ).label("position"),
    ).where(
        CharacterWalletSnapshot.corporation_id == corporation_id,
        CharacterWalletSnapshot.character_id.in_(character_ids),
        CharacterWalletSnapshot.recorded_at < cutoff,
    ).subquery()
    baseline_ids = select(ranked.c.id).where(ranked.c.position == 1)
    return list(db.scalars(
        select(CharacterWalletSnapshot)
        .where(
            CharacterWalletSnapshot.corporation_id == corporation_id,
            CharacterWalletSnapshot.character_id.in_(character_ids),
            or_(CharacterWalletSnapshot.recorded_at >= cutoff, CharacterWalletSnapshot.id.in_(baseline_ids)),
        )
        .order_by(CharacterWalletSnapshot.recorded_at, CharacterWalletSnapshot.id)
    ).all())


def corporation_division_wallet_history(db: Session, corporation_id: int, cutoff: datetime) -> list[CorporationWalletSnapshot]:
    ranked = select(
        CorporationWalletSnapshot.id.label("id"),
        func.row_number().over(
            partition_by=CorporationWalletSnapshot.division,
            order_by=(CorporationWalletSnapshot.recorded_at.desc(), CorporationWalletSnapshot.id.desc()),
        ).label("position"),
    ).where(
        CorporationWalletSnapshot.corporation_id == corporation_id,
        CorporationWalletSnapshot.recorded_at < cutoff,
    ).subquery()
    baseline_ids = select(ranked.c.id).where(ranked.c.position == 1)
    return list(db.scalars(
        select(CorporationWalletSnapshot)
        .where(
            CorporationWalletSnapshot.corporation_id == corporation_id,
            or_(CorporationWalletSnapshot.recorded_at >= cutoff, CorporationWalletSnapshot.id.in_(baseline_ids)),
        )
        .order_by(CorporationWalletSnapshot.recorded_at, CorporationWalletSnapshot.id)
    ).all())


def financial_snapshot_row(row: CharacterWalletSnapshot | CorporationWalletSnapshot, group_attribute: str | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "group_id": int(getattr(row, group_attribute)) if group_attribute else None,
        "recorded_at": engine_iso(row.recorded_at),
        "balance": float(row.balance),
    }


def journal_timeline_row(row: CharacterWalletJournalEntry) -> dict[str, Any]:
    return {
        "id": row.id,
        "occurred_at": iso(row.occurred_at),
        "kind": row.reference_type,
        "label": financial_event_label(row),
        "amount": float(row.amount or 0),
        "balance": float(row.balance) if row.balance is not None else None,
        "description": row.description or row.reason,
        "context_id": row.context_id,
        "item_name": row.item_name,
        "quantity": row.quantity,
        "unit_price": float(row.unit_price) if row.unit_price is not None else None,
        "is_buy": row.is_buy,
    }


def _personal_wallet_calculations_python(
    history: list[CharacterWalletSnapshot],
    journal: list[CharacterWalletJournalEntry],
    cutoff: datetime,
    now: datetime,
    current_balance: float | None,
) -> dict[str, Any]:
    points = daily_closing_points(history, start_date=cutoff.date())
    stats = wallet_statistics(points, current_balance=current_balance)
    income = sum(float(row.amount or 0) for row in journal if float(row.amount or 0) > 0)
    spending = sum(abs(float(row.amount or 0)) for row in journal if float(row.amount or 0) < 0)
    notable = sorted(journal, key=lambda row: abs(float(row.amount or 0)), reverse=True)[:30]
    return {
        "stats": {
            **stats,
            "income": income,
            "spending": spending,
            "spending_velocity": spending / max(1, (now - cutoff).days),
        },
        "points": points,
        "timeline": [journal_timeline_row(row) for row in sorted(notable, key=lambda row: row.occurred_at, reverse=True)],
    }


def personal_wallet_payload(db: Session, character: EveCharacter, cutoff: datetime) -> dict[str, Any]:
    history = character_wallet_history(db, character.id, cutoff)
    journal = list(
        db.scalars(
            select(CharacterWalletJournalEntry)
            .where(CharacterWalletJournalEntry.character_id == character.id, CharacterWalletJournalEntry.occurred_at >= cutoff)
            .order_by(CharacterWalletJournalEntry.occurred_at.desc(), CharacterWalletJournalEntry.id.desc())
        ).all()
    )
    now = datetime.now(timezone.utc)
    current_balance = float(character.current_wallet_balance) if character.current_wallet_balance is not None else None
    calculation = evaluate_financial_analytics_with_engine(
        payload={
            "schema_version": "eqm.financial-analytics.v1",
            "operation": "personal",
            "personal": {
                "start_date": cutoff.date().isoformat(),
                "cutoff": cutoff.isoformat(),
                "now": now.isoformat(),
                "current_balance": current_balance,
                "snapshots": [financial_snapshot_row(row) for row in history],
                "journal": [
                    {
                        "id": row.id,
                        "occurred_at": engine_iso(row.occurred_at),
                        "amount": float(row.amount or 0),
                        "timeline": journal_timeline_row(row),
                    }
                    for row in journal
                ],
            },
        },
        python_result=lambda: _personal_wallet_calculations_python(history, journal, cutoff, now, current_balance),
    )
    return {
        "character_id": character.id,
        "character_eve_id": character.character_id,
        "character_name": character.name,
        "corporation_id": character.corporation_id,
        "corporation_name": character.corporation.name if character.corporation else None,
        "wallet_synced_at": iso(character.wallet_synced_at),
        "history_opt_out": character.wallet_history_opt_out,
        **calculation,
    }


def _corporation_wallet_calculations_python(
    history: list[CharacterWalletSnapshot],
    division_history: list[CorporationWalletSnapshot],
    current_balances: list[float],
    current_division_balances: list[float],
    cutoff: datetime,
    raw_visible: bool,
) -> dict[str, Any]:
    character_points = corporation_daily_points(history, start_date=cutoff.date())
    division_points = corporation_division_daily_points(division_history, start_date=cutoff.date())
    absolute_points = combine_daily_series(character_points, division_points)
    character_wallet_total = sum(current_balances)
    corporation_wallet_total = sum(current_division_balances)
    current_total = character_wallet_total + corporation_wallet_total if current_balances or current_division_balances else None
    stats = wallet_statistics(absolute_points, current_balance=current_total, metric_key="wallet.balance")
    if raw_visible:
        points = absolute_points
        current = current_total
        wealth_distribution = distribution(current_balances)
    else:
        baseline = absolute_points[0]["value"] if absolute_points else 0
        points = [{"date": point["date"], "value": float(point["value"]) - float(baseline)} for point in absolute_points]
        current = None
        wealth_distribution = {"median": None, "average": None}
    return {
        "tracked_characters": len(current_balances),
        "corporation_wallet_divisions": len(current_division_balances),
        "corporation_wallet_total": corporation_wallet_total if raw_visible else None,
        "character_wallet_total": character_wallet_total if raw_visible else None,
        "series_mode": "absolute" if raw_visible else "change",
        "stats": {**stats, "current": current, **wealth_distribution},
        "points": points,
    }


def corporation_wallet_payload(db: Session, corporation: EveCorporation, cutoff: datetime, current_user: User) -> dict[str, Any]:
    eligible_character_ids = set(
        db.scalars(
            select(EveCharacter.id).where(
                EveCharacter.corporation_id == corporation.id,
                EveCharacter.wallet_history_opt_out.is_(False),
                EveCharacter.wallet_corporation_analytics_opt_in.is_(True),
                EveCharacter.sync_opt_out.is_(False),
            )
        ).all()
    )
    history = corporation_character_wallet_history(db, corporation.id, eligible_character_ids, cutoff)
    division_history = corporation_division_wallet_history(db, corporation.id, cutoff)
    current_balances = [
        float(value)
        for value in db.scalars(
            select(EveCharacter.current_wallet_balance).where(
                EveCharacter.id.in_(eligible_character_ids) if eligible_character_ids else False,
                EveCharacter.current_wallet_balance.is_not(None),
            )
        ).all()
    ]
    current_divisions = list(
        db.scalars(
            select(CorporationWalletDivision).where(CorporationWalletDivision.corporation_id == corporation.id)
        ).all()
    )
    current_division_balances = [float(row.balance or 0) for row in current_divisions]
    raw_visible = bool(corporation.character_wallet_totals_visible and role_rank(current_user, db) >= ROLE_RANK["officer"])
    calculation = evaluate_financial_analytics_with_engine(
        payload={
            "schema_version": "eqm.financial-analytics.v1",
            "operation": "corporation",
            "corporation": {
                "start_date": cutoff.date().isoformat(),
                "raw_visible": raw_visible,
                "character_snapshots": [financial_snapshot_row(row, "character_id") for row in history],
                "division_snapshots": [financial_snapshot_row(row, "division") for row in division_history],
                "current_character_balances": current_balances,
                "current_division_balances": current_division_balances,
            },
        },
        python_result=lambda: _corporation_wallet_calculations_python(
            history,
            division_history,
            current_balances,
            current_division_balances,
            cutoff,
            raw_visible,
        ),
    )
    return {
        "corporation_id": corporation.id,
        "corporation_eve_id": corporation.corporation_id,
        "corporation_name": corporation.name,
        "ticker": corporation.ticker,
        "raw_totals_visible": raw_visible,
        **calculation,
    }


@router.get("")
def financial_analytics(
    days: int = Query(30, ge=1, le=3660),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_financial_analytics(current_user, db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    personal_characters = list(
        db.scalars(
            select(EveCharacter)
            .where(
                EveCharacter.owner_user_id == current_user.id,
                EveCharacter.wallet_history_opt_out.is_(False),
                EveCharacter.sync_opt_out.is_(False),
            )
            .order_by(EveCharacter.name)
        ).all()
    )
    corporation_ids = analytics_corporation_ids(db)
    corporations = list(
        db.scalars(select(EveCorporation).where(EveCorporation.id.in_(corporation_ids)).order_by(EveCorporation.name)).all()
    ) if corporation_ids else []
    return {
        "days": days,
        "personal": [personal_wallet_payload(db, character, cutoff) for character in personal_characters],
        "corporations": [corporation_wallet_payload(db, corporation, cutoff, current_user) for corporation in corporations],
        "privacy": {
            "individual_leaderboards_enabled": False,
            "message": "Personal balances are visible only to their owning account. Corporation views default to trends and never expose a richest-pilot leaderboard.",
        },
    }
