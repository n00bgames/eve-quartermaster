"""Persist the creator's chosen corporation for battle-report management."""
from alembic import op
import sqlalchemy as sa

revision = "0094_battle_report_corporation"
down_revision = "0093_report_privacy"
branch_labels = None
depends_on = None


def upgrade():
    # Never infer historical creator affiliation from the battle's selected pilot.
    op.add_column("battle_report_shares", sa.Column("corporation_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_battle_report_shares_corporation_id", "battle_report_shares", ["corporation_id"])


def downgrade():
    op.drop_index("ix_battle_report_shares_corporation_id", table_name="battle_report_shares")
    with op.batch_alter_table("battle_report_shares") as batch:
        batch.drop_column("corporation_id")
