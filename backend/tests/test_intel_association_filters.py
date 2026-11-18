from datetime import timedelta
import pytest
from app.domain.intel import summarize_evidence
from tests.test_intel_reports import AT, env, subject, collect, finish


def fact(kid,day,others):
    return {"id":kid,"time":AT+timedelta(days=day),"system_id":30000001,
            "victim":{"character_id":999},"attackers":[{"character_id":1},*({"character_id":i} for i in others)]}


def sample(facts,**options):
    return summarize_evidence('character',1,facts,AT-timedelta(days=1),AT+timedelta(days=10),**options)


def test_size_filter_keeps_totals_times_and_distinct_players():
    facts=[fact(1,0,[2,2]),fact(2,1,[2,3,4]),fact(3,2,[3])]
    full=sample(facts)
    filtered=sample(facts,association_max_attackers=2)
    assert filtered['kills']==full['kills']==3
    assert filtered['utc_hours']==full['utc_hours']
    assert filtered['timeline']==full['timeline']
    assert filtered['evidence']==full['evidence']
    assert {r['id']:r['kills'] for r in filtered['associates']}=={2:1,3:1}
    assert all(r['share_of_subject_kills_percent']==33.3 for r in filtered['associates'])


def test_day_filter_and_day_ranking_use_surviving_relationship_records():
    facts=[fact(1,0,[2]),fact(2,0,[2]),fact(3,0,[2]),fact(4,1,[3]),fact(5,2,[3])]
    assert sample(facts)['associates'][0]['id']==2
    assert sample(facts,association_sort='days')['associates'][0]['id']==3
    rows=sample(facts,association_min_days=2)['associates']
    assert len(rows)==1 and rows[0]['id']==3 and rows[0]['distinct_days']==2


def test_opponents_and_npc_only_records_never_become_associates():
    npc={**fact(1,0,[2]),'npc_only':True}
    loss={**fact(2,1,[2]),'victim':{'character_id':1},'attackers':[{'character_id':3}]}
    result=sample([npc,loss],association_max_attackers=5)
    assert result['associates']==[] and result['kills']==0 and result['losses']==1


def test_api_filters_return_applied_scope_without_changing_kills(env):
    s=subject(env);finish(env,collect(env,s['id']))
    default=env.client.get(f"/intel/subjects/{s['id']}/report").json()
    filtered=env.client.get(f"/intel/subjects/{s['id']}/report",params={'association_max_attackers':2,'association_min_days':2,'association_sort':'days'})
    assert filtered.status_code==200
    data=filtered.json()
    assert data['association_filters']=={'max_attackers':2,'min_days':2,'sort':'days'}
    assert data['summary']['associates']==[] and data['total_associates']==0
    assert data['summary']['kills']==default['summary']['kills']==2
    assert data['summary']['utc_hours']==default['summary']['utc_hours']


@pytest.mark.parametrize('params',[{'association_max_attackers':0},{'association_max_attackers':10001},{'association_min_days':0},{'association_sort':'invalid'}])
def test_invalid_association_filters_rejected(env,params):
    s=subject(env)
    assert env.client.get(f"/intel/subjects/{s['id']}/report",params=params).status_code==422
