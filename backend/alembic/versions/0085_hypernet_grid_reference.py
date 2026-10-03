"""Temporary, private HyperNet node grid reference."""
from alembic import op
import sqlalchemy as sa

revision = "0085_hypernet_grid_reference"
down_revision = "0084_hypernet_market_sale"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hypernet_offers", sa.Column("grid_reference", sa.JSON(), nullable=True))
    op.add_column("hypernet_offers", sa.Column("grid_reference_data", sa.LargeBinary(), nullable=True))


def downgrade():
    op.drop_column("hypernet_offers", "grid_reference_data")
    op.drop_column("hypernet_offers", "grid_reference")
