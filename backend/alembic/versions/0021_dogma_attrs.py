"""add dogma attributes for fitting simulation

Revision ID: 0021_dogma_attrs
Revises: 0020_fittings
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_dogma_attrs"
down_revision = "0020_fittings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eve_dogma_attributes",
        sa.Column("attribute_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("default_value", sa.Float(), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_eve_dogma_attributes_name", "eve_dogma_attributes", ["name"])
    op.create_index("ix_eve_dogma_attributes_display_name", "eve_dogma_attributes", ["display_name"])
    op.create_index("ix_eve_dogma_attributes_unit_id", "eve_dogma_attributes", ["unit_id"])

    op.create_table(
        "eve_type_dogma_attributes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("attribute_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["type_id"], ["eve_types.type_id"]),
        sa.ForeignKeyConstraint(["attribute_id"], ["eve_dogma_attributes.attribute_id"]),
        sa.UniqueConstraint("type_id", "attribute_id", name="uq_eve_type_dogma_attribute"),
    )
    op.create_index("ix_eve_type_dogma_attributes_type_id", "eve_type_dogma_attributes", ["type_id"])
    op.create_index("ix_eve_type_dogma_attributes_attribute_id", "eve_type_dogma_attributes", ["attribute_id"])


def downgrade() -> None:
    op.drop_index("ix_eve_type_dogma_attributes_attribute_id", table_name="eve_type_dogma_attributes")
    op.drop_index("ix_eve_type_dogma_attributes_type_id", table_name="eve_type_dogma_attributes")
    op.drop_table("eve_type_dogma_attributes")
    op.drop_index("ix_eve_dogma_attributes_unit_id", table_name="eve_dogma_attributes")
    op.drop_index("ix_eve_dogma_attributes_display_name", table_name="eve_dogma_attributes")
    op.drop_index("ix_eve_dogma_attributes_name", table_name="eve_dogma_attributes")
    op.drop_table("eve_dogma_attributes")
