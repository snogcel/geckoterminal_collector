"""
Integration tests for NewPoolsCollector end-to-end workflow.
"""

import pytest
import tempfile
import os
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock

from gecko_terminal_collector.collectors.new_pools_collector import NewPoolsCollector
from gecko_terminal_collector.config.models import CollectionConfig, APIConfig, ErrorConfig, DatabaseConfig
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import Pool as PoolModel, NewPoolsHistory


@pytest.fixture
def temp_db_config():
    """Create temporary database configuration."""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    config = DatabaseConfig(
        url=f"sqlite:///{temp_db.name}",
        pool_size=1,
        max_overflow=0,
        echo=False
    )
    
    yield config
    
    # Cleanup
    try:
        os.unlink(temp_db.name)
    except OSError:
        pass


@pytest.fixture
def collection_config():
    """Create collection configuration."""
    return CollectionConfig(
        api=APIConfig(
            base_url="https://api.geckoterminal.com/api/v2",
            timeout=30,
            rate_limit_delay=0.1  # Faster for testing
        ),
        error_handling=ErrorConfig(
            max_retries=2,
            backoff_factor=1.5,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=60
        )
    )


@pytest.fixture
def db_manager(temp_db_config):
    """Create and initialize database manager."""
    manager = SQLAlchemyDatabaseManager(temp_db_config)
    # Initialize synchronously for testing
    manager.connection.initialize()
    manager.connection.create_tables()
    yield manager
    manager.connection.close()


@pytest.fixture
def mock_new_pools_data():
    """Create mock new pools data for testing."""
    return {
        "data": [
            {
                "id": "integration_pool_1",
                "type": "pool",
                "attributes": {
                    "name": "Integration Test Pool 1",
                    "address": "0x1111111111111111111111111111111111111111",
                    "dex_id": "heaven",
                    "base_token_id": "base_token_integration_1",
                    "quote_token_id": "quote_token_integration_1",
                    "reserve_in_usd": "15000.75",
                    "pool_created_at": "2024-01-15T10:30:00Z",
                    "base_token_price_usd": "2.50",
                    "base_token_price_native_currency": "2.45",
                    "quote_token_price_usd": "1.00",
                    "quote_token_price_native_currency": "0.98",
                    "fdv_usd": "75000.00",
                    "market_cap_usd": "60000.00",
                    "price_change_percentage_h1": "5.2",
                    "price_change_percentage_h24": "-2.8",
                    "transactions_h1_buys": 25,
                    "transactions_h1_sells": 18,
                    "transactions_h24_buys": 300,
                    "transactions_h24_sells": 250,
                    "volume_usd_h24": "8500.25",
                    "network_id": "solana"
                }
            },
            {
                "id": "integration_pool_2",
                "type": "pool",
                "attributes": {
                    "name": "Integration Test Pool 2",
                    "address": "0x2222222222222222222222222222222222222222",
                    "dex_id": "pumpswap",
                    "base_token_id": "base_token_integration_2",
                    "quote_token_id": "quote_token_integration_2",
                    "reserve_in_usd": "32000.50",
                    "pool_created_at": "2024-01-16T14:45:00Z",
                    "base_token_price_usd": "0.85",
                    "fdv_usd": "125000.00",
                    "market_cap_usd": "100000.00",
                    "price_change_percentage_h24": "12.5",
                    "transactions_h24_buys": 450,
                    "transactions_h24_sells": 380,
                    "volume_usd_h24": "12750.80",
                    "network_id": "solana"
                }
            }
        ]
    }


