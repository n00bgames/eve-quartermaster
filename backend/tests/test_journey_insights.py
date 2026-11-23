"""Aggregate truth, private cohorts, and server-side public exclusion boundaries."""
import json
from datetime import timedelta
import pytest
from sqlalchemy import select
from app.api import journey_insights as api
from app.models import EveCategory, EveGroup, EveType, UserSectionPermission
from app.models.journey import JourneyShipSegment
from app.models.journey_views import JourneyAnalyticsView
from .test_journey_analytics import env, visit, mail, seed, AT

BASE = '/api/journey/insights'


@pytest.fixture
def e(env):
    env.client.app.include_router(api.router, prefix='/api')
    env.client.app.include_router(api.public_router, prefix='/api')
    env.db.add(EveCategory(category_id=6, name='Ship'))
    env.db.add_all([EveGroup(group_id=25, category_id=6, name='Frigate'),
        EveGroup(group_id=485, category_id=6, name='Dreadnought'), EveGroup(group_id=30, category_id=6, name='Titan')])
    env.db.flush()
    env.db.get(EveType, 111).group_id = 25
    env.db.get(EveType, 222).group_id = 485
    env.db.add(EveType(type_id=333, group_id=30, name='Demo Titan'))
    env.db.commit()
    return env


def query(e, **changes):
    response = e.client.post(BASE + '/query', json={'period':'all', **changes})
    assert response.status_code == 200, response.text
    return response.json()


def save(e, **scope):
    response = e.client.post(BASE + '/views', json={'title':'Demo shared fleet', 'scope':{'period':'all', **scope}})
    assert response.status_code == 201, response.text
    return response.json()


def publish(e, saved):
    response = e.client.patch(BASE + f"/views/{saved['id']}", json={'is_public':True, 'preview_hash':saved['preview_hash']})
    assert response.status_code == 200, response.text
    return response.json()['share_path'].split('/')[-1]


def test_whole_scope_and_combat_only_hull(e):
    seed(e)
    mail(e, 120, victim=999, attackers=((0,333),))
    mail(e, 121, victim=999, attackers=((0,111),(0,None)))
    e.db.commit()
    data = query(e)
    assert data['summary']['visits'] == 6
    assert data['summary']['kills'] == 5
    assert data['summary']['seconds'] == 7620
    assert next(r for r in data['hulls']['rows'] if r['id'] == 333)['kills'] == 1
    assert next(r for r in data['hulls']['rows'] if r['id'] is None)['kills'] == 1
    filtered = query(e, ship_type_id=111)
    assert filtered['summary']['visits'] == 3 and filtered['summary']['seconds'] == 4740
    assert filtered['summary']['kills'] == 2
    assert {r['id'] for r in filtered['hulls']['rows']} == {111}


def test_mid_visit_hulls_and_clipped_observation_spans(e):
    v = visit(e, 0, 10, 0, length=60)
    for hull, start, end in ((111,0,15),(222,20,40),(111,50,60)):
        e.db.add(JourneyShipSegment(visit_id=v.id, ship_type_id=hull, first_seen_at=AT+timedelta(minutes=start),
            last_seen_at=AT+timedelta(minutes=end), samples=2))
    e.db.commit()
    data = query(e, ship_type_id=111, period='range', from_at='2026-11-08T12:10:00Z', to_at='2026-11-08T12:55:00Z')
    assert data['summary']['seconds'] == 600 and data['summary']['visits'] == 1
    assert data['summary']['segments'] == 2
    assert data['systems']['rows'][0]['seconds'] == 600


def test_selected_and_current_fleet_are_distinct_from_account(e):
    seed(e); e.trackers[0].enabled = True; e.db.commit()
    assert query(e, cohort='fleet')['summary']['visits'] == 4
    assert query(e, cohort='selected', character_ids=[e.chars[1].id])['summary']['visits'] == 2
    assert len(query(e)['cohort']) == 2
    for ids in ([e.chars[2].id], [999999]):
        assert e.client.post(BASE+'/query', json={'cohort':'selected', 'character_ids':ids}).status_code == 404
    assert e.client.post(BASE+'/query', json={'cohort':'selected'}).status_code == 422


