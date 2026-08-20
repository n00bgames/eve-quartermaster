from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import CharacterWalletJournalEntry, EsiToken, EveCharacter, EveCorporation, User
from app.services.bounty_analytics import BOUNTY_REFERENCE_TYPE, build_bounty_ticks, json_value, leaderboard, summarize_ticks, timeline
from app.services.permissions import can_view_section


router = APIRouter(prefix="/bounty-analytics", tags=["bounty-analytics"])
PERIOD_DAYS = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
EXPORT_SCHEMA_VERSION = "eqm.bounty-analytics.v1"
EXPORT_APP_VERSION = "0.1.19-beta"


def require_access(current_user: User, db: Session) -> None:
    if not can_view_section(current_user, "bounty_analytics", db):
        raise HTTPException(status_code=403, detail="Bounty Analytics section access is required")


def local_bounds(
    *,
    period: str,
    date_from: date | None,
    date_to: date | None,
    timezone_name: str,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None, str]:
    tz = ZoneInfo(timezone_name)
    current = (now or datetime.now(timezone.utc)).astimezone(tz)
    if date_from or date_to:
        start = datetime.combine(date_from, time.min, tzinfo=tz).astimezone(timezone.utc) if date_from else None
        end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc) if date_to else None
        return start, end, "custom"
    if period == "all":
        return None, None, "all"
    days = PERIOD_DAYS.get(period)
    if days is None:
        raise HTTPException(status_code=400, detail="period must be 1d, 7d, 30d, 90d, or all")
    return current.astimezone(timezone.utc) - timedelta(days=days), None, period


def eligible_characters(db: Session, current_user: User) -> list[EveCharacter]:
    return list(
        db.scalars(
            select(EveCharacter)
            .options(selectinload(EveCharacter.corporation))
            .where(
                EveCharacter.owner_user_id == current_user.id,
                EveCharacter.wallet_history_opt_out.is_(False),
                EveCharacter.sync_opt_out.is_(False),
            )
            .order_by(EveCharacter.name)
        ).all()
    )


def token_statuses(db: Session, current_user: User, characters: list[EveCharacter]) -> dict[int, str]:
    if not characters:
        return {}
    tokens = list(
        db.scalars(
            select(EsiToken)
            .where(EsiToken.user_id == current_user.id, EsiToken.character_id.in_([row.id for row in characters]))
            .order_by(EsiToken.character_id, EsiToken.created_at.desc())
        ).all()
    )
    latest: dict[int, EsiToken] = {}
    for token in tokens:
        latest.setdefault(token.character_id, token)
    result: dict[int, str] = {}
    for character in characters:
        token = latest.get(character.id)
        if token is None:
            result[character.id] = "missing"
        elif token.revoked_at is not None:
            result[character.id] = "revoked"
        elif "esi-wallet.read_character_wallet.v1" not in token.scopes.split():
            result[character.id] = "missing_scope"
        else:
            result[character.id] = "authorized"
    return result


