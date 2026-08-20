from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable


AGGREGATIONS = frozenset({"sum", "average", "latest", "min", "max", "delta", "histogram"})
TRANSFORMS = frozenset({"daily_delta", "period_delta", "growth_percent", "rolling_average"})


def derived_metric(
    key: str,
    label: str,
    unit: str,
    transform: str,
    *,
    window_days: int | None = None,
    requires_absolute: bool = False,
) -> dict[str, Any]:
    return {
        "metric": key,
        "label": label,
        "unit": unit,
        "transform": transform,
        "windowDays": window_days,
        "valueKind": "derived",
        "materialized": False,
        "requiresAbsolute": requires_absolute,
        "chartTypes": ["line", "bar"],
    }


def wallet_derived(prefix: str) -> list[dict[str, Any]]:
    return [
        derived_metric(f"{prefix}.delta.daily", "Daily wallet change", "ISK", "daily_delta"),
        derived_metric(f"{prefix}.delta.weekly", "Weekly wallet change", "ISK", "period_delta", window_days=7),
        derived_metric(f"{prefix}.growth.percent", "Wallet growth", "%", "growth_percent", requires_absolute=True),
        derived_metric(f"{prefix}.rolling_average_30d", "30-day wallet average", "ISK", "rolling_average", window_days=30, requires_absolute=True),
    ]


def metric(
    key: str,
    label: str,
    unit: str,
    category: str,
    *,
    entity_aggregation: str,
    time_aggregation: str,
    supported_aggregations: list[str],
    value_kind: str = "gauge",
    supports_character: bool,
    supports_corporation: bool,
    chart_types: list[str],
    transforms: list[str] | None = None,
    derived_metrics: list[dict[str, Any]] | None = None,
    dimensions: list[str] | None = None,
    privacy: str = "section",
    description: str,
) -> dict[str, Any]:
    derived = [
        {**item, "sourceMetric": key, "privacy": privacy}
        for item in (derived_metrics or [])
    ]
    return {
        "metric": key,
        "version": 1,
        "label": label,
        "unit": unit,
        # Retained for compatibility; entityAggregation and timeAggregation remove the ambiguity.
        "aggregation": entity_aggregation,
        "entityAggregation": entity_aggregation,
        "timeAggregation": time_aggregation,
        "supportedAggregations": supported_aggregations,
        "supportedTransforms": transforms or [],
        "derivedMetrics": derived,
        "valueKind": value_kind,
        "dimensions": dimensions or [],
        "privacy": privacy,
        "category": category,
        "supportsCharacter": supports_character,
        "supportsCorporation": supports_corporation,
        "chartTypes": chart_types,
        "deprecated": False,
        "registered": True,
        "description": description,
    }


GAUGE_AGGREGATIONS = ["latest", "delta", "average", "min", "max", "histogram"]
ADDITIVE_GAUGE_AGGREGATIONS = ["sum", *GAUGE_AGGREGATIONS]
WALLET_TRANSFORMS = ["daily_delta", "period_delta", "growth_percent", "rolling_average"]


