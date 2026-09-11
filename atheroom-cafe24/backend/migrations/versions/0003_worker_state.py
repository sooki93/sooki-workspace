"""Record the subscription worker heartbeat for the cloud API."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('worker_state',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('online', sa.Boolean(), nullable=False),
        sa.Column('ai_ready', sa.Boolean(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False))


def downgrade():
    op.drop_table('worker_state')
