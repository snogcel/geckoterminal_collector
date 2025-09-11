"""
Unit tests for collectors using enhanced infrastructure.

Tests that all collectors properly integrate with EnhancedRateLimiter,
DataTypeNormalizer, and EnhancedDatabaseManager.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from gecko_terminal_collector.collectors.base import BaseDataCollector
from gecko_terminal_collector.collectors.dex_monitoring import DEXMonitoringCollector
from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
from gecko_terminal_collector.collectors.trade_collector import TradeCollector
from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
from gecko_terminal_collector.utils.enhanced_rate_limiter import EnhancedRateLimiter
from gecko_terminal_collector.utils.data_normalizer import DataTypeNormalizer
from gecko_terminal_collector.models.core import CollectionResult, ValidationResult


@pytest.fixture
def mock_config():
    """Create a mock collection configuration."""
    config = MagicMock(spec=CollectionConfig)
    config.dexes = {'network': 'solana'}
    config.timeframes = {
        'supported': ['1h', '4h', '1d'],
        'ohlcv_default': '1h'
    }
    config.api = MagicMock()
    config.error_handling = MagicMock()
    config.error_handling.max_retries = 3
    config.error_handling.backoff_factor = 2.0
    return config


@pytest.fixture
def mock_enhanced_db_manager():
    """Create a mock enhanced database manager."""
    db_manager = AsyncMock(spec=EnhancedDatabaseManager)
    db_manager.store_collection_run = AsyncMock()
    db_manager.get_watchlist_pools = AsyncMock(return_value=['pool1', 'pool2'])
    return db_manager


@pytest.fixture
def mock_rate_limiter():
    """Create a mock enhanced rate limiter."""
    rate_limiter = AsyncMock(spec=EnhancedRateLimiter)
    rate_limiter.acquire = AsyncMock()
    rate_limiter.handle_rate_limit_response = MagicMock()
    return rate_limiter


@pytest.fixture
def mock_data_normalizer():
    """Create a mock data normalizer."""
    normalizer = MagicMock(spec=DataTypeNormalizer)
    normalizer.normalize_response_data = MagicMock(return_value=[{'id': 'test'}])
    normalizer.validate_expected_structure = MagicMock(
        return_value=ValidationResult(is_valid=True, errors=[], warnings=[])
    )
    return normalizer


class TestBaseCollectorEnhancedIntegration:
    """Test base collector integration with enhanced infrastructure."""
    
    @pytest.mark.asyncio
    async def test_base_collector_initialization_with_enhanced_components(
        self, mock_config, mock_enhanced_db_manager, mock_rate_limiter
    ):
        """Test that base collector properly initializes enhanced components."""
        
        class TestCollector(BaseDataCollector):
            def get_collection_key(self):
                return "test_collector"
            
            async def collect(self):
                return CollectionResult(
                    success=True,
                    records_collected=1,
                    errors=[],
                    collection_time=datetime.now(),
                    collector_type="test_collector"
                )
        
        collector = TestCollector(
            config=mock_config,
            db_manager=mock_enhanced_db_manager,
            rate_limiter=mock_rate_limiter
        )
        
        # Verify enhanced components are initialized
        assert collector.rate_limiter is mock_rate_limiter
        assert isinstance(collector.data_normalizer, DataTypeNormalizer)
        assert collector.db_manager is mock_enhanced_db_manager
    
    @pytest.mark.asyncio
    async def test_make_api_request_uses_rate_limiter(
        self, mock_config, mock_enhanced_db_manager, mock_rate_limiter
    ):
        """Test that make_api_request properly uses rate limiter."""
        
        class TestCollector(BaseDataCollector):
            def get_collection_key(self):
                return "test_collector"
            
            async def collect(self):
                return CollectionResult(
                    success=True,
                    records_collected=1,
                    errors=[],
                    collection_time=datetime.now(),
                    collector_type="test_collector"
                )
        
        collector = TestCollector(
            config=mock_config,
            db_manager=mock_enhanced_db_manager,
            rate_limiter=mock_rate_limiter
        )
        
        # Mock API function
        mock_api_func = AsyncMock(return_value={'data': 'test'})
        
        # Call make_api_request
        result = await collector.make_api_request(mock_api_func, 'arg1', kwarg1='value1')
        
        # Verify rate limiter was called
        mock_rate_limiter.acquire.assert_called_once()
        mock_api_func.assert_called_once_with('arg1', kwarg1='value1')
        assert result == {'data': 'test'}
    
    @pytest.mark.asyncio
    async def test_make_api_request_handles_rate_limit_response(
        self, mock_config, mock_enhanced_db_manager, mock_rate_limiter
    ):
        """Test that make_api_request handles 429 responses properly."""
        
        class TestCollector(BaseDataCollector):
            def get_collection_key(self):
                return "test_collector"
            
            async def collect(self):
                return CollectionResult(
                    success=True,
                    records_collected=1,
                    errors=[],
                    collection_time=datetime.now(),
                    collector_type="test_collector"
                )
        
        collector = TestCollector(
            config=mock_config,
            db_manager=mock_enhanced_db_manager,
            rate_limiter=mock_rate_limiter
        )
        
        # Mock API function that raises 429 error
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        
        mock_error = Exception("Rate limited")
        mock_error.response = mock_response
        
        mock_api_func = AsyncMock(side_effect=mock_error)
        
        # Call make_api_request and expect it to raise
        with pytest.raises(Exception):
            await collector.make_api_request(mock_api_func)
        
        # Verify rate limiter handled the response
        mock_rate_limiter.handle_rate_limit_response.assert_called_once_with({'Retry-After': '60'})
    
    @pytest.mark.asyncio
    async def test_collect_with_error_handling_stores_metadata(
        self, mock_config, mock_enhanced_db_manager, mock_rate_limiter
    ):
        """Test that collect_with_error_handling stores collection metadata."""
        
        class TestCollector(BaseDataCollector):
            def get_collection_key(self):
                return "test_collector"
            
            async def collect(self):
                return CollectionResult(
                    success=True,
                    records_collected=5,
                    errors=[],
                    collection_time=datetime.now(),
                    collector_type="test_collector"
                )
        
        collector = TestCollector(
            config=mock_config,
            db_manager=mock_enhanced_db_manager,
            rate_limiter=mock_rate_limiter
        )
        
        # Mock error handler
        collector.error_handler = AsyncMock()
        collector.error_handler.with_retry = AsyncMock(
            return_value=CollectionResult(
                success=True,
                records_collected=5,
                errors=[],
                collection_time=datetime.now(),
                collector_type="test_collector"
            )
        )
        
        # Call collect_with_error_handling
        result = await collector.collect_with_error_handling()
        
        # Verify metadata was stored
        mock_enhanced_db_manager.store_collection_run.assert_called_once()
        assert result.success is True
        assert result.records_collected == 5


class TestDEXMonitoringCollectorEnhanced:
    """Test DEX monitoring collector with enhanced infrastructure."""
    
    @pytest.mark.asyncio
    async def test_dex_collector_uses_enhanced_infrastructure(
        self, mock_config, mock_enhanced_db_manager, mock_rate_limiter
    ):
        """Test that DEX collector properly uses enhanced infrastructure."""
        
        collector = DEXMonitoringCollector(
            config=mock_config,
            db_manager=mock_enhanced_db_manager,
            rate_limiter=mock_rate_limiter
        )
        
        # Mock client and API response
        mock_client = AsyncMock()
        mock_client.get_dexes_by_network = AsyncMock(return_value=[{'id': 'heaven'}, {'id': 'pumpswap'}])
        collector._client = mock_client
        
        # Mock data normalizer
        collector.data_normalizer.normalize_response_data = MagicMock(
            return_value=[{'id': 'heaven'}, {'id': 'pumpswap'}]
        )
        
        # Mock validation
        collector.validate_data = AsyncMock(
            return_value=ValidationResult(is_valid=True, errors=[], warnings=[])
        )
        
        # Mock database operations
        mock_enhanced_db_manager.store_dex_data = AsyncMock()
        
        # Call collect
        result = await collector.collect()
        
        # Verify rate limiter was used
        mock_rate_limiter.acquire.assert_called()
        
        # Verify data normalizer was used
        collector.data_normalizer.normalize_response_data.assert_called_once()


class TestOHLCVCollectorEnhanced:
    """Test OHLCV collector with enhanced infrastructure."""
    
    @pytest.mark.asyncio
    async def test_ohlcv_collector_uses_rate_limiter_for_api_calls(
        self, mock_config, mock_enhanced_db_manager, mock_rate_limiter
    ):
        """Test that OHLCV collector uses rate limiter for API calls."""
        
        collector = OHLCVCollector(
            config=mock_config,
            db_manager=mock_enhanced_db_manager,
            rate_limiter=mock_rate_limiter
        )
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.get_ohlcv_data = AsyncMock(return_value={'data': {'attributes': {'ohlcv_list': []}}})
        collector._client = mock_client
        
        # Mock database operations
        mock_enhanced_db_manager.get_watchlist_pools = AsyncMock(return_value=['pool1'])
        
        # Call collect
        result = await collector.collect()
        
        # Verify rate limiter was used for API calls
        assert mock_rate_limiter.acquire.call_count > 0


class TestTopPoolsCollectorEnhanced:
    """Test top pools collector with enhanced infrastructure."""
    
    @pytest.mark.asyncio
    async def test_top_pools_collector_uses_enhanced_infrastructure(
        self, mock_config, mock_enhanced_db_manager, mock_rate_limiter
    ):
        """Test that top pools collector properly uses enhanced infrastructure."""
        
        collector = TopPoolsCollector(
            config=mock_config,
            db_manager=mock_enhanced_db_manager,
            rate_limiter=mock_rate_limiter
        )
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.get_top_pools_by_network_dex = AsyncMock(return_value=[{'id': 'pool1'}])
        collector._client = mock_client
        
        # Mock validation
        collector.validate_data = AsyncMock(
            return_value=ValidationResult(is_valid=True, errors=[], warnings=[])
        )
        
        # Mock database operations
        mock_enhanced_db_manager.store_pools_data = AsyncMock()
        
        # Call collect
        result = await collector.collect()
        
        # Verify rate limiter was used
        mock_rate_limiter.acquire.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])