class TestNewPoolsIntegration:
    """Integration test cases for NewPoolsCollector."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_collection_workflow(
        self, 
        collection_config, 
        db_manager, 
        mock_new_pools_data
    ):
        """Test complete end-to-end collection workflow."""
        # Create collector with mock client
        collector = NewPoolsCollector(
            config=collection_config,
            db_manager=db_manager,
            network="solana",
            use_mock=True
        )
        
        # Mock the API response
        mock_client = AsyncMock()
        mock_client.get_new_pools_by_network.return_value = mock_new_pools_data
        collector._client = mock_client
        
        # Mock rate limiter to avoid delays
        collector.rate_limiter.acquire = AsyncMock()
        
        # Execute collection
        result = await collector.collect()
        
        # Verify collection result
        assert result.success is True
        assert result.records_collected == 4  # 2 pools + 2 history records
        assert result.collector_type == "new_pools_solana"
        assert result.metadata["network"] == "solana"
        assert result.metadata["pools_created"] == 2
        assert result.metadata["history_records"] == 2
        
        # Verify pools were stored in database
        pool1 = await db_manager.get_pool_by_id("integration_pool_1")

        print("-_test_end_to_end_collection_workflow--")
        print(pool1)
        print("---")

        assert pool1 is not None
        assert pool1.name == "Integration Test Pool 1"
        assert pool1.address == "0x1111111111111111111111111111111111111111"
        assert pool1.dex_id == "heaven"
        assert pool1.reserve_usd == Decimal("15000.75")
        
        pool2 = await db_manager.get_pool_by_id("integration_pool_2")
        assert pool2 is not None
        assert pool2.name == "Integration Test Pool 2"
        assert pool2.dex_id == "pumpswap"
        
        # Verify history records were stored
        with db_manager.connection.get_session() as session:
            history_count = session.query(NewPoolsHistory).count()
            assert history_count == 2
            
            # Check specific history record
            history1 = session.query(NewPoolsHistory).filter_by(
                pool_id="integration_pool_1"
            ).first()
            assert history1 is not None
            assert history1.name == "Integration Test Pool 1"
            assert history1.base_token_price_usd == Decimal("2.50")
            assert history1.fdv_usd == Decimal("75000.00")
            assert history1.price_change_percentage_h1 == Decimal("5.2")
            assert history1.transactions_h1_buys == 25
            assert history1.volume_usd_h24 == Decimal("8500.25")
            assert history1.network_id == "solana"
    
    @pytest.mark.asyncio
    async def test_duplicate_pool_handling(
        self, 
        collection_config, 
        db_manager, 
        mock_new_pools_data
    ):
        """Test handling of duplicate pools (should not create duplicate pools but should create history records)."""
        # Create collector
        collector = NewPoolsCollector(
            config=collection_config,
            db_manager=db_manager,
            network="solana",
            use_mock=True
        )
        
        # Mock the API response
        mock_client = AsyncMock()
        mock_client.get_new_pools_by_network.return_value = mock_new_pools_data
        collector._client = mock_client
        
        # Mock rate limiter
        collector.rate_limiter.acquire = AsyncMock()
        
        # First collection run
        result1 = await collector.collect()
        assert result1.success is True
        assert result1.metadata["pools_created"] == 2
        
        # Second collection run (same data)
        # Note: Due to unique constraint on (pool_id, collected_at), 
        # duplicate history records within the same timestamp will fail
        result2 = await collector.collect()
        assert result2.success is True
        assert result2.metadata["pools_created"] == 0  # No new pools created
        # History records may be fewer due to unique constraint on timestamp
        assert result2.metadata["history_records"] <= 2
        
        # Verify only 2 pools exist (no duplicates)
        pool_count = await db_manager.count_records("pools")
        assert pool_count == 2
        
        # Verify history records exist (may be fewer than 4 due to unique constraint)
        history_count = await db_manager.count_records("new_pools_history")
        assert history_count >= 2  # At least the first run's records should exist
    
    @pytest.mark.asyncio
    async def test_partial_failure_handling(
        self, 
        collection_config, 
        db_manager
    ):
        """Test handling of partial failures during collection."""
        # Create data with one valid and one invalid pool
        mixed_data = {
            "data": [
                {
                    "id": "valid_pool",
                    "type": "pool",
                    "attributes": {
                        "name": "Valid Pool",
                        "address": "0x1111111111111111111111111111111111111111",
                        "dex_id": "heaven",
                        "reserve_in_usd": "10000.00",
                        "pool_created_at": "2024-01-01T00:00:00Z",
                        "network_id": "solana"
                    }
                },
                {
                    # Missing required 'id' field
                    "type": "pool",
                    "attributes": {
                        "name": "Invalid Pool",
                        "address": "0x2222222222222222222222222222222222222222"
                    }
                }
            ]
        }
        
        # Create collector
        collector = NewPoolsCollector(
            config=collection_config,
            db_manager=db_manager,
            network="solana",
            use_mock=True
        )
        
        # Mock the API response
        mock_client = AsyncMock()
        mock_client.get_new_pools_by_network.return_value = mixed_data
        collector._client = mock_client
        
        # Mock rate limiter
        collector.rate_limiter.acquire = AsyncMock()
        
        # Execute collection
        result = await collector.collect()
        
        # Should succeed overall but with some errors for invalid records
        assert result.success is True
        assert len(result.errors) > 0  # Should have errors for invalid pool
        
        # Valid pool should be stored despite invalid records
        valid_pool = await db_manager.get_pool_by_id("valid_pool")
        assert valid_pool is not None
        assert valid_pool.name == "Valid Pool"
        
        # Should have 1 pool and 1 history record (only for valid pool)
        pool_count = await db_manager.count_records("pools")
        assert pool_count == 1
        
        history_count = await db_manager.count_records("new_pools_history")
        assert history_count == 1
    
    @pytest.mark.asyncio
    async def test_database_constraint_handling(
        self, 
        collection_config, 
        db_manager
    ):
        """Test handling of database constraints and foreign key relationships."""
        # Create pool data with DEX that doesn't exist yet
        pool_data = {
            "data": [
                {
                    "id": "constraint_test_pool",
                    "type": "pool",
                    "attributes": {
                        "name": "Constraint Test Pool",
                        "address": "0x3333333333333333333333333333333333333333",
                        "dex_id": "new_dex_not_in_db",
                        "base_token_id": "base_token_constraint",
                        "quote_token_id": "quote_token_constraint",
                        "reserve_in_usd": "5000.00",
                        "pool_created_at": "2024-01-01T00:00:00Z",
                        "network_id": "solana"
                    }
                }
            ]
        }
        
        # Create collector
        collector = NewPoolsCollector(
            config=collection_config,
            db_manager=db_manager,
            network="solana",
            use_mock=True
        )
        
        # Mock the API response
        mock_client = AsyncMock()
        mock_client.get_new_pools_by_network.return_value = pool_data
        collector._client = mock_client
        
        # Mock rate limiter
        collector.rate_limiter.acquire = AsyncMock()
        
        # Execute collection
        result = await collector.collect()
        
        # Should succeed (the store_pools method should handle DEX creation)
        assert result.success is True
        
        # Pool should be stored
        pool = await db_manager.get_pool_by_id("constraint_test_pool")
        assert pool is not None
        assert pool.dex_id == "new_dex_not_in_db"
        
        # History record should also be stored
        history_count = await db_manager.count_records("new_pools_history")
        assert history_count == 1
    
    @pytest.mark.asyncio
    async def test_data_type_conversion_edge_cases(
        self, 
        collection_config, 
        db_manager
    ):
        """Test handling of various data type conversion edge cases."""
        # Create data with edge case values
        edge_case_data = {
            "data": [
                {
                    "id": "edge_case_pool",
                    "type": "pool",
                    "attributes": {
                        "name": "Edge Case Pool",
                        "address": "0x4444444444444444444444444444444444444444",
                        "dex_id": "heaven",
                        "reserve_in_usd": "0",  # Zero value
                        "pool_created_at": "2024-01-01T00:00:00Z",
                        "base_token_price_usd": None,  # Null value
                        "fdv_usd": "",  # Empty string
                        "price_change_percentage_h1": "invalid_number",  # Invalid number
                        "transactions_h1_buys": "25.5",  # Float as string for int field
                        "volume_usd_h24": "1234567890.123456789",  # High precision decimal
                        "network_id": "solana"
                    }
                }
            ]
        }
        
        # Create collector
        collector = NewPoolsCollector(
            config=collection_config,
            db_manager=db_manager,
            network="solana",
            use_mock=True
        )
        
        # Mock the API response
        mock_client = AsyncMock()
        mock_client.get_new_pools_by_network.return_value = edge_case_data
        collector._client = mock_client
        
        # Mock rate limiter
        collector.rate_limiter.acquire = AsyncMock()
        
        # Execute collection
        result = await collector.collect()
        
        # Should succeed despite edge cases
        assert result.success is True
        
        # Pool should be stored with converted values
        pool = await db_manager.get_pool_by_id("edge_case_pool")
        assert pool is not None
        assert pool.reserve_usd == Decimal("0")
        
        # History record should handle edge cases gracefully
        with db_manager.connection.get_session() as session:
            history = session.query(NewPoolsHistory).filter_by(
                pool_id="edge_case_pool"
            ).first()
            assert history is not None
            assert history.base_token_price_usd is None  # Null handled
            assert history.fdv_usd is None  # Empty string handled
            assert history.price_change_percentage_h1 is None  # Invalid number handled
            assert history.transactions_h1_buys == 25  # Float converted to int
            # Note: Database precision may be limited, so check if value is close
            assert abs(history.volume_usd_h24 - Decimal("1234567890.123456789")) < Decimal("0.01")


if __name__ == "__main__":
    pytest.main([__file__])