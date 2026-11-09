from datetime import timedelta
from pathlib import Path
from uuid import uuid4
import importlib.util
from unittest.mock import patch

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, func, inspect, select, text

from app.api import character_notes, intel
from app.models import AuditEvent, User, UserSectionPermission
from app.models.intel import IntelNote, IntelScanNoteBatch, IntelSubject
from app.models.local_scan import LocalScanReport
from app.services import character_notes as service, local_scan
from .test_local_scan import env, create


@pytest.fixture
def scans(env):
    env.app.include_router(intel.router,prefix='/api')
    env.app.include_router(character_notes.router,prefix='/api')
    env.current[0]=env.users['intel_analyst']
    return env


def report(e,private=False):return create(e,'intel_analyst',is_private=private)
def endpoint(r):return f'/api/local-scans/reports/{r["token"]}/notes'
def post(e,r,body='Suspected multiboxer · mining crew A',private=True,request_id=None):
    return e.client.post(endpoint(r),json={'body':body,'is_private':private,'request_id':request_id or str(uuid4())})
def search(e,q,**extra):
    r=e.client.get('/api/intel/notes/search',params={'q':q,**extra});assert r.status_code==200,r.text
    assert r.headers['cache-control']=='private, no-store';return r.json()
def count(e,model):return e.db.scalar(select(func.count()).select_from(model))


def test_scan_note_tags_each_resolved_character_and_reappears_on_future_scans(scans):
    e=scans;r=report(e);saved=post(e,r);assert saved.status_code==200,saved.text
    assert saved.json()['character_count']==3 and saved.json()['created']==3
    assert count(e,IntelNote)==3 and count(e,IntelSubject)==3 and count(e,IntelScanNoteBatch)==1
    data=search(e,'MULTIBOXER');assert data['total']==3
    assert {x['name'] for x in data['rows']}=={'Alpha One','Beta Two','Gamma Three'}
    assert all(x['notes'][0]['is_private'] for x in data['rows'])
    current=e.client.get(endpoint(r));assert current.status_code==200 and len(current.json()['characters'])==3
    future=report(e);assert len(e.client.get(endpoint(future)).json()['characters'])==3
    assert count(e,IntelNote)==3 # reading/generating does not duplicate tags
    assert not any('Suspected multiboxer' in (a.body or '') for a in e.db.scalars(select(AuditEvent)))


@pytest.mark.parametrize('role',['director','host','admin','intel_analyst'])
def test_private_note_not_searchable_or_readable_by_other_accounts_even_staff(scans,role):
    e=scans;r=report(e);post(e,r)
    if role=='intel_analyst':
        peer=User(email='peer@invalid.test',display_name='Other analyst',role='intel_analyst')
        e.db.add(peer);e.db.commit();e.current[0]=peer
    else:e.current[0]=e.users[role]
    assert search(e,'multiboxer')['total']==0
    assert e.client.get(endpoint(r)).json()['characters']=={}
    row=e.db.scalar(select(IntelNote));path=f'/api/intel/subjects/{row.subject_id}/notes'
    assert e.client.get(path).json()==[]
    assert e.client.patch(f'{path}/{row.id}',json={'body':'overwrite','expected_body':row.body,'expected_is_private':True}).status_code==404
    assert e.client.request('DELETE',f'{path}/{row.id}',json={'expected_body':row.body,'expected_is_private':True}).status_code==404


def test_public_note_shared_only_with_signed_in_intel_users(scans):
    e=scans;r=report(e);assert post(e,r,private=False).status_code==200
    e.current[0]=e.users['director'];data=search(e,'mining crew');assert data['total']==3
    assert len(e.client.get(endpoint(r)).json()['characters'])==3
    e.current[0]=e.users['member'];assert e.client.get('/api/intel/notes/search?q=mining').status_code==403
    assert e.client.get(endpoint(r)).status_code==403
    ctx=e.client.get('/api/local-scans/context').json();assert not ctx['can_note'] and not ctx['can_view_notes']
    # A section override alone cannot bypass Intel's existing role requirements.
    e.db.add(UserSectionPermission(user_id=e.users['member'].id,section='intel_reports',can_view=True));e.db.commit()
    assert e.client.get(endpoint(r)).status_code==403
    e.current[0]=None;assert e.client.get('/api/intel/notes/search?q=mining').status_code==401
    assert e.client.get(endpoint(r)).status_code==401
    public=e.client.get('/api/local-scans/public/'+r['token']);assert public.status_code==200
    assert 'multiboxer' not in public.text and 'intel_notes' not in public.text and 'character_notes' not in public.text


