"""Add historical Planetary Industry production observations.

Revision ID: 0055_planetary_pi_analytics
Revises: 0054_blueprint_shadow_inventory
"""

from alembic import op
import sqlalchemy as sa


revision = "0055_planetary_pi_analytics"
down_revision = "0054_blueprint_shadow_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planetary_production_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "character_id",
            sa.Integer(),
            sa.ForeignKey("eve_characters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("interval_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planet_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "solar_system_id",
            sa.Integer(),
            sa.ForeignKey("eve_systems.system_id"),
            nullable=True,
        ),
        sa.Column("pin_id", sa.BigInteger(), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column(
            "product_type_id",
            sa.Integer(),
            sa.ForeignKey("eve_types.type_id"),
            nullable=False,
        ),
        sa.Column("commodity_tier", sa.String(length=2), nullable=False),
        sa.Column("unit_volume", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_units_per_day", sa.Float(), nullable=False, server_default="0"),
        sa.Column("projected_remaining_units", sa.Float(), nullable=True),
        sa.Column(
            "estimated_units_since_previous",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("program_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "character_id",
            "pin_id",
            "product_type_id",
            "captured_at",
            name="uq_planetary_production_snapshot_observation",
        ),
    )
    for column in (
        "character_id",
        "captured_at",
        "planet_id",
        "solar_system_id",
        "pin_id",
        "source_kind",
        "product_type_id",
        "commodity_tier",
    ):
        op.create_index(
            f"ix_planetary_production_snapshots_{column}",
            "planetary_production_snapshots",
            [column],
        )
    op.create_index(
        "ix_planetary_production_snapshot_character_captured",
        "planetary_production_snapshots",
        ["character_id", "captured_at"],
    )
    op.create_index(
        "ix_planetary_production_snapshot_product_captured",
        "planetary_production_snapshots",
        ["product_type_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_table("planetary_production_snapshots")
