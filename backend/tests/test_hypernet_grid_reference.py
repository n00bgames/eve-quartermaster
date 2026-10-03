import asyncio
import base64
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from PIL import Image, PngImagePlugin
from sqlalchemy import create_engine, inspect, text
from starlette.requests import Request
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from app.api import hypernet
from app.schemas.hypernet import HyperNetNodeMapUpdate, HyperNetReconcileRequest
from app.services.hypernet_grid_reference import MAX_BYTES, normalize_grid_reference
from tests.test_hypernet_market_sale import fixture


def png():
    out = BytesIO()
    Image.new("RGB", (320, 180), (15, 37, 59)).save(out, "PNG")
    return out.getvalue()


def request(data, content_type="image/png"):
    sent = False
    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": data, "more_body": False}
    return Request({"type": "http", "headers": [(b"content-type", content_type.encode())]}, receive)


def save(f, data=None, user=None, mime="image/png"):
    return asyncio.run(hypernet.save_hypernet_grid_reference(f.offer.id, request(png() if data is None else data, mime), user or f.user, f.db))


def winner(f, position=3):
    return hypernet.update_hypernet_node_map(f.offer.id, HyperNetNodeMapUpdate(columns=4, seeded_positions=[1, 2], winning_position=position), f.user, f.db)


def complete(f):
    return hypernet.reconcile_hypernet_offer(f.offer.id, HyperNetReconcileRequest(status="completed", winner="external", reconciled_at=f.now), f.user, f.db)


def test_saved_crop_private_persisted_lossless_and_not_in_offer_payload(fixture):
    f = fixture
    result = save(f)
    assert result["grid_reference"]["width"] == 320
    assert "grid_reference_data" not in result and "data_url" not in result
    f.db.expire_all()
    hypernet.owned_offer(f.db, f.offer.id, f.user)
    assert "grid_reference_data" in inspect(f.offer).unloaded
    response = hypernet.get_hypernet_grid_reference(f.offer.id, f.user, f.db)
    assert response.headers["cache-control"] == "private, no-store"
    restored = base64.b64decode(json.loads(response.body)["data_url"].split(",")[1])
    with Image.open(BytesIO(restored)) as image:
        assert image.size == (320, 180)
        assert image.tobytes() == Image.open(BytesIO(png())).tobytes()


@pytest.mark.parametrize("first", ["winner", "complete"])
def test_cleanup_requires_both_saved_winner_and_completed_in_either_order(fixture, first):
    f = fixture; f.offer.status = "active"; f.db.commit()
    save(f)
    (winner if first == "winner" else complete)(f)
    assert f.offer.grid_reference is not None
    (complete if first == "winner" else winner)(f)
    f.db.expire_all()
    assert f.offer.grid_reference is None and f.offer.grid_reference_data is None
    with pytest.raises(HTTPException) as exc:
        save(f)
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        hypernet.get_hypernet_grid_reference(f.offer.id, f.user, f.db)
    assert exc.value.status_code == 404


def test_replace_remove_expired_and_failed_mutations_preserve_reference(fixture):
    f = fixture
    old = save(f)["grid_reference"]["version"]
    assert save(f)["grid_reference"]["version"] != old
    winner(f)  # Expiration does not delete the reference.
    assert f.offer.grid_reference
    for bad in [b"<svg></svg>", b"\x89PNG\r\n\x1a\ntruncated", b"x" * (MAX_BYTES + 1)]:
        with pytest.raises(HTTPException):
            save(f, bad)
        assert f.offer.grid_reference
    with pytest.raises(HTTPException):
        winner(f, 17)
    assert f.offer.grid_reference
    f.offer.status = "active"; f.db.commit()
    with pytest.raises(HTTPException):
        hypernet.reconcile_hypernet_offer(f.offer.id, HyperNetReconcileRequest(status="completed", winner="external", reconciled_at=f.now, seller_owned_nodes=17), f.user, f.db)
    assert f.offer.grid_reference
    removed = hypernet.remove_hypernet_grid_reference(f.offer.id, f.user, f.db)
    assert removed["grid_reference"] is None and f.offer.grid_reference_data is None


def test_owner_isolation_and_bad_content_type(fixture):
    f = fixture; save(f)
    other = SimpleNamespace(id=2)
    for action in [lambda: save(f, user=other), lambda: hypernet.get_hypernet_grid_reference(f.offer.id, other, f.db), lambda: hypernet.remove_hypernet_grid_reference(f.offer.id, other, f.db)]:
        with pytest.raises(HTTPException) as exc:
            action()
        assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        save(f, mime="image/svg+xml")
    assert exc.value.status_code == 415


def test_dimension_limit(monkeypatch):
    monkeypatch.setattr("app.services.hypernet_grid_reference.MAX_PIXELS", 100)
    with pytest.raises(HTTPException) as exc:
        normalize_grid_reference(png())
    assert exc.value.status_code == 400


def test_metadata_removed_without_changing_pixels():
    source = Image.new("RGBA", (5, 7), (20, 40, 60, 80))
    info = PngImagePlugin.PngInfo(); info.add_text("private", "Do not retain full screenshot metadata")
    out = BytesIO(); source.save(out, "PNG", pnginfo=info)
    data, _ = normalize_grid_reference(out.getvalue())
    with Image.open(BytesIO(data)) as restored:
        assert not restored.info
        assert restored.tobytes() == source.tobytes()


def test_http_upload_read_delete_and_permission_gate(fixture):
    f = fixture
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # Copy the fixture's small schema into a database usable by the ASGI worker threads.
    from app.models import Base
    tables = [Base.metadata.tables[name] for name in inspect(f.db.bind).get_table_names()]
    Base.metadata.create_all(engine, tables=tables)
    db = Session(engine, expire_on_commit=False)
    db.merge(f.offer); db.commit()
    app = FastAPI(); app.include_router(hypernet.router)
    app.dependency_overrides[hypernet.get_db] = lambda: db
    app.dependency_overrides[hypernet.get_current_user] = lambda: f.user
    try:
        with patch.object(hypernet, "can_view_section", return_value=True) as access, TestClient(app) as client:
            path = f"/hypernet/offers/{f.offer.id}/grid-reference"
            assert client.put(path, content=png(), headers={"Content-Type": "image/png"}).status_code == 200
            assert client.get(path).json()["data_url"].startswith("data:image/png;base64,")
            access.return_value = False
            assert client.get(path).status_code == 403
            assert client.put(path, content=png(), headers={"Content-Type": "image/png"}).status_code == 403
            access.return_value = True
            assert client.delete(path).json()["grid_reference"] is None
            assert client.get(path).status_code == 404
    finally:
        db.close(); engine.dispose()


def test_migration_round_trip():
    path = Path(__file__).parents[1] / "alembic/versions/0085_hypernet_grid_reference.py"
    spec = importlib.util.spec_from_file_location("grid_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE hypernet_offers (id INTEGER PRIMARY KEY)"))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {c["name"] for c in inspect(connection).get_columns("hypernet_offers")} == {"id", "grid_reference", "grid_reference_data"}
        migration.downgrade()
        assert [c["name"] for c in inspect(connection).get_columns("hypernet_offers")] == ["id"]
    engine.dispose()

