from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting, AuditEvent, EveCharacter, User

SUPPRESS_PEEK_NOTIFICATIONS = "suppress_peek_notifications"


def bool_setting(db: Session, key: str, default: bool = False) -> bool:
    setting = db.get(AppSetting, key)
    if setting is None:
        return default
    return setting.value.lower() in {"1", "true", "yes", "on"}


def set_bool_setting(db: Session, key: str, value: bool) -> AppSetting:
    setting = db.get(AppSetting, key)
    if setting is None:
        setting = AppSetting(key=key, value="true" if value else "false")
        db.add(setting)
    else:
        setting.value = "true" if value else "false"
    return setting


def record_audit_event(
    db: Session,
    *,
    event_kind: str,
    title: str,
    body: str | None = None,
    actor_user: User | None = None,
    recipient_user_id: int | None = None,
    character: EveCharacter | None = None,
    respect_suppression: bool = False,
) -> AuditEvent:
    notify_recipient_id = recipient_user_id
    if respect_suppression and bool_setting(db, SUPPRESS_PEEK_NOTIFICATIONS):
        notify_recipient_id = None
    event = AuditEvent(
        event_kind=event_kind,
        title=title,
        body=body,
        actor_user_id=actor_user.id if actor_user else None,
        recipient_user_id=notify_recipient_id,
        character_id=character.id if character else None,
    )
    db.add(event)
    db.flush()
    return event


def notify_if_other_user_synced_character(
    db: Session,
    *,
    sync_label: str,
    actor_user: User,
    character: EveCharacter,
    detail: str,
) -> None:
    recipient_user_id = character.owner_user_id
    title = f"{character.name} {sync_label} synced"
    body = f"{actor_user.display_name} synced {sync_label} for {character.name}. {detail}".strip()
    record_audit_event(
        db,
        event_kind=f"character_{sync_label.replace(' ', '_')}_sync",
        title=title,
        body=body,
        actor_user=actor_user,
        recipient_user_id=recipient_user_id if recipient_user_id and recipient_user_id != actor_user.id else None,
        character=character,
        respect_suppression=True,
    )