def test_public_pdf_snapshot_does_not_receive_notes(scans):
    e=scans;r=report(e);post(e,r,body='UNIQUE SECRET',private=False);seen=[]
    async def logos(snapshot):seen.append(snapshot);return {}
    def render(snapshot,images):seen.append(snapshot);return b'%PDF synthetic fixture'
    with patch('app.services.local_scan_pdf.logo_images',logos),patch('app.services.local_scan_pdf.render_pdf',render):
        response=e.client.get('/api/local-scans/public/'+r['token']+'/pdf')
    assert response.status_code==200 and seen
    assert all('UNIQUE SECRET' not in str(snapshot) for snapshot in seen)
    assert 'UNIQUE SECRET' not in str(e.db.get(LocalScanReport,r['token']).payload)


def test_notes_survive_scan_expiry_and_deletion(scans):
    e=scans;r=report(e);post(e,r,private=False)
    stored=e.db.get(LocalScanReport,r['token']);stored.expires_at=local_scan.now()-timedelta(seconds=1);e.db.commit()
    assert e.client.get(endpoint(r)).status_code==404 and post(e,r).status_code==404
    assert search(e,'multiboxer')['total']==3
    e.db.delete(stored);e.db.commit();assert search(e,'multiboxer')['total']==3


def test_private_report_access_still_restricts_bulk_note_source(scans):
    e=scans;r=report(e,private=True);e.current[0]=e.users['host']
    assert post(e,r,private=False).status_code==404
    assert e.client.get(endpoint(r)).status_code==404
    assert count(e,IntelNote)==0


def test_idempotent_retry_and_request_conflict_are_atomic(scans):
    e=scans;r=report(e);request_id=str(uuid4())
    one=post(e,r,request_id=request_id);two=post(e,r,request_id=request_id)
    assert one.status_code==two.status_code==200 and two.json()['replayed'] and two.json()['created']==0
    assert count(e,IntelNote)==3 and count(e,IntelScanNoteBatch)==1
    assert post(e,r,body='Other note',request_id=request_id).status_code==409
    assert post(e,r,private=False,request_id=request_id).status_code==409
    other=report(e);assert post(e,other,request_id=request_id).status_code==409
    assert count(e,IntelNote)==3 and count(e,IntelScanNoteBatch)==1


def test_privacy_changes_are_checked_for_stale_edits_and_deletes(scans):
    e=scans;r=report(e);post(e,r,body='Same operator',private=False)
    row=e.db.scalar(select(IntelNote));path=f'/api/intel/subjects/{row.subject_id}/notes/{row.id}'
    changed=e.client.patch(path,json={'body':'Same operator','expected_body':'Same operator','is_private':True,'expected_is_private':False})
    assert changed.status_code==200 and changed.json()['is_private']
    assert e.client.patch(path,json={'body':'Lost update','expected_body':'Same operator'}).status_code==409
    assert e.client.request('DELETE',path,json={'expected_body':'Same operator'}).status_code==409
    e.current[0]=e.users['director'];data=search(e,'Same operator');assert data['total']==2
    e.current[0]=e.users['intel_analyst']
    assert e.client.request('DELETE',path,json={'expected_body':'Same operator','expected_is_private':True}).status_code==200
    assert search(e,'Same operator')['total']==2


def test_moderators_can_edit_public_text_but_only_authors_change_visibility(scans):
    e=scans;r=report(e);post(e,r,body='Shared operator',private=False)
    row=e.db.scalar(select(IntelNote));base=f'/api/intel/subjects/{row.subject_id}/notes'
    e.current[0]=e.users['admin']
    listing=e.client.get(base).json();assert listing[0]['can_edit'] and not listing[0]['can_change_visibility']
    assert e.client.patch(f'{base}/{row.id}',json={'body':'Shared operator','expected_body':'Shared operator','is_private':True}).status_code==403
    changed=e.client.patch(f'{base}/{row.id}',json={'body':'Reviewed operator','expected_body':'Shared operator','is_private':False})
    assert changed.status_code==200 and not changed.json()['can_change_visibility']
    e.current[0]=e.users['intel_analyst']
    listing=e.client.get(base).json();assert listing[0]['can_change_visibility']


