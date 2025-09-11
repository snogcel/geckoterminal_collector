#!/usr/bin/env python3
"""
Example CLI integration with the CollectionScheduler.

This demonstrates how the scheduler would be integrated into the main CLI application
with enhanced rate limiting support.
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
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.utils.metadata import MetadataTracker
from gecko_terminal_collector.utils.enhanced_rate_limiter import GlobalRateLimitCoordinator

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
    """CLI wrapper for the collection scheduler with enhanced rate limiting."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.scheduler = None
        self.db_manager = None
        self.rate_limit_coordinator = None
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
        logger.info("Initializing collection system with enhanced rate limiting...")
        
        # Load configuration
        config_manager = ConfigManager(self.config_path)
        config = config_manager.get_config()
        
        # Initialize global rate limit coordinator
        self.rate_limit_coordinator = await GlobalRateLimitCoordinator.get_instance(
            requests_per_minute=config.rate_limiting.requests_per_minute,
            daily_limit=config.rate_limiting.daily_limit,
            state_dir=config.rate_limiting.state_file_dir
        )
        logger.info(f"Rate limiting: {config.rate_limiting.requests_per_minute} req/min, "
                   f"{config.rate_limiting.daily_limit} req/day")
        
        # Create database manager
        self.db_manager = SQLAlchemyDatabaseManager(config.database)
        await self.db_manager.initialize()
        
        # Create metadata tracker with database persistence
        metadata_tracker = MetadataTracker(db_manager=self.db_manager)
        
        # Create scheduler configuration
        scheduler_config = SchedulerConfig(
            max_workers=10,
            shutdown_timeout=30,
            error_recovery_delay=60,
            max_consecutive_errors=5,
            health_check_interval=300
        )
        
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
        """Register all collectors with the scheduler and rate limiting."""
        logger.info("Registering collectors with enhanced rate limiting...")
        
        # Get rate limiters for each collector type
        collectors_config = [
            ("dex_monitoring", DEXMonitoringCollector, "1h", True),
            ("top_pools", TopPoolsCollector, config.intervals.top_pools_monitoring, True),
            ("watchlist_monitor", WatchlistMonitor, config.intervals.watchlist_check, True),
            ("watchlist_collector", WatchlistCollector, config.intervals.watchlist_check, True),
            ("ohlcv", OHLCVCollector, config.intervals.ohlcv_collection, True),
            ("trade", TradeCollector, config.intervals.trade_collection, True),
            ("historical_ohlcv", HistoricalOHLCVCollector, "1d", False)
        ]
        
        for collector_id, collector_class, interval, enabled in collectors_config:
            try:
                # Get rate limiter for this collector
                rate_limiter = await self.rate_limit_coordinator.get_limiter(collector_id)
                
                # Create collector instance
                collector = collector_class(
                    config=config,
                    db_manager=self.db_manager,
                    metadata_tracker=metadata_tracker,
                    use_mock=use_mock
                )
                
                # Set rate limiter if collector supports it
                if hasattr(collector, 'set_rate_limiter'):
                    collector.set_rate_limiter(rate_limiter)
                    logger.info(f"Rate limiter configured for {collector_id}")
                else:
                    logger.warning(f"Collector {collector_id} does not support rate limiting")
                
                # Register with scheduler
                self.scheduler.register_collector(
                    collector,
                    interval=interval,
                    enabled=enabled
                )
                
                logger.info(f"Registered {collector_id} collector (interval: {interval}, enabled: {enabled})")
                
            except Exception as e:
                logger.error(f"Failed to register {collector_id} collector: {e}")
                raise
        
        logger.info(f"Successfully registered {len(self.scheduler.list_collectors())} collectors")
    
    async def run(self):
        """Run the scheduler until shutdown signal."""
        logger.info("Starting collection scheduler with rate limiting...")
        
        try:
            # Start the scheduler
            await self.scheduler.start()
            
            # Show initial status
            status = self.scheduler.get_status()
            logger.info(f"Scheduler started with {status['total_collectors']} collectors")
            logger.info(f"Enabled collectors: {status['enabled_collectors']}")
            
            # Show rate limiting status
            if self.rate_limit_coordinator:
                rate_status = await self.rate_limit_coordinator.get_global_status()
                logger.info(f"Rate limiting active: {rate_status['total_limiters']} limiters")
                logger.info(f"Daily usage: {rate_status['global_usage']['daily_usage_percentage']:.1f}%")
            
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
        """Show current scheduler and rate limiting status."""
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
        
        # Show rate limiting status
        if self.rate_limit_coordinator:
            rate_status = await self.rate_limit_coordinator.get_global_status()
            print(f"\n=== Rate Limiting Status ===")
            print(f"Global Limits: {rate_status['global_limits']['requests_per_minute']} req/min, "
                  f"{rate_status['global_limits']['daily_limit']} req/day")
            print(f"Total Daily Requests: {rate_status['global_usage']['total_daily_requests']}")
            print(f"Daily Usage: {rate_status['global_usage']['daily_usage_percentage']:.1f}%")
            
            print(f"\n=== Rate Limiter Details ===")
            for limiter_id, limiter_status in rate_status['limiters'].items():
                print(f"\n{limiter_id}:")
                print(f"  Daily Requests: {limiter_status['daily_requests']}/{limiter_status['daily_limit']}")
                print(f"  Circuit State: {limiter_status['circuit_state']}")
                print(f"  Consecutive Failures: {limiter_status['consecutive_failures']}")
                if limiter_status['backoff_until']:
                    print(f"  Backoff Until: {limiter_status['backoff_until']}")
                
                metrics = limiter_status['metrics']
                print(f"  Total Requests: {metrics['total_requests']}")
                print(f"  Rate Limit Hits: {metrics['rate_limit_hits']}")
                print(f"  Backoff Events: {metrics['backoff_events']}")
                print(f"  Circuit Breaker Trips: {metrics['circuit_breaker_trips']}")


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

            print("-_collector_status--")
            collector = job_id.removeprefix("collector_")
            print("-collector_status--")
            print("job_id: ", job_id)
            print("collector: ", collector)
            print("collector_key: ", collector_status['collector_key'])
            print("---")
            print(collector_status['collector_key'])

            #collector_key = collector_status['collector_key'] if collector_status else ""

            if collector_status and collector in collector_status['collector_key']:
                target_job_id = job_id
                break
        
        if not target_job_id:
            logger.error(f"Collector '{collector}' not found")
            available = [scheduler_cli.scheduler.get_collector_status(jid)['collector_key'] 
                        for jid in collectors]
            logger.info(f"Available collectors: {', '.join(available)}")
            return
        
        logger.info(f"Running collector '{collector}' once with rate limiting...")
        
        try:
            result = await scheduler_cli.scheduler.execute_collector_now(target_job_id)
            
            logger.info(f"Execution completed:")
            logger.info(f"  Success: {result.success}")
            logger.info(f"  Records: {result.records_collected}")
            if result.errors:
                logger.error(f"  Errors: {'; '.join(result.errors)}")
            
            # Show rate limiting metrics after execution
            if scheduler_cli.rate_limit_coordinator:
                rate_status = await scheduler_cli.rate_limit_coordinator.get_global_status()
                logger.info(f"Rate limiting after execution:")
                logger.info(f"  Daily requests used: {rate_status['global_usage']['total_daily_requests']}")
                logger.info(f"  Daily usage: {rate_status['global_usage']['daily_usage_percentage']:.1f}%")
                
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            
            # Check if it's a rate limiting issue
            if "rate limit" in str(e).lower() or "429" in str(e):
                logger.error("This appears to be a rate limiting issue. Check rate limiter status.")
                if scheduler_cli.rate_limit_coordinator:
                    rate_status = await scheduler_cli.rate_limit_coordinator.get_global_status()
                    for limiter_id, limiter_status in rate_status['limiters'].items():
                        if limiter_status['backoff_until']:
                            logger.error(f"Rate limiter {limiter_id} in backoff until: {limiter_status['backoff_until']}")
        
        await scheduler_cli.shutdown()
    
    asyncio.run(run_collector())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
