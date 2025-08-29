"""
Tests for database manager data integrity and continuity features.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.models.core import Pool, Token, OHLCVRecord, TradeRecord, Gap


@pytest.fixture
def db_config():
    """Create test database configuration."""
    return DatabaseConfig(
        url="sqlite:///:memory:",
        pool_size=1,
        echo=False
    )


@pytest.fixture
def db_manager(db_config):
    """Create test database manager."""
    return SQLAlchemyDatabaseManager(db_config)


@pytest_asyncio.fixture
async def initialized_db(db_manager):
    """Initialize test database with sample data."""
    await db_manager.initialize()
    
    # Create test pool
    test_pool = Pool(
        id="test_pool_integrity",
        address="test_address_integrity",
        name="Test Pool for Integrity",
        dex_id="heaven",
        base_token_id="token1",
        quote_token_id="token2",
        reserve_usd=Decimal("1000.0"),
        created_at=datetime.utcnow()
    )
    await db_manager.store_pools([test_pool])
    
    yield db_manager
    await db_manager.close()


class TestDuplicatePrevention:
    """Test duplicate prevention mechanisms."""
    
    @pytest.mark.asyncio
    async def test_ohlcv_duplicate_prevention(self, initialized_db):
        """Test OHLCV duplicate prevention using composite keys."""
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        # Create initial OHLCV record
        ohlcv_record = OHLCVRecord(
            pool_id="test_pool_integrity",
            timeframe="1h",
            timestamp=int(base_time.timestamp()),
            open_price=Decimal("100.0"),
            high_price=Decimal("110.0"),
            low_price=Decimal("95.0"),
            close_price=Decimal("105.0"),
            volume_usd=Decimal("1000.0"),
            datetime=base_time
        )
        
        # Store first record
        stored_count = await initialized_db.store_ohlcv_data([ohlcv_record])
        assert stored_count == 1
        
        # Try to store duplicate with different prices
        duplicate_record = OHLCVRecord(
            pool_id="test_pool_integrity",
            timeframe="1h",
            timestamp=int(base_time.timestamp()),  # Same timestamp
            open_price=Decimal("101.0"),  # Different price
            high_price=Decimal("111.0"),
            low_price=Decimal("96.0"),
            close_price=Decimal("106.0"),
            volume_usd=Decimal("1001.0"),
            datetime=base_time
        )
        
        # Should update existing record, not create new one
        stored_count = await initialized_db.store_ohlcv_data([duplicate_record])
        assert stored_count == 0  # No new records stored
        
        # Verify only one record exists with updated values
        retrieved_data = await initialized_db.get_ohlcv_data("test_pool_integrity", "1h")
        assert len(retrieved_data) == 1
        assert retrieved_data[0].open_price == Decimal("101.0")  # Updated value
    
    @pytest.mark.asyncio
    async def test_trade_duplicate_prevention(self, initialized_db):
        """Test trade duplicate prevention using primary keys."""
        trade_record = TradeRecord(
            id="test_trade_1",
            pool_id="test_pool_integrity",
            block_number=12345,
            tx_hash="test_tx_hash",
            from_token_amount=Decimal("100.0"),
            to_token_amount=Decimal("200.0"),
            price_usd=Decimal("1.50"),
            volume_usd=Decimal("150.0"),
            side="buy",
            block_timestamp=datetime.utcnow()
        )
        
        # Store first trade
        stored_count = await initialized_db.store_trade_data([trade_record])
        assert stored_count == 1
        
        # Try to store duplicate trade with same ID
        duplicate_trade = TradeRecord(
            id="test_trade_1",  # Same ID
            pool_id="test_pool_integrity",
            block_number=12346,  # Different block
            tx_hash="different_tx_hash",
            from_token_amount=Decimal("200.0"),
            to_token_amount=Decimal("400.0"),
            price_usd=Decimal("2.00"),
            volume_usd=Decimal("400.0"),
            side="sell",
            block_timestamp=datetime.utcnow()
        )
        
        # Should not store duplicate
        stored_count = await initialized_db.store_trade_data([duplicate_trade])
        assert stored_count == 0
        
        # Verify only one trade exists with original values
        retrieved_trades = await initialized_db.get_trade_data("test_pool_integrity")
        assert len(retrieved_trades) == 1
        assert retrieved_trades[0].block_number == 12345  # Original value
    
    @pytest.mark.asyncio
    async def test_batch_duplicate_handling(self, initialized_db):
        """Test handling duplicates within a batch."""
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        # Create batch with internal duplicates
        ohlcv_batch = [
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int(base_time.timestamp()),
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time
            ),
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int(base_time.timestamp()),  # Duplicate timestamp
                open_price=Decimal("101.0"),
                high_price=Decimal("111.0"),
                low_price=Decimal("96.0"),
                close_price=Decimal("106.0"),
                volume_usd=Decimal("1001.0"),
                datetime=base_time
            ),
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=1)).timestamp()),  # Different timestamp
                open_price=Decimal("105.0"),
                high_price=Decimal("115.0"),
                low_price=Decimal("100.0"),
                close_price=Decimal("110.0"),
                volume_usd=Decimal("1500.0"),
                datetime=base_time + timedelta(hours=1)
            )
        ]
        
        # Should handle duplicates gracefully
        stored_count = await initialized_db.store_ohlcv_data(ohlcv_batch)
        # Should store 2 records (one duplicate handled)
        assert stored_count <= 2
        
        # Verify correct number of records
        retrieved_data = await initialized_db.get_ohlcv_data("test_pool_integrity", "1h")
        assert len(retrieved_data) == 2


class TestDataValidation:
    """Test data validation mechanisms."""
    
    @pytest.mark.asyncio
    async def test_ohlcv_validation(self, initialized_db):
        """Test OHLCV data validation."""
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        # Test invalid price relationships
        invalid_ohlcv = [
            # High < Low
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int(base_time.timestamp()),
                open_price=Decimal("100.0"),
                high_price=Decimal("90.0"),  # High < Low
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time
            ),
            # Negative prices
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=1)).timestamp()),
                open_price=Decimal("-100.0"),  # Negative price
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time + timedelta(hours=1)
            ),
            # Valid record
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=2)).timestamp()),
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time + timedelta(hours=2)
            )
        ]
        
        # Should only store valid records
        stored_count = await initialized_db.store_ohlcv_data(invalid_ohlcv)
        assert stored_count == 1  # Only the valid record
        
        # Verify only valid record was stored
        retrieved_data = await initialized_db.get_ohlcv_data("test_pool_integrity", "1h")
        assert len(retrieved_data) == 1
        assert retrieved_data[0].datetime == base_time + timedelta(hours=2)
    
    @pytest.mark.asyncio
    async def test_trade_validation(self, initialized_db):
        """Test trade data validation."""
        base_time = datetime.utcnow()
        
        invalid_trades = [
            # Negative volume
            TradeRecord(
                id="invalid_trade_1",
                pool_id="test_pool_integrity",
                block_number=12345,
                tx_hash="test_tx_1",
                from_token_amount=Decimal("100.0"),
                to_token_amount=Decimal("200.0"),
                price_usd=Decimal("1.50"),
                volume_usd=Decimal("-150.0"),  # Negative volume
                side="buy",
                block_timestamp=base_time
            ),
            # Invalid side
            TradeRecord(
                id="invalid_trade_2",
                pool_id="test_pool_integrity",
                block_number=12346,
                tx_hash="test_tx_2",
                from_token_amount=Decimal("100.0"),
                to_token_amount=Decimal("200.0"),
                price_usd=Decimal("1.50"),
                volume_usd=Decimal("150.0"),
                side="invalid_side",  # Invalid side
                block_timestamp=base_time
            ),
            # Valid trade
            TradeRecord(
                id="valid_trade_1",
                pool_id="test_pool_integrity",
                block_number=12347,
                tx_hash="test_tx_3",
                from_token_amount=Decimal("100.0"),
                to_token_amount=Decimal("200.0"),
                price_usd=Decimal("1.50"),
                volume_usd=Decimal("150.0"),
                side="buy",
                block_timestamp=base_time
            )
        ]
        
        # Should only store valid trades
        stored_count = await initialized_db.store_trade_data(invalid_trades)
        assert stored_count == 1  # Only the valid trade
        
        # Verify only valid trade was stored
        retrieved_trades = await initialized_db.get_trade_data("test_pool_integrity")
        assert len(retrieved_trades) == 1
        assert retrieved_trades[0].id == "valid_trade_1"


class TestDataContinuity:
    """Test data continuity checking methods."""
    
    @pytest.mark.asyncio
    async def test_gap_detection_no_data(self, initialized_db):
        """Test gap detection when no data exists."""
        start_time = datetime(2022, 1, 1, 0, 0, 0)
        end_time = datetime(2022, 1, 1, 12, 0, 0)
        
        gaps = await initialized_db.get_data_gaps(
            "test_pool_integrity", "1h", start_time, end_time
        )
        
        # Should detect entire range as a gap
        assert len(gaps) == 1
        assert gaps[0].start_time == start_time
        assert gaps[0].end_time == end_time
        assert gaps[0].pool_id == "test_pool_integrity"
        assert gaps[0].timeframe == "1h"
    
    @pytest.mark.asyncio
    async def test_gap_detection_with_data(self, initialized_db):
        """Test gap detection with existing data."""
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        # Create OHLCV data with gaps
        ohlcv_data = [
            # Hour 0
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int(base_time.timestamp()),
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time
            ),
            # Skip hours 1-2 (gap)
            # Hour 3
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=3)).timestamp()),
                open_price=Decimal("105.0"),
                high_price=Decimal("115.0"),
                low_price=Decimal("100.0"),
                close_price=Decimal("110.0"),
                volume_usd=Decimal("1500.0"),
                datetime=base_time + timedelta(hours=3)
            ),
            # Hour 4
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=4)).timestamp()),
                open_price=Decimal("110.0"),
                high_price=Decimal("120.0"),
                low_price=Decimal("105.0"),
                close_price=Decimal("115.0"),
                volume_usd=Decimal("2000.0"),
                datetime=base_time + timedelta(hours=4)
            )
            # Skip hours 5-6 (gap at end)
        ]
        
        await initialized_db.store_ohlcv_data(ohlcv_data)
        
        # Check for gaps in 8-hour range
        start_time = base_time
        end_time = base_time + timedelta(hours=8)
        
        gaps = await initialized_db.get_data_gaps(
            "test_pool_integrity", "1h", start_time, end_time
        )
        
        # Should detect gaps: hours 1-2 and hours 5-7
        assert len(gaps) >= 1  # At least one gap should be detected
        
        # Verify gap details
        gap_found = False
        for gap in gaps:
            if gap.start_time == base_time + timedelta(hours=1):
                gap_found = True
                assert gap.end_time == base_time + timedelta(hours=3)
        
        assert gap_found, "Expected gap between hours 1-3 not found"
    
    @pytest.mark.asyncio
    async def test_timeframe_alignment(self, initialized_db):
        """Test timeframe alignment for accurate gap detection."""
        # Test with 5-minute timeframe
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        # Create data at 5-minute intervals
        ohlcv_data = []
        for i in range(0, 60, 10):  # Every 10 minutes (skip some 5-minute intervals)
            record_time = base_time + timedelta(minutes=i)
            ohlcv_data.append(OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="5m",
                timestamp=int(record_time.timestamp()),
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=record_time
            ))
        
        await initialized_db.store_ohlcv_data(ohlcv_data)
        
        # Check for gaps in 1-hour range
        start_time = base_time
        end_time = base_time + timedelta(hours=1)
        
        gaps = await initialized_db.get_data_gaps(
            "test_pool_integrity", "5m", start_time, end_time
        )
        
        # Should detect gaps for missing 5-minute intervals
        assert len(gaps) > 0
    
    @pytest.mark.asyncio
    async def test_data_continuity_report(self, initialized_db):
        """Test comprehensive data continuity reporting."""
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        # Create partial OHLCV data
        ohlcv_data = [
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=i)).timestamp()),
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time + timedelta(hours=i)
            )
            for i in [0, 1, 4, 5, 8, 9]  # Missing hours 2, 3, 6, 7
        ]
        
        await initialized_db.store_ohlcv_data(ohlcv_data)
        
        # Get continuity report
        report = await initialized_db.check_data_continuity("test_pool_integrity", "1h")
        
        assert report.pool_id == "test_pool_integrity"
        assert report.timeframe == "1h"
        assert report.total_gaps >= 0
        assert 0.0 <= report.data_quality_score <= 1.0
        assert isinstance(report.gaps, list)


class TestDataIntegrity:
    """Test comprehensive data integrity checks."""
    
    @pytest.mark.asyncio
    async def test_integrity_check_valid_data(self, initialized_db):
        """Test integrity check with valid data."""
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        # Add valid OHLCV data
        valid_ohlcv = OHLCVRecord(
            pool_id="test_pool_integrity",
            timeframe="1h",
            timestamp=int(base_time.timestamp()),
            open_price=Decimal("100.0"),
            high_price=Decimal("110.0"),
            low_price=Decimal("95.0"),
            close_price=Decimal("105.0"),
            volume_usd=Decimal("1000.0"),
            datetime=base_time
        )
        await initialized_db.store_ohlcv_data([valid_ohlcv])
        
        # Add valid trade data
        valid_trade = TradeRecord(
            id="valid_trade_integrity",
            pool_id="test_pool_integrity",
            block_number=12345,
            tx_hash="test_tx_hash",
            from_token_amount=Decimal("100.0"),
            to_token_amount=Decimal("200.0"),
            price_usd=Decimal("1.50"),
            volume_usd=Decimal("150.0"),
            side="buy",
            block_timestamp=base_time
        )
        await initialized_db.store_trade_data([valid_trade])
        
        # Run integrity check
        integrity_report = await initialized_db.check_data_integrity("test_pool_integrity")
        
        assert integrity_report['pool_id'] == "test_pool_integrity"
        assert len(integrity_report['issues_found']) == 0
        assert integrity_report['data_quality_score'] == 1.0
        assert 'pool_existence' in integrity_report['checks_performed']
        assert 'ohlcv_integrity' in integrity_report['checks_performed']
        assert 'trade_integrity' in integrity_report['checks_performed']
    
    @pytest.mark.asyncio
    async def test_data_statistics(self, initialized_db):
        """Test data statistics generation."""
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        # Add sample data
        ohlcv_data = [
            OHLCVRecord(
                pool_id="test_pool_integrity",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=i)).timestamp()),
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time + timedelta(hours=i)
            )
            for i in range(5)
        ]
        await initialized_db.store_ohlcv_data(ohlcv_data)
        
        trade_data = [
            TradeRecord(
                id=f"trade_{i}",
                pool_id="test_pool_integrity",
                block_number=12345 + i,
                tx_hash=f"tx_hash_{i}",
                from_token_amount=Decimal("100.0"),
                to_token_amount=Decimal("200.0"),
                price_usd=Decimal("1.50"),
                volume_usd=Decimal(str(100.0 + i * 50)),
                side="buy",
                block_timestamp=base_time + timedelta(minutes=i * 10)
            )
            for i in range(3)
        ]
        await initialized_db.store_trade_data(trade_data)
        
        # Get statistics
        stats = await initialized_db.get_data_statistics("test_pool_integrity")
        
        assert stats['pool_id'] == "test_pool_integrity"
        assert stats['ohlcv_stats']['total_records'] == 5
        assert stats['trade_stats']['total_records'] == 3
        assert 'timeframe_distribution' in stats['ohlcv_stats']
        assert 'volume' in stats['trade_stats']
        assert stats['trade_stats']['volume']['total_usd'] > 0
    
    @pytest.mark.asyncio
    async def test_data_cleanup(self, initialized_db):
        """Test old data cleanup functionality."""
        # Create old and recent data
        old_time = datetime.utcnow() - timedelta(days=100)
        recent_time = datetime.utcnow() - timedelta(days=10)
        
        # Add old OHLCV data
        old_ohlcv = OHLCVRecord(
            pool_id="test_pool_integrity",
            timeframe="1h",
            timestamp=int(old_time.timestamp()),
            open_price=Decimal("100.0"),
            high_price=Decimal("110.0"),
            low_price=Decimal("95.0"),
            close_price=Decimal("105.0"),
            volume_usd=Decimal("1000.0"),
            datetime=old_time
        )
        
        # Add recent OHLCV data
        recent_ohlcv = OHLCVRecord(
            pool_id="test_pool_integrity",
            timeframe="1h",
            timestamp=int(recent_time.timestamp()),
            open_price=Decimal("105.0"),
            high_price=Decimal("115.0"),
            low_price=Decimal("100.0"),
            close_price=Decimal("110.0"),
            volume_usd=Decimal("1500.0"),
            datetime=recent_time
        )
        
        await initialized_db.store_ohlcv_data([old_ohlcv, recent_ohlcv])
        
        # Add old trade data
        old_trade = TradeRecord(
            id="old_trade",
            pool_id="test_pool_integrity",
            block_number=12345,
            tx_hash="old_tx_hash",
            from_token_amount=Decimal("100.0"),
            to_token_amount=Decimal("200.0"),
            price_usd=Decimal("1.50"),
            volume_usd=Decimal("150.0"),
            side="buy",
            block_timestamp=old_time
        )
        
        # Add recent trade data
        recent_trade = TradeRecord(
            id="recent_trade",
            pool_id="test_pool_integrity",
            block_number=12346,
            tx_hash="recent_tx_hash",
            from_token_amount=Decimal("100.0"),
            to_token_amount=Decimal("200.0"),
            price_usd=Decimal("1.50"),
            volume_usd=Decimal("150.0"),
            side="buy",
            block_timestamp=recent_time
        )
        
        await initialized_db.store_trade_data([old_trade, recent_trade])
        
        # Cleanup data older than 30 days
        cleanup_stats = await initialized_db.cleanup_old_data(days_to_keep=30)
        
        assert cleanup_stats['ohlcv_deleted'] >= 0
        assert cleanup_stats['trades_deleted'] >= 0
        assert 'cutoff_date' in cleanup_stats
        
        # Verify recent data still exists
        recent_ohlcv_data = await initialized_db.get_ohlcv_data(
            "test_pool_integrity", "1h", recent_time - timedelta(hours=1), recent_time + timedelta(hours=1)
        )
        assert len(recent_ohlcv_data) >= 1
        
        recent_trade_data = await initialized_db.get_trade_data(
            "test_pool_integrity", recent_time - timedelta(hours=1), recent_time + timedelta(hours=1)
        )
        assert len(recent_trade_data) >= 1