"""Durable timer reminders, calendar boundaries and source lifecycle."""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.api import structure_timers as api, structures, notifications, events
from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import Base, User, UserSectionPermission, AuditEvent, Event, ManualPos, RoleDefinition, UserRoleAssignment
from app.models.structure_timer import StructureTimerConfig as Config, StructureTimer as Timer, StructureTimerDelivery as Delivery
from app.services import structure_timers as service
from app.services.events import event_is_visible, can_manage_event

AT = datetime(2026,11,9,18,tzinfo=timezone.utc)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(service, 'now', lambda: AT)
    from app.api import manual_pos
    monkeypatch.setattr(manual_pos, 'utcnow', lambda: AT)
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    users = [User(email=f'timer{i}@invalid.test', display_name=role, role=role) for i,role in enumerate(['officer','director','member','admin'])]
    db.add_all(users);db.flush()
    pos = ManualPos(id=str(uuid4()), owner_user_id=users[0].id, name='Demo bridge tower', tower_type='Caldari Control Tower',
                    corporation_name='Demo Logistics', location='Demo System V Moon 14', state='online', fuel_blocks=80,
                    fuel_per_hour=40, stront_units=800, stront_per_hour=400, observed_at=AT, notes='SECRET PRIVATE NOTE',
                    version=1, created_at=AT, updated_at=AT)
    db.add(pos);db.commit();actor=[users[0]]
    def database():
        try: yield db
        finally: db.rollback()
    app=FastAPI()
    for router in [api.router, structures.router, notifications.router, events.router]:app.include_router(router,prefix='/api')
    app.dependency_overrides[get_db]=database;app.dependency_overrides[get_current_user]=lambda:actor[0]
    with TestClient(app) as client:
        yield SimpleNamespace(db=db, client=client, users=users, pos=pos, actor=actor, engine=engine)
    db.close();engine.dispose()


def body(e, **changes):
    return dict(source='manual',source_id=e.pos.id,token_key=0,enabled=True,roles=['officer','director'],minutes=[1440,60],version=0,**changes)


def save(e, **changes):
    payload=body(e);payload.update(changes)
    response=e.client.put('/api/structure-timers',json=payload)
    assert response.status_code==200,response.text
    return response.json()


def fire(e, at=AT):
    cfg=e.db.scalar(select(Config));service.deliver(cfg,e.db,at);e.db.commit()


def test_opt_in_calendar_and_private_fields(env):
    e=env
    assert e.client.get('/api/structure-timers').json()['rows']==[]
    result=save(e);assert result['enabled'] and len(result['events'])==1
    event=e.db.scalar(select(Event));assert service.utc(event.start_at)==AT+timedelta(hours=2)
    assert event.registration_status=='closed' and not can_manage_event(event,e.users[3],e.db)
    assert event_is_visible(event,e.users[1],e.db)
    assert not event_is_visible(event,e.users[3],e.db)  # unselected admin gets no bypass
    assert 'SECRET' not in str(e.client.get('/api/events').json())
    e.actor[0]=e.users[1]
    response=e.client.get(f'/api/events/{event.id}')
    assert response.status_code==200,response.text
    assert 'SECRET' not in response.text and '80 blocks' not in response.text
    assert response.json()['permissions']['can_manage'] is False
    assert e.client.get('/api/structures/manual-pos').json()['rows']==[]


def test_delivery_catchup_dedup_and_second_threshold(env):
    e=env;save(e,minutes=[10080,1440,60]);fire(e);fire(e)
    notices=list(e.db.scalars(select(AuditEvent)));assert len(notices)==2
    assert {n.recipient_user_id for n in notices}=={e.users[0].id,e.users[1].id}
    assert all(n.event_kind=='structure_timer' and 'SECRET' not in n.body for n in notices)
    fire(e,AT+timedelta(minutes=61));fire(e,AT+timedelta(minutes=62))
    assert len(list(e.db.scalars(select(AuditEvent))))==4
    assert len(e.client.get('/api/structure-timers/alerts').json()['rows'])==1
    fire(e,AT+timedelta(days=5));assert len(list(e.db.scalars(select(AuditEvent))))==4
    assert e.client.get('/api/notifications').json()['unread_count']==2


def test_banner_dismiss_is_recipient_private_and_role_revocation(env):
    e=env;save(e);fire(e)
    alert=e.client.get('/api/structure-timers/alerts').json()['rows'][0]
    e.actor[0]=e.users[1]
    assert e.client.post(f'/api/structure-timers/alerts/{alert["id"]}/dismiss').status_code==404
    e.actor[0]=e.users[0]
    assert e.client.post(f'/api/structure-timers/alerts/{alert["id"]}/dismiss').status_code==200
    assert e.client.get('/api/structure-timers/alerts').json()['rows']==[]
    e.actor[0]=e.users[1];e.users[1].role='member';e.db.commit()
    assert e.client.get('/api/structure-timers/alerts').json()['rows']==[]
    assert not event_is_visible(e.db.scalar(select(Event)),e.users[1],e.db)


