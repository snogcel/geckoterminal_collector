"""
Pytest configuration and shared fixtures.
"""

import pytest
from unittest.mock import Mock
from gecko_terminal_collector.config.models import CollectionConfig, DatabaseConfig
from gecko_terminal_collector.database.manager import DatabaseManager


@pytest.fixture
def mock_database_config():
    """Mock database configuration for testing."""
    return DatabaseConfig(
        url="sqlite:///:memory:",
        pool_size=1,
        echo=False
    )


@pytest.fixture
def mock_collection_config():
    """Mock collection configuration for testing."""
    return CollectionConfig()


@pytest.fixture
def mock_database_manager(mock_database_config):
    """Mock database manager for testing."""
    class MockDatabaseManager(DatabaseManager):
        def __init__(self, config):
            super().__init__(config)
            self.initialized = False
        
        async def initialize(self):
            self.initialized = True
        
        async def close(self):
            self.initialized = False
        
        # Mock implementations of abstract methods
        async def store_pools(self, pools):
            return len(pools)
        
        async def get_pool(self, pool_id):
            return None
        
        async def get_pools_by_dex(self, dex_id):
            return []
        
        async def store_tokens(self, tokens):
            return len(tokens)
        
        async def get_token(self, token_id):
            return None
        
        async def store_ohlcv_data(self, data):
            return len(data)
        
        async def get_ohlcv_data(self, pool_id, timeframe, start_time=None, end_time=None):
            return []
        
        async def get_data_gaps(self, pool_id, timeframe, start, end):
            return []
        
        async def store_trade_data(self, data):
            return len(data)
        
        async def get_trade_data(self, pool_id, start_time=None, end_time=None, min_volume_usd=None):
            return []
        
        async def store_watchlist_entry(self, pool_id, metadata):
            pass
        
        async def get_watchlist_pools(self):
            return []
        
        async def remove_watchlist_entry(self, pool_id):
            pass
        
        async def update_collection_metadata(self, collector_type, last_run, success, error_message=None):
            pass
        
        async def get_collection_metadata(self, collector_type):
            return None
    
    return MockDatabaseManager(mock_database_config)