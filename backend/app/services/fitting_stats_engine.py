from __future__ import annotations

import copy
import hashlib
import json
import logging
import subprocess
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger(__name__)
VALID_ENGINES = {"python", "shadow", "rust"}


def _run_rust(binary: str, timeout: float, payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [binary, "fitting-stats", "--input", "-"],
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
    if result.get("schema_version") != "eqm.fitting-stats-output.v1":
        raise RuntimeError("eqm-core returned an unsupported fitting stats schema")
    required = {"offense", "defense", "mobility", "capacitor", "cargo_bays", "targeting", "notes"}
    if not required.issubset(result):
        raise RuntimeError("eqm-core returned an incomplete fitting stats result")
    return result


def _comparison_value(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"schema_version", "notes"}
        and not key.startswith("engine_")
        and not key.startswith("math_engine_")
    }


def _canonical(result: dict[str, Any]) -> str:
    return json.dumps(_comparison_value(result), sort_keys=True, separators=(",", ":"))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _difference_paths(left: Any, right: Any, path: str = "stats", limit: int = 16) -> list[str]:
    if limit <= 0:
        return []
    if isinstance(left, dict) and isinstance(right, dict):
        differences: list[str] = []
        for key in sorted(set(left) | set(right)):
            differences.extend(_difference_paths(left.get(key), right.get(key), f"{path}.{key}", limit - len(differences)))
            if len(differences) >= limit:
                break
        return differences
    if isinstance(left, list) and isinstance(right, list):
        differences = []
        if len(left) != len(right):
            differences.append(f"{path}.length")
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            differences.extend(_difference_paths(left_item, right_item, f"{path}[{index}]", limit - len(differences)))
            if len(differences) >= limit:
                break
        return differences
    if isinstance(left, (int, float)) and not isinstance(left, bool) and isinstance(right, (int, float)) and not isinstance(right, bool):
        scale = max(1.0, abs(float(left)), abs(float(right)))
        return [] if abs(float(left) - float(right)) <= 1e-8 * scale else [path]
    return [] if left == right else [path]


def evaluate_fitting_stats_with_engine(
    *,
    payload: dict[str, Any],
    python_result: dict[str, Any],
    engine: str | None = None,
    binary: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    requested = (engine or settings.eqm_fitting_stats_engine).strip().lower()
    if requested not in VALID_ENGINES:
        logger.warning("Unknown EQM fitting stats engine %r; using Python", requested)
        requested = "python"
    binary = binary or settings.eqm_core_binary
    timeout = timeout if timeout is not None else settings.eqm_core_timeout_seconds

    if requested == "python":
        result = copy.deepcopy(python_result)
        result.update(engine_requested="python", engine_used="python")
        return result

    if requested == "shadow":
        result = copy.deepcopy(python_result)
        try:
            rust_result = _run_rust(binary, timeout, payload)
            python_canonical = _canonical(result)
            rust_canonical = _canonical(rust_result)
            differences = _difference_paths(
                _comparison_value(result),
                _comparison_value(rust_result),
            )
            match = not differences
            if not match:
                logger.warning(
                    "Fitting stats shadow mismatch python=%s rust=%s fields=%s",
                    _digest(python_canonical),
                    _digest(rust_canonical),
                    ",".join(differences),
                )
            result.update(
                engine_requested="shadow",
                engine_used="python-shadow",
                engine_shadow_match=match,
            )
        except Exception as error:
            logger.exception("Rust fitting stats shadow failed; Python result retained")
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
    except Exception as error:
        logger.exception("Rust fitting stats failed; falling back to Python")
        result = copy.deepcopy(python_result)
        result.update(
            engine_requested="rust",
            engine_used="python-fallback",
            engine_fallback_reason=str(error)[:300],
        )
        return result
