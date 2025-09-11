#!/usr/bin/env python3
"""
Demo script to test CLI rate limiting functionality.

This script demonstrates the enhanced rate limiting features
integrated into the CLI scheduler.
"""

import asyncio
import logging
import tempfile
import yaml
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_cli_rate_limiting():
    """Demonstrate CLI rate limiting functionality."""
    logger.info("Starting CLI rate limiting demo...")
    
    # Create temporary config file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_file = temp_path / "demo_config.yaml"
        state_dir = temp_path / "rate_limiter_state"
        
        # Create demo configuration
        config_content = {
            'database': {
                'url': 'sqlite:///:memory:'
            },
            'rate_limiting': {
                'requests_per_minute': 5,  # Low limit for demo
                'daily_limit': 100,  # Minimum allowed by validation
                'circuit_breaker_threshold': 3,
                'circuit_breaker_timeout': 30,  # Minimum allowed by validation
                'state_file_dir': str(state_dir)
            },
            'api': {
                'base_url': 'https://api.geckoterminal.com/api/v2',
                'timeout': 30
            },
            'intervals': {
                'top_pools_monitoring': '1h',
                'ohlcv_collection': '1h',
                'trade_collection': '30m',
                'watchlist_check': '1h'
            }
        }
        
        # Write config file
        with open(config_file, 'w') as f:
            yaml.dump(config_content, f, default_flow_style=False)
        
        logger.info(f"Created demo config at: {config_file}")
        
        # Import CLI class
        import sys
        sys.path.append(str(Path(__file__).parent))
        from cli_with_scheduler import SchedulerCLI
        
        # Create CLI instance
        cli = SchedulerCLI(str(config_file))
        
        try:
            # Initialize with mocks
            logger.info("Initializing CLI with rate limiting...")
            
            # Mock the dependencies to avoid actual database/scheduler setup
            from unittest.mock import AsyncMock, MagicMock, patch
            
            with patch('cli_with_scheduler.SQLAlchemyDatabaseManager') as mock_db, \
                 patch('cli_with_scheduler.CollectionScheduler') as mock_scheduler, \
                 patch('cli_with_scheduler.MetadataTracker') as mock_tracker:
                
                # Setup mocks
                mock_db_instance = AsyncMock()
                mock_db.return_value = mock_db_instance
                
                mock_scheduler_instance = MagicMock()
                mock_scheduler.return_value = mock_scheduler_instance
                
                # Initialize CLI
                await cli.initialize(use_mock=True)
                
                logger.info("✓ CLI initialized successfully with rate limiting")
                
                # Test rate limiter functionality
                logger.info("Testing rate limiter functionality...")
                
                # Get a rate limiter for testing
                limiter = await cli.rate_limit_coordinator.get_limiter("demo_collector")
                
                # Make some requests
                logger.info("Making test requests...")
                for i in range(3):
                    await limiter.acquire()
                    logger.info(f"✓ Request {i+1} successful")
                
                # Show status
                status = limiter.get_status()
                logger.info(f"Rate limiter status:")
                logger.info(f"  Daily requests: {status['daily_requests']}/{status['daily_limit']}")
                logger.info(f"  Circuit state: {status['circuit_state']}")
                
                # Test global coordinator status
                global_status = await cli.rate_limit_coordinator.get_global_status()
                logger.info(f"Global rate limiting status:")
                logger.info(f"  Total limiters: {global_status['total_limiters']}")
                logger.info(f"  Daily usage: {global_status['global_usage']['daily_usage_percentage']:.1f}%")
                
                # Simulate rate limit hit
                logger.info("Simulating rate limit response...")
                headers = {'Retry-After': '2'}
                await limiter.handle_rate_limit_response(headers, 429)
                
                status_after = limiter.get_status()
                logger.info(f"After rate limit hit:")
                logger.info(f"  Consecutive failures: {status_after['consecutive_failures']}")
                logger.info(f"  Backoff until: {status_after['backoff_until']}")
                
                # Test recovery
                logger.info("Simulating successful recovery...")
                await limiter.handle_success()
                
                status_recovered = limiter.get_status()
                logger.info(f"After recovery:")
                logger.info(f"  Consecutive failures: {status_recovered['consecutive_failures']}")
                logger.info(f"  Backoff until: {status_recovered['backoff_until']}")
                
                logger.info("✓ Rate limiting demo completed successfully!")
                
        except Exception as e:
            logger.error(f"Demo failed: {e}")
            raise
        finally:
            # Cleanup (mocked objects don't need actual cleanup)
            logger.info("Demo cleanup completed")


if __name__ == "__main__":
    asyncio.run(demo_cli_rate_limiting())