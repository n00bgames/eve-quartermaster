"""add recruiting public subheading

Revision ID: 0051_recruiting_public_polish
Revises: 0050_recruiting
Create Date: 2026-07-22 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051_recruiting_public_polish"
down_revision: Union[str, None] = "0050_recruiting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recruitment_settings",
        sa.Column("public_subheading", sa.String(500), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("recruitment_settings", "public_subheading")