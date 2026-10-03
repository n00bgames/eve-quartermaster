"""Manual HyperNet seeded and winning node positions."""
from alembic import op
import sqlalchemy as sa

revision = "0082_hypernet_node_positions"
down_revision = "0081_mission_atlas"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hypernet_offers", sa.Column("node_map", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("hypernet_offers", "node_map")
