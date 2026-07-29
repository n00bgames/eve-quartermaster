from __future__ import annotations

from datetime import datetime, timezone
from math import cos, floor

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EveDogmaAttribute, EveTypeDogmaAttribute


EXTRACTOR_DECAY_ATTRIBUTE_ID = 1683
EXTRACTOR_NOISE_ATTRIBUTE_ID = 1687
DEFAULT_DECAY_FACTOR = 0.012
DEFAULT_NOISE_FACTOR = 0.8


def utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def extractor_dogma_factors(
    db: Session,
    type_ids: set[int],
) -> dict[int, tuple[float, float, str]]:
    if not type_ids:
        return {}
    attribute_ids = {EXTRACTOR_DECAY_ATTRIBUTE_ID, EXTRACTOR_NOISE_ATTRIBUTE_ID}
    defaults = {
        attribute_id: float(value)
        for attribute_id, value in db.execute(
            select(EveDogmaAttribute.attribute_id, EveDogmaAttribute.default_value).where(
                EveDogmaAttribute.attribute_id.in_(attribute_ids),
                EveDogmaAttribute.default_value.is_not(None),
            )
        ).all()
    }
    rows = db.execute(
        select(
            EveTypeDogmaAttribute.type_id,
            EveTypeDogmaAttribute.attribute_id,
            EveTypeDogmaAttribute.value,
        ).where(
            EveTypeDogmaAttribute.type_id.in_(type_ids),
            EveTypeDogmaAttribute.attribute_id.in_(attribute_ids),
        )
    ).all()
    values: dict[int, dict[int, float]] = {}
    for type_id, attribute_id, value in rows:
        values.setdefault(type_id, {})[attribute_id] = float(value)
    return {
        type_id: (
            values.get(type_id, {}).get(
                EXTRACTOR_DECAY_ATTRIBUTE_ID,
                defaults.get(EXTRACTOR_DECAY_ATTRIBUTE_ID, DEFAULT_DECAY_FACTOR),
            ),
            values.get(type_id, {}).get(
                EXTRACTOR_NOISE_ATTRIBUTE_ID,
                defaults.get(EXTRACTOR_NOISE_ATTRIBUTE_ID, DEFAULT_NOISE_FACTOR),
            ),
            "dogma"
            if (
                EXTRACTOR_DECAY_ATTRIBUTE_ID in values.get(type_id, {})
                or EXTRACTOR_DECAY_ATTRIBUTE_ID in defaults
            )
            and (
                EXTRACTOR_NOISE_ATTRIBUTE_ID in values.get(type_id, {})
                or EXTRACTOR_NOISE_ATTRIBUTE_ID in defaults
            )
            else "documented_default",
        )
        for type_id in type_ids
    }


def extractor_cycle_output(
    cycle_index: int,
    cycle_time: int,
    quantity_per_cycle: int,
    decay_factor: float,
    noise_factor: float,
) -> int:
    if cycle_index < 0 or cycle_time <= 0 or quantity_per_cycle <= 0:
        return 0
    bar_width = cycle_time / 900.0
    time_value = (cycle_index + 0.5) * bar_width
    decay_value = quantity_per_cycle / (1 + time_value * decay_factor)
    phase_shift = quantity_per_cycle**0.7
    waves = (
        cos(phase_shift + time_value / 12)
        + cos(phase_shift / 2 + time_value * 0.2)
        + cos(time_value * 0.5)
    ) / 3
    bar_height = decay_value * (1 + noise_factor * max(waves, 0))
    return max(0, floor(bar_width * bar_height))


def extractor_program_projection(
    *,
    install_time: datetime | None,
    expiry_time: datetime | None,
    cycle_time: int | None,
    quantity_per_cycle: int | None,
    decay_factor: float = DEFAULT_DECAY_FACTOR,
    noise_factor: float = DEFAULT_NOISE_FACTOR,
    now: datetime | None = None,
) -> dict[str, int | float]:
    installed = utc(install_time)
    expires = utc(expiry_time)
    observed_at = utc(now) or datetime.now(timezone.utc)
    if (
        installed is None
        or expires is None
        or expires <= installed
        or not cycle_time
        or cycle_time <= 0
        or not quantity_per_cycle
        or quantity_per_cycle <= 0
    ):
        return {
            "cycle_count": 0,
            "program_output": 0,
            "average_daily_output": 0,
            "remaining_output": 0,
        }

    duration_seconds = (expires - installed).total_seconds()
    cycle_count = max(0, floor(duration_seconds / cycle_time))
    outputs = [
        extractor_cycle_output(
            cycle_index,
            cycle_time,
            quantity_per_cycle,
            decay_factor,
            noise_factor,
        )
        for cycle_index in range(cycle_count)
    ]
    elapsed_seconds = max(0, (observed_at - installed).total_seconds())
    completed_cycles = min(cycle_count, max(0, floor(elapsed_seconds / cycle_time)))
    program_output = sum(outputs)
    duration_days = duration_seconds / 86_400
    return {
        "cycle_count": cycle_count,
        "program_output": program_output,
        "average_daily_output": round(program_output / duration_days, 1),
        "remaining_output": sum(outputs[completed_cycles:]),
    }
