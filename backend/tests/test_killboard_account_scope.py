from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, EveCharacter, EveCorporation, KillboardSyncRun, Killmail, User
from app.services.killboard_analytics import build_killboard_analytics
from app.services.killboard_sync import (
    _advance_cursor, _execute_sync_loop, _fail_run, create_sync_run,
    sync_targets_for_user, upsert_killmail,
)


class AccountScopeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            user = User(email='owner@test.invalid', display_name='Owner', role='admin')
            other = User(email='other@test.invalid', display_name='Other', role='member')
            npc = EveCorporation(corporation_id=1000049, name='Pator Tech School')
            corp = EveCorporation(corporation_id=98000001, name='Player corporation')
            db.add_all([user, other, npc, corp])
            db.flush()
            self.user_id, self.other_id = user.id, other.id
            db.add_all([
                EveCharacter(character_id=90000001, name='Neutral alt', corporation_id=npc.id, owner_user_id=user.id),
                EveCharacter(character_id=90000002, name='Main', corporation_id=corp.id, owner_user_id=user.id),
                EveCharacter(character_id=90000003, name='Unrelated pilot', corporation_id=npc.id, owner_user_id=other.id),
                EveCharacter(character_id=90000004, name='Opted out', corporation_id=corp.id, owner_user_id=user.id, sync_opt_out=True),
            ])
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def test_personal_discovery_only_uses_owned_enabled_characters_at_every_role(self):
        with self.sessions() as db:
            user = db.get(User, self.user_id)
            for role in ('member', 'officer', 'director', 'admin', 'host'):
                with self.subTest(role=role):
                    user.role = role
                    run = create_sync_run(db, user, scope='account')
                    self.assertEqual(
                        {(t['owner_type'], t['owner_id']) for t in run.targets_json},
                        {('character', 90000001), ('character', 90000002)},
                    )
            # Changing a neutral's corporation must never widen account discovery.
            neutral = db.scalar(select(EveCharacter).where(EveCharacter.character_id == 90000001))
            neutral.corporation_id = db.scalar(select(EveCorporation.id).where(EveCorporation.corporation_id == 98000001))
            self.assertTrue(all(t['owner_type'] == 'character' for t in sync_targets_for_user(db, user)))

    def test_explicit_corporate_discovery_is_preserved(self):
        with self.sessions() as db:
            targets = sync_targets_for_user(db, db.get(User, self.user_id), scope='corporations')
            self.assertIn(('corporation', 98000001), {(t['owner_type'], t['owner_id']) for t in targets})

    def test_cached_corpmate_kills_do_not_count_but_neutral_alt_participation_does(self):
        with self.sessions() as db:
            for key, attacker, victim in ((1, 90000001, 99000000), (2, 90000003, 99000000), (3, 99000000, 90000001)):
                payload = {
                    'killmail_time': datetime.now(timezone.utc).isoformat(), 'solar_system_id': 30000142,
                    'victim': {'character_id': victim, 'corporation_id': 1000049, 'ship_type_id': 587, 'damage_taken': 100},
                    'attackers': [{'character_id': attacker, 'corporation_id': 1000049, 'damage_done': 100, 'final_blow': True}],
                }
                upsert_killmail(db, killmail_id=key, killmail_hash=str(key), esi_payload=payload,
                               zkill_payload={'zkb': {'totalValue': 100}}, owner_type='corporation', owner_id=1000049, feed='kills')
            db.commit()
            data = build_killboard_analytics(db, db.get(User, self.user_id), scope_type='account', days=30)
            self.assertEqual(data['summary']['kills'], 1)
            self.assertEqual(data['summary']['losses'], 1)
            self.assertEqual({row['killmail_id'] for row in data['recent']}, {1, 3})
            self.assertEqual(db.scalar(select(func.count()).select_from(Killmail)), 3)

    def test_admin_personal_status_never_selects_another_users_job(self):
        from app.api.killboard import latest_run
        with self.sessions() as db:
            own = create_sync_run(db, db.get(User, self.user_id))
            own.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
            other = create_sync_run(db, db.get(User, self.other_id))
            other.created_at = datetime.now(timezone.utc)
            db.commit()
            self.assertEqual(latest_run(db, db.get(User, self.user_id)).id, own.id)


class CancellationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            db.add(KillboardSyncRun(id='run', status='queued', targets_json=[
                {'owner_type': 'corporation', 'owner_id': 1000049, 'owner_name': 'Pator Tech School'},
            ], lookback_days=30))
            db.commit()
        self.session_patch = patch('app.services.killboard_sync.SessionLocal', self.sessions)
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()

    def cancel(self):
        with self.sessions() as db:
            db.get(KillboardSyncRun, 'run').status = 'cancelled'
            db.commit()

    async def test_cancelled_run_cannot_restart(self):
        self.cancel()
        discovery, canonical = AsyncMock(), AsyncMock()
        await _execute_sync_loop('run', discovery, canonical, 10)
        discovery.fetch_page.assert_not_called()
        canonical.get.assert_not_called()

    async def test_cancel_during_discovery_prevents_canonical_fetch(self):
        async def fetch(*args):
            self.cancel()
            return [{'killmail_id': 7, 'zkb': {'hash': 'abc'}}]
        discovery, canonical = AsyncMock(), AsyncMock()
        discovery.fetch_page.side_effect = fetch
        await _execute_sync_loop('run', discovery, canonical, 10)
        canonical.get.assert_not_called()

    async def test_cancel_during_canonical_fetch_prevents_import(self):
        async def fetch(*args):
            self.cancel()
            return {'killmail_time': datetime.now(timezone.utc).isoformat(), 'solar_system_id': 30000142,
                    'victim': {'ship_type_id': 587}, 'attackers': []}
        discovery, canonical = AsyncMock(), AsyncMock()
        discovery.fetch_page.return_value = [{'killmail_id': 7, 'zkb': {'hash': 'abc'}}]
        canonical.get.side_effect = fetch
        await _execute_sync_loop('run', discovery, canonical, 10)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Killmail)), 0)
            self.assertEqual(db.get(KillboardSyncRun, 'run').status, 'cancelled')

    async def test_inflight_failure_cannot_overwrite_cancellation(self):
        async def fetch(*args):
            self.cancel()
            raise RuntimeError('request failed after cancellation')
        discovery = AsyncMock()
        discovery.fetch_page.side_effect = fetch
        await _execute_sync_loop('run', discovery, AsyncMock(), 10)
        _advance_cursor('run', 0, 'kills', 1, page_complete=True)
        with self.sessions() as db:
            run = db.get(KillboardSyncRun, 'run')
            self.assertEqual(run.status, 'cancelled')
            self.assertEqual(run.failed_count, 0)
            self.assertEqual(run.feed, 'kills')
