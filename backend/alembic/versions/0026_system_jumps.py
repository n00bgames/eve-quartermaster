"""add system jump observations

Revision ID: 0026_system_jumps
Revises: 0025_contracts
Create Date: 2026-07-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_system_jumps"
down_revision = "0025_contracts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_jump_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("system_id", sa.BigInteger(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ship_jumps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="esi_system_jumps"),
        sa.Column("cached_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["system_id"], ["eve_systems.system_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("system_id", "observed_at", name="uq_system_jump_observation_bucket"),
    )
    for column in ("system_id", "observed_at", "source", "cached_at"):
        op.create_index(f"ix_system_jump_observations_{column}", "system_jump_observations", [column])


def downgrade() -> None:
    for column in reversed(("system_id", "observed_at", "source", "cached_at")):
        op.drop_index(f"ix_system_jump_observations_{column}", table_name="system_jump_observations")
    op.drop_table("system_jump_observations")