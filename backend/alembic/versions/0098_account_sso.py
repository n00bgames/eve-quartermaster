"""Browser-bound account SSO and verified EVE character ownership hashes."""
from alembic import op
import sqlalchemy as sa

revision = '0098_account_sso'
down_revision = '0097_sde_maintenance'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('esi_tokens', sa.Column('sso_owner_hash', sa.String(128)))
    op.create_table('account_sso_attempts',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('browser_hash', sa.String(64), nullable=False),
        sa.Column('encrypted_verifier', sa.Text(), nullable=False),
        sa.Column('invite_id', sa.Integer(), sa.ForeignKey('user_invites.id')),
        sa.Column('remember_me', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True)))
    op.create_index('ix_account_sso_attempts_expires_at', 'account_sso_attempts', ['expires_at'])


def downgrade():
    op.drop_table('account_sso_attempts')
    op.drop_column('esi_tokens', 'sso_owner_hash')
