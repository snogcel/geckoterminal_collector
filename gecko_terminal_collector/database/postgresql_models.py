"""
PostgreSQL-optimized database models with partitioning and advanced features.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, 
    Numeric, String, Text, UniqueConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class DEX(Base):
    """DEX (Decentralized Exchange) model optimized for PostgreSQL."""
    
    __tablename__ = 'dexes'
    
    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    network = Column(String(50), nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    last_updated = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    
    # Metadata
    metadata_json = Column(JSONB, default={})
    
    # Relationships
    pools = relationship("Pool", back_populates="dex", lazy="dynamic")
    
    # Indexes
    __table_args__ = (
        Index('idx_dexes_network', 'network'),
        Index('idx_dexes_name', 'name'),
    )


class Token(Base):
    """Token model optimized for PostgreSQL."""
    
    __tablename__ = 'tokens'
    
    id = Column(String(200), primary_key=True)  # network_address format
    address = Column(String(100), nullable=False)
    name = Column(String(200))
    symbol = Column(String(50), index=True)
    decimals = Column(Integer)
    network = Column(String(50), nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    last_updated = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    
    # Additional metadata
    metadata_json = Column(JSONB, default={})
    
    # Indexes
    __table_args__ = (
        Index('idx_tokens_network_address', 'network', 'address'),
        Index('idx_tokens_symbol_network', 'symbol', 'network'),
        UniqueConstraint('network', 'address', name='uq_tokens_network_address'),
    )


class Pool(Base):
    """Pool model optimized for PostgreSQL with enhanced indexing."""
    
    __tablename__ = 'pools'
    
    id = Column(String(200), primary_key=True)
    address = Column(String(100), nullable=False)
    name = Column(String(200))
    dex_id = Column(String(100), ForeignKey('dexes.id'), nullable=False, index=True)
    base_token_id = Column(String(200), ForeignKey('tokens.id'), index=True)
    quote_token_id = Column(String(200), ForeignKey('tokens.id'), index=True)
    reserve_usd = Column(Numeric(20, 2), default=0)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    last_updated = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    
    # Discovery and activity tracking
    activity_score = Column(Numeric(10, 2), index=True)
    discovery_source = Column(String(50), default='manual', index=True)  # 'auto', 'watchlist', 'manual'
    collection_priority = Column(String(20), default='normal', index=True)  # 'high', 'normal', 'low', 'paused'
    auto_discovered_at = Column(TIMESTAMP(timezone=True))
    last_activity_check = Column(TIMESTAMP(timezone=True))
    
    # Additional metadata
    metadata_json = Column(JSONB, default={})
    
    # Relationships
    dex = relationship("DEX", back_populates="pools")
    base_token = relationship("Token", foreign_keys=[base_token_id])
    quote_token = relationship("Token", foreign_keys=[quote_token_id])
    trades = relationship("Trade", back_populates="pool", lazy="dynamic")
    ohlcv_data = relationship("OHLCVData", back_populates="pool", lazy="dynamic")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_pools_dex_id', 'dex_id'),
        Index('idx_pools_discovery_source', 'discovery_source'),
        Index('idx_pools_collection_priority', 'collection_priority'),
        Index('idx_pools_activity_score_desc', 'activity_score', postgresql_using='btree', postgresql_ops={'activity_score': 'DESC NULLS LAST'}),
        Index('idx_pools_auto_discovered_at', 'auto_discovered_at'),
        Index('idx_pools_last_activity_check', 'last_activity_check'),
        Index('idx_pools_reserve_usd', 'reserve_usd', postgresql_using='btree', postgresql_ops={'reserve_usd': 'DESC'}),
    )


class Trade(Base):
    """
    Trade model optimized for PostgreSQL with partitioning support.
    
    This table will be partitioned by date for better performance.
    """
    
    __tablename__ = 'trades'
    
    id = Column(String(200), primary_key=True)
    pool_id = Column(String(200), ForeignKey('pools.id'), nullable=False, index=True)
    block_number = Column(BigInteger, nullable=False, index=True)
    tx_hash = Column(String(100), nullable=False, index=True)
    tx_from_address = Column(String(100))
    
    # Trade amounts
    from_token_amount = Column(Numeric(30, 10))
    to_token_amount = Column(Numeric(30, 10))
    price_usd = Column(Numeric(20, 8))
    volume_usd = Column(Numeric(20, 2), index=True)
    
    # Trade metadata
    side = Column(String(10))  # 'buy' or 'sell'
    block_timestamp = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    
    # Additional metadata
    metadata_json = Column(JSONB, default={})
    
    # Relationships
    pool = relationship("Pool", back_populates="trades")
    
    # Indexes optimized for time-series queries
    __table_args__ = (
        Index('idx_trades_pool_id_timestamp', 'pool_id', 'block_timestamp'),
        Index('idx_trades_block_timestamp_desc', 'block_timestamp', postgresql_using='btree', postgresql_ops={'block_timestamp': 'DESC'}),
        Index('idx_trades_volume_usd_desc', 'volume_usd', postgresql_using='btree', postgresql_ops={'volume_usd': 'DESC NULLS LAST'}),
        Index('idx_trades_tx_hash', 'tx_hash'),
        Index('idx_trades_block_number', 'block_number'),
        
        # Partial indexes for better performance
        Index('idx_trades_high_volume', 'pool_id', 'block_timestamp', 
              postgresql_where=text('volume_usd > 1000')),
    )


class OHLCVData(Base):
    """
    OHLCV data model optimized for PostgreSQL with partitioning support.
    
    This table will be partitioned by timeframe and date for optimal performance.
    """
    
    __tablename__ = 'ohlcv_data'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pool_id = Column(String(200), ForeignKey('pools.id'), nullable=False)
    timeframe = Column(String(10), nullable=False)  # '1m', '5m', '1h', '1d'
    timestamp = Column(BigInteger, nullable=False)
    datetime = Column(TIMESTAMP(timezone=True), nullable=False)
    
    # OHLCV values
    open_price = Column(Numeric(20, 8), nullable=False)
    high_price = Column(Numeric(20, 8), nullable=False)
    low_price = Column(Numeric(20, 8), nullable=False)
    close_price = Column(Numeric(20, 8), nullable=False)
    volume_usd = Column(Numeric(20, 2), nullable=False)
    
    # Additional metadata
    metadata_json = Column(JSONB, default={})
    
    # Relationships
    pool = relationship("Pool", back_populates="ohlcv_data")
    
    # Composite unique constraint
    __table_args__ = (
        UniqueConstraint('pool_id', 'timeframe', 'timestamp', name='uq_ohlcv_pool_timeframe_timestamp'),
        
        # Indexes for time-series queries
        Index('idx_ohlcv_pool_timeframe_datetime', 'pool_id', 'timeframe', 'datetime'),
        Index('idx_ohlcv_datetime_desc', 'datetime', postgresql_using='btree', postgresql_ops={'datetime': 'DESC'}),
        Index('idx_ohlcv_timeframe', 'timeframe'),
        Index('idx_ohlcv_volume_desc', 'volume_usd', postgresql_using='btree', postgresql_ops={'volume_usd': 'DESC'}),
        
        # Partial indexes for common queries (removed NOW() indexes due to immutability issues)
    )


class WatchlistEntry(Base):
    """Watchlist entry model for PostgreSQL."""
    
    __tablename__ = 'watchlist'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pool_id = Column(String(200), ForeignKey('pools.id'), nullable=False, unique=True)
    token_symbol = Column(String(50))
    token_name = Column(String(200))
    network_address = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    
    # Additional metadata
    metadata_json = Column(JSONB, default={})
    
    # Indexes
    __table_args__ = (
        Index('idx_watchlist_pool_id', 'pool_id'),
        Index('idx_watchlist_active', 'is_active'),
        Index('idx_watchlist_token_symbol', 'token_symbol'),
    )


class CollectionMetadata(Base):
    """Collection metadata model for PostgreSQL."""
    
    __tablename__ = 'collection_metadata'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    collector_type = Column(String(100), nullable=False, unique=True)
    last_run = Column(TIMESTAMP(timezone=True))
    last_success = Column(TIMESTAMP(timezone=True))
    run_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    
    # Additional metadata
    metadata_json = Column(JSONB, default={})
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_collection_metadata_collector_type', 'collector_type'),
        Index('idx_collection_metadata_last_run', 'last_run'),
    )


class DiscoveryMetadata(Base):
    """Discovery metadata model for PostgreSQL."""
    
    __tablename__ = 'discovery_metadata'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    discovery_type = Column(String(50), nullable=False)  # 'dex', 'pool', 'token'
    execution_time_seconds = Column(Numeric(10, 3))
    pools_discovered = Column(Integer, default=0)
    pools_filtered = Column(Integer, default=0)
    api_calls_made = Column(Integer, default=0)
    errors_encountered = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    
    # Additional metadata
    metadata_json = Column(JSONB, default={})
    
    # Indexes
    __table_args__ = (
        Index('idx_discovery_metadata_type_created', 'discovery_type', 'created_at'),
        Index('idx_discovery_metadata_created_at', 'created_at'),
    )


class NewPoolsHistory(Base):
    """New pools history model for PostgreSQL."""
    
    __tablename__ = 'new_pools_history'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pool_id = Column(String(200), ForeignKey('pools.id'), nullable=False)
    collected_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Discovery metadata
    discovery_source = Column(String(50))
    api_response_data = Column(JSONB)
    
    # Unique constraint to prevent duplicates
    __table_args__ = (
        UniqueConstraint('pool_id', 'collected_at', name='uq_new_pools_history_pool_collected'),
        Index('idx_new_pools_history_pool_id', 'pool_id'),
        Index('idx_new_pools_history_collected_at', 'collected_at'),
    )


# Partitioning setup functions (to be run after table creation)

def create_trade_partitions():
    """
    Create monthly partitions for the trades table.
    This should be run after the initial table creation.
    """
    return [
        # Example partition creation - adjust dates as needed
        """
        CREATE TABLE IF NOT EXISTS trades_y2024m01 PARTITION OF trades
        FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
        """,
        """
        CREATE TABLE IF NOT EXISTS trades_y2024m02 PARTITION OF trades
        FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
        """,
        # Add more partitions as needed
    ]


def create_ohlcv_partitions():
    """
    Create partitions for OHLCV data by timeframe and date.
    """
    return [
        # Example partition creation for different timeframes
        """
        CREATE TABLE IF NOT EXISTS ohlcv_data_1h_y2024 PARTITION OF ohlcv_data
        FOR VALUES FROM ('1h', '2024-01-01') TO ('1h', '2025-01-01');
        """,
        """
        CREATE TABLE IF NOT EXISTS ohlcv_data_1d_y2024 PARTITION OF ohlcv_data
        FOR VALUES FROM ('1d', '2024-01-01') TO ('1d', '2025-01-01');
        """,
        # Add more partitions as needed
    ]


# PostgreSQL-specific optimizations

def create_postgresql_extensions():
    """SQL commands to create useful PostgreSQL extensions."""
    return [
        "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;",
        "CREATE EXTENSION IF NOT EXISTS pg_trgm;",  # For text search
        "CREATE EXTENSION IF NOT EXISTS btree_gin;",  # For composite indexes
    ]


def create_materialized_views():
    """Create materialized views for common queries."""
    return [
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS pool_activity_summary AS
        SELECT 
            p.id,
            p.name,
            p.dex_id,
            p.activity_score,
            COUNT(t.id) as trade_count,
            SUM(t.volume_usd) as total_volume_usd,
            MAX(t.block_timestamp) as last_trade_time
        FROM pools p
        LEFT JOIN trades t ON p.id = t.pool_id 
            AND t.block_timestamp > NOW() - INTERVAL '7 days'
        GROUP BY p.id, p.name, p.dex_id, p.activity_score;
        """,
        """
        CREATE UNIQUE INDEX ON pool_activity_summary (id);
        """,
    ]