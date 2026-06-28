"""initial eve-quartermaster schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

owner_kind = postgresql.ENUM("CHARACTER", "CORPORATION", "ALLIANCE", "MANUAL_GROUP", name="ownerkind", create_type=False)
location_kind = postgresql.ENUM("REGION", "CONSTELLATION", "SYSTEM", "STATION", "STRUCTURE", "CONTAINER", "UNKNOWN", name="locationkind", create_type=False)
asset_source = postgresql.ENUM("ESI", "MANUAL", "SDE", name="assetsource", create_type=False)
activity_kind = postgresql.ENUM("MANUFACTURING", "COPYING", "INVENTION", "REACTION", "RESEARCH_MATERIAL", "RESEARCH_TIME", name="activitykind", create_type=False)
procurement_kind = postgresql.ENUM("BUY", "MINE", "REPROCESS", "REACT", "MANUFACTURE", "STOCKPILE", name="procurementkind", create_type=False)
sync_status = postgresql.ENUM("QUEUED", "RUNNING", "SUCCESS", "FAILED", "SKIPPED", name="syncstatus", create_type=False)


def upgrade() -> None:
    owner_kind.create(op.get_bind(), checkfirst=True)
    location_kind.create(op.get_bind(), checkfirst=True)
    asset_source.create(op.get_bind(), checkfirst=True)
    activity_kind.create(op.get_bind(), checkfirst=True)
    procurement_kind.create(op.get_bind(), checkfirst=True)
    sync_status.create(op.get_bind(), checkfirst=True)

    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(320), nullable=False), sa.Column("display_name", sa.String(120), nullable=False), sa.Column("password_hash", sa.String(255)), sa.Column("role", sa.String(40), nullable=False, server_default="member"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table("eve_categories", sa.Column("category_id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.create_index("ix_eve_categories_name", "eve_categories", ["name"])
    op.create_table("eve_groups", sa.Column("group_id", sa.Integer(), primary_key=True), sa.Column("category_id", sa.Integer(), sa.ForeignKey("eve_categories.category_id")), sa.Column("name", sa.String(255), nullable=False), sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.create_index("ix_eve_groups_name", "eve_groups", ["name"])
    op.create_table("eve_types", sa.Column("type_id", sa.Integer(), primary_key=True), sa.Column("group_id", sa.Integer(), sa.ForeignKey("eve_groups.group_id")), sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text()), sa.Column("volume", sa.Float()), sa.Column("packaged_volume", sa.Float()), sa.Column("market_group_id", sa.Integer()), sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.create_index("ix_eve_types_name", "eve_types", ["name"])
    op.create_index("ix_eve_types_market_group_id", "eve_types", ["market_group_id"])

    op.create_table("eve_regions", sa.Column("region_id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(255), nullable=False))
    op.create_index("ix_eve_regions_name", "eve_regions", ["name"])
    op.create_table("eve_constellations", sa.Column("constellation_id", sa.Integer(), primary_key=True), sa.Column("region_id", sa.Integer(), sa.ForeignKey("eve_regions.region_id")), sa.Column("name", sa.String(255), nullable=False))
    op.create_index("ix_eve_constellations_region_id", "eve_constellations", ["region_id"])
    op.create_index("ix_eve_constellations_name", "eve_constellations", ["name"])
    op.create_table("eve_systems", sa.Column("system_id", sa.Integer(), primary_key=True), sa.Column("constellation_id", sa.Integer(), sa.ForeignKey("eve_constellations.constellation_id")), sa.Column("name", sa.String(255), nullable=False), sa.Column("security_status", sa.Float()))
    op.create_index("ix_eve_systems_constellation_id", "eve_systems", ["constellation_id"])
    op.create_index("ix_eve_systems_name", "eve_systems", ["name"])

    op.create_table("eve_alliances", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("alliance_id", sa.Integer(), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("ticker", sa.String(20)))
    op.create_index("ix_eve_alliances_alliance_id", "eve_alliances", ["alliance_id"], unique=True)
    op.create_index("ix_eve_alliances_name", "eve_alliances", ["name"])
    op.create_table("eve_corporations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("corporation_id", sa.Integer(), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("ticker", sa.String(20)), sa.Column("alliance_id", sa.Integer(), sa.ForeignKey("eve_alliances.id")), sa.Column("ceo_character_eve_id", sa.Integer()), sa.Column("last_synced_at", sa.DateTime(timezone=True)))
    op.create_index("ix_eve_corporations_corporation_id", "eve_corporations", ["corporation_id"], unique=True)
    op.create_index("ix_eve_corporations_name", "eve_corporations", ["name"])
    op.create_table("eve_characters", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("character_id", sa.Integer(), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("corporation_id", sa.Integer(), sa.ForeignKey("eve_corporations.id")), sa.Column("alliance_id", sa.Integer(), sa.ForeignKey("eve_alliances.id")), sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("portrait_url", sa.String(500)), sa.Column("last_synced_at", sa.DateTime(timezone=True)))
    op.create_index("ix_eve_characters_character_id", "eve_characters", ["character_id"], unique=True)
    op.create_index("ix_eve_characters_name", "eve_characters", ["name"])

    op.create_table("ownership_entities", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("owner_kind", owner_kind, nullable=False), sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id")), sa.Column("corporation_id", sa.Integer(), sa.ForeignKey("eve_corporations.id")), sa.Column("alliance_id", sa.Integer(), sa.ForeignKey("eve_alliances.id")), sa.Column("display_name", sa.String(255), nullable=False), sa.Column("notes", sa.String()), sa.UniqueConstraint("owner_kind", "character_id", "corporation_id", "alliance_id", "display_name"))
    op.create_index("ix_ownership_entities_display_name", "ownership_entities", ["display_name"])

    op.create_table("locations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("location_kind", location_kind, nullable=False), sa.Column("eve_location_id", sa.Integer()), sa.Column("name", sa.String(255), nullable=False), sa.Column("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id")), sa.Column("parent_location_id", sa.Integer(), sa.ForeignKey("locations.id")), sa.Column("source", asset_source, nullable=False), sa.Column("notes", sa.String()))
    op.create_index("ix_locations_eve_location_id", "locations", ["eve_location_id"])
    op.create_index("ix_locations_name", "locations", ["name"])
    op.create_index("ix_locations_system_id", "locations", ["system_id"])

    op.create_table("assets", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ownership_entity_id", sa.Integer(), sa.ForeignKey("ownership_entities.id"), nullable=False), sa.Column("eve_item_id", sa.Integer()), sa.Column("type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"), sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id")), sa.Column("parent_asset_id", sa.Integer(), sa.ForeignKey("assets.id")), sa.Column("location_flag", sa.String(80)), sa.Column("is_singleton", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("is_blueprint_copy", sa.Boolean()), sa.Column("source", asset_source, nullable=False), sa.Column("last_synced_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_assets_ownership_entity_id", "assets", ["ownership_entity_id"])
    op.create_index("ix_assets_eve_item_id", "assets", ["eve_item_id"], unique=True)
    op.create_index("ix_assets_type_id", "assets", ["type_id"])
    op.create_index("ix_assets_location_id", "assets", ["location_id"])
    op.create_index("ix_assets_parent_asset_id", "assets", ["parent_asset_id"])
    op.create_index("ix_assets_location_flag", "assets", ["location_flag"])

    op.create_table("blueprints", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), unique=True), sa.Column("ownership_entity_id", sa.Integer(), sa.ForeignKey("ownership_entities.id"), nullable=False), sa.Column("blueprint_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False), sa.Column("product_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id")), sa.Column("material_efficiency", sa.Integer(), nullable=False, server_default="0"), sa.Column("time_efficiency", sa.Integer(), nullable=False, server_default="0"), sa.Column("runs_remaining", sa.Integer()), sa.Column("is_copy", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id")), sa.Column("source", asset_source, nullable=False), sa.Column("last_synced_at", sa.DateTime(timezone=True)))
    op.create_index("ix_blueprints_ownership_entity_id", "blueprints", ["ownership_entity_id"])
    op.create_index("ix_blueprints_blueprint_type_id", "blueprints", ["blueprint_type_id"])
    op.create_index("ix_blueprints_product_type_id", "blueprints", ["product_type_id"])
    op.create_index("ix_blueprints_location_id", "blueprints", ["location_id"])

    op.create_table("industry_activities", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("blueprint_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False), sa.Column("activity_kind", activity_kind, nullable=False), sa.Column("product_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id")), sa.Column("product_quantity", sa.Integer(), nullable=False, server_default="1"), sa.Column("time_seconds", sa.Integer()))
    op.create_index("ix_industry_activities_blueprint_type_id", "industry_activities", ["blueprint_type_id"])
    op.create_index("ix_industry_activities_activity_kind", "industry_activities", ["activity_kind"])
    op.create_index("ix_industry_activities_product_type_id", "industry_activities", ["product_type_id"])
    op.create_table("industry_activity_inputs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("activity_id", sa.Integer(), sa.ForeignKey("industry_activities.id"), nullable=False), sa.Column("input_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("consume_type", sa.String(40), nullable=False, server_default="consumed"))
    op.create_index("ix_industry_activity_inputs_activity_id", "industry_activity_inputs", ["activity_id"])
    op.create_index("ix_industry_activity_inputs_input_type_id", "industry_activity_inputs", ["input_type_id"])

    op.create_table("production_plans", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("ownership_entity_id", sa.Integer(), sa.ForeignKey("ownership_entities.id"), nullable=False), sa.Column("blueprint_id", sa.Integer(), sa.ForeignKey("blueprints.id")), sa.Column("activity_id", sa.Integer(), sa.ForeignKey("industry_activities.id"), nullable=False), sa.Column("runs", sa.Integer(), nullable=False, server_default="1"), sa.Column("target_location_id", sa.Integer(), sa.ForeignKey("locations.id")), sa.Column("status", sa.String(40), nullable=False, server_default="draft"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_production_plans_ownership_entity_id", "production_plans", ["ownership_entity_id"])
    op.create_index("ix_production_plans_status", "production_plans", ["status"])
    op.create_table("production_plan_inputs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("production_plan_id", sa.Integer(), sa.ForeignKey("production_plans.id"), nullable=False), sa.Column("input_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False), sa.Column("required_quantity", sa.Integer(), nullable=False), sa.Column("owned_quantity", sa.Integer(), nullable=False, server_default="0"), sa.Column("missing_quantity", sa.Integer(), nullable=False, server_default="0"), sa.Column("procurement_strategy", procurement_kind, nullable=False))
    op.create_index("ix_production_plan_inputs_production_plan_id", "production_plan_inputs", ["production_plan_id"])
    op.create_index("ix_production_plan_inputs_input_type_id", "production_plan_inputs", ["input_type_id"])
    op.create_table("procurement_sources", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id"), nullable=False), sa.Column("source_type", procurement_kind, nullable=False), sa.Column("preferred_location_id", sa.Integer(), sa.ForeignKey("locations.id")), sa.Column("estimated_unit_price", sa.Numeric(18, 2)), sa.Column("priority", sa.Integer(), nullable=False, server_default="3"), sa.Column("notes", sa.String()))
    op.create_index("ix_procurement_sources_type_id", "procurement_sources", ["type_id"])
    op.create_index("ix_procurement_sources_source_type", "procurement_sources", ["source_type"])

    op.create_table("esi_applications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("client_id", sa.String(255), nullable=False), sa.Column("encrypted_client_secret", sa.Text()), sa.Column("callback_url", sa.String(500), nullable=False))
    op.create_table("esi_tokens", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id"), nullable=False), sa.Column("scopes", sa.Text(), nullable=False), sa.Column("encrypted_refresh_token", sa.Text(), nullable=False), sa.Column("access_token_expires_at", sa.DateTime(timezone=True)), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_esi_tokens_user_id", "esi_tokens", ["user_id"])
    op.create_index("ix_esi_tokens_character_id", "esi_tokens", ["character_id"])
    op.create_table("esi_sync_jobs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("token_id", sa.Integer(), sa.ForeignKey("esi_tokens.id")), sa.Column("ownership_entity_id", sa.Integer(), sa.ForeignKey("ownership_entities.id")), sa.Column("sync_type", sa.String(80), nullable=False), sa.Column("status", sync_status, nullable=False), sa.Column("message", sa.Text()), sa.Column("esi_etag", sa.String(255)), sa.Column("esi_expires_at", sa.DateTime(timezone=True)), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_esi_sync_jobs_token_id", "esi_sync_jobs", ["token_id"])
    op.create_index("ix_esi_sync_jobs_ownership_entity_id", "esi_sync_jobs", ["ownership_entity_id"])
    op.create_index("ix_esi_sync_jobs_sync_type", "esi_sync_jobs", ["sync_type"])
    op.create_index("ix_esi_sync_jobs_status", "esi_sync_jobs", ["status"])


def downgrade() -> None:
    for table in ["esi_sync_jobs", "esi_tokens", "esi_applications", "procurement_sources", "production_plan_inputs", "production_plans", "industry_activity_inputs", "industry_activities", "blueprints", "assets", "locations", "ownership_entities", "eve_characters", "eve_corporations", "eve_alliances", "eve_systems", "eve_constellations", "eve_regions", "eve_types", "eve_groups", "eve_categories", "users"]:
        op.drop_table(table)
    sync_status.drop(op.get_bind(), checkfirst=True)
    procurement_kind.drop(op.get_bind(), checkfirst=True)
    activity_kind.drop(op.get_bind(), checkfirst=True)
    asset_source.drop(op.get_bind(), checkfirst=True)
    location_kind.drop(op.get_bind(), checkfirst=True)
    owner_kind.drop(op.get_bind(), checkfirst=True)

