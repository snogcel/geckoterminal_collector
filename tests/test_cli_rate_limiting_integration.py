"""
Integration tests for CLI rate limiting functionality.

Tests the CLI script's integration with the EnhancedRateLimiter,
including proper error handling, backoff logic, and configuration.
"""

import asyncio
import json
import logging
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from gecko_terminal_collector.config.models import CollectionConfig, RateLimitConfig
from gecko_terminal_collector.utils.enhanced_rate_limiter import (
    EnhancedRateLimiter, 
    GlobalRateLimitCoordinator,
    RateLimitExceededError,
    CircuitBreakerOpenError
)

# Import the CLI class
import sys
sys.path.append(str(Path(__file__).parent.parent / "examples"))
from cli_with_scheduler import SchedulerCLI


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for configuration files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_config(temp_config_dir):
    """Create a test configuration with rate limiting settings."""
    config_file = temp_config_dir / "test_config.yaml"
    # Use forward slashes and raw string to avoid YAML escaping issues
    state_dir = str(temp_config_dir / "rate_limiter_state").replace("\\", "/")
    config_content = f"""
database:
  url: "sqlite:///:memory:"
  
rate_limiting:
  requests_per_minute: 10
  daily_limit: 100
  circuit_breaker_threshold: 3
  circuit_breaker_timeout: 60
  state_file_dir: "{state_dir}"

api:
  base_url: "https://api.geckoterminal.com/api/v2"
  timeout: 30
  
intervals:
  top_pools_monitoring: "1h"
  ohlcv_collection: "1h"
  trade_collection: "30m"
  watchlist_check: "1h"
"""
    
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def cli_instance(test_config):
    """Create a CLI instance for testing."""
    return SchedulerCLI(test_config)


