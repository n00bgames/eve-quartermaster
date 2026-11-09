"""Analyst notes, bulk scan tagging, visibility and paged character search."""
from datetime import datetime, timezone
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import func, insert, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import User
from app.models.intel import IntelNote, IntelScanNoteBatch, IntelSubject
from app.services.permissions import quartermaster_read_only


def visible(user):
    return or_(IntelNote.is_private.is_(False), IntelNote.author_user_id == user.id)


def require_notes(db, user, write=False):
    from app.services.intel_reports import require_intel
    require_intel(user, db)
    if write and quartermaster_read_only(user, db):
        raise HTTPException(403, "Your role cannot add character notes")


def available(db, user, write=False):
    try:
        require_notes(db, user, write=write)
        return True
    except HTTPException:
        return False


def clean_body(body):
    body = body.strip()
    if not body or len(body) > 5000 or "\x00" in body:
        raise HTTPException(422, "Write a note of 1–5,000 characters without null characters")
    return body


def chunks(values, size=400):
    values = list(values)
    for start in range(0, len(values), size):
        yield values[start:start + size]


def conflict_insert(db, model):
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        return pg_insert(model)
    if dialect == "sqlite":
        return sqlite_insert(model)
    raise HTTPException(503, "Character notes require PostgreSQL or SQLite")


def add_scan_note(db, user, report, body, is_private, request_id):
    require_notes(db, user, write=True)
    body = clean_body(body)
    pilots = {int(p["character_id"]): p["name"] for p in report.payload.get("pilots", [])
              if isinstance(p.get("character_id"), int) and not isinstance(p["character_id"], bool)
              and 0 < p["character_id"] <= 2147483647 and isinstance(p.get("name"), str)}
    if not pilots:
        raise HTTPException(422, "This scan has no resolved characters to annotate")
    fingerprint = sha256(report.token.encode()).hexdigest()
    at = datetime.now(timezone.utc)
    statement = conflict_insert(db, IntelScanNoteBatch).values(author_user_id=user.id,
        request_id=str(request_id), source_hash=fingerprint, body=body, is_private=is_private,
        pilot_count=len(pilots), created_at=at).on_conflict_do_nothing(index_elements=["author_user_id", "request_id"]).returning(IntelScanNoteBatch.id)
    batch_id = db.scalar(statement)
    if batch_id is None:
        batch = db.scalar(select(IntelScanNoteBatch).where(IntelScanNoteBatch.author_user_id == user.id,
            IntelScanNoteBatch.request_id == str(request_id)))
        if not batch or (batch.source_hash, batch.body, batch.is_private) != (fingerprint, body, is_private):
            raise HTTPException(409, "This note request was already used for different content; start a new note")
        return {"batch_id": batch.id, "character_count": batch.pilot_count, "created": 0, "replayed": True, "is_private": is_private}
    # Resolve only IDs already established in the server's stored scan. This
    # operation creates no ESI requests, collection jobs or combat evidence.
    subject_ids = []
    for group in chunks(pilots):
        values = [{"kind": "character", "eve_id": eid, "name": pilots[eid],
                   "public_data": {}, "created_by_user_id": user.id, "created_at": at, "updated_at": at} for eid in group]
        db.execute(conflict_insert(db, IntelSubject).values(values)
            .on_conflict_do_nothing(index_elements=["kind", "eve_id"]))
        subject_ids.extend(db.scalars(select(IntelSubject.id).where(IntelSubject.kind == "character", IntelSubject.eve_id.in_(group))))
    if len(subject_ids) != len(pilots):
        raise HTTPException(409, "Character identities changed; reload the scan and retry")
    for group in chunks(subject_ids):
        db.execute(insert(IntelNote), [{"subject_id": sid, "author_user_id": user.id,
            "body": body, "is_private": is_private, "scan_batch_id": batch_id, "created_at": at} for sid in group])
    return {"batch_id": batch_id, "character_count": len(pilots), "created": len(pilots), "replayed": False, "is_private": is_private}


def search(db, user, text, offset, limit):
    require_notes(db, user)
    text = text.strip()
    if not text:
        return {"rows": [], "total": 0, "offset": offset, "limit": limit, "query": ""}
    # contains(autoescape=True) treats % and _ as literal note text, not LIKE
    # wildcard instructions. Parameter binding handles all user content.
    filters = [visible(user), func.lower(IntelNote.body).contains(text.lower(), autoescape=True), IntelSubject.kind == "character"]
    matching = select(IntelSubject.id).join(IntelNote, IntelNote.subject_id == IntelSubject.id).where(*filters).distinct()
    total = db.scalar(select(func.count()).select_from(matching.subquery())) or 0
    subjects = db.scalars(select(IntelSubject).where(IntelSubject.id.in_(matching))
        .order_by(func.lower(IntelSubject.name), IntelSubject.eve_id).offset(offset).limit(limit)).all()
    ids = [s.id for s in subjects]
    notes, counts = previews(db, user, ids, text)
    return {"rows": [{"subject_id": s.id, "character_id": s.eve_id, "name": s.name,
                      "notes": notes.get(s.id, []), "matching_note_count": counts.get(s.id, 0)} for s in subjects],
            "total": total, "offset": offset, "limit": limit, "query": text}


def previews(db, user, subject_ids, text=None):
    notes, counts = {}, {}
    for group in chunks(subject_ids):
        query = select(IntelNote.id, IntelNote.subject_id, IntelNote.body, IntelNote.is_private,
            User.display_name.label("author"), IntelNote.created_at,
            func.row_number().over(partition_by=IntelNote.subject_id, order_by=IntelNote.id.desc()).label("position"),
            func.count().over(partition_by=IntelNote.subject_id).label("total"))
        query = query.join(User, User.id == IntelNote.author_user_id).where(IntelNote.subject_id.in_(group), visible(user))
        if text:
            query = query.where(func.lower(IntelNote.body).contains(text.lower(), autoescape=True))
        ranked = query.subquery()
        for row in db.execute(select(ranked).where(ranked.c.position <= 3).order_by(ranked.c.subject_id, ranked.c.position)).mappings():
            notes.setdefault(row["subject_id"], []).append({"id": row["id"], "body": row["body"][:300],
                "truncated": len(row["body"]) > 300, "is_private": row["is_private"],
                "author": row["author"], "created_at": row["created_at"]})
            counts[row["subject_id"]] = row["total"]
    return notes, counts


def scan_notes(db, user, report):
    require_notes(db, user)
    pilots = {p["character_id"] for p in report.payload.get("pilots", [])}
    mapping = {}
    for group in chunks(pilots):
        mapping.update({sid: eid for sid, eid in db.execute(select(IntelSubject.id, IntelSubject.eve_id)
            .where(IntelSubject.kind == "character", IntelSubject.eve_id.in_(group)))})
    notes, counts = previews(db, user, mapping)
    return {str(eid): {"subject_id": sid, "notes": notes.get(sid, []), "total": counts.get(sid, 0)}
            for sid, eid in mapping.items() if counts.get(sid, 0)}
