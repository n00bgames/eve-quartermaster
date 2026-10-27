"""Public intel subjects, change-only observations, leased jobs and compact cache."""
from alembic import op
import sqlalchemy as sa
revision="0089_intel_reports"
down_revision="0088_fleet_assignments"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("intel_subjects",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("kind",sa.String(16),nullable=False),sa.Column("eve_id",sa.BigInteger(),nullable=False),sa.Column("name",sa.String(255),nullable=False),sa.Column("public_data",sa.JSON(),nullable=False),
        sa.Column("created_by_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint("kind","eve_id",name="uq_intel_subject_entity"),sa.CheckConstraint("kind IN ('character','corporation','alliance')",name="ck_intel_subject_kind"))
    op.create_index("ix_intel_subjects_eve_id","intel_subjects",["eve_id"])
    op.create_index("ix_intel_subjects_name","intel_subjects",["name"])
    op.create_table("intel_observations",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("subject_id",sa.Integer(),sa.ForeignKey("intel_subjects.id",ondelete="CASCADE"),nullable=False),sa.Column("source",sa.String(24),nullable=False),sa.Column("fingerprint",sa.String(64),nullable=False),sa.Column("payload",sa.JSON(),nullable=False),sa.Column("observed_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index("ix_intel_observations_subject_id","intel_observations",["subject_id"])
    op.create_index("ix_intel_observations_observed_at","intel_observations",["observed_at"])
    op.create_table("intel_collections",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("subject_id",sa.Integer(),sa.ForeignKey("intel_subjects.id",ondelete="CASCADE"),nullable=False),sa.Column("requested_by_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("status",sa.String(16),nullable=False),sa.Column("from_at",sa.DateTime(timezone=True),nullable=False),sa.Column("to_at",sa.DateTime(timezone=True),nullable=False),sa.Column("max_pages",sa.Integer(),nullable=False),sa.Column("stage",sa.String(16),nullable=False),sa.Column("page",sa.Integer(),nullable=False),
        sa.Column("imported_count",sa.Integer(),nullable=False),sa.Column("reused_count",sa.Integer(),nullable=False),sa.Column("failed_count",sa.Integer(),nullable=False),sa.Column("coverage",sa.JSON(),nullable=False),sa.Column("errors",sa.JSON(),nullable=False),sa.Column("retry_count",sa.Integer(),nullable=False),
        sa.Column("available_at",sa.DateTime(timezone=True)),sa.Column("lease_token",sa.String(36)),sa.Column("lease_until",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("finished_at",sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('queued','running','completed','partial','failed','cancelled')",name="ck_intel_collection_status"))
    for key in ("subject_id","status","available_at","lease_until"):op.create_index(f"ix_intel_collections_{key}","intel_collections",[key])
    op.create_index("uq_intel_active_collection","intel_collections",["subject_id"],unique=True,postgresql_where=sa.text("status IN ('queued','running')"),sqlite_where=sa.text("status IN ('queued','running')"))
    op.create_table("intel_source_cache",sa.Column("key",sa.String(96),primary_key=True),sa.Column("payload",sa.JSON(),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_intel_source_cache_expires_at","intel_source_cache",["expires_at"])
    op.create_table("intel_notes",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("subject_id",sa.Integer(),sa.ForeignKey("intel_subjects.id",ondelete="CASCADE"),nullable=False),sa.Column("author_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),sa.Column("body",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index("ix_intel_notes_subject_id","intel_notes",["subject_id"])

def downgrade():
    for table in ("intel_notes","intel_source_cache","intel_collections","intel_observations","intel_subjects"):op.drop_table(table)
