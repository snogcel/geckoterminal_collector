#!/usr/bin/env python3
"""
Collect historical OHLCV data with better rate limit handling.
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

async def collect_historical_with_delays(
    pool_ids: list = None,
    timeframes: list = None,
    days_back: int = 30,
    delay_between_pools: int = 5,
    delay_between_timeframes: int = 2
):
    """
    Collect historical data with controlled delays to respect rate limits.
    
    Args:
        pool_ids: List of pool IDs to collect for (None = all watchlist)
        timeframes: List of timeframes to collect (None = all supported)
        days_back: Number of days to collect data for
        delay_between_pools: Seconds to wait between pools
        delay_between_timeframes: Seconds to wait between timeframes
    """
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    # Initialize metadata tracker
    metadata_tracker = MetadataTracker(db_manager)
    
    # Initialize historical OHLCV collector with longer delays
    collector = HistoricalOHLCVCollector(
        config=config,
        db_manager=db_manager,
        metadata_tracker=metadata_tracker,
        use_mock=False
    )
    
    # Override pagination delay for better rate limiting
    collector.pagination_delay = 2.0  # 2 seconds between paginated requests
    
    try:
        # Get pool IDs if not specified
        if pool_ids is None:
            entries = await db_manager.get_active_watchlist_entries()
            pool_ids = [entry.pool_id.replace('solana_', '') for entry in entries]
            print(f"Collecting for all {len(pool_ids)} watchlist pools")
        else:
            print(f"Collecting for {len(pool_ids)} specified pools")
        
        # Use default timeframes if not specified
        if timeframes is None:
            timeframes = ['1h', '4h', '1d']  # Start with less frequent timeframes
            print(f"Using timeframes: {timeframes}")
        
        # Set date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        print(f"Date range: {start_date.date()} to {end_date.date()}")
        print(f"Delays: {delay_between_pools}s between pools, {delay_between_timeframes}s between timeframes")
        
        total_collected = 0
        total_errors = []
        
        # Process each pool
        for i, pool_id in enumerate(pool_ids):
            print(f"\n{'='*60}")
            print(f"Processing pool {i+1}/{len(pool_ids)}: {pool_id}")
            print(f"{'='*60}")
            
            pool_collected = 0
            
            # Process each timeframe for this pool
            for j, timeframe in enumerate(timeframes):
                try:
                    print(f"\nCollecting {timeframe} data for {pool_id}...")
                    
                    result = await collector.collect_for_pool(
                        pool_id=pool_id,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        force_refresh=False
                    )
                    
                    if result.success:
                        print(f"✓ Collected {result.records_collected} {timeframe} records")
                        pool_collected += result.records_collected
                        total_collected += result.records_collected
                    else:
                        print(f"✗ Failed to collect {timeframe} data: {result.errors}")
                        total_errors.extend(result.errors)
                    
                    # Delay between timeframes (except for last one)
                    if j < len(timeframes) - 1:
                        print(f"Waiting {delay_between_timeframes}s before next timeframe...")
                        await asyncio.sleep(delay_between_timeframes)
                        
                except Exception as e:
                    error_msg = f"Error collecting {timeframe} data for {pool_id}: {e}"
                    print(f"✗ {error_msg}")
                    total_errors.append(error_msg)
                    continue
            
            print(f"\nPool {pool_id} summary: {pool_collected} records collected")
            
            # Delay between pools (except for last one)
            if i < len(pool_ids) - 1:
                print(f"Waiting {delay_between_pools}s before next pool...")
                await asyncio.sleep(delay_between_pools)
        
        # Final summary
        print(f"\n{'='*60}")
        print(f"COLLECTION COMPLETE")
        print(f"{'='*60}")
        print(f"Total records collected: {total_collected}")
        print(f"Total errors: {len(total_errors)}")
        
        if total_errors:
            print(f"\nErrors encountered:")
            for error in total_errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(total_errors) > 10:
                print(f"  ... and {len(total_errors) - 10} more errors")
        
        return total_collected, total_errors
        
    except Exception as e:
        logger.error(f"Error in controlled historical data collection: {e}", exc_info=True)
        raise
    finally:
        await db_manager.close()

async def collect_missing_timeframes():
    """Collect missing timeframes for pools that have partial data."""
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Get active watchlist entries
        entries = await db_manager.get_active_watchlist_entries()
        
        print("Checking for missing timeframes...")
        
        missing_collections = []
        all_timeframes = ['1m', '5m', '15m', '1h', '4h', '12h', '1d']
        
        for entry in entries:
            pool_id = entry.pool_id.replace('solana_', '')
            print(f"\nChecking {entry.token_symbol} ({pool_id})...")
            
            for timeframe in all_timeframes:
                try:
                    data = await db_manager.get_ohlcv_data(
                        pool_id=entry.pool_id,
                        timeframe=timeframe,
                        start_time=None,
                        end_time=None
                    )
                    
                    if not data:
                        print(f"  Missing {timeframe} data")
                        missing_collections.append((pool_id, timeframe, entry.token_symbol))
                    else:
                        print(f"  Has {len(data)} {timeframe} records")
                        
                except Exception as e:
                    print(f"  Error checking {timeframe}: {e}")
        
        if missing_collections:
            print(f"\nFound {len(missing_collections)} missing timeframe collections")
            print("Would you like to collect them? (This will take time due to rate limits)")
            
            # For now, just show what's missing
            for pool_id, timeframe, symbol in missing_collections:
                print(f"  {symbol}: {timeframe}")
        else:
            print("\nNo missing timeframes found!")
        
        return missing_collections
        
    except Exception as e:
        logger.error(f"Error checking missing timeframes: {e}", exc_info=True)
        raise
    finally:
        await db_manager.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            # Check for missing timeframes
            asyncio.run(collect_missing_timeframes())
        elif sys.argv[1] == "single":
            # Collect for single pool
            if len(sys.argv) < 3:
                print("Usage: python collect_historical_with_rate_limits.py single <pool_id> [timeframe] [days_back]")
                sys.exit(1)
            
            pool_id = sys.argv[2]
            timeframe = sys.argv[3] if len(sys.argv) > 3 else "1h"
            days_back = int(sys.argv[4]) if len(sys.argv) > 4 else 30
            
            print(f"Collecting {timeframe} data for {pool_id} ({days_back} days)")
            asyncio.run(collect_historical_with_delays(
                pool_ids=[pool_id],
                timeframes=[timeframe],
                days_back=days_back
            ))
        else:
            print("Unknown command. Use 'check' or 'single <pool_id>'")
    else:
        # Collect for all pools with conservative settings
        print("Collecting historical data with rate limit protection...")
        asyncio.run(collect_historical_with_delays(
            timeframes=['1h', '4h', '1d'],  # Conservative timeframes
            days_back=30,
            delay_between_pools=10,  # 10 seconds between pools
            delay_between_timeframes=5  # 5 seconds between timeframes
        ))