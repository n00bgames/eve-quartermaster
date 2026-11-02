"""On-demand public corporation metadata and zKill counters; no SSO or history scrape."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import weakref
from fastapi import HTTPException
from app.domain.intel import utc
from app.models import User
from app.models.intel import IntelSubject, IntelSourceCache
from app.services.intel_sources import PublicSource, plain
from app.services.intel_reports import require_intel
from app.services.intel_corporation_data import public_profile
from app.services.intel_alliance_cache import roster, profile_key, stats_key, put

_gates = weakref.WeakKeyDictionary()


def source_factory(): return PublicSource()


def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def member(db, sid, cid, uid):
    user = db.get(User, uid, populate_existing=True)
    if user is None: raise HTTPException(403, "Intel access required")
    require_intel(user, db)
    subject = db.get(IntelSubject, sid, populate_existing=True)
    if subject is None: raise HTTPException(404, "Intel subject not found")
    if subject.kind != "alliance": raise HTTPException(422, "Member corporations require an alliance dossier")
    if not any(row["eve_id"] == cid for row in roster(db, subject)["rows"]):
        raise HTTPException(404, "Corporation is not in this alliance's latest collected roster")


def envelope(row):
    data = deepcopy(row.payload) if row else {"state": "not_collected", "data": {}}
    data["stale"] = row is None or utc(row.expires_at) <= now() or data.get("state") != "available"
    return data


async def details(db, sid, cid, uid, refresh=False):
    member(db, sid, cid, uid)
    keys = {"esi": profile_key(cid), "zkill": stats_key(cid)}
    stored = {kind: envelope(db.get(IntelSourceCache, key)) for kind, key in keys.items()}
    due = []
    for kind, item in stored.items():
        recent = bool(item.get("last_attempt_at") and now()-utc(item["last_attempt_at"]) < timedelta(seconds=60))
        needs = refresh or item["stale"] or (kind == "esi" and not item.get("complete"))
        if needs and not recent: due.append(kind)
    if refresh and not due:
        raise HTTPException(429, "Corporation details were checked recently; wait one minute before refreshing")
    # Release the request's auth/cache transaction before any async queue or I/O.
    db.rollback()
    results = {}
    if due:
        loop = asyncio.get_running_loop()
        if loop not in _gates: _gates[loop] = asyncio.Semaphore(4)
        async with _gates[loop]:
            # Recheck after waiting; concurrent expansions may already have populated caches.
            member(db, sid, cid, uid)
            pending = []
            for kind in due:
                current = envelope(db.get(IntelSourceCache, keys[kind]))
                if current.get("last_attempt_at") and now()-utc(current["last_attempt_at"]) < timedelta(seconds=60):
                    stored[kind] = current
                else:
                    pending.append(kind)
            db.rollback()
            source = source_factory() if pending else None
            try:
                for kind in pending:
                    at = now().isoformat()
                    try:
                        if kind == "esi":
                            data = public_profile(await asyncio.wait_for(source.profile("corporation", cid), 65))
                            people = [data[key] for key in ("ceo_id", "creator_id", "alliance_id", "home_station_id", "faction_id") if data.get(key)]
                            people.extend(item["alliance_id"] for item in data.get("history", [])[:100] if item.get("alliance_id"))
                            names = {}
                            if people:
                                try:
                                    names = {item["id"]: plain(item["name"], 255) for item in await asyncio.wait_for(source.names(sorted(set(people))), 35) if item.get("category") in {"character", "corporation", "alliance", "station", "faction"}}
                                except asyncio.CancelledError: raise
                                except Exception: pass
                            results[kind] = {"state": "available", "data": data, "fetched_at": at, "last_attempt_at": at,
                                             "complete": not data.get("source_errors"), "ceo_name": names.get(data.get("ceo_id")), "creator_name": names.get(data.get("creator_id")), "entity_names": {str(key): value for key, value in names.items()}}
                        else:
                            data = await asyncio.wait_for(source.stats("corporation", cid), 65)
                            results[kind] = {"state": "available", "data": {"totals": data.get("totals", {})}, "fetched_at": at, "last_attempt_at": at}
                    except asyncio.CancelledError: raise
                    except Exception:
                        results[kind] = {**stored[kind], "state": "unavailable", "last_attempt_at": at,
                                         "notice": "Public source unavailable; any retained data may be stale."}
            finally:
                if source: await source.close()
        # Fresh authorization and roster membership after network work, before writes.
        member(db, sid, cid, uid)
        for kind, result in results.items():
            seconds = (86400 if kind == "esi" else 600) if result["state"] == "available" else 60
            put(db, keys[kind], result, now()+timedelta(seconds=seconds))
        db.commit()
    member(db, sid, cid, uid)
    return {kind: envelope(db.get(IntelSourceCache, key)) for kind, key in keys.items()}
