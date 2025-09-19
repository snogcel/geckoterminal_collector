#!/usr/bin/env python3
"""
Collect historical OHLCV data for active watchlist symbols.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from gecko_terminal_collector.collectors.historical_ohlcv_collector import HistoricalOHLCVCollector
from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.utils.metadata import MetadataTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def collect_historical_data():
    """Collect historical OHLCV data for all active watchlist symbols."""
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    # Initialize metadata tracker
    metadata_tracker = MetadataTracker(db_manager)
    
    # Initialize historical OHLCV collector
    collector = HistoricalOHLCVCollector(
        config=config,
        db_manager=db_manager,
        metadata_tracker=metadata_tracker,
        use_mock=False  # Set to True for testing
    )
    
    try:
        # Get active watchlist entries
        print("Getting active watchlist entries...")
        entries = await db_manager.get_active_watchlist_entries()
        pool_ids = await db_manager.get_watchlist_pools()
        
        print(f"Found {len(entries)} active watchlist entries:")
        for entry in entries:
            print(f"  - {entry.token_symbol} ({entry.pool_id})")
        
        print(f"\nPool IDs for collection: {pool_ids}")
        
        # Collect historical data for all pools
        print("\n" + "="*60)
        print("STARTING HISTORICAL OHLCV DATA COLLECTION")
        print("="*60)
        
        result = await collector.collect()
        
        print("\n" + "="*60)
        print("COLLECTION RESULTS")
        print("="*60)
        print(f"Success: {result.success}")
        print(f"Records collected: {result.records_collected}")
        print(f"Errors: {len(result.errors)}")
        
        if result.errors:
            print("\nErrors encountered:")
            for error in result.errors:
                print(f"  - {error}")
        
        # Show collection statistics
        if hasattr(collector, '_collection_stats'):
            stats = collector._collection_stats
            print(f"\nCollection Statistics:")
            print(f"  Total requests: {stats['total_requests']}")
            print(f"  Successful requests: {stats['successful_requests']}")
            print(f"  Failed requests: {stats['failed_requests']}")
            print(f"  Total records: {stats['total_records']}")
            
            if stats['total_requests'] > 0:
                success_rate = (stats['successful_requests'] / stats['total_requests']) * 100
                print(f"  Success rate: {success_rate:.1f}%")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in historical data collection: {e}", exc_info=True)
        raise
    finally:
        await db_manager.close()

async def collect_for_specific_pool(pool_id: str, timeframe: str = "1h", days_back: int = 30):
    """
    Collect historical data for a specific pool.
    
    Args:
        pool_id: Pool ID (without network prefix)
        timeframe: Data timeframe (1m, 5m, 15m, 1h, 4h, 12h, 1d)
        days_back: Number of days to collect data for
    """
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    # Initialize metadata tracker
    metadata_tracker = MetadataTracker(db_manager)
    
    # Initialize historical OHLCV collector
    collector = HistoricalOHLCVCollector(
        config=config,
        db_manager=db_manager,
        metadata_tracker=metadata_tracker,
        use_mock=False
    )
    
    try:
        # Set date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        print(f"Collecting historical data for pool: {pool_id}")
        print(f"Timeframe: {timeframe}")
        print(f"Date range: {start_date.date()} to {end_date.date()}")
        
        # Collect data for specific pool
        result = await collector.collect_for_pool(
            pool_id=pool_id,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            force_refresh=False
        )
        
        print(f"\nCollection completed:")
        print(f"Success: {result.success}")
        print(f"Records collected: {result.records_collected}")
        
        if result.errors:
            print("Errors:")
            for error in result.errors:
                print(f"  - {error}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error collecting data for pool {pool_id}: {e}", exc_info=True)
        raise
    finally:
        await db_manager.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Collect for specific pool
        pool_id = sys.argv[1]
        timeframe = sys.argv[2] if len(sys.argv) > 2 else "1h"
        days_back = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        
        print(f"Collecting historical data for specific pool: {pool_id}")
        asyncio.run(collect_for_specific_pool(pool_id, timeframe, days_back))
    else:
        # Collect for all watchlist pools
        print("Collecting historical data for all active watchlist pools...")
        asyncio.run(collect_historical_data())