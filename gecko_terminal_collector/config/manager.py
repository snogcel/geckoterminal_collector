"""
Configuration manager with hot-reloading support.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.config.validation import (
    CollectionConfigValidator, validate_config_dict, get_env_var_mappings
)


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration file changes."""
    
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
    
    def on_modified(self, event):
        """Handle file modification events."""
        if not event.is_directory and event.src_path == self.config_manager.config_file_path:
            self.config_manager._reload_config()


class ConfigManager:
    """
    Configuration manager with hot-reloading capabilities.
    
    Supports YAML and JSON configuration files with environment variable
    overrides and automatic reloading when files change.
    """
    
    def __init__(self, config_file_path: str = "config.yaml"):
        """
        Initialize configuration manager.
        
        Args:
            config_file_path: Path to the configuration file
        """
        self.config_file_path = os.path.abspath(config_file_path)
        self._config: Optional[CollectionConfig] = None
        self._observer: Optional[Observer] = None
        self._change_callbacks: list[Callable[[CollectionConfig], None]] = []
        
    def load_config(self) -> CollectionConfig:
        """
        Load configuration from file with environment variable overrides.
        
        Returns:
            Loaded and validated configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        if not os.path.exists(self.config_file_path):
            # Create default config file if it doesn't exist
            self._create_default_config()
        
        # Load from file
        config_data = self._load_config_file()
        
        # Apply environment variable overrides
        config_data = self._apply_env_overrides(config_data)
        
        # Validate using Pydantic
        validated_config = validate_config_dict(config_data)
        
        # Convert to legacy format for backward compatibility
        self._config = validated_config.to_legacy_config()
        
        return self._config
    
    def get_config(self) -> CollectionConfig:
        """
        Get current configuration, loading if necessary.
        
        Returns:
            Current configuration
        """
        if self._config is None:
            return self.load_config()
        return self._config
    
    def start_hot_reload(self) -> None:
        """Start watching configuration file for changes."""
        if self._observer is not None:
            return  # Already watching
        
        config_dir = os.path.dirname(self.config_file_path)
        if not config_dir:
            config_dir = "."
        
        event_handler = ConfigFileHandler(self)
        self._observer = Observer()
        self._observer.schedule(event_handler, config_dir, recursive=False)
        self._observer.start()
    
    def stop_hot_reload(self) -> None:
        """Stop watching configuration file for changes."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
    
    def add_change_callback(self, callback: Callable[[CollectionConfig], None]) -> None:
        """
        Add a callback to be called when configuration changes.
        
        Args:
            callback: Function to call with new configuration
        """
        self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable[[CollectionConfig], None]) -> None:
        """Remove a change callback."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    def _reload_config(self) -> None:
        """Reload configuration from file and notify callbacks."""
        try:
            old_config = self._config
            new_config = self.load_config()
            
            # Only notify if config actually changed
            if old_config != new_config:
                for callback in self._change_callbacks:
                    try:
                        callback(new_config)
                    except Exception as e:
                        print(f"Error in config change callback: {e}")
                        
        except Exception as e:
            print(f"Error reloading configuration: {e}")
    
    def _load_config_file(self) -> Dict[str, Any]:
        """Load configuration data from file."""
        with open(self.config_file_path, 'r') as f:
            if self.config_file_path.endswith('.yaml') or self.config_file_path.endswith('.yml'):
                return yaml.safe_load(f) or {}
            elif self.config_file_path.endswith('.json'):
                return json.load(f)
            else:
                raise ValueError(f"Unsupported config file format: {self.config_file_path}")
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        env_mappings = get_env_var_mappings()
        
        for env_var, config_path_str in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Parse the config path (e.g., "database.url" -> ["database", "url"])
                config_path = config_path_str.split('.')
                
                # Navigate to the nested config location
                current = config_data
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # Set the value with appropriate type conversion
                final_key = config_path[-1]
                current[final_key] = self._convert_env_value(env_var, env_value)
        
        return config_data
    
    def _convert_env_value(self, env_var: str, env_value: str) -> Any:
        """Convert environment variable value to appropriate type."""
        # Integer fields
        if env_var in [
            'GECKO_DB_POOL_SIZE', 'GECKO_DB_TIMEOUT', 'GECKO_API_TIMEOUT',
            'GECKO_API_MAX_CONCURRENT', 'GECKO_MAX_RETRIES',
            'GECKO_ERROR_MAX_RETRIES', 'GECKO_ERROR_CIRCUIT_BREAKER_THRESHOLD',
            'GECKO_ERROR_CIRCUIT_BREAKER_TIMEOUT'
        ]:
            return int(env_value)
        
        # Float fields
        elif env_var in [
            'GECKO_MIN_TRADE_VOLUME', 'GECKO_API_RATE_LIMIT_DELAY',
            'GECKO_RATE_LIMIT_DELAY', 'GECKO_BACKOFF_FACTOR',
            'GECKO_ERROR_BACKOFF_FACTOR'
        ]:
            return float(env_value)
        
        # Boolean fields
        elif env_var in [
            'GECKO_DB_ECHO', 'GECKO_WATCHLIST_AUTO_ADD',
            'GECKO_WATCHLIST_REMOVE_INACTIVE'
        ]:
            return env_value.lower() in ('true', '1', 'yes', 'on')
        
        # List fields (comma-separated)
        elif env_var in ['GECKO_DEX_TARGETS']:
            return [item.strip() for item in env_value.split(',') if item.strip()]
        
        # String fields (default)
        else:
            return env_value
    
    def _create_config_from_dict(self, config_data: Dict[str, Any]) -> CollectionConfig:
        """Create CollectionConfig object from dictionary data."""
        from gecko_terminal_collector.config.models import (
            DEXConfig, IntervalConfig, ThresholdConfig, TimeframeConfig,
            DatabaseConfig, APIConfig, ErrorConfig
        )
        
        # Create nested config objects
        dexes_data = config_data.get('dexes', {})
        dexes = DEXConfig(
            targets=dexes_data.get('targets', ['heaven', 'pumpswap']),
            network=dexes_data.get('network', 'solana')
        )
        
        intervals_data = config_data.get('intervals', {})
        intervals = IntervalConfig(
            top_pools_monitoring=intervals_data.get('top_pools_monitoring', '1h'),
            ohlcv_collection=intervals_data.get('ohlcv_collection', '1h'),
            trade_collection=intervals_data.get('trade_collection', '30m'),
            watchlist_check=intervals_data.get('watchlist_check', '1h')
        )
        
        thresholds_data = config_data.get('thresholds', {})
        thresholds = ThresholdConfig(
            min_trade_volume_usd=thresholds_data.get('min_trade_volume_usd', 100),
            max_retries=thresholds_data.get('max_retries', 3),
            rate_limit_delay=thresholds_data.get('rate_limit_delay', 1.0),
            backoff_factor=thresholds_data.get('backoff_factor', 2.0)
        )
        
        timeframes_data = config_data.get('timeframes', {})
        timeframes = TimeframeConfig(
            ohlcv_default=timeframes_data.get('ohlcv_default', '1h'),
            supported=timeframes_data.get('supported', ['1m', '5m', '15m', '1h', '4h', '12h', '1d'])
        )
        
        database_data = config_data.get('database', {})
        database = DatabaseConfig(
            url=database_data.get('url', 'sqlite:///gecko_data.db'),
            pool_size=database_data.get('pool_size', 10),
            echo=database_data.get('echo', False)
        )
        
        api_data = config_data.get('api', {})
        api = APIConfig(
            base_url=api_data.get('base_url', 'https://api.geckoterminal.com/api/v2'),
            timeout=api_data.get('timeout', 30),
            max_concurrent=api_data.get('max_concurrent', 5),
            rate_limit_delay=api_data.get('rate_limit_delay', 1.0)
        )
        
        error_data = config_data.get('error_handling', {})
        error_handling = ErrorConfig(
            max_retries=error_data.get('max_retries', 3),
            backoff_factor=error_data.get('backoff_factor', 2.0),
            circuit_breaker_threshold=error_data.get('circuit_breaker_threshold', 5),
            circuit_breaker_timeout=error_data.get('circuit_breaker_timeout', 300)
        )
        
        return CollectionConfig(
            dexes=dexes,
            intervals=intervals,
            thresholds=thresholds,
            timeframes=timeframes,
            database=database,
            api=api,
            error_handling=error_handling
        )
    
    def _create_default_config(self) -> None:
        """Create a default configuration file."""
        default_config = {
            'dexes': {
                'targets': ['heaven', 'pumpswap'],
                'network': 'solana'
            },
            'intervals': {
                'top_pools_monitoring': '1h',
                'ohlcv_collection': '1h',
                'trade_collection': '30m',
                'watchlist_check': '1h'
            },
            'thresholds': {
                'min_trade_volume_usd': 100,
                'max_retries': 3,
                'rate_limit_delay': 1.0
            },
            'timeframes': {
                'ohlcv_default': '1h',
                'supported': ['1m', '5m', '15m', '1h', '4h', '12h', '1d']
            },
            'database': {
                'url': 'sqlite:///gecko_data.db',
                'pool_size': 10,
                'echo': False
            },
            'api': {
                'base_url': 'https://api.geckoterminal.com/api/v2',
                'timeout': 30,
                'max_concurrent': 5
            }
        }
        
        with open(self.config_file_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)