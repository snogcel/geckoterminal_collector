"""Add new_pools_history table for predictive modeling

Revision ID: 003
Revises: 002
Create Date: 2025-01-28 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new_pools_history table for comprehensive new pools tracking."""
    
    # Create new_pools_history table
    op.create_table(
        'new_pools_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('pool_id', sa.String(255), nullable=False),
        sa.Column('type', sa.String(20), default='pool'),
        sa.Column('name', sa.String(255)),
        sa.Column('base_token_price_usd', sa.Numeric(20, 10)),
        sa.Column('base_token_price_native_currency', sa.Numeric(20, 10)),
        sa.Column('quote_token_price_usd', sa.Numeric(20, 10)),
        sa.Column('quote_token_price_native_currency', sa.Numeric(20, 10)),
        sa.Column('address', sa.String(255)),
        sa.Column('reserve_in_usd', sa.Numeric(20, 4)),
        sa.Column('pool_created_at', sa.DateTime),
        sa.Column('fdv_usd', sa.Numeric(20, 4)),
        sa.Column('market_cap_usd', sa.Numeric(20, 4)),
        sa.Column('price_change_percentage_h1', sa.Numeric(10, 4)),
        sa.Column('price_change_percentage_h24', sa.Numeric(10, 4)),
        sa.Column('transactions_h1_buys', sa.Integer),
        sa.Column('transactions_h1_sells', sa.Integer),
        sa.Column('transactions_h24_buys', sa.Integer),
        sa.Column('transactions_h24_sells', sa.Integer),
        sa.Column('volume_usd_h24', sa.Numeric(20, 4)),
        sa.Column('dex_id', sa.String(100)),
        sa.Column('base_token_id', sa.String(255)),
        sa.Column('quote_token_id', sa.String(255)),
        sa.Column('network_id', sa.String(50)),
        sa.Column('collected_at', sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('pool_id', 'collected_at', name='uq_new_pools_history_pool_collected'),
    )
    
    # Create indexes for efficient querying
    op.create_index('idx_new_pools_history_pool_id', 'new_pools_history', ['pool_id'])
    op.create_index('idx_new_pools_history_collected_at', 'new_pools_history', ['collected_at'])
    op.create_index('idx_new_pools_history_network_dex', 'new_pools_history', ['network_id', 'dex_id'])
    op.create_index('idx_new_pools_history_pool_created_at', 'new_pools_history', ['pool_created_at'])


def downgrade() -> None:
    """Drop new_pools_history table."""
    
    # Drop indexes first
    op.drop_index('idx_new_pools_history_pool_created_at')
    op.drop_index('idx_new_pools_history_network_dex')
    op.drop_index('idx_new_pools_history_collected_at')
    op.drop_index('idx_new_pools_history_pool_id')
    
    # Drop table
    op.drop_table('new_pools_history')