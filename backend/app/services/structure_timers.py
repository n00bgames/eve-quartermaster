"""Calendar deadlines and exactly-once EQM notices, restricted to selected roles."""
import asyncio
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import AuditEvent, EsiToken, EveCharacter, Event, ManualPos, User
from app.models.structure_timer import StructureTimerConfig as Config, StructureTimer as Timer, StructureTimerDelivery as Delivery
from app.services.permissions import assigned_roles, can_view_section

_task = None
LABELS = {'fuel': 'Fuel depletion', 'reinforcement': 'Reinforcement ends'}


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def now():
    return datetime.now(timezone.utc)


def manager(user, db):
    from app.services.events import can_create_event
    return bool(user and not user.deleted_at and can_view_section(user, 'structures', db) and can_create_event(user, db))


def eligible(config, user, db):
    return bool(user and not user.deleted_at and can_view_section(user, 'structures', db)
                and can_view_section(user, 'calendar_events', db)
                and set(assigned_roles(user, db)) & set(config.roles))


def source_authorized(config, db):
    if config.source == 'manual':
        row = db.get(ManualPos, config.source_id, populate_existing=True)
        return bool(row and row.owner_user_id == config.owner_user_id)
    from app.services.esi_scope_policy import effective_token_scopes
    from app.services.structures import UPWELL_SCOPE, POS_SCOPE
    token = db.get(EsiToken, config.token_key, populate_existing=True)
    character = db.get(EveCharacter, token.character_id, populate_existing=True) if token else None
    required = UPWELL_SCOPE if config.source == 'upwell' else POS_SCOPE
    return bool(token and not token.revoked_at and token.user_id == config.owner_user_id
                and character and character.owner_user_id == config.owner_user_id
                and required in effective_token_scopes(token, db))


def managed_timer(event, db):
    return db.scalar(select(Timer).where(Timer.event_id == event.id)) if event.id else None


def visible(timer, user, db):
    config = db.get(Config, timer.config_id)
    return bool(config and config.enabled and config.status == 'Tracking' and timer.deadline
                and manager(db.get(User, config.owner_user_id), db) and source_authorized(config, db)
                and (config.owner_user_id == user.id or eligible(config, user, db)))


def manual_source(row):
    deadlines = {}
    if row.state == 'online' and row.fuel_blocks is not None:
        deadlines['fuel'] = utc(row.observed_at) + timedelta(hours=row.fuel_blocks / row.fuel_per_hour)
    if row.state == 'reinforced':
        if row.reinforced_until:
            deadlines['reinforcement'] = utc(row.reinforced_until)
        elif row.stront_units is not None:
            deadlines['reinforcement'] = utc(row.observed_at) + timedelta(hours=row.stront_units / row.stront_per_hour)
    return row.name, row.location, deadlines, 'Manual estimate; verify in game. Update the private reading after refueling or a state change.'


async def source(config, db):
    if config.source == 'manual':
        row = db.get(ManualPos, config.source_id, populate_existing=True)
        if not row or row.owner_user_id != config.owner_user_id:
            raise ValueError('Manual record removed or unavailable')
        return manual_source(row)
    from app.services import structures
    from app.services.esi_client import EsiClient
    from app.services.esi_refresh import refresh_access_token
    from app.services.esi_scope_policy import effective_token_scopes
    token = db.get(EsiToken, config.token_key, populate_existing=True)
    character = db.get(EveCharacter, token.character_id, populate_existing=True) if token else None
    if not token or token.revoked_at or token.user_id != config.owner_user_id or not character or character.owner_user_id != config.owner_user_id:
        raise ValueError('Structures character authorization unavailable')
    scopes = effective_token_scopes(token, db)
    required = structures.UPWELL_SCOPE if config.source == 'upwell' else structures.POS_SCOPE
    if required not in scopes:
        raise ValueError('Structures scope unavailable')
    client = EsiClient(access_token=await refresh_access_token(token))
    try:
        result = await structures.overview(client, db, character, scopes)
    finally:
        await client.close()
    if not any(s['kind'] == config.source and s['status'] == 'ok' for s in result['sources']):
        raise ValueError('ESI unavailable or denied access; reminders paused')
    row = next((r for r in result['rows'] if r['kind'] == config.source and str(r['id']) == config.source_id), None)
    if not row:
        raise ValueError('Structure no longer reported by current corporation')
    deadlines = {}
    if row.get('fuel_expires'):
        deadlines['fuel'] = utc(row['fuel_expires'])
    if config.source == 'pos':
        end = row.get('reinforced_until') if row['state'] == 'reinforced' else None
    else:
        end = row.get('state_timer_end') if row['state'] in ('armor_reinforce', 'hull_reinforce') else None
    if end:
        deadlines['reinforcement'] = utc(end)
    return row['name'], row['system_name'], deadlines, 'ESI reading; ESI may cache data for up to one hour.'


