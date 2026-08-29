from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.services.killboard_analytics_engine import evaluate_killboard_analytics_with_engine


def result_fixture() -> dict:
    return {
        "schema_version": "eqm.killboard-analytics-output.v1",
        "unknown_value_records": 0,
        "summary": {"kills": 1},
        "hulls": {}, "geography": {}, "opponents": [], "streaks": {}, "wingmates": [], "timeline": [],
    }


@patch("app.services.killboard_analytics_engine.subprocess.run")
def test_rust_mode_sends_versioned_events_over_stdin(run) -> None:
    payload = {"schema_version": "eqm.killboard-analytics-input.v1", "events": []}
    run.return_value = SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(result_fixture()))
    result = evaluate_killboard_analytics_with_engine(payload=payload, python_result=lambda: (_ for _ in ()).throw(AssertionError()), engine="rust", binary="/eqm-core")
    assert result["engine_used"] == "rust"
    assert run.call_args.args[0] == ["/eqm-core", "killboard-analytics", "--input", "-"]
    assert json.loads(run.call_args.kwargs["input"]) == payload


@patch("app.services.killboard_analytics_engine._run_rust")
def test_shadow_mode_requires_exact_parity(run_rust) -> None:
    run_rust.return_value = result_fixture()
    result = evaluate_killboard_analytics_with_engine(payload={}, python_result=result_fixture(), engine="shadow")
    assert result["engine_used"] == "python-shadow"
    assert result["engine_shadow_match"] is True


@patch("app.services.killboard_analytics_engine._run_rust", side_effect=FileNotFoundError("missing"))
def test_rust_failure_lazily_uses_python_fallback(_run_rust) -> None:
    result = evaluate_killboard_analytics_with_engine(payload={}, python_result=result_fixture, engine="rust")
    assert result["engine_used"] == "python-fallback"
    assert "missing" in result["engine_fallback_reason"]
