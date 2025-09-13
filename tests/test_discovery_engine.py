"""
Unit tests for DiscoveryEngine.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from gecko_terminal_collector.collectors.discovery_engine import DiscoveryEngine, DiscoveryResult
from gecko_terminal_collector.config.models import CollectionConfig, DiscoveryConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.database.models import DEX, Pool, Token
from gecko_terminal_collector.clients import BaseGeckoClient
from gecko_terminal_collector.utils.activity_scorer import ActivityScorer


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = CollectionConfig()
    config.discovery = DiscoveryConfig(
        enabled=True,
        min_volume_usd=Decimal("1000"),
        max_pools_per_dex=10,
        activity_threshold=Decimal("25"),
        target_networks=["solana"]
    )
    return config


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    db_manager = AsyncMock()
    
    # Mock DEX operations
    db_manager.get_dex_by_id.return_value = None
    db_manager.store_dex.return_value = None
    
    # Mock Pool operations
    db_manager.get_pool_by_id.return_value = None
    db_manager.store_pool.return_value = None
    
    # Mock Token operations
    db_manager.get_token_by_id.return_value = None
    db_manager.store_token.return_value = None
    
    return db_manager


@pytest.fixture
def mock_client():
    """Create a mock GeckoTerminal client."""
    client = AsyncMock()
    
    # Mock DEX discovery
    client.get_dexes_by_network.return_value = [
        {
            "id": "test_dex",
            "type": "dex",
            "attributes": {
                "name": "Test DEX"
            }
        }
    ]
    
    # Mock pool discovery
    client.get_top_pools_by_network_dex.return_value = {
        "data": [
            {
                "id": "test_pool_1",
                "type": "pool",
                "attributes": {
                    "name": "Test Pool 1",
                    "address": "test_address_1",
                    "reserve_in_usd": "5000.0",
                    "volume_usd": {"h24": "2000.0"},
                    "transactions": {"h24": 50}
                },
                "relationships": {
                    "base_token": {"data": {"id": "solana_token1"}},
                    "quote_token": {"data": {"id": "solana_token2"}}
                }
            }
        ]
    }
    
    # Mock token discovery
    client.get_specific_token_on_network.return_value = {
        "data": {
            "id": "solana_token1",
            "type": "token",
            "attributes": {
                "address": "token1_address",
                "name": "Test Token 1",
                "symbol": "TEST1",
                "decimals": 9
            }
        }
    }
    
    return client


@pytest.fixture
def mock_activity_scorer():
    """Create a mock activity scorer."""
    scorer = MagicMock()
    scorer.should_include_pool.return_value = True
    scorer.calculate_activity_score.return_value = Decimal("75.0")
    scorer.get_collection_priority.return_value = MagicMock(value="high")
    return scorer


@pytest.fixture
def discovery_engine(mock_config, mock_db_manager, mock_client, mock_activity_scorer):
    """Create a DiscoveryEngine instance for testing."""
    return DiscoveryEngine(
        config=mock_config,
        db_manager=mock_db_manager,
        client=mock_client,
        activity_scorer=mock_activity_scorer
    )


class TestDiscoveryEngine:
    """Test cases for DiscoveryEngine."""
    
    @pytest.mark.asyncio
    async def test_discover_dexes_success(self, discovery_engine, mock_client, mock_db_manager):
        """Test successful DEX discovery."""
        # Act
        dexes = await discovery_engine.discover_dexes()
        
        # Assert
        assert len(dexes) == 1
        assert dexes[0].id == "test_dex"
        assert dexes[0].name == "Test DEX"
        assert dexes[0].network == "solana"
        
        # Verify API was called
        mock_client.get_dexes_by_network.assert_called_once_with("solana")
        
        # Verify DEX was stored
        mock_db_manager.store_dex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_discover_dexes_empty_response(self, discovery_engine, mock_client):
        """Test DEX discovery with empty API response."""
        # Arrange
        mock_client.get_dexes_by_network.return_value = []
        
        # Act
        dexes = await discovery_engine.discover_dexes()
        
        # Assert
        assert len(dexes) == 0
    
    @pytest.mark.asyncio
    async def test_discover_pools_success(self, discovery_engine, mock_client, mock_db_manager):
        """Test successful pool discovery."""
        # Arrange
        mock_db_manager.get_dex_by_id.return_value = DEX(
            id="test_dex",
            name="Test DEX",
            network="solana"
        )
        
        # Act
        pools = await discovery_engine.discover_pools(["test_dex"])
        
        # Assert
        assert len(pools) == 1
        assert pools[0].id == "test_pool_1"
        assert pools[0].name == "Test Pool 1"
        assert pools[0].dex_id == "test_dex"
        
        # Verify API was called
        mock_client.get_top_pools_by_network_dex.assert_called_once_with("solana", "test_dex")
        
        # Verify pool was stored
        mock_db_manager.store_pool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_tokens_success(self, discovery_engine, mock_client, mock_db_manager):
        """Test successful token extraction from pools."""
        # Arrange
        pool = Pool(
            id="test_pool_1",
            address="test_address_1",
            name="Test Pool 1",
            dex_id="test_dex",
            base_token_id="solana_token1",
            quote_token_id="solana_token2",
            reserve_usd=Decimal("5000"),
            created_at=datetime.now(),
            last_updated=datetime.now()
        )
        
        mock_db_manager.get_dex_by_id.return_value = DEX(
            id="test_dex",
            name="Test DEX",
            network="solana"
        )
        
        # Act
        tokens = await discovery_engine.extract_tokens([pool])
        
        # Assert
        assert len(tokens) == 2  # base and quote tokens
        
        # Verify tokens were stored
        assert mock_db_manager.store_token.call_count == 2
    
    @pytest.mark.asyncio
    async def test_apply_filters_success(self, discovery_engine, mock_activity_scorer):
        """Test successful pool filtering."""
        # Arrange
        pool = Pool(
            id="test_pool_1",
            address="test_address_1",
            name="Test Pool 1",
            dex_id="test_dex",
            base_token_id="solana_token1",
            quote_token_id="solana_token2",
            reserve_usd=Decimal("5000"),
            created_at=datetime.now(),
            last_updated=datetime.now()
        )
        
        # Act
        filtered_pools = await discovery_engine.apply_filters([pool])
        
        # Assert
        assert len(filtered_pools) == 1
        assert filtered_pools[0].activity_score == Decimal("75.0")
        assert filtered_pools[0].collection_priority == "high"
        assert filtered_pools[0].discovery_source == "auto"
        assert filtered_pools[0].auto_discovered_at is not None
        
        # Verify activity scorer was called
        mock_activity_scorer.should_include_pool.assert_called_once()
        mock_activity_scorer.calculate_activity_score.assert_called_once()
        mock_activity_scorer.get_collection_priority.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_apply_filters_excludes_low_activity(self, discovery_engine, mock_activity_scorer):
        """Test that pools with low activity are filtered out."""
        # Arrange
        pool = Pool(
            id="test_pool_1",
            address="test_address_1",
            name="Test Pool 1",
            dex_id="test_dex",
            base_token_id="solana_token1",
            quote_token_id="solana_token2",
            reserve_usd=Decimal("100"),  # Low reserve
            created_at=datetime.now(),
            last_updated=datetime.now()
        )
        
        mock_activity_scorer.should_include_pool.return_value = False
        
        # Act
        filtered_pools = await discovery_engine.apply_filters([pool])
        
        # Assert
        assert len(filtered_pools) == 0
    
    @pytest.mark.asyncio
    async def test_bootstrap_system_success(self, discovery_engine, mock_client, mock_db_manager):
        """Test successful system bootstrap."""
        # Arrange
        mock_db_manager.get_dex_by_id.return_value = DEX(
            id="test_dex",
            name="Test DEX",
            network="solana"
        )
        
        # Act
        result = await discovery_engine.bootstrap_system()
        
        # Assert
        assert result.success is True
        assert result.dexes_discovered == 1
        assert result.pools_discovered == 1
        assert result.tokens_discovered == 2
        assert result.execution_time_seconds >= 0
        assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_bootstrap_system_no_dexes(self, discovery_engine, mock_client):
        """Test bootstrap failure when no DEXes are discovered."""
        # Arrange
        mock_client.get_dexes_by_network.return_value = []
        
        # Act
        result = await discovery_engine.bootstrap_system()
        
        # Assert
        assert result.success is False
        assert result.dexes_discovered == 0
        assert len(result.errors) > 0
        assert "No DEXes discovered" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_bootstrap_system_api_error(self, discovery_engine, mock_client):
        """Test bootstrap handling of API errors."""
        # Arrange
        mock_client.get_dexes_by_network.side_effect = Exception("API Error")
        
        # Act
        result = await discovery_engine.bootstrap_system()
        
        # Assert
        assert result.success is False
        assert len(result.errors) > 0
        assert "No DEXes discovered" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_process_dex_data_existing_dex(self, discovery_engine, mock_db_manager):
        """Test processing DEX data when DEX already exists."""
        # Arrange
        existing_dex = DEX(
            id="test_dex",
            name="Existing DEX",
            network="solana"
        )
        mock_db_manager.get_dex_by_id.return_value = existing_dex
        
        dex_data = {
            "id": "test_dex",
            "attributes": {"name": "Test DEX"}
        }
        
        # Act
        result = await discovery_engine._process_dex_data(dex_data, "solana")
        
        # Assert
        assert result == existing_dex
        mock_db_manager.store_dex.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_pool_data_existing_pool(self, discovery_engine, mock_db_manager):
        """Test processing pool data when pool already exists."""
        # Arrange
        existing_pool = Pool(
            id="test_pool_1",
            address="existing_address",
            name="Existing Pool",
            dex_id="test_dex",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000"),
            created_at=datetime.now(),
            last_updated=datetime.now()
        )
        mock_db_manager.get_pool_by_id.return_value = existing_pool
        
        pool_data = {
            "id": "test_pool_1",
            "attributes": {
                "name": "Test Pool 1",
                "address": "test_address_1"
            },
            "relationships": {
                "base_token": {"data": {"id": "token1"}},
                "quote_token": {"data": {"id": "token2"}}
            }
        }
        
        # Act
        result = await discovery_engine._process_pool_data(pool_data, "test_dex")
        
        # Assert
        assert result == existing_pool
        mock_db_manager.store_pool.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__])