"""store jump clones and implant sets

Revision ID: 0033_jump_clones_implants
Revises: 0032_eve_type_capacity
Create Date: 2026-07-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0033_jump_clones_implants"
down_revision: Union[str, None] = "0032_eve_type_capacity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "character_jump_clones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("clone_kind", sa.String(length=32), nullable=False),
        sa.Column("jump_clone_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("location_type", sa.String(length=32), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["eve_characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "clone_kind", "jump_clone_id", name="uq_character_jump_clone"),
    )
    op.create_index(op.f("ix_character_jump_clones_character_id"), "character_jump_clones", ["character_id"], unique=False)
    op.create_index(op.f("ix_character_jump_clones_clone_kind"), "character_jump_clones", ["clone_kind"], unique=False)
    op.create_index(op.f("ix_character_jump_clones_jump_clone_id"), "character_jump_clones", ["jump_clone_id"], unique=False)
    op.create_index(op.f("ix_character_jump_clones_location_id"), "character_jump_clones", ["location_id"], unique=False)

    op.create_table(
        "jump_clone_implants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clone_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["clone_id"], ["character_jump_clones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["type_id"], ["eve_types.type_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clone_id", "type_id", name="uq_jump_clone_implant"),
    )
    op.create_index(op.f("ix_jump_clone_implants_clone_id"), "jump_clone_implants", ["clone_id"], unique=False)
    op.create_index(op.f("ix_jump_clone_implants_type_id"), "jump_clone_implants", ["type_id"], unique=False)

    op.create_table(
        "implant_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["eve_characters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_implant_sets_character_id"), "implant_sets", ["character_id"], unique=False)
    op.create_index(op.f("ix_implant_sets_name"), "implant_sets", ["name"], unique=False)
    op.create_index(op.f("ix_implant_sets_owner_user_id"), "implant_sets", ["owner_user_id"], unique=False)

    op.create_table(
        "implant_set_implants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("set_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["set_id"], ["implant_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["type_id"], ["eve_types.type_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("set_id", "type_id", name="uq_implant_set_implant"),
    )
    op.create_index(op.f("ix_implant_set_implants_set_id"), "implant_set_implants", ["set_id"], unique=False)
    op.create_index(op.f("ix_implant_set_implants_type_id"), "implant_set_implants", ["type_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_implant_set_implants_type_id"), table_name="implant_set_implants")
    op.drop_index(op.f("ix_implant_set_implants_set_id"), table_name="implant_set_implants")
    op.drop_table("implant_set_implants")
    op.drop_index(op.f("ix_implant_sets_owner_user_id"), table_name="implant_sets")
    op.drop_index(op.f("ix_implant_sets_name"), table_name="implant_sets")
    op.drop_index(op.f("ix_implant_sets_character_id"), table_name="implant_sets")
    op.drop_table("implant_sets")
    op.drop_index(op.f("ix_jump_clone_implants_type_id"), table_name="jump_clone_implants")
    op.drop_index(op.f("ix_jump_clone_implants_clone_id"), table_name="jump_clone_implants")
    op.drop_table("jump_clone_implants")
    op.drop_index(op.f("ix_character_jump_clones_location_id"), table_name="character_jump_clones")
    op.drop_index(op.f("ix_character_jump_clones_jump_clone_id"), table_name="character_jump_clones")
    op.drop_index(op.f("ix_character_jump_clones_clone_kind"), table_name="character_jump_clones")
    op.drop_index(op.f("ix_character_jump_clones_character_id"), table_name="character_jump_clones")
    op.drop_table("character_jump_clones")
