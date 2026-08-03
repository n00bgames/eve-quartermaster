from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Protocol


MONEY = Decimal("0.01")
FEE_RATE = Decimal("0.05")


def decimal_value(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0))


def money(value: Decimal | int | float | str | None) -> Decimal:
    return decimal_value(value).quantize(MONEY, rounding=ROUND_HALF_UP)


class HyperNetDataSource(Protocol):
    key: str

    def reference(self, supplied_reference: str | None = None) -> str | None: ...


@dataclass(frozen=True)
class ManualHyperNetDataSource:
    key: str = "manual"

    def reference(self, supplied_reference: str | None = None) -> str | None:
        cleaned = (supplied_reference or "").strip()
        return cleaned or None


DATA_SOURCES: dict[str, HyperNetDataSource] = {"manual": ManualHyperNetDataSource()}


def data_source(key: str) -> HyperNetDataSource:
    try:
        return DATA_SOURCES[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported HyperNet data source: {key}") from exc


def offer_financials(
    *,
    total_offer_price: Decimal | int | float | str,
    total_nodes: int,
    hypercores_required: int,
    hypercore_unit_cost: Decimal | int | float | str,
    acquisition_cost: Decimal | int | float | str,
    desired_profit: Decimal | int | float | str = 0,
    jita_sell: Decimal | int | float | str | None = None,
    local_sell: Decimal | int | float | str | None = None,
) -> dict[str, Decimal | None]:
    if total_nodes <= 0:
        raise ValueError("total_nodes must be greater than zero")
    if hypercores_required < 0:
        raise ValueError("hypercores_required cannot be negative")
    gross = money(total_offer_price)
    cores = money(decimal_value(hypercores_required) * decimal_value(hypercore_unit_cost))
    cost_basis = money(acquisition_cost)
    target = money(desired_profit)
    node_price = money(gross / Decimal(total_nodes))
    completion_fee = money(gross * FEE_RATE)
    payout_after_fee = money(gross - completion_fee)
    net_proceeds = money(payout_after_fee - cores)
    profit = money(net_proceeds - cost_basis)
    return_on_cost = money((profit / cost_basis) * 100) if cost_basis else None
    break_even_offer = money((cost_basis + cores) / (Decimal("1") - FEE_RATE))
    minimum_target_offer = money((cost_basis + target + cores) / (Decimal("1") - FEE_RATE))
    maximum_core_unit = None
    if hypercores_required:
        maximum_core_unit = money((gross * (Decimal("1") - FEE_RATE) - cost_basis - target) / Decimal(hypercores_required))
    jita_value = money(jita_sell) if jita_sell is not None else None
    local_value = money(local_sell) if local_sell is not None else None

    def premium(value: Decimal | None) -> Decimal | None:
        return money(((gross - value) / value) * 100) if value else None

    return {
        "node_price": node_price,
        "gross_offer_value": gross,
        "completion_fee": completion_fee,
        "payout_after_fee": payout_after_fee,
        "hypercore_cost": cores,
        "net_proceeds": net_proceeds,
        "profit": profit,
        "return_on_cost_percent": return_on_cost,
        "break_even_offer_price": break_even_offer,
        "break_even_node_price": money(break_even_offer / Decimal(total_nodes)),
        "minimum_offer_for_target_profit": minimum_target_offer,
        "minimum_node_price_for_target_profit": money(minimum_target_offer / Decimal(total_nodes)),
        "maximum_hypercore_unit_cost": maximum_core_unit,
        "premium_over_jita_percent": premium(jita_value),
        "premium_over_local_percent": premium(local_value),
    }


def seeded_node_scenario(
    *,
    total_nodes: int,
    seller_owned_nodes: int,
    node_price: Decimal | int | float | str,
    acquisition_cost: Decimal | int | float | str,
    hypercore_cost: Decimal | int | float | str,
    payout_after_fee: Decimal | int | float | str,
    current_jita_sell: Decimal | int | float | str | None = None,
) -> dict[str, Decimal | bool | None]:
    if total_nodes <= 0:
        raise ValueError("total_nodes must be greater than zero")
    if seller_owned_nodes < 0 or seller_owned_nodes > total_nodes:
        raise ValueError("seller_owned_nodes must be between zero and total_nodes")
    seller_probability = Decimal(seller_owned_nodes) / Decimal(total_nodes)
    external_probability = Decimal("1") - seller_probability
    seeded_spend = money(Decimal(seller_owned_nodes) * decimal_value(node_price))
    cost_basis = money(acquisition_cost)
    cores = money(hypercore_cost)
    payout = money(payout_after_fee)
    external_result = money(payout - cores - seeded_spend - cost_basis)
    seller_cash_result = money(payout - cores - seeded_spend)
    mark_to_cost = money(seller_cash_result)
    jita_value = money(current_jita_sell) if current_jita_sell is not None else None
    mark_to_jita = money(seller_cash_result + jita_value - cost_basis) if jita_value is not None else None
    retained_value_result = mark_to_jita if mark_to_jita is not None else mark_to_cost
    expected_result = money(external_probability * external_result + seller_probability * retained_value_result)
    maximum_loss = money(max(Decimal("0"), -min(external_result, retained_value_result)))
    capital_tied_up = money(cost_basis + cores + seeded_spend)
    return {
        "seller_win_probability_percent": money(seller_probability * 100),
        "external_win_probability_percent": money(external_probability * 100),
        "seller_node_spend": seeded_spend,
        "cash_result_if_external_wins": external_result,
        "cash_result_if_seller_wins": seller_cash_result,
        "seller_wins_item_retained": True,
        "seller_win_mark_to_cost_result": mark_to_cost,
        "seller_win_mark_to_jita_result": mark_to_jita,
        "expected_monetary_result": expected_result,
        "maximum_possible_loss": maximum_loss,
        "capital_tied_up": capital_tied_up,
        "genuinely_profitable": expected_result > 0,
    }


def progress_metrics(
    *,
    created_at: datetime,
    total_nodes: int,
    snapshots: Iterable[object],
) -> dict[str, float | str | None]:
    rows = sorted(snapshots, key=lambda row: (row.captured_at, getattr(row, "id", 0) or 0))
    organic_rows = [row for row in rows if int(row.nodes_sold or 0) - int(row.seller_owned_nodes or 0) > 0]
    first_organic = organic_rows[0].captured_at if organic_rows else None
    latest = rows[-1] if rows else None
    elapsed_hours = None
    organic_per_hour = None
    if latest and latest.captured_at > created_at:
        elapsed_hours = (latest.captured_at - created_at).total_seconds() / 3600
        organic_nodes = max(0, int(latest.nodes_sold or 0) - int(latest.seller_owned_nodes or 0))
        organic_per_hour = organic_nodes / elapsed_hours if elapsed_hours > 0 else None
    trajectory_hours = None
    if latest and organic_per_hour and organic_per_hour > 0:
        trajectory_hours = max(0, total_nodes - int(latest.nodes_sold or 0)) / organic_per_hour
    return {
        "first_organic_node_at": first_organic.isoformat() if first_organic else None,
        "hours_to_first_organic_node": (first_organic - created_at).total_seconds() / 3600 if first_organic else None,
        "organic_nodes_per_hour": organic_per_hour,
        "estimated_hours_to_completion": trajectory_hours,
    }