def filtered_ticks(
    db: Session,
    current_user: User,
    *,
    period: str,
    date_from: date | None,
    date_to: date | None,
    character_eve_id: int | None,
    corporation_eve_id: int | None,
    tax_status: str,
) -> tuple[list[dict[str, Any]], list[EveCharacter], datetime | None, datetime | None, str, str]:
    require_access(current_user, db)
    timezone_name = current_user.timezone or "UTC"
    try:
        start, end, resolved_period = local_bounds(period=period, date_from=date_from, date_to=date_to, timezone_name=timezone_name)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail="The configured reporting timezone is invalid") from exc
    characters = eligible_characters(db, current_user)
    character_by_eve_id = {row.character_id: row for row in characters}
    if character_eve_id is not None and character_eve_id not in character_by_eve_id:
        raise HTTPException(status_code=404, detail="That wallet-visible character is not linked to your account")
    internal_ids = [character_by_eve_id[character_eve_id].id] if character_eve_id is not None else [row.id for row in characters]
    if not internal_ids:
        return [], characters, start, end, resolved_period, timezone_name
    query = (
        select(CharacterWalletJournalEntry)
        .options(selectinload(CharacterWalletJournalEntry.character))
        .where(
            CharacterWalletJournalEntry.character_id.in_(internal_ids),
            CharacterWalletJournalEntry.reference_type == BOUNTY_REFERENCE_TYPE,
        )
    )
    if start is not None:
        query = query.where(CharacterWalletJournalEntry.occurred_at >= start)
    if end is not None:
        query = query.where(CharacterWalletJournalEntry.occurred_at < end)
    if corporation_eve_id is not None:
        query = query.where(
            or_(
                CharacterWalletJournalEntry.corporation_eve_id_at_import == corporation_eve_id,
                CharacterWalletJournalEntry.tax_receiver_id == corporation_eve_id,
            )
        )
    entries = list(db.scalars(query.order_by(CharacterWalletJournalEntry.occurred_at.desc())).all())
    receiver_ids = {int(row.tax_receiver_id) for row in entries if row.tax_receiver_id is not None}
    receiver_names = {
        row.corporation_id: row.name
        for row in db.scalars(select(EveCorporation).where(EveCorporation.corporation_id.in_(receiver_ids))).all()
    } if receiver_ids else {}
    ticks = build_bounty_ticks(entries, tax_receiver_names=receiver_names)
    if tax_status not in {"all", "known", "unknown"}:
        raise HTTPException(status_code=400, detail="tax_status must be all, known, or unknown")
    if tax_status != "all":
        ticks = [row for row in ticks if row["tax_status"] == tax_status]
    return ticks, characters, start, end, resolved_period, timezone_name


def corporation_options(characters: list[EveCharacter], ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[int, str] = {}
    for character in characters:
        if character.corporation:
            values[character.corporation.corporation_id] = character.corporation.name
    for row in ticks:
        if row["corporation_eve_id"] is not None:
            values[int(row["corporation_eve_id"])] = row["corporation_name"] or f"Corporation {row['corporation_eve_id']}"
    return [{"corporation_eve_id": key, "corporation_name": value} for key, value in sorted(values.items(), key=lambda item: item[1].lower())]


@router.get("")
def bounty_analytics(
    period: str = Query("7d"),
    grouping: Literal["tick", "hourly", "daily"] = Query("daily"),
    date_from: date | None = None,
    date_to: date | None = None,
    character_eve_id: int | None = None,
    corporation_eve_id: int | None = None,
    tax_status: str = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ticks, characters, start, end, resolved_period, timezone_name = filtered_ticks(
        db,
        current_user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        character_eve_id=character_eve_id,
        corporation_eve_id=corporation_eve_id,
        tax_status=tax_status,
    )
    statuses = token_statuses(db, current_user, characters)
    offset = (page - 1) * page_size
    payload = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc),
        "period": resolved_period,
        "date_from_utc": start,
        "date_to_exclusive_utc": end,
        "grouping": grouping,
        "reporting_timezone": timezone_name,
        "scope": "current_user_connected_characters",
        "summary": summarize_ticks(ticks),
        "timeline": timeline(ticks, grouping, timezone_name),
        "leaderboard": leaderboard(ticks),
        "ledger": ticks[offset : offset + page_size],
        "tick_count": len(ticks),
        "page": page,
        "page_size": page_size,
        "characters": [
            {
                "character_eve_id": row.character_id,
                "character_name": row.name,
                "corporation_eve_id": row.corporation.corporation_id if row.corporation else None,
                "corporation_name": row.corporation.name if row.corporation else None,
                "wallet_synced_at": row.wallet_synced_at,
                "authorization_status": statuses.get(row.id, "missing"),
            }
            for row in characters
        ],
        "corporations": corporation_options(characters, ticks),
        "definitions": {
            "tick": "One or more authoritative ESI bounty_prizes journal rows for one pilot with the exact same UTC transaction timestamp. EQM does not guess payout cycles from a time window.",
            "net": "The original ESI wallet-journal amount deposited into the pilot wallet.",
            "corporate_tax": "The ESI tax field on the contributing bounty journal row. Missing tax fields remain Unknown.",
            "gross": "Net bounty plus authoritative corporate tax, only when tax is known.",
            "isk_per_hour": "Not calculated because wallet journals do not identify reliable ratting-session boundaries.",
        },
    }
    return json_value(payload)


