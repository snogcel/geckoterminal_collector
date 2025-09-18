"""
Enhanced New Pools History Model for QLib Integration and Predictive Modeling
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


class EnhancedNewPoolsHistory(Base):
    """
    Enhanced new pools history model optimized for QLib and predictive modeling.
    
    This model extends the existing structure with additional fields required for:
    - Time series analysis
    - Feature engineering
    - Predictive modeling
    - QLib integration
    """
    
    __tablename__ = 'new_pools_history_enhanced'
    
    # Primary identification
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pool_id = Column(String(200), nullable=False, index=True)
    
    # Time series keys (critical for QLib)
    timestamp = Column(BigInteger, nullable=False, index=True)  # Unix timestamp for QLib
    datetime = Column(TIMESTAMP(timezone=True), nullable=False, index=True)  # Human readable
    collection_interval = Column(String(10), default='1h')  # '1h', '4h', '1d' for different frequencies
    
    # Basic pool information
    type = Column(String(20), default='pool')
    name = Column(String(255))
    address = Column(String(255))
    network_id = Column(String(50), index=True)
    dex_id = Column(String(100), index=True)
    
    # Token information
    base_token_id = Column(String(255))
    quote_token_id = Column(String(255))
    base_token_symbol = Column(String(50))
    quote_token_symbol = Column(String(50))
    
    # Price data (OHLC-style for QLib)
    open_price_usd = Column(Numeric(20, 10))  # Opening price in the interval
    high_price_usd = Column(Numeric(20, 10))  # Highest price in the interval
    low_price_usd = Column(Numeric(20, 10))   # Lowest price in the interval
    close_price_usd = Column(Numeric(20, 10)) # Closing price in the interval
    
    # Volume and liquidity metrics
    volume_usd_interval = Column(Numeric(20, 4))  # Volume during this interval
    volume_usd_h1 = Column(Numeric(20, 4))        # 1-hour volume
    volume_usd_h24 = Column(Numeric(20, 4))       # 24-hour volume
    reserve_in_usd = Column(Numeric(20, 4))       # Total liquidity
    
    # Market metrics
    market_cap_usd = Column(Numeric(20, 4))
    fdv_usd = Column(Numeric(20, 4))
    
    # Price change indicators
    price_change_percentage_interval = Column(Numeric(10, 4))  # Change during interval
    price_change_percentage_h1 = Column(Numeric(10, 4))
    price_change_percentage_h24 = Column(Numeric(10, 4))
    
    # Trading activity metrics
    transactions_interval_buys = Column(Integer)
    transactions_interval_sells = Column(Integer)
    transactions_h1_buys = Column(Integer)
    transactions_h1_sells = Column(Integer)
    transactions_h24_buys = Column(Integer)
    transactions_h24_sells = Column(Integer)
    
    # Advanced metrics for ML features
    buy_sell_ratio_interval = Column(Numeric(10, 4))  # Buys/Sells ratio
    buy_sell_ratio_h24 = Column(Numeric(10, 4))
    volume_weighted_price = Column(Numeric(20, 10))   # VWAP
    price_volatility = Column(Numeric(10, 4))         # Price volatility measure
    
    # Liquidity metrics
    liquidity_change_percentage = Column(Numeric(10, 4))
    liquidity_depth_usd = Column(Numeric(20, 4))      # Depth of liquidity
    
    # Signal analysis (existing fields enhanced)
    signal_score = Column(Numeric(10, 4), index=True)
    volume_trend = Column(String(20))
    liquidity_trend = Column(String(20))
    momentum_indicator = Column(Numeric(10, 4))
    activity_score = Column(Numeric(10, 4))
    volatility_score = Column(Numeric(10, 4))
    
    # New predictive features
    trend_strength = Column(Numeric(10, 4))           # Trend strength indicator
    support_resistance_level = Column(Numeric(20, 10)) # Key price levels
    relative_strength_index = Column(Numeric(10, 4))  # RSI indicator
    moving_average_convergence = Column(Numeric(10, 4)) # MACD-like indicator
    
    # Pool lifecycle tracking
    pool_age_hours = Column(Integer)                   # Hours since pool creation
    pool_created_at = Column(TIMESTAMP(timezone=True))
    is_new_pool = Column(Boolean, default=True)       # Flag for new vs established pools
    
    # Data quality and metadata
    data_quality_score = Column(Numeric(5, 2))        # Quality score (0-100)
    collection_source = Column(String(50))            # Source of data collection
    api_response_hash = Column(String(64))            # Hash of raw API response
    
    # QLib-specific fields
    qlib_symbol = Column(String(100))                 # QLib-formatted symbol
    qlib_features_json = Column(JSONB)                # Pre-computed QLib features
    
    # Timestamps
    collected_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    processed_at = Column(TIMESTAMP(timezone=True))   # When processed for ML
    
    # Indexes optimized for time series and QLib queries
    __table_args__ = (
        # Unique constraint for time series data
        UniqueConstraint('pool_id', 'timestamp', 'collection_interval', 
                        name='uq_enhanced_pools_history_timeseries'),
        
        # Time series indexes
        Index('idx_enhanced_pools_timestamp', 'timestamp'),
        Index('idx_enhanced_pools_datetime', 'datetime'),
        Index('idx_enhanced_pools_pool_timestamp', 'pool_id', 'timestamp'),
        Index('idx_enhanced_pools_interval_timestamp', 'collection_interval', 'timestamp'),
        
        # QLib optimization indexes
        Index('idx_enhanced_pools_qlib_symbol', 'qlib_symbol'),
        Index('idx_enhanced_pools_symbol_timestamp', 'qlib_symbol', 'timestamp'),
        
        # Feature-based indexes for ML queries
        Index('idx_enhanced_pools_signal_score', 'signal_score', 
              postgresql_using='btree', postgresql_ops={'signal_score': 'DESC NULLS LAST'}),
        Index('idx_enhanced_pools_volume_usd', 'volume_usd_h24',
              postgresql_using='btree', postgresql_ops={'volume_usd_h24': 'DESC NULLS LAST'}),
        Index('idx_enhanced_pools_activity_score', 'activity_score',
              postgresql_using='btree', postgresql_ops={'activity_score': 'DESC NULLS LAST'}),
        
        # Network and DEX indexes
        Index('idx_enhanced_pools_network_timestamp', 'network_id', 'timestamp'),
        Index('idx_enhanced_pools_dex_timestamp', 'dex_id', 'timestamp'),
        
        # New pool tracking
        Index('idx_enhanced_pools_new_pools', 'is_new_pool', 'timestamp'),
        Index('idx_enhanced_pools_age', 'pool_age_hours'),
        
        # Data quality indexes
        Index('idx_enhanced_pools_quality', 'data_quality_score'),
        Index('idx_enhanced_pools_processed', 'processed_at'),
    )


class PoolFeatureVector(Base):
    """
    Pre-computed feature vectors for machine learning models.
    
    This table stores engineered features derived from the history data,
    optimized for fast model training and inference.
    """
    
    __tablename__ = 'pool_feature_vectors'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pool_id = Column(String(200), nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False, index=True)
    feature_set_version = Column(String(20), nullable=False)  # Version of feature engineering
    
    # Technical indicators (normalized 0-1)
    rsi_14 = Column(Numeric(5, 4))
    macd_signal = Column(Numeric(10, 6))
    bollinger_position = Column(Numeric(5, 4))
    volume_sma_ratio = Column(Numeric(10, 6))
    
    # Liquidity features
    liquidity_stability = Column(Numeric(5, 4))
    liquidity_growth_rate = Column(Numeric(10, 6))
    depth_imbalance = Column(Numeric(5, 4))
    
    # Activity features
    trader_diversity_score = Column(Numeric(5, 4))
    whale_activity_indicator = Column(Numeric(5, 4))
    retail_activity_score = Column(Numeric(5, 4))
    
    # Market structure features
    bid_ask_spread_normalized = Column(Numeric(5, 4))
    market_impact_score = Column(Numeric(5, 4))
    arbitrage_opportunity = Column(Numeric(5, 4))
    
    # Temporal features
    hour_of_day = Column(Integer)
    day_of_week = Column(Integer)
    is_weekend = Column(Boolean)
    
    # Target variables (for supervised learning)
    price_return_1h = Column(Numeric(10, 6))    # 1-hour forward return
    price_return_4h = Column(Numeric(10, 6))    # 4-hour forward return
    price_return_24h = Column(Numeric(10, 6))   # 24-hour forward return
    volume_change_1h = Column(Numeric(10, 6))   # 1-hour volume change
    
    # Risk indicators
    drawdown_risk = Column(Numeric(5, 4))
    volatility_regime = Column(String(20))      # 'low', 'medium', 'high'
    
    # Feature vector as JSON (for complex ML models)
    feature_vector_json = Column(JSONB)
    
    # Metadata
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    
    __table_args__ = (
        UniqueConstraint('pool_id', 'timestamp', 'feature_set_version',
                        name='uq_feature_vectors_pool_timestamp_version'),
        Index('idx_feature_vectors_pool_timestamp', 'pool_id', 'timestamp'),
        Index('idx_feature_vectors_version', 'feature_set_version'),
        Index('idx_feature_vectors_timestamp', 'timestamp'),
    )


class QLibDataExport(Base):
    """
    QLib-formatted data export tracking table.
    
    Tracks exports of data to QLib format for model training and backtesting.
    """
    
    __tablename__ = 'qlib_data_exports'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    export_name = Column(String(100), nullable=False)
    export_type = Column(String(50), nullable=False)  # 'training', 'backtesting', 'live'
    
    # Time range
    start_timestamp = Column(BigInteger, nullable=False)
    end_timestamp = Column(BigInteger, nullable=False)
    
    # Data selection criteria
    networks = Column(JSONB)  # List of networks included
    min_liquidity_usd = Column(Numeric(20, 2))
    min_volume_usd = Column(Numeric(20, 2))
    pool_count = Column(Integer)
    
    # Export metadata
    file_path = Column(String(500))
    file_size_bytes = Column(BigInteger)
    record_count = Column(BigInteger)
    
    # QLib configuration
    qlib_config_json = Column(JSONB)
    feature_columns = Column(JSONB)  # List of feature columns included
    
    # Status tracking
    status = Column(String(20), default='pending')  # 'pending', 'processing', 'completed', 'failed'
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True))
    
    __table_args__ = (
        Index('idx_qlib_exports_name', 'export_name'),
        Index('idx_qlib_exports_type_status', 'export_type', 'status'),
        Index('idx_qlib_exports_timestamp_range', 'start_timestamp', 'end_timestamp'),
    )