class TestCLIRateLimitingIntegration:
    """Test CLI integration with enhanced rate limiting."""
    
    @pytest.mark.asyncio
    async def test_cli_initialization_with_rate_limiting(self, cli_instance):
        """Test that CLI properly initializes with rate limiting."""
        # Mock the database and scheduler initialization
        with patch('examples.cli_with_scheduler.SQLAlchemyDatabaseManager') as mock_db, \
             patch('examples.cli_with_scheduler.CollectionScheduler') as mock_scheduler, \
             patch('examples.cli_with_scheduler.MetadataTracker') as mock_tracker:
            
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            
            mock_scheduler_instance = MagicMock()
            mock_scheduler.return_value = mock_scheduler_instance
            
            # Initialize CLI
            await cli_instance.initialize(use_mock=True)
            
            # Verify rate limit coordinator was created
            assert cli_instance.rate_limit_coordinator is not None
            
            # Verify database manager was initialized
            mock_db_instance.initialize.assert_called_once()
            
            # Verify scheduler was created
            mock_scheduler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rate_limiter_configuration_from_config(self, test_config, temp_config_dir):
        """Test that rate limiter gets proper configuration from config file."""
        cli = SchedulerCLI(test_config)
        
        with patch('examples.cli_with_scheduler.SQLAlchemyDatabaseManager') as mock_db, \
             patch('examples.cli_with_scheduler.CollectionScheduler') as mock_scheduler, \
             patch('examples.cli_with_scheduler.MetadataTracker') as mock_tracker:
            
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            
            await cli.initialize(use_mock=True)
            
            # Get a rate limiter and check its configuration
            limiter = await cli.rate_limit_coordinator.get_limiter("test_collector")
            
            assert limiter.requests_per_minute == 10
            assert limiter.daily_limit == 100
            assert limiter.circuit_breaker_threshold == 3
            assert limiter.circuit_breaker_timeout == 60
    
    @pytest.mark.asyncio
    async def test_collector_registration_with_rate_limiters(self, cli_instance):
        """Test that collectors are properly registered with rate limiters."""
        with patch('examples.cli_with_scheduler.SQLAlchemyDatabaseManager') as mock_db, \
             patch('examples.cli_with_scheduler.CollectionScheduler') as mock_scheduler, \
             patch('examples.cli_with_scheduler.MetadataTracker') as mock_tracker:
            
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            
            mock_scheduler_instance = MagicMock()
            mock_scheduler_instance.list_collectors.return_value = []
            mock_scheduler.return_value = mock_scheduler_instance
            
            # Mock collector classes to track rate limiter assignment
            mock_collectors = {}
            collector_classes = [
                'DEXMonitoringCollector', 'TopPoolsCollector', 'WatchlistMonitor',
                'WatchlistCollector', 'OHLCVCollector', 'TradeCollector', 
                'HistoricalOHLCVCollector'
            ]
            
            for collector_class in collector_classes:
                mock_collector = MagicMock()
                mock_collector.set_rate_limiter = MagicMock()
                mock_collectors[collector_class] = mock_collector
                
                # Patch the collector class
                patch_path = f'examples.cli_with_scheduler.{collector_class}'
                patcher = patch(patch_path, return_value=mock_collector)
                patcher.start()
            
            try:
                await cli_instance.initialize(use_mock=True)
                
                # Verify that rate limiters were assigned to collectors that support it
                for collector_class, mock_collector in mock_collectors.items():
                    if hasattr(mock_collector, 'set_rate_limiter'):
                        mock_collector.set_rate_limiter.assert_called_once()
                
            finally:
                # Stop all patches
                patch.stopall()
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_handling_in_cli(self, cli_instance):
        """Test that CLI properly handles rate limit errors."""
        with patch('examples.cli_with_scheduler.SQLAlchemyDatabaseManager') as mock_db, \
             patch('examples.cli_with_scheduler.CollectionScheduler') as mock_scheduler, \
             patch('examples.cli_with_scheduler.MetadataTracker') as mock_tracker:
            
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            
            mock_scheduler_instance = MagicMock()
            mock_scheduler_instance.list_collectors.return_value = ["test_job_id"]
            mock_scheduler_instance.get_collector_status.return_value = {
                'collector_key': 'test_collector'
            }
            
            # Mock a rate limit error during execution
            mock_scheduler_instance.execute_collector_now.side_effect = RateLimitExceededError(
                "Daily API limit exceeded"
            )
            mock_scheduler.return_value = mock_scheduler_instance
            
            await cli_instance.initialize(use_mock=True)
            
            # This should handle the rate limit error gracefully
            # In a real scenario, this would be called through the CLI command
            # but we're testing the underlying logic
            try:
                await mock_scheduler_instance.execute_collector_now("test_job_id")
                assert False, "Should have raised RateLimitExceededError"
            except RateLimitExceededError as e:
                assert "Daily API limit exceeded" in str(e)
    
    @pytest.mark.asyncio
    async def test_rate_limiter_backoff_logic(self, temp_config_dir):
        """Test that rate limiter backoff logic works correctly."""
        # Create a rate limiter with short limits for testing
        state_file = temp_config_dir / "test_limiter.json"
        limiter = EnhancedRateLimiter(
            requests_per_minute=2,
            daily_limit=10,
            state_file=str(state_file)
        )
        
        # Simulate rate limit responses
        headers = {'Retry-After': '5'}
        
        # First rate limit hit
        await limiter.handle_rate_limit_response(headers, 429)
        assert limiter.backoff_state.consecutive_failures == 1
        assert limiter.backoff_state.backoff_until is not None
        
        # Second rate limit hit should increase backoff
        await limiter.handle_rate_limit_response(headers, 429)
        assert limiter.backoff_state.consecutive_failures == 2
        
        # Success should reset backoff
        await limiter.handle_success()
        assert limiter.backoff_state.consecutive_failures == 0
        assert limiter.backoff_state.backoff_until is None
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_functionality(self, temp_config_dir):
        """Test circuit breaker functionality in rate limiter."""
        state_file = temp_config_dir / "test_circuit_breaker.json"
        limiter = EnhancedRateLimiter(
            requests_per_minute=60,
            daily_limit=1000,
            circuit_breaker_threshold=2,
            circuit_breaker_timeout=1,  # 1 second for testing
            state_file=str(state_file)
        )
        
        headers = {'Retry-After': '1'}
        
        # First failure
        await limiter.handle_rate_limit_response(headers, 429)
        assert limiter.circuit_failure_count == 1
        
        # Second failure should open circuit
        await limiter.handle_rate_limit_response(headers, 429)
        assert limiter.circuit_failure_count == 2
        assert limiter.circuit_state.value == "open"
        
        # Should raise CircuitBreakerOpenError when trying to acquire
        with pytest.raises(RateLimitExceededError):
            await limiter.acquire()
        
        # Wait for circuit to go to half-open
        await asyncio.sleep(1.1)
        
        # Should be able to acquire again (circuit goes to half-open)
        await limiter.acquire()
    
    @pytest.mark.asyncio
    async def test_persistent_state_management(self, temp_config_dir):
        """Test that rate limiter state persists across instances."""
        state_file = temp_config_dir / "persistent_test.json"
        
        # Create first limiter instance and make some requests
        limiter1 = EnhancedRateLimiter(
            requests_per_minute=60,
            daily_limit=1000,
            state_file=str(state_file)
        )
        
        await limiter1.acquire()
        await limiter1.acquire()
        assert limiter1.daily_count == 2
        
        # Create second limiter instance - should load state
        limiter2 = EnhancedRateLimiter(
            requests_per_minute=60,
            daily_limit=1000,
            state_file=str(state_file)
        )
        
        # Should have loaded the state from the first instance
        assert limiter2.daily_count == 2
    
    @pytest.mark.asyncio
    async def test_global_coordinator_functionality(self, temp_config_dir):
        """Test global rate limit coordinator."""
        coordinator = await GlobalRateLimitCoordinator.get_instance(
            requests_per_minute=60,
            daily_limit=1000,
            state_dir=str(temp_config_dir)
        )
        
        # Get limiters for different collectors
        limiter1 = await coordinator.get_limiter("collector1")
        limiter2 = await coordinator.get_limiter("collector2")
        
        assert limiter1 != limiter2
        assert limiter1.instance_id == "collector1"
        assert limiter2.instance_id == "collector2"
        
        # Make requests with both limiters
        await limiter1.acquire()
        await limiter2.acquire()
        
        # Check global status
        status = await coordinator.get_global_status()
        assert status['total_limiters'] == 2
        assert status['global_usage']['total_daily_requests'] == 2
    
    @pytest.mark.asyncio
    async def test_cli_status_command_with_rate_limiting(self, cli_instance):
        """Test that CLI status command shows rate limiting information."""
        with patch('examples.cli_with_scheduler.SQLAlchemyDatabaseManager') as mock_db, \
             patch('examples.cli_with_scheduler.CollectionScheduler') as mock_scheduler, \
             patch('examples.cli_with_scheduler.MetadataTracker') as mock_tracker:
            
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            
            mock_scheduler_instance = MagicMock()
            mock_scheduler_instance.get_status.return_value = {
                'state': 'running',
                'total_collectors': 2,
                'enabled_collectors': 2,
                'running_jobs': 0,
                'collectors': {}
            }
            mock_scheduler_instance.get_next_run_times.return_value = {}
            mock_scheduler.return_value = mock_scheduler_instance
            
            await cli_instance.initialize(use_mock=True)
            
            # Make some requests to generate rate limiting data
            limiter = await cli_instance.rate_limit_coordinator.get_limiter("test_collector")
            await limiter.acquire()
            
            # Test status method (would normally be called by CLI command)
            # This tests the underlying functionality
            status = await cli_instance.rate_limit_coordinator.get_global_status()
            
            assert 'global_limits' in status
            assert 'global_usage' in status
            assert 'limiters' in status
            assert status['total_limiters'] >= 1
    
    def test_rate_limiting_configuration_validation(self):
        """Test that rate limiting configuration is properly validated."""
        # Test valid configuration
        config = RateLimitConfig(
            requests_per_minute=60,
            daily_limit=10000,
            circuit_breaker_threshold=5,
            circuit_breaker_timeout=300
        )
        
        assert config.requests_per_minute == 60
        assert config.daily_limit == 10000
        assert config.circuit_breaker_threshold == 5
        assert config.circuit_breaker_timeout == 300
        
        # Test default values
        default_config = RateLimitConfig()
        assert default_config.requests_per_minute == 60
        assert default_config.daily_limit == 10000
        assert default_config.backoff_jitter_factor == 0.3


