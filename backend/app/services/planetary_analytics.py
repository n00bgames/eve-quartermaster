from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import EveType, PlanetaryColony, PlanetaryPin, PlanetaryRoute
from app.models.planetary_analytics import PlanetaryProductionSnapshot
from app.services.planetary_industry import (
    DEFAULT_DECAY_FACTOR,
    DEFAULT_NOISE_FACTOR,
    extractor_dogma_factors,
    extractor_program_projection,
)
from app.services.planetary_analytics_engine import evaluate_planetary_analytics_with_engine

# Stable SDE inventory group identifiers for PI products.
PI_TIER_BY_GROUP_ID = {
    1033: "P0",
    1042: "P1",
    1034: "P2",
    1040: "P3",
    1041: "P4",
}
PI_TIER_LABELS = {
    "P0": "Raw resources",
    "P1": "Basic commodities",
    "P2": "Refined commodities",
    "P3": "Specialized commodities",
    "P4": "Advanced commodities",
}
FACTORY_CYCLE_SECONDS = {"P1": 1800, "P2": 3600, "P3": 3600, "P4": 3600}


def commodity_tier(eve_type: EveType | None) -> str | None:
    return PI_TIER_BY_GROUP_ID.get(eve_type.group_id) if eve_type else None


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _elapsed_days(start: datetime | None, end: datetime) -> float:
    start = _aware(start)
    end = _aware(end) or end
    if start is None or start >= end:
        return 0
    return min((end - start).total_seconds() / 86400, 30)


def _previous_rows(
    db: Session,
    character_id: int,
) -> tuple[datetime | None, dict[tuple[int, int], PlanetaryProductionSnapshot]]:
    captured_at = db.scalar(
        select(func.max(PlanetaryProductionSnapshot.captured_at)).where(
            PlanetaryProductionSnapshot.character_id == character_id
        )
    )
    if captured_at is None:
        return None, {}
    rows = db.scalars(
        select(PlanetaryProductionSnapshot).where(
            PlanetaryProductionSnapshot.character_id == character_id,
            PlanetaryProductionSnapshot.captured_at == captured_at,
        )
    ).all()
    return captured_at, {(row.pin_id, row.product_type_id): row for row in rows}


def record_planetary_production_snapshot(
    db: Session,
    character_id: int,
    captured_at: datetime | None = None,
) -> int:
    captured_at = _aware(captured_at) or datetime.now(timezone.utc)
    previous_at, previous = _previous_rows(db, character_id)
    colonies = db.scalars(
        select(PlanetaryColony)
        .where(PlanetaryColony.character_id == character_id)
        .options(
            selectinload(PlanetaryColony.pins),
            selectinload(PlanetaryColony.routes).selectinload(PlanetaryRoute.content_type),
        )
    ).all()
    extractor_type_ids = {
        pin.type_id
        for colony in colonies
        for pin in colony.pins
        if pin.extractor_cycle_time is not None
    }
    dogma = extractor_dogma_factors(db, extractor_type_ids)
    type_ids = {
        int(pin.extractor_product_type_id)
        for colony in colonies
        for pin in colony.pins
        if pin.extractor_product_type_id
    } | {
        int(route.content_type_id)
        for colony in colonies
        for route in colony.routes
    }
    type_rows = {
        row.type_id: row
        for row in db.scalars(select(EveType).where(EveType.type_id.in_(type_ids))).all()
    }
    created = 0

    for colony in colonies:
        inbound = {route.destination_pin_id for route in colony.routes}
        outbound: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for route in colony.routes:
            outbound[route.source_pin_id][route.content_type_id] += float(route.quantity or 0)

        for pin in colony.pins:
            if pin.extractor_product_type_id and pin.extractor_cycle_time:
                product = type_rows.get(pin.extractor_product_type_id)
                tier = commodity_tier(product)
                if tier != "P0":
                    continue
                decay, noise, _ = dogma.get(
                    pin.type_id,
                    (DEFAULT_DECAY_FACTOR, DEFAULT_NOISE_FACTOR, "documented_default"),
                )
                projection = extractor_program_projection(
                    install_time=pin.install_time,
                    expiry_time=pin.expiry_time,
                    cycle_time=pin.extractor_cycle_time,
                    quantity_per_cycle=pin.extractor_qty_per_cycle,
                    decay_factor=decay,
                    noise_factor=noise,
                    now=captured_at,
                )
                rate = float(projection["average_daily_output"])
                remaining = float(projection["remaining_output"])
                if _aware(pin.expiry_time) and _aware(pin.expiry_time) <= captured_at:
                    rate = 0
                prior = previous.get((pin.pin_id, pin.extractor_product_type_id))
                produced = 0.0
                if (
                    prior
                    and _aware(prior.program_started_at) == _aware(pin.install_time)
                    and prior.projected_remaining_units is not None
                ):
                    produced = max(float(prior.projected_remaining_units) - remaining, 0)
                db.add(
                    _snapshot(
                        character_id,
                        captured_at,
                        previous_at,
                        colony,
                        pin,
                        product,
                        tier,
                        "extractor",
                        rate,
                        remaining,
                        produced,
                        pin.install_time,
                    )
                )
                created += 1

            if pin.schematic_id is None or pin.pin_id not in inbound:
                continue
            for product_type_id, quantity_per_cycle in outbound.get(pin.pin_id, {}).items():
                product = type_rows.get(product_type_id)
                tier = commodity_tier(product)
                cycle_seconds = FACTORY_CYCLE_SECONDS.get(tier or "")
                if not product or not tier or tier == "P0" or not cycle_seconds:
                    continue
                rate = quantity_per_cycle * 86400 / cycle_seconds
                prior = previous.get((pin.pin_id, product_type_id))
                produced = 0.0
                if prior:
                    produced = min(float(prior.projected_units_per_day), rate) * _elapsed_days(
                        previous_at, captured_at
                    )
                db.add(
                    _snapshot(
                        character_id,
                        captured_at,
                        previous_at,
                        colony,
                        pin,
                        product,
                        tier,
                        "factory",
                        rate,
                        None,
                        produced,
                        None,
                    )
                )
                created += 1
    db.flush()
    return created


