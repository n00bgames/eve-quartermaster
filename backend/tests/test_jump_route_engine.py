from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.jump_route_engine import JumpRouteUnavailable, evaluate_jump_route_with_engine


def result_fixture() -> dict:
    return {
        "schema_version": "eqm.jump-route-output.v1",
        "path_system_ids": [1, 2, 3],
        "total_distance_ly": 9.5,
    }


@patch("app.services.jump_route_engine.subprocess.run")
def test_rust_mode_sends_versioned_graph_over_stdin(run) -> None:
    payload = {"schema_version": "eqm.jump-route-input.v1", "systems": []}
    run.return_value = SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(result_fixture()))

    def unused_reference() -> dict:
        raise AssertionError("Rust authority should not execute the Python reference")

    result = evaluate_jump_route_with_engine(
        payload=payload,
        python_result=unused_reference,
        engine="rust",
        binary="/test/eqm-core",
    )

    assert result["engine_used"] == "rust"
    assert run.call_args.args[0] == ["/test/eqm-core", "jump-route", "--input", "-"]
    assert json.loads(run.call_args.kwargs["input"]) == payload


@patch("app.services.jump_route_engine._run_rust")
def test_shadow_mode_reports_route_and_distance_parity(run_rust) -> None:
    rust_result = result_fixture()
    rust_result["total_distance_ly"] += 1e-10
    run_rust.return_value = rust_result

    result = evaluate_jump_route_with_engine(
        payload={"schema_version": "eqm.jump-route-input.v1"},
        python_result=result_fixture(),
        engine="shadow",
    )

    assert result["engine_used"] == "python-shadow"
    assert result["engine_shadow_match"] is True


@patch("app.services.jump_route_engine._run_rust")
def test_shadow_mode_detects_a_different_path(run_rust) -> None:
    rust_result = result_fixture()
    rust_result["path_system_ids"] = [1, 4, 3]
    run_rust.return_value = rust_result

    result = evaluate_jump_route_with_engine(
        payload={"schema_version": "eqm.jump-route-input.v1"},
        python_result=result_fixture(),
        engine="shadow",
    )

    assert result["engine_shadow_match"] is False


@patch("app.services.jump_route_engine._run_rust", side_effect=FileNotFoundError("missing"))
def test_rust_failure_lazily_uses_python_fallback(_run_rust) -> None:
    calls = 0

    def reference() -> dict:
        nonlocal calls
        calls += 1
        return result_fixture()

    result = evaluate_jump_route_with_engine(
        payload={"schema_version": "eqm.jump-route-input.v1"},
        python_result=reference,
        engine="rust",
    )

    assert calls == 1
    assert result["engine_used"] == "python-fallback"
    assert "missing" in result["engine_fallback_reason"]


@patch("app.services.jump_route_engine._run_rust", side_effect=JumpRouteUnavailable("No jump route found"))
def test_rust_no_route_is_a_domain_result_not_an_engine_fallback(_run_rust) -> None:
    def unused_reference() -> dict:
        raise AssertionError("A valid Rust no-route result must not execute the Python reference")

    with pytest.raises(JumpRouteUnavailable, match="No jump route found"):
        evaluate_jump_route_with_engine(
            payload={"schema_version": "eqm.jump-route-input.v1"},
            python_result=unused_reference,
            engine="rust",
        )
