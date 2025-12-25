#!/usr/bin/env python3
"""
Test script to verify Enhanced Watchlist Collector integration with scheduler.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all required imports work."""
    print("Testing imports...")
    
    try:
        from gecko_terminal_collector.collectors.enhanced_watchlist_collector import EnhancedWatchlistCollector
        print("✓ EnhancedWatchlistCollector import successful")
    except ImportError as e:
        print(f"✗ EnhancedWatchlistCollector import failed: {e}")
        return False
    
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        print("✓ ConfigManager import successful")
    except ImportError as e:
        print(f"✗ ConfigManager import failed: {e}")
        return False
    
    try:
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        print("✓ SQLAlchemyDatabaseManager import successful")
    except ImportError as e:
        print(f"✗ SQLAlchemyDatabaseManager import failed: {e}")
        return False
    
    return True

def test_config_loading():
    """Test configuration loading with enhanced watchlist."""
    print("\nTesting configuration loading...")
    
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        print("✓ Configuration loaded successfully")
        
        # Check if enhanced watchlist config exists
        if hasattr(config, 'enhanced_watchlist'):
            print("✓ Enhanced watchlist configuration found")
            print(f"  Enabled: {config.enhanced_watchlist.enabled}")
            print(f"  Interval: {config.enhanced_watchlist.interval}")
            print(f"  Sources: {config.enhanced_watchlist.sources}")
        else:
            print("✗ Enhanced watchlist configuration not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
        return False

def test_collector_initialization():
    """Test enhanced watchlist collector initialization."""
    print("\nTesting collector initialization...")
    
    try:
        from gecko_terminal_collector.collectors.enhanced_watchlist_collector import EnhancedWatchlistCollector
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.utils.metadata import MetadataTracker
        
        # Load config
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Create mock database manager (don't actually connect)
        print("✓ Configuration loaded for collector test")
        
        # Test collector creation with mock
        collector = EnhancedWatchlistCollector(
            config=config,
            db_manager=None,  # Mock - don't actually connect
            metadata_tracker=None,  # Mock
            use_mock=True,
            watchlist_sources=['reference']
        )
        
        print("✓ Enhanced watchlist collector created successfully")
        print(f"  Available sources: {collector.available_sources}")
        print(f"  Sources to collect: {collector.sources_to_collect}")
        print(f"  Rate limit delay: {collector.rate_limit_delay}")
        print(f"  Batch size: {collector.batch_size}")
        
        return True
        
    except Exception as e:
        print(f"✗ Collector initialization failed: {e}")
        return False

def test_scheduler_cli_structure():
    """Test that the CLI structure is correct."""
    print("\nTesting CLI structure...")
    
    try:
        # Read the CLI file and check for enhanced watchlist integration
        cli_file = Path("examples/cli_with_scheduler.py")
        
        if not cli_file.exists():
            print("✗ CLI scheduler file not found")
            return False
        
        content = cli_file.read_text(encoding='utf-8')
        
        # Check for enhanced watchlist import
        if "from gecko_terminal_collector.collectors.enhanced_watchlist_collector import EnhancedWatchlistCollector" in content:
            print("✓ Enhanced watchlist collector import found in CLI")
        else:
            print("✗ Enhanced watchlist collector import not found in CLI")
            return False
        
        # Check for enhanced watchlist configuration
        if "enhanced_watchlist_config" in content:
            print("✓ Enhanced watchlist configuration logic found in CLI")
        else:
            print("✗ Enhanced watchlist configuration logic not found in CLI")
            return False
        
        # Check for enhanced watchlist command
        if "collect_enhanced_watchlist" in content or "collect-enhanced-watchlist" in content:
            print("✓ Enhanced watchlist CLI command found")
        else:
            print("✗ Enhanced watchlist CLI command not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ CLI structure test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Enhanced Watchlist Scheduler Integration Test")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_config_loading,
        test_collector_initialization,
        test_scheduler_cli_structure
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print("=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! Enhanced watchlist scheduler integration is ready.")
        print("\nNext steps:")
        print("1. Ensure your config.yaml has enhanced_watchlist section enabled")
        print("2. Create your source CSV files (watchlist_updated_*.csv)")
        print("3. Run: python create_enhanced_watchlist_table.py")
        print("4. Test with: python -m examples.cli_with_scheduler collect-enhanced-watchlist --mock")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())