def _snapshot(
    character_id: int,
    captured_at: datetime,
    previous_at: datetime | None,
    colony: PlanetaryColony,
    pin: PlanetaryPin,
    product: EveType | None,
    tier: str,
    source_kind: str,
    rate: float,
    remaining: float | None,
    produced: float,
    program_started_at: datetime | None,
) -> PlanetaryProductionSnapshot:
    return PlanetaryProductionSnapshot(
        character_id=character_id,
        captured_at=captured_at,
        interval_started_at=previous_at,
        planet_id=colony.planet_id,
        solar_system_id=colony.solar_system_id,
        pin_id=pin.pin_id,
        source_kind=source_kind,
        product_type_id=product.type_id if product else 0,
        commodity_tier=tier,
        unit_volume=float(product.volume or 0) if product else 0,
        projected_units_per_day=max(rate, 0),
        projected_remaining_units=remaining,
        estimated_units_since_previous=max(produced, 0),
        program_started_at=program_started_at,
    )


def planetary_analytics_summary(
    db: Session,
    days: int,
    character_ids: set[int],
    anonymous_character_ids: set[int] | None = None,
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    history = []
    all_rows = []
    if character_ids:
        history = db.scalars(
            select(PlanetaryProductionSnapshot)
            .where(
                PlanetaryProductionSnapshot.character_id.in_(character_ids),
                PlanetaryProductionSnapshot.captured_at >= cutoff,
            )
            .options(
                selectinload(PlanetaryProductionSnapshot.character),
                selectinload(PlanetaryProductionSnapshot.product_type),
            )
            .order_by(PlanetaryProductionSnapshot.captured_at)
        ).all()
        all_rows = db.scalars(
            select(PlanetaryProductionSnapshot)
            .where(PlanetaryProductionSnapshot.character_id.in_(character_ids))
            .options(
                selectinload(PlanetaryProductionSnapshot.character),
                selectinload(PlanetaryProductionSnapshot.product_type),
            )
            .order_by(
                PlanetaryProductionSnapshot.character_id,
                PlanetaryProductionSnapshot.captured_at.desc(),
            )
        ).all()
    latest_at: dict[int, datetime] = {}
    current: list[PlanetaryProductionSnapshot] = []
    for row in all_rows:
        latest = latest_at.setdefault(row.character_id, row.captured_at)
        if row.captured_at == latest:
            current.append(row)

    anonymous_character_ids = anonymous_character_ids or set()
    payload = {
        "schema_version": "eqm.planetary-analytics.v1",
        "days": days,
        "cutoff": cutoff.isoformat(),
        "history": [_snapshot_engine_row(row) for row in history],
        "current": [_snapshot_engine_row(row) for row in current],
        "anonymous_character_ids": sorted(anonymous_character_ids),
    }
    return evaluate_planetary_analytics_with_engine(
        payload=payload,
        python_result=lambda: _planetary_analytics_summary_python(
            days,
            cutoff,
            history,
            current,
            anonymous_character_ids,
        ),
    )


def _snapshot_engine_row(row: PlanetaryProductionSnapshot) -> dict[str, Any]:
    return {
        "character_id": row.character_id,
        "character_name": row.character.name,
        "product_type_id": row.product_type_id,
        "product_name": row.product_type.name,
        "tier": row.commodity_tier,
        "unit_volume": float(row.unit_volume or 0),
        "estimated_units_since_previous": float(row.estimated_units_since_previous or 0),
        "projected_units_per_day": float(row.projected_units_per_day or 0),
        "interval_started_at": _aware(row.interval_started_at).isoformat() if row.interval_started_at else None,
        "captured_at": (_aware(row.captured_at) or row.captured_at).isoformat(),
    }


def _planetary_analytics_summary_python(
    days: int,
    cutoff: datetime,
    history: list[PlanetaryProductionSnapshot],
    current: list[PlanetaryProductionSnapshot],
    anonymous_character_ids: set[int],
) -> dict[str, Any]:
    if not history and not current:
        return _empty_summary(days)

    aggregates: dict[tuple[int, int], dict[str, Any]] = {}
    for row in history:
        key = (row.character_id, row.product_type_id)
        item = aggregates.setdefault(key, _aggregate_seed(row))
        units = _windowed_estimate(row, cutoff)
        item["estimated_units"] += units
        item["estimated_volume"] += units * row.unit_volume
    for row in current:
        key = (row.character_id, row.product_type_id)
        item = aggregates.setdefault(key, _aggregate_seed(row))
        item["current_units_per_day"] += row.projected_units_per_day
        item["current_volume_per_day"] += row.projected_units_per_day * row.unit_volume

    character_products = sorted(
        aggregates.values(),
        key=lambda item: (item["estimated_volume"], item["current_volume_per_day"]),
        reverse=True,
    )
    products: dict[int, dict[str, Any]] = {}
    tiers = {
        tier: {
            "tier": tier,
            "label": PI_TIER_LABELS[tier],
            "estimated_units": 0.0,
            "estimated_volume": 0.0,
            "current_units_per_day": 0.0,
            "current_volume_per_day": 0.0,
            "products": set(),
            "characters": set(),
        }
        for tier in PI_TIER_LABELS
    }
    for item in character_products:
        product = products.setdefault(
            item["product_type_id"],
            {
                "product_type_id": item["product_type_id"],
                "product_name": item["product_name"],
                "tier": item["tier"],
                "estimated_units": 0.0,
                "estimated_volume": 0.0,
                "current_units_per_day": 0.0,
                "current_volume_per_day": 0.0,
                "top_character": None,
                "_top_score": -1.0,
            },
        )
        for field in (
            "estimated_units",
            "estimated_volume",
            "current_units_per_day",
            "current_volume_per_day",
        ):
            product[field] += item[field]
            tiers[item["tier"]][field] += item[field]
        score = item["estimated_units"] or item["current_units_per_day"]
        if item["character_id"] not in anonymous_character_ids and score > product["_top_score"]:
            product["_top_score"] = score
            product["top_character"] = item["character_name"]
        tiers[item["tier"]]["products"].add(item["product_type_id"])
        tiers[item["tier"]]["characters"].add(item["character_id"])

    product_rows = []
    for item in products.values():
        item.pop("_top_score", None)
        product_rows.append(item)
    product_rows.sort(
        key=lambda item: (item["estimated_volume"], item["current_volume_per_day"]),
        reverse=True,
    )
    tier_rows = []
    for item in tiers.values():
        item["product_count"] = len(item.pop("products"))
        item["character_count"] = len(item.pop("characters"))
        tier_rows.append(item)
    return {
        "days": days,
        "has_history": any(item["estimated_units"] > 0 for item in character_products),
        "cards": {
            "estimated_volume": sum(item["estimated_volume"] for item in character_products),
            "current_volume_per_day": sum(
                item["current_volume_per_day"] for item in character_products
            ),
            "product_count": len(products),
            "character_count": len(
                {item["character_id"] for item in character_products}
            ),
        },
        "tiers": tier_rows,
        "products": product_rows,
        "character_products": [
            item for item in character_products if item["character_id"] not in anonymous_character_ids
        ],
    }


def _aggregate_seed(row: PlanetaryProductionSnapshot) -> dict[str, Any]:
    return {
        "character_id": row.character_id,
        "character_name": row.character.name,
        "product_type_id": row.product_type_id,
        "product_name": row.product_type.name,
        "tier": row.commodity_tier,
        "estimated_units": 0.0,
        "estimated_volume": 0.0,
        "current_units_per_day": 0.0,
        "current_volume_per_day": 0.0,
    }


def _windowed_estimate(row: PlanetaryProductionSnapshot, cutoff: datetime) -> float:
    units = float(row.estimated_units_since_previous or 0)
    started = _aware(row.interval_started_at)
    captured = _aware(row.captured_at) or row.captured_at
    if not started or started >= cutoff or captured <= cutoff:
        return units
    total = (captured - started).total_seconds()
    visible = (captured - cutoff).total_seconds()
    return units * max(0, min(visible / total, 1)) if total > 0 else units


def _empty_summary(days: int) -> dict[str, Any]:
    return {
        "days": days,
        "has_history": False,
        "cards": {
            "estimated_volume": 0,
            "current_volume_per_day": 0,
            "product_count": 0,
            "character_count": 0,
        },
        "tiers": [
            {
                "tier": tier,
                "label": label,
                "estimated_units": 0,
                "estimated_volume": 0,
                "current_units_per_day": 0,
                "current_volume_per_day": 0,
                "product_count": 0,
                "character_count": 0,
            }
            for tier, label in PI_TIER_LABELS.items()
        ],
        "products": [],
        "character_products": [],
    }
