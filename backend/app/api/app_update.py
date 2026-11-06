"""Host-only bridge to the opt-in updater running beside Docker."""
import json
import os
import re
import stat
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import get_current_user, require_host
from app.models import User

router = APIRouter(prefix="/app-update", tags=["app-update"])
JOB_ID = re.compile(r"[a-f0-9]{32}")
ACTIVE = {"queued", "checking", "installing", "starting"}


class UpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str = Field(pattern=r"^[a-f0-9]{32}$")


def host(user: User = Depends(get_current_user)) -> None:
    require_host(user)


def bridge() -> Path | None:
    path = os.environ.get("EQM_UPDATE_BRIDGE")
    return Path(path) if path else None


def snapshot(root: Path | None) -> dict:
    if root is None:
        return {"enabled": False, "online": False, "job": None}
    try:
        heartbeat = (root / "status/heartbeat").stat().st_mtime
        online = abs(time.time() - heartbeat) < 20
    except OSError:
        online = False
    try:
        with (root / "status/job.json").open(encoding="utf-8") as state:
            job = json.loads(state.read(4096))
    except (OSError, ValueError):
        job = None
    if not isinstance(job, dict):
        job = None
    # The inbox is mounted read-write. Never dereference a symlink or read a
    # non-regular file in it. The host helper validates the job ID separately.
    request = root / "inbox/request"
    try:
        before = request.lstat()
        if not stat.S_ISREG(before.st_mode):
            return {"enabled": True, "online": online, "job": job}
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(request, flags)
        with os.fdopen(fd, "rb") as stream:
            after = os.fstat(stream.fileno())
            pending = stream.read(33).decode("ascii") if stat.S_ISREG(after.st_mode) and os.path.samestat(before, after) else ""
        if JOB_ID.fullmatch(pending) and (not job or job.get("id") != pending):
            job = {"id": pending, "phase": "queued", "message": "Waiting for the host helper."}
    except (OSError, UnicodeError):
        pass
    return {"enabled": True, "online": online, "job": job}


@router.get("/status", dependencies=[Depends(host)])
def update_status(response: Response) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    return snapshot(bridge())


@router.post("/jobs", status_code=202, dependencies=[Depends(host)])
def queue_update(
    payload: UpdateRequest,
    response: Response,
    update_intent: str | None = Header(default=None, alias="X-EQM-Update"),
) -> dict:
    response.headers["Cache-Control"] = "private, no-store"
    if update_intent != "1":
        raise HTTPException(403, "Explicit update request required.")
    root = bridge()
    state = snapshot(root)
    job = state["job"]
    if job and job.get("id") == payload.job_id:
        return job
    if root is None or not state["online"]:
        raise HTTPException(503, "The EQM host update helper is offline.")
    if job and job.get("phase") in ACTIVE:
        raise HTTPException(409, "An EQM update is already in progress.")
    try:
        # The fixed exclusive file serializes requests across API processes.
        with (root / "inbox/request").open("xb") as request:
            request.write(payload.job_id.encode("ascii"))
    except FileExistsError as exc:
        raise HTTPException(409, "An EQM update is already queued.") from exc
    except OSError as exc:
        raise HTTPException(503, "The host update inbox is unavailable.") from exc
    return {"id": payload.job_id, "phase": "queued", "message": "Waiting for the host helper."}
