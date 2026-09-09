"""Private PI planning scenarios and durable calculation snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0079_pi_planning"
down_revision = "0078_hypernet_bid_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("pi_planning_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_pi_planning_scenarios_user_id", "pi_planning_scenarios", ["user_id"])
    op.create_table("pi_planning_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress_json", sa.JSON(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_json", sa.JSON()),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    for column in ("user_id", "status", "updated_at"):
        op.create_index(f"ix_pi_planning_jobs_{column}", "pi_planning_jobs", [column])


def downgrade():
    op.drop_table("pi_planning_jobs")
    op.drop_table("pi_planning_scenarios")
