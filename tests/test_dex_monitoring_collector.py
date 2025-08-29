"""
Tests for DEX monitoring collector.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from gecko_terminal_collector.collectors.dex_monitoring import DEXMonitoringCollector
from gecko_terminal_collector.config.models import CollectionConfig, APIConfig, ErrorConfig
from gecko_terminal_collector.database.models import DEX
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult


@pytest.fixture
def mock_config():
    """Create mock configuration for testing."""
    return CollectionConfig(
        api=APIConfig(
            base_url="https://api.geckoterminal.com/api/v2",
            timeout=30,
            rate_limit_delay=1.0,
            max_concurrent=5
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
    """Create mock database manager for testing."""
    db_manager = AsyncMock()
    db_manager.store_dex_data = AsyncMock(return_value=2)
    db_manager.get_dexes_by_network = AsyncMock(return_value=[])
    db_manager.get_dex_by_id = AsyncMock(return_value=None)
    return db_manager


@pytest.fixture
def sample_dex_data():
    """Sample DEX data from the CSV fixture."""
    return [
        {
            "id": "heaven",
            "type": "dex",
            "attributes": {
                "name": "Heaven"
            }
        },
        {
            "id": "pumpswap",
            "type": "dex",
            "attributes": {
                "name": "PumpSwap"
            }
        },
        {
            "id": "raydium",
            "type": "dex",
            "attributes": {
                "name": "Raydium"
            }
        }
    ]


@pytest.fixture
def dex_collector(mock_config, mock_db_manager):
    """Create DEX monitoring collector for testing."""
    return DEXMonitoringCollector(
        config=mock_config,
        db_manager=mock_db_manager,
        network="solana",
        target_dexes=["heaven", "pumpswap"],
        use_mock=True
    )


class TestDEXMonitoringCollector:
    """Test cases for DEX monitoring collector."""
    
    def test_get_collection_key(self, dex_collector):
        """Test collection key generation."""
        assert dex_collector.get_collection_key() == "dex_monitoring_solana"
    
    def test_initialization(self, mock_config, mock_db_manager):
        """Test collector initialization with custom parameters."""
        collector = DEXMonitoringCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            network="ethereum",
            target_dexes=["uniswap", "sushiswap"]
        )
        
        assert collector.network == "ethereum"
        assert collector.target_dexes == ["uniswap", "sushiswap"]
        assert collector.get_collection_key() == "dex_monitoring_ethereum"
    
    def test_initialization_with_defaults(self, mock_config, mock_db_manager):
        """Test collector initialization with default parameters."""
        collector = DEXMonitoringCollector(
            config=mock_config,
            db_manager=mock_db_manager
        )
        
        assert collector.network == "solana"
        assert collector.target_dexes == ["heaven", "pumpswap"]
    
    @pytest.mark.asyncio
    async def test_collect_success(self, dex_collector, sample_dex_data):
        """Test successful DEX data collection."""
        # Mock the API client
        dex_collector.client.get_dexes_by_network = AsyncMock(return_value=sample_dex_data)
        
        result = await dex_collector.collect()
        
        assert result.success is True
        assert result.records_collected == 2  # Mock db_manager returns 2
        assert len(result.errors) == 0
        assert result.collector_type == "dex_monitoring_solana"
        
        # Verify API was called correctly
        dex_collector.client.get_dexes_by_network.assert_called_once_with("solana")
        
        # Verify database storage was called
        dex_collector.db_manager.store_dex_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collect_no_data(self, dex_collector):
        """Test collection when no DEX data is returned."""
        # Mock empty response
        dex_collector.client.get_dexes_by_network = AsyncMock(return_value=None)
        
        result = await dex_collector.collect()
        
        assert result.success is False
        assert result.records_collected == 0
        assert len(result.errors) == 1
        assert "No DEX data returned" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_collect_empty_list(self, dex_collector):
        """Test collection when empty list is returned."""
        # Mock empty list response
        dex_collector.client.get_dexes_by_network = AsyncMock(return_value=[])
        
        result = await dex_collector.collect()
        
        # Empty list should fail because target DEXes are missing
        assert result.success is False
        assert result.records_collected == 0  # No records to store
        assert len(result.errors) >= 1  # Should have errors for missing target DEXes
    
    @pytest.mark.asyncio
    async def test_collect_api_error(self, dex_collector):
        """Test collection when API call fails."""
        # Mock API error
        dex_collector.client.get_dexes_by_network = AsyncMock(
            side_effect=Exception("API connection failed")
        )
        
        result = await dex_collector.collect()
        
        assert result.success is False
        assert result.records_collected == 0
        assert len(result.errors) == 1
        assert "API connection failed" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_collect_missing_target_dex(self, dex_collector):
        """Test collection when target DEX is missing."""
        # Sample data without heaven DEX
        incomplete_data = [
            {
                "id": "pumpswap",
                "type": "dex",
                "attributes": {"name": "PumpSwap"}
            },
            {
                "id": "raydium",
                "type": "dex",
                "attributes": {"name": "Raydium"}
            }
        ]
        
        dex_collector.client.get_dexes_by_network = AsyncMock(return_value=incomplete_data)
        
        result = await dex_collector.collect()
        
        assert result.success is False
        assert len(result.errors) == 1
        assert "Target DEX 'heaven' not found" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_valid(self, dex_collector, sample_dex_data):
        """Test validation of valid DEX data."""
        validation_result = await dex_collector._validate_specific_data(sample_dex_data)
        
        assert validation_result.is_valid is True
        assert len(validation_result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_invalid_structure(self, dex_collector):
        """Test validation of invalid DEX data structure."""
        invalid_data = "not a list"
        
        validation_result = await dex_collector._validate_specific_data(invalid_data)
        
        assert validation_result.is_valid is False
        assert "DEX data must be a list" in validation_result.errors
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_missing_fields(self, dex_collector):
        """Test validation of DEX data with missing required fields."""
        invalid_data = [
            {
                "type": "dex",
                "attributes": {"name": "Test DEX"}
                # Missing 'id' field
            },
            {
                "id": "test-dex-2",
                "attributes": {"name": "Test DEX 2"}
                # Missing 'type' field
            }
        ]
        
        validation_result = await dex_collector._validate_specific_data(invalid_data)
        
        assert validation_result.is_valid is False
        assert any("missing required 'id' field" in error for error in validation_result.errors)
        assert any("missing required 'type' field" in error for error in validation_result.errors)
    
    @pytest.mark.asyncio
    async def test_validate_specific_data_empty_list(self, dex_collector):
        """Test validation of empty DEX data list."""
        validation_result = await dex_collector._validate_specific_data([])
        
        assert validation_result.is_valid is True
        assert len(validation_result.errors) == 0
        assert "No DEXes found in response" in validation_result.warnings
    
    def test_process_dex_data(self, dex_collector, sample_dex_data):
        """Test processing of raw DEX data into model objects."""
        dex_records = dex_collector._process_dex_data(sample_dex_data)
        
        assert len(dex_records) == 3
        
        # Check first DEX record
        heaven_dex = next((dex for dex in dex_records if dex.id == "heaven"), None)
        assert heaven_dex is not None
        assert heaven_dex.name == "Heaven"
        assert heaven_dex.network == "solana"
        assert isinstance(heaven_dex.last_updated, datetime)
        
        # Check second DEX record
        pumpswap_dex = next((dex for dex in dex_records if dex.id == "pumpswap"), None)
        assert pumpswap_dex is not None
        assert pumpswap_dex.name == "PumpSwap"
        assert pumpswap_dex.network == "solana"
    
    def test_process_dex_data_malformed_entry(self, dex_collector):
        """Test processing DEX data with malformed entries."""
        malformed_data = [
            {
                "id": "valid-dex",
                "type": "dex",
                "attributes": {"name": "Valid DEX"}
            },
            {
                # Missing required fields - should be skipped
                "type": "dex"
            },
            None  # Invalid entry - should be skipped
        ]
        
        with patch('gecko_terminal_collector.collectors.dex_monitoring.logger') as mock_logger:
            dex_records = dex_collector._process_dex_data(malformed_data)
        
        # Should only process the valid entry
        assert len(dex_records) == 1
        assert dex_records[0].id == "valid-dex"
        
        # Should log errors for malformed entries
        assert mock_logger.error.call_count >= 2  # One for missing ID, one for None entry
    
    @pytest.mark.asyncio
    async def test_store_dex_data(self, dex_collector):
        """Test storing DEX data in database."""
        dex_records = [
            DEX(id="heaven", name="Heaven", network="solana"),
            DEX(id="pumpswap", name="PumpSwap", network="solana")
        ]
        
        stored_count = await dex_collector._store_dex_data(dex_records)
        
        assert stored_count == 2
        dex_collector.db_manager.store_dex_data.assert_called_once_with(dex_records)
    
    @pytest.mark.asyncio
    async def test_store_dex_data_empty_list(self, dex_collector):
        """Test storing empty DEX data list."""
        stored_count = await dex_collector._store_dex_data([])
        
        assert stored_count == 0
        dex_collector.db_manager.store_dex_data.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_store_dex_data_database_error(self, dex_collector):
        """Test handling database errors during DEX data storage."""
        dex_records = [DEX(id="heaven", name="Heaven", network="solana")]
        
        # Mock database error
        dex_collector.db_manager.store_dex_data.side_effect = Exception("Database error")
        
        with pytest.raises(Exception, match="Database error"):
            await dex_collector._store_dex_data(dex_records)
    
    @pytest.mark.asyncio
    async def test_validate_target_dexes_all_available(self, dex_collector):
        """Test target DEX validation when all are available."""
        dex_records = [
            DEX(id="heaven", name="Heaven", network="solana"),
            DEX(id="pumpswap", name="PumpSwap", network="solana"),
            DEX(id="raydium", name="Raydium", network="solana")
        ]
        
        validation_result = await dex_collector._validate_target_dexes(dex_records)
        
        assert validation_result.is_valid is True
        assert len(validation_result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_target_dexes_missing(self, dex_collector):
        """Test target DEX validation when some are missing."""
        dex_records = [
            DEX(id="raydium", name="Raydium", network="solana"),
            DEX(id="pumpswap", name="PumpSwap", network="solana")
            # Missing "heaven"
        ]
        
        validation_result = await dex_collector._validate_target_dexes(dex_records)
        
        assert validation_result.is_valid is False
        assert len(validation_result.errors) == 1
        assert "Target DEX 'heaven' not found" in validation_result.errors[0]
    
    @pytest.mark.asyncio
    async def test_get_available_dexes(self, dex_collector):
        """Test getting list of available DEXes."""
        mock_dexes = [
            DEX(id="heaven", name="Heaven", network="solana"),
            DEX(id="pumpswap", name="PumpSwap", network="solana")
        ]
        dex_collector.db_manager.get_dexes_by_network.return_value = mock_dexes
        
        available_dexes = await dex_collector.get_available_dexes()
        
        assert available_dexes == ["heaven", "pumpswap"]
        dex_collector.db_manager.get_dexes_by_network.assert_called_once_with("solana")
    
    @pytest.mark.asyncio
    async def test_get_available_dexes_database_error(self, dex_collector):
        """Test handling database errors when getting available DEXes."""
        dex_collector.db_manager.get_dexes_by_network.side_effect = Exception("Database error")
        
        available_dexes = await dex_collector.get_available_dexes()
        
        assert available_dexes == []
    
    @pytest.mark.asyncio
    async def test_is_target_dex_available(self, dex_collector):
        """Test checking if specific DEX is available."""
        # Mock available DEXes
        with patch.object(dex_collector, 'get_available_dexes', return_value=["heaven", "pumpswap"]):
            assert await dex_collector.is_target_dex_available("heaven") is True
            assert await dex_collector.is_target_dex_available("raydium") is False
    
    @pytest.mark.asyncio
    async def test_get_dex_info(self, dex_collector):
        """Test getting detailed DEX information."""
        mock_dex = DEX(id="heaven", name="Heaven", network="solana")
        dex_collector.db_manager.get_dex_by_id.return_value = mock_dex
        
        dex_info = await dex_collector.get_dex_info("heaven")
        
        assert dex_info == mock_dex
        dex_collector.db_manager.get_dex_by_id.assert_called_once_with("heaven")
    
    @pytest.mark.asyncio
    async def test_get_dex_info_not_found(self, dex_collector):
        """Test getting DEX info when DEX is not found."""
        dex_collector.db_manager.get_dex_by_id.return_value = None
        
        dex_info = await dex_collector.get_dex_info("nonexistent")
        
        assert dex_info is None
    
    @pytest.mark.asyncio
    async def test_get_dex_info_database_error(self, dex_collector):
        """Test handling database errors when getting DEX info."""
        dex_collector.db_manager.get_dex_by_id.side_effect = Exception("Database error")
        
        dex_info = await dex_collector.get_dex_info("heaven")
        
        assert dex_info is None


class TestDEXMonitoringCollectorIntegration:
    """Integration tests using mock client with CSV fixture data."""
    
    @pytest.mark.asyncio
    async def test_collect_with_mock_client(self, mock_config, mock_db_manager):
        """Test collection using mock client with CSV fixture data."""
        collector = DEXMonitoringCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            network="solana",
            target_dexes=["heaven", "pumpswap"],
            use_mock=True
        )
        
        result = await collector.collect()
        
        # Should succeed with mock data
        assert result.success is True
        assert result.records_collected == 2
        
        # Verify database was called
        mock_db_manager.store_dex_data.assert_called_once()
        
        # Check that processed DEX records include target DEXes
        call_args = mock_db_manager.store_dex_data.call_args[0][0]
        dex_ids = [dex.id for dex in call_args]
        assert "heaven" in dex_ids
        assert "pumpswap" in dex_ids
    
    @pytest.mark.asyncio
    async def test_collect_with_error_handling(self, mock_config, mock_db_manager):
        """Test collection with error handling wrapper."""
        collector = DEXMonitoringCollector(
            config=mock_config,
            db_manager=mock_db_manager,
            use_mock=True
        )
        
        result = await collector.collect_with_error_handling()
        
        assert isinstance(result, CollectionResult)
        assert result.collector_type == "dex_monitoring_solana"