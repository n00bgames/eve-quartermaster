import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, EveSystem, EveStargate, EveStation, EsiToken, User
from app.models.system_objects import NavigationStructure, SystemObjectSync, EveSystemObject
from app.services.system_distances import position, store_public, system_objects, refresh_public, refresh_structures
from app.services.sde_importer import import_sde


class SystemDistanceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([EveSystem(system_id=1, name="Test", x=9e20, y=9e20, z=9e20), EveSystem(system_id=2, name="Other")])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def token(self, token_id, user_id, revoked=False, scope="esi-universe.read_structures.v1"):
        row = EsiToken(id=token_id, user_id=user_id, character_id=token_id, scopes=scope, encrypted_refresh_token="test", revoked_at=datetime.now(timezone.utc) if revoked else None)
        self.db.add(row)
        self.db.commit()
        return row

    def structure(self, token_id, structure_id, expired=False):
        now = datetime.now(timezone.utc)
        row = NavigationStructure(token_id=token_id, structure_id=structure_id, system_id=1, name=f"Private {structure_id}", x=1, y=2, z=3, checked_at=now, expires_at=now + timedelta(hours=-1 if expired else 1))
        self.db.add(row)
        self.db.commit()
        return row

    def test_missing_and_nonfinite_positions_are_not_zero(self):
        self.assertEqual(position({}), dict(x=None, y=None, z=None))
        self.assertEqual(position({"position": {"x": 0, "y": "nan", "z": "bad"}}), dict(x=0., y=None, z=None))

    def test_catalog_order_and_fallback_coordinates(self):
        store_public(self.db, 50, 1, "moon", "Test I - Moon 1", dict(x=0,y=0,z=0), "sde")
        store_public(self.db, 40, 1, "planet", "Test I", dict(x=2,y=3,z=4), "sde")
        store_public(self.db, 10, 1, "gate", "ESI gate", dict(x=5,y=0,z=0), "esi")
        self.db.add(EveStargate(stargate_id=10, system_id=1, destination_system_id=2))
        self.db.add(EveStation(station_id=20, system_id=1, name="Station", x=1, y=1, z=1))
        self.db.commit()
        result = system_objects(self.db, 1, 1)
        self.assertEqual([o["kind"] for o in result["objects"]], ["gate", "station", "planet", "moon"])
        self.assertEqual(result["objects"][0]["position"]["x"], 5)
        self.assertTrue(all(o["position"]["x"] != 9e20 for o in result["objects"]))
        self.assertIsInstance(result["objects"][0]["object_id"], str)

    def test_private_cache_is_token_scoped_and_expires(self):
        self.token(1, 1)
        self.token(2, 2)
        self.token(3, 1, revoked=True)
        self.token(4, 1, scope="")
        for token_id in range(1, 5): self.structure(token_id, 100 + token_id)
        self.structure(1, 105, expired=True)
        self.assertEqual([o["object_id"] for o in system_objects(self.db, 1, 1)["objects"]], ["101"])
        self.assertEqual([o["object_id"] for o in system_objects(self.db, 1, 2)["objects"]], ["102"])

    def test_unknown_system_rejected(self):
        with self.assertRaises(HTTPException) as caught: system_objects(self.db, 999, 1)
        self.assertEqual(caught.exception.status_code, 404)

    def test_sde_celestial_import_names_coordinates_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "mapPlanets.yaml").write_text("40: {solarSystemID: 1, celestialIndex: 4, position: {x: 100, y: 0, z: 0}}")
            (root / "mapMoons.yaml").write_text("41: {solarSystemID: 1, celestialIndex: 4, orbitIndex: 2, position: {x: 101, y: 0, z: 0}}")
            for _ in range(2):
                stats = import_sde(directory, self.db, sections={"celestials"})
                self.assertEqual(stats["celestials"], 2)
            self.assertEqual(self.db.get(EveSystemObject, 40).name, "Test IV")
            self.assertEqual(self.db.get(EveSystemObject, 41).name, "Test IV - Moon 2")
            self.assertEqual(self.db.get(EveSystemObject, 41).x, 101)

    def test_public_esi_nested_manifest_and_cache(self):
        client = AsyncMock()
        async def get(path):
            if path == "/universe/systems/1/":
                return {"name": "Test", "star_id": 99, "stargates": [10], "stations": [20], "planets": [{"planet_id": 40, "moons": [50], "asteroid_belts": [60]}]}
            return {"name": path, "system_id": 1, "position": {"x": 10, "y": 20, "z": 30}}
        client.get.side_effect = get
        asyncio.run(refresh_public(self.db, 1, client))
        self.db.commit()
        self.assertEqual(len(system_objects(self.db, 1, 1)["objects"]), 6)
        self.assertEqual(self.db.get(EveSystemObject, 99).x, 0)
        self.assertEqual(client.get.await_count, 6)
        asyncio.run(refresh_public(self.db, 1, client))
        self.assertEqual(client.get.await_count, 6)

    def test_partial_esi_preserves_existing_position(self):
        store_public(self.db, 40, 1, "planet", "Test I", dict(x=2,y=3,z=4), "sde")
        self.db.commit()
        client = AsyncMock()
        client.get.side_effect = [{"name": "Test", "planets": [{"planet_id": 40}]}, HTTPException(503)]
        message = asyncio.run(refresh_public(self.db, 1, client))
        self.assertIn("1 unavailable", message)
        self.assertEqual(self.db.get(EveSystemObject, 40).x, 2)

    def test_resolver_uses_only_own_token_and_rejects_other_system(self):
        self.token(1, 1); self.token(2, 2)
        with patch("app.api.esi.refresh_access_token", new_callable=AsyncMock, return_value="private") as refresh, patch("app.services.system_distances.EsiClient") as factory:
            factory.return_value.get = AsyncMock(return_value={"name": "Secret", "solar_system_id": 2, "position": {"x": 1, "y": 2, "z": 3}})
            self.assertEqual(asyncio.run(refresh_structures(self.db, 1, 1, 123)), 0)
            self.assertEqual(refresh.await_args.args[0].user_id, 1)
            self.assertEqual(refresh.await_count, 1)
            self.assertIsNone(self.db.get(NavigationStructure, (1, 123)))

    def test_successful_resolve_is_private_and_403_removes_cached_row(self):
        self.token(1, 1)
        with patch("app.api.esi.refresh_access_token", new_callable=AsyncMock, return_value="private"), patch("app.services.system_distances.EsiClient") as factory:
            factory.return_value.get = AsyncMock(return_value={"name": "My structure", "solar_system_id": 1, "position": {"x": 1, "y": 2, "z": 3}})
            self.assertEqual(asyncio.run(refresh_structures(self.db, 1, 1, 123)), 1)
            self.assertEqual(len(system_objects(self.db, 1, 1)["objects"]), 1)
            self.assertEqual(system_objects(self.db, 1, 2)["objects"], [])
            factory.return_value.get.side_effect = HTTPException(403)
            asyncio.run(refresh_structures(self.db, 1, 1, 123))
            self.assertEqual(system_objects(self.db, 1, 1)["objects"], [])

    def test_empty_structure_candidates_do_not_refresh_tokens(self):
        self.token(1, 1)
        with patch("app.api.esi.refresh_access_token", new_callable=AsyncMock) as refresh:
            self.assertEqual(asyncio.run(refresh_structures(self.db, 1, 1)), 0)
            refresh.assert_not_awaited()

    def test_missing_esi_coordinates_preserve_valid_sde_data(self):
        store_public(self.db, 40, 1, "planet", "Test I", dict(x=2,y=3,z=4), "sde")
        self.db.commit()
        client = AsyncMock()
        client.get.side_effect = [{"name": "Test", "planets": [{"planet_id": 40}]}, {"name": "Test I"}]
        message = asyncio.run(refresh_public(self.db, 1, client))
        self.assertIn("1 unavailable", message)
        self.assertEqual(self.db.get(EveSystemObject, 40).x, 2)

    def test_navigation_permission_applies_to_new_routes(self):
        from app.api.auth import get_current_user
        from app.api.navigation import router
        from app.db.session import get_db
        app = FastAPI(); app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_user] = lambda: User(id=1, email="test@example.invalid", display_name="Test", role="member")
        with TestClient(app) as client, patch("app.api.navigation.can_view_section", return_value=False):
            for path, method in (("/navigation/systems/1/objects", "get"), ("/navigation/systems/1/objects/sync", "post"), ("/navigation/systems/1/objects/structures/123", "post")):
                self.assertEqual(getattr(client, method)(path).status_code, 403)

if __name__ == "__main__": unittest.main()