METRIC_CATALOG: list[dict[str, Any]] = [
    metric("skill_points.total", "Total Skill Points", "SP", "Skills", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["daily_delta", "rolling_average"], supports_character=True, supports_corporation=False, chart_types=["line", "bar", "histogram"], description="Current trained skill points per character."),
    metric("skill_points.lost", "Skill Point History", "SP", "Skills", entity_aggregation="sum", time_aggregation="sum", supported_aggregations=["sum", "average", "max", "histogram"], value_kind="flow", supports_character=True, supports_corporation=False, chart_types=["bar", "histogram"], description="Skill points removed during the selected period."),
    metric("skills.count", "Trained Skill Count", "skills", "Skills", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["daily_delta", "rolling_average"], supports_character=True, supports_corporation=False, chart_types=["line", "bar"], description="Current count of trained skills per character."),
    metric("skill_queue.count", "Skill Queue Count", "skills", "Skills", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["daily_delta", "rolling_average"], supports_character=True, supports_corporation=False, chart_types=["line", "bar"], description="Current number of queued skills per character."),
    metric("skill_points.category", "Skill Points by Category", "SP", "Skills", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, dimensions=["category"], supports_character=True, supports_corporation=False, chart_types=["bar", "pie", "stacked_bar"], description="Current trained skill points grouped by skill category."),
    metric("skill_points.category_lost", "Skill Point History by Category", "SP", "Skills", entity_aggregation="sum", time_aggregation="sum", supported_aggregations=["sum", "average", "max", "histogram"], value_kind="flow", dimensions=["category"], supports_character=True, supports_corporation=False, chart_types=["bar", "pie"], description="Skill points removed during the selected period, grouped by category."),
    metric("standings.base", "NPC Base Standing", "standing", "Standings", entity_aggregation="average", time_aggregation="latest", supported_aggregations=GAUGE_AGGREGATIONS, transforms=["period_delta"], dimensions=["source_type", "source_eve_id", "source_name"], supports_character=True, supports_corporation=False, chart_types=["bar"], description="Unmodified ESI standing per character and NPC agent, corporation, or faction. Social-skill modifiers are deliberately excluded from historical movement."),
    metric("members.count", "Corporation Members", "members", "Corporations", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["daily_delta", "rolling_average"], supports_character=False, supports_corporation=True, chart_types=["line", "bar"], description="Current ESI-reported corporation member count."),
    metric("wallet.balance", "Corporation Wallet Balance", "ISK", "Finance", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=WALLET_TRANSFORMS, derived_metrics=wallet_derived("wallet"), privacy="corporation_authorized", supports_character=False, supports_corporation=True, chart_types=["line", "bar"], description="Current combined balance of synced corporation wallet divisions."),
    metric("character_wallet.balance", "Character Wallet Balance", "ISK", "Finance", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=WALLET_TRANSFORMS, derived_metrics=wallet_derived("character_wallet"), privacy="owner_controlled", supports_character=True, supports_corporation=True, chart_types=["line", "bar", "distribution"], description="Current character wallet balance, subject to owner privacy and corporation opt-in."),
    metric("wallet.division_balance", "Wallet Division Balance", "ISK", "Finance", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["daily_delta", "rolling_average"], dimensions=["division"], privacy="corporation_authorized", supports_character=False, supports_corporation=True, chart_types=["line", "bar", "stacked_bar", "pie"], description="Current corporation wallet balance grouped by division."),
    metric("assets.rows", "Asset Rows", "rows", "Assets", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["daily_delta", "rolling_average"], supports_character=True, supports_corporation=True, chart_types=["line", "bar", "histogram"], description="Current number of visible asset stacks."),
    metric("assets.units", "Asset Units", "units", "Assets", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["daily_delta", "rolling_average"], supports_character=True, supports_corporation=True, chart_types=["line", "bar", "histogram"], description="Current quantity of visible asset units."),
    metric("blueprints.count", "Blueprint Count", "BPs", "Industry", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["daily_delta", "rolling_average"], supports_character=True, supports_corporation=True, chart_types=["line", "bar"], description="Current count of blueprint instances, including visible in-use research blueprints."),
    metric("blueprint.quantity", "Blueprint Quantity", "BPs", "Industry", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, dimensions=["blueprint_type_id", "blueprint", "material_efficiency", "time_efficiency", "is_copy", "inventory_state"], supports_character=True, supports_corporation=True, chart_types=["bar", "pie", "histogram"], description="Current blueprint quantity grouped by blueprint properties and inventory state."),
    metric("killboard.kills", "Kills", "killmails", "Combat", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["period_delta", "rolling_average"], supports_character=True, supports_corporation=True, chart_types=["line", "bar"], description="Current cumulative count of canonical ESI killmails on which the tracked entity participated as an attacker."),
    metric("killboard.losses", "Losses", "killmails", "Combat", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["period_delta", "rolling_average"], supports_character=True, supports_corporation=True, chart_types=["line", "bar"], description="Current cumulative count of canonical ESI killmails on which the tracked entity was the victim."),
    metric("killboard.isk_destroyed", "ISK Destroyed", "ISK", "Combat", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["period_delta", "rolling_average"], supports_character=True, supports_corporation=True, chart_types=["line", "bar"], description="Current cumulative zKill-estimated value of canonical kills attributed to a tracked entity."),
    metric("killboard.isk_lost", "ISK Lost", "ISK", "Combat", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["period_delta", "rolling_average"], supports_character=True, supports_corporation=True, chart_types=["line", "bar"], description="Current cumulative zKill-estimated value of canonical losses attributed to a tracked entity."),
    metric("killboard.solo_kills", "Solo Kills", "killmails", "Combat", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["period_delta", "rolling_average"], supports_character=True, supports_corporation=True, chart_types=["line", "bar"], description="Current cumulative kills classified as solo by zKillboard enrichment."),
    metric("killboard.final_blows", "Final Blows", "killmails", "Combat", entity_aggregation="sum", time_aggregation="latest", supported_aggregations=ADDITIVE_GAUGE_AGGREGATIONS, transforms=["period_delta", "rolling_average"], supports_character=True, supports_corporation=True, chart_types=["line", "bar"], description="Current cumulative canonical attacker rows carrying the final-blow flag."),
]


METRIC_DEFINITIONS = {item["metric"]: item for item in METRIC_CATALOG}
DERIVED_METRIC_DEFINITIONS = {
    derived["metric"]: derived
    for definition in METRIC_CATALOG
    for derived in definition["derivedMetrics"]
}


def metric_definition(metric_key: str) -> dict[str, Any]:
    definition = METRIC_DEFINITIONS.get(metric_key)
    if definition is None:
        raise ValueError(f"Metric {metric_key!r} is not registered; add its aggregation contract before recording it")
    return definition


def derived_metric_definition(metric_key: str) -> dict[str, Any]:
    definition = DERIVED_METRIC_DEFINITIONS.get(metric_key)
    if definition is None:
        raise ValueError(f"Derived metric {metric_key!r} is not registered")
    return definition