def test_reschedule_refuel_reinforced_and_disable(env):
    e=env;result=save(e);fire(e)
    cfg=e.db.scalar(select(Config));timer=e.db.scalar(select(Timer));event_id=timer.event_id
    e.pos.fuel_blocks=800;e.db.flush();service.sync_manual(e.db,e.users[0].id,e.pos.id);e.db.commit()
    assert timer.generation==2 and timer.event_id==event_id
    assert e.client.get('/api/structure-timers/alerts').json()['rows']==[]
    e.pos.state='reinforced';e.pos.reinforced_until=AT+timedelta(hours=3);e.db.flush()
    service.sync_manual(e.db,e.users[0].id,e.pos.id);e.db.commit()
    timers={t.kind:t for t in e.db.scalars(select(Timer))};assert timers['fuel'].deadline is None
    assert service.utc(timers['reinforcement'].deadline)==AT+timedelta(hours=3)
    e.pos.reinforced_until=None;e.db.flush();service.sync_manual(e.db,e.users[0].id,e.pos.id);e.db.commit()
    assert service.utc(timers['reinforcement'].deadline)==AT+timedelta(hours=2)
    save(e,enabled=False,version=result['version']);fire(e)
    assert all(event.lifecycle_status=='cancelled' for event in e.db.scalars(select(Event)))
    assert e.client.get('/api/structure-timers/alerts').json()['rows']==[]


def test_owner_gate_validation_and_conflict(env):
    e=env
    e.actor[0]=e.users[2]
    assert e.client.put('/api/structure-timers',json=body(e)).status_code==403
    e.actor[0]=e.users[3]
    assert e.client.put('/api/structure-timers',json=body(e)).status_code==409
    e.actor[0]=e.users[0]
    for changes in [dict(minutes=[0]),dict(minutes=[43201]),dict(minutes=[1.5]),dict(roles=['missing']),dict(roles=['applicant']),dict(token_key=1),dict(deadline='2027-01-01')]:
        payload=body(e);payload.update(changes)
        assert e.client.put('/api/structure-timers',json=payload).status_code==422
    save(e)
    assert e.client.put('/api/structure-timers',json=body(e)).status_code==409
    e.users[0].role='member';e.db.commit();fire(e)
    assert not list(e.db.scalars(select(AuditEvent)))


def test_deleted_source_cancels_and_permission_revocation_hides(env):
    e=env;save(e);fire(e)
    e.db.add(UserSectionPermission(user_id=e.users[1].id,section='structures',can_view=False));e.db.commit()
    e.actor[0]=e.users[1];assert e.client.get('/api/structure-timers/alerts').json()['rows']==[]
    e.db.delete(e.pos);e.db.flush();service.sync_manual(e.db,e.users[0].id,e.pos.id);e.db.commit()
    assert not event_is_visible(e.db.scalar(select(Event)),e.users[1],e.db)
    assert e.db.scalar(select(Event)).lifecycle_status=='cancelled'


def test_custom_role_and_multiple_assignments(env):
    e=env;e.db.add(RoleDefinition(name='logistics',display_name='Logistics',base_role='officer'))
    e.db.add(UserRoleAssignment(user_id=e.users[1].id,role='logistics'));e.db.commit()
    save(e,roles=['logistics']);fire(e)
    assert [n.recipient_user_id for n in e.db.scalars(select(AuditEvent))]==[e.users[1].id]


def test_worker_runs_without_open_page_and_pauses_on_failed_source(env,monkeypatch):
    e=env;save(e)
    import app.db.session
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr(app.db.session,'SessionLocal',sessionmaker(e.engine))
    asyncio.run(service.tick());asyncio.run(service.tick());e.db.expire_all()
    assert len(list(e.db.scalars(select(AuditEvent))))==2
    async def fail(*args):raise RuntimeError('upstream detail must not leak')
    monkeypatch.setattr(service,'source',fail)
    asyncio.run(service.tick());e.db.expire_all()
    assert e.db.scalar(select(Config)).status.startswith('Source unavailable')
    assert e.db.scalar(select(Event)).lifecycle_status=='cancelled'
    assert e.client.get('/api/structure-timers/alerts').json()['rows']==[]


def test_temporary_failure_recovery_keeps_delivery_identity(env):
    e=env;save(e);fire(e)
    cfg=e.db.scalar(select(Config));timer=e.db.scalar(select(Timer));generation=timer.generation
    service.sync(cfg,e.db,status='Source unavailable');e.db.commit()
    assert e.client.get('/api/structure-timers/alerts').json()['rows']==[]
    service.sync(cfg,e.db,service.manual_source(e.pos));e.db.commit();fire(e)
    assert timer.generation==generation
    assert len(list(e.db.scalars(select(AuditEvent))))==2


