"""Celestial metadata from the SDE; reimport systems after upgrading."""
from alembic import op
import sqlalchemy as sa
revision = "0111_local_universe"
down_revision = "0110_structure_timers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("eve_system_objects", sa.Column("type_id", sa.Integer(), nullable=True))
    op.add_column("eve_system_objects", sa.Column("radius", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("eve_system_objects", "radius")
    op.drop_column("eve_system_objects", "type_id")
