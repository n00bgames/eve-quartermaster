from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.fitting_simulator import fitting_stats_payload


def test_full_fitting_stats_payload_is_versioned_and_json_safe() -> None:
    fitting = SimpleNamespace(
        ship_type_id=100,
        items=[
            SimpleNamespace(
                id=1,
                type_id=200,
                charge_type_id=None,
                flag="HiSlot0",
                quantity=1,
                simulation_state="active",
            )
        ],
    )

    payload = fitting_stats_payload(
        fitting,
        {"shieldCapacity": 1000.0},
        {100: {"shieldCapacity": 1000.0}, 200: {"cpu": 10.0}},
        {100: [{"effect_id": 1, "modifier_info": []}]},
        {100: "Contract Hull", 200: "Contract Module"},
        {200: "Energy Weapon"},
        {200: 53},
        {3416: 5},
        {"Shield Management": 5},
        {200: 5.0},
        100.0,
        1_000_000.0,
        {9002, 9001},
        False,
        {1},
    )

    assert payload["schema_version"] == "eqm.fitting-stats-input.v1"
    assert payload["items"] == [{
        "id": 1,
        "type_id": 200,
        "charge_type_id": None,
        "flag": "HiSlot0",
        "quantity": 1,
        "simulation_state": "active",
    }]
    assert payload["implant_type_ids"] == [9001, 9002]
    assert payload["stats_item_ids"] == [1]
    assert json.loads(json.dumps(payload))["dogma"]["200"]["cpu"] == 10.0
