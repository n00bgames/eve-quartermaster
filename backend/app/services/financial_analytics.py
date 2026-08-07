from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import median
from typing import Any

from app.services.metric_registry import aggregate_metric_values, derive_metric_series, metric_definition


def daily_closing_points(rows: list[Any]) -> list[dict[str, Any]]:
    latest: dict[str, Any] = {}
    for row in rows:
        day = row.recorded_at.date().isoformat()
        previous = latest.get(day)
        if previous is None or (row.recorded_at, row.id) > (previous.recorded_at, previous.id):
            latest[day] = row
    return [{"date": day, "value": float(row.balance)} for day, row in sorted(latest.items())]


def derived_values(metric_key: str, transform: str, points: list[dict[str, Any]]) -> list[float]:
    definition = metric_definition(metric_key)
    derived = next((item for item in definition["derivedMetrics"] if item["transform"] == transform), None)
    if derived is None:
        raise ValueError(f"Metric {metric_key!r} does not declare the {transform!r} transform")
    return [
        float(point["value"])
        for point in derive_metric_series(metric_key, points)[derived["metric"]]
        if point["value"] is not None
    ]


def wallet_statistics(points: list[dict[str, Any]], *, current_balance: float | None = None, metric_key: str = "character_wallet.balance") -> dict[str, Any]:
    if not points:
        return {
            "current": current_balance,
            "net_change": 0.0,
            "percentage_growth": None,
            "average_daily_growth": 0.0,
            "largest_gain": 0.0,
            "largest_loss": 0.0,
        }
    first = float(points[0]["value"])
    latest = float(current_balance if current_balance is not None else points[-1]["value"])
    changes = derived_values(metric_key, "daily_delta", points)
    elapsed_days = max(1, (datetime.fromisoformat(points[-1]["date"]) - datetime.fromisoformat(points[0]["date"])).days)
    net = float(aggregate_metric_values([first, latest], "delta") or 0)
    growth_points = [
        {"date": points[0]["date"], "value": first},
        {"date": points[-1]["date"], "value": latest},
    ]
    growth = derived_values(metric_key, "growth_percent", growth_points)
    return {
        "current": latest,
        "net_change": net,
        "percentage_growth": growth[-1] if growth else None,
        "average_daily_growth": net / elapsed_days,
        "largest_gain": max([0.0, *changes]),
        "largest_loss": min([0.0, *changes]),
    }


def grouped_daily_points(rows: list[Any], group_attribute: str) -> list[dict[str, Any]]:
    latest: dict[tuple[str, int], Any] = {}
    for row in rows:
        day = row.recorded_at.date().isoformat()
        key = (day, int(getattr(row, group_attribute)))
        previous = latest.get(key)
        if previous is None or (row.recorded_at, row.id) > (previous.recorded_at, previous.id):
            latest[key] = row
    observations: dict[str, dict[int, float]] = defaultdict(dict)
    for (day, group_id), row in latest.items():
        observations[day][group_id] = float(row.balance)
    state: dict[int, float] = {}
    points: list[dict[str, Any]] = []
    for day in sorted(observations):
        state.update(observations[day])
        points.append({"date": day, "value": sum(state.values())})
    return points


def corporation_daily_points(rows: list[Any]) -> list[dict[str, Any]]:
    return grouped_daily_points(rows, "character_id")


def corporation_division_daily_points(rows: list[Any]) -> list[dict[str, Any]]:
    return grouped_daily_points(rows, "division")


def combine_daily_series(*series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dates = sorted({str(point["date"]) for points in series for point in points})
    values_by_series = [{str(point["date"]): float(point["value"]) for point in points} for points in series]
    current = [0.0 for _ in series]
    combined: list[dict[str, Any]] = []
    for day in dates:
        for index, values in enumerate(values_by_series):
            if day in values:
                current[index] = values[day]
        combined.append({"date": day, "value": sum(current)})
    return combined


def distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"median": None, "average": None}
    return {"median": float(median(values)), "average": sum(values) / len(values)}
