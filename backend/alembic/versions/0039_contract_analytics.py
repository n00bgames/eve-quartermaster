"""make contract sync ownership-safe and add analytics exclusions

Revision ID: 0039_contract_analytics
Revises: 0038_mfg_activity_fields
Create Date: 2026-07-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0039_contract_analytics"
down_revision: Union[str, None] = "0038_mfg_activity_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE eve_corporations ADD COLUMN IF NOT EXISTS exclude_from_analytics BOOLEAN NOT NULL DEFAULT false")
    op.execute("UPDATE eve_corporations SET exclude_from_analytics = true WHERE hide_from_corporation_list = true")
    op.execute("ALTER TABLE eve_contracts DROP CONSTRAINT IF EXISTS uq_eve_contracts_contract_id")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_eve_contracts_character_contract "
        "ON eve_contracts (contract_id, character_id) "
        "WHERE scope_type = 'character' AND character_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_eve_contracts_corporation_contract "
        "ON eve_contracts (contract_id, corporation_id) "
        "WHERE scope_type = 'corporation' AND corporation_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_eve_contracts_corporation_contract")
    op.execute("DROP INDEX IF EXISTS uq_eve_contracts_character_contract")
    op.execute(
        "DELETE FROM eve_contracts newer USING eve_contracts older "
        "WHERE newer.contract_id = older.contract_id AND newer.id > older.id"
    )
    op.execute("ALTER TABLE eve_contracts ADD CONSTRAINT uq_eve_contracts_contract_id UNIQUE (contract_id)")
    op.execute("ALTER TABLE eve_corporations DROP COLUMN IF EXISTS exclude_from_analytics")
