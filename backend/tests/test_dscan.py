from datetime import timedelta
from io import BytesIO
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy import select
from app.api import dscan
from app.models import EveType, EveGroup, EveCategory, UserSectionPermission
from app.models.local_scan import LocalScanReport
from app.services import dscan as service, local_scan
from tests.test_local_scan import env, create as create_local


@pytest.fixture
def scan_env(env):
    env.app.include_router(dscan.router, prefix="/api")
    ship = EveCategory(category_id=6, name="Ship")
    deployable = EveCategory(category_id=22, name="Deployable")
    cruiser = EveGroup(group_id=26, name="Cruiser", category=ship)
    capsule = EveGroup(group_id=29, name="Capsule", category=ship)
    recon = EveGroup(group_id=833, name="Combat Recon Ship", category=ship)
    mtu = EveGroup(group_id=1250, name="Mobile Tractor Unit", category=deployable)
    env.db.add_all([ship, deployable, cruiser, capsule, recon, mtu])
    env.db.add_all([EveType(type_id=17715, name="Gila", group=cruiser, mass=10000000),
                    EveType(type_id=670, name="Capsule", group=capsule, mass=32000),
                    EveType(type_id=33475, name="Mobile Tractor Unit", group=mtu),
                    *[EveType(type_id=11950+i, name=name, group=recon, mass=11000000) for i, name in enumerate(service.RECONS)]])
    env.db.commit()
    return env


CLIPBOARD = "17715\tRed Corp\tGila\t1 km\n17715\tRed Corp\tGila\t1 km\n670\tPod\tCapsule\t-\n33475\tLoot\tMobile Tractor Unit\t28 km"


