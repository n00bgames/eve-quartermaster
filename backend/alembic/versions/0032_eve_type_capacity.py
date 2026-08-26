"""store EVE type cargo capacity

Revision ID: 0032_eve_type_capacity
Revises: 0031_hide_corporations
Create Date: 2026-07-13 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0032_eve_type_capacity"
down_revision: Union[str, None] = "0031_hide_corporations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fresh databases created by the consolidated initial schema already have
    # this column. Older installations reaching this revision do not.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("eve_types")}
    if "capacity" not in columns:
        op.add_column("eve_types", sa.Column("capacity", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("eve_types", "capacity")
