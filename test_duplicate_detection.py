#!/usr/bin/env python3
"""
Test script to verify duplicate detection in new_pools_history.

This script tests that the duplicate detection logic correctly identifies
and skips records with identical data fields.
"""

import asyncio
import sys
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '.')

from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.models import NewPoolsHistory


async def test_duplicate_detection():
    """Test duplicate detection in store_new_pools_history."""
    
    print("=" * 80)
    print("DUPLICATE DETECTION TEST")
    print("=" * 80)
    
    # Load configuration
    config_manager = ConfigManager('config.yaml')
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Create a test pool ID
        test_pool_id = "solana_TEST_DUPLICATE_DETECTION_POOL"
        
        print(f"\n1. Creating first history record for pool: {test_pool_id}")
        
        # Create first record
        record1 = NewPoolsHistory(
            pool_id=test_pool_id,
            name="Test Pool / SOL",
            reserve_in_usd=Decimal("1000.50"),
            transactions_h1_buys=10,
            transactions_h1_sells=5,
            transactions_h24_buys=100,
            transactions_h24_sells=50,
            volume_usd_h24=Decimal("5000.00"),
            dex_id="test-dex",
            network_id="solana",
            collected_at=datetime.now()
        )
        
        await db_manager.store_new_pools_history(record1)
        print("   ✓ First record stored successfully")
        
        print("\n2. Attempting to store duplicate record (same data, different timestamp)")
        
        # Create duplicate record with same data
        record2 = NewPoolsHistory(
            pool_id=test_pool_id,
            name="Test Pool / SOL",
            reserve_in_usd=Decimal("1000.50"),  # Same
            transactions_h1_buys=10,  # Same
            transactions_h1_sells=5,  # Same
            transactions_h24_buys=100,  # Same
            transactions_h24_sells=50,  # Same
            volume_usd_h24=Decimal("5000.00"),  # Same
            dex_id="test-dex",
            network_id="solana",
            collected_at=datetime.now()  # Different timestamp
        )
        
        await db_manager.store_new_pools_history(record2)
        print("   ✓ Duplicate record was correctly skipped")
        
        print("\n3. Attempting to store record with changed data")
        
        # Create record with different data
        record3 = NewPoolsHistory(
            pool_id=test_pool_id,
            name="Test Pool / SOL",
            reserve_in_usd=Decimal("1500.75"),  # Changed
            transactions_h1_buys=15,  # Changed
            transactions_h1_sells=8,  # Changed
            transactions_h24_buys=120,  # Changed
            transactions_h24_sells=60,  # Changed
            volume_usd_h24=Decimal("7500.00"),  # Changed
            dex_id="test-dex",
            network_id="solana",
            collected_at=datetime.now()
        )
        
        await db_manager.store_new_pools_history(record3)
        print("   ✓ Record with changed data stored successfully")
        
        print("\n4. Verifying records in database")
        
        # Query records
        with db_manager.connection.get_session() as session:
            records = session.query(NewPoolsHistory).filter(
                NewPoolsHistory.pool_id == test_pool_id
            ).order_by(NewPoolsHistory.collected_at).all()
            
            print(f"   Total records found: {len(records)}")
            print(f"   Expected: 2 (first record + changed data record)")
            
            if len(records) == 2:
                print("   ✓ Correct number of records stored")
                print("\n   Record 1:")
                print(f"      - reserve_in_usd: {records[0].reserve_in_usd}")
                print(f"      - transactions_h1_buys: {records[0].transactions_h1_buys}")
                print(f"      - volume_usd_h24: {records[0].volume_usd_h24}")
                print("\n   Record 2:")
                print(f"      - reserve_in_usd: {records[1].reserve_in_usd}")
                print(f"      - transactions_h1_buys: {records[1].transactions_h1_buys}")
                print(f"      - volume_usd_h24: {records[1].volume_usd_h24}")
            else:
                print(f"   ✗ Unexpected number of records: {len(records)}")
                return False
        
        print("\n5. Cleaning up test data")
        
        # Clean up test records
        with db_manager.connection.get_session() as session:
            session.query(NewPoolsHistory).filter(
                NewPoolsHistory.pool_id == test_pool_id
            ).delete()
            session.commit()
            print("   ✓ Test data cleaned up")
        
        print("\n" + "=" * 80)
        print("TEST PASSED: Duplicate detection working correctly!")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await db_manager.close()


if __name__ == "__main__":
    result = asyncio.run(test_duplicate_detection())
    sys.exit(0 if result else 1)