@pytest.mark.parametrize('exclusions', [{'exclude_capitals':True}, {'exclude_types':[222]}, {'exclude_groups':[485]}])
def test_public_exclusions_precede_every_total_and_export(e, exclusions):
    seed(e)
    visit(e, 0, 8888, 200, hull=987654)
    mail(e, 123, victim=999, system=8888, attackers=((0,987654),))
    # Included participant keeps this shared kill, without the blocked participant.
    mail(e, 124, victim=999, system=10, attackers=((0,222),(1,111)))
    e.db.commit()
    saved = save(e, **exclusions, show_systems=True, show_pilots=True)
    assert not saved['is_public'] and saved['share_path'] is None
    report = saved['report']
    assert report['summary']['visits'] == 3 and report['summary']['seconds'] == 4740
    assert report['summary']['kills'] == 3 and report['summary']['losses'] == 1
    assert {r['name'] for r in report['hulls']['rows']} == {'Demo Scout'}
    assert not any(r['name'] == 'Unknown' for r in report['systems']['rows'])
    token = publish(e, saved)
    public = e.client.get('/api/journey-views/'+token)
    assert public.status_code == 200 and 'no-store' in public.headers['cache-control']
    assert public.json()['report'] == report
    raw = public.text
    for forbidden in ('eve_id', 'pilot_id', 'character_ids', 'first_at', 'last_at', 'mail_id', 'exclude_groups', 'Demo Cruiser'):
        assert forbidden not in raw
    for fmt in ('csv', 'json'):
        exported = e.client.get(f'/api/journey-views/{token}/export/{fmt}')
        assert exported.status_code == 200 and 'Demo Cruiser' not in exported.text and '987654' not in exported.text
    assert e.client.get('/api/journey-views/'+token+'?exclude_types=').status_code == 400


def test_private_by_default_preview_gate_and_revocation(e):
    seed(e); saved = save(e)
    row = e.db.get(JourneyAnalyticsView, saved['id'])
    assert e.client.get('/api/journey-views/'+row.token).status_code == 404
    assert 'systems' not in saved['report'] and 'pilots' not in saved['report']
    assert e.client.patch(BASE+f"/views/{row.id}", json={'is_public':True}).status_code == 409
    assert e.client.patch(BASE+f"/views/{row.id}", json={'is_public':True,'preview_hash':'invalid'}).status_code == 422
    token = publish(e, saved)
    assert e.client.get('/api/journey-views/'+token).status_code == 200
    rotated = e.client.patch(BASE+f"/views/{row.id}", json={'rotate':True}).json()
    new = rotated['share_path'].split('/')[-1]
    assert token != new and e.client.get('/api/journey-views/'+token).status_code == 404
    assert e.client.get('/api/journey-views/'+new).status_code == 200
    e.client.patch(BASE+f"/views/{row.id}", json={'is_public':False})
    assert e.client.get('/api/journey-views/'+new).status_code == 404
    assert e.client.get(f'/api/journey-views/{new}/export/json').status_code == 404


def test_transfer_and_permission_loss_disable_published_snapshot(e):
    seed(e); saved = save(e); token = publish(e, saved)
    e.actor[0] = e.users[1]
    assert e.client.get(BASE+f"/views/{saved['id']}").status_code == 404
    assert e.client.delete(BASE+f"/views/{saved['id']}").status_code == 404
    e.actor[0] = e.users[0]
    e.chars[0].owner_user_id = e.users[1].id; e.db.commit()
    assert e.client.get('/api/journey-views/'+token).status_code == 404
    e.chars[0].owner_user_id = e.users[0].id
    e.db.add_all([UserSectionPermission(user_id=e.users[0].id, section=s, can_view=False)
        for s in ('killboard','intel_reports','battle_reports')]); e.db.commit()
    assert e.client.get('/api/journey-views/'+token).status_code == 404
    assert query(e)['summary']['kills'] is None


def test_expiry_deletion_and_private_export_all_groups(e):
    seed(e)
    response = e.client.post(BASE+'/export/json', json={'period':'all', 'limit':1})
    assert response.status_code == 200, response.text
    assert len(response.json()['report']['hulls']['rows']) == 2
    saved = save(e); token = publish(e, saved)
    e.db.get(JourneyAnalyticsView, saved['id']).expires_at = AT; e.db.commit()
    assert e.client.get('/api/journey-views/'+token).status_code == 404
    assert e.client.delete(BASE+f"/views/{saved['id']}").status_code == 200
    assert e.db.get(JourneyAnalyticsView, saved['id']) is None


