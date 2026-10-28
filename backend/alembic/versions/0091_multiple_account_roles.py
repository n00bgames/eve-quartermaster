"""Additional account roles and multi-role invitations; preserve legacy roles."""
from alembic import op
import sqlalchemy as sa
revision = "0091_multiple_account_roles"
down_revision = "0090_local_scan_reports"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("user_role_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.UniqueConstraint("user_id", "role", name="uq_user_role_assignment"))
    op.create_index("ix_user_role_assignments_user_id", "user_role_assignments", ["user_id"])
    op.add_column("user_invites", sa.Column("roles_json", sa.JSON(), nullable=True))
def downgrade():
    op.drop_column("user_invites", "roles_json")
    op.drop_table("user_role_assignments")
