"""Add discovery fields to pools table

Revision ID: 005_add_pool_discovery_fields
Revises: 004_discovery_metadata_table
Create Date: 2025-09-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '005_add_pool_discovery_fields'
down_revision = '004_discovery_metadata_table'
branch_labels = None
depends_on = None


def upgrade():
    """Add discovery-related fields to pools table."""
    # Add new columns to pools table
    op.add_column('pools', sa.Column('activity_score', sa.Numeric(5, 2), nullable=True))
    op.add_column('pools', sa.Column('discovery_source', sa.String(20), nullable=True, default='auto'))
    op.add_column('pools', sa.Column('collection_priority', sa.String(10), nullable=True, default='normal'))
    op.add_column('pools', sa.Column('auto_discovered_at', sa.DateTime(), nullable=True))
    op.add_column('pools', sa.Column('last_activity_check', sa.DateTime(), nullable=True))


def downgrade():
    """Remove discovery-related fields from pools table."""
    # Remove columns from pools table
    op.drop_column('pools', 'last_activity_check')
    op.drop_column('pools', 'auto_discovered_at')
    op.drop_column('pools', 'collection_priority')
    op.drop_column('pools', 'discovery_source')
    op.drop_column('pools', 'activity_score')