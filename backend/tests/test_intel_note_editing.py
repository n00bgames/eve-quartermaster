from sqlalchemy import select
from app.models import AuditEvent,UserSectionPermission,RoleDefinition,UserRoleAssignment
from app.services.permissions import assign_roles
from .test_intel_reports import env,subject

def note(env,sid,body='Evidence-only fixture note'):
    r=env.client.post(f'/intel/subjects/{sid}/notes',json={'body':body});assert r.status_code==201,r.text;return r.json()

def test_author_edits_deletes_and_keeps_original_identity(env):
    sid=subject(env)['id'];env.current[0]=env.users[1];n=note(env,sid)
    assert n['can_edit'] and n['can_delete']
    r=env.client.patch(f'/intel/subjects/{sid}/notes/{n["id"]}',json={'body':'  Revised hypothesis  ','expected_body':n['body']})
    assert r.status_code==200,r.text
    assert r.json()['body']=='Revised hypothesis' and r.json()['author']==n['author'] and r.json()['created_at']==n['created_at']
    listed=env.client.get(f'/intel/subjects/{sid}/notes').json();assert listed[0]['body']=='Revised hypothesis'
    r=env.client.request('DELETE',f'/intel/subjects/{sid}/notes/{n["id"]}',json={'expected_body':'Revised hypothesis'})
    assert r.status_code==200 and r.json()=={'deleted':True,'id':n['id']} and 'no-store' in r.headers['cache-control']
    assert env.client.get(f'/intel/subjects/{sid}/notes').json()==[]
    events=list(env.db.scalars(select(AuditEvent).where(AuditEvent.event_kind=='intel')))
    assert {'Intel analyst note edited','Intel analyst note deleted'}<={e.title for e in events}
    assert not any('Revised hypothesis' in (e.body or '') for e in events)

def test_other_analyst_denied_and_admin_can_moderate(env):
    sid=subject(env)['id'];env.current[0]=env.users[1];n=note(env,sid)
    env.current[0]=env.users[2]
    assert not env.client.get(f'/intel/subjects/{sid}/notes').json()[0]['can_edit']
    for method,body in [('PATCH',{'body':'overwrite','expected_body':n['body']}),('DELETE',{'expected_body':n['body']})]:
        assert env.client.request(method,f'/intel/subjects/{sid}/notes/{n["id"]}',json=body).status_code==403
    env.current[0]=env.users[0]
    r=env.client.patch(f'/intel/subjects/{sid}/notes/{n["id"]}',json={'body':'Moderated','expected_body':n['body']})
    assert r.status_code==200 and r.json()['author']==n['author']
    assert env.client.request('DELETE',f'/intel/subjects/{sid}/notes/{n["id"]}',json={'expected_body':'Moderated'}).status_code==200

def test_conflict_validation_and_cross_subject_scope(env):
    sid=subject(env)['id'];other=subject(env,kind='corporation',eve_id=8002)['id'];n=note(env,sid)
    path=f'/intel/subjects/{sid}/notes/{n["id"]}'
    assert env.client.patch(path,json={'body':'X','expected_body':'stale'}).status_code==409
    assert env.client.request('DELETE',path,json={'expected_body':'stale'}).status_code==409
    assert env.client.patch(path,json={'body':' ','expected_body':n['body']}).status_code==422
    assert env.client.patch(path,json={'body':'X'*5001,'expected_body':n['body']}).status_code==422
    assert env.client.patch(path,json={'body':'X','expected_body':n['body'],'author_user_id':2}).status_code==422
    assert env.client.request('DELETE',path).status_code==422
    assert env.client.patch(f'/intel/subjects/{other}/notes/{n["id"]}',json={'body':'X','expected_body':n['body']}).status_code==404
    assert env.client.request('DELETE',f'/intel/subjects/{other}/notes/{n["id"]}',json={'expected_body':n['body']}).status_code==404
    assert env.client.get(f'/intel/subjects/{sid}/notes').json()[0]['body']==n['body']

def test_analyst_combined_custom_roles_and_revocation(env):
    sid=subject(env)['id'];user=env.users[3]
    env.db.add(RoleDefinition(name='intel_custom',display_name='Custom analyst',base_role='intel_analyst'));env.db.flush()
    assign_roles(env.db,user,['quartermaster','intel_custom']);env.db.commit();env.current[0]=user
    n=note(env,sid)
    path=f'/intel/subjects/{sid}/notes/{n["id"]}'
    assert env.client.patch(path,json={'body':'Edited','expected_body':n['body']}).status_code==200
    env.db.add(UserSectionPermission(user_id=user.id,section='intel_reports',can_view=False));env.db.commit()
    assert env.client.patch(path,json={'body':'Blocked','expected_body':'Edited'}).status_code==403
    assert env.client.request('DELETE',path,json={'expected_body':'Edited'}).status_code==403
