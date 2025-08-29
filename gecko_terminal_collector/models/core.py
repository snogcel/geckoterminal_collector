"""
Core data models for the GeckoTerminal collector system.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class Pool:
    """Represents a trading pool on a DEX."""
    id: str
    address: str
    name: str
    dex_id: str
    base_token_id: str
    quote_token_id: str
    reserve_usd: Decimal
    created_at: datetime


@dataclass
class Token:
    """Represents a cryptocurrency token."""
    id: str
    address: str
    name: str
    symbol: str
    decimals: int
    network: str
    price_usd: Optional[Decimal] = None


@dataclass
class OHLCVRecord:
    """Represents OHLCV (Open, High, Low, Close, Volume) data for a pool."""
    pool_id: str
    timeframe: str
    timestamp: int
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume_usd: Decimal
    datetime: datetime


@dataclass
class TradeRecord:
    """Represents a trade transaction."""
    id: str
    pool_id: str
    block_number: int
    tx_hash: str
    from_token_amount: Decimal
    to_token_amount: Decimal
    price_usd: Decimal
    volume_usd: Decimal
    side: str
    block_timestamp: datetime


@dataclass
class CollectionResult:
    """Result of a data collection operation."""
    success: bool
    records_collected: int
    errors: list[str]
    collection_time: datetime
    collector_type: str


@dataclass
class ValidationResult:
    """Result of data validation."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]


@dataclass
class Gap:
    """Represents a gap in time series data."""
    start_time: datetime
    end_time: datetime
    pool_id: str
    timeframe: str


@dataclass
class ContinuityReport:
    """Report on data continuity for a pool/timeframe combination."""
    pool_id: str
    timeframe: str
    total_gaps: int
    gaps: list[Gap]
    data_quality_score: float