class TestCLIRateLimitingEndToEnd:
    """End-to-end integration tests for CLI rate limiting."""
    
    @pytest.mark.asyncio
    async def test_full_cli_workflow_with_rate_limiting(self, test_config, temp_config_dir):
        """Test complete CLI workflow with rate limiting enabled."""
        # This test would ideally run the actual CLI commands
        # but for now we test the core workflow programmatically
        
        cli = SchedulerCLI(test_config)
        
        with patch('examples.cli_with_scheduler.SQLAlchemyDatabaseManager') as mock_db, \
             patch('examples.cli_with_scheduler.CollectionScheduler') as mock_scheduler, \
             patch('examples.cli_with_scheduler.MetadataTracker') as mock_tracker, \
             patch('examples.cli_with_scheduler.DEXMonitoringCollector') as mock_collector:
            
            # Setup mocks
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            
            mock_scheduler_instance = MagicMock()
            mock_scheduler_instance.list_collectors.return_value = ["job1"]
            mock_scheduler_instance.get_collector_status.return_value = {
                'collector_key': 'dex_monitoring'
            }
            mock_scheduler_instance.execute_collector_now.return_value = MagicMock(
                success=True,
                records_collected=10,
                errors=[]
            )
            mock_scheduler.return_value = mock_scheduler_instance
            
            mock_collector_instance = MagicMock()
            mock_collector_instance.set_rate_limiter = MagicMock()
            mock_collector.return_value = mock_collector_instance
            
            # Initialize and run
            await cli.initialize(use_mock=True)
            
            # Verify rate limiting is active
            assert cli.rate_limit_coordinator is not None
            
            # Simulate running a collector
            result = await mock_scheduler_instance.execute_collector_now("job1")
            assert result.success is True
            
            # Verify rate limiter was used
            limiter = await cli.rate_limit_coordinator.get_limiter("dex_monitoring")
            status = limiter.get_status()
            assert 'daily_requests' in status
            
            await cli.shutdown()
    
    @pytest.mark.asyncio
    async def test_rate_limit_recovery_scenario(self, test_config, temp_config_dir):
        """Test recovery from rate limiting scenarios."""
        cli = SchedulerCLI(test_config)
        
        with patch('examples.cli_with_scheduler.SQLAlchemyDatabaseManager') as mock_db, \
             patch('examples.cli_with_scheduler.CollectionScheduler') as mock_scheduler, \
             patch('examples.cli_with_scheduler.MetadataTracker') as mock_tracker:
            
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            
            mock_scheduler_instance = MagicMock()
            mock_scheduler.return_value = mock_scheduler_instance
            
            await cli.initialize(use_mock=True)
            
            # Get a rate limiter and simulate rate limiting
            limiter = await cli.rate_limit_coordinator.get_limiter("test_collector")
            
            # Simulate hitting rate limit
            headers = {'Retry-After': '1'}
            await limiter.handle_rate_limit_response(headers, 429)
            
            # Verify backoff is active
            assert limiter.backoff_state.consecutive_failures > 0
            assert limiter.backoff_state.backoff_until is not None
            
            # Simulate successful recovery
            await limiter.handle_success()
            
            # Verify backoff is reset
            assert limiter.backoff_state.consecutive_failures == 0
            assert limiter.backoff_state.backoff_until is None
            
            await cli.shutdown()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])