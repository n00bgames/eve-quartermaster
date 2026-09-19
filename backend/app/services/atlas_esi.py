"""Bounded public ESI cache. Never store private character responses here."""
import asyncio
import weakref
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from app.services.esi_client import EsiClient

_cache = OrderedDict()
_locks = weakref.WeakValueDictionary()  # Only retained by in-flight requests.


def header_date(value, fallback):
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return fallback


async def public_snapshot(path):
    now = datetime.now(timezone.utc)
    cached = _cache.get(path)
    if cached and cached["expires_at"] > now:
        _cache.move_to_end(path)
        return cached
    lock = _locks.setdefault(path, asyncio.Lock())
    async with lock:
        try:
            cached = _cache.get(path)
            if cached and cached["expires_at"] > datetime.now(timezone.utc):
                return cached
            data, headers = await EsiClient().get_with_headers(path)
            observed = header_date(headers.get("Last-Modified"), None)
            result = dict(data=data, observed_at=observed.isoformat() if observed else None,
                expires_at=max(now + timedelta(seconds=30), header_date(headers.get("Expires"), now + timedelta(minutes=5))),
                stale=False, error=None)
            _cache[path] = result
            while len(_cache) > 128:
                _cache.popitem(last=False)
            return result
        except Exception:
            # An unavailable feed is not an all-zero feed. Mark retained data explicitly stale.
            if cached:
                return {**cached, "stale": True, "error": "ESI refresh unavailable; showing the previous snapshot."}
            return dict(data=None, observed_at=None, expires_at=now,
                stale=True, error="ESI data unavailable. Try again shortly.")


async def activity_snapshot():
    kills, jumps = await asyncio.gather(public_snapshot("/universe/system_kills/"), public_snapshot("/universe/system_jumps/"))
    result = {}
    for name, snapshot in (("kills", kills), ("jumps", jumps)):
        result[name] = {**snapshot, "expires_at": snapshot["expires_at"].isoformat(),
            "data": {str(row["system_id"]): row for row in snapshot["data"]} if snapshot["data"] is not None else None}
    return result
