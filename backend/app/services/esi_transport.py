"""Loop-scoped ESI connection pool and response-driven admission control.

State is local to one process/event loop. Deploy one API worker, or introduce
distributed coordination before scaling ESI traffic across API replicas.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import math
import re
import time
import weakref
from collections import OrderedDict
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

import httpx

from app.core.config import get_settings


def identity(token: str | None) -> str:
    if not token:
        return "public"
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        # Used only for local accounting, never authentication/authorization.
        value = f"{claims['azp']}:{claims['sub']}"
    except (ValueError, KeyError, IndexError, TypeError):
        value = token
    return hashlib.sha256(value.encode()).hexdigest()


def seconds(value: str | None, default: float = 1.0) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return default


@dataclass
class Bucket:
    remaining: int = 0
    limit: int = 0
    window: float = 60.0
    reset: float = 0.0
    blocked: float = 0.0
    inflight: int = 0


class EsiTransport:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = httpx.AsyncClient(
            base_url="https://esi.evetech.net/latest", timeout=30.0,
            limits=httpx.Limits(max_connections=settings.esi_max_connections,
                               max_keepalive_connections=settings.esi_max_connections,
                               keepalive_expiry=30.0),
        )
        self.slots = asyncio.Semaphore(settings.esi_max_connections)
        self.lock = asyncio.Lock()
        self.groups: dict[str, str] = {}
        self.buckets: dict[tuple[str, str], Bucket] = {}
        self.error_until = 0.0
        self.cache: OrderedDict[tuple, tuple[float, httpx.Response]] = OrderedDict()
        self.margin = settings.esi_rate_limit_cushion

    async def reserve(self, route: str, who: str) -> Bucket | float:
        async with self.lock:
            now = time.monotonic()
            key = (self.groups.get(route, route), who)
            bucket = self.buckets.setdefault(key, Bucket())
            wait = max(self.error_until, bucket.blocked) - now
            if bucket.limit:
                if now >= bucket.reset:
                    bucket.remaining = bucket.limit
                    bucket.reset = now + bucket.window
                reserve = min(max(0, bucket.limit - 2), max(1, math.ceil(bucket.limit * self.margin)))
                if bucket.remaining - 2 * bucket.inflight - 2 < reserve:
                    wait = max(wait, bucket.reset - now)
            if wait <= 0:
                bucket.inflight += 1
                return bucket
            return wait + 0.05

    async def admit(self, route: str, who: str) -> Bucket:
        while True:
            reservation = await self.reserve(route, who)
            if isinstance(reservation, Bucket):
                return reservation
            await asyncio.sleep(reservation)

    async def observe(self, route: str, who: str, admitted: Bucket, response: httpx.Response) -> None:
        async with self.lock:
            admitted.inflight -= 1
            now = time.monotonic()
            headers = response.headers
            group = headers.get("X-Ratelimit-Group")
            bucket = admitted
            if group:
                self.groups[route] = group
                bucket = self.buckets.setdefault((group, who), admitted)
            match = re.fullmatch(r"(\d+)/(\d+)([smh])", headers.get("X-Ratelimit-Limit", ""))
            remaining = headers.get("X-Ratelimit-Remaining")
            if match and remaining and remaining.isdigit():
                limit, duration, unit = match.groups()
                window = int(duration) * {"s": 1, "m": 60, "h": 3600}[unit]
                # Never increase a live budget from out-of-order responses.
                fresh = not bucket.limit or now >= bucket.reset
                bucket.remaining = int(remaining) if fresh else min(bucket.remaining, int(remaining))
                bucket.limit, bucket.window = int(limit), window
                # Conservative recovery for a rolling window: all observed
                # consumption is guaranteed expired one window after now.
                bucket.reset = now + window
            error_left = headers.get("X-ESI-Error-Limit-Remain")
            if error_left and error_left.isdigit() and int(error_left) <= 5:
                self.error_until = max(self.error_until, now + seconds(headers.get("X-ESI-Error-Limit-Reset"), 60) + 0.1)
            if response.status_code in {420, 429}:
                delay = seconds(headers.get("Retry-After"), seconds(headers.get("X-ESI-Error-Limit-Reset"), 60)) + 0.1
                if response.status_code == 420:
                    self.error_until = max(self.error_until, now + delay)
                else:
                    bucket.blocked = max(bucket.blocked, now + delay)

    async def request(self, method: str, path: str, *, headers: dict, params: dict, payload=None) -> httpx.Response:
        # Public routes share one conservative budget even if callers supply
        # different bearer tokens. Private routes use stable character claims.
        private = bool(re.match(r"^/(characters|corporations)/\d+/.+", path)) or path.startswith(("/universe/structures/", "/ui/"))
        if re.fullmatch(r"/(characters/\d+/(portrait|corporationhistory)|corporations/\d+/(icons|alliancehistory|fw/stats))/", path):
            private = False
        token = headers.get("Authorization", "").removeprefix("Bearer ") or None
        who = identity(token) if private else "public"
        route = method + " " + re.sub(r"/\d+(?=/|$)", "/{id}", path)
        # Only explicitly public universe metadata is shared across characters.
        # Private cache entries use the exact credential, so changing scopes or
        # rotating tokens cannot reuse another token's authorized response.
        public_metadata = bool(re.fullmatch(r"/universe/(types|groups|categories|planets|stations|systems)/\d+/", path))
        cache_identity = "public-metadata" if public_metadata else hashlib.sha256((token or "public").encode()).hexdigest()
        cache_key = (cache_identity, method, path, tuple(sorted((k, str(v)) for k, v in params.items())), headers.get("X-Compatibility-Date"))
        cached = self.cache.get(cache_key) if method == "GET" else None
        if cached and cached[0] > time.monotonic():
            self.cache.move_to_end(cache_key)
            return cached[1]
        self.cache.pop(cache_key, None)
        for attempt in range(3):
            while True:
                async with self.slots:
                    reservation = await self.reserve(route, who)
                    if isinstance(reservation, Bucket):
                        try:
                            request = self.client.build_request(method, path, headers=headers, params=params, json=payload)
                            # Never send cookies from another character's request.
                            request.headers.pop("cookie", None)
                            response = await self.client.send(request)
                        except BaseException:
                            async with self.lock:
                                reservation.inflight -= 1
                            raise
                        await self.observe(route, who, reservation, response)
                        break
                # Do not occupy a connection slot while waiting for a bucket.
                # Recheck allowance after obtaining a slot, not before queuing.
                await asyncio.sleep(reservation)
            if response.status_code not in {420, 429, 502, 503, 504} or method not in {"GET", "HEAD"} or attempt == 2:
                break
            if response.status_code >= 500:
                await asyncio.sleep(seconds(response.headers.get("Retry-After"), 0.5 * 2 ** attempt) + 0.1)
        if method == "GET" and response.status_code == 200:
            control = response.headers.get("Cache-Control", "").lower()
            if "no-store" not in control and "no-cache" not in control:
                match = re.search(r"(?:^|,)\s*max-age=(\d+)", control)
                ttl = float(match.group(1)) - seconds(response.headers.get("Age"), 0) if match else seconds(response.headers.get("Expires"), 0)
                if ttl > 0 and len(response.content) <= 512 * 1024:
                    self.cache[cache_key] = (time.monotonic() + ttl, response)
                    while len(self.cache) > 128:
                        self.cache.popitem(last=False)
        return response

    async def close(self) -> None:
        self.cache.clear()
        await self.client.aclose()


_transports: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def get_esi_transport() -> EsiTransport:
    loop = asyncio.get_running_loop()
    if loop not in _transports:
        _transports[loop] = EsiTransport()
    return _transports[loop]


async def close_esi_transport() -> None:
    transport = _transports.pop(asyncio.get_running_loop(), None)
    if transport:
        await transport.close()
