"""
Unit tests for hot-reloading configuration manager.
"""

import os
import tempfile
import time
import threading
import yaml
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from gecko_terminal_collector.config import ConfigManager, CollectionConfig
from gecko_terminal_collector.config.models import (
    DEXConfig, IntervalConfig, ThresholdConfig, DatabaseConfig
)


class TestConfigManager:
    """Test cases for ConfigManager hot-reloading functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.yaml")
        self.manager = ConfigManager(self.config_file)
        
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.manager.is_hot_reload_active():
            self.manager.stop_hot_reload()
        
        # Clean up temp files
        if os.path.exists(self.config_file):
            os.unlink(self.config_file)
        os.rmdir(self.temp_dir)
    
    def create_test_config(self, config_data: dict = None) -> None:
        """Create a test configuration file."""
        if config_data is None:
            config_data = {
                'dexes': {
                    'targets': ['heaven', 'pumpswap'],
                    'network': 'solana'
                },
                'intervals': {
                    'ohlcv_collection': '1h'
                },
                'database': {
                    'url': 'sqlite:///test.db'
                }
            }
        
        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f)
    
    def test_load_config_creates_default_if_missing(self):
        """Test that load_config creates default config if file doesn't exist."""
        # Ensure file doesn't exist
        assert not os.path.exists(self.config_file)
        
        # Load config should create default
        config = self.manager.load_config()
        
        # File should now exist
        assert os.path.exists(self.config_file)
        assert isinstance(config, CollectionConfig)
        assert config.dexes.targets == ['heaven', 'pumpswap']
    
    def test_load_config_from_existing_file(self):
        """Test loading configuration from existing file."""
        test_config = {
            'dexes': {
                'targets': ['raydium', 'orca'],
                'network': 'solana'
            },
            'intervals': {
                'ohlcv_collection': '30m'
            },
            'database': {
                'url': 'postgresql://test'
            }
        }
        self.create_test_config(test_config)
        
        config = self.manager.load_config()
        
        assert config.dexes.targets == ['raydium', 'orca']
        assert config.intervals.ohlcv_collection == '30m'
        assert config.database.url == 'postgresql://test'
    
    def test_environment_variable_overrides(self):
        """Test that environment variables override config file values."""
        self.create_test_config()
        
        with patch.dict(os.environ, {
            'GECKO_DEX_TARGETS': 'heaven,raydium,orca',
            'GECKO_DB_URL': 'postgresql://override',
            'GECKO_API_TIMEOUT': '60'
        }):
            config = self.manager.load_config()
            
            assert config.dexes.targets == ['heaven', 'raydium', 'orca']
            assert config.database.url == 'postgresql://override'
            assert config.api.timeout == 60
    
    def test_config_validation_success(self):
        """Test successful configuration validation."""
        valid_config = {
            'dexes': {
                'targets': ['heaven'],
                'network': 'solana'
            },
            'intervals': {
                'ohlcv_collection': '1h'
            },
            'timeframes': {
                'ohlcv_default': '1h',
                'supported': ['1h', '4h']
            }
        }
        self.create_test_config(valid_config)
        
        config = self.manager.load_config()
        assert self.manager.is_config_valid()
        assert len(self.manager.get_validation_errors()) == 0
    
    def test_config_validation_failure(self):
        """Test configuration validation failure handling."""
        invalid_config = {
            'dexes': {
                'targets': [],  # Invalid: empty targets
                'network': 'solana'
            },
            'database': {
                'url': 'invalid://url'  # Invalid URL format
            }
        }
        self.create_test_config(invalid_config)
        
        with pytest.raises(ValueError, match="Configuration validation failed"):
            self.manager.load_config()
    
    def test_config_validation_with_fallback(self):
        """Test that invalid config falls back to last known good config."""
        # First load a valid config
        valid_config = {
            'dexes': {'targets': ['heaven'], 'network': 'solana'},
            'database': {'url': 'sqlite:///valid.db'}
        }
        self.create_test_config(valid_config)
        
        good_config = self.manager.load_config()
        assert good_config.database.url == 'sqlite:///valid.db'
        
        # Now create an invalid config
        invalid_config = {
            'dexes': {'targets': []},  # Invalid
            'database': {'url': 'invalid://url'}
        }
        self.create_test_config(invalid_config)
        
        # Should return the last known good config
        fallback_config = self.manager.load_config()
        assert fallback_config.database.url == 'sqlite:///valid.db'
        assert not self.manager.is_config_valid()
    
    def test_validate_config_file_method(self):
        """Test the validate_config_file method."""
        # Test with valid config
        valid_config = {
            'dexes': {'targets': ['heaven'], 'network': 'solana'}
        }
        self.create_test_config(valid_config)
        
        is_valid, errors = self.manager.validate_config_file()
        assert is_valid
        assert len(errors) == 0
        
        # Test with invalid config
        invalid_config = {
            'dexes': {'targets': []},  # Invalid
        }
        self.create_test_config(invalid_config)
        
        is_valid, errors = self.manager.validate_config_file()
        assert not is_valid
        assert len(errors) > 0
    
    def test_config_hash_calculation(self):
        """Test configuration hash calculation for change detection."""
        self.create_test_config()
        
        # Load config and get initial hash
        config1 = self.manager.load_config()
        hash1 = self.manager._calculate_config_hash()
        
        # Load again without changes - should be same hash
        config2 = self.manager.load_config()
        hash2 = self.manager._calculate_config_hash()
        assert hash1 == hash2
        
        # Modify config file
        modified_config = {
            'dexes': {'targets': ['raydium'], 'network': 'solana'},
            'database': {'url': 'sqlite:///modified.db'}
        }
        self.create_test_config(modified_config)
        
        # Hash should be different
        hash3 = self.manager._calculate_config_hash()
        assert hash1 != hash3
    
    def test_config_hash_includes_environment_variables(self):
        """Test that config hash includes environment variables."""
        self.create_test_config()
        
        # Get hash without env vars
        hash1 = self.manager._calculate_config_hash()
        
        # Set environment variable and get hash again
        with patch.dict(os.environ, {'GECKO_DB_URL': 'postgresql://env'}):
            hash2 = self.manager._calculate_config_hash()
        
        # Hashes should be different
        assert hash1 != hash2
    
    def test_hot_reload_lifecycle(self):
        """Test hot-reload start/stop lifecycle."""
        assert not self.manager.is_hot_reload_active()
        
        self.manager.start_hot_reload()
        assert self.manager.is_hot_reload_active()
        
        self.manager.stop_hot_reload()
        assert not self.manager.is_hot_reload_active()
        
        # Starting again should work
        self.manager.start_hot_reload()
        assert self.manager.is_hot_reload_active()
    
    def test_hot_reload_duplicate_start(self):
        """Test that starting hot-reload multiple times is safe."""
        self.manager.start_hot_reload()
        observer1 = self.manager._observer
        
        # Starting again should not create new observer
        self.manager.start_hot_reload()
        observer2 = self.manager._observer
        
        assert observer1 is observer2
    
    def test_change_callbacks(self):
        """Test configuration change callbacks."""
        self.create_test_config()
        
        callback_calls = []
        
        def test_callback(config):
            callback_calls.append(config)
        
        # Add callback
        self.manager.add_change_callback(test_callback)
        
        # Load initial config
        initial_config = self.manager.load_config()
        
        # Simulate config change
        modified_config = {
            'dexes': {'targets': ['raydium'], 'network': 'solana'}
        }
        self.create_test_config(modified_config)
        
        # Manually trigger reload (simulating file change)
        self.manager._reload_config()
        
        # Callback should have been called
        assert len(callback_calls) == 1
        assert callback_calls[0].dexes.targets == ['raydium']
    
    def test_change_callback_error_handling(self):
        """Test that callback errors don't break config reloading."""
        self.create_test_config()
        
        def failing_callback(config):
            raise Exception("Callback error")
        
        def working_callback(config):
            working_callback.called = True
        working_callback.called = False
        
        self.manager.add_change_callback(failing_callback)
        self.manager.add_change_callback(working_callback)
        
        # Load initial config
        self.manager.load_config()
        
        # Modify config
        modified_config = {
            'dexes': {'targets': ['raydium'], 'network': 'solana'}
        }
        self.create_test_config(modified_config)
        
        # Reload should work despite failing callback
        self.manager._reload_config()
        
        # Working callback should still be called
        assert working_callback.called
    
    def test_remove_change_callback(self):
        """Test removing change callbacks."""
        callback_calls = []
        
        def test_callback(config):
            callback_calls.append(config)
        
        self.manager.add_change_callback(test_callback)
        self.manager.remove_change_callback(test_callback)
        
        # Create and modify config
        self.create_test_config()
        self.manager.load_config()
        
        modified_config = {
            'dexes': {'targets': ['raydium'], 'network': 'solana'}
        }
        self.create_test_config(modified_config)
        self.manager._reload_config()
        
        # Callback should not have been called
        assert len(callback_calls) == 0
    
    def test_config_equality_comparison(self):
        """Test configuration equality comparison."""
        config1 = CollectionConfig(
            dexes=DEXConfig(targets=['heaven'], network='solana'),
            intervals=IntervalConfig(ohlcv_collection='1h'),
            database=DatabaseConfig(url='sqlite:///test.db')
        )
        
        config2 = CollectionConfig(
            dexes=DEXConfig(targets=['heaven'], network='solana'),
            intervals=IntervalConfig(ohlcv_collection='1h'),
            database=DatabaseConfig(url='sqlite:///test.db')
        )
        
        config3 = CollectionConfig(
            dexes=DEXConfig(targets=['raydium'], network='solana'),
            intervals=IntervalConfig(ohlcv_collection='1h'),
            database=DatabaseConfig(url='sqlite:///test.db')
        )
        
        assert self.manager._configs_are_equal(config1, config2)
        assert not self.manager._configs_are_equal(config1, config3)
        assert self.manager._configs_are_equal(None, None)
        assert not self.manager._configs_are_equal(config1, None)
    
    def test_json_config_file_support(self):
        """Test support for JSON configuration files."""
        json_config_file = os.path.join(self.temp_dir, "test_config.json")
        json_manager = ConfigManager(json_config_file)
        
        config_data = {
            'dexes': {
                'targets': ['heaven'],
                'network': 'solana'
            },
            'database': {
                'url': 'sqlite:///json_test.db'
            }
        }
        
        with open(json_config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = json_manager.load_config()
        assert config.dexes.targets == ['heaven']
        assert config.database.url == 'sqlite:///json_test.db'
        
        # Clean up
        os.unlink(json_config_file)
    
    def test_unsupported_config_file_format(self):
        """Test error handling for unsupported config file formats."""
        txt_config_file = os.path.join(self.temp_dir, "test_config.txt")
        txt_manager = ConfigManager(txt_config_file)
        
        with open(txt_config_file, 'w') as f:
            f.write("invalid config format")
        
        with pytest.raises(ValueError, match="Unsupported config file format"):
            txt_manager.load_config()
        
        # Clean up
        os.unlink(txt_config_file)


class TestConfigFileHandler:
    """Test cases for ConfigFileHandler file watching."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.yaml")
        self.manager = ConfigManager(self.config_file)
        
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.manager.is_hot_reload_active():
            self.manager.stop_hot_reload()
        
        if os.path.exists(self.config_file):
            os.unlink(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_file_change_detection(self):
        """Test that file changes are detected and trigger reloads."""
        # Create initial config
        initial_config = {
            'dexes': {'targets': ['heaven'], 'network': 'solana'}
        }
        with open(self.config_file, 'w') as f:
            yaml.dump(initial_config, f)
        
        # Load initial config and start watching
        config = self.manager.load_config()
        assert config.dexes.targets == ['heaven']
        
        # Mock the reload method to track calls
        reload_calls = []
        original_reload = self.manager._reload_config
        
        def mock_reload():
            reload_calls.append(time.time())
            original_reload()
        
        self.manager._reload_config = mock_reload
        
        self.manager.start_hot_reload()
        
        # Modify the config file
        modified_config = {
            'dexes': {'targets': ['raydium'], 'network': 'solana'}
        }
        
        # Wait a bit to ensure file watcher is ready
        time.sleep(0.2)
        
        with open(self.config_file, 'w') as f:
            yaml.dump(modified_config, f)
        
        # Wait for file system event to be processed
        time.sleep(0.5)
        
        # Reload should have been called
        assert len(reload_calls) > 0
    
    def test_debounce_rapid_changes(self):
        """Test that rapid file changes are debounced."""
        # Create initial config
        with open(self.config_file, 'w') as f:
            yaml.dump({'dexes': {'targets': ['heaven']}}, f)
        
        self.manager.load_config()
        
        # Track reload calls
        reload_calls = []
        original_reload = self.manager._reload_config
        
        def mock_reload():
            reload_calls.append(time.time())
        
        self.manager._reload_config = mock_reload
        self.manager.start_hot_reload()
        
        # Wait for watcher to be ready
        time.sleep(0.2)
        
        # Make rapid changes
        for i in range(5):
            with open(self.config_file, 'w') as f:
                yaml.dump({'dexes': {'targets': [f'dex_{i}']}}, f)
            time.sleep(0.05)  # Very rapid changes
        
        # Wait for debouncing
        time.sleep(1.5)
        
        # Should have fewer reload calls than file changes due to debouncing
        assert len(reload_calls) < 5


class TestConfigManagerIntegration:
    """Integration tests for ConfigManager with real file operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "integration_config.yaml")
        
    def teardown_method(self):
        """Clean up test fixtures."""
        if os.path.exists(self.config_file):
            os.unlink(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_end_to_end_hot_reload_workflow(self):
        """Test complete hot-reload workflow from start to finish."""
        manager = ConfigManager(self.config_file)
        
        # Track configuration changes
        config_changes = []
        
        def track_changes(config):
            config_changes.append({
                'timestamp': time.time(),
                'dex_targets': config.dexes.targets.copy(),
                'db_url': config.database.url
            })
        
        manager.add_change_callback(track_changes)
        
        try:
            # 1. Load initial config (should create default)
            initial_config = manager.load_config()
            assert initial_config.dexes.targets == ['heaven', 'pumpswap']
            
            # 2. Start hot-reloading
            manager.start_hot_reload()
            assert manager.is_hot_reload_active()
            
            # 3. Modify config file
            time.sleep(0.2)  # Let watcher initialize
            
            modified_config = {
                'dexes': {
                    'targets': ['raydium', 'orca'],
                    'network': 'solana'
                },
                'database': {
                    'url': 'postgresql://modified'
                }
            }
            
            with open(self.config_file, 'w') as f:
                yaml.dump(modified_config, f)
            
            # 4. Wait for change detection
            time.sleep(1.0)
            
            # 5. Verify config was reloaded
            current_config = manager.get_config()
            assert current_config.dexes.targets == ['raydium', 'orca']
            assert current_config.database.url == 'postgresql://modified'
            
            # 6. Verify callback was called
            assert len(config_changes) > 0
            latest_change = config_changes[-1]
            assert latest_change['dex_targets'] == ['raydium', 'orca']
            assert latest_change['db_url'] == 'postgresql://modified'
            
        finally:
            # 7. Clean shutdown
            manager.stop_hot_reload()
            assert not manager.is_hot_reload_active()
    
    def test_concurrent_access_thread_safety(self):
        """Test thread safety of configuration access during reloads."""
        manager = ConfigManager(self.config_file)
        
        # Create initial config
        initial_config = {
            'dexes': {'targets': ['heaven'], 'network': 'solana'},
            'database': {'url': 'sqlite:///thread_test.db'}
        }
        with open(self.config_file, 'w') as f:
            yaml.dump(initial_config, f)
        
        manager.load_config()
        manager.start_hot_reload()
        
        # Track access results from multiple threads
        access_results = []
        access_lock = threading.Lock()
        
        def access_config(thread_id):
            """Access configuration from a thread."""
            for i in range(10):
                try:
                    config = manager.get_config()
                    with access_lock:
                        access_results.append({
                            'thread_id': thread_id,
                            'iteration': i,
                            'dex_targets': config.dexes.targets.copy(),
                            'success': True
                        })
                    time.sleep(0.01)
                except Exception as e:
                    with access_lock:
                        access_results.append({
                            'thread_id': thread_id,
                            'iteration': i,
                            'error': str(e),
                            'success': False
                        })
        
        def modify_config():
            """Modify configuration file repeatedly."""
            for i in range(5):
                time.sleep(0.05)
                modified_config = {
                    'dexes': {'targets': [f'dex_{i}'], 'network': 'solana'},
                    'database': {'url': f'sqlite:///test_{i}.db'}
                }
                with open(self.config_file, 'w') as f:
                    yaml.dump(modified_config, f)
        
        try:
            # Start multiple threads accessing config
            threads = []
            for thread_id in range(3):
                thread = threading.Thread(target=access_config, args=(thread_id,))
                threads.append(thread)
                thread.start()
            
            # Start config modification thread
            modify_thread = threading.Thread(target=modify_config)
            modify_thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            modify_thread.join()
            
            # Verify all accesses were successful
            successful_accesses = [r for r in access_results if r['success']]
            failed_accesses = [r for r in access_results if not r['success']]
            
            assert len(successful_accesses) > 0
            assert len(failed_accesses) == 0  # No access should fail
            
        finally:
            manager.stop_hot_reload()


if __name__ == "__main__":
    pytest.main([__file__])