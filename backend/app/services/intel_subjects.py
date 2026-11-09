"""Cached identity browser and scan ingest. No SSO, sightings, or network requests."""
from datetime import datetime, timezone
from sqlalchemy import delete, select, update
from app.domain.intel import utc
from app.models.intel import IntelSubject, IntelCollection, IntelObservation, IntelSighting
from app.models.intel_membership import IntelMembershipMonitor, IntelMembershipSnapshot
from app.services.character_notes import chunks, conflict_insert

def seed_scan(db, user, snapshot, at):
    pilots = {p["character_id"]: p for p in snapshot.get("pilots", [])
              if type(p.get("character_id")) is int and 0 < p["character_id"] <= 2147483647 and p.get("name")}
    for group in chunks(pilots):
        values = []
        for eid in group:
            pilot = pilots[eid]
            profile = {key: pilot.get(key) for key in ("name", "corporation_id", "corporation_name", "alliance_id", "alliance_name", "affiliation_available")}
            values.append(dict(kind="character", eve_id=eid, name=pilot["name"], created_by_user_id=user.id,
                created_at=at, updated_at=at, archived=False, priority=False,
                public_data={"esi": {"state": "partial", "observed_at": at.isoformat(), "data": profile,
                    "notice": "Public identity and affiliation from Local Scan; full profile and combat history not collected."}}))
        statement = conflict_insert(db, IntelSubject).values(values)
        # Existing dossiers are untouched. A deleted dossier can be re-created
        # from a later scan while its stable identity keeps every author's notes.
        db.execute(statement.on_conflict_do_update(index_elements=["kind", "eve_id"],
            set_={"archived": False, "name": statement.excluded.name,
                  "public_data": statement.excluded.public_data, "updated_at": at},
            where=IntelSubject.archived.is_(True)))

def order(row):
    return (not row.get("priority", False), row["name"].casefold(), str(row.get("eve_id", row.get("key", ""))))

def catalog(db, q=""):
    # Only scalar identity metadata crosses this boundary; never notes, scan
    # positions, private enrichment, histories, or whole public JSON documents.
    profile = IntelSubject.public_data["esi"]["data"]
    fields = [profile[key].as_string().label(key) for key in
              ("corporation_id", "corporation_name", "alliance_id", "alliance_name", "affiliation_available")]
    fields.append(IntelSubject.public_data["esi"]["state"].as_string().label("profile_state"))
    fields.append(IntelSubject.public_data["esi"]["fetched_at"].as_string().label("profile_at"))
    fields.append(IntelSubject.public_data["esi"]["observed_at"].as_string().label("identity_at"))
    rows = [dict(r) for r in db.execute(select(IntelSubject.id, IntelSubject.kind, IntelSubject.eve_id,
        IntelSubject.name, IntelSubject.priority, IntelSubject.created_at, *fields)
        .where(IntelSubject.archived.is_(False))).mappings()]
    orgs = {(r["kind"], r["eve_id"]): r for r in rows if r["kind"] != "character"}
    def eid(value):
        try: return int(value) if value and int(value) > 0 else None
        except (ValueError, TypeError): return None
    # A corporation appears once, using its newest known cached affiliation.
    membership = {}
    def identity_time(row):
        try: return utc(row["profile_at"] or row["identity_at"] or row["created_at"])
        except (ValueError, TypeError): return utc(row["created_at"])
    for row in sorted(rows, key=lambda r: (identity_time(r), r["kind"] == "corporation", r["id"])):
        cid = row["eve_id"] if row["kind"] == "corporation" else eid(row["corporation_id"])
        aid = eid(row["alliance_id"])
        known = aid is not None or row["profile_state"] == "available" or str(row["affiliation_available"]).lower() in {"true", "1"}
        if cid and known: membership[cid] = (aid, row["alliance_name"])
    alliances = {}
    def alliance(aid, name=None, unknown=False):
        key = str(aid) if aid else "unknown" if unknown else "none"
        source = orgs.get(("alliance", aid), {})
        return alliances.setdefault(key, dict(key=key, kind="alliance", eve_id=aid, id=source.get("id"),
            name=source.get("name") or name or (f"Alliance {aid}" if aid else "Alliance unknown" if unknown else "No alliance"),
            priority=source.get("priority", False), corporations={}))
    def corporation(cid, name=None):
        aid, aname = membership.get(cid, (None, None))
        parent = alliance(aid, aname, unknown=cid not in membership)
        key = str(cid) if cid else "unknown"
        source = orgs.get(("corporation", cid), {})
        return parent["corporations"].setdefault(key, dict(key=key, kind="corporation", eve_id=cid, id=source.get("id"),
            name=source.get("name") or name or (f"Corporation {cid}" if cid else "Corporation unknown"),
            priority=source.get("priority", False), pilots=[]))
    for row in rows:
        if row["kind"] == "alliance": alliance(row["eve_id"], row["name"])
        elif row["kind"] == "corporation": corporation(row["eve_id"], row["name"])
        else:
            corporation(eid(row["corporation_id"]), row["corporation_name"])["pilots"].append(
                {key: row[key] for key in ("id", "kind", "eve_id", "name", "priority")})
    term = q.strip().casefold()
    result = []
    for parent in alliances.values():
        corps = []
        for corp in parent["corporations"].values():
            pilots = sorted(corp["pilots"], key=order)
            if term and term not in parent["name"].casefold() and term not in corp["name"].casefold():
                pilots = [p for p in pilots if term in p["name"].casefold()]
                if not pilots: continue
            corps.append({**corp, "pilots": pilots, "pilot_count": len(pilots)})
        if corps or not term or term in parent["name"].casefold():
            result.append({**parent, "corporations": sorted(corps, key=order), "pilot_count": sum(c["pilot_count"] for c in corps)})
    return sorted(result, key=order)

def cached_organization(db, kind, eve_id):
    if kind not in {"corporation", "alliance"}: return None
    for alliance in catalog(db):
        if kind == "alliance" and alliance["eve_id"] == eve_id:
            return {"name": alliance["name"]}
        if kind == "corporation":
            for corp in alliance["corporations"]:
                if corp["eve_id"] == eve_id:
                    profile = {"name": corp["name"]}
                    if alliance["key"] != "unknown":
                        profile.update(alliance_id=alliance["eve_id"], alliance_name=alliance["name"], affiliation_available=True)
                    return profile
    return None

def remove_report(db, subject):
    # Lock/fence workers before clearing their owned records. Workers recheck
    # their job/monitor lease after network work and cannot repopulate deletion.
    db.execute(update(IntelCollection).where(IntelCollection.subject_id == subject.id)
        .values(status="cancelled", lease_token=None, lease_until=None))
    db.execute(update(IntelMembershipMonitor).where(IntelMembershipMonitor.subject_id == subject.id)
        .values(enabled=False, lease_token=None, lease_until=None, next_poll_at=None))
    for model in (IntelCollection, IntelMembershipMonitor, IntelMembershipSnapshot, IntelObservation, IntelSighting):
        db.execute(delete(model).where(model.subject_id == subject.id))
    # Scan observations belong to scans, not dossiers, and retain their privacy
    # and expiry-independent lifecycle. Canonical killmails are shared too.
    subject.archived = True
    subject.priority = False
    subject.public_data = {}
    subject.updated_at = datetime.now(timezone.utc)
