"""Full-scope Journey rankings, honest counting and private account boundaries."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import journey as api
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, EveCharacter, EveSystem, EveType, Killmail, KillmailAttacker, User, UserSectionPermission
from app.models.journey import JourneyShipSegment, JourneyTracker, JourneyVisit
from app.services import journey

AT = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
BASE = "/api/journey/analytics"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(journey, "now", lambda: AT + timedelta(days=1))
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine); db = Session(engine, expire_on_commit=False)
    users = [User(email=f"journey-stats-{i}@invalid.test", display_name=role, role=role) for i, role in enumerate(("officer", "admin"))]
    db.add_all(users); db.flush()
    chars = [EveCharacter(character_id=900001+i, name=name, owner_user_id=users[0 if i<2 else 1].id)
             for i, name in enumerate(("Demo Alpha", "Demo Bravo", "Other Pilot"))]
    db.add_all(chars); db.flush()
    trackers = [JourneyTracker(user_id=chars[i].owner_user_id, character_id=chars[i].id) for i in range(3)]
    db.add_all(trackers)
    db.add_all([EveSystem(system_id=10+i, name=name) for i, name in enumerate(("Demo A", "Demo B", "Demo C"))])
    db.add_all([EveType(type_id=111, name="Demo Scout"), EveType(type_id=222, name="Demo Cruiser")]); db.commit()
    actor = [users[0]]
    def identity():
        if actor[0] is None:raise HTTPException(401, "Sign in required")
        return actor[0]
    def database():
        try:yield db
        finally:db.rollback()
    app = FastAPI(); app.include_router(api.router, prefix="/api")
    app.dependency_overrides[get_current_user] = identity; app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield SimpleNamespace(db=db, client=client, users=users, chars=chars, trackers=trackers, actor=actor, engine=engine)
    db.close(); engine.dispose()


def visit(e, pilot, system, minute, length=10, gap=True, hull=None):
    row = JourneyVisit(tracker_id=e.trackers[pilot].id, system_id=system, first_seen_at=AT+timedelta(minutes=minute),
        last_seen_at=AT+timedelta(minutes=minute+length), gap_before=gap, samples=2)
    e.db.add(row); e.db.flush()
    if hull is not None:
        e.db.add(JourneyShipSegment(visit_id=row.id, ship_type_id=hull, first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at, samples=2, gap_before=True))
    return row


def mail(e, kid, victim=None, lost_type=111, system=10, attackers=(), minute=15):
    e.db.add(Killmail(killmail_id=kid, killmail_hash="synthetic", killmail_time=AT+timedelta(minutes=minute),
        solar_system_id=system, victim_character_id=victim, victim_ship_type_id=lost_type, canonical_esi_payload={}))
    e.db.flush()
    for index, (pilot, hull) in enumerate(attackers):
        e.db.add(KillmailAttacker(killmail_id=kid, attacker_index=index, character_id=e.chars[pilot].character_id, ship_type_id=hull))


def seed(e):
    visit(e, 0, 10, 0, hull=111)
    visit(e, 0, 11, 11, length=9, gap=False, hull=222)
    visit(e, 0, 11, 60, hull=222)  # resumed same system is a visit, never a jump
    visit(e, 0, 12, 71, length=9, gap=False, hull=111)
    visit(e, 1, 10, 0, length=60, hull=111)
    visit(e, 1, 12, 61, length=29, gap=False, hull=222)
    visit(e, 2, 9999, 0, length=100, hull=9999)
    mail(e, 100, victim=9999000, system=10, attackers=((0,111),(0,111),(1,111)))
    mail(e, 101, victim=9999000, system=11, attackers=((0,222),))
    mail(e, 102, victim=e.chars[1].character_id, lost_type=222, system=12, attackers=((0,111),))
    mail(e, 103, victim=e.chars[0].character_id, lost_type=111, system=12, attackers=((2,222),))
    mail(e, 104, victim=9999000, system=9999, attackers=((2,9999),))
    e.db.commit()


def stats(e, query="period=all"):
    result=e.client.get(BASE+"?"+query)
    assert result.status_code==200, result.text
    assert result.headers["cache-control"]=="private, no-store"
    return result.json()


def test_full_account_rankings_deduplicate_shared_and_duplicate_attackers(env):
    e=env; seed(e); data=stats(e)
    assert data["scope"]["name"]=="All my pilots"
    assert data["summary"]==dict(pilots=2, visits=6, systems=3, jumps=3, observed_seconds=7620,
        visits_without_hull=0, kills=3, losses=2)
    assert data["systems"]["rows"]==[dict(system_id=10,name="Demo A",visits=2),dict(system_id=11,name="Demo B",visits=2),dict(system_id=12,name="Demo C",visits=2)]
    assert data["ships"]["rows"][0]==dict(ship_type_id=111,visits=3,segments=3,observed_seconds=4740,name="Demo Scout",kills=2)
    assert [(r["name"],r["jumps"],r["kills"],r["losses"]) for r in data["pilots"]["rows"]]==[("Demo Alpha",2,3,1),("Demo Bravo",1,1,1)]
    assert sum(r["kills"] for r in data["pilots"]["rows"])==4  # one shared event
    assert sum(r["kills"] for r in data["kill_systems"]["rows"])==3
    assert [(r["ship_type_id"],r["losses"]) for r in data["lost_ships"]["rows"]]==[(222,1),(111,1)]
    assert data["combat_ships"]["rows"]==data["ships"]["rows"]


def test_selected_pilot_and_date_clipping_preserve_predecessor_jump(env):
    e=env; seed(e)
    data=stats(e, f"character_id={e.chars[0].id}&from_at=2026-11-08T12:11:00Z&to_at=2026-11-08T12:12:00Z")
    assert data["summary"]["pilots"]==1 and data["summary"]["visits"]==1 and data["summary"]["jumps"]==1
    assert data["ships"]["rows"][0]["observed_seconds"]==60
    assert data["summary"]["kills"]==data["summary"]["losses"]==0
    assert data["scope"]["name"]=="Demo Alpha"
    end=stats(e,f"character_id={e.chars[0].id}&from_at=2026-11-08T12:10:00Z&to_at=2026-11-08T12:11:00Z")
    assert end["summary"]["jumps"]==0 and end["summary"]["visits"]==1


def test_unknown_and_conflicting_combat_hulls_never_backfill_flight_history(env):
    e=env; seed(e)
    mail(e, 110, victim=999, attackers=((0,111),(0,222)))
    mail(e, 111, victim=999, attackers=((1,None),))
    mail(e, 112, victim=e.chars[0].character_id, lost_type=None)
    visit(e,0,40444,150,hull=44444)
    visit(e,0,10,200,hull=None)
    e.db.commit(); data=stats(e)
    assert data["summary"]["kills"]==5 and data["summary"]["visits_without_hull"]==1
    assert len(data["combat_ships"]["rows"])==2
    assert next(r for r in data["ships"]["rows"] if r["ship_type_id"]==111)["kills"]==2
    assert any(r["name"]=="Unknown hull" and r["ship_type_id"] is None for r in data["lost_ships"]["rows"])
    assert any(r["name"]=="Type 44444" for r in data["ships"]["rows"])
    assert any(r["name"]=="System 40444" for r in data["systems"]["rows"])
    assert data["summary"]["observed_seconds"]==8220  # only the actual extra recorded hull span


def test_privacy_including_other_admin_transfers_and_misowned_trackers(env):
    e=env; seed(e); owner=e.users[0]
    e.actor[0]=e.users[1]
    assert e.client.get(BASE+f"?character_id={e.chars[0].id}").status_code==404
    assert stats(e)["summary"]["visits"]==1
    e.actor[0]=owner
    e.db.add(JourneyTracker(user_id=e.users[1].id,character_id=e.chars[0].id)); e.db.commit()
    assert stats(e)["summary"]["visits"]==6
    e.chars[0].owner_user_id=e.users[1].id; e.db.commit()
    data=stats(e)
    assert data["summary"]["pilots"]==1 and data["summary"]["visits"]==2
    assert data["summary"]["kills"]==1 and data["summary"]["losses"]==1
    assert e.client.get(BASE+f"?character_id={e.chars[0].id}").status_code==404


def test_navigation_auth_and_revoked_combat_permissions(env):
    e=env; seed(e)
    e.actor[0]=None
    assert e.client.get(BASE).status_code==401
    e.actor[0]=e.users[0]
    e.db.add(UserSectionPermission(user_id=e.users[0].id,section="navigation",can_view=False)); e.db.commit()
    assert e.client.get(BASE).status_code==403
    e.db.query(UserSectionPermission).delete()
    for section in ("killboard","battle_reports","intel_reports"):
        e.db.add(UserSectionPermission(user_id=e.users[0].id,section=section,can_view=False))
    e.db.commit()
    def no_killmail_queries(connection,cursor,statement,parameters,context,executemany):
        assert "killmail" not in statement.lower(), statement
    event.listen(e.engine,"before_cursor_execute",no_killmail_queries)
    try:data=stats(e)
    finally:event.remove(e.engine,"before_cursor_execute",no_killmail_queries)
    assert not data["combat_available"] and data["summary"]["kills"] is None and data["summary"]["losses"] is None
    assert data["kill_systems"]["rows"]==data["combat_ships"]["rows"]==data["lost_ships"]["rows"]==[]
    assert all(r["kills"] is None for r in data["ships"]["rows"])
    assert data["summary"]["visits"]==6


@pytest.mark.parametrize("query", ["limit=0","limit=51","period=invalid","ship_order=invalid",
    "from_at=2026-11-09T00:00:00Z&to_at=2026-11-08T00:00:00Z",
    "from_at=2005-01-01T00:00:00Z&to_at=2026-11-09T00:00:00Z"])
def test_invalid_parameters_rejected(env,query):
    assert env.client.get(BASE+"?"+query).status_code==422


def test_no_recording_does_not_enroll_or_guess_ships_from_killmails(env):
    e=env; mail(e,100,victim=e.chars[0].character_id,lost_type=111);e.db.commit()
    data=stats(e)
    assert data["summary"]["visits"]==0 and data["summary"]["losses"]==1
    assert data["ships"]["rows"]==[] and data["combat_ships"]["rows"]==[]
    assert all(r["jumps"]==0 for r in data["pilots"]["rows"])
    assert all(not t.enabled and not t.track_ship for t in e.trackers)


def test_top_limit_does_not_trim_totals_and_ship_rank_order_is_explicit(env):
    e=env
    visit(e,0,10,0,length=60,hull=111)
    visit(e,0,11,61,length=1,gap=False,hull=222)
    visit(e,0,12,63,length=1,gap=False,hull=222)
    e.db.commit()
    data=stats(e,"period=all&limit=1")
    assert data["ships"]["rows"][0]["ship_type_id"]==222
    assert data["ships"]["total"]==2 and data["ships"]["truncated"]
    assert data["systems"]["total"]==3 and data["summary"]["visits"]==3
    span=stats(e,"period=all&ship_order=span&limit=1")
    assert span["ships"]["rows"][0]["ship_type_id"]==111


def test_entire_history_beyond_replay_and_hull_limits_is_aggregated(env):
    e=env
    for index in range(2010):
        row=visit(e,0,10 if index%2==0 else 11,index/100,length=0,gap=index==0)
        e.db.add_all([JourneyShipSegment(visit_id=row.id,ship_type_id=111,first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,samples=1,gap_before=True) for _ in range(3)])
    e.db.commit(); data=stats(e)
    assert data["summary"]["visits"]==2010 and data["summary"]["jumps"]==2009
    assert data["ships"]["rows"][0]["segments"]==6030
    assert data["ships"]["rows"][0]["visits"]==2010 and data["ships"]["rows"][0]["observed_seconds"]==0


def test_false_continuity_with_no_predecessor_or_same_system_is_not_a_jump(env):
    e=env; visit(e,0,10,0,gap=False);visit(e,0,10,11,gap=False);visit(e,0,11,22,gap=True);e.db.commit()
    assert stats(e)["summary"]["jumps"]==0


def test_empty_account_and_paused_history_do_not_require_live_authorization(env):
    e=env
    user=User(email="empty-journey@invalid.test",display_name="No linked pilots",role="officer")
    e.db.add(user);e.db.commit();e.actor[0]=user
    data=stats(e)
    assert data["summary"]==dict(pilots=0,visits=0,systems=0,jumps=0,observed_seconds=0,
        visits_without_hull=0,kills=0,losses=0)
    assert all(data[key]["rows"]==[] for key in ("systems","ships","combat_ships","kill_systems","lost_ships","pilots"))
    e.actor[0]=e.users[0];visit(e,0,10,0,hull=111);e.db.commit()
    assert not e.trackers[0].enabled and stats(e)["summary"]["visits"]==1


def test_all_history_includes_older_stored_combat_without_claiming_a_recorded_hull(env):
    e=env;row=visit(e,0,10,-86400,length=10,hull=None)
    mail(e,100,victim=e.chars[0].character_id,minute=-86400);e.db.commit()
    data=stats(e)
    assert data["summary"]["visits"]==1 and data["summary"]["losses"]==1
    assert data["summary"]["visits_without_hull"]==1 and data["ships"]["rows"]==[]
    ranged=stats(e,"from_at=2026-11-08T00:00:00Z&to_at=2026-11-09T00:00:00Z")
    assert ranged["summary"]["visits"]==ranged["summary"]["losses"]==0


def test_multiple_hulls_in_one_visit_are_distinct_hull_use_without_duplicate_visits(env):
    e=env;row=visit(e,0,10,0,length=10,hull=111)
    first=e.db.scalar(select(JourneyShipSegment).where(JourneyShipSegment.visit_id==row.id))
    first.last_seen_at=AT+timedelta(minutes=5)
    e.db.add(JourneyShipSegment(visit_id=row.id,ship_type_id=222,first_seen_at=AT+timedelta(minutes=6),
        last_seen_at=AT+timedelta(minutes=10),samples=2,gap_before=False));e.db.commit()
    data=stats(e)
    assert data["summary"]["visits"]==1 and data["summary"]["observed_seconds"]==540
    assert sum(r["visits"] for r in data["ships"]["rows"])==2
    assert data["summary"]["jumps"]==0


def test_timezone_offsets_and_single_sample_ranges(env):
    e=env;visit(e,0,10,0,length=0,hull=111);e.db.commit()
    data=stats(e,"from_at=2026-11-08T14:00:00%2B02:00&to_at=2026-11-08T14:01:00%2B02:00")
    assert data["summary"]["visits"]==1 and data["summary"]["observed_seconds"]==0
    assert data["ships"]["rows"][0]["visits"]==1
