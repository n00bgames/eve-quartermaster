"""User-requested, durable system-wide zKill discovery with canonical ESI imports."""
import asyncio
import json
import math
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, or_, select, update

from app.db.session import SessionLocal
from app.models import KillboardSyncRun, Killmail, User
from app.services.battle_report_scope import BattleWindow, utc
from app.services.battle_reports import _require_report_pilot, resolve_battle_window
from app.services.esi_client import EsiClient
from app.services.killboard_settings import killboard_settings
from app.services.killboard_sync import (ZKILLBOARD_HEADERS, discovery_identity, ensure_discovery,
    parse_killmail_time, upsert_enrichment, upsert_killmail, validate_canonical_payload)
from app.services.permissions import can_view_section

TASKS = {}
TERMINAL = {'complete', 'partial', 'cancelled'}
MAX_PAGES = 100
MAX_IMPORTS = 20000
_request_lock = asyncio.Lock()
_last_request = 0.0


def now():
    return datetime.now(timezone.utc)


class SystemDiscoveryClient:
    def __init__(self):
        self.client = httpx.AsyncClient(headers=ZKILLBOARD_HEADERS, timeout=45, follow_redirects=True)

    async def fetch_page(self, target, page):
        global _last_request
        path = f"https://zkillboard.com/api/solarSystemID/{target['owner_id']}/"
        if target.get('past_seconds'):
            path += f"pastSeconds/{target['past_seconds']}/"
        else:
            path += f"year/{target['year']}/month/{target['month']}/"
        path += f'page/{page}/'
        for attempt in range(3):
            async with _request_lock:
                await asyncio.sleep(max(0, 1.0-(time.monotonic()-_last_request)))
                async with self.client.stream('GET', path) as response:
                    _last_request = time.monotonic()
                    if response.status_code == 429:
                        try:
                            retry = float(response.headers.get('Retry-After', '5'))
                        except ValueError:
                            retry = 5
                        await asyncio.sleep(min(60, max(1, retry)))
                        continue
                    response.raise_for_status()
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 32*1024*1024:
                            raise ValueError('zKillboard page exceeded the collection size limit')
            payload = json.loads(data)
            if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
                raise ValueError('zKillboard returned an error or unsupported response; collection is incomplete')
            if len(payload) > 1000:
                raise ValueError('zKillboard returned an unexpectedly large page')
            return payload
        raise ValueError('zKillboard rate limit prevented collection; retry later')

    async def close(self):
        await self.client.aclose()


def targets_for(window):
    start, end = utc(window.start_time), utc(window.end_time)
    recent = start >= now()-timedelta(days=7)
    months = []
    date = start.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    while date <= end:
        months.append((date.year,date.month))
        date = (date.replace(day=28)+timedelta(days=4)).replace(day=1)
    return [dict(owner_type='system', owner_id=system_id,
        **({'past_seconds': min(604800, max(3600, math.ceil((now()-start).total_seconds()/3600)*3600))}
           if recent else {'year': year, 'month': month}))
        for system_id in window.system_ids for year,month in ([(0,0)] if recent else months)]


def create_job(db, user, *, character_id, gap_minutes=15, seed_killmail_id=None, battle_window=None):
    if not killboard_settings(db)['enabled']:
        raise ValueError('The Killboard data source is disabled')
    _, seed, scope = resolve_battle_window(db,user,character_id=character_id,gap_minutes=gap_minutes,
        seed_killmail_id=seed_killmail_id,battle_window=battle_window)
    if seed is None:
        raise ValueError('Sync the selected pilot first so EQM can identify a battle')
    window = BattleWindow.model_validate(scope)
    pending = db.scalar(select(KillboardSyncRun).where(KillboardSyncRun.feed=='battle',
        KillboardSyncRun.initiated_by_user_id==user.id,
        KillboardSyncRun.status.in_(['queued','running','paused','failed'])).order_by(KillboardSyncRun.created_at.desc()))
    if pending:
        raise ValueError('Finish, resume or cancel your previous battle collection first')
    recent_count = db.scalar(select(func.count()).select_from(KillboardSyncRun).where(
        KillboardSyncRun.feed=='battle',KillboardSyncRun.initiated_by_user_id==user.id,
        KillboardSyncRun.created_at>now()-timedelta(minutes=1))) or 0
    if recent_count:
        raise ValueError('Wait one minute between battle collections; zKillboard responses are cached')
    active = db.scalar(select(func.count()).select_from(KillboardSyncRun).where(
        KillboardSyncRun.feed=='battle',KillboardSyncRun.status.in_(['queued','running']),
        KillboardSyncRun.updated_at>now()-timedelta(minutes=2))) or 0
    if active >= 2:
        raise ValueError('Battle collection queue is busy; retry shortly')
    metadata = dict(character_id=character_id,seed_killmail_id=seed.killmail_id,
        gap_minutes=gap_minutes,window=scope)
    targets = [{**target,'battle':metadata} for target in targets_for(window)]
    row = KillboardSyncRun(id=uuid.uuid4().hex,initiated_by_user_id=user.id,status='queued',feed='battle',
        targets_json=targets,lookback_days=1,errors_json=[],message='Queued system-wide battle collection.')
    db.add(row);db.flush()
    return row


