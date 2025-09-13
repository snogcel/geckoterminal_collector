"""Add discovery_metadata table for tracking discovery operations

Revision ID: 004
Revises: 003
Create Date: 2025-01-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add discovery_metadata table for tracking discovery operations and statistics."""
    
    # Create discovery_metadata table
    op.create_table(
        'discovery_metadata',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('discovery_type', sa.String(50), nullable=False),  # "dex", "pool", "token"
        sa.Column('target_dex', sa.String(50)),
        sa.Column('pools_discovered', sa.Integer, default=0),
        sa.Column('pools_filtered', sa.Integer, default=0),
        sa.Column('discovery_time', sa.DateTime, nullable=False),
        sa.Column('execution_time_seconds', sa.Numeric(10, 3)),
        sa.Column('api_calls_made', sa.Integer, default=0),
        sa.Column('errors_encountered', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.current_timestamp()),
    )
    
    # Create indexes for efficient discovery metadata queries
    op.create_index('idx_discovery_metadata_type_time', 'discovery_metadata', ['discovery_type', 'discovery_time'])
    op.create_index('idx_discovery_metadata_target_dex', 'discovery_metadata', ['target_dex'])
    op.create_index('idx_discovery_metadata_created_at', 'discovery_metadata', ['created_at'])
    op.create_index('idx_discovery_metadata_discovery_time', 'discovery_metadata', ['discovery_time'])


def downgrade() -> None:
    """Drop discovery_metadata table."""
    
    # Drop indexes first
    op.drop_index('idx_discovery_metadata_discovery_time')
    op.drop_index('idx_discovery_metadata_created_at')
    op.drop_index('idx_discovery_metadata_target_dex')
    op.drop_index('idx_discovery_metadata_type_time')
    
    # Drop table
    op.drop_table('discovery_metadata')