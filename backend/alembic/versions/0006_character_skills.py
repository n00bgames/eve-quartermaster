"""add character skill imports

Revision ID: 0006_character_skills
Revises: 0005_corporation_member_count
Create Date: 2026-06-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_character_skills"
down_revision = "0005_corporation_member_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eve_characters", sa.Column("total_skill_points", sa.Integer(), nullable=True))
    op.add_column("eve_characters", sa.Column("unallocated_skill_points", sa.Integer(), nullable=True))
    op.add_column("eve_characters", sa.Column("skills_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("eve_characters", sa.Column("skill_queue_synced_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "character_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id"), nullable=False),
        sa.Column("skill_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False),
        sa.Column("trained_skill_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_skill_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skillpoints_in_skill", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("character_id", "skill_type_id", name="uq_character_skill"),
    )
    op.create_index("ix_character_skills_character_id", "character_skills", ["character_id"])
    op.create_index("ix_character_skills_skill_type_id", "character_skills", ["skill_type_id"])

    op.create_table(
        "character_skill_queue_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id"), nullable=False),
        sa.Column("queue_position", sa.Integer(), nullable=False),
        sa.Column("skill_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False),
        sa.Column("finished_level", sa.Integer(), nullable=False),
        sa.Column("training_start_sp", sa.Integer(), nullable=True),
        sa.Column("level_start_sp", sa.Integer(), nullable=True),
        sa.Column("level_end_sp", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finish_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("character_id", "queue_position", name="uq_character_skill_queue_position"),
    )
    op.create_index("ix_character_skill_queue_entries_character_id", "character_skill_queue_entries", ["character_id"])
    op.create_index("ix_character_skill_queue_entries_skill_type_id", "character_skill_queue_entries", ["skill_type_id"])


def downgrade() -> None:
    op.drop_index("ix_character_skill_queue_entries_skill_type_id", table_name="character_skill_queue_entries")
    op.drop_index("ix_character_skill_queue_entries_character_id", table_name="character_skill_queue_entries")
    op.drop_table("character_skill_queue_entries")
    op.drop_index("ix_character_skills_skill_type_id", table_name="character_skills")
    op.drop_index("ix_character_skills_character_id", table_name="character_skills")
    op.drop_table("character_skills")
    op.drop_column("eve_characters", "skill_queue_synced_at")
    op.drop_column("eve_characters", "skills_synced_at")
    op.drop_column("eve_characters", "unallocated_skill_points")
    op.drop_column("eve_characters", "total_skill_points")
