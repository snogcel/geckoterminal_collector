"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2025-01-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema."""
    
    # Create dexes table
    op.create_table(
        'dexes',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('network', sa.String(20), nullable=False),
        sa.Column('last_updated', sa.DateTime, server_default=sa.func.current_timestamp()),
    )
    
    # Create tokens table
    op.create_table(
        'tokens',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('address', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200)),
        sa.Column('symbol', sa.String(20)),
        sa.Column('decimals', sa.Integer),
        sa.Column('network', sa.String(20), nullable=False),
        sa.Column('last_updated', sa.DateTime, server_default=sa.func.current_timestamp()),
    )
    
    # Create pools table
    op.create_table(
        'pools',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('address', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200)),
        sa.Column('dex_id', sa.String(50), nullable=False),
        sa.Column('base_token_id', sa.String(100)),
        sa.Column('quote_token_id', sa.String(100)),
        sa.Column('reserve_usd', sa.Numeric(20, 8)),
        sa.Column('created_at', sa.DateTime),
        sa.Column('last_updated', sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['dex_id'], ['dexes.id']),
    )
    
    # Create ohlcv_data table
    op.create_table(
        'ohlcv_data',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('pool_id', sa.String(100), nullable=False),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('timestamp', sa.BigInteger, nullable=False),
        sa.Column('open_price', sa.Numeric(30, 18), nullable=False),
        sa.Column('high_price', sa.Numeric(30, 18), nullable=False),
        sa.Column('low_price', sa.Numeric(30, 18), nullable=False),
        sa.Column('close_price', sa.Numeric(30, 18), nullable=False),
        sa.Column('volume_usd', sa.Numeric(20, 8), nullable=False),
        sa.Column('datetime', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['pool_id'], ['pools.id']),
        sa.UniqueConstraint('pool_id', 'timeframe', 'timestamp', name='uq_ohlcv_pool_timeframe_timestamp'),
    )
    
    # Create trades table
    op.create_table(
        'trades',
        sa.Column('id', sa.String(200), primary_key=True),
        sa.Column('pool_id', sa.String(100), nullable=False),
        sa.Column('block_number', sa.BigInteger),
        sa.Column('tx_hash', sa.String(100)),
        sa.Column('tx_from_address', sa.String(100)),
        sa.Column('from_token_amount', sa.Numeric(30, 18)),
        sa.Column('to_token_amount', sa.Numeric(30, 18)),
        sa.Column('price_usd', sa.Numeric(30, 18)),
        sa.Column('volume_usd', sa.Numeric(20, 8)),
        sa.Column('side', sa.String(10)),
        sa.Column('block_timestamp', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['pool_id'], ['pools.id']),
    )
    
    # Create watchlist table
    op.create_table(
        'watchlist',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('pool_id', sa.String(100), nullable=False),
        sa.Column('token_symbol', sa.String(20)),
        sa.Column('token_name', sa.String(200)),
        sa.Column('network_address', sa.String(100)),
        sa.Column('added_at', sa.DateTime, server_default=sa.func.current_timestamp()),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.ForeignKeyConstraint(['pool_id'], ['pools.id']),
        sa.UniqueConstraint('pool_id', name='uq_watchlist_pool_id'),
    )
    
    # Create collection_metadata table
    op.create_table(
        'collection_metadata',
        sa.Column('collector_type', sa.String(50), primary_key=True),
        sa.Column('last_run', sa.DateTime),
        sa.Column('last_success', sa.DateTime),
        sa.Column('run_count', sa.Integer, default=0),
        sa.Column('error_count', sa.Integer, default=0),
        sa.Column('last_error', sa.Text),
    )
    
    # Create indexes for better query performance
    op.create_index('idx_ohlcv_pool_timeframe', 'ohlcv_data', ['pool_id', 'timeframe'])
    op.create_index('idx_ohlcv_datetime', 'ohlcv_data', ['datetime'])
    op.create_index('idx_trades_pool_timestamp', 'trades', ['pool_id', 'block_timestamp'])
    op.create_index('idx_trades_volume', 'trades', ['volume_usd'])
    op.create_index('idx_pools_dex', 'pools', ['dex_id'])
    op.create_index('idx_watchlist_active', 'watchlist', ['is_active'])


def downgrade() -> None:
    """Drop all tables."""
    
    # Drop indexes first
    op.drop_index('idx_watchlist_active')
    op.drop_index('idx_pools_dex')
    op.drop_index('idx_trades_volume')
    op.drop_index('idx_trades_pool_timestamp')
    op.drop_index('idx_ohlcv_datetime')
    op.drop_index('idx_ohlcv_pool_timeframe')
    
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('collection_metadata')
    op.drop_table('watchlist')
    op.drop_table('trades')
    op.drop_table('ohlcv_data')
    op.drop_table('pools')
    op.drop_table('tokens')
    op.drop_table('dexes')