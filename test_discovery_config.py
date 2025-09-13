#!/usr/bin/env python3
"""
Test script to verify discovery configuration implementation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from decimal import Decimal
from gecko_terminal_collector.config.models import CollectionConfig, DiscoveryConfig


def test_discovery_config_defaults():
    """Test that DiscoveryConfig has proper default values."""
    config = DiscoveryConfig()
    
    assert config.enabled == True
    assert config.min_volume_usd == Decimal("1000")
    assert config.max_pools_per_dex == 100
    assert config.discovery_interval == "6h"
    assert config.activity_threshold == Decimal("100")
    assert config.new_pool_lookback_hours == 24
    assert config.max_total_pools == 1000
    assert config.volume_check_interval == "1h"
    assert config.cleanup_inactive_pools == True
    assert config.cleanup_threshold_days == 7
    assert config.bootstrap_on_startup == True
    assert config.target_networks == ["solana"]
    
    print("✓ DiscoveryConfig defaults test passed")


def test_collection_config_includes_discovery():
    """Test that CollectionConfig includes discovery configuration."""
    config = CollectionConfig()
    
    assert hasattr(config, 'discovery')
    assert isinstance(config.discovery, DiscoveryConfig)
    assert config.discovery.enabled == True
    
    print("✓ CollectionConfig includes discovery test passed")


def test_discovery_config_validation():
    """Test discovery configuration validation."""
    config = CollectionConfig()
    
    # Test valid configuration
    errors = config.validate()
    discovery_errors = [e for e in errors if 'discovery' in e.lower() or 'Discovery' in e]
    assert len(discovery_errors) == 0, f"Valid config should not have discovery errors: {discovery_errors}"
    
    # Test invalid volume
    config.discovery.min_volume_usd = Decimal("-100")
    errors = config.validate()
    assert any("Discovery minimum volume must be non-negative" in e for e in errors)
    
    # Reset and test invalid interval
    config.discovery.min_volume_usd = Decimal("1000")
    config.discovery.discovery_interval = "invalid"
    errors = config.validate()
    assert any("Invalid discovery interval format" in e for e in errors)
    
    # Reset and test invalid max pools
    config.discovery.discovery_interval = "6h"
    config.discovery.max_pools_per_dex = 0
    errors = config.validate()
    assert any("Max pools per DEX must be positive" in e for e in errors)
    
    # Reset and test empty target networks
    config.discovery.max_pools_per_dex = 100
    config.discovery.target_networks = []
    errors = config.validate()
    assert any("At least one target network must be specified" in e for e in errors)
    
    print("✓ Discovery configuration validation test passed")


def test_watchlist_optional():
    """Test that watchlist is now optional."""
    config = CollectionConfig()
    config.watchlist = None
    
    # Should not cause validation errors
    errors = config.validate()
    watchlist_errors = [e for e in errors if 'watchlist' in e.lower()]
    assert len(watchlist_errors) == 0, f"Watchlist being None should not cause errors: {watchlist_errors}"
    
    print("✓ Optional watchlist test passed")


if __name__ == "__main__":
    try:
        test_discovery_config_defaults()
        test_collection_config_includes_discovery()
        test_discovery_config_validation()
        test_watchlist_optional()
        print("\n🎉 All discovery configuration tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)