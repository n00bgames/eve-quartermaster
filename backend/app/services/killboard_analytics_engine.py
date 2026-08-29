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
OUTPUT_SCHEMA = "eqm.killboard-analytics-output.v1"


def _run_rust(binary: str, timeout: float, payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [binary, "killboard-analytics", "--input", "-"],
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
        raise RuntimeError("eqm-core returned an unsupported killboard analytics schema")
    required = {"summary", "hulls", "geography", "opponents", "streaks", "wingmates", "timeline", "unknown_value_records"}
    if not required.issubset(result):
        raise RuntimeError("eqm-core returned an incomplete killboard analytics result")
    return result


def _comparison_value(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if not key.startswith("engine_")}


def evaluate_killboard_analytics_with_engine(
    *,
    payload: dict[str, Any],
    python_result: dict[str, Any] | Callable[[], dict[str, Any]],
    engine: str | None = None,
    binary: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    requested = (engine or settings.eqm_killboard_analytics_engine).strip().lower()
    if requested not in VALID_ENGINES:
        logger.warning("Unknown EQM killboard analytics engine %r; using Python", requested)
        requested = "python"
    binary = binary or settings.eqm_core_binary
    timeout = timeout if timeout is not None else settings.eqm_core_timeout_seconds

    def reference() -> dict[str, Any]:
        return python_result() if callable(python_result) else python_result

    if requested == "python":
        result = copy.deepcopy(reference())
        result.update(engine_requested="python", engine_used="python")
        return result
    if requested == "shadow":
        result = copy.deepcopy(reference())
        try:
            rust_result = _run_rust(binary, timeout, payload)
            match = _comparison_value(result) == _comparison_value(rust_result)
            if not match:
                logger.warning("Killboard analytics shadow mismatch")
            result.update(engine_requested="shadow", engine_used="python-shadow", engine_shadow_match=match)
        except Exception as error:
            logger.exception("Rust killboard analytics shadow failed; Python result retained")
            result.update(engine_requested="shadow", engine_used="python-shadow-error", engine_shadow_match=False, engine_fallback_reason=str(error)[:300])
        return result
    try:
        result = _run_rust(binary, timeout, payload)
        result.update(engine_requested="rust", engine_used="rust")
        return result
    except Exception as error:
        logger.exception("Rust killboard analytics failed; falling back to Python")
        result = copy.deepcopy(reference())
        result.update(engine_requested="rust", engine_used="python-fallback", engine_fallback_reason=str(error)[:300])
        return result
