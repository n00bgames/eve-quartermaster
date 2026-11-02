"""Compact current alliance roster and deduplicated public corporation profiles."""
from copy import deepcopy
from datetime import timedelta
from sqlalchemy import select
from app.models.intel import IntelSubject, IntelSourceCache


def roster_key(eid): return f"alliance-roster:{eid}"
def profile_key(eid): return f"corporation-profile:{eid}"
def stats_key(eid): return f"corporation-stats:{eid}"


def put(db, key, value, expires):
    row = db.get(IntelSourceCache, key)
    if row is None:
        db.add(IntelSourceCache(key=key, payload=value, expires_at=expires))
    else:
        row.payload, row.expires_at = value, expires


def census_cache(db, subject_id, payload, at):
    subject = db.get(IntelSubject, subject_id)
    if subject.kind != "alliance":
        return
    rows = payload.get("corporations", [])
    # Keep the dossier's public roster summary aligned with this newer census
    # without pretending the rest of the alliance identity was re-fetched.
    public = deepcopy(subject.public_data or {})
    esi = public.setdefault("esi", {})
    profile = esi.setdefault("data", {})
    profile["corporation_ids"] = [row["eve_id"] for row in rows]
    profile["corporations"] = [{"id": row["eve_id"], "name": row["name"]} for row in rows]
    esi["corporations_fetched_at"] = at.isoformat()
    subject.public_data = public
    # Load cached profiles in batches rather than one SELECT per member corp.
    cached = {}
    keys = [profile_key(row["eve_id"]) for row in rows]
    for offset in range(0, len(keys), 500):
        cached.update({row.key: row for row in db.scalars(select(IntelSourceCache).where(IntelSourceCache.key.in_(keys[offset:offset+500]))).all()})
    roster = []
    for item in rows:
        profile = item.get("profile")
        key = profile_key(item["eve_id"])
        old = cached.get(key)
        data = profile or ((old.payload.get("data") or {}) if old else {})
        summary = {name: item.get(name) for name in ("eve_id", "name", "member_count", "state")}
        summary["name"] = data.get("name") or item.get("name") or f"Corporation {item['eve_id']}"
        summary.update(ticker=data.get("ticker"), ceo_id=data.get("ceo_id"),
                       ceo_name=item.get("ceo_name") or ((old.payload.get("ceo_name")) if old and (old.payload.get("data") or {}).get("ceo_id") == data.get("ceo_id") else None),
                       description=(data.get("description") or "")[:180])
        roster.append(summary)
        if profile:
            value = {"state": "available", "fetched_at": at.isoformat(),
                     "data": deepcopy(profile), "complete": False, "ceo_name": summary["ceo_name"],
                     "creator_name": item.get("creator_name")}
            if old is None:
                db.add(IntelSourceCache(key=key, payload=value, expires_at=at+timedelta(days=1)))
            else:
                old.payload, old.expires_at = value, at+timedelta(days=1)
    put(db, roster_key(subject.eve_id), {"fetched_at": at.isoformat(), "rows": roster,
        "corporation_count": payload["corporation_count"], "resolved_corporations": payload["resolved_corporations"],
        "member_count": payload["member_count"], "known_member_count": payload["known_member_count"]}, at+timedelta(days=1))


def roster(db, subject):
    cached = db.get(IntelSourceCache, roster_key(subject.eve_id))
    if cached:
        return deepcopy(cached.payload)
    profile = ((subject.public_data or {}).get("esi") or {}).get("data") or {}
    names = {item["id"]: item["name"] for item in profile.get("corporations", []) if isinstance(item, dict) and item.get("id") and item.get("name")}
    ids = sorted({eid for eid in profile.get("corporation_ids", []) if type(eid) is int and eid > 0})[:1000]
    # Legacy profiles have IDs but no census. Keep unknown counts unknown.
    return {"fetched_at": None, "rows": [{"eve_id": eid, "name": names.get(eid, f"Corporation {eid}"),
             "member_count": None, "ticker": None, "ceo_id": None, "ceo_name": None, "description": "", "state": "not_collected"}
            for eid in ids], "member_count": None,
            "known_member_count": None, "resolved_corporations": 0, "corporation_count": len(ids)}
