"""Save the selected home city and nearby-area preference."""
from alembic import op
import sqlalchemy as sa
revision = '13_home_city'
down_revision = '12_catalog_places'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('user_preferences',sa.Column('home_city',sa.String(16),nullable=True))
    op.add_column('user_preferences',sa.Column('include_nearby',sa.Boolean(),nullable=False,server_default=sa.false()))

def downgrade():
    op.drop_column('user_preferences','include_nearby')
    op.drop_column('user_preferences','home_city')
