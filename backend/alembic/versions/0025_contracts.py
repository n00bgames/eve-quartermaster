"""add ESI contracts

Revision ID: 0025_contracts
Revises: 0024_dogma_effects
Create Date: 2026-07-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_contracts"
down_revision = "0024_dogma_effects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eve_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("scope_type", sa.String(length=24), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("corporation_id", sa.Integer(), nullable=True),
        sa.Column("issuer_id", sa.BigInteger(), nullable=True),
        sa.Column("issuer_corporation_id", sa.BigInteger(), nullable=True),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column("acceptor_id", sa.BigInteger(), nullable=True),
        sa.Column("for_corporation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("contract_type", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("availability", sa.String(length=40), nullable=True),
        sa.Column("date_issued", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_expired", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_accepted", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_completed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_location_id", sa.BigInteger(), nullable=True),
        sa.Column("end_location_id", sa.BigInteger(), nullable=True),
        sa.Column("start_location_name", sa.String(length=255), nullable=True),
        sa.Column("end_location_name", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Numeric(24, 2), nullable=True),
        sa.Column("reward", sa.Numeric(24, 2), nullable=True),
        sa.Column("collateral", sa.Numeric(24, 2), nullable=True),
        sa.Column("buyout", sa.Numeric(24, 2), nullable=True),
        sa.Column("volume", sa.Numeric(24, 2), nullable=True),
        sa.Column("days_to_complete", sa.Integer(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["character_id"], ["eve_characters.id"]),
        sa.ForeignKeyConstraint(["corporation_id"], ["eve_corporations.id"]),
        sa.UniqueConstraint("contract_id", name="uq_eve_contracts_contract_id"),
    )
    for column in ("contract_id", "scope_type", "owner_user_id", "character_id", "corporation_id", "issuer_id", "issuer_corporation_id", "assignee_id", "acceptor_id", "contract_type", "status", "availability", "date_issued", "date_expired", "start_location_id", "end_location_id", "last_synced_at"):
        op.create_index(f"ix_eve_contracts_{column}", "eve_contracts", [column])


def downgrade() -> None:
    for column in reversed(("contract_id", "scope_type", "owner_user_id", "character_id", "corporation_id", "issuer_id", "issuer_corporation_id", "assignee_id", "acceptor_id", "contract_type", "status", "availability", "date_issued", "date_expired", "start_location_id", "end_location_id", "last_synced_at")):
        op.drop_index(f"ix_eve_contracts_{column}", table_name="eve_contracts")
    op.drop_table("eve_contracts")
