from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger(__name__)
VALID_ENGINES = {"python", "shadow", "rust"}


def _run_rust(payload: dict[str, Any], *, binary: str, timeout: float) -> dict[str, Any]:
    completed = subprocess.run(
        [binary, "event-analytics", "--input", "-"],
        input=json.dumps(payload, separators=(",", ":")),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "Rust event analytics failed").strip())
    result = json.loads(completed.stdout)
    if result.get("schema_version") != "eqm.event-analytics.v1":
        raise RuntimeError("Rust event analytics returned an unsupported schema")
    result.pop("schema_version", None)
    if payload["operation"] == "range":
        result["from_at"] = datetime.fromisoformat(result["from_at"])
        result["to_at"] = datetime.fromisoformat(result["to_at"])
        for row in result["series"]:
            row["period_start"] = datetime.fromisoformat(row["period_start"])
    return result


def evaluate_event_analytics_with_engine(
    *,
    payload: dict[str, Any],
    python_result: dict[str, Any] | Callable[[], dict[str, Any]],
    engine: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    requested = (engine or settings.eqm_event_analytics_engine).strip().lower()
    if requested not in VALID_ENGINES:
        logger.warning("Unknown EQM event analytics engine %r; using Python", requested)
        requested = "python"
    reference = lambda: python_result() if callable(python_result) else python_result
    if requested == "python":
        return {**reference(), "engine_requested": "python", "engine_used": "python"}
    try:
        rust_result = _run_rust(
            payload,
            binary=settings.eqm_core_binary,
            timeout=settings.eqm_core_timeout_seconds,
        )
    except Exception as error:
        logger.exception("Rust event analytics failed; Python result retained")
        result = {
            **reference(),
            "engine_requested": requested,
            "engine_used": "python-shadow-error" if requested == "shadow" else "python-fallback",
            "engine_fallback_reason": str(error)[:300],
        }
        if requested == "shadow":
            result["engine_shadow_match"] = False
        return result
    if requested == "shadow":
        python_value = reference()
        match = python_value == rust_result
        if not match:
            logger.warning("Event analytics shadow mismatch operation=%s", payload["operation"])
        return {
            **python_value,
            "engine_requested": "shadow",
            "engine_used": "python-shadow",
            "engine_shadow_match": match,
        }
    return {**rust_result, "engine_requested": "rust", "engine_used": "rust"}
