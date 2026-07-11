"""store character security status

Revision ID: 0030_character_security_status
Revises: 0029_killmail_wardecs
Create Date: 2026-07-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0030_character_security_status"
down_revision: Union[str, None] = "0029_killmail_wardecs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("eve_characters", sa.Column("security_status", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("eve_characters", "security_status")