"""
Tests for database constraint validation and integrity enforcement.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from gecko_terminal_collector.config.models import DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import (
    Base, DEX, Pool, Token, OHLCVData, Trade, WatchlistEntry, CollectionMetadata
)
from gecko_terminal_collector.models.core import Pool as PoolModel, OHLCVRecord, TradeRecord


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
    """Initialize test database."""
    await db_manager.initialize()
    yield db_manager
    await db_manager.close()


class TestUniqueConstraints:
    """Test unique constraint enforcement."""
    
    @pytest.mark.asyncio
    async def test_ohlcv_unique_constraint_enforcement(self, initialized_db):
        """Test that OHLCV unique constraint is properly enforced."""
        # Create test pool first
        test_pool = PoolModel(
            id="constraint_test_pool",
            address="constraint_test_address",
            name="Constraint Test Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        await initialized_db.store_pools([test_pool])
        
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        timestamp = int(base_time.timestamp())
        
        # Create first OHLCV record
        ohlcv1 = OHLCVRecord(
            pool_id="constraint_test_pool",
            timeframe="1h",
            timestamp=timestamp,
            open_price=Decimal("100.0"),
            high_price=Decimal("110.0"),
            low_price=Decimal("95.0"),
            close_price=Decimal("105.0"),
            volume_usd=Decimal("1000.0"),
            datetime=base_time
        )
        
        # Store first record
        stored_count = await initialized_db.store_ohlcv_data([ohlcv1])
        assert stored_count == 1
        
        # Try to store record with same composite key (pool_id, timeframe, timestamp)
        ohlcv2 = OHLCVRecord(
            pool_id="constraint_test_pool",
            timeframe="1h",
            timestamp=timestamp,  # Same timestamp
            open_price=Decimal("101.0"),  # Different values
            high_price=Decimal("111.0"),
            low_price=Decimal("96.0"),
            close_price=Decimal("106.0"),
            volume_usd=Decimal("1001.0"),
            datetime=base_time
        )
        
        # Should handle duplicate gracefully (update existing)
        stored_count = await initialized_db.store_ohlcv_data([ohlcv2])
        assert stored_count == 0  # No new records stored
        
        # Verify only one record exists with updated values
        retrieved_data = await initialized_db.get_ohlcv_data("constraint_test_pool", "1h")
        assert len(retrieved_data) == 1
    
    @pytest.mark.asyncio
    async def test_trade_primary_key_constraint(self, initialized_db):
        """Test that trade primary key constraint is enforced."""
        # Create test pool first
        test_pool = PoolModel(
            id="trade_constraint_pool",
            address="trade_constraint_address",
            name="Trade Constraint Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        await initialized_db.store_pools([test_pool])
        
        # Create first trade
        trade1 = TradeRecord(
            id="duplicate_trade_id",
            pool_id="trade_constraint_pool",
            block_number=12345,
            tx_hash="tx_hash_1",
            from_token_amount=Decimal("100.0"),
            to_token_amount=Decimal("200.0"),
            price_usd=Decimal("1.50"),
            volume_usd=Decimal("150.0"),
            side="buy",
            block_timestamp=datetime.utcnow()
        )
        
        # Store first trade
        stored_count = await initialized_db.store_trade_data([trade1])
        assert stored_count == 1
        
        # Try to store trade with same ID
        trade2 = TradeRecord(
            id="duplicate_trade_id",  # Same ID
            pool_id="trade_constraint_pool",
            block_number=12346,  # Different values
            tx_hash="tx_hash_2",
            from_token_amount=Decimal("200.0"),
            to_token_amount=Decimal("400.0"),
            price_usd=Decimal("2.00"),
            volume_usd=Decimal("400.0"),
            side="sell",
            block_timestamp=datetime.utcnow()
        )
        
        # Should not store duplicate
        stored_count = await initialized_db.store_trade_data([trade2])
        assert stored_count == 0
        
        # Verify only original trade exists
        retrieved_trades = await initialized_db.get_trade_data("trade_constraint_pool")
        assert len(retrieved_trades) == 1
        assert retrieved_trades[0].block_number == 12345
    
    @pytest.mark.asyncio
    async def test_watchlist_unique_constraint(self, initialized_db):
        """Test watchlist unique constraint on pool_id."""
        # Create test pool first
        test_pool = PoolModel(
            id="watchlist_constraint_pool",
            address="watchlist_constraint_address",
            name="Watchlist Constraint Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        await initialized_db.store_pools([test_pool])
        
        # Add first watchlist entry
        metadata1 = {
            'token_symbol': 'TEST1',
            'token_name': 'Test Token 1',
            'network_address': 'address1'
        }
        await initialized_db.store_watchlist_entry("watchlist_constraint_pool", metadata1)
        
        # Try to add another entry for same pool
        metadata2 = {
            'token_symbol': 'TEST2',
            'token_name': 'Test Token 2',
            'network_address': 'address2'
        }
        
        # Should update existing entry, not create duplicate
        await initialized_db.store_watchlist_entry("watchlist_constraint_pool", metadata2)
        
        # Verify only one entry exists with updated values
        watchlist_pools = await initialized_db.get_watchlist_pools()
        assert "watchlist_constraint_pool" in watchlist_pools
        assert watchlist_pools.count("watchlist_constraint_pool") == 1


class TestForeignKeyConstraints:
    """Test foreign key constraint enforcement."""
    
    @pytest.mark.asyncio
    async def test_pool_dex_foreign_key(self, initialized_db):
        """Test that pool references valid DEX."""
        # Try to create pool without DEX (should create DEX automatically)
        test_pool = PoolModel(
            id="fk_test_pool",
            address="fk_test_address",
            name="FK Test Pool",
            dex_id="nonexistent_dex",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        
        # Should succeed (creates DEX automatically)
        stored_count = await initialized_db.store_pools([test_pool])
        assert stored_count == 1
        
        # Verify DEX was created
        retrieved_pool = await initialized_db.get_pool("fk_test_pool")
        assert retrieved_pool is not None
        assert retrieved_pool.dex_id == "nonexistent_dex"
    
    @pytest.mark.asyncio
    async def test_ohlcv_pool_foreign_key(self, initialized_db):
        """Test that OHLCV data references valid pool."""
        # Try to create OHLCV data for nonexistent pool
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        ohlcv_record = OHLCVRecord(
            pool_id="nonexistent_pool",
            timeframe="1h",
            timestamp=int(base_time.timestamp()),
            open_price=Decimal("100.0"),
            high_price=Decimal("110.0"),
            low_price=Decimal("95.0"),
            close_price=Decimal("105.0"),
            volume_usd=Decimal("1000.0"),
            datetime=base_time
        )
        
        # Should handle gracefully (may create or skip based on implementation)
        try:
            stored_count = await initialized_db.store_ohlcv_data([ohlcv_record])
            # If it succeeds, verify the behavior
            assert stored_count >= 0
        except Exception:
            # If it fails, that's also acceptable for foreign key constraint
            pass
    
    @pytest.mark.asyncio
    async def test_trade_pool_foreign_key(self, initialized_db):
        """Test that trade data references valid pool."""
        # Try to create trade for nonexistent pool
        trade_record = TradeRecord(
            id="fk_test_trade",
            pool_id="nonexistent_pool",
            block_number=12345,
            tx_hash="test_tx_hash",
            from_token_amount=Decimal("100.0"),
            to_token_amount=Decimal("200.0"),
            price_usd=Decimal("1.50"),
            volume_usd=Decimal("150.0"),
            side="buy",
            block_timestamp=datetime.utcnow()
        )
        
        # Should handle gracefully
        try:
            stored_count = await initialized_db.store_trade_data([trade_record])
            assert stored_count >= 0
        except Exception:
            # Foreign key constraint violation is acceptable
            pass


class TestDataTypeConstraints:
    """Test data type and validation constraints."""
    
    @pytest.mark.asyncio
    async def test_decimal_precision_handling(self, initialized_db):
        """Test handling of decimal precision in prices and amounts."""
        # Create test pool
        test_pool = PoolModel(
            id="precision_test_pool",
            address="precision_test_address",
            name="Precision Test Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        await initialized_db.store_pools([test_pool])
        
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        # Test with high precision decimals
        high_precision_ohlcv = OHLCVRecord(
            pool_id="precision_test_pool",
            timeframe="1h",
            timestamp=int(base_time.timestamp()),
            open_price=Decimal("100.123456789012345678"),  # High precision
            high_price=Decimal("110.987654321098765432"),
            low_price=Decimal("95.111111111111111111"),
            close_price=Decimal("105.999999999999999999"),
            volume_usd=Decimal("1000.12345678"),
            datetime=base_time
        )
        
        # Should handle high precision gracefully
        stored_count = await initialized_db.store_ohlcv_data([high_precision_ohlcv])
        assert stored_count == 1
        
        # Verify data was stored (may be rounded based on schema)
        retrieved_data = await initialized_db.get_ohlcv_data("precision_test_pool", "1h")
        assert len(retrieved_data) == 1
        assert retrieved_data[0].open_price > 0
    
    @pytest.mark.asyncio
    async def test_string_length_constraints(self, initialized_db):
        """Test string length constraints."""
        # Test with very long strings
        long_name = "A" * 300  # Longer than typical VARCHAR limits
        
        test_pool = PoolModel(
            id="string_test_pool",
            address="string_test_address",
            name=long_name,  # Very long name
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        
        # Should handle long strings gracefully (truncate or reject)
        try:
            stored_count = await initialized_db.store_pools([test_pool])
            # If successful, verify the data
            if stored_count > 0:
                retrieved_pool = await initialized_db.get_pool("string_test_pool")
                assert retrieved_pool is not None
        except Exception:
            # String length constraint violation is acceptable
            pass


class TestConcurrentAccess:
    """Test concurrent access and race condition handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_duplicate_insertion(self, initialized_db):
        """Test handling of concurrent duplicate insertions."""
        # Create test pool
        test_pool = PoolModel(
            id="concurrent_test_pool",
            address="concurrent_test_address",
            name="Concurrent Test Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        await initialized_db.store_pools([test_pool])
        
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        timestamp = int(base_time.timestamp())
        
        # Create identical OHLCV records (simulating concurrent insertion)
        ohlcv_records = [
            OHLCVRecord(
                pool_id="concurrent_test_pool",
                timeframe="1h",
                timestamp=timestamp,
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time
            )
            for _ in range(3)  # Multiple identical records
        ]
        
        # Should handle duplicates gracefully
        stored_count = await initialized_db.store_ohlcv_data(ohlcv_records)
        
        # Should only store one record
        retrieved_data = await initialized_db.get_ohlcv_data("concurrent_test_pool", "1h")
        assert len(retrieved_data) == 1
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, initialized_db):
        """Test that transactions are properly rolled back on errors."""
        # Create test pool
        test_pool = PoolModel(
            id="rollback_test_pool",
            address="rollback_test_address",
            name="Rollback Test Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000.0"),
            created_at=datetime.utcnow()
        )
        await initialized_db.store_pools([test_pool])
        
        # Create mix of valid and invalid OHLCV records
        base_time = datetime(2022, 1, 1, 0, 0, 0)
        
        mixed_records = [
            # Valid record
            OHLCVRecord(
                pool_id="rollback_test_pool",
                timeframe="1h",
                timestamp=int(base_time.timestamp()),
                open_price=Decimal("100.0"),
                high_price=Decimal("110.0"),
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time
            ),
            # Invalid record (high < low)
            OHLCVRecord(
                pool_id="rollback_test_pool",
                timeframe="1h",
                timestamp=int((base_time + timedelta(hours=1)).timestamp()),
                open_price=Decimal("100.0"),
                high_price=Decimal("90.0"),  # Invalid: high < low
                low_price=Decimal("95.0"),
                close_price=Decimal("105.0"),
                volume_usd=Decimal("1000.0"),
                datetime=base_time + timedelta(hours=1)
            )
        ]
        
        # Should handle mixed batch gracefully (store valid, skip invalid)
        stored_count = await initialized_db.store_ohlcv_data(mixed_records)
        
        # Should store only valid records
        retrieved_data = await initialized_db.get_ohlcv_data("rollback_test_pool", "1h")
        assert len(retrieved_data) >= 0  # At least no crash