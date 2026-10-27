"""Fleet assignments, immutable fitting snapshots, roster and presets."""
from alembic import op
import sqlalchemy as sa
revision = "0088_fleet_assignments"
down_revision = "0087_hypernet_pause"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("fleet_assignment_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("briefing", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_fleet_assignment_status"))
    op.create_index("ix_fleet_assignment_operations_status", "fleet_assignment_operations", ["status"])
    op.create_table("fleet_assignment_pilots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_id", sa.Integer(), sa.ForeignKey("fleet_assignment_operations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("character_eve_id", sa.BigInteger()),
        sa.Column("slot_key", sa.String(36)),
        sa.Column("fitting_snapshot", sa.JSON()),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("operation_id", "normalized_name", name="uq_fleet_assignment_pilot_name"),
        sa.UniqueConstraint("operation_id", "character_eve_id", name="uq_fleet_assignment_pilot_character"))
    op.create_index("ix_fleet_assignment_pilots_operation_id", "fleet_assignment_pilots", ["operation_id"])
    op.create_index("ix_fleet_assignment_pilots_character_eve_id", "fleet_assignment_pilots", ["character_eve_id"])
    op.create_table("fleet_assignment_presets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("briefing", sa.Text(), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))

def downgrade():
    op.drop_table("fleet_assignment_presets")
    op.drop_table("fleet_assignment_pilots")
    op.drop_table("fleet_assignment_operations")
