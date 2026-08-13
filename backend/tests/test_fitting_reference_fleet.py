from __future__ import annotations

import pytest

from tests.fitting_reference import (
    compute_reference_fixture,
    load_reference_fixture,
    metric_at_path,
    reference_fixture_paths,
)


REFERENCE_FIXTURES = reference_fixture_paths()


@pytest.mark.parametrize("fixture_path", REFERENCE_FIXTURES, ids=lambda path: path.stem)
def test_fitting_reference_fixture(fixture_path) -> None:
    fixture = load_reference_fixture(fixture_path)
    result = compute_reference_fixture(fixture)

    for expectation in fixture["expected"]:
        actual = metric_at_path(result, expectation["path"])
        assert actual == pytest.approx(
            float(expectation["value"]),
            abs=float(expectation.get("absolute_tolerance", 0.0)),
            rel=float(expectation.get("relative_tolerance", 1e-6)),
        ), f"{fixture_path.name}: {expectation['path']}"


def test_reference_fleet_contains_at_least_one_fixture() -> None:
    assert REFERENCE_FIXTURES, "Add at least one fitting reference fixture"
