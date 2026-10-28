"""Bounded, batched public-ESI local scan enrichment and report lifecycle."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, and_, or_, select, true
from app.models import EveCharacter, EveCorporation
from app.models.local_scan import LocalScanReport
from app.services.esi_client import EsiClient
from app.services.permissions import ROLE_RANK, role_rank

RETENTIONS = {"30m": 1800, "1h": 3600, "2h": 7200, "12h": 43200,
              "24h": 86400, "3days": 259200, "7days": 604800,
              "30days": 2592000, "permanent": None}
MAX_PILOTS = 2000


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def parse_local(text: str) -> list[str]:
    """Accept plain local clipboard names and the name column of fleet clipboard rows."""
    seen = set()
    names = []
    for line in text.replace("\ufeff", "").splitlines():
        line = line.strip()
        if not line:
            continue
        cells = line.split("\t")
        if len(cells) >= 3 and (re.search(r"\b(?:km|AU|m)\s*$", cells[-1], re.I) or cells[0].isdigit()):
            raise ValueError("This looks like a d-scan. Local Scan needs pilot names; use D-Scan in the Intel menu.")
        name = cells[0].strip()
        if name.casefold() in {"character", "character name", "pilot", "pilot name", "name"} and len(cells) > 1:
            continue
        if len(name) > 100 or any(ord(c) < 32 or c in "<>" for c in name) or name.startswith(("http://", "https://")):
            raise ValueError("Paste one pilot name per line, or fleet clipboard rows with the pilot name first.")
        if name.casefold() not in seen:
            names.append(name)
            seen.add(name.casefold())
        if len(names) > MAX_PILOTS:
            raise ValueError(f"A local scan supports at most {MAX_PILOTS:,} unique pilots.")
    if not names:
        raise ValueError("Paste at least one pilot name.")
    return names


class ScanSource:
    """Public requests only; never receives an OAuth access token."""
    def __init__(self):
        self.esi = EsiClient()

    async def resolve(self, names):
        return await self.esi.post("/universe/ids/", names)

    async def affiliations(self, ids):
        return await self.esi.post("/characters/affiliation/", ids)

    async def names(self, ids):
        return await self.esi.post("/universe/names/", ids)

    async def close(self):
        await self.esi.close()


async def enrich(names: list[str], source) -> dict:
    warnings = []
    resolved = {}
    # A single overall deadline is applied by the API in addition to transport limits.
    for offset in range(0, len(names), 250):
        batch = names[offset:offset + 250]
        try:
            result = await source.resolve(batch)
            requested = {name.casefold() for name in batch}
            for row in result.get("characters", []):
                if isinstance(row.get("id"), int) and row.get("name", "").casefold() in requested:
                    resolved[row["name"].casefold()] = {"character_id": row["id"], "name": row["name"]}
        except Exception:
            warnings.append("Some pilot-name lookups failed. Unresolved names are listed separately; try generating a new report later.")
    pilots = {row["character_id"]: {**row, "corporation_id": None, "alliance_id": None,
                                  "corporation_name": "Affiliation unavailable", "alliance_name": None,
                                  "affiliation_available": False} for row in resolved.values()}
    ids = list(pilots)
    for offset in range(0, len(ids), 250):
        batch = ids[offset:offset + 250]
        try:
            rows = await source.affiliations(batch)
            for row in rows:
                pilot = pilots.get(row.get("character_id"))
                if pilot is not None and isinstance(row.get("corporation_id"), int) and row["corporation_id"] > 0:
                    pilot.update(corporation_id=row["corporation_id"], alliance_id=row.get("alliance_id") or None,
                                 affiliation_available=True)
        except Exception:
            warnings.append("Some affiliations are unavailable. These pilots appear under Affiliation unavailable, not No alliance.")
    org_ids = sorted({p[key] for p in pilots.values() for key in ("corporation_id", "alliance_id") if p[key]})
    org_names = {}
    for offset in range(0, len(org_ids), 250):
        try:
            for row in await source.names(org_ids[offset:offset + 250]):
                if row.get("category") in {"corporation", "alliance"}:
                    org_names[row["id"]] = row["name"]
        except Exception:
            warnings.append("Some corporation/alliance names are unavailable; their EVE IDs are shown instead.")
    for pilot in pilots.values():
        cid, aid = pilot["corporation_id"], pilot["alliance_id"]
        if cid:
            pilot["corporation_name"] = org_names.get(cid, f"Corporation {cid}")
        if aid:
            pilot["alliance_name"] = org_names.get(aid, f"Alliance {aid}")
    if any(not p["affiliation_available"] for p in pilots.values()):
        warnings.append("Affiliation unavailable means ESI did not return a current affiliation; no membership was inferred.")
    unresolved = [name for name in names if name.casefold() not in resolved]
    return {"input_count": len(names), "character_count": len(pilots),
            "pilots": sorted(pilots.values(), key=lambda p: p["name"].casefold()),
            "unresolved": unresolved, "warnings": list(dict.fromkeys(warnings)),
            "source": "Public ESI names and current affiliations; snapshot at generation time."}


def corporations(db, user):
    """Membership is scoped to the actor's own linked characters, never global visibility."""
    return db.execute(select(EveCorporation.corporation_id, EveCorporation.name)
        .join(EveCharacter, EveCharacter.corporation_id == EveCorporation.id)
        .where(EveCharacter.owner_user_id == user.id).distinct()
        .order_by(EveCorporation.name)).all()


def management_scope(db, user):
    if role_rank(user, db) >= ROLE_RANK["admin"]:
        return true()
    own = LocalScanReport.created_by_user_id == user.id
    if role_rank(user, db) >= ROLE_RANK["director"]:
        return or_(own, LocalScanReport.corporation_id.in_([row[0] for row in corporations(db, user)]))
    return own


def active_reports(at=None, kind="local"):
    return and_(LocalScanReport.report_kind == kind, or_(LocalScanReport.expires_at.is_(None), LocalScanReport.expires_at > (at or now())))


def purge_expired(db):
    return db.execute(delete(LocalScanReport).where(LocalScanReport.expires_at <= now())).rowcount


_cleanup_task = None


async def cleanup_loop():
    from app.db.session import SessionLocal
    import logging
    while True:
        try:
            with SessionLocal() as db:
                purge_expired(db)
                db.commit()
        except Exception:
            logging.getLogger(__name__).exception("Local scan expiry cleanup failed; will retry")
        await asyncio.sleep(60)


def start_cleanup():
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(cleanup_loop())


async def stop_cleanup():
    global _cleanup_task
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        _cleanup_task = None
