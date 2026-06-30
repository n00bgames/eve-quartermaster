from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import get_current_user, require_role, serialize_user
from app.db.session import get_db
from app.models import AppSetting, AuditEvent, PrivateMessage, User
from app.services.audit import SUPPRESS_PEEK_NOTIFICATIONS, bool_setting, set_bool_setting
from app.services.permissions import can_view_section

router = APIRouter(prefix="/notifications", tags=["notifications"])


def public_user_name(user: User | None) -> str | None:
    if user is None:
        return None
    name = (user.display_name or "").strip()
    if name and "@" not in name:
        return name
    local_part = user.email.split("@", 1)[0].strip()
    return local_part or name or f"User {user.id}"


def serialize_public_user(user: User) -> dict[str, Any]:
    payload = serialize_user(user)
    payload["display_name"] = public_user_name(user) or payload["display_name"]
    return payload

def serialize_event(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "event_kind": event.event_kind,
        "title": event.title,
        "body": event.body,
        "actor_user_id": event.actor_user_id,
        "actor_display_name": public_user_name(event.actor),
        "recipient_user_id": event.recipient_user_id,
        "recipient_display_name": public_user_name(event.recipient),
        "character_id": event.character_id,
        "character_name": event.character.name if event.character else None,
        "is_read": event.is_read,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def serialize_message(message: PrivateMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "sender_user_id": message.sender_user_id,
        "sender_display_name": public_user_name(message.sender),
        "recipient_user_id": message.recipient_user_id,
        "recipient_display_name": public_user_name(message.recipient),
        "subject": message.subject,
        "body": message.body,
        "is_read": message.is_read,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


@router.get("")
def inbox(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    events = db.scalars(
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor), selectinload(AuditEvent.recipient), selectinload(AuditEvent.character))
        .where(AuditEvent.recipient_user_id == current_user.id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(50)
    ).all()
    messages = db.scalars(
        select(PrivateMessage)
        .options(selectinload(PrivateMessage.sender), selectinload(PrivateMessage.recipient))
        .where(PrivateMessage.recipient_user_id == current_user.id, PrivateMessage.recipient_deleted_at.is_(None))
        .order_by(PrivateMessage.created_at.desc(), PrivateMessage.id.desc())
        .limit(50)
    ).all()
    sent_messages = db.scalars(
        select(PrivateMessage)
        .options(selectinload(PrivateMessage.sender), selectinload(PrivateMessage.recipient))
        .where(PrivateMessage.sender_user_id == current_user.id, PrivateMessage.sender_deleted_at.is_(None))
        .order_by(PrivateMessage.created_at.desc(), PrivateMessage.id.desc())
        .limit(50)
    ).all()
    unread_count = sum(1 for event in events if not event.is_read) + sum(1 for message in messages if not message.is_read)
    users = db.scalars(select(User).order_by(User.display_name)).all()
    return {
        "unread_count": unread_count,
        "events": [serialize_event(event) for event in events],
        "messages": [serialize_message(message) for message in messages],
        "sent_messages": [serialize_message(message) for message in sent_messages],
        "users": [serialize_public_user(user) for user in users],
    }


@router.post("/read")
def mark_read(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    event_ids = [int(item) for item in payload.get("event_ids", [])]
    message_ids = [int(item) for item in payload.get("message_ids", [])]
    if event_ids:
        for event in db.scalars(select(AuditEvent).where(AuditEvent.id.in_(event_ids), AuditEvent.recipient_user_id == current_user.id)):
            event.is_read = True
    if message_ids:
        for message in db.scalars(select(PrivateMessage).where(PrivateMessage.id.in_(message_ids), PrivateMessage.recipient_user_id == current_user.id, PrivateMessage.recipient_deleted_at.is_(None))):
            message.is_read = True
    db.commit()
    return {"status": "read"}


@router.post("/messages")
def send_message(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    recipient_id = int(payload.get("recipient_user_id") or 0)
    subject = str(payload.get("subject") or "").strip()
    body = str(payload.get("body") or "").strip()
    if not recipient_id or not subject or not body:
        raise HTTPException(status_code=400, detail="Recipient, subject, and body are required")
    recipient = db.get(User, recipient_id)
    if recipient is None:
        raise HTTPException(status_code=404, detail="Recipient was not found")
    message = PrivateMessage(sender_user_id=current_user.id, recipient_user_id=recipient.id, subject=subject, body=body)
    db.add(message)
    db.commit()
    db.refresh(message)
    return serialize_message(message)



@router.delete("/messages/{message_id}")
def delete_message(message_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    message = db.get(PrivateMessage, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message was not found")
    if message.sender_user_id != current_user.id and message.recipient_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Message was not found")

    now = datetime.now(timezone.utc)
    if message.sender_user_id == current_user.id:
        message.sender_deleted_at = now
    if message.recipient_user_id == current_user.id:
        message.recipient_deleted_at = now

    if message.sender_deleted_at is not None and message.recipient_deleted_at is not None:
        db.delete(message)
    db.commit()
    return {"status": "deleted", "message_id": message_id}

@router.get("/audit")
def audit_log(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    if not can_view_section(current_user, "audit", db):
        raise HTTPException(status_code=403, detail="Audit Log permission is required")
    events = db.scalars(
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor), selectinload(AuditEvent.recipient), selectinload(AuditEvent.character))
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(250)
    ).all()
    return [serialize_event(event) for event in events]


@router.get("/settings")
def notification_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    return {"suppress_peek_notifications": bool_setting(db, SUPPRESS_PEEK_NOTIFICATIONS)}


@router.patch("/settings")
def update_notification_settings(payload: dict[str, Any], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_role(current_user, "admin")
    setting = set_bool_setting(db, SUPPRESS_PEEK_NOTIFICATIONS, bool(payload.get("suppress_peek_notifications", False)))
    db.commit()
    return {"suppress_peek_notifications": setting.value == "true"}


