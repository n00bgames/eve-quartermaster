import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.mission_atlas import router, owned_lp_token, LP_SCOPE
from app.api.navigation import require_navigation
from app.db.session import get_db
from app.models import Base, EveSystem, EveStation, EveStargate, EveCharacter, EsiToken
from app.models.mission_atlas import EveAgent
from app.services.agent_import import import_agents
from app.services.mission_atlas import find_agents, catalog
from app.services.atlas_distances import python_distances
from app.services import atlas_esi


class AtlasTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://",poolclass=StaticPool,connect_args={"check_same_thread":False})
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine)
        self.db.add_all([EveSystem(system_id=1,name="Origin",security_status=.9,x=0,y=0,z=0),
            EveSystem(system_id=2,name="Neighbor",security_status=.449,x=1,y=0,z=2),
            EveSystem(system_id=3,name="Isolated",security_status=.45,x=3,y=0,z=1)])
        self.db.add_all([EveStargate(stargate_id=11,system_id=1,destination_system_id=2),
            EveStargate(stargate_id=12,system_id=2,destination_system_id=1),
            EveStation(station_id=60000001,system_id=2,name="Test Station",owner_id=1000035,owner_name="Test Navy")])
        self.db.add_all([EveAgent(agent_id=10,name="Nearby",corporation_id=1000035,corporation_name="Test Navy",level=4,
            system_id=2,location_id=60000001,division_id=24),
            EveAgent(agent_id=20,name="Remote",corporation_id=1000035,corporation_name="Test Navy",level=4,system_id=3,division_id=24)])
        self.db.add(EveCharacter(id=1,character_id=90000001,name="Private Pilot"))
        self.db.add(EsiToken(id=1,user_id=1,character_id=1,scopes=LP_SCOPE,encrypted_refresh_token="test"))
        self.db.commit()
        self.app=FastAPI();self.app.include_router(router)
        self.app.dependency_overrides[get_db]=lambda:self.db
        self.app.dependency_overrides[require_navigation]=lambda:SimpleNamespace(id=1)
        self.client=TestClient(self.app)

    def tearDown(self):
        self.client.close();self.db.close();self.engine.dispose()

    def test_catalog_includes_counts_and_gate_edges(self):
        payload=self.client.get("/navigation/atlas/catalog").json()
        self.assertEqual(payload["agent_count"],2)
        neighbor=next(s for s in payload["systems"] if s["system_id"]==2)
        self.assertEqual((neighbor["station_count"],neighbor["agent_count"]),(1,1))
        self.assertIn([1,2],payload["edges"])

    def test_agent_radius_and_security_boundary_and_paging(self):
        with patch("app.services.mission_atlas.gate_distances",side_effect=python_distances):
            self.assertEqual(find_agents(self.db,origin_id=1,max_jumps=0)["total"],0)
            result=find_agents(self.db,origin_id=1,max_jumps=1)
            self.assertEqual(result["total"],1);self.assertEqual(result["agents"][0]["jumps"],1)
        result=find_agents(self.db,highsec_only=True)
        self.assertEqual(result["agents"][0]["name"],"Remote")
        self.assertEqual(find_agents(self.db,q="Test Navy",offset=1,limit=1)["total"],2)
        self.assertEqual(self.client.get("/navigation/atlas/agents?max_jumps=5").status_code,400)

    def test_detail_links_unknown_system(self):
        detail=self.client.get("/navigation/atlas/systems/2").json()
        self.assertEqual(detail["links"]["zkill"],"https://zkillboard.com/system/2/")
        self.assertEqual(detail["agents"][0]["station_name"],"Test Station")
        self.assertEqual(self.client.get("/navigation/atlas/systems/999").status_code,404)

    def test_owner_only_lp_even_for_another_account(self):
        self.app.dependency_overrides[require_navigation]=lambda:SimpleNamespace(id=2,role="admin")
        with patch("app.api.mission_atlas.refresh_access_token",new_callable=AsyncMock) as refresh:
            self.assertEqual(self.client.get("/navigation/atlas/characters/1/loyalty").status_code,403)
            refresh.assert_not_awaited()
        self.assertEqual(self.client.get("/navigation/atlas/characters").json(),[])

    def test_revoked_missing_scope_and_optout(self):
        token=self.db.get(EsiToken,1);token.scopes="publicData";self.db.commit()
        self.assertEqual(self.client.get("/navigation/atlas/characters/1/loyalty").status_code,400)
        token.scopes=LP_SCOPE;self.db.get(EveCharacter,1).sync_opt_out=True;self.db.commit()
        self.assertEqual(self.client.get("/navigation/atlas/characters/1/loyalty").status_code,403)
        token.revoked_at=datetime.now(timezone.utc);self.db.commit()
        self.assertEqual(self.client.get("/navigation/atlas/characters/1/loyalty").status_code,404)

    def test_lp_read_is_private_and_uses_external_character_id(self):
        with patch("app.api.mission_atlas.refresh_access_token",new=AsyncMock(return_value="test")), \
             patch("app.api.mission_atlas.EsiClient.get_with_headers",new=AsyncMock(return_value=(
                 [{"corporation_id":1000035,"loyalty_points":2345}],httpx.Headers()))) as get:
            response=self.client.get("/navigation/atlas/characters/1/loyalty")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers["cache-control"],"private, no-store")
        self.assertEqual(response.json()["balances"][0]["loyalty_points"],2345)
        get.assert_awaited_once_with("/characters/90000001/loyalty/points/")

    def test_public_offers_expose_all_costs_and_not_private_lp(self):
        payload=dict(data=[dict(offer_id=7,type_id=99,quantity=5,lp_cost=100,isk_cost=200,ak_cost=3,
            required_items=[dict(type_id=98,quantity=2)])],observed_at=None,
            expires_at=datetime.now(timezone.utc),stale=False,error=None)
        with patch("app.api.mission_atlas.public_snapshot",new=AsyncMock(return_value=payload)):
            result=self.client.get("/navigation/atlas/stores/1000035/offers").json()["data"][0]
        self.assertEqual(result["ak_cost"],3);self.assertEqual(result["required_items"][0]["quantity"],2)
        self.assertNotIn("balance",result)

    def test_modern_and_legacy_imports_and_unknown_locations(self):
        class Source:
            def __init__(self,data):self.data=data
            def load_yaml(self,key):
                if key not in self.data:raise FileNotFoundError(key)
                return self.data[key]
        corp={1000035:{"name":{"en":"Test Navy"},"factionID":500001}}
        data={"npc_characters":{50:{"name":{"en":"Modern"},"corporationID":1000035,"locationID":60000001,
            "agent":{"level":3,"divisionID":24,"agentTypeID":2}}},"npc_corporations":corp}
        self.assertEqual(import_agents(Source(data),self.db),1)
        self.assertEqual(self.db.get(EveAgent,50).system_id,2)
        data={"npc_characters":{1:{"name":{"en":"CEO"}}},"npc_corporations":corp,
            "agents":{60:{"corporationID":1000035,"locationID":999,"level":2}},
            "station_names":[{"itemID":60,"itemName":"Legacy"}]}
        self.assertEqual(import_agents(Source(data),self.db),1)
        self.assertEqual(self.db.get(EveAgent,60).name,"Legacy")
        self.assertIsNone(self.db.get(EveAgent,60).system_id)
        self.assertEqual(import_agents(Source({}),self.db),0)
        self.assertIsNotNone(self.db.get(EveAgent,60))

    def test_bfs_handles_cycles_and_disconnected_systems(self):
        self.assertEqual(python_distances(1,[[1,2],[2,1],[2,3],[1,3],[3,4],[9,8]]),{1:0,2:1,3:1,4:2})


class ActivityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        atlas_esi._cache.clear()

    async def test_cached_hourly_snapshot_and_failure_staleness(self):
        now=datetime.now(timezone.utc)
        headers=httpx.Headers({"Last-Modified":"Sat, 19 Sep 2026 10:00:00 GMT", "Expires":(now+timedelta(hours=1)).strftime("%a, %d %b %Y %H:%M:%S GMT")})
        with patch("app.services.atlas_esi.EsiClient.get_with_headers",new=AsyncMock(return_value=([{"system_id":1,"ship_kills":2}],headers))) as fetch:
            a=await atlas_esi.public_snapshot("/test/");b=await atlas_esi.public_snapshot("/test/")
            self.assertEqual(a["observed_at"],"2026-09-19T10:00:00+00:00");fetch.assert_awaited_once()
        atlas_esi._cache["/test/"]["expires_at"]=now-timedelta(seconds=1)
        with patch("app.services.atlas_esi.EsiClient.get_with_headers",new=AsyncMock(side_effect=RuntimeError("offline"))):
            stale=await atlas_esi.public_snapshot("/test/");missing=await atlas_esi.public_snapshot("/missing/")
        self.assertTrue(stale["stale"]);self.assertEqual(stale["data"],a["data"])
        self.assertIsNone(missing["data"])

    async def test_missing_timestamp_not_invented(self):
        with patch("app.services.atlas_esi.EsiClient.get_with_headers",new=AsyncMock(return_value=([],httpx.Headers()))):
            self.assertIsNone((await atlas_esi.public_snapshot("/no-header/"))["observed_at"])


class MigrationTests(unittest.TestCase):
    def test_agent_migration_round_trip_matches_model(self):
        import importlib.util
        from pathlib import Path
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from sqlalchemy import inspect
        path=Path(__file__).parents[1]/"alembic/versions/0081_mission_atlas.py"
        spec=importlib.util.spec_from_file_location("atlas_migration",path)
        migration=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine=create_engine("sqlite://")
        with engine.begin() as connection:
            with patch.object(migration,"op",Operations(MigrationContext.configure(connection))):
                migration.upgrade()
                schema=inspect(connection)
                self.assertEqual({c["name"] for c in schema.get_columns("eve_agents")},
                                 set(EveAgent.__table__.columns.keys()))
                self.assertEqual({i["name"] for i in schema.get_indexes("eve_agents")},
                                 {i.name for i in EveAgent.__table__.indexes})
                migration.downgrade()
                self.assertNotIn("eve_agents",inspect(connection).get_table_names())
        engine.dispose()
