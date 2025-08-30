#!/usr/bin/env python3
"""
Demo script showing how to use the CollectionScheduler.

This script demonstrates:
1. Setting up the scheduler with configuration
2. Registering multiple collectors with different intervals
3. Starting and monitoring the scheduler
4. Graceful shutdown
"""

import asyncio
import logging
from datetime import datetime

from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.scheduling.scheduler import CollectionScheduler, SchedulerConfig
from gecko_terminal_collector.collectors.dex_monitoring import DEXMonitoringCollector
from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
from gecko_terminal_collector.collectors.trade_collector import TradeCollector
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.utils.metadata import MetadataTracker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main demo function."""
    logger.info("Starting Collection Scheduler Demo")
    
    # Create configuration
    config = CollectionConfig()
    
    # Create scheduler configuration with shorter intervals for demo
    scheduler_config = SchedulerConfig(
        max_workers=5,
        shutdown_timeout=10,
        error_recovery_delay=30,
        max_consecutive_errors=3,
        health_check_interval=60
    )
    
    # Create metadata tracker
    metadata_tracker = MetadataTracker()
    
    # Create database manager
    db_manager = DatabaseManager(config.database)
    
    # Initialize scheduler
    scheduler = CollectionScheduler(
        config=config,
        scheduler_config=scheduler_config,
        metadata_tracker=metadata_tracker
    )
    
    try:
        # Create collectors (using mock clients for demo)
        logger.info("Creating collectors...")
        
        dex_collector = DEXMonitoringCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        top_pools_collector = TopPoolsCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        watchlist_collector = WatchlistCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        ohlcv_collector = OHLCVCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        trade_collector = TradeCollector(
            config=config,
            db_manager=db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=True
        )
        
        # Register collectors with different intervals
        logger.info("Registering collectors...")
        
        dex_job_id = scheduler.register_collector(
            dex_collector,
            interval="1h",  # Check DEXes every hour
            enabled=True
        )
        
        pools_job_id = scheduler.register_collector(
            top_pools_collector,
            interval="30m",  # Check top pools every 30 minutes
            enabled=True
        )
        
        watchlist_job_id = scheduler.register_collector(
            watchlist_collector,
            interval="1h",  # Check watchlist every hour
            enabled=True
        )
        
        ohlcv_job_id = scheduler.register_collector(
            ohlcv_collector,
            interval="15m",  # Collect OHLCV every 15 minutes
            enabled=True
        )
        
        trade_job_id = scheduler.register_collector(
            trade_collector,
            interval="10m",  # Collect trades every 10 minutes
            enabled=True
        )
        
        logger.info(f"Registered {len(scheduler.list_collectors())} collectors")
        
        # Start the scheduler
        logger.info("Starting scheduler...")
        await scheduler.start()
        
        # Show initial status
        status = scheduler.get_status()
        logger.info(f"Scheduler started with {status['total_collectors']} collectors")
        logger.info(f"Enabled collectors: {status['enabled_collectors']}")
        
        # Let it run for a demo period
        demo_duration = 120  # 2 minutes
        logger.info(f"Running scheduler for {demo_duration} seconds...")
        
        for i in range(demo_duration // 10):
            await asyncio.sleep(10)
            
            # Show periodic status updates
            status = scheduler.get_status()
            logger.info(
                f"Status update {i+1}: "
                f"Running jobs: {status['running_jobs']}, "
                f"State: {status['state']}"
            )
            
            # Show next run times
            next_runs = scheduler.get_next_run_times()
            for job_id, next_run in next_runs.items():
                if next_run:
                    collector_status = scheduler.get_collector_status(job_id)
                    collector_key = collector_status['collector_key'] if collector_status else job_id
                    logger.info(f"  {collector_key}: next run at {next_run}")
        
        # Demonstrate on-demand execution
        logger.info("Demonstrating on-demand execution...")
        result = await scheduler.execute_collector_now(dex_job_id)
        logger.info(f"On-demand execution result: {result.success}, records: {result.records_collected}")
        
        # Show final status
        final_status = scheduler.get_status()
        logger.info("Final scheduler status:")
        for job_id, collector_info in final_status['collectors'].items():
            logger.info(
                f"  {collector_info['collector_key']}: "
                f"errors={collector_info['error_count']}, "
                f"last_run={collector_info['last_run']}"
            )
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Error in demo: {e}")
    finally:
        # Graceful shutdown
        logger.info("Shutting down scheduler...")
        await scheduler.stop()
        logger.info("Scheduler stopped")
        
        # Close database connections
        await db_manager.close()
        logger.info("Demo completed")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())