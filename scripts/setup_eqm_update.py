"""Enable the updater on an existing EQM Docker Compose host."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from xml.sax.saxutils import escape

from eqm_update_agent import Agent, is_local_frontend, lock_runner

OVERLAY = "compose.app-update.yml"
ROOT = Path(__file__).resolve().parents[1]
SERVICE = "eqm-update-" + hashlib.sha256(os.fsencode(ROOT)).hexdigest()[:12]
VOL_TARGETS = {"/eqm-update/inbox", "/eqm-update/status"}


class SetupError(Exception):
    pass


def run(*args, env=None, timeout=30) -> str:
    return subprocess.run(
        args, cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True, timeout=timeout,
    ).stdout.strip()


def heartbeat_time(heartbeat: Path) -> float:
    try:
        return heartbeat.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def wait_for(check, description: str) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(1)
    raise SetupError(description)


def atomic_bytes(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temp = Path(file.name)
        file.write(data)
    try:
        if path.exists() and os.name != "nt":
            temp.chmod(path.stat().st_mode & 0o777)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def configure_windows(args: list[str], online: bool, data: Path) -> None:
    sid = run("whoami", "/user", "/fo", "csv", "/nh").split('"')[-2]
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        raise SetupError("The Windows Python install needs pythonw.exe to run the helper in the background.")
    arguments = escape(subprocess.list2cmdline(args))
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><LogonTrigger><Enabled>true</Enabled><UserId>{escape(sid)}</UserId></LogonTrigger></Triggers>
  <Principals><Principal id="Installer"><UserId>{escape(sid)}</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit></Settings>
  <Actions Context="Installer"><Exec><Command>{escape(str(pythonw))}</Command><Arguments>{arguments}</Arguments><WorkingDirectory>{escape(str(ROOT))}</WorkingDirectory></Exec></Actions>
</Task>"""
    definition = data / "task.xml"
    atomic_bytes(definition, xml.encode("utf-8"))
    run("schtasks", "/Create", "/TN", SERVICE, "/XML", str(definition), "/F")
    if not online:
        run("schtasks", "/Run", "/TN", SERVICE)


def configure_linux(args: list[str], online: bool) -> None:
    try:
        run("systemctl", "--user", "show-environment")
    except (OSError, subprocess.SubprocessError) as exc:
        raise SetupError("Start a systemd user session or use the manual helper setup in docs/application-updates.md.") from exc

    def quote(value, expand_dollars=False):
        value = value.replace("%", "%%")
        return json.dumps(value.replace("$", "$$") if expand_dollars else value, ensure_ascii=False)

    folder = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd/user"
    folder.mkdir(parents=True, exist_ok=True)
    unit = folder / (SERVICE + ".service")
    command = " ".join(quote(value, expand_dollars=True) for value in [sys.executable, *args])
    atomic_bytes(unit, f"""[Unit]
Description=EVE Quartermaster update helper

[Service]
WorkingDirectory={quote(str(ROOT))}
Environment={quote("PATH=" + os.environ.get("PATH", os.defpath))}
ExecStart={command}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
""".encode())
    run("systemctl", "--user", "daemon-reload")
    run("systemctl", "--user", "enable", unit.name)
    if not online:
        run("systemctl", "--user", "start", unit.name)
    try:
        run("loginctl", "enable-linger", str(os.getuid()), timeout=10)
    except (OSError, subprocess.SubprocessError):
        print("The helper is enabled at sign-in. To keep it running after logout, enable systemd user lingering.")