def validate_metric_registry() -> None:
    if len(METRIC_DEFINITIONS) != len(METRIC_CATALOG):
        raise ValueError("Metric registry contains duplicate keys")
    all_derived = [derived for definition in METRIC_CATALOG for derived in definition["derivedMetrics"]]
    if len(DERIVED_METRIC_DEFINITIONS) != len(all_derived):
        raise ValueError("Metric registry contains duplicate derived metric keys")
    if set(DERIVED_METRIC_DEFINITIONS).intersection(METRIC_DEFINITIONS):
        raise ValueError("Derived metric keys cannot replace collected metric keys")
    for definition in METRIC_CATALOG:
        if definition["entityAggregation"] not in AGGREGATIONS:
            raise ValueError(f"Unsupported entity aggregation for {definition['metric']}")
        if definition["timeAggregation"] not in AGGREGATIONS:
            raise ValueError(f"Unsupported time aggregation for {definition['metric']}")
        if not set(definition["supportedAggregations"]).issubset(AGGREGATIONS):
            raise ValueError(f"Unsupported aggregation option for {definition['metric']}")
        if definition["timeAggregation"] not in definition["supportedAggregations"]:
            raise ValueError(f"Default time aggregation is not supported for {definition['metric']}")
        if not set(definition["supportedTransforms"]).issubset(TRANSFORMS):
            raise ValueError(f"Unsupported transform for {definition['metric']}")
        for derived in definition["derivedMetrics"]:
            if derived["sourceMetric"] != definition["metric"]:
                raise ValueError(f"Derived metric source mismatch for {derived['metric']}")
            if derived["transform"] not in definition["supportedTransforms"]:
                raise ValueError(f"Derived metric transform is not supported for {definition['metric']}")
            if derived["windowDays"] is not None and int(derived["windowDays"]) < 1:
                raise ValueError(f"Derived metric window must be positive for {derived['metric']}")


def aggregate_metric_values(values: Iterable[int | float], aggregation: str, *, histogram_bins: int = 10) -> float | dict[str, Any] | None:
    rows = [float(value) for value in values]
    if aggregation not in AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation {aggregation!r}")
    if not rows:
        return None
    if aggregation == "latest":
        return rows[-1]
    if aggregation == "sum":
        return sum(rows)
    if aggregation == "average":
        return sum(rows) / len(rows)
    if aggregation == "min":
        return min(rows)
    if aggregation == "max":
        return max(rows)
    if aggregation == "delta":
        return rows[-1] - rows[0]
    low, high = min(rows), max(rows)
    if low == high:
        return {"min": low, "max": high, "bins": [{"start": low, "end": high, "count": len(rows)}]}
    bin_count = max(1, min(int(histogram_bins), len(rows)))
    width = (high - low) / bin_count
    counts = [0] * bin_count
    for value in rows:
        index = min(bin_count - 1, int((value - low) / width))
        counts[index] += 1
    return {
        "min": low,
        "max": high,
        "bins": [
            {"start": low + index * width, "end": low + (index + 1) * width, "count": count}
            for index, count in enumerate(counts)
        ],
    }


def _dated_points(points: Iterable[dict[str, Any]]) -> list[tuple[date, float]]:
    normalized = [
        (date.fromisoformat(str(point["date"])[:10]), float(point["value"]))
        for point in points
    ]
    return sorted(normalized, key=lambda point: point[0])


def _derive_series(definition: dict[str, Any], points: list[tuple[date, float]]) -> list[dict[str, float | str | None]]:
    transform = definition["transform"]
    if not points:
        return []
    if transform == "daily_delta":
        return [
            {"date": points[index][0].isoformat(), "value": points[index][1] - points[index - 1][1]}
            for index in range(1, len(points))
        ]
    if transform == "period_delta":
        window = timedelta(days=int(definition["windowDays"]))
        result: list[dict[str, float | str | None]] = []
        for index, (current_day, current_value) in enumerate(points):
            eligible = [point for point in points[:index] if point[0] <= current_day - window]
            if eligible:
                result.append({"date": current_day.isoformat(), "value": current_value - eligible[-1][1]})
        return result
    if transform == "growth_percent":
        baseline = points[0][1]
        return [
            {"date": day.isoformat(), "value": ((value - baseline) / baseline * 100) if baseline else None}
            for day, value in points
        ]
    if transform == "rolling_average":
        window = timedelta(days=int(definition["windowDays"]) - 1)
        return [
            {
                "date": current_day.isoformat(),
                "value": sum(value for day, value in points if current_day - window <= day <= current_day)
                / len([1 for day, _ in points if current_day - window <= day <= current_day]),
            }
            for current_day, _ in points
        ]
    raise ValueError(f"Unsupported derived transform {transform!r}")


def derive_metric_series(metric_key: str, points: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, float | str | None]]]:
    definition = metric_definition(metric_key)
    normalized = _dated_points(points)
    return {
        derived["metric"]: _derive_series(derived, normalized)
        for derived in definition["derivedMetrics"]
    }


validate_metric_registry()