@router.get("/export")
def export_bounty_analytics(
    period: str = Query("7d"),
    date_from: date | None = None,
    date_to: date | None = None,
    character_eve_id: int | None = None,
    corporation_eve_id: int | None = None,
    tax_status: str = Query("all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ticks, _, start, end, resolved_period, timezone_name = filtered_ticks(
        db,
        current_user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        character_eve_id=character_eve_id,
        corporation_eve_id=corporation_eve_id,
        tax_status=tax_status,
    )
    generated_at = datetime.now(timezone.utc)
    buffer = io.StringIO(newline="")
    columns = [
        "schema_version", "generated_at_utc", "reporting_timezone", "selected_period", "range_start_utc", "range_end_exclusive_utc",
        "tick_id", "occurred_at_utc", "pilot_eve_id", "pilot_name", "corporation_eve_id_at_payout", "corporation_name_at_payout",
        "reference_ids", "source_entry_count", "net_bounty_isk", "corporate_tax_isk", "gross_bounty_isk", "tax_status",
        "effective_tax_rate_percent", "tax_receiver_ids", "tax_receiver_names", "system_ids", "descriptions",
    ]
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in ticks:
        writer.writerow(
            {
                "schema_version": EXPORT_SCHEMA_VERSION,
                "generated_at_utc": generated_at.isoformat(),
                "reporting_timezone": timezone_name,
                "selected_period": resolved_period,
                "range_start_utc": start.isoformat() if start else "",
                "range_end_exclusive_utc": end.isoformat() if end else "",
                "tick_id": row["tick_id"],
                "occurred_at_utc": row["occurred_at"].isoformat(),
                "pilot_eve_id": str(row["character_eve_id"]),
                "pilot_name": row["character_name"],
                "corporation_eve_id_at_payout": str(row["corporation_eve_id"]) if row["corporation_eve_id"] is not None else "",
                "corporation_name_at_payout": row["corporation_name"] or "",
                "reference_ids": "|".join(str(value) for value in row["reference_ids"]),
                "source_entry_count": row["source_entry_count"],
                "net_bounty_isk": row["net_isk"],
                "corporate_tax_isk": row["corporate_tax_isk"] if row["corporate_tax_isk"] is not None else "",
                "gross_bounty_isk": row["gross_isk"] if row["gross_isk"] is not None else "",
                "tax_status": row["tax_status"],
                "effective_tax_rate_percent": row["effective_tax_rate"] if row["effective_tax_rate"] is not None else "",
                "tax_receiver_ids": "|".join(str(value) for value in row["tax_receiver_ids"]),
                "tax_receiver_names": "|".join(row["tax_receiver_names"]),
                "system_ids": "|".join(str(value) for value in row["system_ids"]),
                "descriptions": " | ".join(row["descriptions"]),
            }
        )
    stamp = generated_at.strftime("%Y-%m-%dT%H%M%SZ")
    return {
        "filename": f"eve-bounty-ledger-{stamp}.csv",
        "mime_type": "text/csv;charset=utf-8",
        "csv": buffer.getvalue(),
        "row_count": len(ticks),
        "schema_version": EXPORT_SCHEMA_VERSION,
        "application_version": EXPORT_APP_VERSION,
        "generated_at_utc": generated_at.isoformat(),
    }
