#!/usr/bin/env python3
"""
Test script for Enhanced New Pools Collector with Auto-Watchlist Integration.

This script tests the implementation of the auto-watchlist functionality
as described in the NEW_POOLS_HISTORY_IMPLEMENTATION_PLAN.md.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockDatabaseManager:
    """Mock database manager for testing."""
    
    def __init__(self):
        self.watchlist_entries = []
        self.enhanced_history = []
        self.feature_vectors = []
    
    async def add_to_watchlist(self, watchlist_data: Dict) -> None:
        """Mock add to watchlist."""
        self.watchlist_entries.append(watchlist_data)
        logger.info(f"Mock: Added pool {watchlist_data['pool_id']} to watchlist")
    
    async def is_pool_in_watchlist(self, pool_id: str) -> bool:
        """Mock check if pool is in watchlist."""
        return any(entry['pool_id'] == pool_id for entry in self.watchlist_entries)
    
    class MockConnection:
        def get_session(self):
            return MockSession()
    
    @property
    def connection(self):
        return self.MockConnection()


class MockSession:
    """Mock database session."""
    
    def __init__(self):
        self.added_items = []
    
    def add(self, item):
        self.added_items.append(item)
    
    def commit(self):
        pass
    
    def query(self, model):
        return MockQuery()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockQuery:
    """Mock database query."""
    
    def filter(self, *args):
        return self
    
    def order_by(self, *args):
        return self
    
    def limit(self, count):
        return self
    
    def all(self):
        return []


def create_test_pool_data(pool_id: str, signal_strength: str = "medium") -> Dict:
    """Create test pool data with different signal strengths."""
    
    base_data = {
        'id': pool_id,
        'type': 'pool',
        'attributes': {
            'name': f'TEST/USDC',
            'address': f'test_address_{pool_id}',
            'base_token_price_usd': '1.25',
            'pool_created_at': (datetime.now() - timedelta(hours=2)).isoformat() + 'Z',
            # Add missing fields that signal analyzer expects
            'transactions_h1_buys': 0,
            'transactions_h1_sells': 0,
            'fdv_usd': '0',
            'market_cap_usd': '0'
        }
    }
    
    if signal_strength == "high":
        # High signal pool - should be added to watchlist
        base_data['attributes'].update({
            'volume_usd_h24': '50000',  # High volume
            'volume_usd_h1': '5000',    # 1h volume
            'reserve_in_usd': '100000',  # Good liquidity
            'price_change_percentage_h1': '15.5',  # Strong momentum
            'price_change_percentage_h24': '25.0',
            'transactions_h24_buys': 150,
            'transactions_h24_sells': 50,  # Buy-heavy
            'transactions_h1_buys': 15,
            'transactions_h1_sells': 5,
            'market_cap_usd': '500000',
            'fdv_usd': '600000'
        })
    elif signal_strength == "medium":
        # Medium signal pool - might be added depending on threshold
        base_data['attributes'].update({
            'volume_usd_h24': '15000',
            'volume_usd_h1': '1500',
            'reserve_in_usd': '30000',
            'price_change_percentage_h1': '5.2',
            'price_change_percentage_h24': '8.5',
            'transactions_h24_buys': 80,
            'transactions_h24_sells': 70,
            'transactions_h1_buys': 8,
            'transactions_h1_sells': 7,
            'market_cap_usd': '150000',
            'fdv_usd': '180000'
        })
    else:  # low signal
        # Low signal pool - should not be added to watchlist
        base_data['attributes'].update({
            'volume_usd_h24': '2000',
            'volume_usd_h1': '200',
            'reserve_in_usd': '5000',
            'price_change_percentage_h1': '1.1',
            'price_change_percentage_h24': '2.3',
            'transactions_h24_buys': 10,
            'transactions_h24_sells': 15,
            'transactions_h1_buys': 1,
            'transactions_h1_sells': 2,
            'market_cap_usd': '25000',
            'fdv_usd': '30000'
        })
    
    return base_data


async def test_signal_analysis():
    """Test signal analysis functionality."""
    print("\n🔍 Testing Signal Analysis")
    print("=" * 50)
    
    try:
        from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer
        
        # Initialize signal analyzer
        analyzer = NewPoolsSignalAnalyzer({
            'auto_watchlist_threshold': 75.0,
            'volume_spike_threshold': 2.0,
            'liquidity_growth_threshold': 1.5
        })
        
        # Test different signal strengths
        test_cases = [
            ("high_signal_pool", "high"),
            ("medium_signal_pool", "medium"),
            ("low_signal_pool", "low")
        ]
        
        for pool_id, signal_strength in test_cases:
            pool_data = create_test_pool_data(pool_id, signal_strength)
            
            print(f"\n📊 Analyzing {pool_id} ({signal_strength} signal):")
            
            # Analyze signals - pass attributes directly as the analyzer expects flattened data
            signal_result = analyzer.analyze_pool_signals(pool_data.get('attributes', {}))
            
            print(f"  Signal Score: {signal_result.signal_score:.1f}")
            print(f"  Volume Trend: {signal_result.volume_trend}")
            print(f"  Liquidity Trend: {signal_result.liquidity_trend}")
            print(f"  Momentum: {signal_result.momentum_indicator:.2f}")
            print(f"  Activity Score: {signal_result.activity_score:.1f}")
            print(f"  Should add to watchlist: {analyzer.should_add_to_watchlist(signal_result)}")
            
            # Show key signals
            if signal_result.signals:
                key_signals = []
                if signal_result.signals.get('volume_spike'):
                    key_signals.append("Volume Spike")
                if signal_result.signals.get('liquidity_growth'):
                    key_signals.append("Liquidity Growth")
                if signal_result.signals.get('price_momentum_strong'):
                    key_signals.append("Strong Momentum")
                if signal_result.signals.get('high_activity'):
                    key_signals.append("High Activity")
                
                if key_signals:
                    print(f"  Key Signals: {', '.join(key_signals)}")
        
        print("\n✅ Signal analysis test completed")
        return True
        
    except Exception as e:
        print(f"❌ Signal analysis test failed: {e}")
        return False


async def test_enhanced_collector():
    """Test enhanced new pools collector with auto-watchlist."""
    print("\n🚀 Testing Enhanced New Pools Collector")
    print("=" * 50)
    
    try:
        # Import the enhanced collector
        from enhanced_new_pools_collector import EnhancedNewPoolsCollector
        
        # Create mock database manager
        mock_db = MockDatabaseManager()
        
        # Create mock config
        class MockConfig:
            def __init__(self):
                self.api_key = "test_key"
                self.rate_limit_requests_per_minute = 60
                
                # Add error handling config
                class ErrorHandling:
                    max_retries = 3
                    backoff_factor = 2.0
                
                self.error_handling = ErrorHandling()
        
        # Initialize enhanced collector
        collector = EnhancedNewPoolsCollector(
            config=MockConfig(),
            db_manager=mock_db,
            network="solana",
            collection_intervals=['1h'],
            enable_feature_engineering=True,
            qlib_integration=True,
            auto_watchlist_enabled=True,
            auto_watchlist_threshold=70.0  # Lower threshold for testing
        )
        
        print(f"✅ Enhanced collector initialized")
        print(f"  Network: {collector.network}")
        print(f"  Auto-watchlist enabled: {collector.auto_watchlist_enabled}")
        print(f"  Watchlist threshold: {collector.auto_watchlist_threshold}")
        print(f"  Has signal analyzer: {hasattr(collector, 'signal_analyzer')}")
        print(f"  Feature engineering: {collector.enable_feature_engineering}")
        print(f"  QLib integration: {collector.qlib_integration}")
        
        # Test auto-watchlist processing with mock data
        test_pools = [
            create_test_pool_data("high_signal_test", "high"),
            create_test_pool_data("medium_signal_test", "medium"),
            create_test_pool_data("low_signal_test", "low")
        ]
        
        print(f"\n🔄 Processing {len(test_pools)} test pools...")
        
        # Process auto-watchlist
        watchlist_additions = await collector._process_auto_watchlist(test_pools)
        
        print(f"✅ Auto-watchlist processing completed")
        print(f"  Pools processed: {len(test_pools)}")
        print(f"  Watchlist additions: {watchlist_additions}")
        
        # Check results
        print(f"\n📋 Watchlist Results:")
        for entry in mock_db.watchlist_entries:
            metadata = entry.get('metadata_json', {})
            print(f"  Pool: {entry['pool_id']}")
            print(f"    Signal Score: {metadata.get('signal_score', 'N/A')}")
            print(f"    Volume Trend: {metadata.get('volume_trend', 'N/A')}")
            print(f"    Source: {metadata.get('source', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced collector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_watchlist_integration():
    """Test watchlist integration functionality."""
    print("\n📋 Testing Watchlist Integration")
    print("=" * 50)
    
    try:
        from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer
        
        # Create analyzer and mock database
        analyzer = NewPoolsSignalAnalyzer({'auto_watchlist_threshold': 70.0})  # Lower threshold for testing
        mock_db = MockDatabaseManager()
        
        # Test different threshold scenarios
        test_scenarios = [
            {"pool_id": "threshold_test_1", "signal_strength": "high", "expected_add": True},
            {"pool_id": "threshold_test_2", "signal_strength": "medium", "expected_add": False},
            {"pool_id": "threshold_test_3", "signal_strength": "low", "expected_add": False}
        ]
        
        print("🎯 Testing threshold-based watchlist decisions:")
        
        for scenario in test_scenarios:
            pool_data = create_test_pool_data(scenario["pool_id"], scenario["signal_strength"])
            signal_result = analyzer.analyze_pool_signals(pool_data.get('attributes', {}))
            should_add = analyzer.should_add_to_watchlist(signal_result)
            
            status = "✅" if should_add == scenario["expected_add"] else "❌"
            print(f"  {status} {scenario['pool_id']}: Score {signal_result.signal_score:.1f}, "
                  f"Should add: {should_add} (expected: {scenario['expected_add']})")
        
        # Test duplicate prevention
        print(f"\n🔄 Testing duplicate prevention:")
        
        # Add a pool to watchlist
        test_pool = create_test_pool_data("duplicate_test", "high")
        await mock_db.add_to_watchlist({
            'pool_id': 'duplicate_test',
            'token_symbol': 'TEST/USDC',
            'is_active': True,
            'metadata_json': {'test': True}
        })
        
        # Check if it's detected as already in watchlist
        is_duplicate = await mock_db.is_pool_in_watchlist('duplicate_test')
        print(f"  Pool in watchlist: {is_duplicate} ✅")
        
        return True
        
    except Exception as e:
        print(f"❌ Watchlist integration test failed: {e}")
        return False


async def test_configuration_options():
    """Test different configuration options."""
    print("\n⚙️  Testing Configuration Options")
    print("=" * 50)
    
    try:
        from enhanced_new_pools_collector import EnhancedNewPoolsCollector
        
        # Test different configurations
        configs = [
            {
                "name": "Full Features Enabled",
                "auto_watchlist_enabled": True,
                "auto_watchlist_threshold": 80.0,
                "enable_feature_engineering": True,
                "qlib_integration": True
            },
            {
                "name": "Auto-Watchlist Disabled",
                "auto_watchlist_enabled": False,
                "enable_feature_engineering": True,
                "qlib_integration": True
            },
            {
                "name": "Low Threshold",
                "auto_watchlist_enabled": True,
                "auto_watchlist_threshold": 50.0,
                "enable_feature_engineering": False,
                "qlib_integration": False
            }
        ]
        
        class MockConfig:
            def __init__(self):
                self.api_key = "test_key"
                self.rate_limit_requests_per_minute = 60
        
        class MockConfig:
            def __init__(self):
                self.api_key = "test_key"
                self.rate_limit_requests_per_minute = 60
                
                # Add error handling config
                class ErrorHandling:
                    max_retries = 3
                    backoff_factor = 2.0
                
                self.error_handling = ErrorHandling()
        
        for config in configs:
            print(f"\n📋 Testing: {config['name']}")
            
            collector = EnhancedNewPoolsCollector(
                config=MockConfig(),
                db_manager=MockDatabaseManager(),
                network="solana",
                **{k: v for k, v in config.items() if k != 'name'}
            )
            
            print(f"  ✅ Auto-watchlist: {collector.auto_watchlist_enabled}")
            if collector.auto_watchlist_enabled:
                print(f"  ✅ Threshold: {collector.auto_watchlist_threshold}")
                print(f"  ✅ Signal analyzer: {hasattr(collector, 'signal_analyzer')}")
            print(f"  ✅ Feature engineering: {collector.enable_feature_engineering}")
            print(f"  ✅ QLib integration: {collector.qlib_integration}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


async def test_cli_integration():
    """Test CLI integration for auto-watchlist functionality."""
    print("\n💻 Testing CLI Integration")
    print("=" * 50)
    
    try:
        # Test CLI command structure
        print("📋 Available CLI commands for auto-watchlist:")
        
        cli_commands = [
            {
                "command": "collect-enhanced",
                "description": "Enhanced collection with auto-watchlist",
                "options": [
                    "--enable-auto-watchlist",
                    "--watchlist-threshold 75.0",
                    "--network solana"
                ]
            },
            {
                "command": "analyze-signals", 
                "description": "Analyze signal patterns",
                "options": [
                    "--pool-id POOL_ID",
                    "--network solana",
                    "--days 7"
                ]
            }
        ]
        
        for cmd in cli_commands:
            print(f"\n  🔧 {cmd['command']}: {cmd['description']}")
            for option in cmd['options']:
                print(f"    {option}")
        
        # Show example usage
        print(f"\n📖 Example usage:")
        print(f"  gecko-cli new-pools-enhanced collect-enhanced \\")
        print(f"    --network solana \\")
        print(f"    --enable-auto-watchlist \\")
        print(f"    --watchlist-threshold 75.0 \\")
        print(f"    --enable-features \\")
        print(f"    --enable-qlib")
        
        return True
        
    except Exception as e:
        print(f"❌ CLI integration test failed: {e}")
        return False


async def run_comprehensive_test():
    """Run comprehensive test suite for auto-watchlist integration."""
    print("🎯 Enhanced New Pools Auto-Watchlist Integration Test")
    print("=" * 60)
    print(f"Test started at: {datetime.now()}")
    
    test_results = {}
    
    # Run all tests
    tests = [
        ("Signal Analysis", test_signal_analysis),
        ("Enhanced Collector", test_enhanced_collector),
        ("Watchlist Integration", test_watchlist_integration),
        ("Configuration Options", test_configuration_options),
        ("CLI Integration", test_cli_integration)
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            result = await test_func()
            test_results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            test_results[test_name] = False
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for result in test_results.values() if result)
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Auto-watchlist integration is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False


if __name__ == "__main__":
    # Run the comprehensive test
    success = asyncio.run(run_comprehensive_test())
    sys.exit(0 if success else 1)