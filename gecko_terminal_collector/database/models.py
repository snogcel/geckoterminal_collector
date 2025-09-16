"""
SQLAlchemy database models for the GeckoTerminal collector system.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()


class DEX(Base):
    """DEX information table."""
    
    __tablename__ = "dexes"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    network = Column(String(20), nullable=False)
    last_updated = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Additional metadata (for PostgreSQL compatibility)
    metadata_json = Column(Text, default="{}")  # JSON metadata
    
    # Relationships
    pools = relationship("Pool", back_populates="dex", cascade="all, delete-orphan")


class Pool(Base):
    """Pool information table."""
    
    __tablename__ = "pools"
    
    id = Column(String(100), primary_key=True)
    address = Column(String(100), nullable=False)
    name = Column(String(200))
    dex_id = Column(String(50), ForeignKey("dexes.id"), nullable=False)
    base_token_id = Column(String(100))
    quote_token_id = Column(String(100))
    reserve_usd = Column(Numeric(20, 8))
    created_at = Column(DateTime)
    last_updated = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Discovery-related fields
    activity_score = Column(Numeric(5, 2))  # Activity score 0-100
    discovery_source = Column(String(20), default="auto")  # "auto", "watchlist", "manual"
    collection_priority = Column(String(10), default="normal")  # "high", "normal", "low", "paused"
    auto_discovered_at = Column(DateTime)  # When pool was auto-discovered
    last_activity_check = Column(DateTime)  # Last time activity was checked
    
    # Additional metadata (for PostgreSQL compatibility)
    metadata_json = Column(Text, default="{}")  # JSON metadata
    
    # Relationships
    dex = relationship("DEX", back_populates="pools")
    ohlcv_data = relationship("OHLCVData", back_populates="pool", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="pool", cascade="all, delete-orphan")
    watchlist_entries = relationship("WatchlistEntry", back_populates="pool", cascade="all, delete-orphan")


class Token(Base):
    """Token information table."""
    
    __tablename__ = "tokens"
    
    id = Column(String(100), primary_key=True)
    address = Column(String(100), nullable=False)
    name = Column(String(200))
    symbol = Column(String(20))
    decimals = Column(Integer)
    network = Column(String(20), nullable=False)
    last_updated = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Additional metadata (for PostgreSQL compatibility)
    metadata_json = Column(Text, default="{}")  # JSON metadata


class OHLCVData(Base):
    """OHLCV data table."""
    
    __tablename__ = "ohlcv_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True) # SQLite's auto-increment only works with INTEGER types, not SMALLINT.
    pool_id = Column(String(100), ForeignKey("pools.id"), nullable=False)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    open_price = Column(Numeric(30, 18), nullable=False)
    high_price = Column(Numeric(30, 18), nullable=False)
    low_price = Column(Numeric(30, 18), nullable=False)
    close_price = Column(Numeric(30, 18), nullable=False)
    volume_usd = Column(Numeric(20, 8), nullable=False)
    datetime = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.current_timestamp())
    
    # Unique constraint to prevent duplicates
    __table_args__ = (
        UniqueConstraint('pool_id', 'timeframe', 'timestamp', name='uq_ohlcv_pool_timeframe_timestamp'),
    )
    
    # Relationships
    pool = relationship("Pool", back_populates="ohlcv_data")


class Trade(Base):
    """Trade data table."""
    
    __tablename__ = "trades"
    
    id = Column(String(200), primary_key=True)
    pool_id = Column(String(100), ForeignKey("pools.id"), nullable=False)
    block_number = Column(BigInteger)
    tx_hash = Column(String(100))
    tx_from_address = Column(String(100))
    from_token_amount = Column(Numeric(30, 18))
    to_token_amount = Column(Numeric(30, 18))
    price_usd = Column(Numeric(30, 18))
    volume_usd = Column(Numeric(20, 8))
    side = Column(String(10))
    block_timestamp = Column(DateTime)
    created_at = Column(DateTime, default=func.current_timestamp())
    
    # Relationships
    pool = relationship("Pool", back_populates="trades")


class WatchlistEntry(Base):
    """Watchlist table."""
    
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pool_id = Column(String(200), ForeignKey("pools.id"), nullable=False)
    token_symbol = Column(String(50))
    token_name = Column(String(200))
    network_address = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps (PostgreSQL compatibility)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Additional metadata (PostgreSQL compatibility)
    metadata_json = Column(Text, default="{}")  # JSON metadata
    
    # Unique constraint to prevent duplicate watchlist entries
    __table_args__ = (
        UniqueConstraint('pool_id', name='uq_watchlist_pool_id'),
    )
    
    # Relationships
    pool = relationship("Pool", back_populates="watchlist_entries")


class CollectionMetadata(Base):
    """Collection metadata for tracking collector runs."""
    
    __tablename__ = "collection_metadata"
    
    collector_type = Column(String(50), primary_key=True)
    last_run = Column(DateTime)
    last_success = Column(DateTime)
    run_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    total_execution_time = Column(Numeric(10, 3), default=0.0)
    total_records_collected = Column(BigInteger, default=0)
    average_execution_time = Column(Numeric(10, 3), default=0.0)
    success_rate = Column(Numeric(5, 2), default=100.0)
    health_score = Column(Numeric(5, 2), default=100.0)
    last_updated = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())


class ExecutionHistory(Base):
    """Execution history for detailed tracking of collection runs."""
    
    __tablename__ = "execution_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    collector_type = Column(String(50), nullable=False)
    execution_id = Column(String(100), nullable=False, unique=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    status = Column(String(20), nullable=False)  # success, failure, partial, timeout, cancelled
    records_collected = Column(Integer, default=0)
    execution_time = Column(Numeric(10, 3))  # in seconds
    error_message = Column(Text)
    warnings = Column(Text)  # JSON array of warnings
    execution_metadata = Column(Text)  # JSON metadata
    created_at = Column(DateTime, default=func.current_timestamp())


class PerformanceMetrics(Base):
    """Performance metrics for operational visibility."""
    
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    collector_type = Column(String(50), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Numeric(20, 8), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    labels = Column(Text)  # JSON labels
    created_at = Column(DateTime, default=func.current_timestamp())
    
    # Index for efficient querying
    __table_args__ = (
        UniqueConstraint('collector_type', 'metric_name', 'timestamp', name='uq_metrics_collector_metric_timestamp'),
    )


class NewPoolsHistory(Base):
    """New pools history table for comprehensive historical tracking."""
    
    __tablename__ = "new_pools_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pool_id = Column(String(255), nullable=False)
    type = Column(String(20), default='pool')
    name = Column(String(255))
    base_token_price_usd = Column(Numeric(20, 10))
    base_token_price_native_currency = Column(Numeric(20, 10))
    quote_token_price_usd = Column(Numeric(20, 10))
    quote_token_price_native_currency = Column(Numeric(20, 10))
    address = Column(String(255))
    reserve_in_usd = Column(Numeric(20, 4))
    pool_created_at = Column(DateTime)
    fdv_usd = Column(Numeric(20, 4))
    market_cap_usd = Column(Numeric(20, 4))
    price_change_percentage_h1 = Column(Numeric(10, 4))
    price_change_percentage_h24 = Column(Numeric(10, 4))
    transactions_h1_buys = Column(Integer)
    transactions_h1_sells = Column(Integer)
    transactions_h24_buys = Column(Integer)
    transactions_h24_sells = Column(Integer)
    volume_usd_h24 = Column(Numeric(20, 4))
    dex_id = Column(String(100))
    base_token_id = Column(String(255))
    quote_token_id = Column(String(255))
    network_id = Column(String(50))
    collected_at = Column(DateTime, default=func.current_timestamp())
    
    # Unique constraint to prevent duplicate records for same pool at same collection time
    __table_args__ = (
        UniqueConstraint('pool_id', 'collected_at', name='uq_new_pools_history_pool_collected'),
    )


class DiscoveryMetadata(Base):
    """Track discovery operations and statistics."""
    
    __tablename__ = "discovery_metadata"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    discovery_type = Column(String(50), nullable=False)  # "dex", "pool", "token"
    target_dex = Column(String(50))
    pools_discovered = Column(Integer, default=0)
    pools_filtered = Column(Integer, default=0)
    discovery_time = Column(DateTime, nullable=False)
    execution_time_seconds = Column(Numeric(10, 3))
    api_calls_made = Column(Integer, default=0)
    errors_encountered = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.current_timestamp())
    
    # Indexes for efficient querying
    __table_args__ = (
        # Index for querying by discovery type and time
        # Note: SQLAlchemy will create these as separate indexes
    )


class SystemAlerts(Base):
    """System alerts for monitoring and failure notification."""
    
    __tablename__ = "system_alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(100), nullable=False, unique=True)
    level = Column(String(20), nullable=False)  # info, warning, error, critical
    collector_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    acknowledged = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    alert_metadata = Column(Text)  # JSON metadata
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())