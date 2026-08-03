import unittest
from unittest.mock import patch

from app.models.eve_static import EveSystem
from app.services.jump_freighter import (
    LIGHT_YEAR_METERS,
    _alternate_jump_candidates,
    _alternate_station_status,
    _waypoint_assisted_jump_path,
)


def system(system_id: int, name: str, x_ly: float, security: float = 0.1) -> EveSystem:
    return EveSystem(
        system_id=system_id,
        name=name,
        security_status=security,
        security_class=None,
        x=x_ly * LIGHT_YEAR_METERS,
        y=0.0,
        z=0.0,
    )


class JumpFreighterAlternateTests(unittest.TestCase):
    def test_station_status_calls_out_missing_and_red_only_stations(self) -> None:
        self.assertEqual(_alternate_station_status(None), "no_station")
        self.assertEqual(_alternate_station_status({"station_count": 2, "risks": {"dangerous"}}), "red_only")
        self.assertEqual(_alternate_station_status({"station_count": 2, "risks": {"dangerous", "safer"}}), "station_available")

    def test_alternates_must_reach_the_next_planned_waypoint(self) -> None:
        origin = system(1, "Origin", 0)
        planned = system(2, "Planned", 4)
        following = system(3, "Following", 8)
        usable = system(4, "Usable", 3)
        cannot_rejoin = system(5, "Stranded", 1)
        highsec = system(6, "Highsec", 3.5, 0.9)

        rows = _alternate_jump_candidates(
            [origin, planned, following, usable, cannot_rejoin, highsec],
            origin,
            planned,
            following,
            5.0,
            {usable.system_id: {"station_count": 1, "risks": {"dangerous"}}},
            {origin.system_id, planned.system_id, following.system_id},
        )

        self.assertEqual([row["system"].name for row in rows], ["Usable"])
        self.assertEqual(rows[0]["station_status"], "red_only")
        self.assertEqual(rows[0]["rejoin_distance_ly"], 5.0)

    def test_required_cyno_waypoint_is_a_route_constraint_not_a_direct_leg(self) -> None:
        origin = system(1, "Origin", 0, 0.9)
        waypoint = system(2, "Existing Cyno", 9)
        destination = system(3, "Destination", 15)

        with patch(
            "app.services.jump_freighter._jump_path",
            side_effect=[[1, 10, 2], [2, 11, 3]],
        ) as route_segment:
            path = _waypoint_assisted_jump_path(
                None,  # type: ignore[arg-type]
                origin,
                destination,
                [waypoint],
                7.0,
                "any",
                set(),
            )

        self.assertEqual(path, [1, 10, 2, 11, 3])
        self.assertTrue(route_segment.call_args_list[0].kwargs["allow_unstationed_destination"])
        self.assertFalse(route_segment.call_args_list[1].kwargs["allow_unstationed_destination"])




if __name__ == "__main__":
    unittest.main()