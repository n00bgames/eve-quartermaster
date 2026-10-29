from datetime import timedelta
from io import BytesIO
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch, Mock
import zipfile
import httpx
import pytest
from sqlalchemy import select,inspect
from sqlalchemy.orm import sessionmaker
from alembic.migration import MigrationContext
from alembic.operations import Operations
from rq.exceptions import NoSuchJobError
from tests.test_local_scan import env
from app.api import sde, auth
from app.core.config import get_settings
from app.core.security import create_session_token
from app.models import SdeMaintenanceJob, AuditEvent, RoleDefinition, UserRoleAssignment
from app.services import sde_maintenance as service
from app.services.sde_importer import SDE_FILES

@pytest.fixture
def app(env,tmp_path):
    env.app.include_router(sde.router,prefix='/api')
    factory=sessionmaker(env.db.get_bind())
    env.current[0]=env.users['admin']
    settings=get_settings()
    with patch.object(service,'SessionLocal',factory),patch.object(settings,'sde_download_path',str(tmp_path/'downloads')),patch.object(service,'enqueue_worker') as enqueue,patch('rq.job.Job.fetch',side_effect=NoSuchJobError):
        env.enqueue=enqueue
        yield env

def archive(omit=None,extra=None):
    content=BytesIO()
    with zipfile.ZipFile(content,'w',zipfile.ZIP_DEFLATED) as z:
        for logical,names in SDE_FILES.items():
            if logical!=omit:z.writestr(names[0],'{}')
        if extra:z.writestr(extra,'{}')
    return content.getvalue()

def client(body=None,metadata=None,status=200):
    body=archive() if body is None else body
    def handle(request):
        if str(request.url)==service.METADATA_URL:
            return httpx.Response(200,text=metadata or json.dumps({'_key':'sde','buildNumber':1234567,'releaseDate':'2026-10-29T11:10:00Z'}))
        assert str(request.url)==service.ARCHIVE_BASE+'eve-online-static-data-1234567-yaml.zip'
        return httpx.Response(status,content=body)
    return httpx.Client(transport=httpx.MockTransport(handle))

def create(app,auto=False):
    response=app.client.post('/api/sde/download',json={'import_after_download':auto})
    assert response.status_code==202,response.text
    return response.json()['id']

def state(app):return app.client.get('/api/sde/import-status').json()

def test_permission_boundaries_and_input_allowlist(app):
    for role in ['member','director','intel_analyst','quartermaster','applicant']:
        app.current[0]=app.users[role]
        assert app.client.post('/api/sde/download',json={}).status_code==403
        assert app.client.post('/api/sde/import',json={}).status_code==403
        assert app.client.get('/api/sde/import-status').status_code==403
    app.current[0]=None
    assert app.client.post('/api/sde/download',json={}).status_code==401
    app.current[0]=app.users['host']
    for payload in [{'url':'http://internal'},{'destination':'/etc/test'},{'command':'rebuild'}]:
        assert app.client.post('/api/sde/download',json=payload).status_code==422
    assert app.client.post('/api/sde/import',json={'sections':['types']}).status_code==400

def test_queued_progress_survives_new_sessions_and_blocks_all_sde_actions(app):
    job=create(app)
    assert app.enqueue.call_args.args==(job,)
    assert state(app)['status']=='queued'
    app.current[0]=app.users['host']
    assert app.client.post('/api/sde/download',json={}).status_code==409
    assert app.client.post('/api/sde/import',json={}).status_code==409
    assert app.db.scalar(select(AuditEvent).where(AuditEvent.event_kind=='sde_maintenance_requested'))

def test_download_only_validation_receipt_and_no_import(app):
    job=create(app)
    with patch.object(service.httpx,'Client',return_value=client()),patch.object(service,'import_sde') as importer:
        service.run_job(job)
    current=state(app)
    assert current['status']=='success' and not current['running']
    assert current['download']['build']=='1234567'
    assert len(current['download']['sha256'])==64
    assert Path(current['source_path']).is_file()
    assert not list(Path(get_settings().sde_download_path).glob('*.partial'))
    importer.assert_not_called()
    app.db.expire_all()
    assert app.db.get(SdeMaintenanceJob,job).active_key is None
    assert app.client.post('/api/sde/download',json={}).status_code==202

def test_download_and_import_updates_full_stats(app):
    job=create(app,True)
    with patch.object(service.httpx,'Client',return_value=client()):service.run_job(job)
    current=state(app)
    assert current['status']=='success' and current['import_after_download']
    assert current['stats']['types']==0 and current['stats']['blueprint_activities']==0

@pytest.mark.parametrize('body,status',[(b'not a zip',200),(archive(omit='types'),200),(archive(extra='../types.yaml'),200),(archive(),503)])
def test_failed_download_preserves_existing_archive_and_releases_slot(app,body,status):
    root=Path(get_settings().sde_download_path);root.mkdir();old=root/'previous.zip';old.write_bytes(b'previous')
    job=create(app)
    with patch.object(service.httpx,'Client',return_value=client(body,status=status)),patch.object(service,'import_sde') as importer:
        with pytest.raises(Exception):service.run_job(job)
    current=state(app)
    assert current['status']=='failed' and not current['running']
    assert old.read_bytes()==b'previous' and list(root.iterdir())==[old]
    importer.assert_not_called()

