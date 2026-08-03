"""Add the manual-first HyperNet Tracker foundation.

Revision ID: 0061_hypernet_tracker
Revises: 0060_analytics_optimization
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0061_hypernet_tracker"
down_revision: Union[str, None] = "0060_analytics_optimization"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hypernet_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")),
        sa.Column("location_name_snapshot", sa.String(length=500)),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(length=24), nullable=False, server_default="personal"),
        sa.Column("created_offer_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("reconciled_at", sa.DateTime(timezone=True)),
        sa.Column("total_offer_price", sa.Numeric(24, 2), nullable=False),
        sa.Column("total_nodes", sa.Integer(), nullable=False),
        sa.Column("nodes_sold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seller_owned_nodes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_participants", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hypercores_required", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hypercore_unit_cost", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("acquisition_cost", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("desired_profit", sa.Numeric(24, 2), nullable=False, server_default="0"),
        sa.Column("completion_fee", sa.Numeric(24, 2)),
        sa.Column("payout", sa.Numeric(24, 2)),
        sa.Column("actual_hypercore_cost", sa.Numeric(24, 2)),
        sa.Column("final_market_value", sa.Numeric(24, 2)),
        sa.Column("final_profit", sa.Numeric(24, 2)),
        sa.Column("winner", sa.String(length=32)),
        sa.Column("item_outcome", sa.String(length=32), nullable=False, server_default="committed"),
        sa.Column("notes", sa.Text()),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("source_reference", sa.String(length=255)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0", name="ck_hypernet_offers_quantity"),
        sa.CheckConstraint("total_nodes > 0", name="ck_hypernet_offers_total_nodes"),
        sa.CheckConstraint("nodes_sold >= 0 AND nodes_sold <= total_nodes", name="ck_hypernet_offers_nodes_sold"),
        sa.CheckConstraint("seller_owned_nodes >= 0 AND seller_owned_nodes <= nodes_sold", name="ck_hypernet_offers_seeded_nodes"),
        sa.CheckConstraint("hypercores_required >= 0", name="ck_hypernet_offers_hypercores"),
    )
    for name, columns in (
        ("ix_hypernet_offers_owner_status", ["owner_user_id", "status", "expires_at"]),
        ("ix_hypernet_offers_seller", ["seller_character_id"]),
        ("ix_hypernet_offers_type", ["type_id"]),
        ("ix_hypernet_offers_location", ["location_id"]),
        ("ix_hypernet_offers_created_offer_at", ["created_offer_at"]),
        ("ix_hypernet_offers_reconciled_at", ["reconciled_at"]),
        ("ix_hypernet_offers_final_profit", ["final_profit"]),
        ("ix_hypernet_offers_source_reference", ["source", "source_reference"]),
    ):
        op.create_index(name, "hypernet_offers", columns)

    op.create_table(
        "hypernet_offer_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offer_id", sa.Integer(), sa.ForeignKey("hypernet_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("nodes_sold", sa.Integer(), nullable=False),
        sa.Column("seller_owned_nodes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_participants", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jita_buy", sa.Numeric(24, 2)),
        sa.Column("jita_sell", sa.Numeric(24, 2)),
        sa.Column("local_buy", sa.Numeric(24, 2)),
        sa.Column("local_sell", sa.Numeric(24, 2)),
        sa.Column("hypercore_buy", sa.Numeric(24, 2)),
        sa.Column("hypercore_sell", sa.Numeric(24, 2)),
        sa.Column("note", sa.Text()),
        sa.Column("screenshot_attachment_id", sa.String(length=255)),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.CheckConstraint("nodes_sold >= 0", name="ck_hypernet_snapshots_nodes_sold"),
        sa.CheckConstraint("seller_owned_nodes >= 0 AND seller_owned_nodes <= nodes_sold", name="ck_hypernet_snapshots_seeded_nodes"),
    )
    op.create_index("ix_hypernet_snapshots_offer_captured", "hypernet_offer_snapshots", ["offer_id", "captured_at", "id"])

    op.create_table(
        "hypernet_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offer_id", sa.Integer(), sa.ForeignKey("hypernet_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("participant_name", sa.String(length=255), nullable=False),
        sa.Column("nodes_owned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_seller", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("offer_id", "participant_name", name="uq_hypernet_participant_name"),
    )
    op.create_index("ix_hypernet_participants_offer", "hypernet_participants", ["offer_id"])
    op.create_index("ix_hypernet_participants_character", "hypernet_participants", ["character_id"])
    op.create_index("ix_hypernet_participants_name", "hypernet_participants", ["participant_name"])

    op.create_table(
        "hypernet_participation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("external_offer_reference", sa.String(length=255)),
        sa.Column("item_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("seller_name", sa.String(length=255), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")),
        sa.Column("nodes_purchased", sa.Integer(), nullable=False),
        sa.Column("node_price", sa.Numeric(24, 2), nullable=False),
        sa.Column("total_spent", sa.Numeric(24, 2), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("won", sa.Boolean()),
        sa.Column("item_value_at_completion", sa.Numeric(24, 2)),
        sa.Column("profit_loss", sa.Numeric(24, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_hypernet_participation_user_created", "hypernet_participation", ["user_id", "created_at"])
    op.create_index("ix_hypernet_participation_character", "hypernet_participation", ["character_id"])
    op.create_index("ix_hypernet_participation_type", "hypernet_participation", ["item_type_id"])
    op.create_index("ix_hypernet_participation_status", "hypernet_participation", ["outcome", "completed_at"])

    op.create_table(
        "hypernet_settings",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("monthly_node_limit", sa.Integer()),
        sa.Column("monthly_spend_limit", sa.Numeric(24, 2)),
        sa.Column("warning_threshold_percent", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("preferred_market_hub", sa.String(length=32), nullable=False, server_default="jita"),
        sa.Column("default_hypercore_price_source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("hypernet_settings")
    op.drop_index("ix_hypernet_participation_status", table_name="hypernet_participation")
    op.drop_index("ix_hypernet_participation_type", table_name="hypernet_participation")
    op.drop_index("ix_hypernet_participation_character", table_name="hypernet_participation")
    op.drop_index("ix_hypernet_participation_user_created", table_name="hypernet_participation")
    op.drop_table("hypernet_participation")
    op.drop_index("ix_hypernet_participants_name", table_name="hypernet_participants")
    op.drop_index("ix_hypernet_participants_character", table_name="hypernet_participants")
    op.drop_index("ix_hypernet_participants_offer", table_name="hypernet_participants")
    op.drop_table("hypernet_participants")
    op.drop_index("ix_hypernet_snapshots_offer_captured", table_name="hypernet_offer_snapshots")
    op.drop_table("hypernet_offer_snapshots")
    for index_name in (
        "ix_hypernet_offers_source_reference",
        "ix_hypernet_offers_final_profit",
        "ix_hypernet_offers_reconciled_at",
        "ix_hypernet_offers_created_offer_at",
        "ix_hypernet_offers_location",
        "ix_hypernet_offers_type",
        "ix_hypernet_offers_seller",
        "ix_hypernet_offers_owner_status",
    ):
        op.drop_index(index_name, table_name="hypernet_offers")
    op.drop_table("hypernet_offers")
