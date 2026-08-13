"""Add durable SRP loss analytics, instances, and audit history.

Revision ID: 0067_srp_loss_analytics
Revises: 0066_fleet_operations
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0067_srp_loss_analytics"
down_revision: Union[str, None] = "0066_fleet_operations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "srp_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("share_token", sa.String(64), nullable=False, unique=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("fleet_commander_character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("doctrine_id", sa.Integer(), sa.ForeignKey("doctrines.id", ondelete="SET NULL")),
        sa.Column("corporation_id", sa.Integer(), sa.ForeignKey("eve_corporations.id", ondelete="SET NULL")),
        sa.Column("alliance_id", sa.Integer(), sa.ForeignKey("eve_alliances.id", ondelete="SET NULL")),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    for column in ("name", "share_token", "start_at", "end_at", "fleet_commander_character_id", "doctrine_id", "corporation_id", "alliance_id", "status", "created_by_user_id", "archived_at"):
        op.create_index(f"ix_srp_operations_{column}", "srp_operations", [column])

    op.create_table(
        "srp_loss_reasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_srp_loss_reasons_key", "srp_loss_reasons", ["key"])
    op.create_index("ix_srp_loss_reasons_is_active", "srp_loss_reasons", ["is_active"])
    reason_table = sa.table("srp_loss_reasons", sa.column("key"), sa.column("name"), sa.column("display_order"), sa.column("is_active"))
    names = ["Fleet combat", "Roam", "Gate camp", "Structure defense", "Structure attack", "Logistics", "Travel", "PvE", "User error", "Disconnect/server issue", "Other"]
    op.bulk_insert(reason_table, [{"key": name.lower().replace("/", "_").replace(" ", "_"), "name": name, "display_order": i, "is_active": True} for i, name in enumerate(names)])

    columns = [
        ("operation_id", sa.Integer(), sa.ForeignKey("srp_operations.id", ondelete="SET NULL")),
        ("loss_reason_id", sa.Integer(), sa.ForeignKey("srp_loss_reasons.id", ondelete="SET NULL")),
        ("corporation_id", sa.Integer(), sa.ForeignKey("eve_corporations.id", ondelete="SET NULL")),
        ("alliance_id", sa.Integer(), sa.ForeignKey("eve_alliances.id", ondelete="SET NULL")),
        ("ship_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id", ondelete="SET NULL")),
        ("ship_group_id", sa.Integer(), sa.ForeignKey("eve_groups.group_id", ondelete="SET NULL")),
        ("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id", ondelete="SET NULL")),
        ("region_id", sa.Integer(), sa.ForeignKey("eve_regions.region_id", ondelete="SET NULL")),
        ("doctrine_priority_code_snapshot", sa.String(120), None), ("fitting_snapshot", sa.JSON(), None),
        ("corporation_name_snapshot", sa.String(255), None), ("alliance_name_snapshot", sa.String(255), None),
        ("ship_group_name_snapshot", sa.String(255), None), ("operation_name_snapshot", sa.String(255), None),
        ("loss_reason_name_snapshot", sa.String(120), None), ("system_name_snapshot", sa.String(255), None),
        ("region_name_snapshot", sa.String(255), None), ("security_status", sa.Float(), None),
        ("security_class", sa.String(24), None),
        ("entered_timezone", sa.String(64), None), ("killmail_id", sa.BigInteger(), None),
        ("killmail_hash", sa.String(255), None), ("killmail_url", sa.String(1000), None),
        ("data_source", sa.String(32), None),
        ("expected_fit_value", sa.Numeric(24, 2), None), ("hull_value", sa.Numeric(24, 2), None),
        ("fitted_module_value", sa.Numeric(24, 2), None), ("cargo_value", sa.Numeric(24, 2), None),
        ("drone_fighter_value", sa.Numeric(24, 2), None), ("submission_estimated_loss_value", sa.Numeric(24, 2), None),
        ("killmail_destroyed_value", sa.Numeric(24, 2), None), ("killmail_dropped_value", sa.Numeric(24, 2), None),
        ("killmail_total_loss_value", sa.Numeric(24, 2), None), ("verified_loss_value", sa.Numeric(24, 2), None),
        ("authoritative_loss_value", sa.Numeric(24, 2), None), ("requested_reimbursement_amount", sa.Numeric(24, 2), None),
        ("approved_reimbursement_amount", sa.Numeric(24, 2), None), ("paid_reimbursement_amount", sa.Numeric(24, 2), None),
        ("valuation_source", sa.String(64), None), ("valuation_timestamp", sa.DateTime(timezone=True), None),
        ("valuation_region_id", sa.Integer(), sa.ForeignKey("eve_regions.region_id", ondelete="SET NULL")),
        ("valuation_market_context", sa.String(255), None), ("valuation_status", sa.String(32), None),
        ("manual_valuation_override", sa.Numeric(24, 2), None), ("valuation_override_reason", sa.Text(), None),
        ("valuation_override_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        ("record_disposition", sa.String(32), None),
        ("duplicate_of_request_id", sa.Integer(), sa.ForeignKey("srp_requests.id", ondelete="SET NULL")),
        ("exclusion_reason", sa.Text(), None),
    ]
    for name, type_, foreign_key in columns:
        args = [foreign_key] if foreign_key is not None else []
        kwargs = {}
        if name == "entered_timezone": kwargs.update(nullable=False, server_default="UTC")
        elif name == "data_source": kwargs.update(nullable=False, server_default="manual")
        elif name == "valuation_status": kwargs.update(nullable=False, server_default="pending")
        elif name == "record_disposition": kwargs.update(nullable=False, server_default="operational")
        op.add_column("srp_requests", sa.Column(name, type_, *args, **kwargs))
    for column in ("operation_id", "loss_reason_id", "corporation_id", "alliance_id", "ship_type_id", "ship_group_id", "system_id", "region_id", "security_class", "killmail_id", "data_source", "valuation_source", "valuation_region_id", "valuation_status", "valuation_override_by_user_id", "record_disposition", "duplicate_of_request_id"):
        op.create_index(f"ix_srp_requests_{column}", "srp_requests", [column])
    op.create_index("ix_srp_loss_doctrine_status", "srp_requests", ["loss_occurred_at", "doctrine_id", "status"])
    op.create_index("ix_srp_loss_disposition", "srp_requests", ["loss_occurred_at", "record_disposition"])

    # Existing requests keep their prior labels and become explicitly manual/pending operational records.
    op.execute("UPDATE srp_requests SET entered_timezone='UTC', data_source='manual', valuation_status='pending', record_disposition='operational'")
    op.execute("UPDATE srp_requests s SET corporation_id=c.corporation_id, alliance_id=c.alliance_id, corporation_name_snapshot=corp.name, alliance_name_snapshot=a.name FROM eve_characters c LEFT JOIN eve_corporations corp ON corp.id=c.corporation_id LEFT JOIN eve_alliances a ON a.id=c.alliance_id WHERE s.character_id=c.id")
    op.execute("UPDATE srp_requests s SET ship_type_id=f.ship_type_id, ship_name_snapshot=t.name, ship_group_id=t.group_id, ship_group_name_snapshot=g.name FROM character_fittings f LEFT JOIN eve_types t ON t.type_id=f.ship_type_id LEFT JOIN eve_groups g ON g.group_id=t.group_id WHERE s.fitting_id=f.id")

    op.create_table(
        "srp_request_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("srp_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("old_values", sa.JSON()), sa.Column("new_values", sa.JSON()), sa.Column("event_metadata", sa.JSON()),
        sa.Column("reason", sa.Text()),
    )
    for column in ("request_id", "event_type", "actor_user_id", "occurred_at"):
        op.create_index(f"ix_srp_request_events_{column}", "srp_request_events", [column])
    op.execute("INSERT INTO srp_request_events (request_id,event_type,actor_user_id,occurred_at,new_values) SELECT id, CASE WHEN status='draft' THEN 'draft_created' ELSE 'legacy_record_imported' END, requesting_user_id, created_at, json_build_object('status',status) FROM srp_requests")


def downgrade() -> None:
    op.drop_table("srp_request_events")
    op.drop_index("ix_srp_loss_disposition", table_name="srp_requests")
    op.drop_index("ix_srp_loss_doctrine_status", table_name="srp_requests")
    names = ["operation_id", "loss_reason_id", "corporation_id", "alliance_id", "ship_type_id", "ship_group_id", "system_id", "region_id", "doctrine_priority_code_snapshot", "fitting_snapshot", "corporation_name_snapshot", "alliance_name_snapshot", "ship_group_name_snapshot", "operation_name_snapshot", "loss_reason_name_snapshot", "system_name_snapshot", "region_name_snapshot", "security_status", "security_class", "entered_timezone", "killmail_id", "killmail_hash", "killmail_url", "data_source", "expected_fit_value", "hull_value", "fitted_module_value", "cargo_value", "drone_fighter_value", "submission_estimated_loss_value", "killmail_destroyed_value", "killmail_dropped_value", "killmail_total_loss_value", "verified_loss_value", "authoritative_loss_value", "requested_reimbursement_amount", "approved_reimbursement_amount", "paid_reimbursement_amount", "valuation_source", "valuation_timestamp", "valuation_region_id", "valuation_market_context", "valuation_status", "manual_valuation_override", "valuation_override_reason", "valuation_override_by_user_id", "record_disposition", "duplicate_of_request_id", "exclusion_reason"]
    for name in reversed(names):
        op.drop_column("srp_requests", name)
    op.drop_table("srp_loss_reasons")
    op.drop_table("srp_operations")
