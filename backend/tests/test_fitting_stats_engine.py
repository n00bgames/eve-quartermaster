from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

from app.services.fitting_stats_engine import _difference_paths, evaluate_fitting_stats_with_engine


def result_fixture() -> dict:
    return {
        "schema_version": "eqm.fitting-stats-output.v1",
        "offense": {},
        "defense": {},
        "mobility": {},
        "capacitor": {},
        "cargo_bays": [],
        "targeting": {},
        "notes": ["implementation-specific note"],
    }


@patch("app.services.fitting_stats_engine.subprocess.run")
def test_rust_mode_sends_full_stats_json_over_stdin(run) -> None:
    payload = {"schema_version": "eqm.fitting-stats-input.v1", "items": []}
    rust_result = result_fixture()
    run.return_value = SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(rust_result))

    result = evaluate_fitting_stats_with_engine(
        payload=payload,
        python_result=result_fixture(),
        engine="rust",
        binary="/test/eqm-core",
        timeout=1,
    )

    assert result["engine_used"] == "rust"
    assert run.call_args.args[0] == ["/test/eqm-core", "fitting-stats", "--input", "-"]
    assert json.loads(run.call_args.kwargs["input"]) == payload


@patch("app.services.fitting_stats_engine._run_rust")
def test_shadow_retains_python_and_ignores_notes_and_math_metadata(run_rust) -> None:
    python_result = result_fixture()
    python_result.update(math_engine_used="rust", math_engine_requested="rust")
    rust_result = copy.deepcopy(result_fixture())
    rust_result["notes"] = ["different Rust note"]
    run_rust.return_value = rust_result

    result = evaluate_fitting_stats_with_engine(
        payload={"schema_version": "eqm.fitting-stats-input.v1"},
        python_result=python_result,
        engine="shadow",
    )

    assert result["engine_used"] == "python-shadow"
    assert result["engine_shadow_match"] is True
    assert result["notes"] == ["implementation-specific note"]


@patch("app.services.fitting_stats_engine._run_rust", side_effect=FileNotFoundError("missing"))
def test_shadow_failure_keeps_python_authoritative(_run_rust) -> None:
    result = evaluate_fitting_stats_with_engine(
        payload={"schema_version": "eqm.fitting-stats-input.v1"},
        python_result=result_fixture(),
        engine="shadow",
    )

    assert result["engine_used"] == "python-shadow-error"
    assert result["engine_shadow_match"] is False
    assert "missing" in result["engine_fallback_reason"]


def test_difference_paths_are_float_tolerant_and_actionable() -> None:
    assert _difference_paths({"dps": 10.0}, {"dps": 10.0 + 1e-10}) == []
    assert _difference_paths({"offense": {"dps": 10.0}}, {"offense": {"dps": 11.0}}) == [
        "stats.offense.dps"
    ]
