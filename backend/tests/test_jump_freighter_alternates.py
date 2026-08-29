import unittest
from unittest.mock import patch

from app.models.assets import Location
from app.models.enums import LocationKind
from app.models.eve_static import EveSystem
from app.services.jump_freighter import (
    LIGHT_YEAR_METERS,
    _alternate_jump_candidates,
    _alternate_station_status,
    _fetch_system_kill_counts,
    _jump_path,
    _waypoint_assisted_jump_path,
    _station_profiles,
    ship_config,
    stations_by_system,
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
    @patch("app.services.jump_freighter.httpx.Client")
    def test_system_kill_counts_parse_hourly_ship_and_pod_activity(self, client_factory) -> None:
        response = client_factory.return_value.__enter__.return_value.get.return_value
        response.json.return_value = [
            {"system_id": 30_000_142, "ship_kills": 12, "pod_kills": 4, "npc_kills": 90},
            {"system_id": "bad", "ship_kills": 99},
        ]

        self.assertEqual(
            _fetch_system_kill_counts(),
            {30_000_142: {"ship_kills": 12, "pod_kills": 4, "npc_kills": 90}},
        )
        response.raise_for_status.assert_called_once_with()

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

    def test_supercapital_route_allows_open_space_midpoints_but_requires_keepstar_destination(self) -> None:
        origin = system(1, "Origin", 0)
        midpoint = system(2, "Open-space cyno", 5)
        destination = system(3, "Keepstar destination", 10)
        avatar = ship_config("Avatar")

        with (
            patch("app.services.jump_freighter._known_space_systems", return_value=[origin, midpoint, destination]),
            patch("app.services.jump_freighter._station_safety_system_ids", return_value={destination.system_id}),
        ):
            path = _jump_path(None, origin, destination, 6.0, ship=avatar)  # type: ignore[arg-type]

        self.assertEqual(path, [origin.system_id, midpoint.system_id, destination.system_id])

        with (
            patch("app.services.jump_freighter._known_space_systems", return_value=[origin, midpoint, destination]),
            patch("app.services.jump_freighter._station_safety_system_ids", return_value=set()),
        ):
            with self.assertRaisesRegex(ValueError, "no known Keepstar"):
                _jump_path(None, origin, destination, 6.0, ship=avatar)  # type: ignore[arg-type]

    def test_supercapital_pos_mode_allows_unstationed_final_destination(self) -> None:
        origin = system(1, "Origin", 0)
        midpoint = system(2, "Open-space midpoint", 5)
        destination = system(3, "POS destination", 10)

        with patch("app.services.jump_freighter._known_space_systems", return_value=[origin, midpoint, destination]):
            path = _jump_path(
                None,  # type: ignore[arg-type]
                origin,
                destination,
                6.0,
                station_safety="pos",
                ship=ship_config("Avatar"),
            )

        self.assertEqual(path, [origin.system_id, midpoint.system_id, destination.system_id])

    def test_non_supercapital_route_rejects_pos_destination_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "available only for supercarriers and titans"):
            _jump_path(
                None,  # type: ignore[arg-type]
                system(1, "Origin", 0),
                system(2, "Destination", 5),
                6.0,
                station_safety="pos",
                ship=ship_config("Rhea"),
            )

    def test_non_supercapital_route_still_requires_dockable_midpoints(self) -> None:
        origin = system(1, "Origin", 0)
        midpoint = system(2, "No station", 5)
        destination = system(3, "Station destination", 10)

        with (
            patch("app.services.jump_freighter._known_space_systems", return_value=[origin, midpoint, destination]),
            patch("app.services.jump_freighter._station_safety_system_ids", return_value={destination.system_id}),
        ):
            with self.assertRaisesRegex(ValueError, "No jump route found"):
                _jump_path(None, origin, destination, 6.0, ship=ship_config("Rhea"))  # type: ignore[arg-type]

    def test_supercapital_profiles_only_known_keepstars(self) -> None:
        keepstar = Location(
            id=1,
            location_kind=LocationKind.STRUCTURE,
            eve_location_id=1_000_000_000_001,
            type_id=35834,
            name="Friendly Keepstar",
            system_id=30_000_001,
        )
        with patch("app.services.jump_freighter._keepstar_locations", return_value=[keepstar]):
            profiles = _station_profiles(None, ship_config("Nyx"))  # type: ignore[arg-type]

        self.assertEqual(profiles, {30_000_001: {"station_count": 1, "risks": {"safer"}}})

    def test_supercapital_station_list_serializes_keepstars_only(self) -> None:
        keepstar = Location(
            id=1,
            location_kind=LocationKind.STRUCTURE,
            eve_location_id=1_000_000_000_001,
            type_id=35834,
            name="Friendly Keepstar",
            system_id=30_000_001,
        )
        with patch("app.services.jump_freighter._keepstar_locations", return_value=[keepstar]):
            rows = stations_by_system(None, [30_000_001], ship_config("Nyx"))  # type: ignore[arg-type]

        self.assertEqual([row["name"] for row in rows[30_000_001]], ["Friendly Keepstar"])
        self.assertEqual(rows[30_000_001][0]["location_kind"], "structure")
        self.assertEqual(rows[30_000_001][0]["type_name"], "Keepstar")




if __name__ == "__main__":
    unittest.main()
