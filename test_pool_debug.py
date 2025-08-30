import asyncio
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
from gecko_terminal_collector.utils.watchlist_processor import WatchlistProcessor

async def test_pool_storage():
    # Load config
    manager = ConfigManager('config.yaml')
    config = manager.load_config()
    
    # Initialize database
    db_manager = SQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    # Load watchlist
    watchlist_processor = WatchlistProcessor(config)
    watchlist_items = await watchlist_processor.load_watchlist('specs/watchlist.csv')
    
    if not watchlist_items:
        print("No watchlist items found")
        return
    
    item = watchlist_items[0]  # Get the CBRL item
    print(f"Testing with item: {item}")
    
    # Collect token data
    collector = WatchlistCollector(config, db_manager)
    result = await collector.collect_single_item(item)
    
    print(f"Collection result: success={result.success}, records={result.records_collected}")
    if result.errors:
        print(f"Errors: {result.errors}")
    
    # Check what pools are in the database
    pool_id = item.get('poolAddress')
    print(f"Looking for pool ID: {pool_id}")
    
    # Query the database directly
    pool = await db_manager.get_pool(pool_id)
    if pool:
        print(f"Found pool in database: id={pool.id}, name={pool.name}")
    else:
        print("Pool not found in database!")
        
        # Check all pools in database using the database manager
        try:
            all_pools = await db_manager.get_all_pools()
            print(f"Total pools in database: {len(all_pools)}")
            for p in all_pools[:5]:  # Show first 5
                print(f"  Pool: id={p.id}, name={p.name}")
        except Exception as e:
            print(f"Error getting all pools: {e}")
            # Try a different approach
            print("Trying alternative method...")
            pools_count = await db_manager.count_records('pools')
            print(f"Pools table has {pools_count} records")
    
    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(test_pool_storage())