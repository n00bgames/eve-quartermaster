"""Retain a market disposition after a HyperNet offer expires."""
from alembic import op
import sqlalchemy as sa

revision = "0084_hypernet_market_sale"
down_revision = "0083_plex_tracker"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hypernet_offers", sa.Column("market_sale", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("hypernet_offers", "market_sale")
