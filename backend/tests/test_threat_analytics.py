from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.services.gatecheck import gatecheck_score, python_threat_reduction, threat_observation_payload


def test_threat_payload_normalizes_exact_money_and_organization_names() -> None:
    row = SimpleNamespace(
        raw_json={
            "_eqm_names": {"10": "Resolved Corp", "20": "Resolved Alliance"},
            "attackers": [
                {"corporation_id": 10, "alliance_id": 20},
                {"corporation_id": 10, "alliance_id": 20},
            ],
        },
        killmail_time=datetime(2026, 8, 29, 12, tzinfo=timezone.utc),
        total_value=Decimal("123456789.12"),
        victim_hull="Badger",
        location_kind="gate",
        location_name="Stargate",
        final_blow_ship_type_name="Tornado",
        attacker_count=2,
        final_blow_corporation_id=10,
        final_blow_corporation_name="Final Corp",
        final_blow_alliance_id=20,
        final_blow_alliance_name="Final Alliance",
        victim_corporation_id=30,
        victim_corporation_name=None,
        victim_alliance_id=40,
        victim_alliance_name="Victim Alliance",
    )

    payload = threat_observation_payload(row)

    assert payload["total_value_cents"] == 12_345_678_912
    assert payload["attacker_corporations"] == ["Final Corp", "Final Corp"]
    assert payload["attacker_alliances"] == ["Final Alliance", "Final Alliance"]
    assert payload["victim_corporation"] == "Corporation 30"
    assert payload["victim_alliance"] == "Victim Alliance"


def test_gatecheck_score_accepts_a_fixed_evaluation_time() -> None:
    evaluated_at = datetime(2026, 8, 29, 12, 30, tzinfo=timezone.utc)
    assert gatecheck_score(2, 2_000_000_000, "2026-08-29T12:00:00+00:00", 24, evaluated_at) == 65


def test_python_reference_reducer_preserves_pvp_ranking_shape() -> None:
    row = SimpleNamespace(
        raw_json={"attackers": []},
        killmail_time=datetime(2026, 8, 29, 12, tzinfo=timezone.utc),
        total_value=Decimal("1500000000.00"),
        victim_hull="Badger",
        location_kind="gate",
        location_name="Stargate",
        final_blow_ship_type_name="Tornado",
        attacker_count=3,
        final_blow_corporation_id=None,
        final_blow_corporation_name=None,
        final_blow_alliance_id=None,
        final_blow_alliance_name=None,
        victim_corporation_id=30,
        victim_corporation_name="Haulers",
        victim_alliance_id=None,
        victim_alliance_name=None,
    )
    result = python_threat_reduction(
        [row],
        evaluated_at=datetime(2026, 8, 29, 12, 30, tzinfo=timezone.utc),
        refresh_hours=24,
        include_victim_organizations=True,
    )

    assert result["total_kills"] == 1
    assert result["risk_score"] == 50
    assert result["top_victim_hulls"] == [{"name": "Badger", "count": 1, "total_value": 1_500_000_000.0}]
    assert result["top_victim_corporations"][0]["name"] == "Haulers"
