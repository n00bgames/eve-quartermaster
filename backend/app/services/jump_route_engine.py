from __future__ import annotations

import copy
import json
import logging
import subprocess
from collections.abc import Callable
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger(__name__)
VALID_ENGINES = {"python", "shadow", "rust"}
OUTPUT_SCHEMA = "eqm.jump-route-output.v1"


class JumpRouteUnavailable(ValueError):
    pass


def _run_rust(binary: str, timeout: float, payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [binary, "jump-route", "--input", "-"],
        input=json.dumps(payload, separators=(",", ":")),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        route_error = detail.removeprefix("eqm-core:").strip()
        if route_error.startswith("No jump route found"):
            raise JumpRouteUnavailable(route_error)
        raise RuntimeError(f"eqm-core failed: {detail[:500]}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("eqm-core returned invalid JSON") from error
    if result.get("schema_version") != OUTPUT_SCHEMA:
        raise RuntimeError("eqm-core returned an unsupported jump route schema")
    path = result.get("path_system_ids")
    if not isinstance(path, list) or not path or not all(isinstance(system_id, int) for system_id in path):
        raise RuntimeError("eqm-core returned an invalid jump route path")
    if not isinstance(result.get("total_distance_ly"), (int, float)):
        raise RuntimeError("eqm-core returned an invalid jump route distance")
    return result


def _routes_match(python_result: dict[str, Any], rust_result: dict[str, Any]) -> bool:
    if python_result.get("path_system_ids") != rust_result.get("path_system_ids"):
        return False
    python_distance = float(python_result.get("total_distance_ly") or 0.0)
    rust_distance = float(rust_result.get("total_distance_ly") or 0.0)
    return abs(python_distance - rust_distance) <= 1e-8 * max(1.0, abs(python_distance), abs(rust_distance))


def evaluate_jump_route_with_engine(
    *,
    payload: dict[str, Any],
    python_result: dict[str, Any] | Callable[[], dict[str, Any]],
    engine: str | None = None,
    binary: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    requested = (engine or settings.eqm_jump_route_engine).strip().lower()
    if requested not in VALID_ENGINES:
        logger.warning("Unknown EQM jump route engine %r; using Python", requested)
        requested = "python"
    binary = binary or settings.eqm_core_binary
    timeout = timeout if timeout is not None else settings.eqm_core_timeout_seconds

    def reference_result() -> dict[str, Any]:
        return python_result() if callable(python_result) else python_result

    if requested == "python":
        result = copy.deepcopy(reference_result())
        result.update(engine_requested="python", engine_used="python")
        return result

    if requested == "shadow":
        result = copy.deepcopy(reference_result())
        try:
            rust_result = _run_rust(binary, timeout, payload)
            match = _routes_match(result, rust_result)
            if not match:
                logger.warning(
                    "Jump route shadow mismatch python_path=%s rust_path=%s python_distance=%s rust_distance=%s",
                    result.get("path_system_ids"),
                    rust_result.get("path_system_ids"),
                    result.get("total_distance_ly"),
                    rust_result.get("total_distance_ly"),
                )
            result.update(engine_requested="shadow", engine_used="python-shadow", engine_shadow_match=match)
        except Exception as error:
            logger.exception("Rust jump route shadow failed; Python result retained")
            result.update(
                engine_requested="shadow",
                engine_used="python-shadow-error",
                engine_shadow_match=False,
                engine_fallback_reason=str(error)[:300],
            )
        return result

    try:
        result = _run_rust(binary, timeout, payload)
        result.update(engine_requested="rust", engine_used="rust")
        return result
    except JumpRouteUnavailable:
        raise
    except Exception as error:
        logger.exception("Rust jump route failed; falling back to Python")
        result = copy.deepcopy(reference_result())
        result.update(
            engine_requested="rust",
            engine_used="python-fallback",
            engine_fallback_reason=str(error)[:300],
        )
        return result
