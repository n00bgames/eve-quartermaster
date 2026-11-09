"""Dossier retention and explicit priority targets."""
from alembic import op
import sqlalchemy as sa
revision = "0108_intel_subject_browser"
down_revision = "0107_manual_pos"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("intel_subjects", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("intel_subjects", sa.Column("priority", sa.Boolean(), nullable=False, server_default=sa.false()))
def downgrade():
    op.drop_column("intel_subjects", "priority")
    op.drop_column("intel_subjects", "archived")
