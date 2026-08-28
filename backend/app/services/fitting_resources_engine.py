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
        [binary, "fitting-resources", "--input", "-"],
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
    if result.get("schema_version") != "eqm.fitting-resources-output.v1":
        raise RuntimeError("eqm-core returned an unsupported fitting resources schema")
    required_keys = {"effective_ship_attrs", "resources", "slots", "item_usage", "stats_item_ids"}
    if not required_keys.issubset(result):
        raise RuntimeError("eqm-core returned an incomplete fitting resources result")
    return result


def _canonical(result: dict[str, Any]) -> str:
    return json.dumps(
        {
            key: value
            for key, value in result.items()
            if not key.startswith("engine_")
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def evaluate_fitting_resources_with_engine(
    *,
    payload: dict[str, Any],
    python_result: dict[str, Any],
    engine: str | None = None,
    binary: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    requested = (engine or settings.eqm_fitting_engine).strip().lower()
    if requested not in VALID_ENGINES:
        logger.warning("Unknown EQM fitting engine %r; using Python", requested)
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
            match = python_canonical == rust_canonical
            if not match:
                logger.warning(
                    "Fitting resources shadow mismatch python=%s rust=%s",
                    _digest(python_canonical),
                    _digest(rust_canonical),
                )
            result.update(
                engine_requested="shadow",
                engine_used="python-shadow",
                engine_shadow_match=match,
            )
        except Exception as error:
            logger.exception("Rust fitting resources shadow failed; Python result retained")
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
        logger.exception("Rust fitting resources failed; falling back to Python")
        result = copy.deepcopy(python_result)
        result.update(
            engine_requested="rust",
            engine_used="python-fallback",
            engine_fallback_reason=str(error)[:300],
        )
        return result
