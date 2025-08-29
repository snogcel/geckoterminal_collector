"""
Tests for configuration validation and management.
"""

import os
import tempfile
import pytest
from decimal import Decimal
from unittest.mock import patch
from gecko_terminal_collector.config import (
    ConfigManager,
    CollectionConfigValidator,
    validate_config_dict,
    get_env_var_mappings,
    TimeframeEnum,
    NetworkEnum
)


class TestConfigurationValidation:
    """Test configuration validation using Pydantic."""
    
    def test_valid_default_config(self):
        """Test that default configuration is valid."""
        config = CollectionConfigValidator()
        assert config.dexes.network == NetworkEnum.SOLANA
        assert config.timeframes.ohlcv_default == TimeframeEnum.ONE_HOUR
        assert config.database.url == "sqlite:///gecko_data.db"
    
    def test_invalid_database_url(self):
        """Test validation of invalid database URL."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Unsupported database URL format"):
            CollectionConfigValidator(database={"url": "invalid://url"})
    
    def test_invalid_interval_format(self):
        """Test validation of invalid interval format."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Invalid interval format"):
            CollectionConfigValidator(intervals={"top_pools_monitoring": "invalid"})
    
    def test_invalid_timeframe(self):
        """Test validation of invalid timeframe."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CollectionConfigValidator(timeframes={"ohlcv_default": "invalid"})
    
    def test_negative_thresholds(self):
        """Test validation of negative threshold values."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CollectionConfigValidator(thresholds={"min_trade_volume_usd": -100})
    
    def test_empty_dex_targets(self):
        """Test validation of empty DEX targets."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="List should have at least 1 item"):
            CollectionConfigValidator(dexes={"targets": []})
    
    def test_invalid_dex_target_name(self):
        """Test validation of invalid DEX target names."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Invalid DEX target name"):
            CollectionConfigValidator(dexes={"targets": ["invalid-name!"]})
    
    def test_out_of_range_values(self):
        """Test validation of out-of-range values."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CollectionConfigValidator(database={"pool_size": 200})  # Max is 100
        
        with pytest.raises(ValidationError):
            CollectionConfigValidator(api={"max_concurrent": 100})  # Max is 50
    
    def test_interval_range_validation(self):
        """Test validation of interval ranges."""
        # Valid intervals
        config = CollectionConfigValidator(intervals={
            "top_pools_monitoring": "30m",
            "ohlcv_collection": "2h",
            "trade_collection": "1d"
        })
        assert config.intervals.top_pools_monitoring == "30m"
        
        # Invalid intervals
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Minute interval must be between"):
            CollectionConfigValidator(intervals={"top_pools_monitoring": "2000m"})
    
    def test_default_timeframe_in_supported(self):
        """Test that default timeframe must be in supported list."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="Default timeframe.*must be in supported"):
            CollectionConfigValidator(timeframes={
                "ohlcv_default": "1h",
                "supported": ["5m", "15m"]  # Missing 1h
            })
    
    def test_watchlist_config_validation(self):
        """Test watchlist configuration validation."""
        # Valid config
        config = CollectionConfigValidator(watchlist={
            "file_path": "test.csv",
            "check_interval": "2h"
        })
        assert config.watchlist.file_path == "test.csv"
        
        # Invalid file extension
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="must be a CSV file"):
            CollectionConfigValidator(watchlist={"file_path": "test.txt"})
    
    def test_to_legacy_config_conversion(self):
        """Test conversion to legacy config format."""
        validator_config = CollectionConfigValidator()
        legacy_config = validator_config.to_legacy_config()
        
        assert legacy_config.dexes.network == "solana"
        assert legacy_config.timeframes.ohlcv_default == "1h"
        assert isinstance(legacy_config.thresholds.min_trade_volume_usd, Decimal)