def require_job(db,user,job_id):
    row = db.get(KillboardSyncRun,job_id)
    if row is None or row.feed!='battle' or row.initiated_by_user_id!=user.id:
        raise LookupError('Battle collection was not found')
    meta = row.targets_json[0]['battle']
    _require_report_pilot(db,user,meta['character_id'])
    return row


def payload(row):
    meta = row.targets_json[0]['battle']
    active = row.id in TASKS and not TASKS[row.id].done()
    return dict(job_id=row.id,status=row.status,**meta,page=row.page,target_index=row.target_index,
        target_count=len(row.targets_json),discovered_count=row.discovered_count,imported_count=row.imported_count,
        cached_count=row.skipped_count,failed_count=row.failed_count,message=row.message,
        can_resume=row.status not in TERMINAL and not active and (row.status!='running' or utc(row.updated_at)<=now()-timedelta(minutes=2)),
        checked_at=utc(row.updated_at).isoformat() if row.updated_at else None)


def report_coverage(db,user,job_id,*,character_id,window):
    row=require_job(db,user,job_id)
    meta=row.targets_json[0]['battle']
    if meta['character_id']!=character_id or meta['window']!=BattleWindow.model_validate(window).model_dump(mode='json'):
        raise ValueError('Collection does not match this pilot and battle window')
    return {k:v for k,v in payload(row).items() if k in {'status','discovered_count','imported_count','cached_count','failed_count','message','checked_at'}}


def start(job_id):
    if job_id in TASKS and not TASKS[job_id].done():return False
    task=asyncio.create_task(execute(job_id))
    TASKS[job_id]=task
    task.add_done_callback(lambda completed: TASKS.pop(job_id,None) if TASKS.get(job_id) is completed else None)
    return True


def allowed(db,row,lease=None):
    if row is None or row.feed!='battle' or row.status in TERMINAL:return False
    if lease is not None and row.targets_json[0].get('lease')!=lease:return False
    user=db.get(User,row.initiated_by_user_id) if row.initiated_by_user_id else None
    if user is None or user.deleted_at is not None or not can_view_section(user,'battle_reports',db) or not killboard_settings(db)['enabled']:
        return False
    try:_require_report_pilot(db,user,row.targets_json[0]['battle']['character_id'])
    except (LookupError,PermissionError):return False
    return True


