"""Read-only restart probes, piped into Python in the existing backend container."""
import json
import time
import urllib.error
import urllib.request


CHECKS = (
    ("backend health", "http://127.0.0.1:8000/api/health", "health"),
    ("database-backed login", "http://127.0.0.1:8000/api/auth/bootstrap", "bootstrap"),
    ("database-backed branding", "http://127.0.0.1:8000/api/appearance/branding", "branding"),
    ("frontend page", "http://frontend:5173/", "html"),
    ("frontend API proxy", "http://frontend:5173/api/auth/bootstrap", "bootstrap"),
)


def probe(url, kind, timeout):
    # Internal Docker traffic must not inherit an operator's external HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("Unexpected HTTP status")
        body = response.read(65537)
        if len(body) > 65536:
            raise ValueError("Unexpectedly large readiness response")
        if kind == "html":
            if b"<html" not in body.lower():
                raise ValueError("Frontend did not return HTML")
            return
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object")
        if kind == "health" and payload.get("status") != "ok":
            raise ValueError("Backend health is not ok")
        if kind == "bootstrap" and type(payload.get("needs_admin")) is not bool:
            raise ValueError("Unexpected login response")
        if kind == "branding" and type(payload.get("revision")) is not int:
            raise ValueError("Unexpected branding response")


def wait_ready(checks=CHECKS, *, wait_seconds=90, interval=3, request_timeout=3):
    deadline = time.monotonic() + wait_seconds
    print(f"Waiting up to {wait_seconds:g} seconds for EQM readiness...", flush=True)
    while time.monotonic() < deadline:
        failed = None
        for label, url, kind in checks:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failed = label
                break
            try:
                probe(url, kind, min(request_timeout, remaining))
            except (OSError, urllib.error.URLError, ValueError):
                failed = label
                break
        if failed is None:
            print("Ready: backend, database-backed login/branding, frontend and API proxy.", flush=True)
            return 0
        print(f"Waiting for {failed}...", flush=True)
        time.sleep(max(0, min(interval, deadline - time.monotonic())))
    print("Readiness timed out; restart is NOT confirmed healthy.", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(wait_ready())
