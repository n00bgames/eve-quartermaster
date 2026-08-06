from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from heapq import heappop, heappush
from itertools import count
from typing import Literal

from app.services.planetary_industry import extractor_cycle_output


PinKind = Literal["extractor", "factory", "storage", "infrastructure"]


def utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class SimulationSchematic:
    cycle_time: int
    inputs: dict[int, int]
    output_type_id: int
    output_quantity: int


@dataclass(frozen=True)
class SimulationRoute:
    source_pin_id: int
    destination_pin_id: int
    content_type_id: int
    quantity: int


@dataclass(frozen=True)
class SimulationPin:
    pin_id: int
    kind: PinKind
    contents: dict[int, int] = field(default_factory=dict)
    capacity_m3: float | None = None
    schematic: SimulationSchematic | None = None
    last_cycle_start: datetime | None = None
    install_time: datetime | None = None
    expiry_time: datetime | None = None
    extractor_cycle_time: int | None = None
    extractor_product_type_id: int | None = None
    extractor_quantity_per_cycle: int | None = None
    extractor_decay_factor: float = 0.012
    extractor_noise_factor: float = 0.8


@dataclass
class _PinState:
    definition: SimulationPin
    contents: dict[int, int]
    factory_running_until: datetime | None = None
    status: str = "online"


MAX_SIMULATION_EVENTS = 100_000


def known_pin_capacity_m3(type_name: str) -> float | None:
    """Return the standard commodity capacity for PI storage-class pins."""
    name = type_name.casefold()
    if "launchpad" in name:
        return 10_000.0
    if "storage" in name:
        return 12_000.0
    if "command center" in name:
        return 500.0
    return None


