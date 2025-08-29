"""
Tests for configuration management.
"""

import pytest
import tempfile
import os
import yaml
from gecko_terminal_collector.config.models import (
    CollectionConfig, DatabaseConfig, APIConfig, IntervalConfig,
    ThresholdConfig, TimeframeConfig, DEXConfig
)
from gecko_terminal_collector.config.manager import ConfigManager


def test_collection_config_defaults():
    """Test CollectionConfig with default values."""
    config = CollectionConfig()
    
    assert config.dexes.network == "solana"
    assert "heaven" in config.dexes.targets
    assert "pumpswap" in config.dexes.targets
    assert config.intervals.ohlcv_collection == "1h"
    assert config.timeframes.ohlcv_default == "1h"


def test_collection_config_validation_success():
    """Test successful configuration validation."""
    config = CollectionConfig()
    errors = config.validate()
    
    assert len(errors) == 0


def test_collection_config_validation_invalid_timeframe():
    """Test configuration validation with invalid default timeframe."""
    config = CollectionConfig()
    config.timeframes.ohlcv_default = "invalid"
    
    errors = config.validate()
    assert len(errors) > 0
    assert "Default timeframe" in errors[0]


def test_collection_config_validation_empty_dex_targets():
    """Test configuration validation with empty DEX targets."""
    config = CollectionConfig()
    config.dexes.targets = []
    
    errors = config.validate()
    assert len(errors) > 0
    assert "At least one DEX target" in errors[0]


def test_collection_config_validation_invalid_interval():
    """Test configuration validation with invalid interval format."""
    config = CollectionConfig()
    config.intervals.ohlcv_collection = "invalid_interval"
    
    errors = config.validate()
    assert len(errors) > 0
    assert "Invalid interval format" in errors[0]


def test_collection_config_validation_negative_volume():
    """Test configuration validation with negative minimum trade volume."""
    config = CollectionConfig()
    config.thresholds.min_trade_volume_usd = -100
    
    errors = config.validate()
    assert len(errors) > 0
    assert "Minimum trade volume must be non-negative" in errors[0]


def test_config_manager_create_default():
    """Test ConfigManager creates default config file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "test_config.yaml")
        manager = ConfigManager(config_path)
        
        # Should create default config
        config = manager.load_config()
        
        assert os.path.exists(config_path)
        assert config.dexes.network == "solana"
        assert len(config.dexes.targets) > 0


def test_config_manager_load_existing():
    """Test ConfigManager loads existing config file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "test_config.yaml")
        
        # Create test config
        test_config = {
            'dexes': {
                'targets': ['test_dex'],
                'network': 'test_network'
            },
            'intervals': {
                'ohlcv_collection': '2h'
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        manager = ConfigManager(config_path)
        config = manager.load_config()
        
        assert config.dexes.network == "test_network"
        assert "test_dex" in config.dexes.targets


def test_config_manager_env_overrides():
    """Test ConfigManager applies environment variable overrides."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "test_config.yaml")
        
        # Set environment variables
        os.environ['GECKO_NETWORK'] = 'env_network'
        os.environ['GECKO_MAX_RETRIES'] = '5'
        
        try:
            manager = ConfigManager(config_path)
            config = manager.load_config()
            
            assert config.dexes.network == "env_network"
            assert config.thresholds.max_retries == 5
            
        finally:
            # Clean up environment variables
            os.environ.pop('GECKO_NETWORK', None)
            os.environ.pop('GECKO_MAX_RETRIES', None)


def test_database_config():
    """Test DatabaseConfig model."""
    config = DatabaseConfig(
        url="postgresql://user:pass@localhost/db",
        pool_size=20,
        echo=True
    )
    
    assert config.url == "postgresql://user:pass@localhost/db"
    assert config.pool_size == 20
    assert config.echo is True


def test_api_config():
    """Test APIConfig model."""
    config = APIConfig(
        base_url="https://test.api.com",
        timeout=60,
        max_concurrent=10
    )
    
    assert config.base_url == "https://test.api.com"
    assert config.timeout == 60
    assert config.max_concurrent == 10


def test_interval_config():
    """Test IntervalConfig model."""
    config = IntervalConfig(
        top_pools_monitoring="2h",
        ohlcv_collection="30m",
        trade_collection="15m",
        watchlist_check="4h"
    )
    
    assert config.top_pools_monitoring == "2h"
    assert config.ohlcv_collection == "30m"
    assert config.trade_collection == "15m"
    assert config.watchlist_check == "4h"