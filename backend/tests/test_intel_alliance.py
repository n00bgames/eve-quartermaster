import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
import pytest
from sqlalchemy import select, func, update
from app.api import intel_alliance
from app.models import EveCharacter, User
from app.models.intel import IntelSubject, IntelCollection, IntelSourceCache
from app.models.intel_membership import IntelMembershipMonitor, IntelMembershipSnapshot
from app.services.intel_membership_source import MembershipSource
from app.services.intel_membership import write_census, now
from app.services.intel_alliance_cache import profile_key, stats_key, roster_key
from app.services import intel_alliance_details
from .test_intel_reports import env, subject, collect, finish


def census(complete=True):
    return {"member_count":530 if complete else None,"corporation_count":2,"resolved_corporations":2 if complete else 1,
            "known_member_count":530 if complete else 500,"corporations":[
        {"eve_id":8002,"name":"Demo Foundry","member_count":500,"state":"available","ceo_name":"Demo CEO","creator_name":"Demo Founder",
         "profile":{"name":"Demo Foundry","ticker":"DEMO","description":"A public industrial corporation.","ceo_id":9008,"creator_id":9009,"member_count":500,"alliance_id":7001}},
        {"eve_id":8003,"name":"Demo Scouts","member_count":30 if complete else None,"state":"available" if complete else "unavailable"}]}


def seed(env,payload=None):
    env.app.include_router(intel_alliance.router)
    s=subject(env,'alliance',7001)
    write_census(env.db,s['id'],payload or census(),now());env.db.commit()
    return s['id']


def test_scrape_census_runs_even_with_fresh_alliance_profile_and_records_no_monitor(env):
    s=subject(env,'alliance',7001)
    calls=[]
    async def membership(kind,eid):
        calls.append((kind,eid));return census()
    env.source.membership=membership
    # Existing subject has a freshly cached ESI profile; census is still mandatory.
    job=collect(env,s['id']);done=finish(env,job)
    assert calls==[('alliance',7001)] and done['status']=='completed'
    assert done['coverage']['membership']['resolved']==2
    row=env.db.scalar(select(IntelMembershipSnapshot))
    assert row.member_count==530 and row.corporation_count==2
    assert 'profile' not in row.corporations[0] and 'description' not in row.corporations[0]
    assert env.db.get(IntelMembershipMonitor,s['id']) is None
    assert env.db.get(IntelSourceCache,roster_key(7001)).payload['rows'][0]['ceo_name']=='Demo CEO'
    assert env.db.get(IntelSubject,s['id']).public_data['esi']['data']['corporation_ids']==[8002,8003]


@pytest.mark.parametrize('unavailable',[False,True])
def test_partial_census_keeps_complete_total_and_continues_kill_collection(env,unavailable):
    sid=seed(env)
    async def membership(kind,eid):
        if unavailable:raise RuntimeError('fixture upstream unavailable')
        return census(False)
    env.source.membership=membership
    done=finish(env,collect(env,sid))
    assert done['status']=='partial' and done['imported_count']==3
    assert done['coverage']['membership']['status']==('unavailable' if unavailable else 'partial')
    assert env.db.scalar(select(IntelMembershipSnapshot)).member_count==530
    if not unavailable:
        assert env.db.get(IntelSourceCache,roster_key(7001)).payload['member_count'] is None


def test_cancel_during_census_discards_results(env):
    sid=subject(env,'alliance',7001)['id'];job=collect(env,sid)
    async def membership(kind,eid):
        with env.factory() as db:
            db.execute(update(IntelCollection).where(IntelCollection.id==job['id']).values(status='cancelled',lease_token=None));db.commit()
        return census()
    env.source.membership=membership
    done=finish(env,job)
    assert done['status']=='cancelled'
    assert env.db.scalar(select(func.count()).select_from(IntelMembershipSnapshot))==0


def test_roster_pagination_search_largest_sort_and_legacy_unknown(env):
    sid=seed(env)
    path=f'/intel/subjects/{sid}/corporations'
    r=env.client.get(path);assert r.status_code==200 and r.headers['cache-control']=='private, no-store'
    assert [c['eve_id'] for c in r.json()['rows']]==[8002,8003]
    assert env.client.get(path+'?search=demo%20ceo').json()['total']==1
    assert env.client.get(path+'?search=DEMO&sort=name').json()['rows'][0]['name']=='Demo Foundry'
    payload=census();payload['corporations']=[{'eve_id':8100+i,'name':f'Corporation {i:03}','member_count':i} for i in range(113)]
    write_census(env.db,sid,payload,now());env.db.commit()
    assert len(env.client.get(path).json()['rows'])==50
    assert len(env.client.get(path+'?page=3').json()['rows'])==13
    assert env.client.get(path+'?sort=invalid').status_code==422
    env.db.delete(env.db.get(IntelSourceCache,roster_key(7001)))
    row=env.db.get(IntelSubject,sid);row.public_data={'esi':{'data':{'corporation_ids':[8002],'corporations':[{'id':8002,'name':'Legacy Corp'}]}}};env.db.commit()
    legacy=env.client.get(path).json()
    assert legacy['rows'][0]['name']=='Legacy Corp' and legacy['rows'][0]['member_count'] is None and legacy['stale']


