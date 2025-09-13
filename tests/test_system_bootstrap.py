"""
Tests for the SystemBootstrap class.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from gecko_terminal_collector.utils.bootstrap import (
    SystemBootstrap,
    BootstrapResult,
    BootstrapProgress,
    BootstrapError
)
from gecko_terminal_collector.config.models import CollectionConfig, DiscoveryConfig
from gecko_terminal_collector.database.models import DEX as DEXModel, Pool as PoolModel, Token as TokenModel
from gecko_terminal_collector.models.core import Pool, Token


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = CollectionConfig()
    config.discovery = DiscoveryConfig(
        enabled=True,
        target_networks=["solana"],
        min_volume_usd=Decimal("1000"),
        max_pools_per_dex=100
    )
    return config


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    db_manager = AsyncMock()
    db_manager.initialize = AsyncMock()
    db_manager.store_dex_data = AsyncMock(return_value=2)
    db_manager.store_pools = AsyncMock(return_value=5)
    db_manager.store_tokens = AsyncMock(return_value=10)
    return db_manager


@pytest.fixture
def mock_client():
    """Create a mock API client."""
    client = AsyncMock()
    client.get_networks = AsyncMock(return_value={"data": [{"id": "solana"}]})
    return client


@pytest.fixture
def mock_discovery_engine():
    """Create a mock discovery engine."""
    engine = AsyncMock()
    
    # Mock DEX discovery
    mock_dexes = [
        DEXModel(id="heaven", name="Heaven", network="solana"),
        DEXModel(id="pumpswap", name="PumpSwap", network="solana")
    ]
    engine.discover_dexes = AsyncMock(return_value=mock_dexes)
    
    # Mock pool discovery
    mock_pools = [
        Pool(
            id="solana_pool1",
            address="addr1",
            name="Pool 1",
            dex_id="heaven",
            base_token_id="solana_token1",
            quote_token_id="solana_token2",
            reserve_usd=Decimal("5000"),
            created_at=datetime.now()
        ),
        Pool(
            id="solana_pool2",
            address="addr2",
            name="Pool 2",
            dex_id="pumpswap",
            base_token_id="solana_token3",
            quote_token_id="solana_token4",
            reserve_usd=Decimal("10000"),
            created_at=datetime.now()
        )
    ]
    engine.discover_pools = AsyncMock(return_value=mock_pools)
    
    # Mock token extraction
    mock_tokens = [
        Token(
            id="solana_token1",
            address="token1_addr",
            name="Token 1",
            symbol="TK1",
            decimals=9,
            network="solana"
        ),
        Token(
            id="solana_token2",
            address="token2_addr",
            name="Token 2",
            symbol="TK2",
            decimals=6,
            network="solana"
        )
    ]
    engine.extract_tokens = AsyncMock(return_value=mock_tokens)
    
    return engine


@pytest.fixture
def bootstrap_system(mock_config, mock_db_manager, mock_client, mock_discovery_engine):
    """Create a SystemBootstrap instance for testing."""
    return SystemBootstrap(
        config=mock_config,
        db_manager=mock_db_manager,
        client=mock_client,
        discovery_engine=mock_discovery_engine
    )


class TestSystemBootstrap:
    """Test cases for SystemBootstrap class."""
    
    @pytest.mark.asyncio
    async def test_successful_bootstrap(self, bootstrap_system, mock_discovery_engine):
        """Test successful complete bootstrap process."""
        result = await bootstrap_system.bootstrap()
        
        assert result.success is True
        assert result.dexes_discovered == 2
        assert result.pools_discovered == 2
        assert result.tokens_discovered == 2
        assert result.execution_time_seconds >= 0
        assert len(result.errors) == 0
        
        # Verify all phases were called
        mock_discovery_engine.discover_dexes.assert_called_once()
        mock_discovery_engine.discover_pools.assert_called_once()
        mock_discovery_engine.extract_tokens.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bootstrap_with_invalid_config(self, mock_db_manager, mock_client):
        """Test bootstrap with invalid configuration."""
        # Create invalid config (no target networks)
        invalid_config = CollectionConfig()
        invalid_config.discovery = DiscoveryConfig(
            enabled=True,
            target_networks=[]  # Invalid - empty
        )
        
        bootstrap = SystemBootstrap(
            config=invalid_config,
            db_manager=mock_db_manager,
            client=mock_client
        )
        
        result = await bootstrap.bootstrap()
        
        assert result.success is False
        assert len(result.errors) > 0
        assert "target network" in result.errors[0].lower()
    
    @pytest.mark.asyncio
    async def test_bootstrap_with_discovery_disabled(self, mock_db_manager, mock_client):
        """Test bootstrap with discovery disabled."""
        config = CollectionConfig()
        config.discovery = DiscoveryConfig(enabled=False)
        
        bootstrap = SystemBootstrap(
            config=config,
            db_manager=mock_db_manager,
            client=mock_client
        )
        
        result = await bootstrap.bootstrap()
        
        assert result.success is False
        assert len(result.errors) > 0
        assert "discovery is disabled" in result.errors[0].lower()
    
    @pytest.mark.asyncio
    async def test_bootstrap_with_database_failure(self, mock_config, mock_client):
        """Test bootstrap with database initialization failure."""
        # Mock database manager that fails initialization
        failing_db = AsyncMock()
        failing_db.initialize = AsyncMock(side_effect=Exception("Database connection failed"))
        
        bootstrap = SystemBootstrap(
            config=mock_config,
            db_manager=failing_db,
            client=mock_client
        )
        
        result = await bootstrap.bootstrap()
        
        assert result.success is False
        assert len(result.errors) > 0
        assert "database initialization failed" in result.errors[0].lower()
    
    @pytest.mark.asyncio
    async def test_bootstrap_with_api_failure(self, mock_config, mock_db_manager):
        """Test bootstrap with API connectivity failure."""
        # Mock client that fails connectivity test
        failing_client = AsyncMock()
        failing_client.get_networks = AsyncMock(side_effect=Exception("API connection failed"))
        
        bootstrap = SystemBootstrap(
            config=mock_config,
            db_manager=mock_db_manager,
            client=failing_client
        )
        
        result = await bootstrap.bootstrap()
        
        assert result.success is False
        assert len(result.errors) > 0
        assert "api connectivity test failed" in result.errors[0].lower()
    
    @pytest.mark.asyncio
    async def test_bootstrap_with_no_dexes_discovered(self, bootstrap_system, mock_discovery_engine):
        """Test bootstrap when no DEXes are discovered."""
        # Mock discovery engine to return no DEXes
        mock_discovery_engine.discover_dexes = AsyncMock(return_value=[])
        
        result = await bootstrap_system.bootstrap()
        
        assert result.success is False
        assert result.dexes_discovered == 0
        assert len(result.errors) > 0
        assert "no dexes discovered" in result.errors[0].lower()
    
    @pytest.mark.asyncio
    async def test_bootstrap_with_no_pools_discovered(self, bootstrap_system, mock_discovery_engine):
        """Test bootstrap when no pools are discovered."""
        # Mock discovery engine to return no pools
        mock_discovery_engine.discover_pools = AsyncMock(return_value=[])
        
        result = await bootstrap_system.bootstrap()
        
        # Should still succeed with warnings
        assert result.success is True
        assert result.pools_discovered == 0
        assert result.tokens_discovered == 0
        assert len(result.warnings) > 0
    
    @pytest.mark.asyncio
    async def test_bootstrap_with_storage_failure(self, bootstrap_system, mock_db_manager):
        """Test bootstrap with database storage failure."""
        # Mock database manager to fail DEX storage
        mock_db_manager.store_dex_data = AsyncMock(side_effect=Exception("Storage failed"))
        
        result = await bootstrap_system.bootstrap()
        
        assert result.success is False
        assert len(result.errors) > 0
        assert "failed to store dex data" in result.errors[0].lower()
    
    @pytest.mark.asyncio
    async def test_progress_tracking(self, bootstrap_system):
        """Test that progress tracking works correctly."""
        progress_updates = []
        
        def progress_callback(progress: BootstrapProgress):
            progress_updates.append({
                'phase': progress.phase,
                'overall_progress': progress.overall_progress,
                'current_phase': progress.current_phase
            })
        
        bootstrap_system.progress_callback = progress_callback
        
        result = await bootstrap_system.bootstrap()
        
        assert result.success is True
        assert len(progress_updates) > 0
        
        # Check that progress increases over time
        for i in range(1, len(progress_updates)):
            assert progress_updates[i]['overall_progress'] >= progress_updates[i-1]['overall_progress']
        
        # Check that final progress is 100%
        assert progress_updates[-1]['overall_progress'] == 100.0
    
    @pytest.mark.asyncio
    async def test_dex_validation(self, bootstrap_system):
        """Test DEX data validation."""
        # Test valid DEX
        valid_dex = DEXModel(id="test", name="Test DEX", network="solana")
        assert await bootstrap_system._validate_dex_data(valid_dex) is True
        
        # Test invalid DEX (missing ID)
        invalid_dex = DEXModel(id="", name="Test DEX", network="solana")
        assert await bootstrap_system._validate_dex_data(invalid_dex) is False
        
        # Test invalid DEX (wrong network)
        wrong_network_dex = DEXModel(id="test", name="Test DEX", network="ethereum")
        assert await bootstrap_system._validate_dex_data(wrong_network_dex) is False
    
    @pytest.mark.asyncio
    async def test_pool_validation(self, bootstrap_system):
        """Test pool data validation."""
        dex_ids = ["heaven", "pumpswap"]
        
        # Test valid pool
        valid_pool = Pool(
            id="test_pool",
            address="test_addr",
            name="Test Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000"),
            created_at=datetime.now()
        )
        assert await bootstrap_system._validate_pool_data(valid_pool, dex_ids) is True
        
        # Test invalid pool (missing ID)
        invalid_pool = Pool(
            id="",
            address="test_addr",
            name="Test Pool",
            dex_id="heaven",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000"),
            created_at=datetime.now()
        )
        assert await bootstrap_system._validate_pool_data(invalid_pool, dex_ids) is False
        
        # Test invalid pool (non-existent DEX)
        wrong_dex_pool = Pool(
            id="test_pool",
            address="test_addr",
            name="Test Pool",
            dex_id="nonexistent",
            base_token_id="token1",
            quote_token_id="token2",
            reserve_usd=Decimal("1000"),
            created_at=datetime.now()
        )
        assert await bootstrap_system._validate_pool_data(wrong_dex_pool, dex_ids) is False
    
    @pytest.mark.asyncio
    async def test_token_validation(self, bootstrap_system):
        """Test token data validation."""
        # Test valid token
        valid_token = Token(
            id="test_token",
            address="test_addr",
            name="Test Token",
            symbol="TEST",
            decimals=9,
            network="solana"
        )
        assert await bootstrap_system._validate_token_data(valid_token) is True
        
        # Test invalid token (missing ID)
        invalid_token = Token(
            id="",
            address="test_addr",
            name="Test Token",
            symbol="TEST",
            decimals=9,
            network="solana"
        )
        assert await bootstrap_system._validate_token_data(invalid_token) is False
        
        # Test invalid token (wrong network)
        wrong_network_token = Token(
            id="test_token",
            address="test_addr",
            name="Test Token",
            symbol="TEST",
            decimals=9,
            network="ethereum"
        )
        assert await bootstrap_system._validate_token_data(wrong_network_token) is False
        
        # Test invalid token (invalid decimals)
        invalid_decimals_token = Token(
            id="test_token",
            address="test_addr",
            name="Test Token",
            symbol="TEST",
            decimals=50,  # Too high
            network="solana"
        )
        assert await bootstrap_system._validate_token_data(invalid_decimals_token) is False
    
    @pytest.mark.asyncio
    async def test_bootstrap_error_handling(self, bootstrap_system):
        """Test BootstrapError handling and recovery."""
        # Initialize start time
        bootstrap_system.progress.start_time = datetime.now()
        
        # Test recoverable error
        recoverable_error = BootstrapError("Test error", "test_phase", recoverable=True)
        result = await bootstrap_system._handle_bootstrap_error(recoverable_error)
        
        assert result.success is False
        assert len(result.errors) > 0
        assert len(result.recovery_actions) > 0
        
        # Test non-recoverable error
        non_recoverable_error = BootstrapError("Critical error", "test_phase", recoverable=False)
        result = await bootstrap_system._handle_bootstrap_error(non_recoverable_error)
        
        assert result.success is False
        assert len(result.errors) > 0
    
    @pytest.mark.asyncio
    async def test_progress_calculation(self, bootstrap_system):
        """Test progress calculation accuracy."""
        # Initialize start time
        bootstrap_system.progress.start_time = datetime.now()
        
        # Test progress update
        await bootstrap_system._update_progress("Test phase", 2, 50.0)
        
        progress = bootstrap_system.progress
        assert progress.current_phase == 2
        assert progress.phase_progress == 50.0
        assert progress.overall_progress == 37.5  # (1 * 25) + (0.5 * 25) = 37.5%
        assert progress.phase == "Test phase"
    
    def test_bootstrap_error_creation(self):
        """Test BootstrapError creation and properties."""
        error = BootstrapError("Test message", "test_phase", recoverable=True)
        
        assert str(error) == "Test message"
        assert error.phase == "test_phase"
        assert error.recoverable is True
        
        # Test default recoverable value
        error2 = BootstrapError("Test message", "test_phase")
        assert error2.recoverable is True
    
    def test_bootstrap_result_creation(self):
        """Test BootstrapResult creation and default values."""
        result = BootstrapResult(success=True)
        
        assert result.success is True
        assert result.dexes_discovered == 0
        assert result.pools_discovered == 0
        assert result.tokens_discovered == 0
        assert result.execution_time_seconds == 0.0
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert len(result.recovery_actions) == 0
    
    def test_bootstrap_progress_creation(self):
        """Test BootstrapProgress creation and default values."""
        progress = BootstrapProgress()
        
        assert progress.phase == "initializing"
        assert progress.total_phases == 4
        assert progress.current_phase == 0
        assert progress.phase_progress == 0.0
        assert progress.overall_progress == 0.0
        assert progress.dexes_discovered == 0
        assert progress.pools_discovered == 0
        assert progress.tokens_discovered == 0
        assert len(progress.errors) == 0
        assert len(progress.warnings) == 0
        assert progress.start_time is None
        assert progress.phase_start_time is None
        assert progress.estimated_completion is None