import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, inspect, select, create_engine
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.api.intel_membership import router
from app.domain.intel import utc
from app.models import EveCharacter
from app.models.intel import IntelObservation, IntelSubject
from app.models.intel_membership import IntelMembershipMonitor, IntelMembershipSnapshot
from app.services import intel_membership as service
from app.services.intel_membership_report import read
from app.services.intel_membership_source import MembershipSource, MAX_CORPORATIONS
from .test_intel_reports import env, subject


@pytest.fixture
def member(env):
    env.app.include_router(router)
    env.sid = subject(env, "corporation", 8002)["id"]
    return env


def sample(db, sid, at, count, corporations=None):
    rows = corporations or []
    db.add(IntelMembershipSnapshot(subject_id=sid, utc_day=at.date().isoformat(), observed_at=at,
        member_count=count, corporation_count=len(rows) if corporations is not None else None,
        resolved_corporations=len([r for r in rows if r["member_count"] is not None]),
        known_member_count=count, corporations=rows))
    db.commit()


def payload(count=100):
    return {"member_count":count,"corporation_count":None,"resolved_corporations":0,"known_member_count":count,"corporations":[]}


def report(member, start=None, end=None):
    end = end or service.now() + timedelta(seconds=1)
    return read(member.db, member.db.get(IntelSubject, member.sid), start or end-timedelta(days=365), end)


class Census:
    def __init__(self, result=None, before=None, fail=False):
        self.result = result or payload()
        self.before = before
        self.fail = fail
        self.calls = []
    async def census(self, kind, eid):
        self.calls.append((kind, eid))
        if self.before:
            self.before()
        if self.fail:
            raise RuntimeError("Synthetic failure containing no upstream credentials")
        return self.result


def run(member, source=None):
    asyncio.run(service.run_sample(member.sid, source=source or Census(), factory=member.factory))
    member.db.expire_all()


def test_manual_refresh_and_shared_daily_toggle_do_not_enroll_characters(member):
    url=f"/intel/subjects/{member.sid}/membership"
    assert member.client.get(url).json()["monitor"]["enabled"] is False
    assert member.client.post(url+"/refresh").status_code==202
    run(member)
    result=member.client.get(url).json()
    assert (result["member_count"],result["monitor"]["enabled"],result["monitor"]["next_poll_at"])==(100,False,None)
    assert member.client.put(url+"/monitoring",json={"enabled":True}).status_code==200
    run(member)
    result=member.client.get(url).json()
    assert result["monitor"]["enabled"] and result["monitor"]["next_poll_at"]
    assert member.client.put(url+"/monitoring",json={"enabled":False}).status_code==200
    assert member.client.get(url).json()["member_count"]==100
    assert member.db.scalar(select(func.count()).select_from(EveCharacter))==0
    for value in ["true",1,None]:
        assert member.client.put(url+"/monitoring",json={"enabled":value}).status_code==422
    assert member.client.put(url+"/monitoring",json={"enabled":True,"character_id":123}).status_code==422


def test_access_is_intel_scoped_including_role_loss(member):
    url=f"/intel/subjects/{member.sid}/membership"
    for user in [member.users[3], member.users[4], None]:
        member.current[0]=user
        expected=401 if user is None else 403
        assert member.client.get(url).status_code==expected
        assert member.client.post(url+"/refresh").status_code==expected
        assert member.client.put(url+"/monitoring",json={"enabled":True}).status_code==expected
    member.current[0]=member.users[0]
    character=subject(member)["id"]
    assert member.client.get(f"/intel/subjects/{character}/membership").status_code==422
    assert member.client.post(f"/intel/subjects/{character}/membership/refresh").status_code==422
    assert member.client.get(url+"?from_at=2026-11-02T00:00:00Z&to_at=2026-11-01T00:00:00Z").status_code==422


def test_snapshot_lease_exclusion_pause_and_permission_recheck(member):
    current=member.db.get(IntelSubject,member.sid)
    service.request_refresh(member.db,current,member.users[0],True)
    assert service.claim(member.factory,member.sid,"first")==("corporation",8002)
    assert service.claim(member.factory,member.sid,"second") is None
    service.request_refresh(member.db,current,member.users[0],False)
    service.persist(member.factory,member.sid,"first",payload())
    assert member.db.scalar(select(func.count()).select_from(IntelMembershipSnapshot))==0
    service.request_refresh(member.db,current,member.users[0],True)
    def revoke():
        with member.factory() as db:
            row=db.get(type(member.users[0]),member.users[0].id);row.deleted_at=service.now();db.commit()
    run(member,Census(before=revoke))
    monitor=member.db.get(IntelMembershipMonitor,member.sid)
    assert not monitor.enabled and monitor.status=="paused"
    assert member.db.scalar(select(func.count()).select_from(IntelMembershipSnapshot))==0


