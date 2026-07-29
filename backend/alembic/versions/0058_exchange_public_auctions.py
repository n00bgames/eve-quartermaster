"""Add external bidder identity fields for public auctions.

Revision ID: 0058_exchange_public_auctions
Revises: 0057_corporate_exchange
"""

from alembic import op
import sqlalchemy as sa

revision = "0058_exchange_public_auctions"
down_revision = "0057_corporate_exchange"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("exchange_bids", sa.Column("bidder_name", sa.String(255)))
    op.add_column("exchange_bids", sa.Column("bidder_contact", sa.String(255)))


def downgrade() -> None:
    op.drop_column("exchange_bids", "bidder_contact")
    op.drop_column("exchange_bids", "bidder_name")