class DetailsSource:
    def __init__(self,env):self.env=env;self.calls=[];self.fail=False;self.hook=None;self.closed=False
    def check(self):
        assert not self.env.db.in_transaction(), 'Database transaction held during upstream I/O'
        if self.hook:self.hook();self.hook=None
        if self.fail:raise RuntimeError('fixture source failure')
    async def profile(self,kind,eid):
        self.check();self.calls.append('esi')
        return {'name':'Demo Foundry','ticker':'DEMO','ceo_id':9008,'creator_id':9009,'member_count':501,'alliance_id':7001,
                'description':'<b>Public</b> profile','shares':9223372036854775807,'tax_rate':.05,'url':'https://example.invalid',
                'war_eligible':True,'date_founded':'2020-01-01T00:00:00Z','home_station_id':60003760,
                'history':[{'alliance_id':7001,'start_date':'2021-01-01T00:00:00Z'}],'wallet':'PRIVATE SENTINEL','source_errors':[]}
    async def names(self,ids):
        self.check();return [{'id':9008,'name':'Demo CEO','category':'character'},{'id':9009,'name':'Demo Founder','category':'character'},{'id':7001,'name':'Demo Alliance','category':'alliance'},{'id':60003760,'name':'Demo Station','category':'station'}]
    async def stats(self,kind,eid):
        self.check();self.calls.append('zkill');return {'totals':{'shipsDestroyed':45,'shipsLost':7},'wallet':'PRIVATE SENTINEL'}
    async def close(self):self.closed=True


def test_expansion_public_details_lazy_cache_and_cooldown(env):
    sid=seed(env);source=DetailsSource(env);path=f'/intel/subjects/{sid}/corporations/8002'
    with patch.object(intel_alliance_details,'source_factory',return_value=source):
        r=env.client.get(path);assert r.status_code==200,r.text
        data=r.json();assert source.calls==['esi','zkill'] and source.closed
        assert data['esi']['ceo_name']=='Demo CEO' and data['esi']['creator_name']=='Demo Founder'
        assert data['esi']['entity_names']['60003760']=='Demo Station' and data['esi']['entity_names']['7001']=='Demo Alliance'
        assert data['esi']['data']['description']=='Public profile'
        assert data['esi']['data']['shares']=='9223372036854775807'
        assert 'PRIVATE SENTINEL' not in r.text
        assert data['zkill']['data']['totals']['shipsDestroyed']==45
        assert env.client.get(path).status_code==200 and source.calls==['esi','zkill']
        assert env.client.post(path+'/refresh').status_code==429
    assert env.db.scalar(select(func.count()).select_from(EveCharacter))==0
    assert env.db.scalar(select(func.count()).select_from(IntelSubject))==1


def test_failed_expansion_retains_counters_and_marks_stale(env):
    sid=seed(env);source=DetailsSource(env);path=f'/intel/subjects/{sid}/corporations/8002'
    with patch.object(intel_alliance_details,'source_factory',return_value=source):
        assert env.client.get(path).status_code==200
        for key in (profile_key(8002),stats_key(8002)):
            row=env.db.get(IntelSourceCache,key);row.expires_at=now()-timedelta(seconds=1)
            row.payload={**row.payload,'last_attempt_at':(now()-timedelta(minutes=2)).isoformat()}
        env.db.commit();source.fail=True
        r=env.client.get(path);assert r.status_code==200
        assert r.json()['zkill']['state']=='unavailable' and r.json()['zkill']['stale']
        assert r.json()['zkill']['data']['totals']['shipsDestroyed']==45


def test_details_require_authorized_user_and_latest_roster_membership(env):
    sid=seed(env);source=DetailsSource(env);path=f'/intel/subjects/{sid}/corporations/'
    with patch.object(intel_alliance_details,'source_factory',return_value=source):
        assert env.client.get(path+'999999').status_code==404 and not source.calls
        env.current[0]=env.users[3]
        assert env.client.get(path+'8002').status_code==403
        assert env.client.get(f'/intel/subjects/{sid}/corporations').status_code==403
        env.current[0]=None
        assert env.client.get(path+'8002').status_code==401


@pytest.mark.parametrize('change',['roster','access'])
def test_membership_and_access_rechecked_after_network_before_cache_write(env,change):
    sid=seed(env);source=DetailsSource(env);path=f'/intel/subjects/{sid}/corporations/8002'
    def hook():
        with env.factory() as db:
            if change=='roster':
                row=db.get(IntelSourceCache,roster_key(7001));row.payload={**row.payload,'rows':[]}
            else:
                row=db.get(User,env.users[0].id);row.role='member'
            db.commit()
    source.hook=hook
    with patch.object(intel_alliance_details,'source_factory',return_value=source):
        assert env.client.get(path).status_code==(404 if change=='roster' else 403)
    assert env.db.get(IntelSourceCache,stats_key(8002)) is None


def test_census_enrichment_uses_public_fields_names_and_handles_moves():
    class Client:
        async def get(self,path):
            if '/alliances/' in path:return [8002,8003]
            cid=int(path.split('/')[2])
            return {'name':'<b>Foundry</b>','member_count':50,'alliance_id':7001 if cid==8002 else 7002,
                    'ceo_id':9008,'creator_id':9009,'description':'<a>Welcome</a>','wallet':'PRIVATE SENTINEL'}
        async def post(self,path,ids):return [{'id':9008,'name':'CEO','category':'character'}]
    result=asyncio.run(MembershipSource(client=Client()).census('alliance',7001))
    assert result['member_count'] is None and result['known_member_count']==50
    assert result['corporations'][0]['ceo_name']=='CEO'
    assert result['corporations'][0]['profile']['description']=='Welcome'
    assert result['corporations'][1]['state']=='affiliation_changed'
    assert 'PRIVATE SENTINEL' not in str(result)


def test_census_name_failure_does_not_invalidate_count():
    class Client:
        async def get(self,path):
            return [8002] if '/alliances/' in path else {'name':'Foundry','member_count':50,'alliance_id':7001,'ceo_id':9008}
        async def post(self,path,ids):raise RuntimeError('names unavailable')
    result=asyncio.run(MembershipSource(client=Client()).census('alliance',7001))
    assert result['member_count']==50 and result['corporations'][0]['ceo_name'] is None
