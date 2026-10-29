"""Fixed-source SDE jobs executed by the existing isolated RQ worker."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import time
from uuid import uuid4
import zipfile

import httpx
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuditEvent, SdeMaintenanceJob
from app.services.sde_importer import import_sde, SDE_FILES

METADATA_URL="https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
ARCHIVE_BASE="https://developers.eveonline.com/static-data/tranquility/"
ACTIVE={"queued","running"}
REQUIRED={"categories","groups","types","blueprints","dogma_attributes","dogma_effects","type_dogma","planet_schematics","regions","constellations","systems","stargates","stations"}

def now():
    return datetime.now(timezone.utc)

def queue_connection():
    from redis import Redis
    return Redis.from_url(get_settings().redis_url,socket_connect_timeout=3,socket_timeout=3)

def enqueue_worker(job_id):
    from rq import Queue
    Queue("eve-quartermaster",connection=queue_connection()).enqueue(
        "app.services.sde_maintenance.run_job",job_id,job_id=job_id,
        job_timeout=get_settings().sde_job_timeout_seconds,result_ttl=86400,failure_ttl=604800,
        on_failure="app.services.sde_maintenance.rq_failed",
        on_stopped="app.services.sde_maintenance.rq_stopped")

def serialize(job):
    if job is None:
        return {"running":False,"status":"idle","stage":"idle","stats":None}
    return {"id":job.id,"action":job.action,"running":job.status in ACTIVE,"status":job.status,"stage":job.stage,
        "source_path":job.source_path,"started_at":job.started_at.isoformat() if job.started_at else None,
        "created_at":job.created_at.isoformat(),"updated_at":job.updated_at.isoformat(),
        "completed_at":job.completed_at.isoformat() if job.completed_at else None,
        "error":job.error,"stats":job.progress.get("stats"),"download":job.archive,
        "bytes_received":job.progress.get("bytes_received",0),"total_bytes":job.progress.get("total_bytes"),
        "import_after_download":job.options.get("import_after_download",False)}

def finish(job_id,status,error=None):
    with SessionLocal() as db:
        job=db.get(SdeMaintenanceJob,job_id)
        if job is None or job.status not in ACTIVE:
            return
        job.status=status;job.stage="complete" if status=="success" else "failed"
        job.error=error;job.completed_at=now();job.updated_at=now();job.active_key=None
        db.add(AuditEvent(event_kind="sde_maintenance_finished",title=f"SDE {job.action}: {status}",actor_user_id=job.created_by_user_id))
        db.commit()

def rq_failed(job,connection,*args):
    finish(job.id,"failed","Worker stopped or timed out. Check worker logs; a partial import may need to be rerun.")

def rq_stopped(job,connection):
    rq_failed(job,connection)

def latest(db):
    job=db.scalar(select(SdeMaintenanceJob).order_by(SdeMaintenanceJob.created_at.desc(),SdeMaintenanceJob.id.desc()).limit(1))
    if job and job.status in ACTIVE:
        # Recover a failed/killed worker without releasing a still-running job.
        from rq.job import Job
        from rq.exceptions import NoSuchJobError
        try:
            state=Job.fetch(job.id,connection=queue_connection()).get_status(refresh=True)
            state=getattr(state,"value",state)
            if state in {"failed","stopped","canceled","finished"}:
                db.execute(update(SdeMaintenanceJob).where(SdeMaintenanceJob.id==job.id,SdeMaintenanceJob.status.in_(ACTIVE)).values(
                    status="failed",stage="failed",active_key=None,completed_at=now(),updated_at=now(),error="Worker ended before recording completion. Check worker logs and retry."))
                db.commit();db.refresh(job)
        except NoSuchJobError:
            created=job.created_at.replace(tzinfo=timezone.utc) if job.created_at.tzinfo is None else job.created_at
            if job.status=="queued" and now()-created>timedelta(minutes=10):
                db.execute(update(SdeMaintenanceJob).where(SdeMaintenanceJob.id==job.id,SdeMaintenanceJob.status=="queued").values(status="failed",stage="failed",active_key=None,error="Job is missing from the worker queue. Please retry.",completed_at=now(),updated_at=now()))
                db.commit();db.refresh(job)
        except Exception:
            # A queue outage is not evidence that an import has stopped.
            pass
    return job

def submit(db,user,action,source_path=None,import_after_download=False,sections=None):
    latest(db)
    job=SdeMaintenanceJob(id=str(uuid4()),active_key="sde",action=action,status="queued",stage="queued",created_by_user_id=user.id,
        source_path=source_path,options={"import_after_download":import_after_download,"sections":sections},progress={},archive={},created_at=now(),updated_at=now())
    db.add(job)
    db.add(AuditEvent(event_kind="sde_maintenance_requested",title=f"SDE {action} queued",actor_user_id=user.id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409,"Another SDE maintenance job is already queued or running") from exc
    try:
        enqueue_worker(job.id)
    except Exception as exc:
        # Preserve the operation as queued: a network timeout can occur after
        # Redis accepted it. Reconciliation releases only confirmed missing jobs.
        raise HTTPException(503,"The worker queue could not be confirmed. Refresh status before retrying; do not start a manual import.") from exc
    db.refresh(job)
    return serialize(job)

def progress(job_id,stage,**updates):
    with SessionLocal() as db:
        job=db.get(SdeMaintenanceJob,job_id)
        if job is None or job.status!="running":
            raise RuntimeError("SDE operation is no longer active")
        job.stage=stage;job.updated_at=now();job.progress={**job.progress,**updates};db.commit()

def metadata(client):
    with client.stream("GET",METADATA_URL) as response:
        response.raise_for_status();content=bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content)>1048576:
                raise ValueError("SDE metadata exceeded its size limit")
    for line in content.decode("utf-8").splitlines():
        row=json.loads(line)
        if row.get("_key")=="sde":
            build=str(row.get("buildNumber",""))
            if not re.fullmatch(r"[0-9]{1,12}",build):
                raise ValueError("Invalid SDE build number")
            return build,str(row.get("releaseDate") or "")
    raise ValueError("CCP metadata does not contain an SDE build")

def validate_archive(path):
    with zipfile.ZipFile(path) as archive:
        members=archive.infolist()
        if len(members)>2000 or sum(m.file_size for m in members)>4*1024**3 or any(m.file_size>1024**3 for m in members):
            raise ValueError("SDE archive exceeds validation limits")
        names=set()
        for member in members:
            name=PurePosixPath(member.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in member.filename or member.flag_bits&1:
                raise ValueError("SDE archive contains unsafe or encrypted entries")
            if member.filename in names:
                raise ValueError("SDE archive contains duplicate entries")
            names.add(member.filename)
        for logical in REQUIRED:
            if not any(any(name==candidate or name.endswith('/'+candidate) for candidate in SDE_FILES[logical]) for name in names):
                raise ValueError(f"SDE archive is missing {logical}")
        if archive.testzip() is not None:
            raise ValueError("SDE archive integrity check failed")

def download(job_id):
    root=Path(get_settings().sde_download_path).resolve()
    root.mkdir(parents=True,exist_ok=True)
    temporary=root/f".{job_id}.partial"
    try:
        with httpx.Client(timeout=httpx.Timeout(60,connect=15),follow_redirects=False,headers={"User-Agent":"EVE-Quartermaster/2.0.0 SDE Maintenance"}) as client:
            build,released=metadata(client)
            url=f"{ARCHIVE_BASE}eve-online-static-data-{build}-yaml.zip"
            target=root/f"eve-online-static-data-{build}-{job_id}-yaml.zip"
            progress(job_id,"downloading",bytes_received=0)
            received=0;digest=hashlib.sha256();last_update=time.monotonic();limit=get_settings().sde_download_max_bytes
            with client.stream("GET",url) as response:
                response.raise_for_status()
                total=int(response.headers["Content-Length"]) if response.headers.get("Content-Length") else None
                if total and total>limit:
                    raise ValueError("SDE download exceeds configured size limit")
                with temporary.open("xb") as output:
                    for chunk in response.iter_bytes(1024*1024):
                        received+=len(chunk)
                        if received>limit:
                            raise ValueError("SDE download exceeds configured size limit")
                        output.write(chunk);digest.update(chunk)
                        if time.monotonic()-last_update>=1:
                            progress(job_id,"downloading",bytes_received=received,total_bytes=total);last_update=time.monotonic()
                    output.flush();os.fsync(output.fileno())
                if total is not None and received!=total:
                    raise ValueError("SDE download was incomplete")
            progress(job_id,"validating archive",bytes_received=received,total_bytes=total)
            validate_archive(temporary)
            os.replace(temporary,target)
            details={"build":build,"released_at":released,"bytes":received,"sha256":digest.hexdigest(),"source_url":url,"path":str(target)}
            with SessionLocal() as db:
                job=db.get(SdeMaintenanceJob,job_id);job.source_path=str(target);job.archive=details;job.updated_at=now();db.commit()
            return str(target)
    finally:
        temporary.unlink(missing_ok=True)

def run_job(job_id):
    with SessionLocal() as db:
        claim=db.execute(update(SdeMaintenanceJob).where(SdeMaintenanceJob.id==job_id,SdeMaintenanceJob.status=="queued").values(status="running",started_at=now(),updated_at=now(),stage="starting"))
        db.commit()
        if claim.rowcount!=1:
            return
        job=db.get(SdeMaintenanceJob,job_id);action=job.action;source_path=job.source_path;options=dict(job.options)
    try:
        if action=="download":
            source_path=download(job_id)
        if action=="import" or options.get("import_after_download"):
            progress(job_id,"starting import")
            with SessionLocal() as db:
                stats=import_sde(source_path,db,sections=set(options["sections"]) if options.get("sections") else None,
                    progress=lambda stats,stage:progress(job_id,stage,stats=stats.to_dict()))
            progress(job_id,"import complete",stats=stats)
        finish(job_id,"success")
    except Exception:
        logging.getLogger(__name__).exception("SDE maintenance job failed: %s",job_id)
        finish(job_id,"failed","SDE maintenance failed. Check worker logs and storage permissions. Existing archives are preserved; a partial import may need to be rerun.")
        raise
