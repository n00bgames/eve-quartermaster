"""Add Calendar and Events planning, registration, attendance, and analytics records.

Revision ID: 0059_calendar_events
Revises: 0058_exchange_public_auctions
"""

from alembic import op
import sqlalchemy as sa


revision = "0059_calendar_events"
down_revision = "0058_exchange_public_auctions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doctrines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("external_url", sa.String(1000)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_doctrines_name", "doctrines", ["name"])
    op.create_index("ix_doctrines_created_by_user_id", "doctrines", ["created_by_user_id"])
    op.create_index("ix_doctrines_archived_at", "doctrines", ["archived_at"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("lifecycle_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("registration_status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("formup_at", sa.DateTime(timezone=True)),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("estimated_duration_minutes", sa.Integer()),
        sa.Column("operational_area", sa.String(500)),
        sa.Column("route_notes", sa.Text()),
        sa.Column("discord_voice_label", sa.String(255)),
        sa.Column("discord_voice_url", sa.String(1000)),
        sa.Column("discord_guild_id", sa.String(64)),
        sa.Column("discord_channel_id", sa.String(64)),
        sa.Column("lead_character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("lead_name_snapshot", sa.String(255)),
        sa.Column("doctrine_mode", sa.String(32), nullable=False, server_default="none"),
        sa.Column("doctrine_id", sa.Integer(), sa.ForeignKey("doctrines.id", ondelete="SET NULL")),
        sa.Column("doctrine_manual_name", sa.String(255)),
        sa.Column("doctrine_external_url", sa.String(1000)),
        sa.Column("doctrine_notes", sa.Text()),
        sa.Column("related_url", sa.String(1000)),
        sa.Column("instructions", sa.Text()),
        sa.Column("audience_kind", sa.String(32), nullable=False, server_default="all_members"),
        sa.Column("audience_corporation_id", sa.Integer(), sa.ForeignKey("eve_corporations.id", ondelete="SET NULL")),
        sa.Column("audience_alliance_id", sa.Integer(), sa.ForeignKey("eve_alliances.id", ondelete="SET NULL")),
        sa.Column("composition_visibility", sa.String(32), nullable=False, server_default="participants"),
        sa.Column("participant_limit", sa.Integer()),
        sa.Column("limit_basis", sa.String(16), nullable=False, server_default="characters"),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("formup_at IS NULL OR formup_at <= start_at", name="ck_events_formup_before_start"),
        sa.CheckConstraint("end_at IS NULL OR end_at > start_at", name="ck_events_end_after_start"),
        sa.CheckConstraint("end_at IS NULL OR estimated_duration_minutes IS NULL", name="ck_events_end_or_duration"),
        sa.CheckConstraint(
            "estimated_duration_minutes IS NULL OR (estimated_duration_minutes >= 1 AND estimated_duration_minutes <= 43200)",
            name="ck_events_duration_range",
        ),
        sa.CheckConstraint("participant_limit IS NULL OR participant_limit > 0", name="ck_events_participant_limit_positive"),
        sa.CheckConstraint(
            "audience_kind != 'corporation' OR audience_corporation_id IS NOT NULL",
            name="ck_events_corporation_audience",
        ),
        sa.CheckConstraint(
            "audience_kind != 'alliance' OR audience_alliance_id IS NOT NULL",
            name="ck_events_alliance_audience",
        ),
    )
    for column in (
        "title",
        "event_type",
        "lifecycle_status",
        "registration_status",
        "created_by_user_id",
        "formup_at",
        "start_at",
        "end_at",
        "lead_character_id",
        "doctrine_mode",
        "doctrine_id",
        "audience_kind",
        "audience_corporation_id",
        "audience_alliance_id",
        "locked_by_user_id",
    ):
        op.create_index(f"ix_events_{column}", "events", [column])

    op.create_table(
        "event_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_role", sa.String(24), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("system_id", sa.Integer(), sa.ForeignKey("eve_systems.system_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")),
        sa.Column("eve_location_id", sa.BigInteger()),
        sa.Column("location_name_snapshot", sa.String(500)),
        sa.Column("notes", sa.String(1000)),
        sa.CheckConstraint("sort_order >= 0", name="ck_event_locations_sort_order"),
    )
    for column in ("event_id", "location_role", "system_id", "location_id", "eve_location_id"):
        op.create_index(f"ix_event_locations_{column}", "event_locations", [column])
    op.create_index(
        "uq_event_locations_formup",
        "event_locations",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("location_role = 'formup'"),
    )
    op.create_index(
        "uq_event_locations_destination",
        "event_locations",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("location_role = 'destination'"),
    )

    op.create_table(
        "event_role_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_key", sa.String(48), nullable=False),
        sa.Column("custom_label", sa.String(120)),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("event_id", "role_key", "custom_label", name="uq_event_role_requirement"),
        sa.CheckConstraint("requested_quantity > 0", name="ck_event_role_requirement_quantity"),
        sa.CheckConstraint("sort_order >= 0", name="ck_event_role_requirement_sort_order"),
    )
    op.create_index("ix_event_role_requirements_event_id", "event_role_requirements", ["event_id"])
    op.create_index("ix_event_role_requirements_role_key", "event_role_requirements", ["role_key"])

    op.create_table(
        "event_doctrine_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "role_requirement_id",
            sa.Integer(),
            sa.ForeignKey("event_role_requirements.id", ondelete="SET NULL"),
        ),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("requested_quantity > 0", name="ck_event_doctrine_requirement_quantity"),
        sa.CheckConstraint("sort_order >= 0", name="ck_event_doctrine_requirement_sort_order"),
    )
    op.create_index("ix_event_doctrine_requirements_event_id", "event_doctrine_requirements", ["event_id"])
    op.create_index(
        "ix_event_doctrine_requirements_role_requirement_id",
        "event_doctrine_requirements",
        ["role_requirement_id"],
    )

    op.create_table(
        "event_doctrine_requirement_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "requirement_id",
            sa.Integer(),
            sa.ForeignKey("event_doctrine_requirements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ship_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id", ondelete="SET NULL")),
        sa.Column("fitting_id", sa.Integer(), sa.ForeignKey("character_fittings.id", ondelete="SET NULL")),
        sa.Column("manual_name_snapshot", sa.String(255)),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "ship_type_id IS NOT NULL OR fitting_id IS NOT NULL OR manual_name_snapshot IS NOT NULL",
            name="ck_event_doctrine_option_identity",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_event_doctrine_option_sort_order"),
    )
    for column in ("requirement_id", "ship_type_id", "fitting_id"):
        op.create_index(
            f"ix_event_doctrine_requirement_options_{column}",
            "event_doctrine_requirement_options",
            [column],
        )

    op.create_table(
        "event_user_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("notes", sa.String(500)),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_user_response"),
    )
    for column in ("event_id", "user_id", "status"):
        op.create_index(f"ix_event_user_responses_{column}", "event_user_responses", [column])

    op.create_table(
        "event_character_registrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("character_eve_id_snapshot", sa.BigInteger(), nullable=False),
        sa.Column("character_name_snapshot", sa.String(255), nullable=False),
        sa.Column("corporation_name_snapshot", sa.String(255)),
        sa.Column("alliance_name_snapshot", sa.String(255)),
        sa.Column("registration_status", sa.String(24), nullable=False, server_default="registered"),
        sa.Column("confirmation_status", sa.String(24), nullable=False, server_default="tentative"),
        sa.Column("planned_ship_source", sa.String(24), nullable=False, server_default="undecided"),
        sa.Column("ship_type_id", sa.Integer(), sa.ForeignKey("eve_types.type_id", ondelete="SET NULL")),
        sa.Column("ship_name_snapshot", sa.String(255)),
        sa.Column("saved_fitting_id", sa.Integer(), sa.ForeignKey("character_fittings.id", ondelete="SET NULL")),
        sa.Column("fitting_name_snapshot", sa.String(255)),
        sa.Column("fitting_updated_at_snapshot", sa.DateTime(timezone=True)),
        sa.Column(
            "doctrine_requirement_id",
            sa.Integer(),
            sa.ForeignKey("event_doctrine_requirements.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "doctrine_option_id",
            sa.Integer(),
            sa.ForeignKey("event_doctrine_requirement_options.id", ondelete="SET NULL"),
        ),
        sa.Column("role_key", sa.String(48)),
        sa.Column("custom_role", sa.String(120)),
        sa.Column("freeform_ship_description", sa.String(255)),
        sa.Column("notes", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in (
        "event_id",
        "user_id",
        "character_id",
        "registration_status",
        "confirmation_status",
        "ship_type_id",
        "saved_fitting_id",
        "doctrine_requirement_id",
        "doctrine_option_id",
        "role_key",
    ):
        op.create_index(
            f"ix_event_character_registrations_{column}",
            "event_character_registrations",
            [column],
        )
    op.create_index(
        "uq_event_character_registration",
        "event_character_registrations",
        ["event_id", "user_id", "character_id"],
        unique=True,
        postgresql_where=sa.text("character_id IS NOT NULL"),
    )

    op.create_table(
        "event_attendance_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "registration_id",
            sa.Integer(),
            sa.ForeignKey("event_character_registrations.id", ondelete="SET NULL"),
        ),
        sa.Column("attendee_source", sa.String(32), nullable=False),
        sa.Column("attendance_status", sa.String(24), nullable=False, server_default="attended"),
        sa.Column("linked_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("eve_characters.id", ondelete="SET NULL")),
        sa.Column("character_eve_id_snapshot", sa.BigInteger()),
        sa.Column("display_name_snapshot", sa.String(255), nullable=False),
        sa.Column("corporation_name_snapshot", sa.String(255)),
        sa.Column("alliance_name_snapshot", sa.String(255)),
        sa.Column("checked_in_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.String(1000)),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "attendee_source != 'registration' OR registration_id IS NOT NULL",
            name="ck_event_attendance_registration_source",
        ),
        sa.CheckConstraint(
            "attendee_source != 'linked_character' OR character_id IS NOT NULL",
            name="ck_event_attendance_linked_source",
        ),
        sa.CheckConstraint(
            "attendee_source != 'external_character' OR character_eve_id_snapshot IS NOT NULL",
            name="ck_event_attendance_external_source",
        ),
    )
    for column in (
        "event_id",
        "registration_id",
        "attendee_source",
        "attendance_status",
        "linked_user_id",
        "character_id",
        "character_eve_id_snapshot",
        "recorded_by_user_id",
    ):
        op.create_index(f"ix_event_attendance_entries_{column}", "event_attendance_entries", [column])
    op.create_index(
        "uq_event_attendance_registration",
        "event_attendance_entries",
        ["event_id", "registration_id"],
        unique=True,
        postgresql_where=sa.text("registration_id IS NOT NULL"),
    )
    op.create_index(
        "uq_event_attendance_character",
        "event_attendance_entries",
        ["event_id", "character_eve_id_snapshot"],
        unique=True,
        postgresql_where=sa.text("character_eve_id_snapshot IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("event_attendance_entries")
    op.drop_table("event_character_registrations")
    op.drop_table("event_user_responses")
    op.drop_table("event_doctrine_requirement_options")
    op.drop_table("event_doctrine_requirements")
    op.drop_table("event_role_requirements")
    op.drop_table("event_locations")
    op.drop_table("events")
    op.drop_table("doctrines")
