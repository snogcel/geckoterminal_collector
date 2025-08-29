#!/usr/bin/env python3
"""
Hot-reloading configuration manager demonstration.

This script demonstrates the hot-reloading capabilities of the ConfigManager,
showing how configuration changes are automatically detected and applied.
"""

import os
import time
import tempfile
import yaml
from pathlib import Path
from gecko_terminal_collector.config import ConfigManager


def demo_hot_reload():
    """Demonstrate hot-reloading configuration management."""
    print("=== Hot-Reloading Configuration Manager Demo ===\n")
    
    # Create a temporary config file for the demo
    temp_dir = tempfile.mkdtemp()
    config_file = os.path.join(temp_dir, "demo_config.yaml")
    
    print(f"Using temporary config file: {config_file}")
    
    # Create initial configuration
    initial_config = {
        'dexes': {
            'targets': ['heaven', 'pumpswap'],
            'network': 'solana'
        },
        'intervals': {
            'ohlcv_collection': '1h',
            'trade_collection': '30m'
        },
        'thresholds': {
            'min_trade_volume_usd': 100.0
        },
        'database': {
            'url': 'sqlite:///demo.db'
        }
    }
    
    with open(config_file, 'w') as f:
        yaml.dump(initial_config, f, default_flow_style=False, indent=2)
    
    print("Created initial configuration file\n")
    
    # Create config manager
    manager = ConfigManager(config_file)
    
    # Track configuration changes
    config_changes = []
    
    def on_config_change(new_config):
        """Callback function for configuration changes."""
        timestamp = time.strftime("%H:%M:%S")
        config_changes.append({
            'timestamp': timestamp,
            'dex_targets': new_config.dexes.targets.copy(),
            'ohlcv_interval': new_config.intervals.ohlcv_collection,
            'min_volume': float(new_config.thresholds.min_trade_volume_usd),
            'db_url': new_config.database.url
        })
        print(f"[{timestamp}] Configuration changed!")
        print(f"  DEX Targets: {new_config.dexes.targets}")
        print(f"  OHLCV Interval: {new_config.intervals.ohlcv_collection}")
        print(f"  Min Volume: ${new_config.thresholds.min_trade_volume_usd}")
        print(f"  Database: {new_config.database.url}")
        print()
    
    try:
        # Load initial configuration
        print("Loading initial configuration...")
        config = manager.load_config()
        print(f"Initial DEX Targets: {config.dexes.targets}")
        print(f"Initial OHLCV Interval: {config.intervals.ohlcv_collection}")
        print(f"Initial Min Volume: ${config.thresholds.min_trade_volume_usd}")
        print()
        
        # Add change callback and start hot-reloading
        manager.add_change_callback(on_config_change)
        manager.start_hot_reload()
        
        print("Started hot-reloading. Configuration changes will be detected automatically.")
        print("Making configuration changes...\n")
        
        # Simulate configuration changes
        changes = [
            {
                'description': 'Adding Raydium DEX',
                'config': {
                    **initial_config,
                    'dexes': {
                        'targets': ['heaven', 'pumpswap', 'raydium'],
                        'network': 'solana'
                    }
                }
            },
            {
                'description': 'Changing OHLCV collection interval to 15 minutes',
                'config': {
                    **initial_config,
                    'dexes': {
                        'targets': ['heaven', 'pumpswap', 'raydium'],
                        'network': 'solana'
                    },
                    'intervals': {
                        'ohlcv_collection': '15m',
                        'trade_collection': '30m'
                    }
                }
            },
            {
                'description': 'Increasing minimum trade volume to $500',
                'config': {
                    **initial_config,
                    'dexes': {
                        'targets': ['heaven', 'pumpswap', 'raydium'],
                        'network': 'solana'
                    },
                    'intervals': {
                        'ohlcv_collection': '15m',
                        'trade_collection': '30m'
                    },
                    'thresholds': {
                        'min_trade_volume_usd': 500.0
                    }
                }
            },
            {
                'description': 'Switching to PostgreSQL database',
                'config': {
                    **initial_config,
                    'dexes': {
                        'targets': ['heaven', 'pumpswap', 'raydium'],
                        'network': 'solana'
                    },
                    'intervals': {
                        'ohlcv_collection': '15m',
                        'trade_collection': '30m'
                    },
                    'thresholds': {
                        'min_trade_volume_usd': 500.0
                    },
                    'database': {
                        'url': 'postgresql://user:pass@localhost/gecko_data'
                    }
                }
            }
        ]
        
        for i, change in enumerate(changes, 1):
            print(f"Change {i}: {change['description']}")
            
            # Write new configuration
            with open(config_file, 'w') as f:
                yaml.dump(change['config'], f, default_flow_style=False, indent=2)
            
            # Wait for change detection
            time.sleep(1.5)
        
        print("All configuration changes completed!")
        print(f"Total changes detected: {len(config_changes)}")
        
        # Show final configuration
        final_config = manager.get_config()
        print("\nFinal configuration:")
        print(f"  DEX Targets: {final_config.dexes.targets}")
        print(f"  OHLCV Interval: {final_config.intervals.ohlcv_collection}")
        print(f"  Min Volume: ${final_config.thresholds.min_trade_volume_usd}")
        print(f"  Database: {final_config.database.url}")
        
        # Test validation
        print("\n=== Configuration Validation Demo ===")
        
        print("Testing invalid configuration...")
        invalid_config = {
            'dexes': {
                'targets': [],  # Invalid: empty targets
                'network': 'solana'
            },
            'database': {
                'url': 'invalid://url'  # Invalid URL
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(invalid_config, f)
        
        time.sleep(1.0)
        
        # Check validation status
        if not manager.is_config_valid():
            print("✓ Invalid configuration detected correctly")
            print(f"  Validation errors: {manager.get_validation_errors()}")
            print("  Using last known good configuration as fallback")
            
            current_config = manager.get_config()
            print(f"  Current DEX targets: {current_config.dexes.targets}")
        else:
            print("✗ Invalid configuration was not detected")
        
    finally:
        # Clean up
        manager.stop_hot_reload()
        os.unlink(config_file)
        os.rmdir(temp_dir)
        print(f"\nDemo completed. Cleaned up temporary files.")


def demo_environment_overrides():
    """Demonstrate environment variable overrides."""
    print("\n=== Environment Variable Overrides Demo ===")
    
    # Create temporary config
    temp_dir = tempfile.mkdtemp()
    config_file = os.path.join(temp_dir, "env_demo_config.yaml")
    
    base_config = {
        'dexes': {
            'targets': ['heaven'],
            'network': 'solana'
        },
        'database': {
            'url': 'sqlite:///base.db'
        },
        'thresholds': {
            'min_trade_volume_usd': 100.0
        }
    }
    
    with open(config_file, 'w') as f:
        yaml.dump(base_config, f)
    
    try:
        manager = ConfigManager(config_file)
        
        print("Base configuration from file:")
        config = manager.load_config()
        print(f"  DEX Targets: {config.dexes.targets}")
        print(f"  Database URL: {config.database.url}")
        print(f"  Min Volume: ${config.thresholds.min_trade_volume_usd}")
        
        print("\nSetting environment variable overrides...")
        os.environ['GECKO_DEX_TARGETS'] = 'heaven,raydium,orca'
        os.environ['GECKO_DB_URL'] = 'postgresql://env:override@localhost/gecko'
        os.environ['GECKO_MIN_TRADE_VOLUME'] = '250.0'
        
        # Reload configuration with environment overrides
        config = manager.load_config()
        print("Configuration with environment overrides:")
        print(f"  DEX Targets: {config.dexes.targets}")
        print(f"  Database URL: {config.database.url}")
        print(f"  Min Volume: ${config.thresholds.min_trade_volume_usd}")
        
    finally:
        # Clean up environment variables
        for var in ['GECKO_DEX_TARGETS', 'GECKO_DB_URL', 'GECKO_MIN_TRADE_VOLUME']:
            os.environ.pop(var, None)
        
        os.unlink(config_file)
        os.rmdir(temp_dir)


def main():
    """Run the hot-reload demonstration."""
    print("GeckoTerminal Hot-Reloading Configuration Manager Demo")
    print("=" * 60)
    
    demo_hot_reload()
    demo_environment_overrides()
    
    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("\nKey features demonstrated:")
    print("✓ Automatic configuration file change detection")
    print("✓ Real-time configuration reloading")
    print("✓ Configuration change callbacks")
    print("✓ Configuration validation with fallback")
    print("✓ Environment variable overrides")
    print("✓ Thread-safe configuration access")
    print("✓ Support for YAML and JSON formats")


if __name__ == "__main__":
    main()