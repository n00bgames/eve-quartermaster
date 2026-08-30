from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from app.core.config import get_settings


logger = logging.getLogger(__name__)
SCHEMA_VERSION = "eqm.hypernet-economics.v1"
VALID_ENGINES = {"python", "shadow", "rust"}
CENT = Decimal("100")


def _cents(value: Decimal | int | float | str | None) -> int | None:
    if value is None:
        return None
    return int((Decimal(str(value)) * CENT).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _money_from_cents(value: int | None) -> Decimal | None:
    if value is None:
        return None
    return (Decimal(value) / CENT).quantize(Decimal("0.01"))


def _run_rust(payload: dict[str, Any], *, binary: str, timeout: float) -> dict[str, Any]:
    completed = subprocess.run(
        [binary, "hypernet-economics", "--input", "-"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "Rust HyperNet economics failed").strip())
    result = json.loads(completed.stdout)
    if not isinstance(result, dict):
        raise RuntimeError("Rust HyperNet economics returned a non-object response")
    return result


def _engine() -> tuple[str, str, float]:
    settings = get_settings()
    requested = settings.eqm_hypernet_engine.strip().lower()
    if requested not in VALID_ENGINES:
        logger.warning("Unknown EQM HyperNet engine %r; using Python", requested)
        requested = "python"
    return requested, settings.eqm_core_binary, settings.eqm_core_timeout_seconds


def _offer_result(raw: dict[str, Any]) -> dict[str, Any]:
    def money_group(group: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in raw[group].items():
            if key.endswith("_cents"):
                result[key.removesuffix("_cents")] = _money_from_cents(value)
            else:
                result[key] = value
        return result

    return {
        "financials": money_group("financials"),
        "seeded_scenario": money_group("seeded_scenario"),
        "progress": raw["progress"],
    }


def _normalized(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {key: _normalized(item) for key, item in sorted(value.items()) if not key.startswith("engine_")}
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    return value


def _select(
    *,
    python_result: dict[str, Any],
    payload: dict[str, Any],
    convert: Any,
) -> dict[str, Any]:
    requested, binary, timeout = _engine()
    if requested == "python":
        return {**python_result, "engine_requested": "python", "engine_used": "python"}
    if requested == "shadow":
        try:
            rust_result = convert(_run_rust(payload, binary=binary, timeout=timeout))
            match = _normalized(python_result) == _normalized(rust_result)
            if not match:
                logger.warning("HyperNet economics shadow mismatch operation=%s", payload["operation"])
            return {
                **python_result,
                "engine_requested": "shadow",
                "engine_used": "python-shadow",
                "engine_shadow_match": match,
            }
        except Exception as error:  # pragma: no cover - defensive runtime fallback
            logger.exception("Rust HyperNet economics shadow failed; Python result retained")
            return {
                **python_result,
                "engine_requested": "shadow",
                "engine_used": "python-shadow-error",
                "engine_shadow_match": False,
                "engine_fallback_reason": str(error)[:300],
            }
    try:
        result = convert(_run_rust(payload, binary=binary, timeout=timeout))
        return {**result, "engine_requested": "rust", "engine_used": "rust"}
    except Exception as error:  # pragma: no cover - defensive runtime fallback
        logger.exception("Rust HyperNet economics failed; Python fallback retained")
        return {
            **python_result,
            "engine_requested": "rust",
            "engine_used": "python-fallback",
            "engine_fallback_reason": str(error)[:300],
        }


def evaluate_offer_with_engine(
    *,
    python_result: dict[str, Any],
    total_offer_price: Decimal,
    total_nodes: int,
    seller_owned_nodes: int,
    hypercores_required: int,
    hypercore_unit_cost: Decimal,
    acquisition_cost: Decimal,
    desired_profit: Decimal = Decimal("0"),
    jita_sell: Decimal | None = None,
    local_sell: Decimal | None = None,
    created_at: datetime | None = None,
    snapshots: Iterable[object] = (),
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "operation": "offer",
        "offer": {
            "total_offer_price_cents": _cents(total_offer_price),
            "total_nodes": total_nodes,
            "seller_owned_nodes": seller_owned_nodes,
            "hypercores_required": hypercores_required,
            "hypercore_unit_cost_cents": _cents(hypercore_unit_cost),
            "acquisition_cost_cents": _cents(acquisition_cost),
            "desired_profit_cents": _cents(desired_profit),
            "jita_sell_cents": _cents(jita_sell),
            "local_sell_cents": _cents(local_sell),
            "created_at": created_at.isoformat() if created_at else None,
            "snapshots": [
                {
                    "id": getattr(row, "id", 0) or 0,
                    "captured_at": row.captured_at.isoformat(),
                    "nodes_sold": int(row.nodes_sold or 0),
                    "seller_owned_nodes": int(row.seller_owned_nodes or 0),
                }
                for row in snapshots
            ],
        },
    }
    return _select(python_result=python_result, payload=payload, convert=_offer_result)


def evaluate_participation_with_engine(
    *,
    python_result: dict[str, Any],
    total_nodes: int,
    nodes_purchased: int,
    node_price: Decimal,
    outcome: str,
    item_value_at_completion: Decimal | None,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "operation": "participation",
        "participation": {
            "total_nodes": total_nodes,
            "nodes_purchased": nodes_purchased,
            "node_price_cents": _cents(node_price),
            "outcome": outcome,
            "item_value_at_completion_cents": _cents(item_value_at_completion),
        },
    }

    def convert(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "win_probability_percent": raw["win_probability_percent_ten_thousandths"] / 10_000,
            "total_spent": _money_from_cents(raw["total_spent_cents"]),
            "item_value_at_completion": _money_from_cents(raw["item_value_at_completion_cents"]),
            "profit_loss": _money_from_cents(raw["profit_loss_cents"]),
        }

    return _select(python_result=python_result, payload=payload, convert=convert)


def evaluate_reconciliation_with_engine(*, python_result: dict[str, Any], **values: Any) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "operation": "reconciliation",
        "reconciliation": {
            "status": values["status"],
            "winner": values["winner"],
            "total_offer_price_cents": _cents(values["total_offer_price"]),
            "total_nodes": values["total_nodes"],
            "seller_owned_nodes": values["seller_owned_nodes"],
            "hypercores_required": values["hypercores_required"],
            "hypercore_unit_cost_cents": _cents(values["hypercore_unit_cost"]),
            "acquisition_cost_cents": _cents(values["acquisition_cost"]),
            "actual_hypercore_cost_cents": _cents(values.get("actual_hypercore_cost")),
            "payout_cents": _cents(values.get("payout")),
            "final_market_value_cents": _cents(values.get("final_market_value")),
            "final_profit_cents": _cents(values.get("final_profit")),
        },
    }

    def convert(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "actual_hypercore_cost": _money_from_cents(raw["actual_hypercore_cost_cents"]),
            "seeded_spend": _money_from_cents(raw["seeded_spend_cents"]),
            "final_profit": _money_from_cents(raw["final_profit_cents"]),
            "item_outcome": raw["item_outcome"],
        }

    return _select(python_result=python_result, payload=payload, convert=convert)
