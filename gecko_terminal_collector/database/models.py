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


class OHLCVData(Base):
    """OHLCV data table."""
    
    __tablename__ = "ohlcv_data"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
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
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, nullable=False)
    pool_id = Column(String(100), ForeignKey("pools.id"), nullable=False)
    token_symbol = Column(String(20))
    token_name = Column(String(200))
    network_address = Column(String(100))
    added_at = Column(DateTime, default=func.current_timestamp())
    is_active = Column(Boolean, default=True)
    
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