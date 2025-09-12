"""
Unit tests for NewPoolsCollector.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from gecko_terminal_collector.collectors.new_pools_collector import NewPoolsCollector
from gecko_terminal_collector.config.models import CollectionConfig, APIConfig, ErrorConfig
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return CollectionConfig(
        api=APIConfig(
            base_url="https://api.geckoterminal.com/api/v2",
            timeout=30,
            rate_limit_delay=1.0
        ),
        error_handling=ErrorConfig(
            max_retries=3,
            backoff_factor=2.0,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=300
        )
    )


@pytest.fixture
def mock_db_manager():
    """Create mock database manager."""
    db_manager = AsyncMock()
    db_manager.get_pool_by_id = AsyncMock(return_value=None)
    db_manager.store_pool = AsyncMock()
    db_manager.store_new_pools_history = AsyncMock()
    return db_manager


@pytest.fixture
def mock_api_response():
    """Create mock API response data."""
    return {
        "data": [
            {
                "id": "solana_pool_1",
                "type": "pool",
                "attributes": {
                    "name": "Test Pool 1",
                    "address": "0x1234567890abcdef",
                    "dex_id": "heaven",
                    "base_token_id": "base_token_1",
                    "quote_token_id": "quote_token_1",
                    "reserve_in_usd": "10000.50",
                    "pool_created_at": "2024-01-01T00:00:00Z",
                    "base_token_price_usd": "1.25",
                    "quote_token_price_usd": "1.00",
                    "fdv_usd": "50000.00",
                    "market_cap_usd": "40000.00",
                    "price_change_percentage_h1": "2.5",
                    "price_change_percentage_h24": "-1.2",
                    "transactions_h1_buys": 15,
                    "transactions_h1_sells": 10,
                    "transactions_h24_buys": 150,
                    "transactions_h24_sells": 120,
                    "volume_usd_h24": "5000.75",
                    "network_id": "solana"
                }
            },
            {
                "id": "solana_pool_2",
                "type": "pool",
                "attributes": {
                    "name": "Test Pool 2",
                    "address": "0xabcdef1234567890",
                    "dex_id": "pumpswap",
                    "base_token_id": "base_token_2",
                    "quote_token_id": "quote_token_2",
                    "reserve_in_usd": "25000.75",
                    "pool_created_at": "2024-01-02T12:00:00Z",
                    "network_id": "solana"
                }
            }
        ]
    }


@pytest.fixture
def new_pools_collector(mock_config, mock_db_manager):
    """Create NewPoolsCollector instance."""
    return NewPoolsCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        network="solana",
        use_mock=True
    )


class TestNewPoolsCollector:
    """Test cases for NewPoolsCollector."""
    
    def test_get_collection_key(self, new_pools_collector):
        """Test collection key generation."""
        assert new_pools_collector.get_collection_key() == "new_pools_solana"
    
    def test_extract_pool_info_valid_data(self, new_pools_collector):
        """Test extracting pool info from valid API data."""
        pool_data = {
            "id": "test_pool_1",
            "attributes": {
                "name": "Test Pool",
                "address": "0x123456",
                "dex_id": "heaven",
                "base_token_id": "base_1",
                "quote_token_id": "quote_1",
                "reserve_in_usd": "10000.50",
                "pool_created_at": "2024-01-01T00:00:00Z"
            }
        }
        
        result = new_pools_collector._extract_pool_info(pool_data)
        
        assert result is not None
        assert result["id"] == "test_pool_1"
        assert result["name"] == "Test Pool"
        assert result["address"] == "0x123456"
        assert result["dex_id"] == "heaven"
        assert result["base_token_id"] == "base_1"
        assert result["quote_token_id"] == "quote_1"
        assert result["reserve_usd"] == Decimal("10000.50")
        assert isinstance(result["created_at"], datetime)
    
    def test_extract_pool_info_missing_id(self, new_pools_collector):
        """Test extracting pool info with missing ID."""
        pool_data = {
            "attributes": {
                "name": "Test Pool",
                "address": "0x123456"
            }
        }
        
        result = new_pools_collector._extract_pool_info(pool_data)
        assert result is None
    
    def test_extract_pool_info_invalid_timestamp(self, new_pools_collector):
        """Test extracting pool info with invalid timestamp."""
        pool_data = {
            "id": "test_pool_1",
            "attributes": {
                "name": "Test Pool",
                "address": "0x123456",
                "dex_id": "heaven",
                "pool_created_at": "invalid_timestamp"
            }
        }
        
        result = new_pools_collector._extract_pool_info(pool_data)
        
        assert result is not None
        assert result["created_at"] is None  # Should handle invalid timestamp gracefully
    
    def test_create_history_record_valid_data(self, new_pools_collector):
        """Test creating history record from valid API data."""
        pool_data = {
            "id": "test_pool_1",
            "type": "pool",
            "attributes": {
                "name": "Test Pool",
                "address": "0x123456",
                "dex_id": "heaven",
                "base_token_id": "base_1",
                "quote_token_id": "quote_1",
                "reserve_in_usd": "10000.50",
                "pool_created_at": "2024-01-01T00:00:00Z",
                "base_token_price_usd": "1.25",
                "fdv_usd": "50000.00",
                "price_change_percentage_h1": "2.5",
                "transactions_h1_buys": 15,
                "volume_usd_h24": "5000.75",
                "network_id": "solana"
            }
        }
        
        result = new_pools_collector._create_history_record(pool_data)
        
        assert result is not None
        assert result["pool_id"] == "test_pool_1"
        assert result["type"] == "pool"
        assert result["name"] == "Test Pool"
        assert result["address"] == "0x123456"
        assert result["dex_id"] == "heaven"
        assert result["base_token_price_usd"] == Decimal("1.25")
        assert result["fdv_usd"] == Decimal("50000.00")
        assert result["price_change_percentage_h1"] == Decimal("2.5")
        assert result["transactions_h1_buys"] == 15
        assert result["volume_usd_h24"] == Decimal("5000.75")
        assert result["network_id"] == "solana"
        assert isinstance(result["collected_at"], datetime)
    
    def test_create_history_record_with_nulls(self, new_pools_collector):
        """Test creating history record with null/empty values."""
        pool_data = {
            "id": "test_pool_1",
            "attributes": {
                "name": "Test Pool",
                "base_token_price_usd": None,
                "fdv_usd": "",
                "transactions_h1_buys": None,
                "volume_usd_h24": "invalid_number"
            }
        }
        
        result = new_pools_collector._create_history_record(pool_data)
        
        assert result is not None
        assert result["pool_id"] == "test_pool_1"
        assert result["base_token_price_usd"] is None
        assert result["fdv_usd"] is None
        assert result["transactions_h1_buys"] is None
        assert result["volume_usd_h24"] is None  # Invalid number should become None
    
    @pytest.mark.asyncio
    async def test_ensure_pool_exists_new_pool(self, new_pools_collector, mock_db_manager):
        """Test ensuring pool exists when pool is new."""
        pool_info = {
            "id": "new_pool_1",
            "name": "New Pool",
            "address": "0x123456",
            "dex_id": "heaven",
            "base_token_id": "base_1",
            "quote_token_id": "quote_1",
            "reserve_usd": Decimal("10000.50"),
            "created_at": datetime.now(),
            "last_updated": datetime.now()
        }
        
        # Mock that pool doesn't exist
        mock_db_manager.get_pool_by_id.return_value = None
        
        result = await new_pools_collector._ensure_pool_exists(pool_info)
        
        assert result is True
        mock_db_manager.get_pool_by_id.assert_called_once_with("new_pool_1")
        mock_db_manager.store_pool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ensure_pool_exists_existing_pool(self, new_pools_collector, mock_db_manager):
        """Test ensuring pool exists when pool already exists."""
        pool_info = {
            "id": "existing_pool_1",
            "name": "Existing Pool"
        }
        
        # Mock that pool already exists
        mock_pool = MagicMock()
        mock_db_manager.get_pool_by_id.return_value = mock_pool
        
        result = await new_pools_collector._ensure_pool_exists(pool_info)
        
        assert result is False
        mock_db_manager.get_pool_by_id.assert_called_once_with("existing_pool_1")
        mock_db_manager.store_pool.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_store_history_record(self, new_pools_collector, mock_db_manager):
        """Test storing history record."""
        history_record = {
            "pool_id": "test_pool_1",
            "name": "Test Pool",
            "collected_at": datetime.now()
        }
        
        await new_pools_collector._store_history_record(history_record)
        
        mock_db_manager.store_new_pools_history.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_valid(self, new_pools_collector):
        """Test validation with valid data."""
        data = [
            {
                "id": "pool_1",
                "attributes": {"name": "Pool 1"}
            },
            {
                "id": "pool_2", 
                "attributes": {"name": "Pool 2"}
            }
        ]
        
        result = await new_pools_collector._validate_specific_data(data)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_invalid_type(self, new_pools_collector):
        """Test validation with invalid data type."""
        data = "not_a_list"
        
        result = await new_pools_collector._validate_specific_data(data)
        
        assert result.is_valid is False
        assert "Expected list of pools" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_missing_fields(self, new_pools_collector):
        """Test validation with missing required fields."""
        data = [
            {"attributes": {"name": "Pool 1"}},  # Missing id
            {"id": "pool_2"}  # Missing attributes
        ]
        
        result = await new_pools_collector._validate_specific_data(data)
        
        assert result.is_valid is False
        assert any("Missing required 'id' field" in error for error in result.errors)
        assert any("Missing 'attributes' field" in error for error in result.errors)
    
    @pytest.mark.asyncio
    async def test_collect_success(self, new_pools_collector, mock_api_response):
        """Test successful collection."""
        # Mock the API client
        mock_client = AsyncMock()
        mock_client.get_new_pools_by_network.return_value = mock_api_response
        new_pools_collector._client = mock_client
        
        # Mock rate limiter
        new_pools_collector.rate_limiter = AsyncMock()
        new_pools_collector.rate_limiter.acquire = AsyncMock()
        
        result = await new_pools_collector.collect()
        
        assert result.success is True
        assert result.records_collected > 0
        assert result.collector_type == "new_pools_solana"
        assert "network" in result.metadata
        assert result.metadata["network"] == "solana"
    
    @pytest.mark.asyncio
    async def test_collect_no_data(self, new_pools_collector):
        """Test collection with no data from API."""
        # Mock the API client to return empty response
        mock_client = AsyncMock()
        mock_client.get_new_pools_by_network.return_value = None
        new_pools_collector._client = mock_client
        
        # Mock rate limiter
        new_pools_collector.rate_limiter = AsyncMock()
        new_pools_collector.rate_limiter.acquire = AsyncMock()
        
        result = await new_pools_collector.collect()
        
        assert result.success is False
        assert "No data received from API" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_collect_validation_failure(self, new_pools_collector):
        """Test collection with validation failure."""
        # Mock the API client to return invalid data
        mock_client = AsyncMock()
        mock_client.get_new_pools_by_network.return_value = {"data": "invalid_data"}
        new_pools_collector._client = mock_client
        
        # Mock rate limiter
        new_pools_collector.rate_limiter = AsyncMock()
        new_pools_collector.rate_limiter.acquire = AsyncMock()
        
        result = await new_pools_collector.collect()

        print("-_test_collect_validation_failure--")
        print(result)
        print("---")
        
        assert result.success is False
        assert "Data validation failed" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_collect_api_exception(self, new_pools_collector):
        """Test collection with API exception."""
        # Mock the API client to raise exception
        mock_client = AsyncMock()
        mock_client.get_new_pools_by_network.side_effect = Exception("API Error")
        new_pools_collector._client = mock_client
        
        # Mock rate limiter
        new_pools_collector.rate_limiter = AsyncMock()
        new_pools_collector.rate_limiter.acquire = AsyncMock()
        
        result = await new_pools_collector.collect()
        
        assert result.success is False
        assert "New pools collection failed" in result.errors[0]
        assert "API Error" in result.errors[0]


if __name__ == "__main__":
    pytest.main([__file__])