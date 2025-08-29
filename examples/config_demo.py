#!/usr/bin/env python3
"""
Configuration system demonstration script.

This script demonstrates how to use the GeckoTerminal collector configuration system
with YAML/JSON files, environment variable overrides, and validation.
"""

import os
import tempfile
from pathlib import Path
from gecko_terminal_collector.config import ConfigManager, CollectionConfigValidator


def demo_basic_config_loading():
    """Demonstrate basic configuration loading."""
    print("=== Basic Configuration Loading ===")
    
    # Create a config manager (will create default config if none exists)
    manager = ConfigManager("config.yaml")
    config = manager.load_config()
    
    print(f"Database URL: {config.database.url}")
    print(f"DEX Targets: {config.dexes.targets}")
    print(f"Network: {config.dexes.network}")
    print(f"OHLCV Collection Interval: {config.intervals.ohlcv_collection}")
    print(f"Min Trade Volume: ${config.thresholds.min_trade_volume_usd}")
    print()


def demo_environment_overrides():
    """Demonstrate environment variable overrides."""
    print("=== Environment Variable Overrides ===")
    
    # Set some environment variables
    os.environ['GECKO_DB_URL'] = 'postgresql://user:pass@localhost/gecko'
    os.environ['GECKO_DEX_TARGETS'] = 'heaven,pumpswap,raydium'
    os.environ['GECKO_MIN_TRADE_VOLUME'] = '500.0'
    os.environ['GECKO_API_TIMEOUT'] = '60'
    
    try:
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
dexes:
  targets: ["heaven"]  # This will be overridden
  network: solana
database:
  url: "sqlite:///default.db"  # This will be overridden
