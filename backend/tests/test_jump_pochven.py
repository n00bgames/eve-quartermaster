import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.eve_static import EveConstellation, EveRegion, EveStargate, EveSystem
from app.services.jump_freighter import (
    LIGHT_YEAR_METERS, _alternate_jump_candidates, _jump_path,
    _known_space_systems, cyno_eligible, plan_jump_freighter_route, route_map_context, ship_config,
)
from app.services.navigation import POCHVEN_SYSTEM_IDS, search_systems


def system(system_id, name, x=0, security=0.1):
    return EveSystem(system_id=system_id, name=name, security_status=security,
                     x=x * LIGHT_YEAR_METERS, y=0, z=0)


class PochvenJumpPlannerTests(unittest.TestCase):
    def test_all_27_ids_are_ineligible_even_with_stale_region_or_security(self):
        self.assertEqual(len(POCHVEN_SYSTEM_IDS), 27)
        for system_id in POCHVEN_SYSTEM_IDS:
            with self.subTest(system_id=system_id):
                self.assertFalse(cyno_eligible(system(system_id, 'Pochven', security=-1)))
        self.assertTrue(cyno_eligible(system(30000142, 'Ordinary lowsec')))

    def test_endpoints_and_same_system_are_rejected_before_shortcut(self):
        pochven = system(30000157, 'Otela')
        normal = system(30000001, 'Normal')
        for origin, destination in [(pochven, normal), (normal, pochven), (pochven, pochven)]:
            with self.subTest(origin=origin.name, destination=destination.name):
                with self.assertRaisesRegex(ValueError, 'Pochven'):
                    _jump_path(None, origin, destination, 10)

    def test_manual_waypoint_rejected_before_route_engine(self):
        rows = [system(30000001, 'Origin'), system(30000002, 'Destination'), system(30000157, 'Otela')]
        with patch('app.services.jump_freighter.resolve_system', side_effect=rows), patch('app.services.jump_freighter._jump_path') as route:
            with self.assertRaisesRegex(ValueError, 'waypoint Otela is in Pochven'):
                plan_jump_freighter_route(None, 'Origin', 'Destination', ship_name='Rhea', waypoint_queries=['Otela'])
            route.assert_not_called()

    def test_pochven_not_in_engine_graph_and_cannot_bridge_a_gap(self):
        origin = system(30000001, 'Origin', 0)
        midpoint = system(30000157, 'Otela', 5, -1)
        destination = system(30000002, 'Destination', 10)
        for ship_name in ['Rhea', 'Widow', 'Avatar']:
            with self.subTest(ship=ship_name), patch('app.services.jump_freighter._known_space_systems', return_value=[origin, midpoint, destination]), patch('app.services.jump_freighter._station_safety_system_ids', return_value={midpoint.system_id, destination.system_id}):
                def evaluate(*, payload, python_result):
                    self.assertNotIn(midpoint.system_id, [row['system_id'] for row in payload['systems']])
                    return python_result()
                with patch('app.services.jump_freighter.evaluate_jump_route_with_engine', side_effect=evaluate):
                    with self.assertRaisesRegex(ValueError, 'No jump route found'):
                        _jump_path(None, origin, destination, 6, ship=ship_config(ship_name))

    def test_alternate_stop_excluded_even_with_station(self):
        pochven = system(30000157, 'Otela', 2, -1)
        normal = system(30000003, 'Normal', 3)
        rows = _alternate_jump_candidates([pochven, normal], system(1, 'Origin'), system(2, 'Planned', 4), None, 6,
                                         {pochven.system_id: {'station_count': 1, 'risks': {'safer'}}}, set())
        self.assertEqual([row['system'].name for row in rows], ['Normal'])

    def test_search_and_graph_exclude_ids_and_region_before_limit(self):
        engine = create_engine('sqlite://')
        try:
            for table in [EveRegion.__table__, EveConstellation.__table__, EveSystem.__table__, EveStargate.__table__]:
                table.create(engine)
            with Session(engine) as db:
                db.add(EveRegion(region_id=10000070, name='Pochven'))
                db.add(EveConstellation(constellation_id=20000001, region_id=10000070, name='Triglav'))
                db.flush()
                stale = system(30000157, 'Test A stale')
                region = system(30000003, 'Test B region')
                region.constellation_id = 20000001
                normal = system(30000001, 'Test C normal', security=0.9)
                db.add_all([stale, region, normal])
                db.flush()
                db.add(EveStargate(stargate_id=50000001, system_id=normal.system_id, destination_system_id=stale.system_id))
                db.commit()
                self.assertEqual(len(search_systems(db, 'Test')), 3)
                self.assertEqual([row['name'] for row in search_systems(db, 'Test', 1, exclude_pochven=True)], ['Test C normal'])
                self.assertEqual(search_systems(db, str(stale.system_id), exclude_pochven=True), [])
                self.assertEqual([row.name for row in _known_space_systems(db)], ['Test C normal'])
                self.assertFalse(cyno_eligible(region))
                context = route_map_context(db, [normal])
                self.assertEqual([row['system_id'] for row in context['systems']], [normal.system_id])
                self.assertEqual(context['stargates'], [])
        finally:
            engine.dispose()


if __name__ == '__main__':
    unittest.main()