def test_literal_case_insensitive_search_includes_existing_dossier_notes(scans):
    e=scans;r=report(e);post(e,r,body='100%_Group O\'Brien',private=False)
    post(e,r,body='10000Group',private=False)
    assert search(e,'100%_gRoUp')['total']==3
    assert search(e,"O'Brien")['total']==3
    assert search(e,"%' OR 1=1 --")['total']==0
    sid=e.db.scalar(select(IntelSubject.id))
    added=e.client.post(f'/api/intel/subjects/{sid}/notes',json={'body':'Existing dossier label','is_private':False})
    assert added.status_code==201
    assert search(e,'dossier label')['total']==1
    assert search(e,'  ')['total']==0


def test_pagination_deduplicates_characters_and_reports_more_matching_notes(scans):
    e=scans;r=report(e)
    for _ in range(4):post(e,r,body='Shared team',private=False)
    data=search(e,'shared team',limit=2);assert data['total']==3 and len(data['rows'])==2
    assert all(row['matching_note_count']==4 and len(row['notes'])==3 for row in data['rows'])
    other=search(e,'shared team',limit=2,offset=2);assert len(other['rows'])==1
    assert not ({x['character_id'] for x in data['rows']}&{x['character_id'] for x in other['rows']})


def test_revoked_intel_permission_and_invalid_inputs_leave_no_partial_notes(scans):
    e=scans;r=report(e)
    for body in (' ','\x00','X'*5001):assert post(e,r,body=body).status_code==422
    assert e.client.post(endpoint(r),json={'body':'x','request_id':'bad'}).status_code==422
    e.db.add(UserSectionPermission(user_id=e.users['intel_analyst'].id,section='intel_reports',can_view=False));e.db.commit()
    assert post(e,r).status_code==403 and e.client.get(endpoint(r)).status_code==403
    assert count(e,IntelNote)==count(e,IntelScanNoteBatch)==0


def test_9999_pilots_bulk_note_and_late_search_page(scans):
    e=scans;r=report(e);stored=e.db.get(LocalScanReport,r['token'])
    stored.payload={**stored.payload,'pilots':[{'character_id':10000000+i,'name':f'Demo Pilot {i:05d}'} for i in range(9999)]}
    e.db.commit();response=post(e,r,body='Large multibox team',private=False)
    assert response.status_code==200,response.text
    assert response.json()['created']==9999 and count(e,IntelNote)==9999
    data=search(e,'large multibox',offset=9900,limit=100)
    assert data['total']==9999 and len(data['rows'])==99 and data['rows'][-1]['name']=='Demo Pilot 09998'


def test_mid_batch_failure_rolls_back_notes_identities_and_retry_ledger(scans,monkeypatch):
    e=scans;r=report(e);stored=e.db.get(LocalScanReport,r['token'])
    stored.payload={**stored.payload,'pilots':[{'character_id':11000000+i,'name':f'Atomic Pilot {i:05d}'} for i in range(801)]}
    e.db.commit();original=service.insert;calls=0
    def failing_insert(model):
        nonlocal calls
        calls+=1
        if calls==2:raise RuntimeError('Synthetic write failure')
        return original(model)
    monkeypatch.setattr(service,'insert',failing_insert)
    with pytest.raises(RuntimeError,match='Synthetic write failure'):post(e,r)
    assert count(e,IntelNote)==count(e,IntelScanNoteBatch)==0
    assert count(e,IntelSubject)==3  # Original scan stubs survive; 801 new note identities roll back.
    assert e.db.get(LocalScanReport,r['token']) is not None


def test_migration_preserves_existing_notes_and_refuses_to_publish_private_notes_on_rollback():
    file=Path(__file__).parents[1]/'alembic/versions/0106_scan_character_notes.py'
    spec=importlib.util.spec_from_file_location('scan_note_migration',file);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE intel_subjects (id INTEGER PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE intel_notes (id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL, author_user_id INTEGER NOT NULL, body TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)'))
        conn.execute(text("INSERT INTO intel_notes (subject_id,author_user_id,body) VALUES (1,1,'Keep this note')"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            assert conn.scalar(text('SELECT is_private FROM intel_notes'))==0
            conn.execute(text('UPDATE intel_notes SET is_private=true'))
            with pytest.raises(RuntimeError,match='private Intel notes'):migration.downgrade()
            assert 'is_private' in {c['name'] for c in inspect(conn).get_columns('intel_notes')}
            conn.execute(text('UPDATE intel_notes SET is_private=false'));migration.downgrade()
            assert conn.scalar(text('SELECT body FROM intel_notes'))=='Keep this note'
            assert 'intel_scan_note_batches' not in inspect(conn).get_table_names()
