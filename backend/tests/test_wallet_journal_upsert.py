from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from app.api.esi import (
    CHARACTER_WALLET_JOURNAL_UPSERT_BATCH_SIZE,
    POSTGRES_BIND_PARAMETER_LIMIT,
    compact_wallet_sync_error,
    upsert_character_wallet_journal_rows,
)


class WalletJournalUpsertTests(unittest.TestCase):
    def test_wallet_failure_message_omits_bulk_parameter_dump(self) -> None:
        message = compact_wallet_sync_error(RuntimeError("duplicate row\n[parameters: {'private': 'bulk'}]"))
        self.assertEqual(message, "duplicate row")

    def test_wallet_failure_message_omits_bulk_sql_statement(self) -> None:
        message = compact_wallet_sync_error(
            RuntimeError("(psycopg.OperationalError) parameter limit exceeded\n[SQL: INSERT INTO private_data ...]")
        )
        self.assertEqual(message, "(psycopg.OperationalError) parameter limit exceeded")

    def test_duplicate_esi_references_are_collapsed_into_one_atomic_upsert(self) -> None:
        db = MagicMock()
        rows = [
            {"id": 77, "date": "2026-08-08T12:00:00Z", "ref_type": "market_transaction", "amount": -10, "context_id": 900},
            {"id": 77, "date": "2026-08-08T12:00:00Z", "ref_type": "market_transaction", "amount": -12, "context_id": 900},
        ]
        transactions = {900: {"type_id": 34, "quantity": 2, "unit_price": 6, "is_buy": True}}

        count = upsert_character_wallet_journal_rows(
            db,
            character_id=5,
            journal_rows=rows,
            transactions=transactions,
            transaction_names={34: "Tritanium"},
            synced_at=datetime(2026, 8, 8, 13, tzinfo=timezone.utc),
        )

        self.assertEqual(count, 1)
        db.execute.assert_called_once()
        statement = db.execute.call_args.args[0]
        compiled = statement.compile(dialect=postgresql.dialect())
        self.assertIn("ON CONFLICT ON CONSTRAINT uq_character_wallet_journal_reference DO UPDATE", str(compiled))
        self.assertIn(-12, compiled.params.values())
        self.assertIn("Tritanium", compiled.params.values())
        self.assertNotIn("corporation_eve_id_at_import = excluded.corporation_eve_id_at_import", str(compiled))

    def test_large_wallet_history_is_split_below_postgres_parameter_limit(self) -> None:
        db = MagicMock()
        row_count = (CHARACTER_WALLET_JOURNAL_UPSERT_BATCH_SIZE * 2) + 1
        rows = [
            {
                "id": reference_id,
                "date": "2026-08-08T12:00:00Z",
                "ref_type": "player_donation",
                "amount": reference_id,
            }
            for reference_id in range(1, row_count + 1)
        ]

        count = upsert_character_wallet_journal_rows(
            db,
            character_id=5,
            journal_rows=rows,
            transactions={},
            transaction_names={},
            synced_at=datetime(2026, 8, 8, 13, tzinfo=timezone.utc),
        )

        self.assertEqual(count, row_count)
        self.assertEqual(db.execute.call_count, 3)
        for call in db.execute.call_args_list:
            compiled = call.args[0].compile(dialect=postgresql.dialect())
            self.assertLessEqual(len(compiled.params), POSTGRES_BIND_PARAMETER_LIMIT)
            self.assertIn("ON CONFLICT ON CONSTRAINT uq_character_wallet_journal_reference DO UPDATE", str(compiled))


if __name__ == "__main__":
    unittest.main()
