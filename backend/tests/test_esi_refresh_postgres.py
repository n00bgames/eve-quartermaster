"""Opt-in regression against a disposable, isolated PostgreSQL database only."""
import asyncio
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import httpx
from fastapi import HTTPException
from sqlalchemy import create_engine,select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.security import generate_key,encrypt_secret,decrypt_secret
from app.models import Base,EsiToken,EsiSyncJob,EveCharacter,User,RoleDefinition,RoleSectionPermission,UserRoleAssignment,UserSectionPermission,AppSetting,RecruitmentUserCapability
from app.services import esi_refresh as service


@unittest.skipUnless(os.getenv('EQM_REFRESH_TEST_DATABASE_URL'),'requires disposable PostgreSQL test database')
class RefreshPostgresTests(unittest.TestCase):
    def setUp(self):
        url=os.environ['EQM_REFRESH_TEST_DATABASE_URL'];parsed=make_url(url)
        assert parsed.database=='eqm_refresh_test' and parsed.host in {'127.0.0.1','localhost'},'Refuse a non-isolated test target'
        self.engine=create_engine(url,pool_size=5,max_overflow=2,connect_args={'connect_timeout':3})
        self.tables={m.__table__ for m in [EsiToken,EsiSyncJob,EveCharacter,User,RoleDefinition,RoleSectionPermission,UserRoleAssignment,UserSectionPermission,AppSetting,RecruitmentUserCapability]}
        while True:
            parents={fk.column.table for t in self.tables for fk in t.foreign_keys}
            if parents.issubset(self.tables):break
            self.tables|=parents
        Base.metadata.create_all(self.engine,tables=list(self.tables))
        self.key=generate_key();self.db=Session(self.engine,expire_on_commit=False)
        user=User(email='postgres-regression@test.invalid',display_name='Synthetic',role='member');self.db.add(user);self.db.flush()
        character=EveCharacter(character_id=90001,name='Synthetic',owner_user_id=user.id);self.db.add(character);self.db.flush()
        self.token=EsiToken(user_id=user.id,character_id=character.id,scopes='esi-assets.read_assets.v1',encrypted_refresh_token=encrypt_secret('original',self.key));self.db.add(self.token);self.db.commit()
        settings=SimpleNamespace(token_encryption_key=self.key,eve_sso_client_id='synthetic',eve_sso_client_secret='synthetic')
        self.settings=patch.object(service,'get_settings',return_value=settings);self.settings.start()

    def tearDown(self):
        self.settings.stop();self.db.close();Base.metadata.drop_all(self.engine,tables=list(self.tables));self.engine.dispose()

    def http(self):
        context=AsyncMock();context.__aenter__.return_value=SimpleNamespace(post=AsyncMock(return_value=httpx.Response(200,json={'access_token':'demo','refresh_token':'rotated'})))
        return patch.object(service.httpx,'AsyncClient',return_value=context)

    def test_legacy_flushed_rotation_reproduces_the_live_row_lock(self):
        self.token.encrypted_refresh_token=encrypt_secret('legacy-pending',self.key);self.db.flush()
        with Session(self.engine) as other,self.assertRaises(DBAPIError) as error:
            other.scalar(select(EsiToken).where(EsiToken.id==self.token.id).with_for_update(nowait=True,key_share=True))
        self.assertEqual(error.exception.orig.sqlstate,'55P03');self.db.rollback()

    def test_rotation_releases_row_while_callers_uncommitted_sync_job_stays_open(self):
        job=EsiSyncJob(token_id=self.token.id,sync_type='character_assets');self.db.add(job);self.db.flush();job_id=job.id;token_id=self.token.id
        with self.http():self.assertEqual(asyncio.run(service.refresh_access_token(self.token)),'demo')
        with Session(self.engine) as other:
            row=other.scalar(select(EsiToken).where(EsiToken.id==token_id).with_for_update(nowait=True,key_share=True))
            self.assertEqual(decrypt_secret(row.encrypted_refresh_token,self.key),'rotated')
            self.assertIsNone(other.get(EsiSyncJob,job_id));row.access_token_expires_at=None;other.commit()
        self.db.rollback()
        with Session(self.engine) as other:
            self.assertIsNone(other.get(EsiSyncJob,job_id));self.assertEqual(decrypt_secret(other.get(EsiToken,token_id).encrypted_refresh_token,self.key),'rotated')

    def test_a_busy_row_returns_safe_503_without_blocking_the_event_loop(self):
        with Session(self.engine) as locker:
            locker.scalar(select(EsiToken).where(EsiToken.id==self.token.id).with_for_update())
            async def run():
                task=asyncio.create_task(service.refresh_access_token(self.token));ticks=0;started=time.monotonic()
                while not task.done():await asyncio.sleep(.001);ticks+=1
                with self.assertRaises(HTTPException) as error:await task
                self.assertEqual(error.exception.status_code,503);self.assertEqual(error.exception.headers,{'Retry-After':'5'})
                self.assertNotIn('UPDATE',str(error.exception.detail));self.assertLess(time.monotonic()-started,2);self.assertGreater(ticks,0)
            with self.http():asyncio.run(run())


if __name__=='__main__':unittest.main()
