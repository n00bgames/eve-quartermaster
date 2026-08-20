from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from app.models import CharacterWalletJournalEntry


BOUNTY_REFERENCE_TYPE = "bounty_prizes"


def decimal_value(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_bounty_ticks(
    entries: Iterable[CharacterWalletJournalEntry],
    *,
    tax_receiver_names: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic payout ticks from authoritative ESI journal rows.

    A tick is one or more ``bounty_prizes`` rows for the same character with the
    exact same authoritative ESI timestamp. No time-window guessing is used.
    The stable tick key therefore survives repeated imports and late-arriving
    rows for the same payout timestamp.
    """
    grouped: dict[tuple[int, datetime], list[CharacterWalletJournalEntry]] = defaultdict(list)
    for row in entries:
        if row.reference_type != BOUNTY_REFERENCE_TYPE or row.amount is None:
            continue
        grouped[(row.character_id, utc(row.occurred_at))].append(row)

    receiver_names = tax_receiver_names or {}
    ticks: list[dict[str, Any]] = []
    for (_, occurred_at), rows in grouped.items():
        rows.sort(key=lambda row: (row.reference_id, row.id or 0))
        character = rows[0].character
        net = sum((decimal_value(row.amount) for row in rows), Decimal("0"))
        tax_known = all(row.tax is not None for row in rows)
        tax = sum((decimal_value(row.tax) for row in rows), Decimal("0")) if tax_known else None
        gross = net + tax if tax is not None else None
        tax_receivers = sorted({int(row.tax_receiver_id) for row in rows if row.tax_receiver_id is not None})
        contexts = sorted({int(row.context_id) for row in rows if row.context_id is not None})
        descriptions = [text for text in dict.fromkeys((row.description or row.reason or "").strip() for row in rows) if text]
        corporation_eve_id = next((int(row.corporation_eve_id_at_import) for row in rows if row.corporation_eve_id_at_import is not None), None)
        corporation_name = next((row.corporation_name_at_import for row in rows if row.corporation_name_at_import), None)
        if tax_receivers:
            corporation_eve_id = tax_receivers[0]
            corporation_name = receiver_names.get(tax_receivers[0], corporation_name)
        tick_id = f"{character.character_id}:{occurred_at.isoformat()}"
        ticks.append(
            {
                "tick_id": tick_id,
                "occurred_at": occurred_at,
                "character_id": character.id,
                "character_eve_id": character.character_id,
                "character_name": character.name,
                "corporation_eve_id": corporation_eve_id,
                "corporation_name": corporation_name,
                "reference_ids": [int(row.reference_id) for row in rows],
                "source_entry_count": len(rows),
                "net_isk": net,
                "corporate_tax_isk": tax,
                "gross_isk": gross,
                "tax_status": "known" if tax_known else "unknown",
                "effective_tax_rate": (tax / gross * Decimal("100")) if tax is not None and gross and gross != 0 else None,
                "tax_receiver_ids": tax_receivers,
                "tax_receiver_names": [receiver_names.get(receiver_id) for receiver_id in tax_receivers if receiver_names.get(receiver_id)],
                "system_ids": contexts,
                "descriptions": descriptions,
            }
        )
    return sorted(ticks, key=lambda row: (row["occurred_at"], row["character_name"], row["tick_id"]), reverse=True)


def summarize_ticks(ticks: list[dict[str, Any]]) -> dict[str, Any]:
    tick_count = len(ticks)
    net_total = sum((row["net_isk"] for row in ticks), Decimal("0"))
    known = [row for row in ticks if row["corporate_tax_isk"] is not None and row["gross_isk"] is not None]
    tax_known_total = sum((row["corporate_tax_isk"] for row in known), Decimal("0"))
    gross_known_total = sum((row["gross_isk"] for row in known), Decimal("0"))
    complete = len(known) == tick_count
    highest = max(ticks, key=lambda row: row["net_isk"]) if ticks else None
    recent = max(ticks, key=lambda row: row["occurred_at"]) if ticks else None
    return {
        "net_isk": net_total,
        "tick_count": tick_count,
        "average_tick_isk": net_total / tick_count if tick_count else Decimal("0"),
        "highest_tick_isk": highest["net_isk"] if highest else None,
        "highest_tick_id": highest["tick_id"] if highest else None,
        "highest_tick_pilot": highest["character_name"] if highest else None,
        "most_recent_at": recent["occurred_at"] if recent else None,
        "active_pilots": len({row["character_eve_id"] for row in ticks}),
        "corporate_tax_isk": tax_known_total if complete else None,
        "known_corporate_tax_isk": tax_known_total,
        "gross_isk": gross_known_total if complete else None,
        "known_gross_isk": gross_known_total,
        "effective_tax_rate": (
            tax_known_total / gross_known_total * Decimal("100")
            if complete and gross_known_total
            else None
        ),
        "tax_coverage_complete": complete,
        "tax_known_ticks": len(known),
        "tax_unknown_ticks": tick_count - len(known),
    }


def leaderboard(ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in ticks:
        grouped[row["character_eve_id"]].append(row)
    result: list[dict[str, Any]] = []
    for character_eve_id, rows in grouped.items():
        stats = summarize_ticks(rows)
        result.append(
            {
                "character_eve_id": character_eve_id,
                "character_name": rows[0]["character_name"],
                "corporation_eve_id": rows[0]["corporation_eve_id"],
                "corporation_name": rows[0]["corporation_name"],
                **stats,
                "tick_ids": [row["tick_id"] for row in rows],
                "reference_ids": [reference_id for row in rows for reference_id in row["reference_ids"]],
            }
        )
    result.sort(key=lambda row: (row["net_isk"], row["highest_tick_isk"] or Decimal("0"), row["character_name"]), reverse=True)
    for position, row in enumerate(result, 1):
        row["rank"] = position
    return result


def timeline(ticks: list[dict[str, Any]], grouping: str, timezone_name: str) -> list[dict[str, Any]]:
    tz = ZoneInfo(timezone_name)
    buckets: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for row in ticks:
        local = row["occurred_at"].astimezone(tz)
        if grouping == "daily":
            local = local.replace(hour=0, minute=0, second=0, microsecond=0)
        elif grouping == "hourly":
            local = local.replace(minute=0, second=0, microsecond=0)
        else:
            local = row["occurred_at"]
        buckets[local.astimezone(timezone.utc)].append(row)
    result: list[dict[str, Any]] = []
    for bucket_start, rows in sorted(buckets.items()):
        stats = summarize_ticks(rows)
        result.append({"bucket_start": bucket_start, **stats})
    return result


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return utc(value).isoformat()
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    return value
