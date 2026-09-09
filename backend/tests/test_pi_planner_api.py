from __future__ import annotations

import asyncio
import copy
import importlib.util
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import pi_planner as api
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, EveCharacter, PiPlanningJob, PiPlanningScenario, User
from tests.test_pi_planner import context, market, request


@pytest.fixture
def client(monkeypatch):
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine,tables=[User.__table__,PiPlanningScenario.__table__,PiPlanningJob.__table__])
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    with factory() as db:
        db.add_all([User(id=1,email="one@test.invalid",display_name="One"),User(id=2,email="two@test.invalid",display_name="Two")]);db.commit()
    state={"user":1,"visible":True,"permission":True}
    app=FastAPI();app.include_router(api.router,prefix="/api")
    def current_user():
        with factory() as db:return db.get(User,state["user"])
    def database():
        with factory() as db:yield db
    def permitted(*args):
        if not state["permission"]:raise HTTPException(403,"PI permission required")
    monkeypatch.setattr(api,"SessionLocal",factory)
    monkeypatch.setattr(api,"require_planetary_view",permitted)
    monkeypatch.setattr(api,"visible_characters",lambda *a:[EveCharacter(id=1,character_id=10001,name="Pilot")] if state["visible"] else [])
    monkeypatch.setattr(api,"build_context",lambda *a:context())
    async def prices(*args):return market()
    monkeypatch.setattr(api,"market_snapshot",prices)
    app.dependency_overrides[get_current_user]=current_user
    app.dependency_overrides[get_db]=database
    with TestClient(app) as test:
        yield test,state,factory
    engine.dispose()


ROOT="/api/planetary-industry/planner"


def completed(test,job_id):
    for _ in range(100):
        response=test.get(f"{ROOT}/jobs/{job_id}")
        assert response.status_code==200,response.text
        job=response.json()
        if job["status"] not in api.ACTIVE:return job
        time.sleep(.03)
    pytest.fail("Job did not complete")


def test_private_scenarios_version_conflicts_and_delete(client):
    test,state,_=client
    body={"request":request().model_dump()}
    first=test.post(ROOT+"/scenarios",json=body)
    assert first.status_code==201,first.text
    record=first.json()
    assert len(test.get(ROOT+"/scenarios").json())==1
    assert test.put(f"{ROOT}/scenarios/{record['id']}",json={**body,"revision":1}).status_code==200
    assert test.put(f"{ROOT}/scenarios/{record['id']}",json={**body,"revision":1}).status_code==409
    state["user"]=2
    assert test.get(ROOT+"/scenarios").json()==[]
    assert test.delete(f"{ROOT}/scenarios/{record['id']}").status_code==404
    state["user"]=1
    assert test.delete(f"{ROOT}/scenarios/{record['id']}").status_code==204
    assert test.get(ROOT+"/scenarios").json()==[]


def test_job_end_to_end_snapshot_replay_template_and_ownership(client):
    test,state,_=client
    body=request(objective="quota").model_dump()
    start=test.post(ROOT+"/jobs",json=body)
    assert start.status_code==202,start.text
    job_id=start.json()["id"]
    job=completed(test,job_id)
    assert job["status"]=="complete",job
    assert job["result"]["plans"][0]["colonies"]
    assert any(row["id"]==job_id for row in test.get(ROOT+"/jobs").json())
    exported=test.get(f"{ROOT}/jobs/{job_id}/snapshot").json()
    assert exported["snapshot"]["context"]["catalog"]["3645"]["name"]=="Water"
    generated=test.post(ROOT+"/templates/generate",json={"job_id":job_id,"plan_index":0,"colony_index":0})
    assert generated.status_code==200,generated.text
    assert generated.json()["template"]["Pln"]==2017
    replay=test.post(f"{ROOT}/jobs/{job_id}/replay").json()
    replayed=completed(test,replay["id"])
    assert replayed["result"]["replayed_snapshot"] is True
    assert replayed["result"]["plans"]==job["result"]["plans"]
    state["user"]=2
    assert test.get(ROOT+"/jobs").json()==[]
    assert test.get(f"{ROOT}/jobs/{job_id}").status_code==404
    assert test.get(f"{ROOT}/jobs/{job_id}/snapshot").status_code==404
    assert test.post(ROOT+"/templates/generate",json={"job_id":job_id,"plan_index":0,"colony_index":0}).status_code==404


def test_visibility_revocation_hides_saved_data(client):
    test,state,_=client
    saved=test.post(ROOT+"/scenarios",json={"request":request().model_dump()}).json()
    start=test.post(ROOT+"/jobs",json=request(objective="quota").model_dump()).json()
    completed(test,start["id"])
    state["visible"]=False
    assert test.get(ROOT+"/jobs").json()==[]
    assert test.get(ROOT+"/scenarios").json()==[]
    assert test.get(f"{ROOT}/jobs/{start['id']}/snapshot").status_code==403
    assert test.put(f"{ROOT}/scenarios/{saved['id']}",json={"request":request().model_dump(),"revision":1}).status_code==403


def test_section_permission_and_input_validation(client):
    test,state,_=client
    state["permission"]=False
    assert test.get(ROOT+"/context").status_code==403
    assert test.post(ROOT+"/jobs",json=request().model_dump()).status_code==403
    state["permission"]=True
    body=request().model_dump();body["pilots"][0]["character_id"]=999
    assert test.post(ROOT+"/validate",json=body).status_code==403
    body=request().model_dump();body["prices"]={"3645":999}
    assert test.post(ROOT+"/jobs",json=body).status_code==422


def test_cancel_pricing_and_recover_orphan(client,monkeypatch):
    test,_,factory=client
    async def slow_prices(*args):
        await asyncio.sleep(.1)
        return market()
    monkeypatch.setattr(api,"market_snapshot",slow_prices)
    start=test.post(ROOT+"/jobs",json=request().model_dump()).json()
    assert test.post(f"{ROOT}/jobs/{start['id']}/cancel").status_code==200
    assert completed(test,start["id"])["status"]=="cancelled"
    with factory() as db:
        db.add(PiPlanningJob(id="orphan",user_id=1,status="solving",request_json=request().model_dump(),progress_json={},cancel_requested=False,updated_at=datetime.now(timezone.utc)-timedelta(minutes=10)));db.commit()
    orphan=test.get(ROOT+"/jobs/orphan").json()
    assert orphan["status"]=="failed" and "Worker stopped" in orphan["error"]


def test_recipe_and_template_bad_json(client):
    test,_,_=client
    r=test.post(ROOT+"/recipe",json={"targets":[{"type_id":3645,"quantity":40}],"inventory":[{"type_id":2268,"quantity":3000}]})
    assert r.status_code==200 and r.json()["shopping"]["2268"]==3000
    assert test.post(ROOT+"/templates/inspect",json={"text":"{not-json}"}).status_code==422


def test_migration_roundtrip_sqlite():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    file=Path(__file__).parents[1]/"alembic/versions/0079_pi_planning.py"
    spec=importlib.util.spec_from_file_location("pi_migration",file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine("sqlite://")
    with engine.begin() as connection:
        Base.metadata.create_all(connection,tables=[User.__table__])
        module.op=Operations(MigrationContext.configure(connection))
        module.upgrade()
        assert "pi_planning_jobs" in inspect(connection).get_table_names()
        module.downgrade()
        assert "pi_planning_jobs" not in inspect(connection).get_table_names()
    engine.dispose()
