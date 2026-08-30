from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from typing import Any

from app.core.config import get_settings


logger = logging.getLogger(__name__)
VALID_ENGINES = {"python", "shadow", "rust"}


def _run_rust(payload: dict[str, Any], *, binary: str, timeout: float) -> dict[str, Any]:
    completed = subprocess.run(
        [binary, "threat-analytics", "--input", "-"],
        input=json.dumps(payload, separators=(",", ":")),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "Rust threat analytics failed").strip())
    result = json.loads(completed.stdout)
    if result.get("schema_version") != "eqm.threat-analytics-output.v1":
        raise RuntimeError("Rust threat analytics returned an unsupported schema")
    return result


def _convert(raw: dict[str, Any], expected_keys: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "total_destroyed_value": raw["total_destroyed_value_cents"] / 100,
        "latest_killmail_time": raw["latest_killmail_time"],
        "risk_score": raw["risk_score"],
        "risk_label": raw["risk_label"],
    }
    for key, value in raw.items():
        if key.startswith("top_") or key == "most_dangerous_locations":
            result[key] = [
                {
                    "name": row["name"],
                    "count": row["count"],
                    "total_value": row["total_value_cents"] / 100,
                }
                for row in value
            ]
    if "total_industrial_kills" in expected_keys:
        result["total_industrial_kills"] = raw["total_kills"]
    if "total_kills" in expected_keys:
        result["total_kills"] = raw["total_kills"]
    return {key: value for key, value in result.items() if key in expected_keys}


def evaluate_threat_analytics_with_engine(
    *,
    payload: dict[str, Any],
    python_result: dict[str, Any] | Callable[[], dict[str, Any]],
    expected_keys: set[str],
    engine: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    requested = (engine or settings.eqm_threat_analytics_engine).strip().lower()
    if requested not in VALID_ENGINES:
        logger.warning("Unknown EQM threat analytics engine %r; using Python", requested)
        requested = "python"
    reference = lambda: python_result() if callable(python_result) else python_result
    if requested == "python":
        return {**reference(), "engine_requested": "python", "engine_used": "python"}
    try:
        raw = _run_rust(payload, binary=settings.eqm_core_binary, timeout=settings.eqm_core_timeout_seconds)
        rust_result = _convert(raw, expected_keys)
    except Exception as error:
        logger.exception("Rust threat analytics failed; Python result retained")
        return {
            **reference(),
            "engine_requested": requested,
            "engine_used": "python-shadow-error" if requested == "shadow" else "python-fallback",
            "engine_shadow_match": False if requested == "shadow" else None,
            "engine_fallback_reason": str(error)[:300],
        }
    if requested == "shadow":
        python_value = reference()
        match = python_value == rust_result
        if not match:
            logger.warning("Threat analytics shadow mismatch")
        return {
            **python_value,
            "engine_requested": "shadow",
            "engine_used": "python-shadow",
            "engine_shadow_match": match,
        }
    return {**rust_result, "engine_requested": "rust", "engine_used": "rust"}
