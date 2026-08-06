from __future__ import annotations

import unittest
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.characters import can_view_character_isk_values, update_character, visible_characters
from app.models import Base, CharacterWalletJournalEntry, CharacterWalletSnapshot, EsiToken, EveAlliance, EveCharacter, EveCorporation, SnapshotMetric, SnapshotRun, User


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
                SnapshotRun.__table__,
                SnapshotMetric.__table__,
                CharacterWalletSnapshot.__table__,
                CharacterWalletJournalEntry.__table__,
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

    def test_opted_out_character_isk_values_have_no_staff_override(self) -> None:
        character = self.add_character("Private Pilot", token_state="active")
        character.sync_opt_out = True
        other_host = User(email="other-host@example.test", display_name="Other Host", role="host")
        self.db.add(other_host)
        self.db.commit()

        self.assertTrue(can_view_character_isk_values(self.host, character))
        self.assertFalse(can_view_character_isk_values(other_host, character))

        character.sync_opt_out = False
        self.assertTrue(can_view_character_isk_values(other_host, character))

    def test_wallet_opt_out_purges_history_and_current_balance(self) -> None:
        character = self.add_character("Wallet Owner", token_state="active")
        character.current_wallet_balance = 1_000_000
        run = SnapshotRun(scope_type="character", scope_id=character.id, source="character_wallet", status="success")
        self.db.add(run)
        self.db.flush()
        self.db.add(CharacterWalletSnapshot(snapshot_run_id=run.id, character_id=character.id, character_eve_id=character.character_id, character_name=character.name, balance=1_000_000))
        self.db.add(CharacterWalletJournalEntry(character_id=character.id, reference_id=123, occurred_at=datetime.now(timezone.utc), reference_type="market_transaction", amount=-100))
        self.db.add(SnapshotMetric(snapshot_run_id=run.id, owner_type="character", owner_id=character.id, owner_name=character.name, metric_key="character_wallet.balance", metric_value=1_000_000))
        self.db.commit()

        result = update_character(character.id, {"wallet_history_opt_out": True}, self.host, self.db)

        self.assertTrue(result["wallet_history_opt_out"])
        self.assertIsNone(result["current_wallet_balance"])
        self.assertEqual(self.db.query(CharacterWalletSnapshot).count(), 0)
        self.assertEqual(self.db.query(CharacterWalletJournalEntry).count(), 0)
        self.assertEqual(self.db.query(SnapshotMetric).filter(SnapshotMetric.metric_key == "character_wallet.balance").count(), 0)

    def test_only_owner_can_opt_in_to_corporation_wallet_analytics(self) -> None:
        character = self.add_character("Consent Pilot", token_state="active")
        other_host = User(email="consent-host@example.test", display_name="Other Host", role="host")
        self.db.add(other_host)
        self.db.commit()

        with self.assertRaises(HTTPException):
            update_character(character.id, {"wallet_corporation_analytics_opt_in": True}, other_host, self.db)
        self.db.rollback()
        self.assertFalse(self.db.get(EveCharacter, character.id).wallet_corporation_analytics_opt_in)

        result = update_character(character.id, {"wallet_corporation_analytics_opt_in": True}, self.host, self.db)
        self.assertTrue(result["wallet_corporation_analytics_opt_in"])

    def test_only_characters_with_active_tokens_are_listed(self) -> None:
        active = self.add_character("Active Pilot", token_state="active")
        self.add_character("Unlinked Pilot", token_state="revoked")
        self.add_character("Historical Pilot", token_state="none")

        self.assertEqual([character.id for character in visible_characters(self.host, self.db)], [active.id])


if __name__ == "__main__":
    unittest.main()