""")
            config_path = f.name
        
        manager = ConfigManager(config_path)
        config = manager.load_config()
        
        print(f"Database URL (overridden): {config.database.url}")
        print(f"DEX Targets (overridden): {config.dexes.targets}")
        print(f"Min Trade Volume (overridden): ${config.thresholds.min_trade_volume_usd}")
        print(f"API Timeout (overridden): {config.api.timeout}s")
        
    finally:
        # Clean up
        os.unlink(config_path)
        for var in ['GECKO_DB_URL', 'GECKO_DEX_TARGETS', 'GECKO_MIN_TRADE_VOLUME', 'GECKO_API_TIMEOUT']:
            os.environ.pop(var, None)
    
    print()


def demo_validation():
    """Demonstrate configuration validation."""
    print("=== Configuration Validation ===")
    
    # Valid configuration
    try:
        valid_config = CollectionConfigValidator(
            dexes={"targets": ["heaven", "pumpswap"]},
            intervals={"ohlcv_collection": "2h"},
            thresholds={"min_trade_volume_usd": 250.0}
        )
        print("✓ Valid configuration created successfully")
        print(f"  DEX Targets: {valid_config.dexes.targets}")
        print(f"  OHLCV Interval: {valid_config.intervals.ohlcv_collection}")
    except Exception as e:
        print(f"✗ Validation failed: {e}")
    
    # Invalid configuration examples
    invalid_configs = [
        {
            "name": "Invalid database URL",
            "config": {"database": {"url": "invalid://url"}},
            "expected_error": "Unsupported database URL format"
        },
        {
            "name": "Invalid interval format",
            "config": {"intervals": {"ohlcv_collection": "invalid"}},
            "expected_error": "Invalid interval format"
        },
        {
            "name": "Empty DEX targets",
            "config": {"dexes": {"targets": []}},
            "expected_error": "List should have at least 1 item"
        },
        {
            "name": "Out of range pool size",
            "config": {"database": {"pool_size": 200}},
            "expected_error": "Input should be less than or equal to 100"
        }
    ]
    
    for test_case in invalid_configs:
        try:
            CollectionConfigValidator(**test_case["config"])
            print(f"✗ {test_case['name']}: Should have failed but didn't")
        except Exception as e:
            if test_case["expected_error"] in str(e):
                print(f"✓ {test_case['name']}: Correctly rejected")
            else:
                print(f"? {test_case['name']}: Rejected with unexpected error: {e}")
    
    print()


def demo_config_conversion():
    """Demonstrate conversion between validation and legacy formats."""
    print("=== Configuration Format Conversion ===")
    
    # Create a validated config
    validated_config = CollectionConfigValidator(
        dexes={"targets": ["heaven", "pumpswap"], "network": "solana"},
        intervals={"ohlcv_collection": "4h", "trade_collection": "1h"},
        thresholds={"min_trade_volume_usd": 150.0, "max_retries": 5}
    )
    
    # Convert to legacy format
    legacy_config = validated_config.to_legacy_config()
    
    print("Validated Config:")
    print(f"  Network: {validated_config.dexes.network} (enum)")
    print(f"  Timeframe: {validated_config.timeframes.ohlcv_default} (enum)")
    
    print("Legacy Config:")
    print(f"  Network: {legacy_config.dexes.network} (string)")
    print(f"  Timeframe: {legacy_config.timeframes.ohlcv_default} (string)")
    print(f"  Min Volume: {legacy_config.thresholds.min_trade_volume_usd} (Decimal)")
    
    print()


def demo_comprehensive_config():
    """Show a comprehensive configuration example."""
    print("=== Comprehensive Configuration Example ===")
    
    config_data = {
        "dexes": {
            "targets": ["heaven", "pumpswap", "raydium"],
            "network": "solana"
        },
        "intervals": {
            "top_pools_monitoring": "30m",
            "ohlcv_collection": "15m",
            "trade_collection": "5m",
            "watchlist_check": "2h"
        },
        "thresholds": {
            "min_trade_volume_usd": 50.0,
            "max_retries": 5,
            "rate_limit_delay": 0.5,
            "backoff_factor": 1.5
        },
        "timeframes": {
            "ohlcv_default": "15m",
            "supported": ["1m", "5m", "15m", "1h", "4h", "1d"]
        },
        "database": {
            "url": "postgresql://gecko:password@localhost:5432/gecko_data",
            "pool_size": 20,
            "echo": False,
            "timeout": 45
        },
        "api": {
            "base_url": "https://api.geckoterminal.com/api/v2",
            "timeout": 45,
            "max_concurrent": 10,
            "rate_limit_delay": 0.8
        },
        "error_handling": {
            "max_retries": 5,
            "backoff_factor": 2.5,
            "circuit_breaker_threshold": 10,
            "circuit_breaker_timeout": 600
        },
        "watchlist": {
            "file_path": "production_watchlist.csv",
            "check_interval": "30m",
            "auto_add_new_tokens": True,
            "remove_inactive_tokens": False
        }
    }
    
    try:
        config = CollectionConfigValidator(**config_data)
        print("✓ Comprehensive configuration validated successfully")
        print(f"  Monitoring {len(config.dexes.targets)} DEXes on {config.dexes.network}")
        print(f"  OHLCV collection every {config.intervals.ohlcv_collection}")
        print(f"  Trade collection every {config.intervals.trade_collection}")
        print(f"  Database: {config.database.url.split('@')[0]}@***")
        print(f"  API concurrency: {config.api.max_concurrent} requests")
        print(f"  Watchlist: {config.watchlist.file_path}")
        
        # Show validation works
        validation_errors = []
        if config.timeframes.ohlcv_default not in config.timeframes.supported:
            validation_errors.append("Default timeframe not in supported list")
        
        if not validation_errors:
            print("✓ All validation checks passed")
        else:
            print(f"✗ Validation issues: {validation_errors}")
            
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
    
    print()


def main():
    """Run all configuration demonstrations."""
    print("GeckoTerminal Configuration System Demo")
    print("=" * 50)
    print()
    
    demo_basic_config_loading()
    demo_environment_overrides()
    demo_validation()
    demo_config_conversion()
    demo_comprehensive_config()
    
    print("Demo completed! Check the config.yaml file that was created.")


if __name__ == "__main__":
    main()