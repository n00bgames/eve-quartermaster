"""Personal layouts/themes and public site branding."""
from alembic import op
import sqlalchemy as sa
revision = "0095_appearance"
down_revision = "0094_battle_report_corporation"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("user_appearance", sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),primary_key=True),
        sa.Column("preferences",sa.JSON(),nullable=False),sa.Column("banner",sa.LargeBinary()),sa.Column("revision",sa.Integer(),nullable=False))
    op.create_table("site_branding",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("banner",sa.LargeBinary()),
        sa.Column("login_background",sa.LargeBinary()),sa.Column("revision",sa.Integer(),nullable=False))

def downgrade():
    op.drop_table("site_branding")
    op.drop_table("user_appearance")
