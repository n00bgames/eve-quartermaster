from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.characters import visible_characters
from app.models import Base, EsiToken, EveAlliance, EveCharacter, EveCorporation, User


class CharacterVisibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                User.__table__,
                EveAlliance.__table__,
                EveCorporation.__table__,
                EveCharacter.__table__,
                EsiToken.__table__,
            ],
        )
        self.db = Session(self.engine)
        self.host = User(email="host@example.test", display_name="Host", role="host")
        self.db.add(self.host)
        self.db.flush()
        self.sequence = 0

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def add_character(self, name: str, *, token_state: str) -> EveCharacter:
        self.sequence += 1
        character = EveCharacter(
            character_id=90_000_000 + self.sequence,
            name=name,
            owner_user_id=self.host.id,
        )
        self.db.add(character)
        self.db.flush()
        if token_state != "none":
            self.db.add(
                EsiToken(
                    user_id=self.host.id,
                    character_id=character.id,
                    scopes="esi-assets.read_assets.v1",
                    encrypted_refresh_token="encrypted",
                    revoked_at=datetime.now(timezone.utc) if token_state == "revoked" else None,
                )
            )
        self.db.commit()
        return character

    def test_only_characters_with_active_tokens_are_listed(self) -> None:
        active = self.add_character("Active Pilot", token_state="active")
        self.add_character("Unlinked Pilot", token_state="revoked")
        self.add_character("Historical Pilot", token_state="none")

        self.assertEqual([character.id for character in visible_characters(self.host, self.db)], [active.id])


if __name__ == "__main__":
    unittest.main()