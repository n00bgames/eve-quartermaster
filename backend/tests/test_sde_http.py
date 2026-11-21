"""HTTP transport defenses and parity through the real shared importer/worker."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import yaml
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from tests.test_local_scan import env
from tests.test_sde_maintenance import app, archive, client as zip_client
from app.core.config import get_settings
from app.models import Base, EveType, EveStation, EveSystem, EveStargate, EvePlanetSchematic, SdeMaintenanceJob
from app.models.system_objects import EveSystemObject
from app.services import sde_http as http, sde_maintenance as service
from app.services.sde_importer import import_sde, SDE_FILES

FIXTURE = json.loads((Path(__file__).parent / "fixtures/http-sde-20261120.json").read_text(encoding="utf-8"))
RELEASE = FIXTURE["release"]
VERSION = "a" * 64


def manifest(release=RELEASE, build=3724492):
    return {"release": release, "buildNumber": build, "releaseDate": "2026-11-20T16:58:26Z",
            "tables": {t.name: {"version": VERSION,
                "jsonl": {"url": f"{http.ORIGIN}/tranquility/{release}/{t.name}.jsonl"}} for t in http.TABLES.values()}}


def transport(m=None, rows=None, mutate=None, calls=None):
    m = deepcopy(m if m is not None else manifest())
    rows = deepcopy(rows if rows is not None else FIXTURE["tables"])

    def handle(request):
        if calls is not None:
            calls.append(str(request.url))
        if str(request.url) == http.LATEST_URL:
            response = httpx.Response(302, headers={"Location": f"/tranquility/{m['release']}/"})
        elif request.url.path.endswith("/"):
            response = httpx.Response(200, json=m)
        else:
            name = request.url.path.rsplit("/", 1)[-1].removesuffix(".jsonl")
            data = rows.get(name, {})
            content = data if isinstance(data, bytes) else (json.dumps(data) + "\n").encode()
            response = httpx.Response(200, content=gzip.compress(content), headers={"Content-Encoding": "gzip"})
        return mutate(request, response) if mutate else response
    return httpx.MockTransport(handle)


def fetch(path, **kwargs):
    with httpx.Client(transport=transport(**kwargs)) as client:
        return http.fetch_release(path, 64 * 1024**2, lambda *a, **kw: None, lambda *a: None, client)


def test_release_gzip_named_keys_pi_rows_and_only_consumed_tables(tmp_path):
    calls = []
    details = fetch(tmp_path, calls=calls)
    assert details["release"] == RELEASE and details["build"] == "3724492"
    assert len(details["tables"]) == len(http.TABLES)
    assert sum(url == http.LATEST_URL for url in calls) == 1
    source = http.JsonlSource(tmp_path)
    assert list(source.load_yaml("types").items())[0][0] == 0
    schematic = list(source.load_yaml("planet_schematics").values())[0]
    assert schematic["types"][9838] == {"isInput": False, "quantity": 5}
    assert all("typeBonus" not in url for url in calls)
    assert all(len(t["sha256"]) == 64 for t in details["tables"].values())


def test_field_order_is_irrelevant_and_duplicate_ids_or_fields_rejected(tmp_path):
    rows = deepcopy(FIXTURE["tables"])
    rows["types"] = dict(reversed(list(rows["types"].items())))
    fetch(tmp_path / "order", rows=rows)
    for bad in [b'{"typeID":1,"typeID":2,"name":"bad","groupID":1}\n',
                b'{"typeID":1,"groupID":1,"name":"first"}\n{"typeID":1,"groupID":1,"name":"second"}\n']:
        rows["types"] = bad
        with pytest.raises(http.SdeHttpError): fetch(tmp_path / str(len(bad)), rows=rows)


@pytest.mark.parametrize("table,payload", [
    ("types", {"_key": 1, "groupID": 1, "name": "ZIP keys are not HTTP keys"}),
    ("mapPlanets", {"planetID": 1, "solarSystemID": 2, "typeID": 11, "radius": "bad", "position": {}}),
    ("typeDogma", {"typeID": 1, "dogmaAttributes": [{"attributeID": 1, "value": "bad"}], "dogmaEffects": []}),
    ("blueprints", {"blueprintTypeID": 1, "activities": []}),
    ("planetSchematics", {"schematicID": 1, "cycleTime": 1, "types": {"1": {"isInput": False}}}),
])
def test_importer_shapes_validated_before_writes(tmp_path, table, payload):
    rows = deepcopy(FIXTURE["tables"]); rows[table] = payload
    with pytest.raises(http.SdeHttpError): fetch(tmp_path, rows=rows)


@pytest.mark.parametrize("bad", ["https://evil.invalid/tranquility/", "http://sde.evetech.net/tranquility/",
                                "https://sde.evetech.net@evil.invalid/", "https://sde.evetech.net:443/tranquility/",
                                "https://sde.evetech.net/tranquility/latest/types.jsonl"])
def test_table_url_allowlist_prevents_arbitrary_requests(tmp_path, bad):
    m = manifest();m["tables"]["types"]["jsonl"]["url"] = bad
    calls = []
    with pytest.raises(http.SdeHttpError): fetch(tmp_path, m=m, calls=calls)
    assert all("evil.invalid" not in url for url in calls)
    assert not list(tmp_path.glob("*.jsonl"))


def test_expected_content_blob_redirect_and_rejection_before_request(tmp_path):
    tables = list(http.TABLES.values())
    table = tables[0]
    calls = []
    m = manifest()
    def handle(request):
        calls.append(str(request.url))
        if request.url.path == "/tranquility/latest/": return httpx.Response(200, json=m)
        if request.url.path.endswith(table.name + ".jsonl"):
            return httpx.Response(302, headers={"Location": f"/blobs/{VERSION}.jsonl"})
        if request.url.path.startswith("/blobs/"):
            return httpx.Response(200, text=json.dumps(FIXTURE["tables"][table.name]))
        name = request.url.path.rsplit("/", 1)[-1].removesuffix(".jsonl")
        return httpx.Response(200, json=FIXTURE["tables"][name])
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        http.fetch_release(tmp_path / "good", 64000000, lambda *a, **kw: None, lambda *a: None, client)
    assert http.ORIGIN + f"/blobs/{VERSION}.jsonl" in calls
    for target in ["https://evil.invalid/private", "/tranquility/20261119T000000Z/types.jsonl", "/blobs/" + "b"*64 + ".jsonl"]:
        calls.clear()
        def redirect(request, response):
            if request.url.path.endswith("types.jsonl"): return httpx.Response(302, headers={"Location": target})
            return response
        with pytest.raises(http.SdeHttpError): fetch(tmp_path / str(len(target)), mutate=redirect, calls=calls)
        assert not any(url.endswith(target) for url in calls)


def test_limits_missing_core_optional_and_expiry(tmp_path):
    m = manifest();del m["tables"]["types"]
    with pytest.raises(http.SdeHttpError, match="Missing required"): fetch(tmp_path / "missing", m=m)
    m = manifest();del m["tables"]["mapStars"]
    assert fetch(tmp_path / "optional", m=m)["missing_optional_tables"] == ["mapStars"]
    with httpx.Client(transport=transport()) as client:
        with pytest.raises(http.SdeHttpError, match="size limit"):
            http.fetch_release(tmp_path / "size", 1, lambda *a, **kw: None, lambda *a: None, client)
    with patch.object(http, "MAX_MANIFEST_BYTES", 5):
        with pytest.raises(http.SdeHttpError, match="manifest exceeds"): fetch(tmp_path / "manifest")
    with patch.object(http, "MAX_TABLE_BYTES", 5):
        with pytest.raises(http.SdeHttpError, match="table exceeds"): fetch(tmp_path / "table")
    with patch.object(http, "MAX_LINE_BYTES", 5):
        with pytest.raises(http.SdeHttpError, match="record exceeds"): fetch(tmp_path / "line")
    def expire(request, response):
        return httpx.Response(410) if request.url.path.endswith("mapPlanets.jsonl") else response
    with pytest.raises(http.SdeHttpError, match="expired"): fetch(tmp_path / "expired", mutate=expire)


def test_same_release_rows_have_yaml_import_parity_and_idempotence(tmp_path):
    http_path, yaml_path = tmp_path / "http", tmp_path / "yaml"
    fetch(http_path);yaml_path.mkdir()
    for logical, spec in http.TABLES.items():
        # Independent legacy keyed shape for the two changed PI/named-ID forms.
        row = deepcopy(FIXTURE["tables"][spec.name]);key = row.pop(spec.key)
        if logical == "planet_schematics":
            row["types"] = {r["typeID"]: {k: v for k, v in r.items() if k != "typeID"} for r in row["types"]}
        (yaml_path / SDE_FILES[logical][0]).write_text(yaml.safe_dump({key: row}), encoding="utf-8")
    def run(path, fmt):
        engine = create_engine("sqlite://");Base.metadata.create_all(engine)
        with Session(engine) as db:
            # Cached star coordinates must survive either adapter.
            db.add(EveSystem(system_id=30000001, name="Before"));db.commit()
            db.add(EveSystemObject(object_id=40000001, system_id=30000001, kind="star", name="Before", x=1, y=2, z=3, source="esi"));db.commit()
            first = import_sde(str(path), db, source_format=fmt)
            second = import_sde(str(path), db, source_format=fmt)
            assert first == second
            snapshot = {}
            for table in Base.metadata.tables.values():
                rows = [dict(row) for row in db.execute(table.select()).mappings()]
                if rows: snapshot[table.name] = rows
            planet = db.get(EveSystemObject, 40000002)
            assert planet.type_id == 11 and planet.radius == 5060000
            star = db.get(EveSystemObject, 40000001)
            assert (star.x, star.y, star.z, star.source) == (1, 2, 3, "esi")
            assert db.get(EveType, 0).name == "#System"
            assert db.get(EveStargate, 50000001).destination_system_id == 30000778
            assert db.get(EvePlanetSchematic, 65).output_type_id == 9838
            assert db.get(EveStation, 60000004).owner_name is not None
        engine.dispose()
        first.pop("source_path")
        # timestamps/serial identifiers differ, compare meaningful imported columns.
        for rows in snapshot.values():
            for row in rows:
                for key in list(row):
                    if key.endswith("_at") or key == "id": del row[key]
        return first, snapshot
    assert run(http_path, "http_jsonl") == run(yaml_path, "yaml")


def queue(app):
    response = app.client.post("/api/sde/http-import", json={})
    assert response.status_code == 202, response.text
    return response.json()["id"]


def test_http_permissions_inputs_and_shared_lock(app):
    for role in ["member", "director", "quartermaster", "intel_analyst", "applicant"]:
        app.current[0] = app.users[role]
        assert app.client.post("/api/sde/http-import", json={}).status_code == 403
    app.current[0] = None
    assert app.client.post("/api/sde/http-import", json={}).status_code == 401
    app.current[0] = app.users["host"]
    for payload in [{"url": "https://evil.invalid"}, {"release": RELEASE}, {"source_path": "/tmp"}, {"sections": ["agents"]}]:
        assert app.client.post("/api/sde/http-import", json=payload).status_code == 422
    queue(app)
    assert app.client.post("/api/sde/http-import", json={}).status_code == 409
    assert app.client.post("/api/sde/download", json={}).status_code == 409
    assert app.client.post("/api/sde/import", json={}).status_code == 409


def test_worker_success_reload_same_build_new_release_failure_retry(app):
    real_client = httpx.Client
    def run(job, **kwargs):
        with patch.object(http.httpx, "Client", return_value=real_client(transport=transport(**kwargs))):
            service.run_job(job)
    job = queue(app); run(job)
    state = app.client.get("/api/sde/import-status").json()
    assert state["status"] == "success" and state["last_successful_http_import"]["release"] == RELEASE
    assert state["stats"]["celestial_planets"] == 1 and state["source"] == "ccp_http"
    assert list(Path(get_settings().sde_download_path).iterdir()) == []
    newer = "20261121T010203Z"
    job = queue(app);run(job, m=manifest(newer))
    assert app.client.get("/api/sde/import-status").json()["last_successful_http_import"]["release"] == newer
    def fail(request, response):
        return httpx.Response(503) if request.url.path.endswith("types.jsonl") else response
    job = queue(app)
    with patch.object(service, "import_sde") as importer:
        with pytest.raises(http.SdeHttpError, match="types: HTTP transfer failed"): run(job, mutate=fail)
        importer.assert_not_called()
    state = app.client.get("/api/sde/import-status").json()
    assert state["status"] == "failed" and state["failure_stage"]
    assert state["last_successful_http_import"]["release"] == newer
    assert not list(Path(get_settings().sde_download_path).iterdir())
    job = queue(app);run(job)
    assert app.client.get("/api/sde/import-status").json()["last_successful_http_import"]["release"] == RELEASE


def test_import_failure_keeps_last_success_and_duplicate_delivery_noop(app):
    real_client = httpx.Client
    job = queue(app)
    with patch.object(http.httpx, "Client", return_value=real_client(transport=transport())), patch.object(service, "import_sde", side_effect=RuntimeError("fixture import failure")) as importer:
        with pytest.raises(RuntimeError): service.run_job(job)
        service.run_job(job)
        assert importer.call_count == 1
    state = app.client.get("/api/sde/import-status").json()
    assert state["last_successful_http_import"] is None and state["failure_stage"] == "starting HTTP import"
    assert not list(Path(get_settings().sde_download_path).iterdir())


def test_http_then_zip_job_preserves_http_success_receipt(app):
    real_client = httpx.Client
    job = queue(app)
    with patch.object(http.httpx, "Client", return_value=real_client(transport=transport())): service.run_job(job)
    job = app.client.post("/api/sde/download", json={}).json()["id"]
    mock = zip_client()
    with patch.object(service.httpx, "Client", return_value=mock): service.run_job(job)
    state = app.client.get("/api/sde/import-status").json()
    assert state["source"] == "yaml" and state["status"] == "success"
    assert state["last_successful_http_import"]["release"] == RELEASE
