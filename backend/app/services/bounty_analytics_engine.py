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
OUTPUT_SCHEMA = "eqm.bounty-analytics-output.v1"
REQUIRED_FIELDS = {"summary", "timeline", "leaderboard"}


def _run_rust(binary: str, timeout: float, payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [binary, "bounty-analytics", "--input", "-"],
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
    if result.get("schema_version") != OUTPUT_SCHEMA:
        raise RuntimeError("eqm-core returned an unsupported bounty analytics schema")
    if not REQUIRED_FIELDS.issubset(result):
        raise RuntimeError("eqm-core returned an incomplete bounty analytics result")
    return result


def _comparison_value(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key != "schema_version" and not key.startswith("engine_")
    }


def _difference_paths(left: Any, right: Any, path: str = "bounty", limit: int = 16) -> list[str]:
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


def evaluate_bounty_analytics_with_engine(
    *,
    payload: dict[str, Any],
    python_result: dict[str, Any] | Callable[[], dict[str, Any]],
    engine: str | None = None,
    binary: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    requested = (engine or settings.eqm_bounty_analytics_engine).strip().lower()
    if requested not in VALID_ENGINES:
        logger.warning("Unknown EQM bounty analytics engine %r; using Python", requested)
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
            differences = _difference_paths(_comparison_value(result), _comparison_value(rust_result))
            match = not differences
            if not match:
                logger.warning("Bounty analytics shadow mismatch fields=%s", ",".join(differences))
            result.update(engine_requested="shadow", engine_used="python-shadow", engine_shadow_match=match)
        except Exception as error:
            logger.exception("Rust bounty analytics shadow failed; Python result retained")
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
        logger.exception("Rust bounty analytics failed; falling back to Python")
        result = copy.deepcopy(reference_result())
        result.update(
            engine_requested="rust",
            engine_used="python-fallback",
            engine_fallback_reason=str(error)[:300],
        )
        return result