def test_download_size_limit_and_fixed_source(app):
    job=create(app)
    with patch.object(get_settings(),'sde_download_max_bytes',1),patch.object(service.httpx,'Client',return_value=client()):
        with pytest.raises(ValueError):service.run_job(job)
    assert state(app)['status']=='failed'

def test_duplicate_worker_delivery_cannot_run_twice(app):
    job=create(app)
    with patch.object(service.httpx,'Client',return_value=client()),patch.object(service,'download',return_value='example.zip') as download:
        service.run_job(job);service.run_job(job)
    assert download.call_count==1

def test_failed_worker_is_reconciled_but_queue_outage_never_unlocks_running_job(app):
    job=create(app)
    with patch('rq.job.Job.fetch',side_effect=ConnectionError):assert state(app)['running']
    with patch('rq.job.Job.fetch',return_value=Mock(get_status=lambda **kw:'failed')):
        assert state(app)['status']=='failed'
    assert app.client.post('/api/sde/download',json={}).status_code==202

def test_unknown_enqueue_outcome_stays_locked_until_confirmed_missing(app):
    app.enqueue.side_effect=ConnectionError
    assert app.client.post('/api/sde/download',json={}).status_code==503
    assert state(app)['status']=='queued'
    job=app.db.scalar(select(SdeMaintenanceJob));job.created_at=service.now()-timedelta(minutes=11);app.db.commit()
    assert state(app)['status']=='failed'

def test_queue_callback_marks_failed_without_overwriting_success(app):
    job=create(app);service.rq_failed(Mock(id=job),None)
    assert state(app)['status']=='failed'
    app.enqueue.reset_mock();job=create(app)
    with patch.object(service.httpx,'Client',return_value=client()):service.run_job(job)
    service.rq_failed(Mock(id=job),None)
    assert state(app)['status']=='success'

def test_agents_only_import_uses_worker_and_reports_failure(app,tmp_path):
    response=app.client.post('/api/sde/import',json={'source_path':str(tmp_path/'missing.zip'),'sections':['agents']})
    assert response.status_code==202
    with pytest.raises(FileNotFoundError):service.run_job(response.json()['id'])
    assert state(app)['status']=='failed'

def test_migration_roundtrip(app):
    app.db.commit();engine=app.db.get_bind();SdeMaintenanceJob.__table__.drop(engine)
    path=Path(__file__).parents[1]/'alembic/versions/0097_sde_maintenance.py'
    spec=importlib.util.spec_from_file_location('maintenance_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade();assert 'sde_maintenance_jobs' in inspect(connection).get_table_names()
            module.downgrade();assert 'sde_maintenance_jobs' not in inspect(connection).get_table_names()


@pytest.mark.parametrize('metadata',[
    '{"_key":"sde","buildNumber":"../../internal"}',
    '{"_key":"other","buildNumber":1234567}',
    'not-json',
])
def test_metadata_failure_never_imports_or_promotes_archive(app,metadata):
    job=create(app)
    with patch.object(service.httpx,'Client',return_value=client(metadata=metadata)),patch.object(service,'import_sde') as importer:
        with pytest.raises(ValueError):service.run_job(job)
    assert state(app)['status']=='failed'
    importer.assert_not_called()
    assert not list(Path(get_settings().sde_download_path).glob('*'))

def test_real_rq_enqueue_configuration_uses_existing_queue_and_callbacks():
    from rq.job import Callback
    from rq.utils import import_attribute
    connection=Mock()
    with patch.object(service,'queue_connection',return_value=connection),patch('rq.Queue') as queue:
        service.enqueue_worker('example-job')
    assert queue.call_args.args==('eve-quartermaster',)
    args=queue.return_value.enqueue.call_args
    assert args.args==('app.services.sde_maintenance.run_job','example-job')
    assert args.kwargs['job_id']=='example-job' and args.kwargs['job_timeout']==get_settings().sde_job_timeout_seconds
    for key in ['on_failure','on_stopped']:
        assert callable(import_attribute(Callback(args.kwargs[key]).func))

def test_real_auth_allows_combined_roles_but_rejects_utility_user(app):
    app.app.dependency_overrides.pop(auth.get_current_user)
    user=app.users['member']
    app.db.add(UserRoleAssignment(user_id=user.id,role='admin'));app.db.commit()
    headers={'Authorization':'Bearer '+create_session_token(user)}
    response=app.client.post('/api/sde/download',headers=headers,json={})
    assert response.status_code==202,response.text
    headers={'Authorization':'Bearer '+create_session_token(app.users['quartermaster'])}
    assert app.client.post('/api/sde/download',headers=headers,json={}).status_code==403
