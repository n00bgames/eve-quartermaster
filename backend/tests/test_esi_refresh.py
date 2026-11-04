import asyncio
import threading
import time
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,inspect,select
from sqlalchemy.orm import Session

from app.core.security import generate_key,encrypt_secret,decrypt_secret
from app.models import Base,EsiToken,EveCharacter,User,RoleDefinition,RoleSectionPermission,UserRoleAssignment,UserSectionPermission,AppSetting,RecruitmentUserCapability
from app.services import esi_refresh as service


@pytest.fixture
def linked(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+(tmp_path/'refresh.sqlite').as_posix())
    tables={m.__table__ for m in [EsiToken,EveCharacter,User,RoleDefinition,RoleSectionPermission,UserRoleAssignment,UserSectionPermission,AppSetting,RecruitmentUserCapability]}
    while True:
        parents={fk.column.table for table in tables for fk in table.foreign_keys}
        if parents.issubset(tables):break
        tables|=parents
    Base.metadata.create_all(engine,tables=list(tables))
    key=generate_key()
    monkeypatch.setattr(service,'get_settings',lambda:SimpleNamespace(token_encryption_key=key,eve_sso_client_id='demo',eve_sso_client_secret='synthetic'))
    with Session(engine,expire_on_commit=False) as db:
        user=User(email='refresh@test.invalid',display_name='Original',role='member');db.add(user);db.flush()
        character=EveCharacter(character_id=9001,name='Synthetic',owner_user_id=user.id);db.add(character);db.flush()
        token=EsiToken(user_id=user.id,character_id=character.id,scopes='esi-assets.read_assets.v1',encrypted_refresh_token=encrypt_secret('old',key));db.add(token);db.commit()
        db.execute(select(EsiToken.id)).scalar_one()
        yield SimpleNamespace(db=db,engine=engine,user=user,token=token,key=key)
    engine.dispose()


def upstream(payload=None,status=200,hook=None):
    async def post(*args,**kwargs):
        if hook:await hook(kwargs)
        return httpx.Response(status,json=payload or {'access_token':'demo-access','refresh_token':'rotated','expires_in':1200})
    context=AsyncMock();context.__aenter__.return_value=SimpleNamespace(post=AsyncMock(side_effect=post))
    return patch.object(service.httpx,'AsyncClient',return_value=context)


def test_rotation_is_durable_without_committing_the_callers_pending_work(linked):
    e=linked;e.user.display_name='Uncommitted edit'
    async def check(kwargs):
        with Session(e.engine) as other:assert other.get(User,e.user.id).display_name=='Original'
        assert e.engine.pool.checkedout()==1  # Only the caller; no OAuth-spanning helper connection.
        assert kwargs['data']['scope']=='esi-assets.read_assets.v1'
    with upstream(hook=check):assert asyncio.run(service.refresh_access_token(e.token))=='demo-access'
    assert not inspect(e.token).attrs.encrypted_refresh_token.history.has_changes()
    e.db.rollback()
    with Session(e.engine) as other:
        assert decrypt_secret(other.get(EsiToken,e.token.id).encrypted_refresh_token,e.key)=='rotated'
        assert other.get(User,e.user.id).display_name=='Original'


@pytest.mark.parametrize('change',['credential','revoke','owner','delete','permission','character_transfer'])
def test_changes_during_sso_are_not_overwritten_or_revived(linked,change):
    e=linked;token_id=e.token.id;user_id=e.user.id
    async def mutate(_):
        with Session(e.engine) as other:
            token=other.get(EsiToken,token_id)
            if change=='credential':token.encrypted_refresh_token=encrypt_secret('newer',e.key)
            elif change=='revoke':token.revoked_at=datetime.now(timezone.utc)
            elif change=='delete':other.delete(token)
            elif change=='owner':
                user=User(email='new@test.invalid',display_name='New',role='member');other.add(user);other.flush();token.user_id=user.id
            elif change=='character_transfer':other.get(EveCharacter,token.character_id).owner_user_id=None
            else:other.get(User,user_id).role='intel_analyst'
            other.commit()
    with upstream(hook=mutate),pytest.raises(HTTPException) as error:asyncio.run(service.refresh_access_token(e.token))
    assert error.value.status_code==(403 if change=='permission' else 409)
    with Session(e.engine) as other:
        token=other.get(EsiToken,token_id)
        if change=='credential':assert decrypt_secret(token.encrypted_refresh_token,e.key)=='newer'
        elif change=='revoke':assert token.revoked_at is not None
        elif change=='delete':assert token is None
        elif change=='owner':assert token.user_id!=user_id


def test_slow_database_work_does_not_stop_the_api_event_loop(linked,monkeypatch):
    e=linked;original=service.persist;loop_thread=threading.get_ident();threads=[]
    def slow(*args):
        threads.append(threading.get_ident());time.sleep(.12);original(*args)
    monkeypatch.setattr(service,'persist',slow)
    async def run():
        task=asyncio.create_task(service.refresh_access_token(e.token));ticks=0
        while not task.done():await asyncio.sleep(.01);ticks+=1
        assert await task=='demo-access';assert ticks>=6
    with upstream():asyncio.run(run())
    assert threads and all(t!=loop_thread for t in threads)


@pytest.mark.parametrize('payload,status',[({'error':'credential-must-not-leak'},400),({'expires_in':1200},200),({'access_token':''},200)])
def test_sso_failure_or_invalid_response_does_not_leak_or_save_payload(linked,payload,status):
    e=linked;before=e.token.encrypted_refresh_token
    with upstream(payload,status),pytest.raises(HTTPException) as error:asyncio.run(service.refresh_access_token(e.token))
    assert error.value.status_code==(400 if status==400 else 502)
    assert 'credential-must-not-leak' not in str(error.value.detail)
    with Session(e.engine) as other:assert other.get(EsiToken,e.token.id).encrypted_refresh_token==before


def test_expiry_only_refresh_remains_clean_and_detached_tokens_are_rejected(linked):
    e=linked;before=e.token.encrypted_refresh_token
    with upstream({'access_token':'demo-access'}):assert asyncio.run(service.refresh_access_token(e.token))=='demo-access'
    assert e.token.encrypted_refresh_token==before and e.token.access_token_expires_at
    e.db.expunge(e.token)
    with pytest.raises(HTTPException) as error:asyncio.run(service.refresh_access_token(e.token))
    assert error.value.status_code==409
