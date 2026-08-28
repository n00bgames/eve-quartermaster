from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.services.planetary_simulation import (
    MAX_SIMULATION_EVENTS,
    SimulationPin,
    SimulationRoute,
    simulate_colony,
)


logger = logging.getLogger(__name__)
VALID_ENGINES = {"python", "shadow", "rust"}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _payload(
    *,
    checkpoint_at: datetime | None,
    projected_at: datetime,
    pins: list[SimulationPin],
    routes: list[SimulationRoute],
    type_volumes: dict[int, float],
    max_events: int,
) -> dict[str, Any]:
    return {
        "schema_version": "eqm.planetary-colony-simulation-input.v1",
        "checkpoint_at": _iso(checkpoint_at),
        "projected_at": _iso(projected_at),
        "max_events": max_events,
        "pins": [
            {
                "pin_id": pin.pin_id,
                "kind": pin.kind,
                "contents": pin.contents,
                "capacity_m3": pin.capacity_m3,
                "schematic": {
                    "cycle_time": pin.schematic.cycle_time,
                    "inputs": pin.schematic.inputs,
                    "output_type_id": pin.schematic.output_type_id,
                    "output_quantity": pin.schematic.output_quantity,
                } if pin.schematic else None,
                "last_cycle_start": _iso(pin.last_cycle_start),
                "install_time": _iso(pin.install_time),
                "expiry_time": _iso(pin.expiry_time),
                "extractor_cycle_time": pin.extractor_cycle_time,
                "extractor_product_type_id": pin.extractor_product_type_id,
                "extractor_quantity_per_cycle": pin.extractor_quantity_per_cycle,
                "extractor_decay_factor": pin.extractor_decay_factor,
                "extractor_noise_factor": pin.extractor_noise_factor,
            }
            for pin in pins
        ],
        "routes": [
            {
                "source_pin_id": route.source_pin_id,
                "destination_pin_id": route.destination_pin_id,
                "content_type_id": route.content_type_id,
                "quantity": route.quantity,
            }
            for route in routes
        ],
        "type_volumes": type_volumes,
    }


def _decode_rust_result(payload: dict[str, Any]) -> dict[str, Any]:
    payload["checkpoint_at"] = _parse_time(payload.get("checkpoint_at"))
    payload["projected_at"] = _parse_time(payload.get("projected_at"))
    payload["pins"] = {
        int(pin_id): {
            **pin,
            "contents": {int(type_id): quantity for type_id, quantity in pin.get("contents", {}).items()},
            "produced": {int(type_id): quantity for type_id, quantity in pin.get("produced", {}).items()},
            "blocked": {int(type_id): quantity for type_id, quantity in pin.get("blocked", {}).items()},
        }
        for pin_id, pin in payload.get("pins", {}).items()
    }
    return payload


def _run_rust(binary: str, timeout: float, payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [binary, "colony-simulation", "--input", "-"],
        input=json.dumps(payload, separators=(",", ":")),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise RuntimeError(f"eqm-core failed: {detail[:500]}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("eqm-core returned invalid JSON") from error
    return _decode_rust_result(result)


def _canonical(result: dict[str, Any]) -> str:
    def normalize(value: Any) -> Any:
        if isinstance(value, datetime):
            return _iso(value)
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in value.items() if not str(key).startswith("engine_")}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value

    return json.dumps(normalize(result), sort_keys=True, separators=(",", ":"))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def simulate_colony_with_engine(
    *,
    checkpoint_at: datetime | None,
    projected_at: datetime,
    pins: list[SimulationPin],
    routes: list[SimulationRoute],
    type_volumes: dict[int, float],
    max_events: int = MAX_SIMULATION_EVENTS,
    engine: str | None = None,
    binary: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    requested = (engine or settings.eqm_pi_engine).strip().lower()
    if requested not in VALID_ENGINES:
        logger.warning("Unknown EQM PI engine %r; using Python", requested)
        requested = "python"
    binary = binary or settings.eqm_core_binary
    timeout = timeout if timeout is not None else settings.eqm_core_timeout_seconds
    rust_payload = _payload(
        checkpoint_at=checkpoint_at,
        projected_at=projected_at,
        pins=pins,
        routes=routes,
        type_volumes=type_volumes,
        max_events=max_events,
    )

    def python_result() -> dict[str, Any]:
        return simulate_colony(
            checkpoint_at=checkpoint_at,
            projected_at=projected_at,
            pins=pins,
            routes=routes,
            type_volumes=type_volumes,
            max_events=max_events,
        )

    if requested == "python":
        result = python_result()
        result.update(engine_requested="python", engine_used="python")
        return result

    if requested == "shadow":
        result = python_result()
        try:
            rust_result = _run_rust(binary, timeout, rust_payload)
            python_canonical = _canonical(result)
            rust_canonical = _canonical(rust_result)
            match = python_canonical == rust_canonical
            if not match:
                logger.warning(
                    "PI simulation shadow mismatch python=%s rust=%s",
                    _digest(python_canonical),
                    _digest(rust_canonical),
                )
            result.update(
                engine_requested="shadow",
                engine_used="python-shadow",
                engine_shadow_match=match,
            )
        except Exception as error:
            logger.exception("Rust PI shadow simulation failed; Python result retained")
            result.update(
                engine_requested="shadow",
                engine_used="python-shadow-error",
                engine_shadow_match=False,
                engine_fallback_reason=str(error)[:300],
            )
        return result

    try:
        result = _run_rust(binary, timeout, rust_payload)
        result.update(engine_requested="rust", engine_used="rust")
        return result
    except Exception as error:
        logger.exception("Rust PI simulation failed; falling back to Python")
        result = python_result()
        result.update(
            engine_requested="rust",
            engine_used="python-fallback",
            engine_fallback_reason=str(error)[:300],
        )
        return result
