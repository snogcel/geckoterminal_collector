#!/usr/bin/env python3
"""
Collect 1-minute OHLCV data for specific pools.

1-minute data is high-volume, so this script is optimized for:
- Single pool collection
- Shorter time periods
- Progress monitoring
- Efficient pagination
"""

import asyncio
import logging
from datetime import datetime, timedelta
from gecko_terminal_collector.collectors.historical_ohlcv_collector import HistoricalOHLCVCollector
from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.utils.metadata import MetadataTracker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def collect_1m_data(
    pool_id: str,
    days_back: int = 7,
    show_progress: bool = True
):
    """
    Collect 1-minute OHLCV data for a specific pool.
    
    Args:
        pool_id: Pool ID (without 'solana_' prefix)
        days_back: Number of days to collect (default: 7, max recommended: 30)
        show_progress: Show detailed progress information
    """
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    # Initialize metadata tracker
    metadata_tracker = MetadataTracker(db_manager)
    
    # Initialize collector
    collector = HistoricalOHLCVCollector(
        config=config,
        db_manager=db_manager,
        metadata_tracker=metadata_tracker,
        use_mock=False
    )
    
    # Set pagination delay for 1m data (more requests needed)
    collector.pagination_delay = 2.0
    
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # Calculate expected records
        expected_records = days_back * 24 * 60  # 1 record per minute
        
        print("=" * 80)
        print("1-MINUTE DATA COLLECTION")
        print("=" * 80)
        print(f"Pool ID: {pool_id}")
        print(f"Date range: {start_date.date()} to {end_date.date()}")
        print(f"Days: {days_back}")
        print(f"Expected records: ~{expected_records:,}")
        print(f"Estimated API calls: ~{expected_records // 1000 + 1}")
        print(f"Estimated time: ~{(expected_records // 1000 + 1) * 2} seconds")
        print("=" * 80)
        print()
        
        # Check if data already exists
        existing_data = await db_manager.get_ohlcv_data(
            pool_id=f"solana_{pool_id}",
            timeframe="1m",
            start_time=start_date,
            end_time=end_date
        )
        
        if existing_data:
            print(f"⚠️  Found {len(existing_data)} existing 1m records")
            response = input("Overwrite existing data? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Cancelled.")
                return
            force_refresh = True
        else:
            force_refresh = False
        
        print("\nStarting collection...")
        start_time = datetime.now()
        
        # Collect data
        result = await collector.collect_for_pool(
            pool_id=pool_id,
            timeframe="1m",
            start_date=start_date,
            end_date=end_date,
            force_refresh=force_refresh
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Show results
        print("\n" + "=" * 80)
        print("COLLECTION COMPLETE")
        print("=" * 80)
        
        if result.success:
            print(f"✓ Success!")
            print(f"  Records collected: {result.records_collected:,}")
            print(f"  Time taken: {duration:.1f} seconds")
            print(f"  Records per second: {result.records_collected / duration:.1f}")
            
            # Calculate coverage
            coverage = (result.records_collected / expected_records) * 100
            print(f"  Coverage: {coverage:.1f}%")
            
            if coverage < 90:
                print(f"  ⚠️  Coverage is low - some data may be missing")
        else:
            print(f"✗ Failed!")
            print(f"  Errors: {result.errors}")
        
        print("=" * 80)
        
        # Show sample of collected data
        if result.success and result.records_collected > 0:
            print("\nVerifying data in database...")
            
            sample_data = await db_manager.get_ohlcv_data(
                pool_id=f"solana_{pool_id}",
                timeframe="1m",
                start_time=start_date,
                end_time=end_date
            )
            
            if sample_data:
                print(f"✓ Verified {len(sample_data)} records in database")
                print(f"\nFirst record: {sample_data[0].datetime}")
                print(f"Last record:  {sample_data[-1].datetime}")
                
                # Show sample prices
                print(f"\nSample data:")
                for i, record in enumerate(sample_data[:5]):
                    print(f"  {record.datetime}: O={record.open_price} H={record.high_price} "
                          f"L={record.low_price} C={record.close_price} V={record.volume_usd}")
            else:
                print("⚠️  No data found in database after collection")
        
        return result
        
    except Exception as e:
        logger.error(f"Error collecting 1m data: {e}", exc_info=True)
        raise
    finally:
        await db_manager.close()


async def collect_1m_for_watchlist(
    days_back: int = 3,
    max_pools: int = 10
):
    """
    Collect 1m data for watchlist pools (limited to avoid overwhelming the system).
    
    Args:
        days_back: Number of days (keep short for 1m data)
        max_pools: Maximum number of pools to process
    """
    
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Get active watchlist entries
        entries = await db_manager.get_active_watchlist_entries()
        
        if len(entries) > max_pools:
            print(f"⚠️  Watchlist has {len(entries)} pools, limiting to {max_pools}")
            print(f"   (1m data is high-volume, process in batches)")
            entries = entries[:max_pools]
        
        print(f"Collecting 1m data for {len(entries)} pools ({days_back} days each)")
        print(f"Expected total records: ~{len(entries) * days_back * 1440:,}")
        print(f"Estimated time: ~{len(entries) * 2} minutes")
        print()
        
        response = input("Continue? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Cancelled.")
            return
        
        total_collected = 0
        
        for i, entry in enumerate(entries):
            pool_id = entry.pool_id.replace('solana_', '')
            
            print(f"\n[{i+1}/{len(entries)}] Processing {entry.token_symbol} ({pool_id})...")
            
            result = await collect_1m_data(
                pool_id=pool_id,
                days_back=days_back,
                show_progress=False
            )
            
            if result.success:
                total_collected += result.records_collected
                print(f"  ✓ Collected {result.records_collected:,} records")
            else:
                print(f"  ✗ Failed: {result.errors}")
            
            # Delay between pools
            if i < len(entries) - 1:
                print(f"  Waiting 10 seconds before next pool...")
                await asyncio.sleep(10)
        
        print(f"\n{'='*80}")
        print(f"BATCH COMPLETE")
        print(f"{'='*80}")
        print(f"Total records collected: {total_collected:,}")
        print(f"Pools processed: {len(entries)}")
        
    finally:
        await db_manager.close()


async def check_1m_coverage():
    """Check which pools have 1m data and coverage."""
    
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        entries = await db_manager.get_active_watchlist_entries()
        
        print("=" * 80)
        print("1-MINUTE DATA COVERAGE CHECK")
        print("=" * 80)
        print()
        
        pools_with_1m = 0
        total_1m_records = 0
        
        for entry in entries:
            data = await db_manager.get_ohlcv_data(
                pool_id=entry.pool_id,
                timeframe="1m",
                start_time=None,
                end_time=None
            )
            
            if data:
                pools_with_1m += 1
                total_1m_records += len(data)
                
                # Calculate date range
                dates = [d.datetime for d in data]
                days_covered = (max(dates) - min(dates)).days + 1
                
                print(f"✓ {entry.token_symbol:10} {len(data):6,} records  "
                      f"({min(dates).date()} to {max(dates).date()}, {days_covered} days)")
            else:
                print(f"✗ {entry.token_symbol:10} No 1m data")
        
        print()
        print("=" * 80)
        print(f"Summary:")
        print(f"  Pools with 1m data: {pools_with_1m}/{len(entries)}")
        print(f"  Total 1m records: {total_1m_records:,}")
        print(f"  Average per pool: {total_1m_records // max(pools_with_1m, 1):,}")
        print("=" * 80)
        
    finally:
        await db_manager.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python collect_1m_data.py <pool_id> [days_back]")
        print("  python collect_1m_data.py check")
        print("  python collect_1m_data.py batch [days_back] [max_pools]")
        print()
        print("Examples:")
        print("  python collect_1m_data.py abc123 7          # 7 days of 1m data")
        print("  python collect_1m_data.py abc123 1          # Last 24 hours")
        print("  python collect_1m_data.py check             # Check coverage")
        print("  python collect_1m_data.py batch 3 10        # 3 days for 10 pools")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "check":
        asyncio.run(check_1m_coverage())
    elif command == "batch":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        max_pools = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        asyncio.run(collect_1m_for_watchlist(days, max_pools))
    else:
        pool_id = command
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        asyncio.run(collect_1m_data(pool_id, days))
