"""allow corporations to be hidden from the corporations page

Revision ID: 0031_hide_corporations
Revises: 0030_character_security_status
Create Date: 2026-07-13 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0031_hide_corporations"
down_revision: Union[str, None] = "0030_character_security_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("eve_corporations", sa.Column("hide_from_corporation_list", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.alter_column("eve_corporations", "hide_from_corporation_list", server_default=None)


def downgrade() -> None:
    op.drop_column("eve_corporations", "hide_from_corporation_list")
