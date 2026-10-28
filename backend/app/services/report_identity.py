"""Report attribution never falls back to an account/login name."""
from sqlalchemy import select, exists
from app.models import EveCharacter, EsiToken

def owned_characters(db, user):
    return list(db.scalars(select(EveCharacter).where(
        EveCharacter.owner_user_id == user.id,
        exists(select(EsiToken.id).where(EsiToken.character_id == EveCharacter.id,
            EsiToken.user_id == user.id, EsiToken.revoked_at.is_(None)))
    ).order_by(EveCharacter.name)))

def main_character(db, user):
    if user.main_character_id is None:
        return None
    return db.scalar(select(EveCharacter).where(
        EveCharacter.character_id == user.main_character_id,
        EveCharacter.owner_user_id == user.id,
        exists(select(EsiToken.id).where(EsiToken.character_id == EveCharacter.id,
            EsiToken.user_id == user.id, EsiToken.revoked_at.is_(None)))
    ))

def report_identity(db, user, anonymous=False):
    main = None if anonymous else main_character(db, user)
    return (main.name[:120], False) if main else ("Anonymous", True)
