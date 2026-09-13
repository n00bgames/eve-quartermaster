"""System-relative celestial positions and token-scoped structure cache."""
from alembic import op
import sqlalchemy as sa

revision = "0080_system_distances"
down_revision = "0079_pi_planning"
branch_labels = None
depends_on = None

def coordinates():
    return [sa.Column(axis, sa.Float(), nullable=True) for axis in ("x", "y", "z")]

def upgrade():
    op.create_table("eve_system_objects",
        sa.Column("object_id", sa.BigInteger(), primary_key=True),
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("name", sa.String(255), nullable=False), *coordinates(),
        sa.Column("source", sa.String(12), nullable=False))
    op.create_index("ix_eve_system_objects_system_id", "eve_system_objects", ["system_id"])
    op.create_table("system_object_syncs",
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id"), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.String(255), nullable=False))
    op.create_table("navigation_structures",
        sa.Column("token_id", sa.Integer(), sa.ForeignKey("esi_tokens.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("structure_id", sa.BigInteger(), primary_key=True),
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False), *coordinates(),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_navigation_structures_system_id", "navigation_structures", ["system_id"])

def downgrade():
    op.drop_table("navigation_structures")
    op.drop_table("system_object_syncs")
    op.drop_table("eve_system_objects")
