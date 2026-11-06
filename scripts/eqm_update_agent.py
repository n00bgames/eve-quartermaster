"""Run on the Docker host as the owner of the EQM checkout (Python 3.10+)."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

JOB_ID = re.compile(rb"[a-f0-9]{32}")
REVISION = re.compile(r"[a-f0-9]{40}")
ACTIVE = {"queued", "checking", "installing", "starting"}


def atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1)


def lock_runner(path: Path):
    lock = path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        raise SystemExit("An EQM updater is already running for this checkout.")
    return lock


def read_request(path: Path) -> str | None:
    # This directory is writable by the web backend. Read only a plain file
    # of the expected size, and never use its contents as a path or command.
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or getattr(before, "st_file_attributes", 0) & 0x400:
        raise ValueError("Invalid request file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as request:
        after = os.fstat(request.fileno())
        if not stat.S_ISREG(after.st_mode) or not os.path.samestat(before, after):
            raise ValueError("Request changed while being read")
        value = request.read(33)
    if JOB_ID.fullmatch(value):
        return value.decode("ascii")
    # The API creates the file exclusively before writing the ID.
    if time.time() - before.st_mtime < 10:
        return None
    raise ValueError("Invalid request ID")


class UpdateFailed(Exception):
    pass


class Agent:
    def __init__(self, root: Path, frontend_url: str):
        self.root = root
        self.frontend_url = frontend_url.rstrip("/")
        self.data = root / ".eqm-update"
        self.inbox = self.data / "inbox"
        self.status = self.data / "status"
        self.request = self.inbox / "request"
        self.job_file = self.status / "job.json"
        self.log = self.data / "update.log"
        self.env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"}
        for path in (self.inbox, self.status):
            path.mkdir(parents=True, exist_ok=True)

    def keep_alive(self, stop: threading.Event) -> None:
        heartbeat = self.status / "heartbeat"
        while not stop.is_set():
            heartbeat.touch()
            stop.wait(2)

    def publish(self, job_id: str, phase: str, message: str, **details) -> None:
        atomic_write(self.job_file, json.dumps({
            "id": job_id, "phase": phase, "message": message, **details,
        }))

    def previous_job(self) -> dict:
        try:
            job = json.loads(self.job_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return job if isinstance(job, dict) else {}

    def command(self, args: list[str], timeout: int = 20) -> str:
        return subprocess.run(
            args, cwd=self.root, env=self.env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True, timeout=timeout,
        ).stdout.strip()

    def compose_command(self) -> list[str]:
        try:
            self.command(["docker", "compose", "version"])
        except (OSError, subprocess.SubprocessError):
            self.command(["docker-compose", "version"])
            return ["docker-compose"]
        return ["docker", "compose"]

    def probe(self, revision: str) -> bool:
        # Use the same proxy path as the browser and bypass machine proxies.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(f"{self.frontend_url}/api/health", timeout=3) as response:
                health = json.loads(response.read(4096))
            if not isinstance(health, dict) or health.get("status") != "ok" or health.get("revision") != revision:
                return False
            with opener.open(self.frontend_url, timeout=3) as response:
                return response.status == 200 and response.headers.get_content_type() == "text/html"
        except (OSError, ValueError):
            return False

    def services_ready(self, compose: list[str], revision: str) -> bool:
        try:
            containers = self.command([*compose, "ps", "-q", "frontend", "worker"], timeout=5).splitlines()
            if len(containers) != 2:
                return False
            format_string = '{{.State.Status}} {{index .Config.Labels "com.n00bgames.eqm.revision"}}'
            states = self.command(["docker", "inspect", "--format", format_string, *containers], timeout=5)
            return states.splitlines() == [f"running {revision}"] * 2
        except (OSError, subprocess.SubprocessError):
            return False

    def run_script(self, revision: str, lock) -> None:
        name = "update-eqm.bat" if os.name == "nt" else "update-eqm.sh"
        # Git can replace the updater during the fast-forward. Execute a
        # private copy so the running script stays consistent across the pull.
        with tempfile.TemporaryDirectory(dir=self.data) as directory, self.log.open("wb") as log:
            shutil.copyfile(self.root / name, Path(directory) / name)
            args = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", name] if os.name == "nt" else ["/bin/sh", name]
            options = {} if os.name == "nt" else {"pass_fds": (lock.fileno(),)}
            with subprocess.Popen(
                args, cwd=directory, env={
                    **self.env, "EQM_UPDATE_ROOT": str(self.root), "EQM_UPDATE_TARGET": revision,
                }, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **options,
            ) as process:
                while process.poll() is None:
                    time.sleep(2)
                if process.returncode:
                    raise UpdateFailed(f"The update script exited with code {process.returncode}. See the host update log.")

    def update(self, job_id: str, lock) -> None:
        self.publish(job_id, "checking", "Checking origin/main for updates.")
        if self.command(["git", "branch", "--show-current"]) != "main":
            raise UpdateFailed("Switch the EQM checkout to main on the host before updating.")
        if self.command(["git", "status", "--porcelain", "--untracked-files=all"]):
            raise UpdateFailed("The EQM checkout has local changes. Resolve them on the host before updating.")
        self.command(["git", "fetch", "--no-tags", "origin", "refs/heads/main"], timeout=60)
        current = self.command(["git", "rev-parse", "HEAD"])
        target = self.command(["git", "rev-parse", "FETCH_HEAD"])
        if not REVISION.fullmatch(target):
            raise UpdateFailed("Git returned an invalid update revision.")
        try:
            self.command(["git", "merge-base", "--is-ancestor", current, target])
        except subprocess.CalledProcessError as exc:
            raise UpdateFailed("The EQM checkout cannot fast-forward to origin/main.") from exc
        compose = self.compose_command()
        if current == target and self.probe(target) and self.services_ready(compose, target):
            self.publish(job_id, "current", "EQM is up to date.", revision=target)
            return
        self.publish(job_id, "installing", "Building and installing EQM. The app may reconnect during this step.", revision=target)
        self.run_script(target, lock)
        if self.command(["git", "rev-parse", "HEAD"]) != target:
            raise UpdateFailed("The update script did not install the requested revision.")
        self.publish(job_id, "starting", "Waiting for EQM and its worker to come back online.", revision=target)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if self.probe(target) and self.services_ready(compose, target):
                self.publish(job_id, "succeeded", "EQM updated and ready.", revision=target)
                return
            time.sleep(3)
        raise UpdateFailed("The update script finished, but the new EQM did not become ready in five minutes.")

    def serve(self, lock) -> None:
        previous = self.previous_job()
        if previous.get("phase") in ACTIVE:
            self.publish(previous["id"], "failed", "The host helper was interrupted. Check the host before retrying.")
        while True:
            try:
                job_id = read_request(self.request)
            except FileNotFoundError:
                job_id = None
            except (OSError, ValueError) as exc:
                print(f"Rejected update request: {exc}", file=sys.stderr, flush=True)
                if not self.request.is_dir():
                    self.request.unlink(missing_ok=True)
                job_id = None
            if job_id is None:
                time.sleep(2)
                continue
            # A terminal result can survive a restart between publish and unlink.
            if self.previous_job().get("id") != job_id:
                try:
                    self.update(job_id, lock)
                except UpdateFailed as exc:
                    self.publish(job_id, "failed", str(exc))
                except (OSError, subprocess.SubprocessError) as exc:
                    print(f"Update check failed: {exc}", file=sys.stderr, flush=True)
                    self.publish(job_id, "failed", "A host Git or Docker command failed. Check the helper output.")
            self.request.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    url = urlsplit(args.frontend_url)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "::1", "localhost"} or url.path not in {"", "/"} or url.username or url.query or url.fragment:
        parser.error("Use the loopback HTTP origin of EQM's Compose frontend.")
    agent = Agent(Path(__file__).resolve().parents[1], args.frontend_url)
    with lock_runner(agent.data / "agent.lock") as lock:
        print(f"EQM update helper is watching {agent.root}.", flush=True)
        stop = threading.Event()
        heartbeat = threading.Thread(target=agent.keep_alive, args=(stop,), daemon=True)
        heartbeat.start()
        try:
            agent.serve(lock)
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            heartbeat.join()
            (agent.status / "heartbeat").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