def generate(env, **extra):
    response = env.client.post("/api/d-scans", json={"text": CLIPBOARD, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_parser_formats_headers_duplicates_and_rejected_lines():
    objects, ignored = service.parse("\ufeffID\tName\tType\tDistance\r\n"+CLIPBOARD+"\nOther name\tGila\t0.4 AU\nthis is not a scan")
    assert len(objects) == 5 and len(ignored) == 1
    assert objects[0] == objects[1]  # Equal clipboard rows are two objects, not deduplicated pilots.
    assert objects[-1]["type_id"] is None
    assert "this is not a scan" not in str(ignored)
    with pytest.raises(ValueError): service.parse("Alpha One\nBeta Two")
    with pytest.raises(ValueError): service.parse("\n".join(["Pod\tCapsule\t-"]*5001))


def test_summary_counts_types_mass_and_manual_additions(scan_env):
    report = generate(scan_env, manual_recons={"Huginn": 2}, system_id=30000142)
    assert report["object_count"] == 4 and report["observed_ship_count"] == 3
    assert report["manual_ship_count"] == 2 and report["ship_count"] == 5
    assert report["ship_mass_kg"] == 42032000 and report["mass_complete"]
    assert report["classes"][0] == {"name": "Combat Recon Ship", "count": 2}
    assert next(r for r in report["rows"] if r["type_name"] == "Huginn")["observed"] == 0
    assert report["share_url"].endswith("/#d-scan/"+report["token"])
    assert report["system"] == {"id": 30000142, "name": "Jita"}
    assert not any("owner" in row or "highlighted" in row for row in report["rows"])


def test_names_resolve_without_ids_and_ids_take_precedence(scan_env):
    report = generate(scan_env, text="A\tgIlA\t-\n670\tB\tGila\t1 km\n999999\tC\tGila\t2 km")
    assert report["observed_ship_count"] == 2 and report["unresolved_count"] == 1
    assert {r["type_name"] for r in report["rows"]} == {"Gila", "Capsule"}
    assert not report["mass_complete"]
    assert any("disagree" in w for w in report["warnings"])


def test_missing_mass_is_partial_and_manual_counts_validated(scan_env):
    scan_env.db.get(EveType, 17715).mass = None; scan_env.db.commit()
    report = generate(scan_env)
    assert not report["mass_complete"] and report["mass_unknown_count"] == 2
    for invalid in ({"Rook": -1}, {"Rook": True}, {"Rook": 1.5}, {"Gila": 3}, {"Curse": 1001}):
        assert scan_env.client.post("/api/d-scans", json={"text": CLIPBOARD, "manual_recons": invalid}).status_code == 422


def test_shared_highlights_mark_local_not_ship_names(scan_env):
    scan_env.client.post("/api/d-scans/highlights", json={"kind": "corporation", "name": "Red Corp"})
    assert len(scan_env.client.get("/api/local-scans/highlights").json()) == 1
    report = generate(scan_env, local_text="Alpha One\nBeta Two\nGamma Three\nUnknown Pilot")
    assert report["local_scan"]["highlighted_count"] == 2
    assert report["local_scan"]["unresolved"] == ["Unknown Pilot"]
    assert all("highlighted" not in obj for obj in report["objects"])
    assert next(r for r in report["rows"] if r["type_name"] == "Gila")["count"] == 2


@pytest.mark.parametrize("mode", ["tokens", "range", "all"])
def test_management_scopes_and_kinds_are_isolated(scan_env, mode):
    local = create_local(scan_env)
    mine = generate(scan_env)
    scan_env.current[0] = scan_env.users["other"]
    other = generate(scan_env, corporation_id=102)
    scan_env.current[0] = scan_env.users["member"]
    assert scan_env.client.get("/api/d-scans/reports").json()["total"] == 1
    assert scan_env.client.get("/api/local-scans/reports").json()["total"] == 1
    spec = {"tokens": [mine["token"], other["token"], local["token"]]} if mode == "tokens" else {"all_in_scope": True} if mode == "all" else {
        "from_at": (local_scan.now()-timedelta(days=1)).isoformat(), "to_at": (local_scan.now()+timedelta(days=1)).isoformat()}
    assert scan_env.client.post("/api/d-scans/reports/delete", json=spec).json()["deleted"] == 1
    assert scan_env.client.get("/api/d-scans/public/"+other["token"]).status_code == 200
    assert scan_env.client.get("/api/local-scans/public/"+local["token"]).status_code == 200
    assert scan_env.client.get("/api/local-scans/public/"+other["token"]).status_code == 404
    assert scan_env.client.get("/api/d-scans/public/"+local["token"]).status_code == 404


def test_director_corporation_scope_and_admin(scan_env):
    report = generate(scan_env, corporation_id=101)
    personal = generate(scan_env)
    scan_env.current[0] = scan_env.users["director"]
    assert scan_env.client.post("/api/d-scans/reports/delete", json={"all_in_scope": True}).json()["deleted"] == 1
    assert scan_env.client.get("/api/d-scans/public/"+personal["token"]).status_code == 200
    scan_env.current[0] = scan_env.users["admin"]
    assert scan_env.client.post("/api/d-scans/reports/delete", json={"all_in_scope": True}).json()["deleted"] == 1


def test_public_expiry_pdf_and_cleanup(scan_env):
    report = generate(scan_env, retention="30m")
    scan_env.current[0] = None
    response = scan_env.client.get("/api/d-scans/public/"+report["token"])
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    row = scan_env.db.get(LocalScanReport, report["token"])
    row.expires_at = local_scan.now()-timedelta(seconds=1); scan_env.db.commit()
    assert scan_env.client.get("/api/d-scans/public/"+report["token"]).status_code == 404
    assert scan_env.client.get("/api/d-scans/public/"+report["token"]+"/pdf").status_code == 404
    assert local_scan.purge_expired(scan_env.db) == 1


def test_permissions_independent_and_corporation_checked(scan_env):
    scan_env.current[0] = scan_env.users["intel_analyst"]
    assert scan_env.client.get("/api/d-scans/context").status_code == 200
    assert scan_env.client.post("/api/d-scans", json={"text": CLIPBOARD, "corporation_id": 102}).status_code == 403
    scan_env.db.add(UserSectionPermission(user_id=scan_env.current[0].id, section="local_scan", can_view=False)); scan_env.db.commit()
    assert scan_env.client.get("/api/d-scans/highlights").status_code == 200
    scan_env.db.add(UserSectionPermission(user_id=scan_env.current[0].id, section="dscan", can_view=False)); scan_env.db.commit()
    assert scan_env.client.post("/api/d-scans", json={"text": CLIPBOARD}).status_code == 403


def test_pdf_attribution_and_complete_summary(scan_env):
    from pypdf import PdfReader
    report = generate(scan_env, local_text="Alpha One\nBeta Two", manual_recons={"Huginn": 2}, system_id=30000142)
    with patch("app.services.dscan_pdf.report_images", new=AsyncMock(return_value={})):
        result = scan_env.client.get("/api/d-scans/public/"+report["token"]+"/pdf")
    assert result.status_code == 200 and result.content.startswith(b"%PDF")
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(result.content)).pages)
    for expected in ("Generated by EVE Quartermaster v2.0.0 by Member", "System: Jita", "Huginn", "Mobile Tractor Unit", "Alpha One", "Manual", "42,032.000"):
        assert expected in text