async def execute(job_id, *, discovery=None, canonical=None, budget_seconds=900):
    lease=uuid.uuid4().hex
    with SessionLocal() as db:
        row=db.get(KillboardSyncRun,job_id)
        if not allowed(db,row):return
        if row.status=='running' and utc(row.updated_at)>now()-timedelta(minutes=2):return
        targets=[dict(x) for x in row.targets_json];targets[0]['lease']=lease
        claim=db.execute(update(KillboardSyncRun).where(KillboardSyncRun.id==job_id,
            KillboardSyncRun.status==row.status,
            or_(KillboardSyncRun.status!='running',KillboardSyncRun.updated_at<now()-timedelta(minutes=2))).values(status='running',targets_json=targets,
                started_at=row.started_at or now(),updated_at=now(),message='Discovering all kills in the battle systems and UTC window.'))
        if not claim.rowcount:db.rollback();return
        db.commit()
    own_discovery=discovery is None;own_canonical=canonical is None
    discovery=discovery or SystemDiscoveryClient();canonical=canonical or EsiClient()
    deadline=time.monotonic()+budget_seconds
    seen=set()
    try:
        while True:
            with SessionLocal() as db:
                run=db.get(KillboardSyncRun,job_id)
                if not allowed(db,run,lease):
                    if run and run.status=='running' and run.targets_json[0].get('lease')==lease:
                        run.status='cancelled';run.message='Collection stopped because access or the data source changed.';run.updated_at=now();db.commit()
                    return
                if run.target_index>=len(run.targets_json):
                    run.status='partial' if run.failed_count else 'complete';run.finished_at=now();run.updated_at=now()
                    run.message=('Collection partial: '+(run.message or 'Some records or pages could not be collected.')) if run.failed_count else 'Collection finished. zKillboard coverage is best-effort; recent/delayed kills may appear later.'
                    db.commit();return
                if time.monotonic()>=deadline:
                    run.status='paused';run.message='Collection paused at its time budget. Resume to continue from the saved page.';run.updated_at=now();db.commit();return
                if run.imported_count+run.updated_count>=MAX_IMPORTS:
                    run.status='partial';run.message='Collection reached 20,000 imported records; narrow the window for further coverage.';run.updated_at=now();db.commit();return
                target=dict(run.targets_json[run.target_index]);page=run.page
                scope=BattleWindow.model_validate(target['battle']['window'])
            # No database transaction or ORM session is retained during HTTP waits.
            entries=await discovery.fetch_page(target,page)
            for entry in entries:
                if time.monotonic()>=deadline:break
                with SessionLocal() as db:
                    run=db.get(KillboardSyncRun,job_id)
                    if not allowed(db,run,lease):return
                    if run.imported_count+run.updated_count>=MAX_IMPORTS:
                        run.status='partial';run.message='Collection reached 20,000 imported records; narrow the window for further coverage.';run.updated_at=now();db.commit();return
                try:
                    kid,khash=discovery_identity(entry)
                    if kid<=0 or len(khash)!=40 or any(c not in '0123456789abcdef' for c in khash.lower()):
                        raise ValueError('Invalid killmail identity')
                    if kid in seen:continue
                    seen.add(kid)
                    # Metadata only limits redundant canonical reads; imported facts
                    # always come from ESI (or an existing verified ESI cache row).
                    listed_time=parse_killmail_time(entry['killmail_time']) if entry.get('killmail_time') else None
                    if listed_time and not scope.start_time<=listed_time<=scope.end_time:continue
                    with SessionLocal() as db:
                        existing=db.get(Killmail,kid)
                        cached=existing is not None and existing.killmail_hash==khash
                        existing_time=utc(existing.killmail_time) if cached else None
                        existing_system=existing.solar_system_id if cached else None
                    raw=None
                    if not cached:
                        raw=await canonical.get(f'/killmails/{kid}/{khash}/')
                        raw,kill_time,system_id=validate_canonical_payload(raw)
                        if raw.get('killmail_id',kid)!=kid:raise ValueError('ESI killmail ID does not match discovery')
                    else:kill_time,system_id=existing_time,existing_system
                    with SessionLocal() as db:
                        run=db.get(KillboardSyncRun,job_id)
                        if not allowed(db,run,lease):return
                        run.discovered_count+=1;run.updated_at=now()
                        if system_id!=target['owner_id'] or not scope.start_time<=kill_time<=scope.end_time:
                            run.skipped_count+=1;db.commit();continue
                        if cached:
                            ensure_discovery(db,kid,'system',system_id,'battle');upsert_enrichment(db,kid,entry);run.skipped_count+=1
                        else:
                            _,created=upsert_killmail(db,killmail_id=kid,killmail_hash=khash,esi_payload=raw,
                                zkill_payload=entry,owner_type='system',owner_id=system_id,feed='battle')
                            if created:run.imported_count+=1
                            else:run.updated_count+=1
                        db.commit()
                except Exception:
                    with SessionLocal() as db:
                        run=db.get(KillboardSyncRun,job_id)
                        if not allowed(db,run,lease):return
                        run.failed_count+=1;run.updated_at=now();run.message='Some canonical records could not be imported; coverage will be marked partial.';db.commit()
            with SessionLocal() as db:
                run=db.get(KillboardSyncRun,job_id)
                if not allowed(db,run,lease):return
                if time.monotonic()>=deadline:
                    run.status='paused';run.message='Collection paused; resume to retry the current page safely.'
                elif not entries:
                    run.target_index+=1;run.page=1
                elif page>=MAX_PAGES:
                    run.failed_count+=1;run.message='zKillboard page limit reached; collection is partial.'
                    run.target_index+=1;run.page=1
                else:run.page+=1
                run.updated_at=now();db.commit()
                if run.status=='paused':return
    except Exception:
        with SessionLocal() as db:
            run=db.get(KillboardSyncRun,job_id)
            if allowed(db,run,lease):
                run.status='failed';run.message='Collection interrupted by a source or import error. Resume to retry the saved page.';run.updated_at=now();db.commit()
    finally:
        with SessionLocal() as db:
            run=db.get(KillboardSyncRun,job_id)
            if run and run.status=='running' and run.targets_json[0].get('lease')==lease and not allowed(db,run,lease):
                run.status='cancelled';run.message='Collection stopped because access or the source changed.';run.updated_at=now();db.commit()
        if own_discovery:await discovery.close()
        if own_canonical:await canonical.close()
