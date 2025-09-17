#!/usr/bin/env python3
"""
Test script for the new pools signal analysis system.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_signal_analyzer():
    """Test the signal analyzer with mock data."""
    from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer
    
    print("🧪 Testing Signal Analyzer...")
    print("-" * 50)
    
    # Initialize analyzer
    config = {
        'volume_spike_threshold': 2.0,
        'liquidity_growth_threshold': 1.5,
        'momentum_lookback_hours': 6,
        'min_signal_score': 60.0,
        'auto_watchlist_threshold': 75.0
    }
    
    analyzer = NewPoolsSignalAnalyzer(config)
    
    # Test case 1: High volume spike
    print("Test 1: High Volume Spike Pool")
    current_data_1 = {
        'volume_usd_h24': 50000,
        'reserve_in_usd': 100000,
        'price_change_percentage_h1': 15.5,
        'price_change_percentage_h24': 25.0,
        'transactions_h1_buys': 80,
        'transactions_h1_sells': 20,
        'transactions_h24_buys': 400,
        'transactions_h24_sells': 100
    }
    
    historical_data_1 = [
        {'volume_usd_h24': 10000, 'reserve_in_usd': 80000, 'price_change_percentage_h1': 2.0, 'price_change_percentage_h24': 5.0},
        {'volume_usd_h24': 12000, 'reserve_in_usd': 85000, 'price_change_percentage_h1': 1.5, 'price_change_percentage_h24': 3.0},
        {'volume_usd_h24': 8000, 'reserve_in_usd': 75000, 'price_change_percentage_h1': -1.0, 'price_change_percentage_h24': 1.0}
    ]
    
    result_1 = analyzer.analyze_pool_signals(current_data_1, historical_data_1)
    print(f"  Signal Score: {result_1.signal_score:.1f}")
    print(f"  Volume Trend: {result_1.volume_trend}")
    print(f"  Liquidity Trend: {result_1.liquidity_trend}")
    print(f"  Should add to watchlist: {analyzer.should_add_to_watchlist(result_1)}")
    print()
    
    # Test case 2: Stable pool (low signals)
    print("Test 2: Stable Pool (Low Signals)")
    current_data_2 = {
        'volume_usd_h24': 1000,
        'reserve_in_usd': 50000,
        'price_change_percentage_h1': 0.5,
        'price_change_percentage_h24': 1.0,
        'transactions_h1_buys': 5,
        'transactions_h1_sells': 5,
        'transactions_h24_buys': 50,
        'transactions_h24_sells': 50
    }
    
    historical_data_2 = [
        {'volume_usd_h24': 1200, 'reserve_in_usd': 48000, 'price_change_percentage_h1': 0.2, 'price_change_percentage_h24': 0.8},
        {'volume_usd_h24': 900, 'reserve_in_usd': 52000, 'price_change_percentage_h1': -0.1, 'price_change_percentage_h24': 0.5}
    ]
    
    result_2 = analyzer.analyze_pool_signals(current_data_2, historical_data_2)
    print(f"  Signal Score: {result_2.signal_score:.1f}")
    print(f"  Volume Trend: {result_2.volume_trend}")
    print(f"  Liquidity Trend: {result_2.liquidity_trend}")
    print(f"  Should add to watchlist: {analyzer.should_add_to_watchlist(result_2)}")
    print()
    
    # Test case 3: New pool (no historical data)
    print("Test 3: New Pool (No Historical Data)")
    current_data_3 = {
        'volume_usd_h24': 25000,
        'reserve_in_usd': 200000,
        'price_change_percentage_h1': 8.0,
        'price_change_percentage_h24': 12.0,
        'transactions_h1_buys': 60,
        'transactions_h1_sells': 15,
        'transactions_h24_buys': 300,
        'transactions_h24_sells': 80
    }
    
    result_3 = analyzer.analyze_pool_signals(current_data_3, [])
    print(f"  Signal Score: {result_3.signal_score:.1f}")
    print(f"  Volume Trend: {result_3.volume_trend}")
    print(f"  Liquidity Trend: {result_3.liquidity_trend}")
    print(f"  Should add to watchlist: {analyzer.should_add_to_watchlist(result_3)}")
    print()
    
    print("✅ Signal Analyzer tests completed!")
    return True


async def test_enhanced_collector():
    """Test the enhanced new pools collector with signal analysis."""
    from gecko_terminal_collector.config.manager import ConfigManager
    from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
    from gecko_terminal_collector.collectors.new_pools_collector import NewPoolsCollector
    
    print("🔄 Testing Enhanced New Pools Collector...")
    print("-" * 50)
    
    try:
        # Load configuration
        config_manager = ConfigManager('config.yaml')
        config = config_manager.load_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Initialize collector
        collector = NewPoolsCollector(config, db_manager, 'solana')
        
        print(f"✅ Collector initialized successfully")
        print(f"  Signal analysis enabled: {collector.signal_analysis_enabled}")
        print(f"  Auto-watchlist enabled: {collector.auto_watchlist_enabled}")
        print(f"  Network: {collector.network}")
        
        await db_manager.close()
        return True
        
    except Exception as e:
        print(f"❌ Collector test failed: {e}")
        return False


async def test_database_methods():
    """Test the new database methods for signal analysis."""
    from gecko_terminal_collector.config.manager import ConfigManager
    from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
    from datetime import datetime, timedelta
    import uuid
    
    print("🗄️  Testing Database Methods...")
    print("-" * 50)
    
    try:
        # Load configuration
        config_manager = ConfigManager('config.yaml')
        config = config_manager.load_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Use unique IDs to avoid conflicts
        test_suffix = str(uuid.uuid4())[:8]
        test_pool_id = f"solana_test_pool_{test_suffix}"
        test_dex_id = f"test_dex_{test_suffix}"
        test_address = f"test_address_{test_suffix}"
        
        # Test pool history retrieval
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        history = await db_manager.get_pool_history(test_pool_id, cutoff_time)
        print(f"✅ get_pool_history: Retrieved {len(history)} records")
        
        # Test watchlist check
        in_watchlist = await db_manager.is_pool_in_watchlist(test_pool_id)
        print(f"✅ is_pool_in_watchlist: {in_watchlist}")
        
        # Test watchlist addition (with test data)
        if not in_watchlist:
            # First create a test pool to satisfy foreign key constraint
            from gecko_terminal_collector.database.models import Pool as PoolModel
            from gecko_terminal_collector.database.models import DEX as DEXModel
            
            test_pool = PoolModel(
                id=test_pool_id,
                address=test_address,
                name='Test Pool',
                dex_id=test_dex_id
            )
            
            # Create test DEX first
            test_dex = DEXModel(
                id=test_dex_id,
                name='Test DEX',
                network='solana'
            )
            
            with db_manager.connection.get_session() as session:
                try:
                    # Add DEX and pool
                    session.add(test_dex)
                    session.add(test_pool)
                    session.commit()
                    
                    test_watchlist_data = {
                        'pool_id': test_pool_id,
                        'token_symbol': 'TEST',
                        'token_name': 'Test Token',
                        'network_address': test_address,
                        'is_active': True,
                        'metadata_json': {
                            'auto_added': True,
                            'signal_score': 85.5,
                            'test_entry': True
                        }
                    }
                    
                    await db_manager.add_to_watchlist(test_watchlist_data)
                    print(f"✅ add_to_watchlist: Added test entry")
                    
                    # Verify it was added
                    in_watchlist_after = await db_manager.is_pool_in_watchlist(test_pool_id)
                    print(f"✅ Verification: Pool now in watchlist: {in_watchlist_after}")
                    
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    # Clean up test data
                    try:
                        # Remove from watchlist first (due to foreign key constraints)
                        from gecko_terminal_collector.database.models import WatchlistEntry
                        session.query(WatchlistEntry).filter_by(pool_id=test_pool_id).delete()
                        # Remove test pool
                        session.query(PoolModel).filter_by(id=test_pool_id).delete()
                        # Remove test DEX
                        session.query(DEXModel).filter_by(id=test_dex_id).delete()
                        session.commit()
                        print(f"✅ Cleanup: Removed test data")
                    except Exception as cleanup_error:
                        print(f"⚠️  Cleanup warning: {cleanup_error}")
                        session.rollback()
        
        await db_manager.close()
        return True
        
    except Exception as e:
        print(f"❌ Database methods test failed: {e}")
        return False


async def test_cli_commands():
    """Test the new CLI commands."""
    import subprocess
    import sys
    
    print("⚡ Testing CLI Commands...")
    print("-" * 50)
    
    try:
        # Test analyze-pool-signals command help
        result = subprocess.run([
            sys.executable, '-m', 'gecko_terminal_collector.cli',
            'analyze-pool-signals', '--help'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ analyze-pool-signals command help works")
        else:
            print(f"❌ analyze-pool-signals help failed: {result.stderr}")
        
        # Test monitor-pool-signals command help
        result = subprocess.run([
            sys.executable, '-m', 'gecko_terminal_collector.cli',
            'monitor-pool-signals', '--help'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ monitor-pool-signals command help works")
        else:
            print(f"❌ monitor-pool-signals help failed: {result.stderr}")
        
        return True
        
    except Exception as e:
        print(f"❌ CLI commands test failed: {e}")
        return False


async def run_comprehensive_test():
    """Run comprehensive test of the signal analysis system."""
    print("🚀 Starting Comprehensive Signal Analysis System Test")
    print("=" * 60)
    
    test_results = []
    
    # Test 1: Signal Analyzer
    try:
        result = await test_signal_analyzer()
        test_results.append(("Signal Analyzer", result))
    except Exception as e:
        print(f"❌ Signal Analyzer test failed: {e}")
        test_results.append(("Signal Analyzer", False))
    
    print()
    
    # Test 2: Enhanced Collector
    try:
        result = await test_enhanced_collector()
        test_results.append(("Enhanced Collector", result))
    except Exception as e:
        print(f"❌ Enhanced Collector test failed: {e}")
        test_results.append(("Enhanced Collector", False))
    
    print()
    
    # Test 3: Database Methods
    try:
        result = await test_database_methods()
        test_results.append(("Database Methods", result))
    except Exception as e:
        print(f"❌ Database Methods test failed: {e}")
        test_results.append(("Database Methods", False))
    
    print()
    
    # Test 4: CLI Commands
    try:
        result = await test_cli_commands()
        test_results.append(("CLI Commands", result))
    except Exception as e:
        print(f"❌ CLI Commands test failed: {e}")
        test_results.append(("CLI Commands", False))
    
    # Print summary
    print()
    print("📊 Test Summary")
    print("=" * 30)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<20} {status}")
        if result:
            passed += 1
    
    print("-" * 30)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Signal analysis system is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_comprehensive_test())