def rate_limit_status(config):
    """Show detailed rate limiting status."""
    async def show_rate_status():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=True)
        
        if not scheduler_cli.rate_limit_coordinator:
            logger.error("Rate limit coordinator not initialized")
            return
        
        rate_status = await scheduler_cli.rate_limit_coordinator.get_global_status()
        
        print(f"\n=== Global Rate Limiting Status ===")
        print(f"Requests per minute limit: {rate_status['global_limits']['requests_per_minute']}")
        print(f"Daily request limit: {rate_status['global_limits']['daily_limit']}")
        print(f"Total daily requests: {rate_status['global_usage']['total_daily_requests']}")
        print(f"Daily usage percentage: {rate_status['global_usage']['daily_usage_percentage']:.2f}%")
        print(f"Active rate limiters: {rate_status['total_limiters']}")
        
        print(f"\n=== Individual Rate Limiter Status ===")
        for limiter_id, limiter_status in rate_status['limiters'].items():
            print(f"\n{limiter_id.upper()}:")
            print(f"  Daily requests: {limiter_status['daily_requests']}/{limiter_status['daily_limit']}")
            print(f"  Requests per minute: {limiter_status['requests_per_minute']}")
            print(f"  Circuit breaker state: {limiter_status['circuit_state']}")
            print(f"  Consecutive failures: {limiter_status['consecutive_failures']}")
            
            if limiter_status['backoff_until']:
                print(f"  ⚠️  In backoff until: {limiter_status['backoff_until']}")
            
            if limiter_status['next_daily_reset']:
                print(f"  Next daily reset: {limiter_status['next_daily_reset']}")
            
            # Show metrics
            metrics = limiter_status['metrics']
            print(f"  Metrics:")
            print(f"    Total requests: {metrics['total_requests']}")
            print(f"    Rate limit hits: {metrics['rate_limit_hits']}")
            print(f"    Backoff events: {metrics['backoff_events']}")
            print(f"    Circuit breaker trips: {metrics['circuit_breaker_trips']}")
        
        await scheduler_cli.shutdown()
    
    asyncio.run(show_rate_status())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--collector', help='Reset rate limiter for specific collector')
