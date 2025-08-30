#!/usr/bin/env python3
"""
Example CLI integration with the CollectionScheduler.

This demonstrates how the scheduler would be integrated into the main CLI application.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

import click
import yaml

from gecko_terminal_collector.config.models import CollectionConfig
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.scheduling.scheduler import CollectionScheduler, SchedulerConfig
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.utils.metadata import MetadataTracker

# Import all collectors
from gecko_terminal_collector.collectors.dex_monitoring import DEXMonitoringCollector
from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
from gecko_terminal_collector.collectors.watchlist_monitor import WatchlistMonitor
from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
from gecko_terminal_collector.collectors.trade_collector import TradeCollector
from gecko_terminal_collector.collectors.historical_ohlcv_collector import HistoricalOHLCVCollector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SchedulerCLI:
    """CLI wrapper for the collection scheduler."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.scheduler = None
        self.db_manager = None
        self.shutdown_event = asyncio.Event()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
    
    async def initialize(self, use_mock: bool = False):
        """Initialize the scheduler and all components."""
        logger.info("Initializing collection system...")
        
        # Load configuration
        config_manager = ConfigManager(self.config_path)
        config = config_manager.get_config()
        
        # Create scheduler configuration
        scheduler_config = SchedulerConfig(
            max_workers=10,
            shutdown_timeout=30,
            error_recovery_delay=60,
            max_consecutive_errors=5,
            health_check_interval=300
        )
        
        # Create metadata tracker
        metadata_tracker = MetadataTracker()
        
        # Create database manager
        self.db_manager = DatabaseManager(config.database)
        await self.db_manager.initialize()
        
        # Create scheduler
        self.scheduler = CollectionScheduler(
            config=config,
            scheduler_config=scheduler_config,
            metadata_tracker=metadata_tracker
        )
        
        # Register all collectors
        await self._register_collectors(config, metadata_tracker, use_mock)
        
        logger.info("Initialization completed")
    
    async def _register_collectors(self, config: CollectionConfig, metadata_tracker: MetadataTracker, use_mock: bool):
        """Register all collectors with the scheduler."""
        logger.info("Registering collectors...")
        
        # DEX Monitoring Collector
        dex_collector = DEXMonitoringCollector(
            config=config,
            db_manager=self.db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=use_mock
        )
        self.scheduler.register_collector(
            dex_collector,
            interval="1h",  # From config.intervals.top_pools_monitoring
            enabled=True
        )
        
        # Top Pools Collector
        top_pools_collector = TopPoolsCollector(
            config=config,
            db_manager=self.db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=use_mock
        )
        self.scheduler.register_collector(
            top_pools_collector,
            interval=config.intervals.top_pools_monitoring,
            enabled=True
        )
        
        # Watchlist Monitor
        watchlist_monitor = WatchlistMonitor(
            config=config,
            db_manager=self.db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=use_mock
        )
        self.scheduler.register_collector(
            watchlist_monitor,
            interval=config.intervals.watchlist_check,
            enabled=True
        )
        
        # Watchlist Collector
        watchlist_collector = WatchlistCollector(
            config=config,
            db_manager=self.db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=use_mock
        )
        self.scheduler.register_collector(
            watchlist_collector,
            interval=config.intervals.watchlist_check,
            enabled=True
        )
        
        # OHLCV Collector
        ohlcv_collector = OHLCVCollector(
            config=config,
            db_manager=self.db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=use_mock
        )
        self.scheduler.register_collector(
            ohlcv_collector,
            interval=config.intervals.ohlcv_collection,
            enabled=True
        )
        
        # Trade Collector
        trade_collector = TradeCollector(
            config=config,
            db_manager=self.db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=use_mock
        )
        self.scheduler.register_collector(
            trade_collector,
            interval=config.intervals.trade_collection,
            enabled=True
        )
        
        # Historical OHLCV Collector (disabled by default, run on-demand)
        historical_collector = HistoricalOHLCVCollector(
            config=config,
            db_manager=self.db_manager,
            metadata_tracker=metadata_tracker,
            use_mock=use_mock
        )
        self.scheduler.register_collector(
            historical_collector,
            interval="1d",  # Daily check for historical data gaps
            enabled=False  # Disabled by default
        )
        
        logger.info(f"Registered {len(self.scheduler.list_collectors())} collectors")
    
    async def run(self):
        """Run the scheduler until shutdown signal."""
        logger.info("Starting collection scheduler...")
        
        try:
            # Start the scheduler
            await self.scheduler.start()
            
            # Show initial status
            status = self.scheduler.get_status()
            logger.info(f"Scheduler started with {status['total_collectors']} collectors")
            logger.info(f"Enabled collectors: {status['enabled_collectors']}")
            
            # Wait for shutdown signal
            logger.info("Collection system is running. Press Ctrl+C to stop.")
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Error running scheduler: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown the system."""
        logger.info("Shutting down collection system...")
        
        if self.scheduler:
            await self.scheduler.stop()
            logger.info("Scheduler stopped")
        
        if self.db_manager:
            await self.db_manager.close()
            logger.info("Database connections closed")
        
        logger.info("Shutdown completed")
    
    async def status(self):
        """Show current scheduler status."""
        if not self.scheduler:
            logger.error("Scheduler not initialized")
            return
        
        status = self.scheduler.get_status()
        
        print(f"\n=== Collection Scheduler Status ===")
        print(f"State: {status['state']}")
        print(f"Total Collectors: {status['total_collectors']}")
        print(f"Enabled Collectors: {status['enabled_collectors']}")
        print(f"Running Jobs: {status['running_jobs']}")
        
        print(f"\n=== Collector Details ===")
        for job_id, collector_info in status['collectors'].items():
            print(f"\n{collector_info['collector_key']}:")
            print(f"  Interval: {collector_info['interval']}")
            print(f"  Enabled: {collector_info['enabled']}")
            print(f"  Last Run: {collector_info['last_run']}")
            print(f"  Last Success: {collector_info['last_success']}")
            print(f"  Error Count: {collector_info['error_count']}")
            print(f"  Consecutive Errors: {collector_info['consecutive_errors']}")
        
        # Show next run times
        next_runs = self.scheduler.get_next_run_times()
        print(f"\n=== Next Run Times ===")
        for job_id, next_run in next_runs.items():
            collector_status = self.scheduler.get_collector_status(job_id)
            collector_key = collector_status['collector_key'] if collector_status else job_id
            print(f"{collector_key}: {next_run}")


@click.group()
def cli():
    """GeckoTerminal Data Collector CLI with Scheduler."""
    pass


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--mock', is_flag=True, help='Use mock clients for testing')
def start(config, mock):
    """Start the collection scheduler."""
    async def run_scheduler():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=mock)
        await scheduler_cli.run()
    
    asyncio.run(run_scheduler())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
def status(config):
    """Show scheduler status."""
    async def show_status():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=True)  # Mock for status check
        await scheduler_cli.status()
    
    asyncio.run(show_status())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--collector', '-col', help='Collector to run (e.g., dex_monitoring, top_pools)')
@click.option('--mock', is_flag=True, help='Use mock clients for testing')
def run_once(config, collector, mock):
    """Run a specific collector once."""
    async def run_collector():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=mock)
        
        # Find the collector job ID
        collectors = scheduler_cli.scheduler.list_collectors()
        target_job_id = None
        
        for job_id in collectors:
            collector_status = scheduler_cli.scheduler.get_collector_status(job_id)
            if collector_status and collector in collector_status['collector_key']:
                target_job_id = job_id
                break
        
        if not target_job_id:
            logger.error(f"Collector '{collector}' not found")
            return
        
        logger.info(f"Running collector '{collector}' once...")
        result = await scheduler_cli.scheduler.execute_collector_now(target_job_id)
        
        logger.info(f"Execution completed:")
        logger.info(f"  Success: {result.success}")
        logger.info(f"  Records: {result.records_collected}")
        if result.errors:
            logger.error(f"  Errors: {'; '.join(result.errors)}")
        
        await scheduler_cli.shutdown()
    
    asyncio.run(run_collector())


if __name__ == '__main__':
    cli()