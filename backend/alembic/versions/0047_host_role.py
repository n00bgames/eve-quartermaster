"""add host account role

Revision ID: 0047_host_role
Revises: 0046_research_queue
Create Date: 2026-07-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047_host_role"
down_revision: Union[str, None] = "0046_research_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET role = 'host'
            WHERE id = (
                SELECT id
                FROM users
                WHERE role = 'admin' AND deleted_at IS NULL
                ORDER BY id
                LIMIT 1
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE role = 'host'"))
