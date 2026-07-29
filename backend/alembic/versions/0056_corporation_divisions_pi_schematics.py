"""Add corporation divisions and Planetary Industry schematics.

Revision ID: 0056_divisions_pi_schematics
Revises: 0055_planetary_pi_analytics
"""

from alembic import op
import sqlalchemy as sa


revision = "0056_divisions_pi_schematics"
down_revision = "0055_planetary_pi_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corporation_divisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "corporation_id",
            sa.Integer(),
            sa.ForeignKey("eve_corporations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("division_type", sa.String(length=16), nullable=False),
        sa.Column("division", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "corporation_id",
            "division_type",
            "division",
            name="uq_corporation_division",
        ),
    )
    for column in ("corporation_id", "division_type", "division"):
        op.create_index(
            f"ix_corporation_divisions_{column}",
            "corporation_divisions",
            [column],
        )

    op.create_table(
        "eve_planet_schematics",
        sa.Column("schematic_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("cycle_time", sa.Integer(), nullable=False),
        sa.Column(
            "output_type_id",
            sa.Integer(),
            sa.ForeignKey("eve_types.type_id"),
            nullable=False,
        ),
        sa.Column("output_quantity", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_eve_planet_schematics_name",
        "eve_planet_schematics",
        ["name"],
    )
    op.create_index(
        "ix_eve_planet_schematics_output_type_id",
        "eve_planet_schematics",
        ["output_type_id"],
    )

    op.create_table(
        "eve_planet_schematic_inputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "schematic_id",
            sa.Integer(),
            sa.ForeignKey("eve_planet_schematics.schematic_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type_id",
            sa.Integer(),
            sa.ForeignKey("eve_types.type_id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "schematic_id",
            "type_id",
            name="uq_eve_planet_schematic_input",
        ),
    )
    op.create_index(
        "ix_eve_planet_schematic_inputs_schematic_id",
        "eve_planet_schematic_inputs",
        ["schematic_id"],
    )
    op.create_index(
        "ix_eve_planet_schematic_inputs_type_id",
        "eve_planet_schematic_inputs",
        ["type_id"],
    )


def downgrade() -> None:
    op.drop_table("eve_planet_schematic_inputs")
    op.drop_table("eve_planet_schematics")
    op.drop_table("corporation_divisions")
