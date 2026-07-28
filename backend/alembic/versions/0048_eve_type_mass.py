"""store EVE type mass

Revision ID: 0048_eve_type_mass
Revises: 0047_host_role
Create Date: 2026-07-21 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048_eve_type_mass"
down_revision: Union[str, None] = "0047_host_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("eve_types", sa.Column("mass", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("eve_types", "mass")