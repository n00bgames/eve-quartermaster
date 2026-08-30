from __future__ import annotations

from unittest.mock import patch

from app.services.event_analytics_engine import evaluate_event_analytics_with_engine


def composition_fixture() -> dict:
    return {
        "totals": {
            "rsvp": {"going": 1},
            "registration": {"registered": 1},
            "confirmation": {"confirmed": 1},
            "attendance": {"attended": 0, "no_show": 0, "excused": 0, "unmarked": 1},
        },
        "roles": [{"label": "logistics", "count": 1}],
        "hulls": [{"label": "Guardian", "count": 1}],
        "role_requirements": [],
        "doctrine_requirements": [],
        "users_without_characters": 0,
    }


@patch("app.services.event_analytics_engine._run_rust")
def test_rust_mode_is_authoritative_and_keeps_python_lazy(run_rust) -> None:
    run_rust.return_value = composition_fixture()

    def unused_reference() -> dict:
        raise AssertionError("Rust authority should not execute the Python reference")

    result = evaluate_event_analytics_with_engine(
        payload={"schema_version": "eqm.event-analytics.v1", "operation": "composition"},
        python_result=unused_reference,
        engine="rust",
    )

    assert result["engine_used"] == "rust"
    assert result["roles"] == [{"label": "logistics", "count": 1}]


@patch("app.services.event_analytics_engine._run_rust")
def test_shadow_mode_reports_exact_parity(run_rust) -> None:
    run_rust.return_value = composition_fixture()

    result = evaluate_event_analytics_with_engine(
        payload={"schema_version": "eqm.event-analytics.v1", "operation": "composition"},
        python_result=composition_fixture,
        engine="shadow",
    )

    assert result["engine_used"] == "python-shadow"
    assert result["engine_shadow_match"] is True


@patch("app.services.event_analytics_engine._run_rust", side_effect=FileNotFoundError("missing"))
def test_rust_failure_lazily_uses_python_fallback(_run_rust) -> None:
    calls = 0

    def reference() -> dict:
        nonlocal calls
        calls += 1
        return composition_fixture()

    result = evaluate_event_analytics_with_engine(
        payload={"schema_version": "eqm.event-analytics.v1", "operation": "composition"},
        python_result=reference,
        engine="rust",
    )

    assert calls == 1
    assert result["engine_used"] == "python-fallback"
    assert "missing" in result["engine_fallback_reason"]