def test_migration_roundtrip(env):
    e=env
    for table in [Delivery.__table__,Timer.__table__,Config.__table__]:table.drop(e.engine)
    path=Path(__file__).parents[1]/'alembic/versions/0110_structure_timers.py'
    spec=importlib.util.spec_from_file_location('timer_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with e.engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade();assert 'structure_timers' in inspect(conn).get_table_names()
            normal=conn.execute(Event.__table__.insert().values(title='User-authored event',event_type='other',start_at=AT)).inserted_primary_key[0]
            generated=conn.execute(Event.__table__.insert().values(title='Managed deadline',event_type='logistics',start_at=AT)).inserted_primary_key[0]
            config=conn.execute(Config.__table__.insert().values(owner_user_id=e.users[0].id,source='manual',source_id=e.pos.id,token_key=0)).inserted_primary_key[0]
            conn.execute(Timer.__table__.insert().values(config_id=config,kind='fuel',deadline=AT,event_id=generated))
            module.downgrade()
            assert 'structure_timers' not in inspect(conn).get_table_names()
            assert conn.scalar(select(Event.title).where(Event.id==normal))=='User-authored event'
            assert conn.scalar(select(Event.id).where(Event.id==generated)) is None


@pytest.mark.parametrize('kind,state,expected',[
    ('upwell','armor_reinforce',{'fuel','reinforcement'}),
    ('upwell','hull_reinforce',{'fuel','reinforcement'}),
    ('upwell','shield_vulnerable',{'fuel'}),
    ('upwell','anchoring',{'fuel'}),
    ('pos','reinforced',{'reinforcement'}),
])
def test_esi_fields_states_and_no_invented_pos_fuel(env,monkeypatch,kind,state,expected):
    e=env
    from app.models import EsiToken,EveCharacter
    from app.services import structures as esi,esi_scope_policy,esi_refresh,esi_client
    character=EveCharacter(character_id=900001,name='Demo Pilot',owner_user_id=e.users[0].id)
    e.db.add(character);e.db.flush()
    token=EsiToken(character_id=character.id,user_id=e.users[0].id,encrypted_refresh_token='synthetic',scopes=' '.join(esi.SCOPES))
    e.db.add(token);e.db.commit()
    monkeypatch.setattr(esi_scope_policy,'effective_token_scopes',lambda *args:esi.SCOPES)
    class Client:
        def __init__(self,**kwargs):pass
        async def close(self):pass
    monkeypatch.setattr(esi_client,'EsiClient',Client)
    async def refresh(*args):return 'synthetic'
    monkeypatch.setattr(esi_refresh,'refresh_access_token',refresh)
    async def overview(*args):
        row=dict(id=123,kind=kind,name='Demo Upwell',system_name='Demo System',state=state,
                 state_timer_end=(AT+timedelta(hours=2)).isoformat(),reinforced_until=(AT+timedelta(hours=3)).isoformat())
        if kind=='upwell':row['fuel_expires']=(AT+timedelta(days=2)).isoformat()
        return dict(sources=[dict(kind=kind,status='ok')],rows=[row])
    monkeypatch.setattr(esi,'overview',overview)
    result=save(e,source=kind,source_id='123',token_key=token.id)
    assert {t['kind'] for t in result['events']}==expected
    token.revoked_at=AT;e.db.commit()
    cfg=e.db.scalar(select(Config));assert not service.source_authorized(cfg,e.db)
    fire(e);assert not list(e.db.scalars(select(AuditEvent)))
    for event in e.db.scalars(select(Event)):assert not event_is_visible(event,e.users[1],e.db)


def test_manual_put_and_delete_resync_immediately(env):
    e=env;save(e);fire(e)
    payload={key:getattr(e.pos,key) for key in ('name','tower_type','corporation_name','location','state','fuel_blocks','fuel_per_hour','stront_units','stront_per_hour','notes')}
    payload.update(observed_at=AT.isoformat(),reinforced_until=None,version=1,fuel_blocks=4000)
    response=e.client.put(f'/api/structures/manual-pos/{e.pos.id}',json=payload)
    assert response.status_code==200,response.text
    assert service.utc(e.db.scalar(select(Timer)).deadline)==AT+timedelta(hours=100)
    assert e.client.get('/api/structure-timers/alerts').json()['rows']==[]
    assert e.client.delete(f'/api/structures/manual-pos/{e.pos.id}?version=2').status_code==200
    assert not event_is_visible(e.db.scalar(select(Event)),e.users[1],e.db)