def simulate_colony(
    *,
    checkpoint_at: datetime | None,
    projected_at: datetime,
    pins: list[SimulationPin],
    routes: list[SimulationRoute],
    type_volumes: dict[int, float],
    max_events: int = MAX_SIMULATION_EVENTS,
) -> dict:
    checkpoint = utc(checkpoint_at)
    target = utc(projected_at) or datetime.now(timezone.utc)
    states = {
        pin.pin_id: _PinState(
            definition=pin,
            contents={int(type_id): max(0, int(quantity)) for type_id, quantity in pin.contents.items()},
        )
        for pin in pins
    }
    if checkpoint is None or target <= checkpoint:
        return _result(states, checkpoint, target, 0, False, False, {}, {})

    outgoing: dict[tuple[int, int], list[SimulationRoute]] = {}
    incoming: dict[tuple[int, int], list[SimulationRoute]] = {}
    for route in routes:
        outgoing.setdefault((route.source_pin_id, route.content_type_id), []).append(route)
        incoming.setdefault((route.destination_pin_id, route.content_type_id), []).append(route)
    for route_list in (*outgoing.values(), *incoming.values()):
        route_list.sort(key=lambda row: (row.destination_pin_id, row.source_pin_id))

    event_order = count()
    events: list[tuple[datetime, int, str, int]] = []
    produced: dict[int, dict[int, int]] = {}
    blocked: dict[int, dict[int, int]] = {}

    def schedule(when: datetime, kind: str, pin_id: int) -> None:
        if when <= target:
            heappush(events, (when, next(event_order), kind, pin_id))

    def capacity_remaining(state: _PinState) -> float | None:
        capacity = state.definition.capacity_m3
        if capacity is None:
            return None
        used = sum(type_volumes.get(type_id, 0.0) * quantity for type_id, quantity in state.contents.items())
        return max(0.0, capacity - used)

    def add_commodity(state: _PinState, type_id: int, quantity: int) -> int:
        if quantity <= 0:
            return 0
        remaining = capacity_remaining(state)
        volume = max(0.0, type_volumes.get(type_id, 0.0))
        accepted = quantity
        if remaining is not None and volume > 0:
            accepted = min(accepted, int(remaining // volume))
        if accepted > 0:
            state.contents[type_id] = state.contents.get(type_id, 0) + accepted
        return accepted

    def remove_commodity(state: _PinState, type_id: int, quantity: int) -> int:
        available = state.contents.get(type_id, 0)
        removed = min(max(0, quantity), available)
        if removed:
            remaining = available - removed
            if remaining:
                state.contents[type_id] = remaining
            else:
                state.contents.pop(type_id, None)
        return removed

    def route_output(source_pin_id: int, type_id: int, quantity: int, when: datetime) -> bool:
        remaining = quantity
        destinations: set[int] = set()
        for route in outgoing.get((source_pin_id, type_id), []):
            destination = states.get(route.destination_pin_id)
            if destination is None or remaining <= 0:
                continue
            moved = add_commodity(destination, type_id, min(remaining, max(0, route.quantity)))
            remaining -= moved
            destinations.add(destination.definition.pin_id)
        if remaining > 0:
            blocked.setdefault(source_pin_id, {})[type_id] = blocked.setdefault(source_pin_id, {}).get(type_id, 0) + remaining
        for destination_id in destinations:
            destination = states[destination_id]
            if destination.definition.kind == "factory" and destination.factory_running_until is None:
                try_start_factory(destination, when)
        return remaining == 0

    def pull_factory_inputs(state: _PinState) -> None:
        schematic = state.definition.schematic
        if schematic is None:
            return
        for type_id, required in schematic.inputs.items():
            needed = max(0, required - state.contents.get(type_id, 0))
            for route in incoming.get((state.definition.pin_id, type_id), []):
                if needed <= 0:
                    break
                source = states.get(route.source_pin_id)
                if source is None:
                    continue
                moved = remove_commodity(source, type_id, min(needed, max(0, route.quantity)))
                if moved:
                    add_commodity(state, type_id, moved)
                    needed -= moved

    def try_start_factory(state: _PinState, when: datetime) -> bool:
        schematic = state.definition.schematic
        if schematic is None or schematic.cycle_time <= 0 or state.factory_running_until is not None:
            return False
        pull_factory_inputs(state)
        if any(state.contents.get(type_id, 0) < required for type_id, required in schematic.inputs.items()):
            state.status = "starved"
            return False
        for type_id, required in schematic.inputs.items():
            remove_commodity(state, type_id, required)
        completion = when + timedelta(seconds=schematic.cycle_time)
        state.factory_running_until = completion
        state.status = "running"
        schedule(completion, "factory", state.definition.pin_id)
        return True

    for state in states.values():
        pin = state.definition
        if pin.kind == "extractor" and pin.extractor_cycle_time and pin.extractor_cycle_time > 0:
            last_start = utc(pin.last_cycle_start) or checkpoint
            next_completion = last_start + timedelta(seconds=pin.extractor_cycle_time)
            while next_completion <= checkpoint:
                next_completion += timedelta(seconds=pin.extractor_cycle_time)
            expiry = utc(pin.expiry_time)
            if expiry is None or next_completion <= expiry:
                state.status = "active"
                schedule(next_completion, "extractor", pin.pin_id)
            else:
                state.status = "expired"
        elif pin.kind == "factory" and pin.schematic:
            last_start = utc(pin.last_cycle_start)
            completion = last_start + timedelta(seconds=pin.schematic.cycle_time) if last_start else None
            if completion and completion > checkpoint:
                state.factory_running_until = completion
                state.status = "running"
                schedule(completion, "factory", pin.pin_id)
            else:
                try_start_factory(state, checkpoint)

    events_processed = 0
    truncated = False
    while events:
        when, _, event_kind, pin_id = heappop(events)
        if when > target:
            break
        if events_processed >= max_events:
            truncated = True
            break
        events_processed += 1
        state = states.get(pin_id)
        if state is None:
            continue
        pin = state.definition
        if event_kind == "extractor":
            expiry = utc(pin.expiry_time)
            if expiry is not None and when > expiry:
                state.status = "expired"
                continue
            cycle_time = pin.extractor_cycle_time or 0
            product_type_id = pin.extractor_product_type_id
            base_quantity = pin.extractor_quantity_per_cycle or 0
            if cycle_time <= 0 or product_type_id is None or base_quantity <= 0:
                state.status = "idle"
                continue
            installed = utc(pin.install_time)
            cycle_index = max(0, int((when - installed).total_seconds() // cycle_time) - 1) if installed else 0
            quantity = extractor_cycle_output(
                cycle_index,
                cycle_time,
                base_quantity,
                pin.extractor_decay_factor,
                pin.extractor_noise_factor,
            ) if installed else base_quantity
            produced.setdefault(pin_id, {})[product_type_id] = produced.setdefault(pin_id, {}).get(product_type_id, 0) + quantity
            route_output(pin_id, product_type_id, quantity, when)
            next_completion = when + timedelta(seconds=cycle_time)
            if expiry is None or next_completion <= expiry:
                schedule(next_completion, "extractor", pin_id)
            else:
                state.status = "expired"
        elif event_kind == "factory":
            schematic = pin.schematic
            if schematic is None:
                continue
            state.factory_running_until = None
            produced.setdefault(pin_id, {})[schematic.output_type_id] = produced.setdefault(pin_id, {}).get(schematic.output_type_id, 0) + schematic.output_quantity
            delivered = route_output(pin_id, schematic.output_type_id, schematic.output_quantity, when)
            if delivered:
                try_start_factory(state, when)
            else:
                state.status = "blocked"

    for state in states.values():
        pin = state.definition
        if pin.kind == "factory" and pin.pin_id in blocked:
            state.status = "blocked"
        elif pin.kind == "factory" and state.factory_running_until is not None:
            state.status = "running"
        elif pin.kind == "storage":
            remaining = capacity_remaining(state)
            state.status = "full" if remaining is not None and remaining < 0.001 else "online"
        elif pin.kind == "extractor" and utc(pin.expiry_time) and utc(pin.expiry_time) <= target:
            state.status = "expired"

    return _result(states, checkpoint, target, events_processed, True, truncated, produced, blocked)


def _result(
    states: dict[int, _PinState],
    checkpoint: datetime | None,
    target: datetime,
    events_processed: int,
    projected: bool,
    truncated: bool,
    produced: dict[int, dict[int, int]],
    blocked: dict[int, dict[int, int]],
) -> dict:
    return {
        "checkpoint_at": checkpoint,
        "projected_at": target,
        "is_projection": projected,
        "events_processed": events_processed,
        "truncated": truncated,
        "pins": {
            pin_id: {
                "contents": dict(sorted(state.contents.items())),
                "status": state.status,
                "produced": dict(sorted(produced.get(pin_id, {}).items())),
                "blocked": dict(sorted(blocked.get(pin_id, {}).items())),
            }
            for pin_id, state in states.items()
        },
    }
