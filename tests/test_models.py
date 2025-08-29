"""
Tests for core data models.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from gecko_terminal_collector.models.core import (
    Pool, Token, OHLCVRecord, TradeRecord, CollectionResult,
    ValidationResult, Gap, ContinuityReport
)


def test_pool_creation():
    """Test Pool model creation."""
    pool = Pool(
        id="test_pool_1",
        address="solana_address_123",
        name="Test Pool",
        dex_id="heaven",
        base_token_id="token_1",
        quote_token_id="token_2",
        reserve_usd=Decimal("1000.50"),
        created_at=datetime.utcnow()
    )
    
    assert pool.id == "test_pool_1"
    assert pool.dex_id == "heaven"
    assert pool.reserve_usd == Decimal("1000.50")


def test_token_creation():
    """Test Token model creation."""
    token = Token(
        id="token_1",
        address="token_address_123",
        name="Test Token",
        symbol="TEST",
        decimals=9,
        network="solana",
        price_usd=Decimal("1.50")
    )
    
    assert token.symbol == "TEST"
    assert token.decimals == 9
    assert token.price_usd == Decimal("1.50")


def test_ohlcv_record_creation():
    """Test OHLCVRecord model creation."""
    now = datetime.utcnow()
    ohlcv = OHLCVRecord(
        pool_id="test_pool_1",
        timeframe="1h",
        timestamp=int(now.timestamp()),
        open_price=Decimal("1.00"),
        high_price=Decimal("1.10"),
        low_price=Decimal("0.95"),
        close_price=Decimal("1.05"),
        volume_usd=Decimal("10000.00"),
        datetime=now
    )
    
    assert ohlcv.timeframe == "1h"
    assert ohlcv.high_price >= ohlcv.low_price
    assert ohlcv.volume_usd > 0


def test_trade_record_creation():
    """Test TradeRecord model creation."""
    trade = TradeRecord(
        id="trade_123",
        pool_id="test_pool_1",
        block_number=12345,
        tx_hash="tx_hash_123",
        from_token_amount=Decimal("100.0"),
        to_token_amount=Decimal("105.0"),
        price_usd=Decimal("1.05"),
        volume_usd=Decimal("105.0"),
        side="buy",
        block_timestamp=datetime.utcnow()
    )
    
    assert trade.side == "buy"
    assert trade.volume_usd > 0


def test_collection_result():
    """Test CollectionResult model."""
    result = CollectionResult(
        success=True,
        records_collected=100,
        errors=[],
        collection_time=datetime.utcnow(),
        collector_type="test_collector"
    )
    
    assert result.success is True
    assert result.records_collected == 100
    assert len(result.errors) == 0


def test_validation_result():
    """Test ValidationResult model."""
    result = ValidationResult(
        is_valid=False,
        errors=["Invalid price"],
        warnings=["Low volume"]
    )
    
    assert result.is_valid is False
    assert "Invalid price" in result.errors
    assert "Low volume" in result.warnings


def test_gap_model():
    """Test Gap model."""
    start = datetime(2024, 1, 1, 10, 0)
    end = datetime(2024, 1, 1, 12, 0)
    
    gap = Gap(
        start_time=start,
        end_time=end,
        pool_id="test_pool_1",
        timeframe="1h"
    )
    
    assert gap.start_time < gap.end_time
    assert gap.timeframe == "1h"


def test_continuity_report():
    """Test ContinuityReport model."""
    gaps = [
        Gap(
            start_time=datetime(2024, 1, 1, 10, 0),
            end_time=datetime(2024, 1, 1, 11, 0),
            pool_id="test_pool_1",
            timeframe="1h"
        )
    ]
    
    report = ContinuityReport(
        pool_id="test_pool_1",
        timeframe="1h",
        total_gaps=1,
        gaps=gaps,
        data_quality_score=0.95
    )
    
    assert report.total_gaps == 1
    assert len(report.gaps) == 1
    assert 0.0 <= report.data_quality_score <= 1.0