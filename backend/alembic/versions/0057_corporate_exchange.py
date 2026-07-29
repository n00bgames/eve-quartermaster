"""Add the Corporate Exchange marketplace foundation.

Revision ID: 0057_corporate_exchange
Revises: 0056_divisions_pi_schematics
"""

from alembic import op
import sqlalchemy as sa


revision = "0057_corporate_exchange"
down_revision = "0056_divisions_pi_schematics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False, unique=True),
        sa.Column("seller_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("seller_character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("seller_corporation_id", sa.Integer(), sa.ForeignKey("eve_corporations.id", ondelete="SET NULL")),
        sa.Column("listing_type", sa.String(32), nullable=False, server_default="fixed"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.String(500)),
        sa.Column("description", sa.Text()),
        sa.Column("contact_method", sa.String(255)),
        sa.Column("quantity_total", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("quantity_available", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("asking_price", sa.Numeric(24, 2)),
        sa.Column("minimum_bid", sa.Numeric(24, 2)),
        sa.Column("reserve_price", sa.Numeric(24, 2)),
        sa.Column("sell_as_complete_lot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("bid_visibility", sa.String(32), nullable=False, server_default="private"),
        sa.Column("visibility", sa.String(32), nullable=False, server_default="users"),
        sa.Column("eligibility_notes", sa.Text()),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")),
        sa.Column("location_text", sa.String(500)),
        sa.Column("division_name", sa.String(255)),
        sa.Column("condition_notes", sa.String(500)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("public_id", "seller_user_id", "seller_character_id", "seller_corporation_id", "listing_type", "status", "title", "visibility", "location_id", "expires_at"):
        op.create_index(f"ix_exchange_listings_{column}", "exchange_listings", [column])

    op.create_table(
        "exchange_listing_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id", ondelete="SET NULL")),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="SET NULL")),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.String(500)),
    )
    for column in ("listing_id", "type_id", "asset_id", "item_name"):
        op.create_index(f"ix_exchange_listing_items_{column}", "exchange_listing_items", [column])

    op.create_table(
        "exchange_appraisals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hub_key", sa.String(48), nullable=False),
        sa.Column("hub_name", sa.String(120), nullable=False),
        sa.Column("immediate_buy_value", sa.Numeric(24, 2)),
        sa.Column("immediate_sell_value", sa.Numeric(24, 2)),
        sa.Column("replacement_value", sa.Numeric(24, 2)),
        sa.Column("source", sa.String(80), nullable=False, server_default="ESI market orders"),
        sa.Column("priced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_exchange_appraisals_listing_id", "exchange_appraisals", ["listing_id"])
    op.create_index("ix_exchange_appraisals_hub_key", "exchange_appraisals", ["hub_key"])

    op.create_table(
        "exchange_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claimant_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(24, 2)),
        sa.Column("total_price", sa.Numeric(24, 2)),
        sa.Column("status", sa.String(32), nullable=False, server_default="reserved"),
        sa.Column("contract_id", sa.BigInteger()),
        sa.Column("contract_notes", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("listing_id", "claimant_user_id", "status", "expires_at"):
        op.create_index(f"ix_exchange_claims_{column}", "exchange_claims", [column])

    op.create_table(
        "exchange_bids",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bidder_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(24, 2), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("listing_id", "bidder_user_id", "status", "expires_at"):
        op.create_index(f"ix_exchange_bids_{column}", "exchange_bids", [column])

    op.create_table(
        "exchange_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("exchange_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("exchange_claims.id", ondelete="SET NULL")),
        sa.Column("bid_id", sa.Integer(), sa.ForeignKey("exchange_bids.id", ondelete="SET NULL")),
        sa.Column("seller_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("buyer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Numeric(24, 2)),
        sa.Column("status", sa.String(32), nullable=False, server_default="reserved"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("listing_id", "claim_id", "bid_id", "seller_user_id", "buyer_user_id", "status"):
        op.create_index(f"ix_exchange_transactions_{column}", "exchange_transactions", [column])

    op.create_table(
        "exchange_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("exchange_listings.id", ondelete="CASCADE")),
        sa.Column("notification_kind", sa.String(48), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("user_id", "listing_id", "notification_kind"):
        op.create_index(f"ix_exchange_notifications_{column}", "exchange_notifications", [column])

    op.create_table(
        "exchange_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("exchange_listings.id", ondelete="SET NULL")),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_kind", sa.String(48), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("listing_id", "actor_user_id", "event_kind"):
        op.create_index(f"ix_exchange_audit_logs_{column}", "exchange_audit_logs", [column])


def downgrade() -> None:
    op.drop_table("exchange_audit_logs")
    op.drop_table("exchange_notifications")
    op.drop_table("exchange_transactions")
    op.drop_table("exchange_bids")
    op.drop_table("exchange_claims")
    op.drop_table("exchange_appraisals")
    op.drop_table("exchange_listing_items")
    op.drop_table("exchange_listings")
