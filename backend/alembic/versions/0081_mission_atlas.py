"""Public SDE agent directory for Navigation and Missions/LP."""
from alembic import op
import sqlalchemy as sa

revision = "0081_mission_atlas"
down_revision = "0080_system_distances"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("eve_agents",
        sa.Column("agent_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("corporation_id", sa.Integer(), nullable=False),
        sa.Column("corporation_name", sa.String(255), nullable=False),
        sa.Column("faction_id", sa.Integer()),
        sa.Column("division_id", sa.Integer()),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("agent_type_id", sa.Integer()),
        sa.Column("is_locator", sa.Boolean(), nullable=False),
        sa.Column("location_id", sa.Integer()),
        sa.Column("system_id", sa.Integer()))
    for field in ("name", "corporation_id", "faction_id", "division_id", "level", "system_id"):
        op.create_index(f"ix_eve_agents_{field}", "eve_agents", [field])


def downgrade():
    op.drop_table("eve_agents")
