"""These preferences pause new EQM records, never in-game HyperNet access."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EveCharacter, HyperNetCharacterPause, HyperNetSetting, User


def lock_pause_preferences(db: Session, user: User):
    # Serialize pause changes and creation for this user, even without a settings row yet.
    db.scalar(select(User).where(User.id == user.id).with_for_update())


def pause_payload(db: Session, user: User):
    setting = db.get(HyperNetSetting, user.id, populate_existing=True)
    account_paused = bool(setting and setting.paused)
    paused = set(db.scalars(select(HyperNetCharacterPause.character_id).where(
        HyperNetCharacterPause.user_id == user.id, HyperNetCharacterPause.paused.is_(True),
    )))
    characters = db.scalars(select(EveCharacter).where(EveCharacter.owner_user_id == user.id)
                           .order_by(EveCharacter.name, EveCharacter.id)).all()
    return {"account_paused": account_paused, "characters": [
        {"id": row.id, "name": row.name, "paused": row.id in paused,
         "effective_paused": account_paused or row.id in paused} for row in characters
    ]}


def require_new_hypernet_record(db: Session, user: User, character_id: int):
    lock_pause_preferences(db, user)
    setting = db.get(HyperNetSetting, user.id, populate_existing=True)
    if setting and setting.paused:
        raise HTTPException(403, "HyperNet is temporarily paused for your EQM account. Resume it in HyperNet pause controls to add new bids or offers.")
    pause = db.get(HyperNetCharacterPause, (user.id, character_id), populate_existing=True)
    if pause and pause.paused:
        raise HTTPException(403, "HyperNet is temporarily paused for this character in EQM. Resume it in HyperNet pause controls to add new bids or offers.")
