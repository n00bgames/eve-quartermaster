"""add manufacturing ledger

Revision ID: 0034_manufacturing_ledger
Revises: 0033_jump_clones_implants
Create Date: 2026-07-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0034_manufacturing_ledger"
down_revision: Union[str, None] = "0033_jump_clones_implants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "manufacturing_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("output_type_id", sa.Integer(), nullable=True),
        sa.Column("output_quantity", sa.Integer(), nullable=False),
        sa.Column("activity_flags", sa.String(length=160), nullable=False, server_default="manufacturing"),
        sa.Column("research_runs", sa.Integer(), nullable=True),
        sa.Column("me_start", sa.Integer(), nullable=True),
        sa.Column("me_target", sa.Integer(), nullable=True),
        sa.Column("te_start", sa.Integer(), nullable=True),
        sa.Column("te_target", sa.Integer(), nullable=True),
        sa.Column("copy_runs", sa.Integer(), nullable=True),
        sa.Column("invention_runs", sa.Integer(), nullable=True),
        sa.Column("invention_successes", sa.Integer(), nullable=True),
        sa.Column("output_disposition", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("output_sale_price", sa.Numeric(24, 2), nullable=True),
        sa.Column("output_sale_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("cost_to_run", sa.Numeric(24, 2), nullable=True),
        sa.Column("time_to_run", sa.String(length=80), nullable=True),
        sa.Column("date_started", sa.Date(), nullable=True),
        sa.Column("time_started", sa.Time(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["output_type_id"], ["eve_types.type_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_manufacturing_jobs_activity_flags"), "manufacturing_jobs", ["activity_flags"], unique=False)
    op.create_index(op.f("ix_manufacturing_jobs_created_by_user_id"), "manufacturing_jobs", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_manufacturing_jobs_name"), "manufacturing_jobs", ["name"], unique=False)
    op.create_index(op.f("ix_manufacturing_jobs_output_disposition"), "manufacturing_jobs", ["output_disposition"], unique=False)
    op.create_index(op.f("ix_manufacturing_jobs_output_type_id"), "manufacturing_jobs", ["output_type_id"], unique=False)
    op.create_index(op.f("ix_manufacturing_jobs_status"), "manufacturing_jobs", ["status"], unique=False)

    op.create_table(
        "manufacturing_job_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("item_type_id", sa.Integer(), nullable=True),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(24, 2), nullable=True),
        sa.Column("price_paid", sa.Numeric(24, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["item_type_id"], ["eve_types.type_id"]),
        sa.ForeignKeyConstraint(["job_id"], ["manufacturing_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_manufacturing_job_items_category"), "manufacturing_job_items", ["category"], unique=False)
    op.create_index(op.f("ix_manufacturing_job_items_item_type_id"), "manufacturing_job_items", ["item_type_id"], unique=False)
    op.create_index(op.f("ix_manufacturing_job_items_job_id"), "manufacturing_job_items", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_manufacturing_job_items_job_id"), table_name="manufacturing_job_items")
    op.drop_index(op.f("ix_manufacturing_job_items_item_type_id"), table_name="manufacturing_job_items")
    op.drop_index(op.f("ix_manufacturing_job_items_category"), table_name="manufacturing_job_items")
    op.drop_table("manufacturing_job_items")
    op.drop_index(op.f("ix_manufacturing_jobs_status"), table_name="manufacturing_jobs")
    op.drop_index(op.f("ix_manufacturing_jobs_activity_flags"), table_name="manufacturing_jobs")
    op.drop_index(op.f("ix_manufacturing_jobs_output_type_id"), table_name="manufacturing_jobs")
    op.drop_index(op.f("ix_manufacturing_jobs_output_disposition"), table_name="manufacturing_jobs")
    op.drop_index(op.f("ix_manufacturing_jobs_name"), table_name="manufacturing_jobs")
    op.drop_index(op.f("ix_manufacturing_jobs_created_by_user_id"), table_name="manufacturing_jobs")
    op.drop_table("manufacturing_jobs")

