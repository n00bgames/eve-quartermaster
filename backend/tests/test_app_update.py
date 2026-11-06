from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import app_update
from app.api.auth import get_current_user
from app.models import User


def test_only_host_can_queue_and_read_updates(tmp_path, monkeypatch):
    for name in ("status", "inbox"):
        (tmp_path / name).mkdir()
    (tmp_path / "status/heartbeat").touch()
    monkeypatch.setenv("EQM_UPDATE_BRIDGE", str(tmp_path))

    app = FastAPI()
    app.include_router(app_update.router)
    user = User(role="admin")
    app.dependency_overrides[get_current_user] = lambda: user
    job = {"job_id": "a" * 32}
    headers = {"X-EQM-Update": "1"}
    with TestClient(app) as client:
        assert client.get("/app-update/status").status_code == 403
        assert client.post("/app-update/jobs", json=job, headers=headers).status_code == 403
        user.role = "host"
        assert client.post("/app-update/jobs", json=job).status_code == 403
        assert client.post("/app-update/jobs", json={**job, "script": "evil"}, headers=headers).status_code == 422

        with ThreadPoolExecutor(max_workers=2) as pool:
            def submit(character):
                return client.post("/app-update/jobs", json={"job_id": character * 32}, headers=headers)

            results = list(pool.map(submit, ("a", "b")))
        assert sorted(result.status_code for result in results) == [202, 409]
        job_id = next(result.json()["id"] for result in results if result.status_code == 202)
        assert (tmp_path / "inbox/request").read_text() == job_id
        response = client.get("/app-update/status")
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.json()["job"]["id"] == job_id
        assert response.json()["job"]["phase"] == "queued"
        assert client.post("/app-update/jobs", json={"job_id": job_id}, headers=headers).status_code == 202


def test_disabled_and_offline_helpers_do_not_accept_jobs(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(app_update.router)
    app.dependency_overrides[get_current_user] = lambda: User(role="host")
    monkeypatch.delenv("EQM_UPDATE_BRIDGE", raising=False)
    with TestClient(app) as client:
        assert client.get("/app-update/status").json() == {"enabled": False, "online": False, "job": None}
        monkeypatch.setenv("EQM_UPDATE_BRIDGE", str(tmp_path))
        assert client.get("/app-update/status").json() == {"enabled": True, "online": False, "job": None}
        assert client.post(
            "/app-update/jobs", json={"job_id": "a" * 32}, headers={"X-EQM-Update": "1"},
        ).status_code == 503
        assert not (tmp_path / "inbox/request").exists()