def sync(config, db, reading=None, status='Tracking'):
    """Called under the configuration row lock; disabled/invalid sources cancel events."""
    config.status = status if config.enabled else 'Disabled'
    config.checked_at = now()
    name, location, deadlines, caveat = reading or ('', '', {}, '')
    if config.enabled and status != 'Tracking':
        # Preserve deadline identity through temporary ESI failures. Recovery
        # must not resend a threshold that was already delivered.
        for timer in db.scalars(select(Timer).where(Timer.config_id == config.id)):
            db.get(Event, timer.event_id).lifecycle_status = 'cancelled'
        return
    if not config.enabled or status != 'Tracking':
        deadlines = {}
    timers = {t.kind: t for t in db.scalars(select(Timer).where(Timer.config_id == config.id))}
    for kind in set(timers) | set(deadlines):
        deadline = deadlines.get(kind)
        timer = timers.get(kind)
        if not timer:
            event = Event(title=f'{LABELS[kind]} · {name}'[:255], event_type='logistics',
                          lifecycle_status='scheduled', registration_status='closed',
                          created_by_user_id=config.owner_user_id, start_at=deadline,
                          audience_kind='invite_only', doctrine_mode='none', operational_area=location)
            db.add(event); db.flush()
            timer = Timer(config_id=config.id, kind=kind, deadline=deadline, event_id=event.id, generation=1)
            db.add(timer); db.flush()
        else:
            event = db.get(Event, timer.event_id)
            if (utc(timer.deadline) if timer.deadline else None) != deadline:
                timer.generation += 1
            timer.deadline = deadline
        if deadline:
            event.title = f'{LABELS[kind]} · {name}'[:255]
            event.start_at = deadline
            event.operational_area = location
            event.lifecycle_status = 'scheduled'
            event.instructions = f'{caveat}\nManaged from Structures. Visible to selected eligible roles. Timer reminders are EQM notices, not attack detection.'
            event.related_url = None
        else:
            event.lifecycle_status = 'cancelled'


def deliver(config, db, at):
    if not config.enabled or config.status != 'Tracking' or not manager(db.get(User, config.owner_user_id), db) or not source_authorized(config, db):
        return
    users = [u for u in db.scalars(select(User).where(User.deleted_at.is_(None))) if eligible(config, u, db)]
    for timer in db.scalars(select(Timer).where(Timer.config_id == config.id, Timer.deadline.is_not(None))):
        seconds = (utc(timer.deadline) - at).total_seconds()
        # An overdue historical reading never triggers a new reminder.
        if seconds <= 0:
            continue
        due = sorted([m for m in config.minutes if seconds <= m * 60])
        if not due:
            continue
        # A late worker/configuration sends one catch-up notice, not every missed threshold.
        lead = due[0]
        event = db.get(Event, timer.event_id)
        for user in users:
            prior = db.scalars(select(Delivery).where(Delivery.timer_id == timer.id,
                Delivery.generation == timer.generation, Delivery.user_id == user.id)).all()
            if any(d.minutes <= lead for d in prior):
                continue
            try:
                with db.begin_nested():
                    notice = AuditEvent(event_kind='structure_timer', title=event.title,
                        body=f'{event.operational_area or ""}\nDeadline: {utc(timer.deadline).strftime("%Y-%m-%d %H:%M UTC")}\n{event.instructions}',
                        actor_user_id=config.owner_user_id, recipient_user_id=user.id, is_read=False)
                    db.add(notice); db.flush()
                    db.add(Delivery(timer_id=timer.id, generation=timer.generation, minutes=lead,
                                    user_id=user.id, notice_id=notice.id, dismissed=False))
                    db.flush()
            except IntegrityError:
                pass  # Unique delivery key also protects concurrent API workers/restarts.


async def refresh(config, db):
    if not config.enabled:
        sync(config, db)
        return
    if not manager(db.get(User, config.owner_user_id, populate_existing=True), db):
        sync(config, db, status='Owner no longer eligible; reminders paused')
        return
    try:
        reading = await source(config, db)
    except Exception:
        logging.getLogger(__name__).warning('Structure timer source unavailable (configuration %s)', config.id)
        sync(config, db, status='Source unavailable; reminders paused. Check record, ESI and permissions.')
        return
    sync(config, db, reading)


def sync_manual(db, user_id, source_id):
    for config in db.scalars(select(Config).where(Config.owner_user_id == user_id, Config.source == 'manual',
                                                 Config.source_id == source_id).with_for_update()):
        row = db.get(ManualPos, source_id, populate_existing=True)
        if row and row.owner_user_id == user_id and manager(db.get(User, user_id), db):
            sync(config, db, manual_source(row))
        else:
            sync(config, db, status='Manual source unavailable; reminders paused')


async def tick():
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        ids = list(db.scalars(select(Config.id).where(Config.enabled.is_(True))))
    for config_id in ids:
        # Network reads happen before acquiring a write lock. Recheck the saved
        # settings version and authorization before applying the result.
        with SessionLocal() as db:
            config = db.get(Config, config_id)
            if not config or not config.enabled:
                continue
            at = now()
            version = config.version
            checked_at = config.checked_at
            due = config.source == 'manual' or not config.checked_at or (at - utc(config.checked_at)).total_seconds() >= 300
            reading, status = None, 'Tracking'
            if due:
                try:
                    if not manager(db.get(User, config.owner_user_id), db):
                        raise ValueError('Owner unavailable')
                    reading = await source(config, db)
                except Exception:
                    status = 'Source unavailable; reminders paused. Check record, ESI and permissions.'
        with SessionLocal() as db:
            config = db.scalar(select(Config).where(Config.id == config_id).with_for_update())
            if not config or not config.enabled or config.version != version:
                continue
            if config.source != 'manual' and config.checked_at != checked_at:
                continue
            if not manager(db.get(User, config.owner_user_id), db) or not source_authorized(config, db):
                sync(config, db, status='Owner no longer eligible; reminders paused')
            elif due:
                # Another process may have refreshed since our source read.
                if config.source == 'manual':
                    reading = manual_source(db.get(ManualPos, config.source_id, populate_existing=True))
                sync(config, db, reading, status)
            deliver(config, db, now())
            db.commit()


async def run():
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.getLogger(__name__).exception('Structure timer worker failed')
        await asyncio.sleep(30)


def start_worker():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(run())


async def stop_worker():
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
