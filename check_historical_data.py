#!/usr/bin/env python3
"""
Check existing historical OHLCV data in the database.
"""

import asyncio
from datetime import datetime
from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager

async def check_historical_data():
    """Check what historical OHLCV data exists for watchlist symbols."""
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Get active watchlist entries
        entries = await db_manager.get_active_watchlist_entries()
        pool_ids = await db_manager.get_watchlist_pools()
        
        print("Historical OHLCV Data Summary")
        print("=" * 60)
        
        for entry in entries:
            print(f"\n{entry.token_symbol} ({entry.token_name})")
            print(f"Pool ID: {entry.pool_id}")
            print("-" * 40)
            
            # Check data for each timeframe
            timeframes = ['1m', '5m', '15m', '1h', '4h', '12h', '1d']
            
            for timeframe in timeframes:
                try:
                    # Get OHLCV data for this pool and timeframe
                    data = await db_manager.get_ohlcv_data(
                        pool_id=entry.pool_id,
                        timeframe=timeframe,
                        start_time=None,
                        end_time=None
                    )
                    
                    if data:
                        # Find date range
                        timestamps = [record.datetime for record in data]
                        earliest = min(timestamps)
                        latest = max(timestamps)
                        
                        print(f"  {timeframe:>3}: {len(data):>5} records | {earliest.date()} to {latest.date()}")
                    else:
                        print(f"  {timeframe:>3}: {0:>5} records | No data")
                        
                except Exception as e:
                    print(f"  {timeframe:>3}: Error - {e}")
        
        # Overall statistics
        print("\n" + "=" * 60)
        print("OVERALL STATISTICS")
        print("=" * 60)
        
        # Count total OHLCV records
        try:
            total_records = await db_manager.count_records("ohlcv_data")
            print(f"Total OHLCV records in database: {total_records:,}")
        except Exception as e:
            print(f"Error counting total records: {e}")
        
        # Check data by timeframe across all pools
        print(f"\nData by timeframe (all pools):")
        timeframes = ['1m', '5m', '15m', '1h', '4h', '12h', '1d']
        
        for timeframe in timeframes:
            try:
                # This is a simplified count - you might need to implement a specific method
                count = 0
                earliest_date = None
                latest_date = None
                
                for pool_id in pool_ids:
                    data = await db_manager.get_ohlcv_data(
                        pool_id=pool_id,
                        timeframe=timeframe,
                        start_time=None,
                        end_time=None
                    )
                    if data:
                        count += len(data)
                        timestamps = [record.datetime for record in data]
                        pool_earliest = min(timestamps)
                        pool_latest = max(timestamps)
                        
                        if earliest_date is None or pool_earliest < earliest_date:
                            earliest_date = pool_earliest
                        if latest_date is None or pool_latest > latest_date:
                            latest_date = pool_latest
                
                if count > 0:
                    print(f"  {timeframe:>3}: {count:>6} records | {earliest_date.date()} to {latest_date.date()}")
                else:
                    print(f"  {timeframe:>3}: {count:>6} records | No data")
                    
            except Exception as e:
                print(f"  {timeframe:>3}: Error - {e}")
        
    except Exception as e:
        print(f"Error checking historical data: {e}")
        raise
    finally:
        await db_manager.close()

async def check_data_gaps():
    """Check for gaps in historical data."""
    
    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Initialize database manager
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    try:
        # Get active watchlist entries
        entries = await db_manager.get_active_watchlist_entries()
        
        print("Data Gaps Analysis")
        print("=" * 60)
        
        for entry in entries:
            print(f"\n{entry.token_symbol} - Checking for data gaps...")
            
            # Check 1h timeframe for gaps (most common)
            try:
                data = await db_manager.get_ohlcv_data(
                    pool_id=entry.pool_id,
                    timeframe="1h",
                    start_time=None,
                    end_time=None
                )
                
                if not data:
                    print(f"  No 1h data found")
                    continue
                
                # Sort by timestamp
                data.sort(key=lambda x: x.timestamp)
                
                # Check for gaps (more than 1 hour between consecutive records)
                gaps = []
                for i in range(1, len(data)):
                    time_diff = data[i].timestamp - data[i-1].timestamp
                    if time_diff > 3600:  # More than 1 hour
                        gap_hours = time_diff / 3600
                        gaps.append({
                            'start': datetime.fromtimestamp(data[i-1].timestamp),
                            'end': datetime.fromtimestamp(data[i].timestamp),
                            'duration_hours': gap_hours
                        })
                
                if gaps:
                    print(f"  Found {len(gaps)} gaps in 1h data:")
                    for gap in gaps[:5]:  # Show first 5 gaps
                        print(f"    {gap['start']} to {gap['end']} ({gap['duration_hours']:.1f} hours)")
                    if len(gaps) > 5:
                        print(f"    ... and {len(gaps) - 5} more gaps")
                else:
                    print(f"  No significant gaps found in 1h data")
                    
            except Exception as e:
                print(f"  Error checking gaps: {e}")
        
    except Exception as e:
        print(f"Error in gap analysis: {e}")
        raise
    finally:
        await db_manager.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "gaps":
        print("Checking for data gaps...")
        asyncio.run(check_data_gaps())
    else:
        print("Checking existing historical data...")
        asyncio.run(check_historical_data())