def configure_macos(args: list[str], online: bool, data: Path) -> None:
    folder = Path.home() / "Library/LaunchAgents"
    folder.mkdir(parents=True, exist_ok=True)
    label = "com.n00bgames." + SERVICE
    path = folder / (label + ".plist")
    atomic_bytes(path, plistlib.dumps({
        "Label": label, "ProgramArguments": [sys.executable, *args],
        "WorkingDirectory": str(ROOT), "RunAtLoad": True,
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", os.defpath)},
        "StandardOutPath": str(data / "helper.log"),
        "StandardErrorPath": str(data / "helper.log"),
    }))
    domain = f"gui/{os.getuid()}"
    try:
        run("launchctl", "print", f"{domain}/{label}")
    except subprocess.CalledProcessError:
        run("launchctl", "bootstrap", domain, str(path))
    else:
        if not online:
            run("launchctl", "kickstart", f"{domain}/{label}")


def comparable(config: dict) -> dict:
    # Both renders come from the local Compose CLI. Compare everything
    # except the precise environment key and mounts the overlay adds.
    config = deepcopy(config)
    backend = config["services"]["backend"]
    backend.get("environment", {}).pop("EQM_UPDATE_BRIDGE", None)
    if "volumes" in backend:
        backend["volumes"] = [v for v in backend["volumes"] if v["target"] not in VOL_TARGETS]
        if not backend["volumes"]:
            backend.pop("volumes")
    return config


def append_compose_file(dotenv: bytes, value: str) -> bytes:
    if "\n" in value or "\r" in value:
        raise SetupError("Compose file paths must fit on one line.")
    quoted = value.replace("'", "\\'")
    separator = b"\r\n" if b"\r\n" in dotenv else b"\n"
    before = dotenv if not dotenv or dotenv.endswith(b"\n") else dotenv + separator
    return before + b"# EQM update helper" + separator + f"COMPOSE_FILE='{quoted}'".encode() + separator


