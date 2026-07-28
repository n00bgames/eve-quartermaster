"""add configurable recruiting workflow

Revision ID: 0050_recruiting
Revises: 0049_mining_mineral_shares
Create Date: 2026-07-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050_recruiting"
down_revision: Union[str, None] = "0049_mining_mineral_shares"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "recruitment_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("setup_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("corporation_eve_id", sa.Integer()), sa.Column("corporation_name", sa.String(255)),
        sa.Column("corporation_ticker", sa.String(20)), sa.Column("corporation_logo_url", sa.String(500)),
        sa.Column("alliance_eve_id", sa.Integer()), sa.Column("alliance_name", sa.String(255)),
        sa.Column("alliance_ticker", sa.String(20)), sa.Column("alliance_logo_url", sa.String(500)),
        sa.Column("ceo_character_eve_id", sa.Integer()), sa.Column("ceo_character_name", sa.String(255)),
        sa.Column("ceo_portrait_url", sa.String(500)), sa.Column("ceo_manual_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("primary_timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("activity_window_start", sa.String(5), nullable=False, server_default="18:00"),
        sa.Column("activity_window_end", sa.String(5), nullable=False, server_default="23:00"),
        sa.Column("public_headline", sa.String(255), nullable=False, server_default="Recruitment"),
        sa.Column("public_summary", sa.Text(), nullable=False, server_default=""), sa.Column("public_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("offers_json", sa.JSON(), nullable=False, server_default="[]"), sa.Column("expectations_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("priorities_json", sa.JSON(), nullable=False, server_default="[]"), sa.Column("statuses_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tags_json", sa.JSON(), nullable=False, server_default="[]"), sa.Column("form_options_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("application_questions_json", sa.JSON(), nullable=False, server_default="[]"), sa.Column("interview_questions_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("parameter_definitions_json", sa.JSON(), nullable=False, server_default="[]"), sa.Column("required_scopes_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("privacy_notice", sa.Text(), nullable=False, server_default=""),
        sa.Column("declined_retention_days", sa.Integer(), nullable=False, server_default="365"), sa.Column("withdrawn_retention_days", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("abandoned_retention_days", sa.Integer(), nullable=False, server_default="90"), sa.Column("auto_refresh_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
    )
    op.create_table(
        "recruitment_user_capabilities",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability", sa.String(40), nullable=False), sa.Column("assigned_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "capability", name="uq_recruitment_user_capability"),
    )
    op.create_table(
        "recruitment_applications",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("applicant_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(80), nullable=False, server_default="Draft"), sa.Column("assigned_recruiter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("discord_username", sa.String(120)), sa.Column("discord_display_name", sa.String(120)), sa.Column("discord_user_id", sa.String(40)),
        sa.Column("discord_verified_at", sa.DateTime(timezone=True)), sa.Column("discord_verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("preferred_name", sa.String(120)), sa.Column("pronouns", sa.String(80)), sa.Column("timezone", sa.String(64)), sa.Column("primary_interest", sa.String(80)),
        sa.Column("veteran_status", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("answers_json", sa.JSON(), nullable=False, server_default="{}"), sa.Column("acknowledgements_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("activity_preferences_json", sa.JSON(), nullable=False, server_default="{}"), sa.Column("internal_flags_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("recruiter_ratings_json", sa.JSON(), nullable=False, server_default="{}"), sa.Column("tags_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"), sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)), sa.Column("closed_at", sa.DateTime(timezone=True)), sa.Column("last_applicant_activity_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_table(
        "recruitment_linked_characters",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="CASCADE"), nullable=False), sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("snapshot_json", sa.JSON(), nullable=False, server_default="{}"), sa.Column("employment_history_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("granted_scopes_json", sa.JSON(), nullable=False, server_default="[]"), sa.Column("token_health", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("verification_status", sa.String(40), nullable=False, server_default="pending"), sa.Column("last_successful_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_error", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("application_id", "character_id", name="uq_recruitment_application_character"),
    )
    op.create_table(
        "recruitment_interviews",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interviewer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("applicant_timezone", sa.String(64)), sa.Column("availability_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("attendance_status", sa.String(40), nullable=False, server_default="requested"), sa.Column("answers_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("internal_notes", sa.Text()), sa.Column("visible_follow_up", sa.Text()), sa.Column("recommendation", sa.String(80)),
        sa.Column("applicant_acknowledged_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), *_timestamps(),
    )
    op.create_table(
        "recruitment_notes",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("applicant_visible", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("redacted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "recruitment_messages",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("from_applicant", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "recruitment_status_history",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("recruitment_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(80)), sa.Column("new_status", sa.String(80), nullable=False), sa.Column("acting_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reason", sa.Text()), sa.Column("applicant_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notifications_json", sa.JSON(), nullable=False, server_default="[]"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "recruitment_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), sa.ForeignKey("recruitment_applications.id", ondelete="SET NULL")),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("action", sa.String(100), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False), sa.Column("details_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for table, columns in {
        "recruitment_user_capabilities": ["user_id", "capability"], "recruitment_applications": ["applicant_user_id", "status", "assigned_recruiter_user_id", "submitted_at"],
        "recruitment_linked_characters": ["application_id", "character_id"], "recruitment_interviews": ["application_id", "scheduled_at"],
        "recruitment_notes": ["application_id"], "recruitment_messages": ["application_id"], "recruitment_status_history": ["application_id"],
        "recruitment_audit_logs": ["application_id", "actor_user_id", "action"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table in ["recruitment_audit_logs", "recruitment_status_history", "recruitment_messages", "recruitment_notes", "recruitment_interviews", "recruitment_linked_characters", "recruitment_applications", "recruitment_user_capabilities", "recruitment_settings"]:
        op.drop_table(table)