def test_lost_permissions_before_claim_stops_without_network(member):
    service.request_refresh(member.db,member.db.get(IntelSubject,member.sid),member.users[0],True)
    member.users[0].role="applicant";member.db.commit()
    source=Census();run(member,source)
    assert not source.calls
    assert member.db.get(IntelMembershipMonitor,member.sid).status=="paused"


def test_no_db_connection_held_while_fetching_and_event_loop_remains_free(member):
    service.request_refresh(member.db,member.db.get(IntelSubject,member.sid),member.users[0])
    engine=member.factory.kw["bind"];checked=[0]
    def checkout(*args):checked[0]+=1
    def checkin(*args):checked[0]-=1
    event.listen(engine,"checkout",checkout);event.listen(engine,"checkin",checkin)
    try:
        source=Census()
        async def census(kind,eid):
            assert checked[0]==0
            await asyncio.sleep(0)
            return payload()
        source.census=census
        run(member,source)
    finally:
        event.remove(engine,"checkout",checkout);event.remove(engine,"checkin",checkin)


def test_failure_preserves_complete_count_and_schedules_bounded_retry(member):
    at=service.now()-timedelta(days=1)
    sample(member.db,member.sid,at,180)
    service.request_refresh(member.db,member.db.get(IntelSubject,member.sid),member.users[0],True)
    run(member,Census(fail=True))
    data=report(member)
    assert data["member_count"]==180 and data["monitor"]["status"]=="unavailable"
    assert data["monitor"]["next_poll_at"] and len(data["history"])==1
    assert "Synthetic" not in data["monitor"]["notice"]


def test_same_day_complete_is_not_overwritten_by_partial_and_zero_is_valid(member):
    service.request_refresh(member.db,member.db.get(IntelSubject,member.sid),member.users[0],True)
    assert service.claim(member.factory,member.sid,"a")
    service.persist(member.factory,member.sid,"a",payload(0))
    member.db.expire_all()
    row=member.db.get(IntelMembershipMonitor,member.sid);row.next_poll_at=service.now();member.db.commit()
    assert service.claim(member.factory,member.sid,"b")
    service.persist(member.factory,member.sid,"b",{**payload(),"member_count":None})
    member.db.expire_all()
    assert report(member)["member_count"]==0
    assert member.db.scalar(select(func.count()).select_from(IntelMembershipSnapshot))==1


def test_net_change_windows_zero_baseline_and_real_observation_dates(member):
    at=service.now()-timedelta(hours=1)
    for days,n in [(92,0),(32,100),(8,130),(0,160)]:sample(member.db,member.sid,at-timedelta(days=days),n)
    data=report(member)
    windows={row["days"]:row for row in data["windows"]}
    assert [windows[d]["change"] for d in (7,30,90)]==[30,60,160]
    assert windows[90]["percent"] is None
    assert windows[7]["elapsed_days"]==8
    assert data["direction"]=="gaining"
    assert data["previous"]["change"]==30
    assert utc(windows[7]["baseline_at"])==at-timedelta(days=8)
    narrow=report(member,start=at-timedelta(days=1))
    assert len(narrow["history"])==1 and narrow["windows"][0]["change"]==30


def test_missing_baselines_and_long_gaps_do_not_manufacture_monthly_trends(member):
    at=service.now()-timedelta(hours=1)
    sample(member.db,member.sid,at-timedelta(days=15),100)
    sample(member.db,member.sid,at,90)
    data=report(member)
    assert all(w["state"]=="no_baseline" and w["change"] is None for w in data["windows"])
    assert data["direction"]=="losing" and data["previous"]["elapsed_days"]==15


def test_existing_corporation_observations_supply_only_real_historic_baselines(member):
    at=service.now()-timedelta(hours=1)
    member.db.add(IntelObservation(subject_id=member.sid,source="esi",fingerprint="old",payload={"member_count":40},observed_at=at-timedelta(days=30)))
    sample(member.db,member.sid,at,60)
    member.db.commit()
    data=report(member)
    assert data["windows"][1]["change"]==20
    assert data["history"][0]["source"]=="retained_public_profile"
    actual=member.client.get(f"/intel/subjects/{member.sid}/report").json()
    assert actual["membership"]["member_count"]==60
    assert actual["summary"]["kills"]==actual["summary"]["losses"]==0


