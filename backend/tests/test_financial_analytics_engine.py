from __future__ import annotations

from unittest.mock import patch

from app.services.financial_analytics_engine import evaluate_financial_analytics_with_engine


def result_fixture() -> dict:
    return {
        "stats": {"current": 130.0, "net_change": 30.0},
        "points": [{"date": "2026-08-01", "value": 100.0}],
        "timeline": [],
    }


@patch("app.services.financial_analytics_engine._run_rust")
def test_rust_mode_is_authoritative_and_keeps_python_lazy(run_rust) -> None:
    run_rust.return_value = result_fixture()

    def unused_reference() -> dict:
        raise AssertionError("Rust authority should not execute the Python reference")

    result = evaluate_financial_analytics_with_engine(
        payload={"schema_version": "eqm.financial-analytics.v1", "operation": "personal"},
        python_result=unused_reference,
        engine="rust",
    )
    assert result["engine_used"] == "rust"
    assert result["stats"]["current"] == 130.0


@patch("app.services.financial_analytics_engine._run_rust")
def test_shadow_mode_reports_exact_parity(run_rust) -> None:
    run_rust.return_value = result_fixture()
    result = evaluate_financial_analytics_with_engine(
        payload={"schema_version": "eqm.financial-analytics.v1", "operation": "personal"},
        python_result=result_fixture,
        engine="shadow",
    )
    assert result["engine_used"] == "python-shadow"
    assert result["engine_shadow_match"] is True


@patch("app.services.financial_analytics_engine._run_rust", side_effect=FileNotFoundError("missing"))
def test_rust_failure_lazily_uses_python_fallback(_run_rust) -> None:
    calls = 0

    def reference() -> dict:
        nonlocal calls
        calls += 1
        return result_fixture()

    result = evaluate_financial_analytics_with_engine(
        payload={"schema_version": "eqm.financial-analytics.v1", "operation": "personal"},
        python_result=reference,
        engine="rust",
    )
    assert calls == 1
    assert result["engine_used"] == "python-fallback"
    assert "missing" in result["engine_fallback_reason"]
