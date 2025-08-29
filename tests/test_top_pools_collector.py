"""
Tests for the TopPoolsCollector.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
from gecko_terminal_collector.config.models import CollectionConfig, APIConfig, ErrorConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult, Pool


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
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
    """Create a mock database manager."""
    db_manager = AsyncMock(spec=DatabaseManager)
    return db_manager


@pytest.fixture
def sample_pools_api_response():
    """Sample API response for top pools."""
    return {
        "data": [
            {
                "id": "solana_AnvQMnzXbAeYRWEbhM7FcivoSxA1roFS41La1ZcFxfgb",
                "type": "pool",
                "attributes": {
                    "name": "Resilience / SOL",
                    "address": "AnvQMnzXbAeYRWEbhM7FcivoSxA1roFS41La1ZcFxfgb",
                    "base_token_price_usd": "0.0000130998297715387",
                    "quote_token_price_usd": "214.73",
                    "reserve_in_usd": "19680.7346",
                    "pool_created_at": "2025-08-28T17:52:49Z",
                    "fdv_usd": "13099.82977",
                    "market_cap_usd": None,
                    "price_change_percentage": {
                        "h1": -0.834,
                        "h24": -40.815
                    },
                    "transactions": {
                        "h1": {"buys": 0, "sells": 3},
                        "h24": {"buys": 1981, "sells": 1503}
                    },
                    "volume_usd": {"h24": "449979.315884139"}
                },
                "relationships": {
                    "dex": {
                        "data": {"id": "heaven", "type": "dex"}
                    },
                    "base_token": {
                        "data": {"id": "J6zQ2rjFrs7Va3yCHw5bs63n3VFgKfq9DaFUxBCVY777", "type": "token"}
                    },
                    "quote_token": {
                        "data": {"id": "So11111111111111111111111111111111111111112", "type": "token"}
                    }
                }
            },
            {
                "id": "solana_EkU9zGSkUnVVK6nhmPSqnxqcKPzt1PicrCjdxSbWo9uA",
                "type": "pool",
                "attributes": {
                    "name": "$LIGHT / SOL",
                    "address": "EkU9zGSkUnVVK6nhmPSqnxqcKPzt1PicrCjdxSbWo9uA",
                    "base_token_price_usd": "0.0678777593860309",
                    "quote_token_price_usd": "215.15",
                    "reserve_in_usd": "3052941.1365",
                    "pool_created_at": "2025-08-11T20:37:25Z",
                    "fdv_usd": "63949167.973854",
                    "market_cap_usd": "34869432.469885"
                },
                "relationships": {
                    "dex": {
                        "data": {"id": "heaven", "type": "dex"}
                    },
                    "base_token": {
                        "data": {"id": "LiGHtkg3uTa9836RaNkKLLriqTNRcMdRAhqjGWNv777", "type": "token"}
                    },
                    "quote_token": {
                        "data": {"id": "So11111111111111111111111111111111111111112", "type": "token"}
                    }
                }
            }
        ],
        "meta": {
            "page": {"current": 1, "total": 1}
        }
    }


@pytest.fixture
def sample_pumpswap_pools_response():
    """Sample API response for pumpswap pools."""
    return {
        "data": [
            {
                "id": "solana_3wbpAjoX1rxxYerML8WNRemVzhURfgwVM5RLyNG8gZjR",
                "type": "pool",
                "attributes": {
                    "name": "LILPEPE / SOL",
                    "address": "3wbpAjoX1rxxYerML8WNRemVzhURfgwVM5RLyNG8gZjR",
                    "base_token_price_usd": "0.000000910765610973197221239067403588963512548543180968162675148052983",
                    "quote_token_price_usd": "215.248203858186543737468032297097775055730853853",
                    "reserve_in_usd": "0.1723",
                    "pool_created_at": "2025-08-28T09:48:18Z"
                },
                "relationships": {
                    "dex": {
                        "data": {"id": "pumpswap", "type": "dex"}
                    },
                    "base_token": {
                        "data": {"id": "3tsDiiC2AyHg8RAttK4qpbG7HBUSjrM8Ho1h4kqUMgTr", "type": "token"}
                    },
                    "quote_token": {
                        "data": {"id": "So11111111111111111111111111111111111111112", "type": "token"}
                    }
                }
            }
        ]
    }


class TestTopPoolsCollector:
    """Test cases for TopPoolsCollector."""
    
    def test_initialization(self, mock_config, mock_db_manager):
        """Test collector initialization."""
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            network="solana",
            target_dexes=["heaven", "pumpswap"]
        )
        
        assert collector.network == "solana"
        assert collector.target_dexes == ["heaven", "pumpswap"]
        assert collector.get_collection_key() == "top_pools_solana"
    
    def test_initialization_with_defaults(self, mock_config, mock_db_manager):
        """Test collector initialization with default values."""
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        assert collector.network == "solana"
        assert collector.target_dexes == ["heaven", "pumpswap"]
    
    @pytest.mark.asyncio
    async def test_collect_success(self, mock_config, mock_db_manager, sample_pools_api_response, sample_pumpswap_pools_response):
        """Test successful collection of top pools."""
        # Setup mocks
        mock_client = AsyncMock()
        mock_client.get_top_pools_by_network_dex.side_effect = [
            sample_pools_api_response,  # heaven response
            sample_pumpswap_pools_response  # pumpswap response
        ]
        
        mock_db_manager.store_pools.return_value = 3  # Total pools stored
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
        
        # Mock the client property by patching the _client attribute
        with patch.object(collector, '_client', mock_client):
            result = await collector.collect()
        
        # Verify result
        assert result.success is True
        assert result.records_collected == 6  # 3 pools per DEX
        assert len(result.errors) == 0
        assert result.collector_type == "top_pools_solana"
        
        # Verify API calls
        assert mock_client.get_top_pools_by_network_dex.call_count == 2
        mock_client.get_top_pools_by_network_dex.assert_any_call("solana", "heaven")
        mock_client.get_top_pools_by_network_dex.assert_any_call("solana", "pumpswap")
        
        # Verify database calls
        assert mock_db_manager.store_pools.call_count == 2
    
    @pytest.mark.asyncio
    async def test_collect_api_failure(self, mock_config, mock_db_manager):
        """Test collection with API failure."""
        mock_client = AsyncMock()
        mock_client.get_top_pools_by_network_dex.side_effect = Exception("API Error")
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            target_dexes=["heaven"]
        )
        
        with patch.object(collector, '_client', mock_client):
            result = await collector.collect()
        
        # Verify result
        assert result.success is False
        assert result.records_collected == 0
        assert len(result.errors) == 1
        assert "API Error" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_collect_partial_failure(self, mock_config, mock_db_manager, sample_pools_api_response):
        """Test collection with partial failure (one DEX fails)."""
        mock_client = AsyncMock()
        mock_client.get_top_pools_by_network_dex.side_effect = [
            sample_pools_api_response,  # heaven succeeds
            Exception("Pumpswap API Error")  # pumpswap fails
        ]
        
        mock_db_manager.store_pools.return_value = 2
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        with patch.object(collector, '_client', mock_client):
            result = await collector.collect()
        
        # Verify result - should be failure due to errors, but some records collected
        assert result.success is False
        assert result.records_collected == 2
        assert len(result.errors) == 1
        assert "Pumpswap API Error" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_collect_empty_response(self, mock_config, mock_db_manager):
        """Test collection with empty API response."""
        mock_client = AsyncMock()
        mock_client.get_top_pools_by_network_dex.return_value = None
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            target_dexes=["heaven"]
        )
        
        with patch.object(collector, '_client', mock_client):
            result = await collector.collect()
        
        # Verify result
        assert result.success is False
        assert result.records_collected == 0
        assert len(result.errors) == 1
        assert "No pools data returned" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_valid(self, mock_config, mock_db_manager, sample_pools_api_response):
        """Test validation of valid pools data."""
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        validation_result = await collector._validate_specific_data(sample_pools_api_response)
        
        assert validation_result.is_valid is True
        assert len(validation_result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_invalid_structure(self, mock_config, mock_db_manager):
        """Test validation of invalid data structure."""
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        # Test with non-dict data
        validation_result = await collector._validate_specific_data("invalid")
        assert validation_result.is_valid is False
        assert "must be a dictionary" in validation_result.errors[0]
        
        # Test with missing data field
        validation_result = await collector._validate_specific_data({"meta": {}})
        assert validation_result.is_valid is True  # Empty data is valid but generates warning
        assert "No pools found" in validation_result.warnings[0]
        
        # Test with empty data
        validation_result = await collector._validate_specific_data({"data": []})
        assert validation_result.is_valid is True
        assert "No pools found" in validation_result.warnings[0]
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_missing_fields(self, mock_config, mock_db_manager):
        """Test validation with missing required fields."""
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        invalid_data = {
            "data": [
                {
                    # Missing id and type
                    "attributes": {"name": "Test Pool"}
                }
            ]
        }
        
        validation_result = await collector._validate_specific_data(invalid_data)
        assert validation_result.is_valid is False
        assert any("missing required 'id' field" in error for error in validation_result.errors)
        assert any("missing required 'type' field" in error for error in validation_result.errors)
    
    def test_process_pools_data(self, mock_config, mock_db_manager, sample_pools_api_response):
        """Test processing of pools data."""
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        pool_records = collector._process_pools_data(sample_pools_api_response, "heaven")
        
        assert len(pool_records) == 2
        
        # Check first pool
        pool1 = pool_records[0]
        assert pool1.id == "solana_AnvQMnzXbAeYRWEbhM7FcivoSxA1roFS41La1ZcFxfgb"
        assert pool1.name == "Resilience / SOL"
        assert pool1.address == "AnvQMnzXbAeYRWEbhM7FcivoSxA1roFS41La1ZcFxfgb"
        assert pool1.dex_id == "heaven"
        assert pool1.base_token_id == "J6zQ2rjFrs7Va3yCHw5bs63n3VFgKfq9DaFUxBCVY777"
        assert pool1.quote_token_id == "So11111111111111111111111111111111111111112"
        assert pool1.reserve_usd == Decimal("19680.7346")
        assert pool1.created_at.replace(tzinfo=None) == datetime(2025, 8, 28, 17, 52, 49)
        
        # Check second pool
        pool2 = pool_records[1]
        assert pool2.id == "solana_EkU9zGSkUnVVK6nhmPSqnxqcKPzt1PicrCjdxSbWo9uA"
        assert pool2.name == "$LIGHT / SOL"
        assert pool2.reserve_usd == Decimal("3052941.1365")
    
    def test_process_pools_data_invalid_entries(self, mock_config, mock_db_manager):
        """Test processing with invalid pool entries."""
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        invalid_data = {
            "data": [
                None,  # Invalid entry
                {"id": "valid_pool", "attributes": {"name": "Valid Pool", "address": "addr1"}},
                {"attributes": {"name": "No ID"}},  # Missing ID
            ]
        }
        
        pool_records = collector._process_pools_data(invalid_data, "heaven")
        
        # Should only process the valid entry
        assert len(pool_records) == 1
        assert pool_records[0].id == "valid_pool"
    
    def test_safe_decimal_conversion(self, mock_config, mock_db_manager):
        """Test safe decimal conversion."""
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        # Test valid conversions
        assert collector._safe_decimal_conversion("123.45") == Decimal("123.45")
        assert collector._safe_decimal_conversion(123.45) == Decimal("123.45")
        assert collector._safe_decimal_conversion(123) == Decimal("123")
        assert collector._safe_decimal_conversion("1,234.56") == Decimal("1234.56")
        
        # Test invalid conversions
        assert collector._safe_decimal_conversion(None) is None
        assert collector._safe_decimal_conversion("") is None
        assert collector._safe_decimal_conversion("invalid") is None
        assert collector._safe_decimal_conversion(".") is None
    
    @pytest.mark.asyncio
    async def test_store_pools_data(self, mock_config, mock_db_manager):
        """Test storing pools data."""
        mock_db_manager.store_pools.return_value = 2
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        pool_records = [
            Pool(id="pool1", address="addr1", name="Pool 1", dex_id="heaven", 
                 base_token_id="token1", quote_token_id="token2", 
                 reserve_usd=Decimal("1000"), created_at=datetime.now()),
            Pool(id="pool2", address="addr2", name="Pool 2", dex_id="heaven",
                 base_token_id="token3", quote_token_id="token4", 
                 reserve_usd=Decimal("2000"), created_at=datetime.now())
        ]
        
        stored_count = await collector._store_pools_data(pool_records)
        
        assert stored_count == 2
        mock_db_manager.store_pools.assert_called_once_with(pool_records)
    
    @pytest.mark.asyncio
    async def test_store_pools_data_empty(self, mock_config, mock_db_manager):
        """Test storing empty pools data."""
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        stored_count = await collector._store_pools_data([])
        
        assert stored_count == 0
        mock_db_manager.store_pools.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_store_pools_data_database_error(self, mock_config, mock_db_manager):
        """Test handling database errors during storage."""
        mock_db_manager.store_pools.side_effect = Exception("Database error")
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        pool_records = [Pool(id="pool1", address="addr1", name="Pool 1", dex_id="heaven",
                            base_token_id="token1", quote_token_id="token2", 
                            reserve_usd=Decimal("1000"), created_at=datetime.now())]
        
        with pytest.raises(Exception, match="Database error"):
            await collector._store_pools_data(pool_records)
    
    @pytest.mark.asyncio
    async def test_get_top_pools_by_dex(self, mock_config, mock_db_manager):
        """Test getting top pools by DEX."""
        # Setup mock pools with different reserves
        mock_pools = [
            Pool(id="pool1", address="addr1", name="Pool 1", dex_id="heaven", 
                 base_token_id="token1", quote_token_id="token2", 
                 reserve_usd=Decimal("1000"), created_at=datetime.now()),
            Pool(id="pool2", address="addr2", name="Pool 2", dex_id="heaven", 
                 base_token_id="token3", quote_token_id="token4", 
                 reserve_usd=Decimal("2000"), created_at=datetime.now()),
            Pool(id="pool3", address="addr3", name="Pool 3", dex_id="heaven", 
                 base_token_id="token5", quote_token_id="token6", 
                 reserve_usd=None, created_at=datetime.now()),
        ]
        mock_db_manager.get_pools_by_dex.return_value = mock_pools
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        # Test without limit
        result = await collector.get_top_pools_by_dex("heaven")
        assert len(result) == 3
        assert result[0].id == "pool2"  # Highest reserve first
        assert result[1].id == "pool1"
        assert result[2].id == "pool3"  # None reserve last
        
        # Test with limit
        result = await collector.get_top_pools_by_dex("heaven", limit=2)
        assert len(result) == 2
        assert result[0].id == "pool2"
        assert result[1].id == "pool1"
    
    @pytest.mark.asyncio
    async def test_get_pool_statistics(self, mock_config, mock_db_manager):
        """Test getting pool statistics."""
        # Setup mock pools for different DEXes
        heaven_pools = [
            Pool(id="h1", address="addr1", name="Pool 1", dex_id="heaven", 
                 base_token_id="token1", quote_token_id="token2", 
                 reserve_usd=Decimal("1000"), created_at=datetime.now()),
            Pool(id="h2", address="addr2", name="Pool 2", dex_id="heaven", 
                 base_token_id="token3", quote_token_id="token4", 
                 reserve_usd=Decimal("2000"), created_at=datetime.now()),
        ]
        pumpswap_pools = [
            Pool(id="p1", address="addr3", name="Pool 3", dex_id="pumpswap", 
                 base_token_id="token5", quote_token_id="token6", 
                 reserve_usd=Decimal("500"), created_at=datetime.now()),
        ]
        
        def mock_get_pools_by_dex(dex_id):
            if dex_id == "heaven":
                return heaven_pools
            elif dex_id == "pumpswap":
                return pumpswap_pools
            return []
        
        mock_db_manager.get_pools_by_dex.side_effect = mock_get_pools_by_dex
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        # Test statistics for all DEXes
        stats = await collector.get_pool_statistics()
        
        assert stats["total_pools"] == 3
        assert stats["total_reserve_usd"] == Decimal("3500")
        assert stats["dex_breakdown"]["heaven"]["pools"] == 2
        assert stats["dex_breakdown"]["heaven"]["reserve_usd"] == Decimal("3000")
        assert stats["dex_breakdown"]["pumpswap"]["pools"] == 1
        assert stats["dex_breakdown"]["pumpswap"]["reserve_usd"] == Decimal("500")
        
        # Test statistics for specific DEX
        stats = await collector.get_pool_statistics("heaven")
        
        assert stats["total_pools"] == 2
        assert stats["total_reserve_usd"] == Decimal("3000")
        assert len(stats["dex_breakdown"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_pool_statistics_database_error(self, mock_config, mock_db_manager):
        """Test handling database errors in statistics."""
        mock_db_manager.get_pools_by_dex.side_effect = Exception("Database error")
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        stats = await collector.get_pool_statistics()
        
        assert stats["total_pools"] == 0
        assert stats["total_reserve_usd"] == Decimal("0")
        assert "error" in stats
        assert "Database error" in stats["error"]


class TestTopPoolsCollectorIntegration:
    """Integration tests using CSV fixture data."""
    
    @pytest.mark.asyncio
    async def test_collect_with_mock_client_heaven(self, mock_config, mock_db_manager):
        """Test collection using mock client with heaven CSV data."""
        mock_db_manager.store_pools.return_value = 20  # Assume 20 pools stored
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            target_dexes=["heaven"],
            use_mock=True
        )
        
        result = await collector.collect()
        
        # Should succeed with mock data
        assert result.success is True
        assert result.records_collected == 20
        assert len(result.errors) == 0
        
        # Verify database was called
        mock_db_manager.store_pools.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collect_with_mock_client_pumpswap(self, mock_config, mock_db_manager):
        """Test collection using mock client with pumpswap CSV data."""
        mock_db_manager.store_pools.return_value = 20  # Assume 20 pools stored
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            target_dexes=["pumpswap"],
            use_mock=True
        )
        
        result = await collector.collect()
        
        # Should succeed with mock data
        assert result.success is True
        assert result.records_collected == 20
        assert len(result.errors) == 0
        
        # Verify database was called
        mock_db_manager.store_pools.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collect_with_mock_client_both_dexes(self, mock_config, mock_db_manager):
        """Test collection using mock client with both DEX CSV data."""
        mock_db_manager.store_pools.return_value = 20  # Assume 20 pools stored per DEX
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
        
        result = await collector.collect()
        
        # Should succeed with mock data for both DEXes
        assert result.success is True
        assert result.records_collected == 40  # 20 pools per DEX
        assert len(result.errors) == 0
        
        # Verify database was called twice (once per DEX)
        assert mock_db_manager.store_pools.call_count == 2