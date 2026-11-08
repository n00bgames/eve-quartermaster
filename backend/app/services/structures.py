"""Read-only owned structures. Each request uses only the viewer's own token.

No private structure data is written into the public navigation catalog. ESI's
transport cache remains authoritative; a refresh cannot bypass CCP's cache.
"""
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from app.models import EveCorporation, EveSystem, EveSystemObject, EveType
from app.services.esi_client import gather_esi

UPWELL_SCOPE = "esi-corporations.read_structures.v1"
POS_SCOPE = "esi-corporations.read_starbases.v1"
SCOPES = {UPWELL_SCOPE, POS_SCOPE}
UPWELL_FIELDS = ("fuel_expires", "state_timer_start", "state_timer_end", "unanchors_at",
                 "reinforce_hour", "next_reinforce_hour", "next_reinforce_apply", "profile_id")
POS_FIELDS = ("moon_id", "onlined_since", "reinforced_until", "unanchor_at")
SETTINGS = ("allow_alliance_members", "allow_corporation_members", "attack_if_at_war",
            "attack_if_other_security_status_dropping", "attack_security_status_threshold",
            "attack_standing_threshold", "use_alliance_standings", "fuel_bay_view",
            "fuel_bay_take", "anchor", "unanchor", "online", "offline")


def now():
    return datetime.now(timezone.utc).isoformat()


def source_info(headers):
    # Date is the original ESI response date, including when served by our cache.
    return {"response_date": headers.get("Date"), "expires": headers.get("Expires"),
            "last_modified": headers.get("Last-Modified"), "cache_control": headers.get("Cache-Control")}


async def pages(client, path):
    rows, metadata, page = [], [], 1
    while True:
        payload, headers = await client.get_with_headers(path, params={"page": page})
        if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
            raise HTTPException(502, "ESI returned an invalid structure list")
        rows.extend(payload)
        metadata.append(source_info(headers))
        try:
            total = int(headers.get("X-Pages", "1"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(502, "ESI returned invalid pagination") from exc
        if total < page:
            raise HTTPException(502, "ESI structure pages changed; refresh again")
        if page >= total:
            # IDs deduplicate page-boundary overlaps; a failed page never becomes
            # an apparently complete partial list.
            key = "starbase_id" if "/starbases/" in path else "structure_id"
            if any(key not in row or "system_id" not in row or "type_id" not in row for row in rows):
                raise HTTPException(502, "ESI returned incomplete structure records")
            return list({row[key]: row for row in rows}.values()), metadata
        page += 1


def failure(exc):
    status = exc.status_code if isinstance(exc, HTTPException) else 503
    if status == 403:
        return {"status": "forbidden", "message": "ESI denied access. Check this character's corporation role and membership."}
    if status == 401:
        return {"status": "unauthorized", "message": "EVE authorization expired or was revoked. Reauthorize this character."}
    if status in {420, 429}:
        return {"status": "error", "message": "ESI is rate limiting requests. Try again later."}
    return {"status": "error", "message": "ESI is temporarily unavailable. Refresh to try again."}


async def fetch_source(client, corporation_id, kind, granted):
    scope = UPWELL_SCOPE if kind == "upwell" else POS_SCOPE
    if scope not in granted:
        return {"kind": kind, "status": "missing_scope", "required_scope": scope,
                "message": "Reauthorize a corporation character to read this list.", "rows": [], "pages": []}
    try:
        suffix = "structures" if kind == "upwell" else "starbases"
        rows, metadata = await pages(client, f"/corporations/{corporation_id}/{suffix}/")
        return {"kind": kind, "status": "ok", "rows": rows, "pages": metadata}
    except (HTTPException, httpx.HTTPError) as exc:
        return {"kind": kind, **failure(exc), "rows": [], "pages": []}


def decorate(db, raw, kind):
    type_ids = {row["type_id"] for row in raw}
    system_ids = {row["system_id"] for row in raw}
    moon_ids = {row["moon_id"] for row in raw if row.get("moon_id")}
    types = {row.type_id: row.name for row in db.scalars(select(EveType).where(EveType.type_id.in_(type_ids)))} if type_ids else {}
    systems = {row.system_id: row for row in db.scalars(select(EveSystem).where(EveSystem.system_id.in_(system_ids)))} if system_ids else {}
    moons = {row.object_id: row.name for row in db.scalars(select(EveSystemObject).where(EveSystemObject.object_id.in_(moon_ids)))} if moon_ids else {}
    result = []
    for row in raw:
        sid = row["structure_id"] if kind == "upwell" else row["starbase_id"]
        system = systems.get(row["system_id"])
        moon_name = moons.get(row.get("moon_id"))
        item = {"id": sid, "kind": kind, "type_id": row["type_id"],
                "type_name": types.get(row["type_id"], f"Type {row['type_id']}"),
                "system_id": row["system_id"], "system_name": system.name if system else f"System {row['system_id']}",
                "security_status": system.security_status if system else None,
                "name": row.get("name") or (moon_name or f"Moon {row['moon_id']}" if row.get("moon_id") else f"Structure {sid}"),
                "state": row.get("state") or "unknown", "moon_name": moon_name}
        item.update({key: row.get(key) for key in (UPWELL_FIELDS if kind == "upwell" else POS_FIELDS)})
        item["services"] = [{"name": service.get("name", "Unknown service"), "state": service.get("state", "unknown")}
                            for service in row.get("services", [])] if kind == "upwell" else None
        result.append(item)
    return result


async def current_corporation(client, character, db):
    # Local character links can lag a move to another corporation. Never issue a
    # private request against the old corporation based only on that local link.
    public = await client.get(f"/characters/{character.character_id}/")
    corporation_id = public["corporation_id"]
    corp = db.scalar(select(EveCorporation).where(EveCorporation.corporation_id == corporation_id))
    return {"id": corporation_id, "name": corp.name if corp else f"Corporation {corporation_id}"}


async def overview(client, db, character, granted):
    corp = await current_corporation(client, character, db)
    sources = await gather_esi(*(fetch_source(client, corp["id"], kind, granted) for kind in ("upwell", "pos")))
    rows = []
    for source in sources:
        rows.extend(decorate(db, source.pop("rows"), source["kind"]))
    return {"corporation": corp, "checked_at": now(), "sources": sources,
            "complete": all(source["status"] == "ok" for source in sources),
            "rows": sorted(rows, key=lambda row: (row["system_name"].casefold(), row["name"].casefold(), row["id"]))}


async def pos_detail(client, db, character, starbase_id):
    corp = await current_corporation(client, character, db)
    rows, _metadata = await pages(client, f"/corporations/{corp['id']}/starbases/")
    row = next((row for row in rows if row["starbase_id"] == starbase_id), None)
    if row is None:
        raise HTTPException(404, "This POS is not in the character's current corporation list")
    payload, headers = await client.get_with_headers(f"/corporations/{corp['id']}/starbases/{starbase_id}/", params={"system_id": row["system_id"]})
    fuels = payload.get("fuels")
    if fuels is not None:
        names = {row.type_id: row.name for row in db.scalars(select(EveType).where(EveType.type_id.in_({fuel["type_id"] for fuel in fuels})))}
        fuels = [{"type_id": fuel["type_id"], "name": names.get(fuel["type_id"], f"Type {fuel['type_id']}"), "quantity": fuel["quantity"]} for fuel in fuels]
    return {"id": starbase_id, "corporation": corp, "checked_at": now(), "source": source_info(headers),
            "fuels": fuels, "settings": {key: payload[key] for key in SETTINGS if key in payload}}
