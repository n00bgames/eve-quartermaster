"""Add doctrine management, skill plans, and SRP requests.

Revision ID: 0066_fleet_operations
Revises: 0065_analytics_retention_mode
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0066_fleet_operations"
down_revision: Union[str, None] = "0065_analytics_retention_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doctrine_priority_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False, server_default="select"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_doctrine_priority_fields_key", "doctrine_priority_fields", ["key"])
    op.create_index("ix_doctrine_priority_fields_is_active", "doctrine_priority_fields", ["is_active"])
    op.create_table(
        "doctrine_priority_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("doctrine_priority_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("value", sa.String(120), nullable=False),
        sa.Column("short_code", sa.String(32)),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("field_id", "value", name="uq_doctrine_priority_option_value"),
    )
    op.create_index("ix_doctrine_priority_options_field_id", "doctrine_priority_options", ["field_id"])
    op.create_table(
        "skill_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("fitting_id", sa.Integer(), sa.ForeignKey("character_fittings.id", ondelete="SET NULL")),
        sa.Column("source_doctrine_id", sa.Integer(), sa.ForeignKey("doctrines.id", ondelete="SET NULL")),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    for column in ("name", "owner_user_id", "character_id", "fitting_id", "source_doctrine_id", "source", "archived_at"):
        op.create_index(f"ix_skill_plans_{column}", "skill_plans", [column])
    op.create_table(
        "skill_plan_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("skill_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_level", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("introduced_by", sa.JSON(), nullable=False, server_default="[]"),
        sa.CheckConstraint("target_level >= 1 AND target_level <= 5", name="ck_skill_plan_target_level"),
        sa.UniqueConstraint("plan_id", "skill_type_id", name="uq_skill_plan_entry_skill"),
    )
    op.create_index("ix_skill_plan_entries_plan_id", "skill_plan_entries", ["plan_id"])
    op.create_index("ix_skill_plan_entries_skill_type_id", "skill_plan_entries", ["skill_type_id"])
    op.add_column("doctrines", sa.Column("purpose", sa.String(500)))
    op.add_column("doctrines", sa.Column("priority_code", sa.String(120)))
    op.add_column("doctrines", sa.Column("priority_values", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("doctrines", sa.Column("priority_code_manual", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("doctrines", sa.Column("fitting_id", sa.Integer(), sa.ForeignKey("character_fittings.id", ondelete="RESTRICT")))
    op.add_column("doctrines", sa.Column("fitting_snapshot", sa.JSON()))
    op.add_column("doctrines", sa.Column("notes", sa.Text()))
    op.add_column("doctrines", sa.Column("linked_skill_plan_id", sa.Integer(), sa.ForeignKey("skill_plans.id", ondelete="SET NULL")))
    op.add_column("doctrines", sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")))
    for column in ("priority_code", "fitting_id", "linked_skill_plan_id", "updated_by_user_id"):
        op.create_index(f"ix_doctrines_{column}", "doctrines", [column])
    op.create_table(
        "srp_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requesting_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fitting_id", sa.Integer(), sa.ForeignKey("character_fittings.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("doctrine_id", sa.Integer(), sa.ForeignKey("doctrines.id", ondelete="SET NULL")),
        sa.Column("character_name_snapshot", sa.String(255), nullable=False),
        sa.Column("fitting_name_snapshot", sa.String(255), nullable=False),
        sa.Column("ship_name_snapshot", sa.String(255)),
        sa.Column("doctrine_name_snapshot", sa.String(255)),
        sa.Column("loss_date", sa.Date(), nullable=False),
        sa.Column("loss_time", sa.Time(), nullable=False),
        sa.Column("loss_occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    for column in ("requesting_user_id", "character_id", "fitting_id", "doctrine_id", "loss_date", "loss_occurred_at", "status", "reviewed_by_user_id", "archived_at"):
        op.create_index(f"ix_srp_requests_{column}", "srp_requests", [column])


def downgrade() -> None:
    op.drop_table("srp_requests")
    for column in ("updated_by_user_id", "linked_skill_plan_id", "fitting_id", "priority_code"):
        op.drop_index(f"ix_doctrines_{column}", table_name="doctrines")
    for column in ("updated_by_user_id", "linked_skill_plan_id", "notes", "fitting_snapshot", "fitting_id", "priority_code_manual", "priority_values", "priority_code", "purpose"):
        op.drop_column("doctrines", column)
    op.drop_table("skill_plan_entries")
    op.drop_table("skill_plans")
    op.drop_table("doctrine_priority_options")
    op.drop_table("doctrine_priority_fields")
