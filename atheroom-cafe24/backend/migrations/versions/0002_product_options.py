from alembic import op
import sqlalchemy as sa

revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('products',sa.Column('option_settings',sa.JSON(),nullable=False,server_default='{}'))

def downgrade():
    op.drop_column('products','option_settings')
