"""Per-search Rust worker with Python reference/fallback and bounded IPC.

Only calculation inputs enter the worker. Authentication, ESI, quotes, persistence,
and the independent result validator stay in FastAPI.
"""
from __future__ import annotations

import json
import logging
import math
import queue
import subprocess
import threading
import time

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def equivalent(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(equivalent(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-7)
    return a == b


class AllocationEngine:
    def __init__(self, request, context, *, engine=None, binary=None):
        from app.services.pi_planner import operation_slots

        settings = get_settings()
        self.request, self.context = request, context
        self.requested = engine or settings.eqm_pi_planner_engine
        if self.requested not in {"rust", "python", "shadow"}:
            self.requested = "python"
        self.used = "python" if self.requested == "python" else self.requested
        self.reason = None
        self.process = None
        self.responses = queue.Queue(maxsize=2)
        self.timeout = max(.1, min(30., settings.eqm_core_timeout_seconds))
        self.deadline = time.monotonic() + request.search_seconds
        if self.requested == "python":
            return
        slots, notes = operation_slots(request, context)
        self.state = {"schema_version": "eqm.pi-allocation-state.v1", "catalog": context["catalog"], "pins": context["pins"], "schedule": request.schedule.model_dump(), "costs": request.costs.model_dump(), "notes": notes, "slots": [{**s, "used": [], "planets": [p.model_dump() for p in s["planets"]]} for s in slots]}
        try:
            self.process = subprocess.Popen([binary or settings.eqm_core_binary, "pi-allocation-worker"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            def read():
                try:
                    while True:
                        line = self.process.stdout.readline(8 * 1024 * 1024 + 1)
                        if not line or len(line) > 8 * 1024 * 1024:
                            self.responses.put(None)
                            return
                        self.responses.put(json.loads(line))
                except (ValueError, OSError):
                    self.responses.put(None)
            self.reader = threading.Thread(target=read, daemon=True, name="eqm-pi-allocation-output")
            self.reader.start()
            self._write(self.state)
            if self.responses.get(timeout=self.timeout) != {"ready": True}:
                raise RuntimeError("Rust worker did not accept the input contract")
            self.deadline = time.monotonic() + request.search_seconds
        except (OSError, RuntimeError, queue.Empty):
            self._fallback()

    def _write(self, payload):
        self.process.stdin.write(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")
        self.process.stdin.flush()

    def _fallback(self):
        self.close()
        self.used = "python-fallback"
        self.reason = "Rust allocation unavailable or invalid; Python reference used"
        logger.info(self.reason)

    def allocate(self, request, context, expansion, cancelled=None):
        from app.services.pi_planner import allocate

        if self.used in ("python", "python-fallback"):
            return allocate(request, context, expansion, cancelled)
        if cancelled and cancelled():
            return None, ["Search cancelled"]
        try:
            remaining = max(0., self.deadline - time.monotonic())
            self._write({"nodes": expansion["nodes"], "raw": expansion["raw"], "time_limit_ms": int(min(remaining, self.timeout) * 1000)})
            response = self.responses.get(timeout=min(remaining, self.timeout) + 1.)
            if not isinstance(response, dict) or set(response) != {"colonies", "notes"}:
                raise RuntimeError("Invalid Rust allocation response")
            colonies = response["colonies"]
            if colonies is not None:
                for colony in colonies:
                    for field in ("inputs", "external_inputs", "outputs", "extraction"):
                        colony[field] = {int(t): q for t, q in colony[field].items()}
                    # Template contract requires integer runs/link levels.
                    colony["batches"] = int(colony["batches"])
                    colony["link_levels"] = [int(n) for n in colony["link_levels"]]
            native = colonies, response["notes"]
            if self.requested == "shadow":
                reference = allocate(request, context, expansion, cancelled)
                if not equivalent(reference, native):
                    self._fallback()
                return reference
            return native
        except (OSError, RuntimeError, queue.Empty, ValueError, KeyError, TypeError):
            self._fallback()
            return allocate(request, context, expansion, cancelled)

    def close(self):
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for stream in (process.stdin, process.stdout):
            if stream:
                try:
                    stream.close()
                except OSError:
                    pass  # Closing a broken Windows pipe may try to flush it again.

    def metadata(self):
        return {"requested": self.requested, "used": self.used, "fallback_reason": self.reason, "scope": "Colony allocation and facility/link capacity calculations"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