def test_public_union_exclusions_and_new_types_cannot_bypass_class_filter(e):
    seed(e)
    e.db.add(EveType(type_id=555, group_id=485, name='Future Dreadnought')); e.db.flush()
    visit(e, 0, 9999, 300, hull=555); e.db.commit()
    saved = save(e, exclude_types=[111], exclude_capitals=True, show_systems=True, show_pilots=True)
    assert saved['report']['summary'] == dict(visits=0, systems=0, segments=0, seconds=0, kills=0, losses=0)
    assert all(saved['report'][k]['rows'] == [] for k in ('hulls','systems','pilots'))
    assert 'Future Dreadnought' not in json.dumps(saved['report'])


def test_supercapital_preset_preserves_ordinary_capitals(e):
    seed(e); mail(e, 120, victim=999, attackers=((0,333),)); e.db.commit()
    saved = save(e, exclude_supercapitals=True)
    assert {r['name'] for r in saved['report']['hulls']['rows']} == {'Demo Scout','Demo Cruiser'}
    assert saved['report']['summary']['kills'] == 3


def test_anonymous_access_and_deleted_owner(e):
    seed(e); saved = save(e); token = publish(e, saved)
    e.actor[0] = None
    assert e.client.get('/api/journey-views/'+token).status_code == 200
    assert e.client.get(BASE+'/views').status_code == 401
    e.users[0].deleted_at = AT; e.db.commit()
    unavailable = e.client.get('/api/journey-views/'+token)
    assert unavailable.status_code == 404 and unavailable.headers['cache-control'] == 'no-store'


def test_inputs_options_search_and_csv_formula_protection(e):
    seed(e)
    result = e.client.get(BASE+'/options?search=Scout')
    assert result.status_code == 200, result.text
    assert result.json()['types'] == [{'type_id':111, 'name':'Demo Scout'}]
    assert e.client.get(BASE+'/options?search=%25').json()['types'] == []
    for spec in ({'limit':51},{'cohort':'account','character_ids':[1]},{'exclude_types':[-1]},
        {'metric':'invalid'},{'period':'range','from_at':'2026-11-09T00:00:00Z','to_at':'2026-11-08T00:00:00Z'}):
        assert e.client.post(BASE+'/query', json=spec).status_code == 422
    assert e.client.post(BASE+'/views', json={'scope':{},'is_public':True}).status_code == 422
    e.chars[0].name = '=DEMO()'; e.db.commit()
    csv = e.client.post(BASE+'/export/csv', json={})
    assert csv.status_code == 200 and "'=DEMO()" in csv.text
    assert 'scope_json' in csv.text and 'coverage' in csv.text


def test_public_mid_visit_filter_cannot_include_blocked_span(e):
    v = visit(e,0,10,0,length=60)
    for hull,start,end in ((111,0,15),(222,20,40),(111,50,60)):
        e.db.add(JourneyShipSegment(visit_id=v.id,ship_type_id=hull,first_seen_at=AT+timedelta(minutes=start),
            last_seen_at=AT+timedelta(minutes=end),samples=2))
    e.db.commit()
    saved = save(e, exclude_capitals=True, period='range', from_at='2026-11-08T12:10:00Z',to_at='2026-11-08T12:55:00Z')
    assert saved['report']['summary']['seconds'] == 600
    assert saved['report']['summary']['segments'] == 2


def test_snapshot_migration_upgrade_and_downgrade():
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, inspect, text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1]/'alembic/versions/0112_journey_analytics_views.py'
    spec = importlib.util.spec_from_file_location('journey_views_migration',path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
            assert 'journey_analytics_views' in inspect(conn).get_table_names()
            module.downgrade()
            assert 'journey_analytics_views' not in inspect(conn).get_table_names()
    engine.dispose()


def test_insights_and_snapshot_totals_exceed_replay_limits(e):
    for index in range(2010):
        v = visit(e,0,10 if index%2 else 11,index/100,length=0)
        e.db.add_all([JourneyShipSegment(visit_id=v.id,ship_type_id=111,first_seen_at=v.first_seen_at,
            last_seen_at=v.last_seen_at,samples=1) for _ in range(3)])
    e.db.commit()
    data = query(e,limit=1)
    assert data['summary']['visits'] == 2010 and data['summary']['segments'] == 6030
    assert data['summary']['seconds'] == 0 and data['systems']['total'] == 2
    saved = save(e,limit=1,show_systems=True)
    assert saved['report']['summary'] == data['summary']
    assert saved['report']['systems']['truncated'] and len(saved['report']['systems']['rows']) == 1
