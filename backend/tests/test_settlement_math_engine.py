from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.services.settlement_math_engine import evaluate_settlement_math_with_engine


def result_fixture() -> dict:
    return {
        "schema_version": "eqm.settlement-math-output.v1",
        "fixed_payout_total_cents": 0,
        "share_pool_cents": 100,
        "participant_payout_total_cents": 100,
        "unallocated_cents": 0,
        "participants": [{"index": 0, "payout_cents": 100, "payout_ratio_units": 10_000_000_000, "mineral_payouts": []}],
        "outputs": [],
    }


@patch("app.services.settlement_math_engine.subprocess.run")
def test_rust_mode_sends_versioned_contract_over_stdin(run) -> None:
    payload = {"schema_version": "eqm.settlement-math-input.v1", "participants": [], "outputs": []}
    run.return_value = SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(result_fixture()))
    result = evaluate_settlement_math_with_engine(payload=payload, python_result=lambda: (_ for _ in ()).throw(AssertionError()), engine="rust", binary="/eqm-core")
    assert result["engine_used"] == "rust"
    assert run.call_args.args[0] == ["/eqm-core", "settlement-math", "--input", "-"]
    assert json.loads(run.call_args.kwargs["input"]) == payload


@patch("app.services.settlement_math_engine._run_rust")
def test_shadow_mode_reports_exact_parity(run_rust) -> None:
    run_rust.return_value = result_fixture()
    result = evaluate_settlement_math_with_engine(payload={}, python_result=result_fixture(), engine="shadow")
    assert result["engine_used"] == "python-shadow"
    assert result["engine_shadow_match"] is True


@patch("app.services.settlement_math_engine._run_rust", side_effect=FileNotFoundError("missing"))
def test_rust_failure_lazily_uses_python_fallback(_run_rust) -> None:
    result = evaluate_settlement_math_with_engine(payload={}, python_result=result_fixture, engine="rust")
    assert result["engine_used"] == "python-fallback"
    assert "missing" in result["engine_fallback_reason"]
