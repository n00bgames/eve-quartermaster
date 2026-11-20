import asyncio
import ast
import importlib.util
import json
import re
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, EveType, EveSystem, EveStation, EveRegion, EveConstellation
from app.models.system_objects import EveSystemObject
from app.api import esi, fittings, pi_planner
from app.api.planetary_industry import local_planet_name
from app.services.gatecheck import kill_location
from app.services.intel_sources import PublicSource, IntelSourceError
from app.services.sde_importer import import_sde


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([EveSystem(system_id=30000001, name="Tanoo", security_status=.858324),
                         EveType(type_id=11, name="Planet (Temperate)", volume=1),
                         EveStation(station_id=60000001, system_id=30000001, name="Local station")])
        session.commit()
        yield session
    engine.dispose()


def test_official_fixture_zip_reimport_and_nullable_metadata(db, tmp_path):
    fixture = json.loads((Path(__file__).parent / "fixtures/universe-sde-3720952.json").read_text())
    archive = tmp_path / "sde.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name, row in fixture.items():
            if name == "_sde": continue
            row = dict(row)
            key = row.pop("_key")
            z.writestr(name + ".yaml", yaml.safe_dump({key: row}))
    for _ in range(2):
        result = import_sde(str(archive), db, sections={"celestials"})
        assert result["celestial_stars"] == 1
        assert result["celestial_planets"] == 1
    planet = db.get(EveSystemObject, 40000002)
    assert (planet.name, planet.type_id, planet.radius, planet.x) == ("Tanoo I", 11, 5060000, 161891117336.0)
    assert db.get(EveSystemObject, 40000004).name == "Tanoo I - Moon 1"
    star = db.get(EveSystemObject, 40000001)
    assert star.name == "Tanoo" and star.type_id == 45041
    assert star.x is None and star.y is None and star.z is None
    star.x, star.y, star.z, star.source = 0, 0, 0, "esi"
    db.commit()
    import_sde(str(archive), db, sections={"celestials"})
    assert star.x == 0 and star.source == "esi"
    from app.api.sde import sde_status
    assert sde_status(None, db)["celestials"] == 4
    assert local_planet_name(db, 40000002) == "Tanoo I"
    assert local_planet_name(db, 999) == "Planet 999"
    (tmp_path / "mapPlanets.yaml").write_text("99: {solarSystemID: 30000001, celestialIndex: 2}")
    import_sde(str(tmp_path), db, sections={"celestials"})
    assert db.get(EveSystemObject, 99).radius is None
    assert db.get(EveSystemObject, 99).type_id is None


def test_scout_local_type_radius_and_missing_data(db):
    db.add(EveSystemObject(object_id=40, system_id=30000001, kind="planet", name="Tanoo I", type_id=11, radius=5060000))
    db.commit()
    catalog = {2268: {"tier": 0, "planet_types": [pi_planner.PLANET_TYPES[11]]}}
    body = pi_planner.ScoutRequest(system_ids=[30000001], resource_type_ids=[2268])
    with patch.object(pi_planner, "authorize"), patch.object(pi_planner, "build_context", return_value={"catalog": catalog}), patch("app.services.esi_client.EsiClient.get", side_effect=AssertionError("Static ESI")):
        result = asyncio.run(pi_planner.scout(body, None, db))["systems"][0]
        assert result["score"] == 1 and result["covered_resources"] == [2268]
        assert result["planets"][0]["diameter_km"] == 10120
        db.get(EveSystemObject, 40).radius = None
        db.flush()
        missing = asyncio.run(pi_planner.scout(body, None, db))["systems"][0]
        assert missing["score"] == -1 and "Reimport" in missing["error"]


def test_manual_imports_metadata_and_gatecheck_local(db):
    client = AsyncMock()
    client.get.side_effect = AssertionError("Static ESI")
    with patch("app.services.esi_client.EsiClient.get", side_effect=AssertionError("Static ESI")):
        assert asyncio.run(esi.import_type(11, db))["name"] == "Planet (Temperate)"
        assert asyncio.run(esi.import_system(30000001, db))["name"] == "Tanoo"
        assert asyncio.run(esi.import_station(60000001, db))["name"] == "Local station"
        for fn in [esi.import_type, esi.import_system, esi.import_station]:
            with pytest.raises(HTTPException) as exc: asyncio.run(fn(999, db))
            assert exc.value.status_code == 404
        asyncio.run(esi.apply_type_metadata(client, db, {11, 999}))
        asyncio.run(esi.apply_skill_metadata(client, db, {11}))
        asyncio.run(fittings.refresh_public_type_metadata(db, {11, 998}))
        assert db.get(EveType, 11).volume == 1
        assert db.get(EveType, 999).name == "Type 999"
        assert db.get(EveType, 998).name == "Type 998"
        assert asyncio.run(kill_location(db, client, {"zkb": {"locationID": 60000001}}))["location_name"] == "Local station"
        assert asyncio.run(kill_location(db, client, {"zkb": {"locationID": 999}}))["location_name"] == "Location 999"
    client.get.assert_not_awaited()


def test_intel_local_metadata_and_dynamic_resolvers(db):
    db.add(EveRegion(region_id=1, name="Region"))
    db.add(EveConstellation(constellation_id=2, region_id=1, name="Constellation"))
    db.get(EveSystem, 30000001).constellation_id = 2
    db.commit()
    async def run():
        source = PublicSource(session_factory=sessionmaker(bind=db.bind))
        source.esi.get = AsyncMock(side_effect=AssertionError("Static ESI"))
        source.esi.post = AsyncMock(return_value=[])
        try:
            assert (await source.type_info(11))["name"] == "Planet (Temperate)"
            assert (await source.system_info(30000001))["region_name"] == "Region"
            with pytest.raises(IntelSourceError): await source.type_info(999)
            with pytest.raises(IntelSourceError): await source.system_info(999)
            await source.resolve(["Pilot"])
            await source.names([90000001])
            assert [c.args[0] for c in source.esi.post.await_args_list] == ["/universe/ids/", "/universe/names/"]
        finally: await source.close()
    asyncio.run(run())


def test_no_runtime_retiring_universe_requests():
    retired = re.compile(r"/universe/(types|groups|categories|systems|planets|moons|asteroid_belts|stars|stargates|stations|constellations|regions)/")
    for path in (Path(__file__).parents[1] / "app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "request"}:
                assert not retired.search(ast.unparse(node)), str(path)


def test_migration_roundtrip_preserves_old_rows():
    path = Path(__file__).parents[1] / "alembic/versions/0111_local_universe.py"
    spec = importlib.util.spec_from_file_location("migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE eve_system_objects (object_id BIGINT PRIMARY KEY, name VARCHAR(255))"))
        connection.execute(text("INSERT INTO eve_system_objects VALUES (1, 'Existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert connection.execute(text("SELECT name, type_id, radius FROM eve_system_objects")).one() == ("Existing", None, None)
            module.downgrade()
            assert [c["name"] for c in inspect(connection).get_columns("eve_system_objects")] == ["object_id", "name"]
    engine.dispose()
