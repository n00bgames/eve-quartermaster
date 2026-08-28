from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.fitting_simulator import (
    capacitor_depletion_seconds,
    capacitor_recharge_at_percent,
    capacitor_stable_percent,
    percent_bonus_multiplier,
    stacking_multiplier,
    stacking_raw_multiplier,
    unpenalized_multiplier,
)


def assert_optional_approx(actual: float | None, expected: float | None) -> None:
    if expected is None:
        assert actual is None
    else:
        assert actual == pytest.approx(expected)


def test_shared_fitting_math_fixture_matches_python_reference() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    payload = json.loads((fixtures / "fitting-math-input.v1.json").read_text())
    expected = json.loads((fixtures / "fitting-math-output.v1.json").read_text())

    for case, result in zip(payload["stacking_cases"], expected["stacking_cases"], strict=True):
        assert stacking_raw_multiplier(case["raw_multipliers"]) == pytest.approx(result["raw_multiplier"])
        assert unpenalized_multiplier(case["unpenalized_multipliers"]) == pytest.approx(result["unpenalized_multiplier"])
        assert stacking_multiplier(case["dogma_values"]) == pytest.approx(result["dogma_multiplier"])
        assert percent_bonus_multiplier(case["percent_bonuses"]) == pytest.approx(result["percent_bonus_multiplier"])

    for case, result in zip(payload["capacitor_cases"], expected["capacitor_cases"], strict=True):
        assert capacitor_recharge_at_percent(
            case["capacity"], case["recharge_seconds"], case["sample_percent"]
        ) == pytest.approx(result["recharge_at_sample"])
        stable = capacitor_stable_percent(
            case["capacity"], case["recharge_seconds"], case["drain_per_second"]
        )
        depletion = capacitor_depletion_seconds(
            case["capacity"], case["recharge_seconds"], case["drain_per_second"]
        )
        assert_optional_approx(stable, result["stable_percent"])
        assert_optional_approx(depletion, result["depletion_seconds"])
