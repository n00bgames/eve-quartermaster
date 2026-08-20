"""Preserve corporation identity on character wallet journal history.

Revision ID: 0072_bounty_analytics
Revises: 0071_killboard_entity_names
"""

from alembic import op
import sqlalchemy as sa


revision = "0072_bounty_analytics"
down_revision = "0071_killboard_entity_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("character_wallet_journal_entries", sa.Column("corporation_eve_id_at_import", sa.BigInteger()))
    op.add_column("character_wallet_journal_entries", sa.Column("corporation_name_at_import", sa.String(length=255)))
    op.create_index(
        "ix_character_wallet_journal_corporation_at_import",
        "character_wallet_journal_entries",
        ["corporation_eve_id_at_import"],
    )
    op.execute(
        """
        UPDATE character_wallet_journal_entries AS journal
        SET corporation_eve_id_at_import = corporation.corporation_id,
            corporation_name_at_import = corporation.name
        FROM eve_characters AS character
        LEFT JOIN eve_corporations AS corporation ON corporation.id = character.corporation_id
        WHERE journal.character_id = character.id
          AND journal.corporation_eve_id_at_import IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_character_wallet_journal_corporation_at_import", table_name="character_wallet_journal_entries")
    op.drop_column("character_wallet_journal_entries", "corporation_name_at_import")
    op.drop_column("character_wallet_journal_entries", "corporation_eve_id_at_import")
