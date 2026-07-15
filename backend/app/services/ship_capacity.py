from __future__ import annotations


FREIGHTER_CARGO_CAPACITY_BY_TYPE_ID = {
    20189: 435_000.0,  # Fenrir
}

FREIGHTER_CARGO_CAPACITY_BY_NAME = {
    "fenrir": FREIGHTER_CARGO_CAPACITY_BY_TYPE_ID[20189],
}


def resolved_ship_capacity(type_id: int | None, name: str | None = None, stored_capacity: float | None = None) -> float | None:
    if stored_capacity is not None and stored_capacity > 0:
        return float(stored_capacity)
    if type_id is not None:
        fallback = FREIGHTER_CARGO_CAPACITY_BY_TYPE_ID.get(int(type_id))
        if fallback is not None:
            return fallback
    if name:
        return FREIGHTER_CARGO_CAPACITY_BY_NAME.get(name.strip().lower())
    return None
