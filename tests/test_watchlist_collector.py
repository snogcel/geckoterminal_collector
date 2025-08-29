"""
Tests for the WatchlistCollector.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
from gecko_terminal_collector.config.models import CollectionConfig, DEXConfig, WatchlistConfig
from gecko_terminal_collector.database.models import WatchlistEntry
from gecko_terminal_collector.models.core import Pool, Token, ValidationResult


class TestWatchlistCollector:
    """Test WatchlistCollector functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock(spec=CollectionConfig)
        
        # Mock DEX config
        config.dexes = MagicMock(spec=DEXConfig)
        config.dexes.network = "solana"
        
        # Mock watchlist config
        config.watchlist = MagicMock(spec=WatchlistConfig)
        config.watchlist.batch_size = 20
        
        # Mock error handling config
        config.error_handling = MagicMock()
        config.error_handling.max_retries = 3
        config.error_handling.backoff_factor = 2.0
        config.error_handling.circuit_breaker_threshold = 5
        config.error_handling.circuit_breaker_timeout = 300
        
        # Mock API config
        config.api = MagicMock()
        config.api.timeout = 30
        config.api.max_concurrent = 5
        
        return config
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        db_manager = AsyncMock()
        
        # Mock watchlist methods
        db_manager.get_watchlist_pools.return_value = [
            "solana_pool1",
            "solana_pool2"
        ]
        
        # Mock watchlist entry
        watchlist_entry1 = WatchlistEntry(
            pool_id="solana_pool1",
            token_symbol="TOKEN1",
            token_name="Test Token 1",
            network_address="network_addr1",
            is_active=True
        )
        watchlist_entry2 = WatchlistEntry(
            pool_id="solana_pool2",
            token_symbol="TOKEN2",
            token_name="Test Token 2",
            network_address="network_addr2",
            is_active=True
        )
        
        db_manager.get_watchlist_entry_by_pool_id.side_effect = lambda pool_id: {
            "solana_pool1": watchlist_entry1,
            "solana_pool2": watchlist_entry2
        }.get(pool_id)
        
        # Mock storage methods
        db_manager.store_pools.return_value = 2
        db_manager.store_tokens.return_value = 2
        
        # Mock retrieval methods
        db_manager.get_pool.return_value = Pool(
            id="solana_pool1",
            address="pool_address1",
            name="Test Pool",
            dex_id="heaven",
            base_token_id="base_token1",
            quote_token_id="quote_token1",
            reserve_usd=Decimal("10000.0"),
            created_at=datetime.now()
        )
        
        db_manager.get_token.return_value = Token(
            id="network_addr1",
            address="network_addr1",
            name="Test Token",
            symbol="TOKEN1",
            decimals=9,
            network="solana",
            price_usd=Decimal("1.50")
        )
        
        return db_manager
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock API client."""
        client = AsyncMock()
        
        # Mock multiple pools response
        client.get_multiple_pools_by_network.return_value = {
            "data": [
                {
                    "id": "solana_pool1",
                    "attributes": {
                        "address": "pool_address1",
                        "name": "Test Pool 1",
                        "reserve_in_usd": "10000.0",
                        "pool_created_at": "2024-01-01T00:00:00Z"
                    },
                    "relationships": {
                        "dex": {"data": {"id": "heaven"}},
                        "base_token": {"data": {"id": "base_token1"}},
                        "quote_token": {"data": {"id": "quote_token1"}}
                    }
                },
                {
                    "id": "solana_pool2",
                    "attributes": {
                        "address": "pool_address2",
                        "name": "Test Pool 2",
                        "reserve_in_usd": "20000.0",
                        "pool_created_at": "2024-01-02T00:00:00Z"
                    },
                    "relationships": {
                        "dex": {"data": {"id": "pumpswap"}},
                        "base_token": {"data": {"id": "base_token2"}},
                        "quote_token": {"data": {"id": "quote_token2"}}
                    }
                }
            ]
        }
        
        # Mock single pool response
        client.get_pool_by_network_address.return_value = {
            "data": {
                "id": "solana_pool1",
                "attributes": {
                    "address": "pool_address1",
                    "name": "Test Pool 1",
                    "reserve_in_usd": "10000.0",
                    "pool_created_at": "2024-01-01T00:00:00Z"
                },
                "relationships": {
                    "dex": {"data": {"id": "heaven"}},
                    "base_token": {"data": {"id": "base_token1"}},
                    "quote_token": {"data": {"id": "quote_token1"}}
                }
            }
        }
        
        # Mock token response
        client.get_token_info.return_value = {
            "data": {
                "id": "network_addr1",
                "attributes": {
                    "address": "network_addr1",
                    "name": "Test Token",
                    "symbol": "TOKEN1",
                    "decimals": 9,
                    "price_usd": "1.50"
                }
            }
        }
        
        return client
    
    @pytest.fixture
    def collector(self, mock_config, mock_db_manager):
        """Create a WatchlistCollector instance."""
        return WatchlistCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
    
    @pytest.mark.asyncio
    async def test_collect_success(self, collector, mock_client):
        """Test successful watchlist data collection."""
        collector._client = mock_client
        
        result = await collector.collect()
        
        assert result.success is True
        assert result.records_collected > 0
        assert len(result.errors) == 0
        
        # Verify API calls were made
        mock_client.get_multiple_pools_by_network.assert_called_once()
        mock_client.get_token_info.assert_called()
    
    @pytest.mark.asyncio
    async def test_collect_no_watchlist_entries(self, collector, mock_db_manager):
        """Test collection when no watchlist entries exist."""
        mock_db_manager.get_watchlist_pools.return_value = []
        
        result = await collector.collect()
        
        assert result.success is True
        assert result.records_collected == 0
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_collect_batch_api_failure_with_fallback(self, collector, mock_client):
        """Test batch collection failure with individual fallback."""
        collector._client = mock_client
        
        # Make batch call fail
        mock_client.get_multiple_pools_by_network.side_effect = Exception("API Error")
        
        result = await collector.collect()
        
        # Should still succeed with individual calls
        assert result.success is True
        assert result.records_collected > 0
        
        # Verify fallback to individual calls
        mock_client.get_pool_by_network_address.assert_called()
    
    @pytest.mark.asyncio
    async def test_parse_pools_response(self, collector):
        """Test parsing of multiple pools API response."""
        response = {
            "data": [
                {
                    "id": "solana_pool1",
                    "attributes": {
                        "address": "pool_address1",
                        "name": "Test Pool",
                        "reserve_in_usd": "10000.0",
                        "pool_created_at": "2024-01-01T00:00:00Z"
                    },
                    "relationships": {
                        "dex": {"data": {"id": "heaven"}},
                        "base_token": {"data": {"id": "base_token1"}},
                        "quote_token": {"data": {"id": "quote_token1"}}
                    }
                }
            ]
        }
        
        pools = collector._parse_pools_response(response)
        
        assert len(pools) == 1
        assert pools[0].id == "solana_pool1"
        assert pools[0].address == "pool_address1"
        assert pools[0].name == "Test Pool"
        assert pools[0].dex_id == "heaven"
        assert pools[0].reserve_usd == Decimal("10000.0")
    
    @pytest.mark.asyncio
    async def test_parse_single_pool_response(self, collector):
        """Test parsing of single pool API response."""
        response = {
            "data": {
                "id": "solana_pool1",
                "attributes": {
                    "address": "pool_address1",
                    "name": "Test Pool",
                    "reserve_in_usd": "10000.0",
                    "pool_created_at": "2024-01-01T00:00:00Z"
                },
                "relationships": {
                    "dex": {"data": {"id": "heaven"}},
                    "base_token": {"data": {"id": "base_token1"}},
                    "quote_token": {"data": {"id": "quote_token1"}}
                }
            }
        }
        
        pool = collector._parse_single_pool_response(response)
        
        assert pool is not None
        assert pool.id == "solana_pool1"
        assert pool.address == "pool_address1"
        assert pool.name == "Test Pool"
        assert pool.dex_id == "heaven"
        assert pool.reserve_usd == Decimal("10000.0")
    
    @pytest.mark.asyncio
    async def test_parse_token_response(self, collector):
        """Test parsing of token API response."""
        response = {
            "data": {
                "id": "network_addr1",
                "attributes": {
                    "address": "network_addr1",
                    "name": "Test Token",
                    "symbol": "TOKEN1",
                    "decimals": 9,
                    "price_usd": "1.50"
                }
            }
        }
        
        token = collector._parse_token_response(response)
        
        assert token is not None
        assert token.id == "network_addr1"
        assert token.address == "network_addr1"
        assert token.name == "Test Token"
        assert token.symbol == "TOKEN1"
        assert token.decimals == 9
        assert token.price_usd == Decimal("1.50")
        assert token.network == "solana"
    
    @pytest.mark.asyncio
    async def test_parse_pool_data_missing_required_fields(self, collector):
        """Test parsing pool data with missing required fields."""
        pool_data = {
            "attributes": {
                "name": "Test Pool",
                "reserve_in_usd": "10000.0"
            },
            "relationships": {
                "dex": {"data": {"id": "heaven"}}
            }
        }
        
        pool = collector._parse_pool_data(pool_data)
        
        assert pool is None
    
    @pytest.mark.asyncio
    async def test_parse_token_response_missing_required_fields(self, collector):
        """Test parsing token response with missing required fields."""
        response = {
            "data": {
                "attributes": {
                    "name": "Test Token",
                    "symbol": "TOKEN1",
                    "decimals": 9
                }
            }
        }
        
        token = collector._parse_token_response(response)
        
        assert token is None
    
    @pytest.mark.asyncio
    async def test_validate_specific_data(self, collector, mock_db_manager):
        """Test data validation."""
        # Mock successful validation
        mock_db_manager.get_pool.return_value = Pool(
            id="solana_pool1",
            address="pool_address1",
            name="Test Pool",
            dex_id="heaven",
            base_token_id="base_token1",
            quote_token_id="quote_token1",
            reserve_usd=Decimal("10000.0"),
            created_at=datetime.now()
        )
        
        result = await collector._validate_specific_data(None)
        
        assert result is not None
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_missing_pool(self, collector, mock_db_manager):
        """Test validation with missing pool data."""
        # Mock missing pool
        mock_db_manager.get_pool.return_value = None
        
        result = await collector._validate_specific_data(None)
        
        assert result is not None
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Pool data missing" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_get_collection_status(self, collector, mock_db_manager):
        """Test getting collection status."""
        status = await collector.get_collection_status()
        
        assert "total_watchlist_entries" in status
        assert "pools_with_data" in status
        assert "tokens_with_data" in status
        assert "data_coverage_percentage" in status
        assert status["total_watchlist_entries"] == 2
        assert status["pools_with_data"] == 2
        assert status["tokens_with_data"] == 2
        assert status["data_coverage_percentage"] == 100.0
    
    @pytest.mark.asyncio
    async def test_get_collection_key(self, collector):
        """Test getting collection key."""
        key = collector.get_collection_key()
        assert key == "watchlist_collector"
    
    @pytest.mark.asyncio
    async def test_collect_with_api_error(self, collector, mock_client):
        """Test collection with API error."""
        collector._client = mock_client
        
        # Make all API calls fail
        mock_client.get_multiple_pools_by_network.side_effect = Exception("API Error")
        mock_client.get_pool_by_network_address.side_effect = Exception("API Error")
        mock_client.get_token_info.side_effect = Exception("API Error")
        
        result = await collector.collect()
        
        # Should handle errors gracefully
        assert result.success is True  # Still succeeds even with API errors
        # Records may still be collected from database operations
        assert result.records_collected >= 0
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, collector, mock_client):
        """Test batch processing with large number of pools."""
        collector._client = mock_client
        
        # Create collector with small batch size
        collector.batch_size = 1
        
        result = await collector.collect()
        
        assert result.success is True
        # Should make multiple batch calls due to small batch size
        assert mock_client.get_multiple_pools_by_network.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_parse_pools_response_invalid_data(self, collector):
        """Test parsing pools response with invalid data structure."""
        response = {
            "data": "invalid_data_structure"
        }
        
        pools = collector._parse_pools_response(response)
        
        assert len(pools) == 0
    
    @pytest.mark.asyncio
    async def test_parse_pool_data_invalid_decimal(self, collector):
        """Test parsing pool data with invalid decimal values."""
        pool_data = {
            "id": "solana_pool1",
            "attributes": {
                "address": "pool_address1",
                "name": "Test Pool",
                "reserve_in_usd": "invalid_decimal",
                "pool_created_at": "2024-01-01T00:00:00Z"
            },
            "relationships": {
                "dex": {"data": {"id": "heaven"}},
                "base_token": {"data": {"id": "base_token1"}},
                "quote_token": {"data": {"id": "quote_token1"}}
            }
        }
        
        pool = collector._parse_pool_data(pool_data)
        
        assert pool is not None
        assert pool.reserve_usd == Decimal("0")  # Should default to 0
    
    @pytest.mark.asyncio
    async def test_parse_pool_data_invalid_date(self, collector):
        """Test parsing pool data with invalid date format."""
        pool_data = {
            "id": "solana_pool1",
            "attributes": {
                "address": "pool_address1",
                "name": "Test Pool",
                "reserve_in_usd": "10000.0",
                "pool_created_at": "invalid_date"
            },
            "relationships": {
                "dex": {"data": {"id": "heaven"}},
                "base_token": {"data": {"id": "base_token1"}},
                "quote_token": {"data": {"id": "quote_token1"}}
            }
        }
        
        pool = collector._parse_pool_data(pool_data)
        
        assert pool is not None
        assert pool.created_at is not None  # Should use current time as fallback