@click.option('--all', 'reset_all', is_flag=True, help='Reset all rate limiters')
def reset_rate_limiter(config, collector, reset_all):
    """Reset rate limiter state (use with caution)."""
    async def reset_limiter():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=True)
        
        if not scheduler_cli.rate_limit_coordinator:
            logger.error("Rate limit coordinator not initialized")
            return
        
        if reset_all:
            # Reset all rate limiters
            rate_status = await scheduler_cli.rate_limit_coordinator.get_global_status()
            for limiter_id in rate_status['limiters'].keys():
                limiter = await scheduler_cli.rate_limit_coordinator.get_limiter(limiter_id)
                # Reset backoff state
                limiter.backoff_state.consecutive_failures = 0
                limiter.backoff_state.backoff_until = None
                # Reset circuit breaker
                limiter.circuit_state = limiter.circuit_state.CLOSED
                limiter.circuit_failure_count = 0
                limiter.circuit_last_failure = None
                limiter.circuit_next_attempt = None
                logger.info(f"Reset rate limiter for {limiter_id}")
            
            logger.info("All rate limiters have been reset")
            
        elif collector:
            # Reset specific collector's rate limiter
            try:
                limiter = await scheduler_cli.rate_limit_coordinator.get_limiter(collector)
                # Reset backoff state
                limiter.backoff_state.consecutive_failures = 0
                limiter.backoff_state.backoff_until = None
                # Reset circuit breaker
                limiter.circuit_state = limiter.circuit_state.CLOSED
                limiter.circuit_failure_count = 0
                limiter.circuit_last_failure = None
                limiter.circuit_next_attempt = None
                logger.info(f"Reset rate limiter for {collector}")
                
            except Exception as e:
                logger.error(f"Failed to reset rate limiter for {collector}: {e}")
        else:
            logger.error("Must specify either --collector or --all")
        
        await scheduler_cli.shutdown()
    
    asyncio.run(reset_limiter())


if __name__ == '__main__':
    cli()