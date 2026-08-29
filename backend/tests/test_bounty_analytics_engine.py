from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.services.bounty_analytics import timeline_bucket_start
from app.services.bounty_analytics_engine import evaluate_bounty_analytics_with_engine


def result_fixture() -> dict:
    return {
        "schema_version": "eqm.bounty-analytics-output.v1",
        "summary": {"net_isk": 2850.0, "tick_count": 2},
        "timeline": [{"bucket_start": "2026-08-18T05:00:00Z", "net_isk": 2850.0}],
        "leaderboard": [{"rank": 1, "character_eve_id": 90000001, "net_isk": 2850.0}],
    }


@patch("app.services.bounty_analytics_engine.subprocess.run")
def test_rust_mode_sends_versioned_ticks_over_stdin(run) -> None:
    payload = {"schema_version": "eqm.bounty-analytics-input.v1", "ticks": []}
    run.return_value = SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(result_fixture()))

    def unused_reference() -> dict:
        raise AssertionError("Rust authority should not execute the Python reference")

    result = evaluate_bounty_analytics_with_engine(
        payload=payload,
        python_result=unused_reference,
        engine="rust",
        binary="/test/eqm-core",
    )

    assert result["engine_used"] == "rust"
    assert run.call_args.args[0] == ["/test/eqm-core", "bounty-analytics", "--input", "-"]
    assert json.loads(run.call_args.kwargs["input"]) == payload


@patch("app.services.bounty_analytics_engine._run_rust")
def test_shadow_mode_reports_numeric_parity(run_rust) -> None:
    rust_result = result_fixture()
    rust_result["summary"]["net_isk"] += 1e-9
    run_rust.return_value = rust_result

    result = evaluate_bounty_analytics_with_engine(
        payload={"schema_version": "eqm.bounty-analytics-input.v1"},
        python_result=result_fixture(),
        engine="shadow",
    )

    assert result["engine_used"] == "python-shadow"
    assert result["engine_shadow_match"] is True


@patch("app.services.bounty_analytics_engine._run_rust", side_effect=FileNotFoundError("missing"))
def test_rust_failure_lazily_uses_python_fallback(_run_rust) -> None:
    calls = 0

    def reference() -> dict:
        nonlocal calls
        calls += 1
        return result_fixture()

    result = evaluate_bounty_analytics_with_engine(
        payload={"schema_version": "eqm.bounty-analytics-input.v1"},
        python_result=reference,
        engine="rust",
    )

    assert calls == 1
    assert result["engine_used"] == "python-fallback"
    assert "missing" in result["engine_fallback_reason"]


def test_daily_bucket_preparation_uses_reporting_timezone_and_returns_utc() -> None:
    first = timeline_bucket_start(datetime(2026, 8, 18, 4, 30, tzinfo=timezone.utc), "daily", "America/Chicago")
    second = timeline_bucket_start(datetime(2026, 8, 18, 6, 30, tzinfo=timezone.utc), "daily", "America/Chicago")

    assert first == datetime(2026, 8, 17, 5, tzinfo=timezone.utc)
    assert second == datetime(2026, 8, 18, 5, tzinfo=timezone.utc)
