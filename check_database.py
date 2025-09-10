#!/usr/bin/env python3
import asyncio
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager

async def check_database():
    manager = ConfigManager('config.yaml')
    config = manager.load_config()
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    # Check if the test pool exists
    test_pool_id = 'solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP'
    test_pool = await db_manager.get_pool(test_pool_id)
    print(f'Test pool {test_pool_id} exists: {test_pool is not None}')
    
    # Check another pool ID format
    test_pool_id2 = '7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP'
    test_pool2 = await db_manager.get_pool(test_pool_id2)
    print(f'Test pool {test_pool_id2} exists: {test_pool2 is not None}')
    
    # Check watchlist pools
    watchlist_pools = await db_manager.get_watchlist_pools()
    print(f'Found {len(watchlist_pools)} watchlist pools')
    for pool_id in watchlist_pools[:5]:
        print(f'  Watchlist pool: {pool_id}')
    
    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(check_database())