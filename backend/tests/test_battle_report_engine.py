from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.services.battle_report_engine import evaluate_battle_report_with_engine


def report_fixture() -> dict:
    return {"seed_killmail_id": 1, "side_overrides": {}, "teams": [], "participants": [], "timeline": [], "composition": []}


@patch("app.services.battle_report_engine.subprocess.run")
def test_rust_mode_sends_versioned_candidates_over_stdin(run) -> None:
    payload = {"schema_version": "eqm.battle-report-input.v1", "rows": []}
    run.return_value = SimpleNamespace(
        returncode=0, stderr="", stdout=json.dumps({"schema_version": "eqm.battle-report-output.v1", "report": report_fixture()}),
    )
    result = evaluate_battle_report_with_engine(
        payload=payload,
        python_result=lambda: (_ for _ in ()).throw(AssertionError()),
        engine="rust",
        binary="/eqm-core",
    )
    assert result["engine_used"] == "rust"
    assert run.call_args.args[0] == ["/eqm-core", "battle-report", "--input", "-"]
    assert json.loads(run.call_args.kwargs["input"]) == payload


@patch("app.services.battle_report_engine._run_rust")
def test_shadow_mode_requires_exact_report_parity(run_rust) -> None:
    run_rust.return_value = report_fixture()
    result = evaluate_battle_report_with_engine(
        payload={}, python_result={"pilot": {}, "report": report_fixture(), "coverage": {}}, engine="shadow",
    )
    assert result["engine_used"] == "python-shadow"
    assert result["engine_shadow_match"] is True


@patch("app.services.battle_report_engine._run_rust", side_effect=FileNotFoundError("missing"))
def test_rust_failure_lazily_uses_complete_python_fallback(_run_rust) -> None:
    reference = {"pilot": {"character_id": 1}, "report": report_fixture(), "coverage": {}}
    result = evaluate_battle_report_with_engine(payload={}, python_result=lambda: reference, engine="rust")
    assert result["engine_used"] == "python-fallback"
    assert result["report"] == reference["report"]
    assert "missing" in result["engine_fallback_reason"]
