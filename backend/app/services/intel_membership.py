"""Shared Intel workspace monitoring, using short DB transactions and fenced leases."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from app.db.session import SessionLocal
from app.domain.intel import utc
from app.models import User
from app.models.intel import IntelSubject
from app.models.intel_membership import IntelMembershipMonitor, IntelMembershipSnapshot
from app.services.intel_reports import require_intel
from app.services.intel_membership_source import MembershipSource

_task = None


def now():
    return datetime.now(timezone.utc)


def organization(subject):
    if subject.kind not in {"corporation", "alliance"}:
        raise HTTPException(422, "Membership monitoring requires a corporation or alliance dossier")


def monitor_payload(row):
    if row is None:
        return {"enabled": False, "status": "idle", "next_poll_at": None,
                "last_attempt_at": None, "last_success_at": None, "notice": None}
    return {key: (utc(value) if isinstance(value := getattr(row, key), datetime) else value)
            for key in ("enabled", "status", "next_poll_at", "last_attempt_at", "last_success_at", "notice")}


def get_monitor(db, sid):
    row = db.get(IntelMembershipMonitor, sid)
    if row is None:
        try:
            with db.begin_nested():
                row = IntelMembershipMonitor(subject_id=sid, enabled=False, status="idle", failures=0)
                db.add(row)
                db.flush()
        except IntegrityError:
            row = db.get(IntelMembershipMonitor, sid, populate_existing=True)
    return row


def request_refresh(db, subject, user, enabled=None):
    organization(subject)
    row = get_monitor(db, subject.id)
    at = now()
    if enabled is False:
        row.enabled = False
        row.next_poll_at = row.lease_token = row.lease_until = None
        row.status = "paused"
        row.notice = None
    else:
        active = row.status in {"queued", "running"} and row.next_poll_at is not None
        if enabled is None and active:
            row.requested_by_user_id = user.id
            db.commit()
            return row
        if enabled is None and row.last_attempt_at and at - utc(row.last_attempt_at) < timedelta(seconds=60):
            raise HTTPException(429, "Counts were checked recently; wait one minute before refreshing")
        if enabled is True:
            row.enabled = True
            row.requested_by_user_id = user.id
            if active:
                db.commit()
                return row
        row.requested_by_user_id = user.id
        row.next_poll_at = at
        row.lease_token = row.lease_until = None
        row.status = "queued"
        row.notice = None
        row.failures = 0
    db.commit()
    return row


def allowed(db, row):
    user = db.get(User, row.requested_by_user_id) if row.requested_by_user_id else None
    if user is None:
        return False
    try:
        require_intel(user, db)
    except HTTPException:
        return False
    return True


def pause_unauthorized(row):
    row.enabled = False
    row.next_poll_at = row.lease_token = row.lease_until = None
    row.status = "paused"
    row.notice = "Monitoring paused: the requesting analyst no longer has Intel access."


def claim(factory, sid, token):
    with factory() as db:
        at = now()
        result = db.execute(update(IntelMembershipMonitor).where(
            IntelMembershipMonitor.subject_id == sid, IntelMembershipMonitor.next_poll_at <= at,
            or_(IntelMembershipMonitor.lease_until.is_(None), IntelMembershipMonitor.lease_until <= at))
            .values(lease_token=token, lease_until=at + timedelta(minutes=5), status="running", last_attempt_at=at))
        if result.rowcount != 1:
            db.rollback()
            return None
        row = db.get(IntelMembershipMonitor, sid)
        subject = db.get(IntelSubject, sid)
        if not subject or not allowed(db, row):
            pause_unauthorized(row)
            db.commit()
            return None
        identity = (subject.kind, subject.eve_id)
        db.commit()
        return identity


def persist(factory, sid, token, payload, error=False):
    with factory() as db:
        row = db.scalar(select(IntelMembershipMonitor).where(
            IntelMembershipMonitor.subject_id == sid, IntelMembershipMonitor.lease_token == token,
            IntelMembershipMonitor.lease_until > now()).with_for_update())
        if row is None:
            return
        if not allowed(db, row):
            pause_unauthorized(row)
            db.commit()
            return
        at = now()
        complete = payload is not None and payload["member_count"] is not None
        if payload is not None:
            day = at.date().isoformat()
            snapshot = db.scalar(select(IntelMembershipSnapshot).where(
                IntelMembershipSnapshot.subject_id == sid, IntelMembershipSnapshot.utc_day == day))
            if snapshot is None:
                snapshot = IntelMembershipSnapshot(subject_id=sid, utc_day=day)
                db.add(snapshot)
            # Do not replace a complete same-day observation with a partial one.
            if snapshot.member_count is None or complete:
                for key in ("member_count", "corporation_count", "resolved_corporations", "known_member_count", "corporations"):
                    setattr(snapshot, key, payload[key])
                snapshot.observed_at = at
        if complete:
            row.last_success_at = at
            row.failures = 0
            row.status = "available"
            row.notice = None
            row.next_poll_at = at + timedelta(days=1) if row.enabled else None
        else:
            row.failures += 1
            row.status = "unavailable" if error else "partial"
            row.notice = "Public ESI counts are unavailable; the last complete total is retained." if error else "Some corporation counts are missing or their cached affiliation disagrees. No alliance pilot total was recorded."
            row.next_poll_at = at + timedelta(minutes=min(360, 5 * 2 ** min(row.failures - 1, 7))) if row.enabled else None
        row.lease_token = row.lease_until = None
        db.commit()


async def run_sample(sid, source=None, factory=SessionLocal):
    token = str(uuid4())
    identity = await asyncio.to_thread(claim, factory, sid, token)
    if identity is None:
        return
    owns = source is None
    source = source or MembershipSource()
    try:
        payload = await asyncio.wait_for(source.census(*identity), timeout=180)
        await asyncio.to_thread(persist, factory, sid, token, payload)
    except asyncio.CancelledError:
        # The short lease expires after interruption; no partial census is written.
        raise
    except Exception:
        await asyncio.to_thread(persist, factory, sid, token, None, True)
    finally:
        if owns:
            await source.close()


def due_subject(factory):
    with factory() as db:
        at = now()
        return db.scalar(select(IntelMembershipMonitor.subject_id).where(
            IntelMembershipMonitor.next_poll_at <= at,
            or_(IntelMembershipMonitor.lease_until.is_(None), IntelMembershipMonitor.lease_until <= at))
            .order_by(IntelMembershipMonitor.next_poll_at, IntelMembershipMonitor.subject_id).limit(1))


async def worker_loop():
    while True:
        try:
            sid = await asyncio.to_thread(due_subject, SessionLocal)
            if sid is None:
                await asyncio.sleep(5)
            else:
                await run_sample(sid)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).warning("Membership monitor unavailable; retrying")
            await asyncio.sleep(5)


def start_membership_worker():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(worker_loop())


async def stop_membership_worker():
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
