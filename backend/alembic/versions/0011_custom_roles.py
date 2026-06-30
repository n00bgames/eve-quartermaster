"""custom role definitions

Revision ID: 0011_custom_roles
Revises: 0010_section_permissions
Create Date: 2026-06-29 22:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_custom_roles"
down_revision: Union[str, None] = "0010_section_permissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "role_definitions",
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("base_role", sa.String(length=40), nullable=False, server_default="member"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("role_definitions")
