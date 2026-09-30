"""Distinguish timed sessions, published periods and undated places.

Revision ID: 12_catalog_places
Revises: 3887022d9d15
"""
from alembic import op
import sqlalchemy as sa
revision = '12_catalog_places'
down_revision = '3887022d9d15'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('events', sa.Column('kind', sa.String(16), nullable=False, server_default='event'))
    op.add_column('events', sa.Column('schedule_note', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('import_version', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('event_occurrences', sa.Column('schedule_kind', sa.String(16), nullable=False, server_default='session'))
    op.add_column('event_occurrences', sa.Column('external_url', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('event_occurrences', 'external_url')
    op.drop_column('event_occurrences', 'schedule_kind')
    op.drop_column('events', 'schedule_note')
    op.drop_column('events', 'import_version')
    op.drop_column('events', 'kind')
