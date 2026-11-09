"""Private analyst notes and retry-safe whole-scan character annotations."""
from alembic import op
import sqlalchemy as sa

revision = "0106_scan_character_notes"
down_revision = "0105_intel_membership"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("intel_scan_note_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_private", sa.Boolean(), nullable=False),
        sa.Column("pilot_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("author_user_id", "request_id", name="uq_intel_scan_note_request"))
    with op.batch_alter_table("intel_notes") as batch:
        batch.add_column(sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("scan_batch_id", sa.Integer()))
        batch.create_foreign_key("fk_intel_note_scan_batch", "intel_scan_note_batches", ["scan_batch_id"], ["id"], ondelete="SET NULL")
        batch.create_unique_constraint("uq_intel_note_scan_pilot", ["subject_id", "scan_batch_id"])


def downgrade():
    # Do not turn private notes into shared notes during rollback. Notes are not
    # reproducible source data, so require an explicit export/removal first.
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM intel_notes WHERE is_private = true")):
        raise RuntimeError("Export and explicitly remove private Intel notes before downgrading 0106")
    with op.batch_alter_table("intel_notes") as batch:
        batch.drop_constraint("uq_intel_note_scan_pilot", type_="unique")
        batch.drop_constraint("fk_intel_note_scan_batch", type_="foreignkey")
        batch.drop_column("scan_batch_id")
        batch.drop_column("is_private")
    op.drop_table("intel_scan_note_batches")