class TestConfigManager:
    """Test configuration manager functionality."""
    
    def test_config_manager_initialization(self):
        """Test config manager initialization."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            config_path = f.name
        
        try:
            manager = ConfigManager(config_path)
            assert manager.config_file_path == os.path.abspath(config_path)
        finally:
            os.unlink(config_path)
    
    def test_create_default_config(self):
        """Test creation of default configuration file."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            config_path = f.name
        
        # Remove the file so it gets created by the manager
        os.unlink(config_path)
        
        try:
            manager = ConfigManager(config_path)
            config = manager.load_config()
            
            assert os.path.exists(config_path)
            assert config.dexes.network == "solana"
            assert "heaven" in config.dexes.targets
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)
    
    def test_load_yaml_config(self):
        """Test loading YAML configuration file."""
        config_data = {
            'dexes': {
                'targets': ['test_dex'],
                'network': 'solana'
            },
            'database': {
                'url': 'sqlite:///test.db'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            manager = ConfigManager(config_path)
            config = manager.load_config()
            
            assert config.dexes.targets == ['test_dex']
            assert config.database.url == 'sqlite:///test.db'
        finally:
            os.unlink(config_path)
    
    def test_load_json_config(self):
        """Test loading JSON configuration file."""
        config_data = {
            'dexes': {
                'targets': ['test_dex'],
                'network': 'solana'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            manager = ConfigManager(config_path)
            config = manager.load_config()
            
            assert config.dexes.targets == ['test_dex']
        finally:
            os.unlink(config_path)
    
    def test_unsupported_config_format(self):
        """Test error handling for unsupported config file format."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            config_path = f.name
        
        try:
            manager = ConfigManager(config_path)
            with pytest.raises(ValueError, match="Unsupported config file format"):
                manager.load_config()
        finally:
            os.unlink(config_path)
    
    @patch.dict(os.environ, {
        'GECKO_DB_URL': 'postgresql://test:test@localhost/test',
        'GECKO_DEX_TARGETS': 'heaven,pumpswap,test',
        'GECKO_MIN_TRADE_VOLUME': '500.0',
        'GECKO_API_TIMEOUT': '60',
        'GECKO_DB_ECHO': 'true'
    })
    def test_environment_variable_overrides(self):
        """Test environment variable overrides."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump({}, f)  # Empty config file
            config_path = f.name
        
        try:
            manager = ConfigManager(config_path)
            config = manager.load_config()
            
            assert config.database.url == 'postgresql://test:test@localhost/test'
            assert config.dexes.targets == ['heaven', 'pumpswap', 'test']
            assert config.thresholds.min_trade_volume_usd == Decimal('500.0')
            assert config.api.timeout == 60
            assert config.database.echo is True
        finally:
            os.unlink(config_path)
    
    def test_invalid_config_validation_error(self):
        """Test that invalid configuration raises validation error."""
        config_data = {
            'database': {
                'url': 'invalid://url'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            manager = ConfigManager(config_path)
            with pytest.raises(ValueError, match="Configuration validation failed"):
                manager.load_config()
        finally:
            os.unlink(config_path)
    
    def test_get_config_caching(self):
        """Test that get_config returns cached configuration."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            config_path = f.name
        
        # Remove the file so it gets created by the manager
        os.unlink(config_path)
        
        try:
            manager = ConfigManager(config_path)
            
            # First call should load config
            config1 = manager.get_config()
            
            # Second call should return cached config
            config2 = manager.get_config()
            
            assert config1 is config2
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)


class TestEnvironmentVariableMappings:
    """Test environment variable mappings."""
    
    def test_get_env_var_mappings(self):
        """Test that environment variable mappings are complete."""
        mappings = get_env_var_mappings()
        
        # Check that all expected mappings exist
        expected_vars = [
            'GECKO_DB_URL',
            'GECKO_API_TIMEOUT',
            'GECKO_DEX_TARGETS',
            'GECKO_MIN_TRADE_VOLUME',
            'GECKO_OHLCV_DEFAULT_TIMEFRAME'
        ]
        
        for var in expected_vars:
            assert var in mappings
            assert isinstance(mappings[var], str)
            assert '.' in mappings[var]  # Should be dot-separated path
    
    def test_env_value_conversion(self):
        """Test environment value type conversion."""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            config_path = f.name
        
        # Remove the file so it gets created by the manager
        os.unlink(config_path)
        
        try:
            manager = ConfigManager(config_path)
            
            # Test integer conversion
            assert manager._convert_env_value('GECKO_API_TIMEOUT', '30') == 30
            
            # Test float conversion
            assert manager._convert_env_value('GECKO_MIN_TRADE_VOLUME', '100.5') == 100.5
            
            # Test boolean conversion
            assert manager._convert_env_value('GECKO_DB_ECHO', 'true') is True
            assert manager._convert_env_value('GECKO_DB_ECHO', 'false') is False
            
            # Test list conversion
            result = manager._convert_env_value('GECKO_DEX_TARGETS', 'heaven,pumpswap,test')
            assert result == ['heaven', 'pumpswap', 'test']
            
            # Test string conversion (default)
            assert manager._convert_env_value('GECKO_DB_URL', 'sqlite:///test.db') == 'sqlite:///test.db'
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)


class TestValidateConfigDict:
    """Test standalone config validation function."""
    
    def test_validate_valid_config_dict(self):
        """Test validation of valid configuration dictionary."""
        config_data = {
            'dexes': {
                'targets': ['heaven'],
                'network': 'solana'
            }
        }
        
        validated = validate_config_dict(config_data)
        assert isinstance(validated, CollectionConfigValidator)
        assert validated.dexes.targets == ['heaven']
    
    def test_validate_invalid_config_dict(self):
        """Test validation of invalid configuration dictionary."""
        config_data = {
            'database': {
                'url': 'invalid://url'
            }
        }
        
        with pytest.raises(ValueError, match="Configuration validation failed"):
            validate_config_dict(config_data)
    
    def test_validate_empty_config_dict(self):
        """Test validation of empty configuration dictionary (should use defaults)."""
        validated = validate_config_dict({})
        assert isinstance(validated, CollectionConfigValidator)
        assert validated.dexes.network == NetworkEnum.SOLANA