def mounted_helper(compose: list[str]) -> bool:
    # Use Docker exec so this also works with a custom published API port.
    code = (
        "import os, pathlib, urllib.request; "
        "assert os.getenv('EQM_UPDATE_BRIDGE') == '/eqm-update'; "
        "assert pathlib.Path('/eqm-update/status/heartbeat').is_file(); "
        "urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).close()"
    )
    try:
        run(*compose, "exec", "-T", "backend", "python", "-c", code, timeout=6)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def setup(frontend_url: str) -> None:
    if not is_local_frontend(frontend_url):
        raise SetupError("Use the loopback HTTP origin of EQM's Compose frontend.")
    if os.name != "nt" and os.getuid() == 0:
        raise SetupError("Run this launcher as the account that normally runs EQM, without sudo.")
    if not shutil.which("git") or not shutil.which("docker"):
        raise SetupError("Install Git and Docker using the EQM installer first.")
    if any(os.environ.get(key) for key in ("COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_PATH_SEPARATOR", "COMPOSE_ENV_FILES", "COMPOSE_DISABLE_ENV_FILE")):
        raise SetupError("Put your Compose file, project and separator settings in the checkout's .env, then unset those shell overrides.")
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
        raise SetupError("Select the local Docker context with docker context use, then unset Docker shell overrides.")
    if not (ROOT / OVERLAY).is_file():
        raise SetupError("Run this installer from the updated EQM checkout.")
    dotenv = ROOT / ".env"
    if dotenv.is_symlink():
        raise SetupError("This checkout uses a linked .env. Use the manual setup to preserve it.")
    run("git", "rev-parse", "--is-inside-work-tree")
    endpoint = run("docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}")
    if not endpoint.startswith(("unix://", "npipe://")):
        raise SetupError("Run setup on the Docker host using its local Docker context.")
    try:
        run("docker", "compose", "version")
        run("docker", "info", "--format", "{{.ServerVersion}}")
    except (OSError, subprocess.SubprocessError) as exc:
        raise SetupError("Start Docker with Compose v2 on this host and run the installer again.") from exc

    agent = Agent(ROOT, frontend_url)
    with lock_runner(agent.data / "setup.lock"):
        if agent.request.exists():
            raise SetupError("Wait for the active update to finish before running setup.")
        compose = ["docker", "compose"]
        backend = run(*compose, "ps", "-q", "backend")
        if not backend or "\n" in backend:
            raise SetupError("Start the updated EQM stack in this checkout before installing its helper.")
        try:
            run(*compose, "exec", "-T", "backend", "python", "-c",
                "import importlib.util; assert importlib.util.find_spec('app.api.app_update')")
        except subprocess.CalledProcessError as exc:
            raise SetupError("Install the current EQM version with the normal update script first.") from exc

        settings = dict(line.split("=", 1) for line in run(*compose, "config", "--environment").splitlines() if "=" in line)
        separator = settings.get("COMPOSE_PATH_SEPARATOR") or os.pathsep
        configured = settings.get("COMPOSE_FILE")
        if configured:
            files = configured.split(separator)
        else:
            label = '{{index .Config.Labels "com.docker.compose.project.config_files"}}'
            files = run("docker", "inspect", "--format", label, backend).split(",")
        if not files or any(not name or not (ROOT / name).is_file() for name in files):
            raise SetupError("Could not identify the active Compose files. List them in COMPOSE_FILE in .env and retry.")
        overlay = (ROOT / OVERLAY).resolve()
        if all((ROOT / name).resolve() != overlay for name in files):
            files.append(OVERLAY)
        target = separator.join(files)
        before = json.loads(run(*compose, "config", "--format", "json"))
        candidate = json.loads(run(*compose, "config", "--format", "json", env={**os.environ, "COMPOSE_FILE": target}))
        if candidate["services"]["backend"].get("environment", {}).get("EQM_UPDATE_BRIDGE") != "/eqm-update":
            raise SetupError("The Compose overlay did not enable the update bridge.")
        if comparable(before) != comparable(candidate):
            raise SetupError("Enabling the updater would change other Compose settings. Review your Compose file list first.")

        heartbeat = agent.status / "heartbeat"
        args = [str(ROOT / "scripts/eqm_update_agent.py"), "--frontend-url", frontend_url]
        initial_heartbeat = heartbeat_time(heartbeat)
        try:
            with lock_runner(agent.data / "agent.lock"):
                online = False
        except SystemExit:
            online = abs(time.time() - initial_heartbeat) < 20
        if sys.platform == "win32":
            configure_windows(args, online, agent.data)
        elif sys.platform == "darwin":
            configure_macos(args, online, agent.data)
        elif sys.platform.startswith("linux"):
            configure_linux(args, online)
        else:
            raise SetupError("Use the manual helper setup for this host platform.")
        def helper_ready():
            current = heartbeat_time(heartbeat)
            return abs(time.time() - current) < 20 and (online or current != initial_heartbeat)

        wait_for(helper_ready, "The background helper did not start. Check the host startup service and retry.")

        if configured != target:
            previous = dotenv.read_bytes() if dotenv.exists() else None
            atomic_bytes(dotenv, append_compose_file(previous or b"", target))
            try:
                actual = json.loads(run(*compose, "config", "--format", "json"))
                if actual != candidate:
                    raise SetupError("Compose did not load the saved overlay. Your original .env was restored.")
            except (OSError, ValueError, subprocess.SubprocessError, SetupError):
                if previous is None:
                    dotenv.unlink()
                else:
                    atomic_bytes(dotenv, previous)
                raise

        if not mounted_helper(compose):
            print("Applying the helper integration. EQM's backend will restart briefly.", flush=True)
            subprocess.run([*compose, "up", "-d", "--no-deps", "backend"], cwd=ROOT, check=True)
            wait_for(lambda: mounted_helper(compose), "EQM's backend did not become ready. Check Docker Compose and run setup again.")
        print("Update helper ready. Sign in as the EQM host and open Settings > Application Update.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    try:
        setup(args.frontend_url)
    except SetupError as exc:
        sys.exit(f"Setup stopped. {exc}")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        sys.exit(f"Setup stopped while configuring EQM. {exc}")


if __name__ == "__main__":
    main()
