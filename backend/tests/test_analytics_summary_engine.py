from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.services.analytics_summary_engine import evaluate_analytics_summary_with_engine


def result_fixture() -> dict:
    return {
        "schema_version": "eqm.analytics-summary-output.v1",
        "cards": {"wallet_total": 10, "blueprint_total": 2, "member_total": 3, "character_count": 1},
        "change_composition": {},
        "top_sp_gainers": [],
        "top_sp_losses": [],
        "top_skill_category_gainers": [],
        "top_skill_category_losses": [],
        "wallet_growth": [],
        "member_growth": [],
        "blueprint_growth": [],
        "standings_movement": {},
        "series": {},
    }


@patch("app.services.analytics_summary_engine.subprocess.run")
def test_rust_mode_sends_versioned_json_over_stdin(run) -> None:
    payload = {"schema_version": "eqm.analytics-summary-input.v1", "character_rows": []}
    rust_result = result_fixture()
    run.return_value = SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(rust_result))

    def unused_reference() -> dict:
        raise AssertionError("Rust authority should not execute the Python reference")

    result = evaluate_analytics_summary_with_engine(
        payload=payload,
        python_result=unused_reference,
        engine="rust",
        binary="/test/eqm-core",
    )

    assert result["engine_used"] == "rust"
    assert run.call_args.args[0] == ["/test/eqm-core", "analytics-summary", "--input", "-"]
    assert json.loads(run.call_args.kwargs["input"]) == payload


@patch("app.services.analytics_summary_engine._run_rust")
def test_shadow_mode_reports_numeric_parity(run_rust) -> None:
    python_result = result_fixture()
    rust_result = result_fixture()
    rust_result["cards"]["wallet_total"] = 10.000000001
    run_rust.return_value = rust_result

    result = evaluate_analytics_summary_with_engine(
        payload={"schema_version": "eqm.analytics-summary-input.v1"},
        python_result=python_result,
        engine="shadow",
    )

    assert result["engine_used"] == "python-shadow"
    assert result["engine_shadow_match"] is True


@patch("app.services.analytics_summary_engine._run_rust", side_effect=FileNotFoundError("missing"))
def test_rust_failure_keeps_python_fallback(_run_rust) -> None:
    result = evaluate_analytics_summary_with_engine(
        payload={"schema_version": "eqm.analytics-summary-input.v1"},
        python_result=result_fixture(),
        engine="rust",
    )

    assert result["engine_used"] == "python-fallback"
    assert "missing" in result["engine_fallback_reason"]
