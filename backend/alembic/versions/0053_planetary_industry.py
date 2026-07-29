"""add planetary industry colonies and layouts

Revision ID: 0053_planetary_industry
Revises: 0052_character_standings
Create Date: 2026-07-28 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053_planetary_industry"
down_revision: Union[str, None] = "0052_character_standings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planetary_colonies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("planet_id", sa.BigInteger(), nullable=False),
        sa.Column("planet_name", sa.String(length=255), nullable=False),
        sa.Column("planet_type", sa.String(length=40), nullable=True),
        sa.Column("solar_system_id", sa.Integer(), nullable=True),
        sa.Column("upgrade_level", sa.Integer(), nullable=False),
        sa.Column("num_pins", sa.Integer(), nullable=False),
        sa.Column("esi_last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["eve_characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["solar_system_id"], ["eve_systems.system_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "planet_id", name="uq_planetary_colony_character_planet"),
    )
    for column in ("character_id", "planet_id", "planet_name", "planet_type", "solar_system_id", "esi_last_update", "last_synced_at"):
        op.create_index(op.f(f"ix_planetary_colonies_{column}"), "planetary_colonies", [column])

    op.create_table(
        "planetary_pins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("colony_id", sa.Integer(), nullable=False),
        sa.Column("pin_id", sa.BigInteger(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("install_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_cycle_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schematic_id", sa.Integer(), nullable=True),
        sa.Column("extractor_cycle_time", sa.Integer(), nullable=True),
        sa.Column("extractor_head_radius", sa.Float(), nullable=True),
        sa.Column("extractor_product_type_id", sa.Integer(), nullable=True),
        sa.Column("extractor_qty_per_cycle", sa.Integer(), nullable=True),
        sa.Column("contents_json", sa.JSON(), nullable=False),
        sa.Column("extractor_heads_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["colony_id"], ["planetary_colonies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extractor_product_type_id"], ["eve_types.type_id"]),
        sa.ForeignKeyConstraint(["type_id"], ["eve_types.type_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("colony_id", "pin_id", name="uq_planetary_pin_colony_pin"),
    )
    for column in ("colony_id", "pin_id", "type_id", "expiry_time", "schematic_id", "extractor_product_type_id"):
        op.create_index(op.f(f"ix_planetary_pins_{column}"), "planetary_pins", [column])

    op.create_table(
        "planetary_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("colony_id", sa.Integer(), nullable=False),
        sa.Column("source_pin_id", sa.BigInteger(), nullable=False),
        sa.Column("destination_pin_id", sa.BigInteger(), nullable=False),
        sa.Column("link_level", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["colony_id"], ["planetary_colonies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("colony_id", "source_pin_id", "destination_pin_id"):
        op.create_index(op.f(f"ix_planetary_links_{column}"), "planetary_links", [column])

    op.create_table(
        "planetary_routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("colony_id", sa.Integer(), nullable=False),
        sa.Column("route_id", sa.BigInteger(), nullable=False),
        sa.Column("source_pin_id", sa.BigInteger(), nullable=False),
        sa.Column("destination_pin_id", sa.BigInteger(), nullable=False),
        sa.Column("content_type_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("waypoints_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["colony_id"], ["planetary_colonies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_type_id"], ["eve_types.type_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("colony_id", "route_id", name="uq_planetary_route_colony_route"),
    )
    for column in ("colony_id", "route_id", "source_pin_id", "destination_pin_id", "content_type_id"):
        op.create_index(op.f(f"ix_planetary_routes_{column}"), "planetary_routes", [column])


def downgrade() -> None:
    op.drop_table("planetary_routes")
    op.drop_table("planetary_links")
    op.drop_table("planetary_pins")
    op.drop_table("planetary_colonies")