def test_alliance_list_movements_and_incomplete_totals_are_separate(member):
    member.sid=subject(member,"alliance",7001)["id"]
    at=service.now()-timedelta(hours=1)
    org=lambda eid,name,n:{"eve_id":eid,"name":name,"member_count":n}
    sample(member.db,member.sid,at-timedelta(days=1),300,[org(8001,"Leaving corp",100),org(8002,"Staying corp",200)])
    sample(member.db,member.sid,at,None,[org(8002,"Staying corp",200),org(8003,"Joining corp",None)])
    data=report(member)
    assert data["member_count"]==300
    assert data["history"][-1]["member_count"] is None
    assert data["previous"] is None
    movement=data["corporation_changes"][0]
    assert movement["added"]==[{"eve_id":8003,"name":"Joining corp"}]
    assert movement["removed"]==[{"eve_id":8001,"name":"Leaving corp"}]


@pytest.mark.parametrize("bad",[None,True,-1,"22",2147483648])
def test_bad_public_corporation_counts_rejected(bad):
    async def get(path):return {"member_count":bad}
    async def check():
        source=MembershipSource()
        try:
            with patch.object(source.client,"get",side_effect=get):
                with pytest.raises(ValueError):await source.census("corporation",8001)
        finally:await source.close()
    asyncio.run(check())


def test_alliance_source_deduplicates_and_bounds_concurrency_and_handles_missing():
    peak=[0];active=[0];calls=[]
    async def get(path):
        calls.append(path)
        if path.startswith("/alliances/"):return list(range(1,10))+[1]
        active[0]+=1;peak[0]=max(peak[0],active[0]);await asyncio.sleep(0.001);active[0]-=1
        cid=int(path.split('/')[2])
        if cid==8:raise ValueError("unavailable")
        return {"member_count":10,"alliance_id":7001 if cid!=9 else 7002,"name":f"Corp {cid}"}
    async def check():
        source=MembershipSource()
        try:
            with patch.object(source.client,"get",side_effect=get):return await source.census("alliance",7001)
        finally:await source.close()
    data=asyncio.run(check())
    assert (data["member_count"],data["corporation_count"],data["resolved_corporations"],data["known_member_count"])==(None,9,7,70)
    assert 1<peak[0]<=4 and len(calls)==10


def test_complete_alliance_sum_and_oversized_list_never_silently_truncated():
    async def check(ids):
        source=MembershipSource()
        async def get(path):return ids if path.startswith('/alliances/') else {"member_count":12,"alliance_id":7001,"name":"Corp"}
        try:
            with patch.object(source.client,"get",side_effect=get):return await source.census("alliance",7001)
        finally:await source.close()
    assert asyncio.run(check([1,2]))["member_count"]==24
    assert asyncio.run(check([]))["member_count"]==0
    with pytest.raises(ValueError):asyncio.run(check(list(range(1,MAX_CORPORATIONS+2))))


def test_monitor_migration_round_trip_retains_existing_subjects():
    path=Path(__file__).parents[1]/"alembic/versions/0105_intel_membership.py"
    spec=importlib.util.spec_from_file_location("membership_migration",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    engine=create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("CREATE TABLE intel_subjects (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("INSERT INTO intel_subjects (id) VALUES (1)")
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            assert "intel_membership_snapshots" in inspect(conn).get_table_names()
            assert conn.exec_driver_sql("SELECT count(*) FROM intel_membership_monitors").scalar()==0
            module.downgrade()
            assert conn.exec_driver_sql("SELECT id FROM intel_subjects").scalar()==1
            assert "intel_membership_snapshots" not in inspect(conn).get_table_names()


def test_interrupted_sample_recovers_after_lease_expiry_without_duplicate_day(member):
    service.request_refresh(member.db,member.db.get(IntelSubject,member.sid),member.users[0],True)
    class Interrupted:
        async def census(self,*args):raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):run(member,Interrupted())
    member.db.expire_all()
    row=member.db.get(IntelMembershipMonitor,member.sid)
    assert row.status=="running" and row.lease_until is not None
    row.lease_until=service.now()-timedelta(seconds=1);member.db.commit()
    run(member)
    assert report(member)["member_count"]==100
    assert member.db.scalar(select(func.count()).select_from(IntelMembershipSnapshot))==1


def test_first_partial_alliance_remains_unknown_and_reads_are_no_store(member):
    member.sid=subject(member,"alliance",7001)["id"]
    sample(member.db,member.sid,service.now()-timedelta(minutes=1),None,[{"eve_id":8002,"name":"Unknown count","member_count":None}])
    response=member.client.get(f"/intel/subjects/{member.sid}/membership")
    assert response.headers["cache-control"]=="private, no-store"
    data=response.json()
    assert data["member_count"] is None and data["direction"]=="insufficient_history"
    assert data["history"][0]["member_count"] is None
    assert all(w["change"] is None for w in data["windows"])