def test_migration_preserves_existing_local_reports():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text, inspect
    engine = create_engine("sqlite://")
    root = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    def module(file):
        spec = importlib.util.spec_from_file_location("test_migration", root / file)
        loaded = importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded)
        return loaded
    initial = module("0090_local_scan_reports.py")
    migration = module("0092_dscan_reports.py")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        operations = Operations(MigrationContext.configure(connection))
        with patch.object(initial, "op", operations): initial.upgrade()
        connection.execute(text("INSERT INTO local_scan_reports (token, account_name, application_version, created_at, retention, payload) VALUES ('old', 'Example', '2.0.0', CURRENT_TIMESTAMP, 'permanent', '{}')"))
        with patch.object(migration, "op", operations): migration.upgrade()
        assert connection.execute(text("SELECT report_kind FROM local_scan_reports WHERE token='old'")).scalar() == "local"
        connection.execute(text("INSERT INTO local_scan_reports (token, account_name, application_version, created_at, retention, payload, report_kind) VALUES ('scan', 'Example', '2.0.0', CURRENT_TIMESTAMP, 'permanent', '{}', 'dscan')"))
        with patch.object(migration, "op", operations): migration.downgrade()
        assert "report_kind" not in {c["name"] for c in inspect(connection).get_columns("local_scan_reports")}
        assert connection.execute(text("SELECT token FROM local_scan_reports")).scalars().all() == ["old"]
    engine.dispose()


def test_pdf_expiry_rechecked_after_rendering(scan_env):
    report = generate(scan_env)
    def render(snapshot, images):
        row = scan_env.db.get(LocalScanReport, report["token"])
        row.expires_at = local_scan.now()-timedelta(seconds=1); scan_env.db.commit()
        return b"%PDF-test"
    with patch("app.services.dscan_pdf.report_images", new=AsyncMock(return_value={})), patch("app.services.dscan_pdf.render_pdf", side_effect=render):
        assert scan_env.client.get("/api/d-scans/public/"+report["token"]+"/pdf").status_code == 404


def test_update_is_a_new_snapshot_and_manual_zero_resets(scan_env):
    original = generate(scan_env, manual_recons={"Huginn": 2})
    updated = generate(scan_env, manual_recons={"Huginn": 0})
    assert original["token"] != updated["token"]
    assert updated["ship_count"] == 3
    assert scan_env.client.get("/api/d-scans/public/"+original["token"]).json()["ship_count"] == 5


def test_partial_sde_classification_remains_unknown(scan_env):
    scan_env.db.get(EveType,17715).group=None
    scan_env.db.commit()
    result=generate(scan_env)
    assert result["unresolved_count"]==2 and not result["mass_complete"]
    assert result["observed_ship_count"]==1


def test_large_snapshot_and_linked_local_pdf_preserve_totals_and_last_pilot(scan_env):
    from app.services.dscan_pdf import render_pdf
    from pypdf import PdfReader
    objects,_=service.parse("\n".join(["Gila\tGila\t-"]*5000))
    snapshot=service.summarize(scan_env.db,objects,{})
    report=generate(scan_env)
    local={"character_count":2000,"input_count":2000,"unresolved":[],"warnings":[],
           "pilots":[{"name":f"Pilot {i:04d}","corporation_id":101,"alliance_id":201,
                      "corporation_name":"Example Corporation","alliance_name":"Example Alliance",
                      "affiliation_available":True,"highlighted":True,"alliance_highlighted":True} for i in range(2000)]}
    data={**report,**snapshot,"local_scan":local,"ignored":[],"account_name":"L"*120}
    content=render_pdf(data,{})
    reader=PdfReader(BytesIO(content))
    text="\n".join(page.extract_text() for page in reader.pages)
    assert len(reader.pages)>1 and "Pilot 1999" in text and "5,000 observed ships" in text
    assert "Example Alliance" in text and "Example Corporation" in text
