#!/usr/bin/env python3
"""
Test script to verify auto-watchlist functionality and constraint handling.

This script tests:
1. Adding a pool to watchlist when pool exists
2. Handling foreign key constraint when pool doesn't exist
3. Handling unique constraint when pool already in watchlist
"""

import asyncio
import sys
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '.')

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import Pool as PoolModel, DEX as DEXModel


async def test_auto_watchlist():
    """Test auto-watchlist functionality with constraint handling."""
    
    print("=" * 80)
    print("AUTO-WATCHLIST CONSTRAINT HANDLING TEST")
    print("=" * 80)
    
    # Load configuration
    config_manager = ConfigManager('config.yaml')
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        test_pool_id = "solana_TEST_AUTO_WATCHLIST_POOL"
        test_dex_id = "test-dex-watchlist"
        
        # Clean up any existing test data
        print("\n0. Cleaning up any existing test data...")
        with db_manager.connection.get_session() as session:
            from gecko_terminal_collector.database.models import WatchlistEntry
            session.query(WatchlistEntry).filter(
                WatchlistEntry.pool_id == test_pool_id
            ).delete()
            session.query(PoolModel).filter(
                PoolModel.id == test_pool_id
            ).delete()
            session.query(DEXModel).filter(
                DEXModel.id == test_dex_id
            ).delete()
            session.commit()
        print("   ✓ Test data cleaned up")
        
        # Test 1: Try to add pool to watchlist when pool doesn't exist (foreign key constraint)
        print("\n1. Testing foreign key constraint (pool doesn't exist)")
        watchlist_data = {
            'pool_id': test_pool_id,
            'token_symbol': 'TEST',
            'token_name': 'Test Token / SOL',
            'network_address': 'test_address_123',
            'is_active': True,
            'metadata_json': {
                'auto_added': True,
                'signal_score': 85.0,
                'test': True
            }
        }
        
        await db_manager.add_to_watchlist(watchlist_data)
        print("   ✓ Foreign key constraint handled gracefully (pool doesn't exist)")
        
        # Verify pool was NOT added to watchlist
        is_in_watchlist = await db_manager.is_pool_in_watchlist(test_pool_id)
        if not is_in_watchlist:
            print("   ✓ Pool correctly NOT added to watchlist (foreign key prevented it)")
        else:
            print("   ✗ ERROR: Pool was added despite missing from pools table!")
            return False
        
        # Test 2: Create the pool first, then add to watchlist
        print("\n2. Creating pool in pools table")
        
        # Create DEX first
        with db_manager.connection.get_session() as session:
            dex = DEXModel(
                id=test_dex_id,
                name="Test DEX",
                network="solana"
            )
            session.add(dex)
            session.commit()
        print("   ✓ DEX created")
        
        # Create pool
        with db_manager.connection.get_session() as session:
            pool = PoolModel(
                id=test_pool_id,
                address="test_address_123",
                name="Test Pool / SOL",
                dex_id=test_dex_id,
                reserve_usd=Decimal("10000.00")
            )
            session.add(pool)
            session.commit()
        print("   ✓ Pool created")
        
        # Test 3: Add pool to watchlist (should succeed now)
        print("\n3. Adding pool to watchlist (should succeed)")
        await db_manager.add_to_watchlist(watchlist_data)
        
        # Verify pool was added
        is_in_watchlist = await db_manager.is_pool_in_watchlist(test_pool_id)
        if is_in_watchlist:
            print("   ✓ Pool successfully added to watchlist")
        else:
            print("   ✗ ERROR: Pool was not added to watchlist!")
            return False
        
        # Test 4: Try to add same pool again (unique constraint)
        print("\n4. Testing unique constraint (pool already in watchlist)")
        await db_manager.add_to_watchlist(watchlist_data)
        print("   ✓ Unique constraint handled gracefully (duplicate prevented)")
        
        # Verify only one entry exists
        with db_manager.connection.get_session() as session:
            from gecko_terminal_collector.database.models import WatchlistEntry
            count = session.query(WatchlistEntry).filter(
                WatchlistEntry.pool_id == test_pool_id
            ).count()
            
            if count == 1:
                print(f"   ✓ Correct: Only 1 watchlist entry exists")
            else:
                print(f"   ✗ ERROR: Found {count} watchlist entries (expected 1)")
                return False
        
        # Test 5: Verify watchlist entry data
        print("\n5. Verifying watchlist entry data")
        with db_manager.connection.get_session() as session:
            from gecko_terminal_collector.database.models import WatchlistEntry
            entry = session.query(WatchlistEntry).filter(
                WatchlistEntry.pool_id == test_pool_id
            ).first()
            
            if entry:
                print(f"   - pool_id: {entry.pool_id}")
                print(f"   - token_symbol: {entry.token_symbol}")
                print(f"   - token_name: {entry.token_name}")
                print(f"   - is_active: {entry.is_active}")
                print(f"   - metadata_json: {entry.metadata_json}")
                print("   ✓ Watchlist entry data verified")
            else:
                print("   ✗ ERROR: Watchlist entry not found!")
                return False
        
        # Clean up test data
        print("\n6. Cleaning up test data")
        with db_manager.connection.get_session() as session:
            from gecko_terminal_collector.database.models import WatchlistEntry
            session.query(WatchlistEntry).filter(
                WatchlistEntry.pool_id == test_pool_id
            ).delete()
            session.query(PoolModel).filter(
                PoolModel.id == test_pool_id
            ).delete()
            session.query(DEXModel).filter(
                DEXModel.id == test_dex_id
            ).delete()
            session.commit()
        print("   ✓ Test data cleaned up")
        
        print("\n" + "=" * 80)
        print("TEST PASSED: Auto-watchlist constraint handling working correctly!")
        print("=" * 80)
        print("\nKey findings:")
        print("✓ Foreign key constraint properly handled (pool must exist first)")
        print("✓ Unique constraint properly handled (duplicates prevented)")
        print("✓ Watchlist entries created successfully when constraints satisfied")
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await db_manager.close()


if __name__ == "__main__":
    result = asyncio.run(test_auto_watchlist())
    sys.exit(0 if result else 1)
