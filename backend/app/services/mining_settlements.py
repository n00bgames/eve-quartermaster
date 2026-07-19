from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any, Iterable

MONEY = Decimal("0.01")
RATE = Decimal("0.0000000001")
WEIGHT = Decimal("0.00000001")
ZERO = Decimal("0")
CONTRIBUTION_BASES = {"estimated_raw_value", "volume", "quantity", "manual"}
RESERVE_METHODS = {"none", "percentage", "output_percentage", "flat_isk"}
COMPENSATION_METHODS = {"fixed_percentage", "shares"}
DEDUCTION_METHODS = {"percentage", "flat_isk"}


class SettlementValidationError(ValueError):
    pass


def decimal_value(value: Any, label: str = "value") -> Decimal:
    if value is None or value == "":
        return ZERO
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise SettlementValidationError(f"{label} must be a number.") from exc
    if not result.is_finite():
        raise SettlementValidationError(f"{label} must be finite.")
    return result


def money(value: Any) -> Decimal:
    return decimal_value(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def normalize_percentage(value: Any, label: str = "percentage") -> Decimal:
    entered = decimal_value(value, label)
    if entered < 0:
        raise SettlementValidationError(f"{label} cannot be negative.")
    normalized = entered if entered <= 1 else entered / Decimal("100")
    if normalized > 1:
        raise SettlementValidationError(f"{label} cannot exceed 100%.")
    return normalized.quantize(RATE, rounding=ROUND_HALF_UP)


def serialize_decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def aggregate_contributions(rows: Iterable[dict[str, Any]], basis: str) -> list[dict[str, Any]]:
    if basis not in CONTRIBUTION_BASES:
        raise SettlementValidationError("Choose a supported contribution basis.")
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        character_id = int(row["character_id"])
        bucket = grouped.setdefault(
            character_id,
            {
                "character_id": character_id,
                "display_name": str(row["character_name"]),
                "ore_types": set(),
                "quantity": ZERO,
                "volume": ZERO,
                "estimated_value": ZERO,
            },
        )
        bucket["ore_types"].add(str(row["ore_type_name"]))
        bucket["quantity"] += decimal_value(row.get("quantity"))
        bucket["volume"] += decimal_value(row.get("volume"))
        bucket["estimated_value"] += decimal_value(row.get("estimated_price"))

    basis_field = {
        "estimated_raw_value": "estimated_value",
        "volume": "volume",
        "quantity": "quantity",
        "manual": None,
    }[basis]
    basis_total = sum((row[basis_field] for row in grouped.values()), ZERO) if basis_field else Decimal(len(grouped))
    average = basis_total / Decimal(len(grouped)) if grouped and basis_total > 0 else Decimal("1")
    results: list[dict[str, Any]] = []
    for row in sorted(grouped.values(), key=lambda item: item["display_name"].lower()):
        basis_value = row[basis_field] if basis_field else Decimal("1")
        contribution_percentage = basis_value / basis_total if basis_total > 0 else ZERO
        auto_weight = basis_value / average if average > 0 else Decimal("1")
        results.append(
            {
                **row,
                "ore_types": sorted(row["ore_types"]),
                "basis_value": basis_value,
                "contribution_percentage": contribution_percentage,
                "auto_share_weight": auto_weight.quantize(WEIGHT, rounding=ROUND_HALF_UP),
            }
        )
    return results


def allocate_money(total: Decimal, weighted_rows: list[tuple[int, Decimal]]) -> dict[int, Decimal]:
    if total <= 0:
        return {key: ZERO for key, _ in weighted_rows}
    positive = [(key, value) for key, value in weighted_rows if value > 0]
    weight_total = sum((value for _, value in positive), ZERO)
    if not positive or weight_total <= 0:
        raise SettlementValidationError("Share-based funds remain, but total share weight is zero.")

    cents_total = int((money(total) * 100).to_integral_value())
    floors: dict[int, int] = {}
    fractions: list[tuple[Decimal, int]] = []
    for key, value in positive:
        exact_cents = Decimal(cents_total) * value / weight_total
        floor_cents = int(exact_cents.to_integral_value(rounding=ROUND_FLOOR))
        floors[key] = floor_cents
        fractions.append((exact_cents - floor_cents, key))
    remainder = cents_total - sum(floors.values())
    for _, key in sorted(fractions, key=lambda item: (-item[0], item[1]))[:remainder]:
        floors[key] += 1
    return {key: Decimal(floors.get(key, 0)) / 100 for key, _ in weighted_rows}


def _clean_outputs(raw_outputs: Any, default_price_source: str) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(raw_outputs, list) or not raw_outputs:
        raise SettlementValidationError("Add at least one actual refined output.")
    outputs: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[int] = set()
    for raw in raw_outputs:
        if not isinstance(raw, dict):
            continue
        type_id = int(raw.get("type_id") or 0)
        name = str(raw.get("type_name") or "").strip()
        quantity = decimal_value(raw.get("quantity"), f"{name or 'Output'} quantity")
        unit_price = decimal_value(raw.get("unit_price"), f"{name or 'Output'} unit price")
        if not type_id or not name:
            raise SettlementValidationError("Choose every refined material from the SDE mineral list.")
        if type_id in seen:
            raise SettlementValidationError(f"{name} appears more than once. Combine duplicate mineral rows.")
        if quantity < 0 or unit_price < 0:
            raise SettlementValidationError("Mineral quantities and prices cannot be negative.")
        seen.add(type_id)
        if quantity == 0:
            continue
        refine_rate = normalize_percentage(raw.get("stated_refine_percent"), f"{name} refine percentage") if raw.get("stated_refine_percent") not in (None, "") else None
        total_value = money(quantity * unit_price)
        overridden = bool(raw.get("price_overridden"))
        if unit_price == 0:
            warnings.append(f"{name} has no unit price, so it contributes no settlement value.")
        if overridden:
            warnings.append(f"{name} uses a manually overridden unit price.")
        outputs.append(
            {
                "type_id": type_id,
                "type_name": name,
                "quantity": quantity,
                "unit_price": unit_price.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                "total_value": total_value,
                "stated_refine_percent": refine_rate,
                "price_source": str(raw.get("price_source") or default_price_source),
                "price_overridden": overridden,
            }
        )
    if not outputs:
        raise SettlementValidationError("At least one refined-output quantity must be greater than zero.")
    return outputs, warnings


def _clean_deductions(raw_deductions: Any, gross_value: Decimal) -> list[dict[str, Any]]:
    deductions: list[dict[str, Any]] = []
    for raw in raw_deductions if isinstance(raw_deductions, list) else []:
        if not isinstance(raw, dict):
            continue
        description = str(raw.get("description") or "").strip()
        deduction_type = str(raw.get("deduction_type") or "other").strip().lower()
        method = str(raw.get("calculation_method") or "flat_isk").strip().lower()
        entered = decimal_value(raw.get("value"), description or "Deduction")
        if not description:
            raise SettlementValidationError("Every deduction needs a description.")
        if method not in DEDUCTION_METHODS:
            raise SettlementValidationError(f"{description} uses an unsupported calculation method.")
        if entered < 0:
            raise SettlementValidationError(f"{description} cannot be negative.")
        normalized = normalize_percentage(entered, description) if method == "percentage" else None
        calculated = money(gross_value * normalized if normalized is not None else entered)
        deductions.append(
            {
                "deduction_type": deduction_type,
                "description": description,
                "calculation_method": method,
                "entered_value": entered,
                "normalized_percentage": normalized,
                "calculated_amount": calculated,
            }
        )
    return deductions


def _participant_rows(contributions: list[dict[str, Any]], raw_participants: Any) -> tuple[list[dict[str, Any]], list[str]]:
    raw_rows = [row for row in raw_participants if isinstance(row, dict)] if isinstance(raw_participants, list) else []
    overrides = {int(row["character_id"]): row for row in raw_rows if row.get("character_id") and str(row.get("source") or "") == "ledger"}
    participants: list[dict[str, Any]] = []
    warnings: list[str] = []

    for contribution in contributions:
        override = overrides.get(contribution["character_id"], {})
        method = str(override.get("compensation_method") or "shares")
        if method not in COMPENSATION_METHODS:
            raise SettlementValidationError(f"{contribution['display_name']} uses an unsupported compensation method.")
        share_overridden = bool(override.get("share_weight_overridden"))
        share_weight = decimal_value(override.get("compensation_value"), "Share weight") if method == "shares" and share_overridden else contribution["auto_share_weight"]
        fixed_rate = normalize_percentage(override.get("compensation_value"), f"{contribution['display_name']} fixed percentage") if method == "fixed_percentage" else None
        if method == "shares" and share_weight < 0:
            raise SettlementValidationError("Share weights cannot be negative.")
        if share_overridden:
            warnings.append(f"{contribution['display_name']} has a manually overridden share weight.")
        participants.append(
            {
                **contribution,
                "role": str(override.get("role") or "Miner").strip() or "Miner",
                "source": "ledger",
                "compensation_method": method,
                "fixed_percentage": fixed_rate,
                "share_weight": share_weight.quantize(WEIGHT, rounding=ROUND_HALF_UP) if method == "shares" else None,
                "share_weight_overridden": share_overridden,
                "notes": str(override.get("notes") or "").strip() or None,
            }
        )

    for raw in raw_rows:
        if str(raw.get("source") or "manual") not in {"manual", "linked_character"}:
            continue
        name = str(raw.get("display_name") or "").strip()
        if not name:
            raise SettlementValidationError("Every manual participant needs a display name.")
        method = str(raw.get("compensation_method") or "shares")
        if method not in COMPENSATION_METHODS:
            raise SettlementValidationError(f"{name} uses an unsupported compensation method.")
        entered = decimal_value(raw.get("compensation_value"), f"{name} compensation")
        if entered < 0:
            raise SettlementValidationError(f"{name} compensation cannot be negative.")
        fixed_rate = normalize_percentage(entered, f"{name} fixed percentage") if method == "fixed_percentage" else None
        linked_character_id = int(raw["character_id"]) if raw.get("character_id") else None
        participants.append(
            {
                "character_id": linked_character_id,
                "display_name": name,
                "ore_types": [],
                "quantity": ZERO,
                "volume": ZERO,
                "estimated_value": ZERO,
                "basis_value": ZERO,
                "contribution_percentage": ZERO,
                "auto_share_weight": ZERO,
                "role": str(raw.get("role") or "Other").strip() or "Other",
                "source": "linked_character" if linked_character_id else "manual",
                "compensation_method": method,
                "fixed_percentage": fixed_rate,
                "share_weight": entered.quantize(WEIGHT, rounding=ROUND_HALF_UP) if method == "shares" else None,
                "share_weight_overridden": method == "shares",
                "notes": str(raw.get("notes") or "").strip() or None,
            }
        )
    return participants, warnings


def calculate_settlement(contribution_rows: Iterable[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    basis = str(payload.get("contribution_basis") or "estimated_raw_value")
    contributions = aggregate_contributions(contribution_rows, basis)
    if not contributions:
        raise SettlementValidationError("The selected operation or date range has no Mining Ledger records.")

    price_source = str(payload.get("price_source") or "manual")
    outputs, warnings = _clean_outputs(payload.get("outputs"), price_source)
    gross_value = money(sum((row["total_value"] for row in outputs), ZERO))
    participants, participant_warnings = _participant_rows(contributions, payload.get("participants"))
    warnings.extend(participant_warnings)

    reserve = payload.get("reserve") if isinstance(payload.get("reserve"), dict) else {}
    reserve_method = str(reserve.get("method") or "none")
    if reserve_method not in RESERVE_METHODS:
        raise SettlementValidationError("Choose a supported operation reserve method.")
    reserve_entered = decimal_value(reserve.get("value"), "Operation reserve")
    if reserve_entered < 0:
        raise SettlementValidationError("Operation reserve cannot be negative.")
    reserve_rate = normalize_percentage(reserve_entered, "Operation reserve") if reserve_method in {"percentage", "output_percentage"} else None
    reserve_value = money(gross_value * reserve_rate if reserve_rate is not None else reserve_entered if reserve_method == "flat_isk" else ZERO)

    deductions = _clean_deductions(payload.get("deductions"), gross_value)
    deduction_total = money(sum((row["calculated_amount"] for row in deductions), ZERO))
    if reserve_value + deduction_total > gross_value:
        raise SettlementValidationError("Operation reserve and expenses cannot exceed gross refined value.")
    distributable = money(gross_value - reserve_value - deduction_total)

    fixed_rate_total = sum((row["fixed_percentage"] or ZERO for row in participants if row["compensation_method"] == "fixed_percentage"), ZERO)
    if fixed_rate_total > 1:
        raise SettlementValidationError("Participant fixed percentages cannot exceed 100% of the distributable pool.")
    fixed_payout_total = ZERO
    for row in participants:
        fixed_payout = money(distributable * row["fixed_percentage"]) if row["fixed_percentage"] is not None else ZERO
        row["payout_isk"] = fixed_payout
        fixed_payout_total += fixed_payout
    fixed_payout_total = money(fixed_payout_total)
    share_pool = money(distributable - fixed_payout_total)
    share_rows = [(index, row["share_weight"] or ZERO) for index, row in enumerate(participants) if row["compensation_method"] == "shares"]
    if share_pool > 0:
        allocations = allocate_money(share_pool, share_rows)
        for index, amount in allocations.items():
            participants[index]["payout_isk"] += amount

    participant_payout_total = money(sum((row["payout_isk"] for row in participants), ZERO))
    unallocated = money(gross_value - reserve_value - deduction_total - participant_payout_total)
    if abs(unallocated) > MONEY:
        raise SettlementValidationError("The settlement does not reconcile.")
    for row in participants:
        row["payout_isk"] = money(row["payout_isk"])
        row["payout_ratio"] = (row["payout_isk"] / distributable).quantize(RATE, rounding=ROUND_HALF_UP) if distributable > 0 else ZERO
        if row["payout_isk"] == 0:
            warnings.append(f"{row['display_name']} has no calculated payout.")

    source_value = money(sum((row["estimated_value"] for row in contributions), ZERO))
    source_volume = sum((row["volume"] for row in contributions), ZERO)
    source_quantity = sum((row["quantity"] for row in contributions), ZERO)
    if source_value > 0 and gross_value > 0:
        difference = abs(gross_value - source_value) / source_value
        if difference >= Decimal("0.25"):
            warnings.append("Actual refined output value differs from estimated raw contribution value by at least 25%.")
    if payload.get("refining_pilot_name") and not payload.get("refining_pilot_character_id"):
        warnings.append("The refining pilot is not linked to an EQM character.")

    stated_refine = normalize_percentage(payload.get("stated_refine_percent"), "Stated refine percentage") if payload.get("stated_refine_percent") not in (None, "") else None
    return {
        "contribution_basis": basis,
        "price_source": price_source,
        "outputs": outputs,
        "participants": participants,
        "deductions": deductions,
        "reserve_method": reserve_method,
        "reserve_entered_value": reserve_entered,
        "reserve_normalized_percentage": reserve_rate,
        "stated_refine_percent": stated_refine,
        "source_entry_count": len(list(contribution_rows)) if isinstance(contribution_rows, list) else 0,
        "source_quantity": source_quantity,
        "source_volume": source_volume,
        "source_estimated_value": source_value,
        "gross_value": gross_value,
        "reserve_value": reserve_value,
        "deduction_total": deduction_total,
        "distributable_value": distributable,
        "fixed_payout_total": fixed_payout_total,
        "share_pool_value": share_pool,
        "participant_payout_total": participant_payout_total,
        "unallocated_remainder": unallocated,
        "warnings": list(dict.fromkeys(warnings)),
    }
