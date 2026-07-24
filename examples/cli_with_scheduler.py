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

# Load .env file before anything else so env vars are available to all modules
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — rely on env vars being set externally

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
from gecko_terminal_collector.collectors.enhanced_watchlist_collector import EnhancedWatchlistCollector
from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
from gecko_terminal_collector.collectors.trade_collector import TradeCollector
from gecko_terminal_collector.collectors.historical_ohlcv_collector import HistoricalOHLCVCollector
from gecko_terminal_collector.collectors.new_pools_collector import NewPoolsCollector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Import the new statistics engine
from gecko_terminal_collector.utils.statistics_engine import StatisticsEngine


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
        
        # Load the raw config to check what's actually defined in the YAML
        import yaml
        with open(self.config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Get intervals from raw config (only what's explicitly defined)
        raw_intervals = raw_config.get('intervals', {})
        
        logger.info(f"Loading collectors from config - found {len(raw_intervals)} interval definitions")
        
        # Standard collectors configuration (collector_id, collector_class, interval, enabled, additional_params)
        # Only register collectors that have intervals explicitly defined in the YAML
        collectors_config = []
        
        # Only add collectors if their interval is explicitly set in the raw YAML config
        if 'top_pools_monitoring' in raw_intervals:
            interval = raw_intervals['top_pools_monitoring']
            logger.info(f"Enabling top_pools collectors (interval: {interval})")
            collectors_config.append(("dex_monitoring", DEXMonitoringCollector, "1h", True, {}))
            collectors_config.append(("top_pools", TopPoolsCollector, interval, True, {}))
        
        # Enhanced watchlist collector - check for enhanced_watchlist config section
        enhanced_watchlist_config = raw_config.get('enhanced_watchlist', {})
        if enhanced_watchlist_config.get('enabled', False):
            interval = enhanced_watchlist_config.get('interval', '1h')
            sources = enhanced_watchlist_config.get('sources', ['reference'])
            logger.info(f"Enabling enhanced watchlist collector (interval: {interval}, sources: {sources})")
            collectors_config.append(("enhanced_watchlist", EnhancedWatchlistCollector, interval, True, {
                'watchlist_sources': sources
            }))           

        if 'watchlist_check' in raw_intervals:
            interval = raw_intervals['watchlist_check']
            logger.info(f"Enabling watchlist collectors (interval: {interval})")
            collectors_config.append(("watchlist_monitor", WatchlistMonitor, interval, True, {}))
            collectors_config.append(("watchlist_collector", WatchlistCollector, interval, True, {}))
        
        if 'ohlcv_collection' in raw_intervals:
            interval = raw_intervals['ohlcv_collection']
            logger.info(f"Enabling ohlcv collector (interval: {interval})")
            collectors_config.append(("ohlcv", OHLCVCollector, interval, True, {}))
        
        if 'trade_collection' in raw_intervals:
            interval = raw_intervals['trade_collection']
            logger.info(f"Enabling trade collector (interval: {interval})")
            collectors_config.append(("trade", TradeCollector, interval, True, {}))
        
        logger.info(f"Configured {len(collectors_config)} collectors based on config.yaml intervals")
        
        # Historical OHLCV is optional - only add if explicitly enabled
        # collectors_config.append(("historical_ohlcv", HistoricalOHLCVCollector, "1d", False, {}))

        



        
        #print("===_register_collectors: config===")
        #print(config)
        #print("===")

        # raise SystemExit()

        # Add network-specific new pools collectors
        for network_name, network_config in config.new_pools.networks.items():
            collector_id = f"new_pools_{network_name}"
            rate_limit_key = network_config.rate_limit_key or collector_id
            
            collectors_config.append((
                collector_id,
                NewPoolsCollector,
                network_config.interval,
                network_config.enabled,
                {"network": network_name}
            ))
            
            logger.info(f"Added new pools collector for network '{network_name}' "
                       f"(interval: {network_config.interval}, enabled: {network_config.enabled})")
        
        print("==_collector_config_==")
        print(collectors_config)
        print("===")

        # Register all collectors - bug: isn't differentiating between old collector / new collector
        for collector_config in collectors_config:

            print("--_collector_config: ", collector_config[0])
            
            if (collector_config[0] in ["trade","ohlcv","historical_ohlcv","watchlist_monitor","watchlist_collector"]):
                # Legacy format without additional params
                print("===_parsing_legacy_format: ")
                print(collector_config)
                print("===")
                collector_id, collector_class, interval, enabled, additional_params = collector_config
                additional_params = {}
            else:
                # New format with additional params
                collector_id, collector_class, interval, enabled, additional_params = collector_config
                print("===_parsed_new_format: ")
                print(collector_config)
                print("===")
            
            try:
                # Get rate limiter for this collector
                rate_limiter = await self.rate_limit_coordinator.get_limiter(collector_id)
                
                # Rate Limited to avoid API calls not working
                #print("-_register_rate_limiter--")
                #print(rate_limiter)
                #print("---")









                # Create collector instance with additional parameters
                collector_kwargs = {
                    "config": config,
                    "db_manager": self.db_manager,
                    "metadata_tracker": metadata_tracker,
                    "use_mock": use_mock
                }
                collector_kwargs.update(additional_params)
                
                collector = collector_class(**collector_kwargs)
                
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
            collector_key = collector_info['collector_key']
            
            # Add network information for new pools collectors
            network_info = ""
            if collector_key.startswith('new_pools_'):
                network = collector_key.replace('new_pools_', '')
                network_info = f" (Network: {network})"
            
            print(f"\n{collector_key}{network_info}:")
            print(f"  Type: {'New Pools Collector' if collector_key.startswith('new_pools_') else 'Standard Collector'}")
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
@click.option('--collector', '-col', help='Collector to run (e.g., dex_monitoring, top_pools, new_pools_solana, or just solana for new_pools_solana)')
@click.option('--mock', is_flag=True, help='Use mock clients for testing')
def run_once(config, collector, mock):
    """Run a specific collector once."""
    async def run_collector():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=mock)
        
        # Check if collector is provided
        if not collector:
            logger.error("Collector name is required. Use --collector option.")
            print("Available collectors:")
            collectors = scheduler_cli.scheduler.list_collectors()
            for job_id in collectors:
                collector_status = scheduler_cli.scheduler.get_collector_status(job_id)
                if collector_status:
                    print(f"  - {collector_status['collector_key']}")
            return
        
        # Find the collector job ID
        collectors = scheduler_cli.scheduler.list_collectors()
        target_job_id = None

        print("registered_collectors: ", collectors)
        print("registered_collectors_length: ", len(collectors))
        
        # First, try to find exact matches
        for job_id in collectors:
            collector_status = scheduler_cli.scheduler.get_collector_status(job_id)

            print("collector_status: ", collector_status)
            print("job_id: ", job_id)
            
            if collector_status:
                collector_key = collector_status['collector_key']

                # Exact match has highest priority - check both collector key and simplified names
                if (collector and collector == collector_key or 
                    collector and collector == collector_key.replace('_collector', '') or
                    collector and f"{collector}_collector" == collector_key):
                    target_job_id = job_id
                    logger.info(f"Found exact match: '{collector_key}'")
                    break
        
        # If no exact match, try to find new pools collectors by network name
        if not target_job_id:
            for job_id in collectors:
                collector_status = scheduler_cli.scheduler.get_collector_status(job_id)
                
                if collector_status:
                    collector_key = collector_status['collector_key']
                    
                    # Prioritize new pools collectors for network names
                    if collector and collector_key == f"new_pools_{collector}":
                        target_job_id = job_id
                        logger.info(f"Found new pools collector for network '{collector}': '{collector_key}'")
                        break
        

        print("--NO MATCH FOUND--")

        # If still no match, try partial matches
        if not target_job_id:
            for job_id in collectors:
                collector_status = scheduler_cli.scheduler.get_collector_status(job_id)
                
                if collector_status:
                    collector_key = collector_status['collector_key']

                    # Support partial matches for other collectors
                    if (collector and (collector in collector_key or 
                        collector_key.endswith(f"_{collector}") or 
                        collector_key.startswith(f"{collector}_") or
                        collector_key.replace('_collector', '') == collector)):
                        target_job_id = job_id
                        logger.info(f"Found partial match: '{collector_key}' for '{collector}'")
                        break
        
        if not target_job_id:
            logger.error(f"Collector '{collector or 'None'}' not found")
            available = []
            new_pools_collectors = []
            
            for jid in collectors:
                collector_status = scheduler_cli.scheduler.get_collector_status(jid)
                if collector_status:
                    collector_key = collector_status['collector_key']
                    available.append(collector_key)
                    if collector_key.startswith('new_pools_'):
                        network = collector_key.replace('new_pools_', '')
                        new_pools_collectors.append(f"{network} (use '{collector_key}' or '{network}')")
            
            logger.info(f"Available collectors: {', '.join(available)}")
            if new_pools_collectors:
                logger.info(f"New pools collectors: {', '.join(new_pools_collectors)}")
            return
        
        logger.info(f"Running collector '{collector or 'None'}' once with rate limiting...")
        
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
            # Add type information for new pools collectors
            limiter_type = ""
            if limiter_id.startswith('new_pools_'):
                network = limiter_id.replace('new_pools_', '')
                limiter_type = f" (New Pools - {network.title()})"
            
            print(f"\n{limiter_id.upper()}{limiter_type}:")
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
@click.option('--network', '-n', default='solana', help='Network to collect pools for')
@click.option('--mock', is_flag=True, help='Use mock clients for testing')
def collect_new_pools(config, network, mock):
    """Run new pools collection for a specific network on-demand."""
    async def run_collection():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=mock)
        
        try:
            # Create a temporary NewPoolsCollector instance for this network
            config_manager = ConfigManager(config)
            collection_config = config_manager.get_config()
            
            # Check if network is configured
            if network not in collection_config.new_pools.networks:
                logger.error(f"Network '{network}' not configured in new_pools.networks")
                available_networks = list(collection_config.new_pools.networks.keys())
                logger.info(f"Available networks: {', '.join(available_networks)}")
                return
            
            # Get rate limiter for this network
            collector_id = f"new_pools_{network}"

            print("-_collect_new_pools--")
            print(collector_id)
            print("---")

            rate_limiter = await scheduler_cli.rate_limit_coordinator.get_limiter(collector_id)            

            print("-_should_this_have_a_api_request_limit_prevention_method:")
            print(rate_limiter)
            print("---")
            
            # Create metadata tracker
            metadata_tracker = MetadataTracker(db_manager=scheduler_cli.db_manager)
            
            # Create collector instance
            collector = NewPoolsCollector(
                config=collection_config,
                db_manager=scheduler_cli.db_manager,
                network=network,
                metadata_tracker=metadata_tracker,
                use_mock=mock
            )
            
            # Set rate limiter
            if hasattr(collector, 'set_rate_limiter'):
                collector.set_rate_limiter(rate_limiter)

            print("_-rate_limiter_set--")
            
            #logger.info(f"Starting new pools collection for network: {network}")
            
            # Check rate limiter status before execution
            """ if rate_limiter:
                try:
                    # limiter_status = await rate_limiter.get_status()
                    limiter_status = await rate_limiter.get_status()
                    if limiter_status.get('backoff_until'):
                        logger.warning(f"Rate limiter in backoff until: {limiter_status['backoff_until']}")
                        logger.warning("Collection may be delayed due to rate limiting")
                except Exception as e:
                    logger.warning(f"Could not check rate limiter status: {e}") """
            
            # Execute collection
            result = await collector.collect()
            
            # Display comprehensive results
            print(f"\n=== New Pools Collection Results ===")
            print(f"Network: {network}")
            print(f"Success: {result.success}")
            print(f"Total Records: {result.records_collected}")
            print(f"Collection Time: {result.collection_time}")
            
            if result.metadata:
                print(f"\n=== Collection Details ===")
                print(f"Pools Created: {result.metadata.get('pools_created', 0)}")
                print(f"History Records: {result.metadata.get('history_records', 0)}")
                print(f"API Pools Received: {result.metadata.get('api_pools_received', 0)}")
            
            if result.errors:
                print(f"\n=== Errors ({len(result.errors)}) ===")
                for error in result.errors:
                    print(f"  • {error}")
            
            # Show rate limiting status after execution
            """ if rate_limiter:
                try:
                    rate_status = await rate_limiter.get_status()
                    print(f"\n=== Rate Limiting Status ===")
                    print(f"Daily Requests: {rate_status.get('daily_requests', 0)}/{rate_status.get('daily_limit', 0)}")
                    print(f"Circuit State: {rate_status.get('circuit_state', 'Unknown')}")
                    
                    if rate_status.get('backoff_until'):
                        print(f"⚠️  In backoff until: {rate_status['backoff_until']}")
                    
                    metrics = rate_status.get('metrics', {})
                    print(f"Total API Requests: {metrics.get('total_requests', 0)}")
                    print(f"Rate Limit Hits: {metrics.get('rate_limit_hits', 0)}")
                    
                    if metrics.get('rate_limit_hits', 0) > 0:
                        print(f"⚠️  Rate limiting detected during collection")
                except Exception as e:
                    print(f"\n=== Rate Limiting Status ===")
                    print(f"Could not retrieve rate limiter status: {e}") """
            
            # Show global rate limiting status
            global_status = await scheduler_cli.rate_limit_coordinator.get_global_status()
            print(f"\n=== Global Rate Usage ===")
            print(f"Daily Usage: {global_status['global_usage']['daily_usage_percentage']:.1f}%")
            print(f"Total Daily Requests: {global_status['global_usage']['total_daily_requests']}")
            
        except Exception as e:
            logger.error(f"Collection failed: {e}")
            
            # Check if it's a rate limiting issue
            if "rate limit" in str(e).lower() or "429" in str(e):
                logger.error("This appears to be a rate limiting issue.")
                if scheduler_cli.rate_limit_coordinator:
                    rate_status = await scheduler_cli.rate_limit_coordinator.get_global_status()
                    for limiter_id, limiter_status in rate_status['limiters'].items():
                        if network in limiter_id and limiter_status['backoff_until']:
                            logger.error(f"Rate limiter {limiter_id} in backoff until: {limiter_status['backoff_until']}")
                            logger.error("Try again later or use --mock flag for testing")
        
        finally:
            await scheduler_cli.shutdown()
    
    asyncio.run(run_collection())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--network', '-n', help='Filter by network (optional)')
@click.option('--limit', '-l', default=10, help='Number of recent records to show')
@click.option('--hours', '-h', default=24, help='Hours to look back for activity timeline')
@click.option('--errors', is_flag=True, help='Show detailed error analysis')
@click.option('--performance', is_flag=True, help='Show performance metrics')
def new_pools_stats(config, network, limit, hours, errors, performance):
    """Display comprehensive statistics and recent data from new pools collection."""
    async def show_stats():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=True)  # Mock for stats check
        
        try:
            logger.info(f"Retrieving comprehensive new pools statistics (network: {network}, limit: {limit})")
            
            # Initialize statistics engine
            stats_engine = StatisticsEngine(scheduler_cli.db_manager)
            
            # Get comprehensive statistics
            stats = await stats_engine.get_comprehensive_statistics(network, limit, hours)
            
            print(f"\n=== New Pools Collection Statistics ===")
            print(f"Total Pools in Database: {stats.total_pools:,}")
            print(f"Total History Records: {stats.total_history_records:,}")
            
            # Network distribution
            if stats.network_distribution:
                print(f"\n=== Network Distribution ===")
                for network_name, count in sorted(stats.network_distribution.items()):
                    percentage = (count / stats.total_history_records * 100) if stats.total_history_records > 0 else 0
                    print(f"{network_name}: {count:,} records ({percentage:.1f}%)")
            
            # DEX distribution
            if stats.dex_distribution:
                print(f"\n=== DEX Distribution ===")
                sorted_dexes = sorted(stats.dex_distribution.items(), key=lambda x: x[1], reverse=True)
                for dex_name, count in sorted_dexes[:10]:  # Top 10 DEXes
                    percentage = (count / stats.total_history_records * 100) if stats.total_history_records > 0 else 0
                    print(f"{dex_name}: {count:,} records ({percentage:.1f}%)")
                
                if len(sorted_dexes) > 10:
                    remaining_count = sum(count for _, count in sorted_dexes[10:])
                    print(f"... and {len(sorted_dexes) - 10} more DEXes with {remaining_count:,} records")
            
            # Collection activity timeline
            if stats.collection_activity:
                print(f"\n=== Collection Activity (Last {hours} Hours) ===")
                total_recent_records = sum(activity['records'] for activity in stats.collection_activity)
                print(f"Total records collected: {total_recent_records:,}")
                
                # Show hourly breakdown for last 6 hours
                recent_activity = stats.collection_activity[-6:] if len(stats.collection_activity) > 6 else stats.collection_activity
                if recent_activity:
                    print("Recent hourly activity:")
                    for activity in recent_activity:
                        unique_pools = activity.get('unique_pools', 'N/A')
                        avg_reserve = activity.get('avg_reserve_usd')
                        total_volume = activity.get('total_volume_h24')
                        
                        activity_line = f"  {activity['hour']}: {activity['records']} records"
                        if unique_pools != 'N/A':
                            activity_line += f" ({unique_pools} unique pools)"
                        if avg_reserve:
                            activity_line += f", avg reserve: ${avg_reserve:,.2f}"
                        if total_volume:
                            activity_line += f", total volume: ${total_volume:,.2f}"
                        
                        print(activity_line)
            
            # Error summary
            if stats.error_summary:
                print(f"\n=== Collection Health (Last {hours} Hours) ===")
                error_sum = stats.error_summary
                print(f"Total Executions: {error_sum['total_executions']}")
                print(f"Successful: {error_sum['successful_executions']} ({error_sum['success_rate']:.1f}%)")
                print(f"Failed: {error_sum['failed_executions']}")
                print(f"Partial: {error_sum['partial_executions']}")
            
            # Rate limiting context
            if stats.rate_limiting_context:
                rate_ctx = stats.rate_limiting_context
                if rate_ctx['rate_limit_errors_count'] > 0:
                    print(f"\n=== Rate Limiting Issues ===")
                    print(f"Rate limit errors in last {hours}h: {rate_ctx['rate_limit_errors_count']}")
                    print(f"Rate limit alerts: {rate_ctx['rate_limit_alerts_count']}")
                    
                    if rate_ctx['recent_rate_limit_errors']:
                        print("Recent rate limit errors:")
                        for error in rate_ctx['recent_rate_limit_errors']:
                            print(f"  {error['timestamp']} - {error['collector_type']}: {error['error_message']}")
            
            # Recent records
            if stats.recent_records:
                print(f"\n=== Recent Records (Last {limit}) ===")
                for i, record in enumerate(stats.recent_records, 1):
                    print(f"\n{i}. {record['name']} ({record['pool_id']})")
                    print(f"  Network: {record['network_id']}, DEX: {record['dex_id']}")
                    print(f"  Address: {record['address']}")
                    
                    if record['reserve_in_usd']:
                        print(f"  Reserve: ${record['reserve_in_usd']:,.2f}")
                    
                    if record['volume_usd_h24']:
                        print(f"  24h Volume: ${record['volume_usd_h24']:,.2f}")
                    
                    if record['price_change_percentage_h1'] is not None:
                        change_1h = record['price_change_percentage_h1']
                        change_24h = record['price_change_percentage_h24'] or 0
                        print(f"  Price Change: 1h: {change_1h:+.2f}%, 24h: {change_24h:+.2f}%")
                    
                    if record['fdv_usd']:
                        print(f"  FDV: ${record['fdv_usd']:,.2f}")
                    
                    if record['pool_created_at']:
                        print(f"  Pool Created: {record['pool_created_at']}")
                    
                    if record['collected_at']:
                        print(f"  Collected: {record['collected_at']}")
                    
                    if record['transactions_h24_buys'] is not None and record['transactions_h24_sells'] is not None:
                        buys = record['transactions_h24_buys'] or 0
                        sells = record['transactions_h24_sells'] or 0
                        print(f"  24h Transactions: {buys} buys, {sells} sells")
            
            # Detailed error analysis if requested
            if errors:
                print(f"\n=== Detailed Error Analysis ===")
                error_analysis = await stats_engine.get_error_analysis(network, hours)
                
                print(f"Total errors in last {hours}h: {error_analysis.error_count}")
                print(f"Rate limiting errors: {error_analysis.rate_limiting_errors}")
                print(f"Validation errors: {error_analysis.validation_errors}")
                print(f"Database errors: {error_analysis.database_errors}")
                print(f"API errors: {error_analysis.api_errors}")
                
                if error_analysis.recent_errors:
                    print(f"\nRecent errors:")
                    for error in error_analysis.recent_errors[:5]:
                        print(f"  {error['timestamp']} - {error['collector_type']} ({error['error_type']})")
                        print(f"    {error['error_message']}")
                
                if error_analysis.recovery_suggestions:
                    print(f"\nRecovery suggestions:")
                    for suggestion in error_analysis.recovery_suggestions:
                        print(f"  • {suggestion}")
            
            # Performance metrics if requested
            if performance:
                print(f"\n=== Performance Metrics ===")
                perf_metrics = await stats_engine.get_collection_performance_metrics(network, hours)
                
                print(f"Total executions: {perf_metrics['total_executions']}")
                print(f"Average execution time: {perf_metrics['avg_execution_time']}s")
                print(f"Min/Max execution time: {perf_metrics['min_execution_time']}s / {perf_metrics['max_execution_time']}s")
                print(f"Total records collected: {perf_metrics['total_records_collected']:,}")
                print(f"Average records per execution: {perf_metrics['avg_records_per_execution']:.1f}")
                print(f"Processing rate: {perf_metrics['records_per_second']:.1f} records/second")
            
            # Summary
            print(f"\n=== Summary ===")
            if network:
                print(f"Showing statistics for network: {network}")
            else:
                print("Showing statistics for all networks")
            
            if stats.total_history_records > 0:
                latest_collection = stats.recent_records[0]['collected_at'] if stats.recent_records else "Unknown"
                print(f"Latest collection: {latest_collection}")
                
                # Calculate collection frequency
                if len(stats.collection_activity) > 1:
                    total_hours_with_data = len([a for a in stats.collection_activity if a['records'] > 0])
                    if total_hours_with_data > 0:
                        avg_records_per_hour = sum(a['records'] for a in stats.collection_activity) / total_hours_with_data
                        print(f"Average records per active hour: {avg_records_per_hour:.1f}")
            else:
                print("No collection data found")
            
            # Show available options
            print(f"\nUse --errors for detailed error analysis, --performance for performance metrics")
        
        except Exception as e:
            logger.error(f"Failed to retrieve statistics: {e}")
            print(f"Error retrieving statistics: {e}")
        
        finally:
            await scheduler_cli.shutdown()
    
    asyncio.run(show_stats())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--network', '-n', help='Filter by network (optional)')
@click.option('--hours', '-h', default=24, help='Hours to look back for error analysis')
def new_pools_errors(config, network, hours):
    """Display comprehensive error analysis for new pools collection with rate limiting context."""
    async def show_errors():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=True)
        
        try:
            logger.info(f"Analyzing new pools collection errors (network: {network}, hours: {hours})")
            
            # Initialize statistics engine
            stats_engine = StatisticsEngine(scheduler_cli.db_manager)
            
            # Get comprehensive error analysis
            error_analysis = await stats_engine.get_error_analysis(network, hours)
            
            print(f"\n=== New Pools Collection Error Analysis (Last {hours} Hours) ===")
            
            # Error summary
            print(f"\nTotal errors: {error_analysis.error_count}")
            if error_analysis.error_count == 0:
                print("✅ No errors found in the specified time period!")
                return
            
            # Error categorization
            print(f"\n=== Error Categories ===")
            print(f"Rate limiting errors: {error_analysis.rate_limiting_errors}")
            print(f"Validation errors: {error_analysis.validation_errors}")
            print(f"Database errors: {error_analysis.database_errors}")
            print(f"API errors: {error_analysis.api_errors}")
            
            # Recent errors with details
            if error_analysis.recent_errors:
                print(f"\n=== Recent Errors (Last 10) ===")
                for i, error in enumerate(error_analysis.recent_errors[:10], 1):
                    print(f"\n{i}. {error['timestamp']} - {error['collector_type']}")
                    print(f"   Type: {error['error_type']}")
                    print(f"   Message: {error['error_message']}")
                    if error['execution_time']:
                        print(f"   Execution time: {error['execution_time']:.2f}s")
                    if error['records_collected']:
                        print(f"   Records collected: {error['records_collected']}")
            
            # Recovery suggestions
            if error_analysis.recovery_suggestions:
                print(f"\n=== Recovery Suggestions ===")
                for i, suggestion in enumerate(error_analysis.recovery_suggestions, 1):
                    print(f"{i}. {suggestion}")
            
            # Rate limiting context
            stats = await stats_engine.get_comprehensive_statistics(network, 5, hours)
            if stats.rate_limiting_context and stats.rate_limiting_context['rate_limit_errors_count'] > 0:
                print(f"\n=== Rate Limiting Context ===")
                rate_ctx = stats.rate_limiting_context
                print(f"Rate limit errors: {rate_ctx['rate_limit_errors_count']}")
                print(f"Rate limit alerts: {rate_ctx['rate_limit_alerts_count']}")
                
                if rate_ctx['recent_rate_limit_errors']:
                    print("\nRecent rate limit errors:")
                    for error in rate_ctx['recent_rate_limit_errors']:
                        print(f"  {error['timestamp']} - {error['collector_type']}")
                        print(f"    {error['error_message']}")
                
                print(f"\n💡 Use 'rate-limit-status' command to check current rate limiter status")
                print(f"💡 Use 'reset-rate-limiter --network {network or 'NETWORK'}' to reset rate limiters if needed")
            
            # Performance impact
            perf_metrics = await stats_engine.get_collection_performance_metrics(network, hours)
            if perf_metrics['total_executions'] > 0:
                success_rate = ((perf_metrics['total_executions'] - error_analysis.error_count) / perf_metrics['total_executions']) * 100
                print(f"\n=== Performance Impact ===")
                print(f"Success rate: {success_rate:.1f}%")
                print(f"Total executions: {perf_metrics['total_executions']}")
                print(f"Failed executions: {error_analysis.error_count}")
        
        except Exception as e:
            logger.error(f"Failed to analyze errors: {e}")
            print(f"Error analyzing errors: {e}")
        
        finally:
            await scheduler_cli.shutdown()
    
    asyncio.run(show_errors())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--sources', '-s', help='Comma-separated list of sources (e.g., reference,lowcap,micro)')
@click.option('--mock', is_flag=True, help='Use mock clients for testing')
def collect_enhanced_watchlist(config, sources, mock):
    """Run enhanced watchlist collection for specified sources."""
    async def run_collection():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=mock)
        
        try:
            # Load configuration
            config_manager = ConfigManager(config)
            collection_config = config_manager.load_config()
            
            # Parse sources
            if sources:
                source_list = [s.strip() for s in sources.split(',')]
            else:
                source_list = collection_config.enhanced_watchlist.sources
            
            logger.info(f"Starting enhanced watchlist collection for sources: {source_list}")
            
            # Get rate limiter
            rate_limiter = await scheduler_cli.rate_limit_coordinator.get_limiter("enhanced_watchlist")
            
            # Create metadata tracker
            metadata_tracker = MetadataTracker(db_manager=scheduler_cli.db_manager)
            
            # Create collector instance
            collector = EnhancedWatchlistCollector(
                config=collection_config,
                db_manager=scheduler_cli.db_manager,
                metadata_tracker=metadata_tracker,
                use_mock=mock,
                watchlist_sources=source_list
            )
            
            # Set rate limiter
            if hasattr(collector, 'set_rate_limiter'):
                collector.set_rate_limiter(rate_limiter)
            
            # Execute collection
            result = await collector.collect()
            
            # Display results
            print(f"\n=== Enhanced Watchlist Collection Results ===")
            print(f"Sources: {', '.join(source_list)}")
            print(f"Success: {result.success}")
            print(f"Total Records: {result.records_collected}")
            print(f"Collection Time: {result.collection_time}")
            
            if result.metadata:
                print(f"\n=== Collection Details ===")
                print(f"Sources Processed: {result.metadata.get('sources_processed', 0)}")
                print(f"Entries Processed: {result.metadata.get('entries_processed', 0)}")
                print(f"Addresses Resolved: {result.metadata.get('addresses_resolved', 0)}")
                print(f"API Calls Made: {result.metadata.get('api_calls_made', 0)}")
                print(f"Resolution Rate: {result.metadata.get('addresses_resolved', 0) / max(result.metadata.get('entries_processed', 1), 1) * 100:.1f}%")
            
            if result.errors:
                print(f"\n=== Errors ({len(result.errors)}) ===")
                for error in result.errors:
                    print(f"  • {error}")
            
            # Show rate limiting status
            global_status = await scheduler_cli.rate_limit_coordinator.get_global_status()
            print(f"\n=== Rate Usage ===")
            print(f"Daily Usage: {global_status['global_usage']['daily_usage_percentage']:.1f}%")
            print(f"Total Daily Requests: {global_status['global_usage']['total_daily_requests']}")
            
        except Exception as e:
            logger.error(f"Enhanced watchlist collection failed: {e}")
            
            if "rate limit" in str(e).lower() or "429" in str(e):
                logger.error("This appears to be a rate limiting issue.")
                logger.error("Try again later or use --mock flag for testing")
        
        finally:
            await scheduler_cli.shutdown()
    
    asyncio.run(run_collection())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
def reset_watchlist(config):
    """Set all watchlist entries to inactive (is_active = False)."""
    async def reset_entries():
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=True)
        
        try:
            logger.info("Resetting all watchlist entries to inactive...")
            
            # Use the database manager's session to execute raw SQL
            from sqlalchemy import text
            
            with scheduler_cli.db_manager.connection.get_session() as session:
                result = session.execute(
                    text("UPDATE watchlist SET is_active = :is_active, updated_at = CURRENT_TIMESTAMP"),
                    {"is_active": False}
                )
                session.commit()
                rows_affected = result.rowcount
            
            logger.info(f"Successfully set {rows_affected} watchlist entries to inactive")
            print(f"\n✅ Reset complete: {rows_affected} watchlist entries set to inactive")
            print(f"💡 Now run: python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources \"micro\"")
            
        except Exception as e:
            logger.error(f"Failed to reset watchlist entries: {e}")
            print(f"❌ Error: {e}")
        
        finally:
            await scheduler_cli.shutdown()
    
    asyncio.run(reset_entries())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--json-path', '-j', default='watchlist_state.json', help='Path to watchlist state JSON file')
@click.option('--dry-run', is_flag=True, help='Preview changes without updating database')
def sync_watchlist_status(config, json_path, dry_run):
    """Synchronize watchlist is_active status from watchlist_state.json file.
    
    This command reads the watchlist_state.json file and updates the is_active
    field in the database based on the 'active' field in the JSON.
    """
    async def sync_status():
        import json
        from pathlib import Path
        
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=True)
        
        try:
            # Load watchlist state JSON
            json_file = Path(json_path)
            if not json_file.exists():
                logger.error(f"Watchlist state file not found: {json_path}")
                print(f"❌ Error: File not found: {json_path}")
                return
            
            logger.info(f"Loading watchlist state from {json_path}...")
            with open(json_file, 'r') as f:
                state_data = json.load(f)
            
            tokens = state_data.get('tokens', {})
            meta = state_data.get('meta', {})
            
            if not tokens:
                logger.warning("No tokens found in watchlist state")
                print("⚠️  Warning: No tokens found in watchlist state file")
                return
            
            # Extract active and inactive addresses
            active_addresses = []
            inactive_addresses = []
            
            for token_address, token_data in tokens.items():
                is_active = token_data.get('active', False)
                if is_active:
                    active_addresses.append(token_address)
                else:
                    inactive_addresses.append(token_address)
            
            logger.info(f"Loaded {len(tokens)} tokens from state file")
            logger.info(f"Active: {len(active_addresses)}, Inactive: {len(inactive_addresses)}")
            
            print(f"\n=== Watchlist State Analysis ===")
            print(f"Total tokens: {len(tokens)}")
            print(f"✅ Active: {len(active_addresses)}")
            print(f"❌ Inactive: {len(inactive_addresses)}")
            print(f"📅 Total cycles: {meta.get('total_cycles', 'N/A')}")
            print(f"🕐 Last run: {meta.get('last_run', 'N/A')}")
            
            if dry_run:
                print(f"\n🔍 DRY RUN MODE - No changes will be made")
                print(f"Would update {len(active_addresses)} tokens to active")
                print(f"Would update {len(inactive_addresses)} tokens to inactive")
                return
            
            # Perform bulk update using the existing method
            logger.info("Performing bulk update...")
            addresses_by_status = {
                'active': active_addresses,
                'inactive': inactive_addresses
            }
            
            stats = await scheduler_cli.db_manager.bulk_update_watchlist_active_status(addresses_by_status)
            
            print(f"\n=== Synchronization Results ===")
            print(f"✅ Tokens set to active: {stats.get('active_updated', 0)}")
            print(f"❌ Tokens set to inactive: {stats.get('inactive_updated', 0)}")
            print(f"⚠️  Tokens not found in DB: {stats.get('not_found', 0)}")
            
            if stats.get('not_found', 0) > 0:
                print(f"\n💡 Note: 'Not found' means tokens are in JSON but not in database watchlist")
            
            logger.info("Synchronization completed successfully")
            print(f"\n✅ Synchronization completed successfully!")
            
        except Exception as e:
            logger.error(f"Failed to synchronize watchlist status: {e}")
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await scheduler_cli.shutdown()
    
    asyncio.run(sync_status())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--json-path', '-j', default='watchlist_state.json', help='Path to watchlist state JSON file')
def diagnose_watchlist(config, json_path):
    """Diagnose which tokens are in watchlist_state.json but not in database.
    
    This command helps identify why some tokens show as "not found" during sync.
    """
    async def run_diagnosis():
        import json
        from pathlib import Path
        from sqlalchemy import text
        
        scheduler_cli = SchedulerCLI(config)
        await scheduler_cli.initialize(use_mock=True)
        
        try:
            # Load JSON
            json_file = Path(json_path)
            if not json_file.exists():
                print(f"❌ Error: File not found: {json_path}")
                return
            
            with open(json_file, 'r') as f:
                state_data = json.load(f)
            
            tokens = state_data.get('tokens', {})
            json_addresses = set(tokens.keys())
            
            # Get addresses from database
            with scheduler_cli.db_manager.connection.get_session() as session:
                result = session.execute(
                    text("SELECT network_address FROM watchlist WHERE network_address IS NOT NULL")
                )
                db_addresses = {row[0] for row in result}
                
                # Get total stats
                result = session.execute(text("SELECT COUNT(*) FROM watchlist"))
                total_entries = result.scalar()
                
                result = session.execute(
                    text("SELECT COUNT(*) FROM watchlist WHERE is_active = :active"),
                    {"active": True}
                )
                active_entries = result.scalar()
            
            # Find missing
            missing_addresses = json_addresses - db_addresses
            found_addresses = json_addresses & db_addresses
            
            # Analyze missing tokens
            active_missing = []
            inactive_missing = []
            
            for address in missing_addresses:
                token_data = tokens[address]
                is_active = token_data.get('active', False)
                if is_active:
                    active_missing.append((address, token_data))
                else:
                    inactive_missing.append((address, token_data))
            
            # Print results
            print(f"\n{'=' * 70}")
            print("WATCHLIST SYNC DIAGNOSTIC")
            print(f"{'=' * 70}")
            print(f"\nTokens in watchlist_state.json: {len(json_addresses)}")
            print(f"Tokens found in database: {len(found_addresses)}")
            print(f"Tokens NOT in database: {len(missing_addresses)}")
            print(f"Match rate: {len(found_addresses)/len(json_addresses)*100:.1f}%")
            
            print(f"\n{'=' * 70}")
            print("MISSING TOKENS BREAKDOWN")
            print(f"{'=' * 70}")
            print(f"Active missing (⚠️  CRITICAL): {len(active_missing)}")
            print(f"Inactive missing (ℹ️  Normal): {len(inactive_missing)}")
            
            if active_missing:
                print(f"\n🔴 ACTIVE TOKENS NOT IN DATABASE:")
                print("=" * 70)
                for i, (address, data) in enumerate(active_missing[:10], 1):
                    print(f"\n{i}. FULL TOKEN ADDRESS:")
                    print(f"   {address}")
                    print(f"   Peak score: {data.get('peak_score', 'N/A')}")
                    print(f"   Liquidity: ${data.get('prev_metrics', {}).get('liquidity', 0):,.2f}")
                    print(f"   Smart degen: {data.get('prev_metrics', {}).get('smart_degen_count', 0)}")
                    print(f"   First seen: {data.get('first_seen', 'N/A')[:19]}")
                    print(f"   Last seen: {data.get('last_seen', 'N/A')[:19]}")
                
                if len(active_missing) > 10:
                    print(f"\n... and {len(active_missing) - 10} more")
                
                # Export to file for investigation
                print(f"\n💾 Full list of active missing tokens:")
                for address, data in active_missing:
                    print(f"   {address}")
            
            if inactive_missing:
                print(f"\n⚪ INACTIVE TOKENS NOT IN DATABASE:")
                print("=" * 70)
                
                # Group by reason
                by_reason = {}
                for address, data in inactive_missing:
                    reason = data.get('deactivation_reason', 'unknown')
                    by_reason[reason] = by_reason.get(reason, 0) + 1
                
                print(f"\nBy deactivation reason:")
                for reason, count in sorted(by_reason.items(), key=lambda x: x[1], reverse=True):
                    print(f"  • {reason}: {count}")
                
                # Show first 5 with full addresses
                print(f"\nSample (first 5) with FULL TOKEN ADDRESSES:")
                for i, (address, data) in enumerate(inactive_missing[:5], 1):
                    print(f"\n{i}. {address}")
                    print(f"   Peak score: {data.get('peak_score', 'N/A')}")
                    print(f"   Reason: {data.get('deactivation_reason', 'N/A')}")
                    print(f"   Deactivated: {data.get('deactivated_at', 'N/A')[:19]}")
                
                # Export all to see full list
                if len(inactive_missing) > 5:
                    print(f"\n💾 All {len(inactive_missing)} inactive missing token addresses:")
                    for address, _ in inactive_missing:
                        print(f"   {address}")
            
            # Database stats
            print(f"\n{'=' * 70}")
            print("DATABASE WATCHLIST TABLE")
            print(f"{'=' * 70}")
            print(f"Total entries: {total_entries}")
            print(f"Active entries: {active_entries}")
            print(f"Inactive entries: {total_entries - active_entries}")
            
            # Explanation
            print(f"\n{'=' * 70}")
            print("WHY ARE TOKENS MISSING?")
            print(f"{'=' * 70}")
            print("""
Common reasons:

1. NORMAL BEHAVIOR (Most Common)
   • watchlist_state.json tracks ALL monitored tokens
   • Database watchlist only contains tokens that met entry criteria
   • Missing = monitored but didn't qualify for watchlist

2. TIMING ISSUE
   • Token became inactive before being added to database
   • Token appeared briefly then disappeared
   • Collector cycles vs database update timing

3. CRITERIA NOT MET
   • Token didn't meet minimum score/liquidity threshold
   • Token filtered out by enhanced watchlist collector rules
   • Token from excluded DEX or network
            """)
            
            # Troubleshooting guide
            print(f"\n{'=' * 70}")
            print("HOW TO INVESTIGATE REJECTIONS")
            print(f"{'=' * 70}")
            print("""
To find out why a specific token wasn't added to database:

1. CHECK ENHANCED WATCHLIST HISTORY TABLE
   These tokens may be in enhanced_watchlist_history but not watchlist:
   
   SELECT * FROM enhanced_watchlist_history 
   WHERE base_token_address = 'TOKEN_ADDRESS'
   ORDER BY collected_at DESC;

2. CHECK COLLECTOR LOGS
   Search for the token address in collector logs:
   
   grep "TOKEN_ADDRESS" /var/log/collector.log
   grep "rejected" /var/log/collector.log | grep "TOKEN_ADDRESS"

3. CHECK ENHANCED WATCHLIST COLLECTOR LOGIC
   File: gecko_terminal_collector/collectors/enhanced_watchlist_collector.py
   
   Look for rejection reasons:
   - Minimum score threshold (typically 30-50)
   - Minimum liquidity threshold
   - DEX filtering
   - Duplicate detection
   - Address resolution failures

4. COMMON REJECTION PATTERNS
   • "Score too low" - didn't meet minimum threshold
   • "Liquidity insufficient" - below minimum liquidity
   • "Address resolution failed" - couldn't resolve base token address
   • "Duplicate entry" - already in watchlist
   • "Filtered DEX" - from excluded DEX
            """)
            
            if active_missing:
                print(f"""
⚠️  ACTION REQUIRED:

You have {len(active_missing)} ACTIVE tokens missing from database!

Recommendations:
1. Re-run enhanced watchlist collector:
   python -m examples.cli_with_scheduler collect-enhanced-watchlist
   
2. Check collector logs for why these weren't added

3. Verify enhanced_watchlist_collector entry criteria

4. Search for specific token:
   grep "TOKEN_ADDRESS" /var/log/collector.log
                """)
            else:
                print("""
✅ All active tokens are in database - system is healthy!
   Missing tokens are all inactive (normal behavior).
                """)
            
        except Exception as e:
            logger.error(f"Diagnosis failed: {e}")
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await scheduler_cli.shutdown()
    
    asyncio.run(run_diagnosis())


@cli.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--collector', help='Reset rate limiter for specific collector (e.g., dex_monitoring, new_pools_solana)')
@click.option('--network', help='Reset rate limiter for new pools collector of specific network (e.g., solana, ethereum)')
@click.option('--all', 'reset_all', is_flag=True, help='Reset all rate limiters')
def reset_rate_limiter(config, collector, network, reset_all):
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
        elif network:
            # Reset rate limiter for new pools collector of specific network
            collector_id = f"new_pools_{network}"
            try:
                limiter = await scheduler_cli.rate_limit_coordinator.get_limiter(collector_id)
                # Reset backoff state
                limiter.backoff_state.consecutive_failures = 0
                limiter.backoff_state.backoff_until = None
                # Reset circuit breaker
                limiter.circuit_state = limiter.circuit_state.CLOSED
                limiter.circuit_failure_count = 0
                limiter.circuit_last_failure = None
                limiter.circuit_next_attempt = None
                logger.info(f"Reset rate limiter for new pools collector on network '{network}' ({collector_id})")
                
            except Exception as e:
                logger.error(f"Failed to reset rate limiter for new pools collector on network '{network}': {e}")
        else:
            logger.error("Must specify either --collector, --network, or --all")
        
        await scheduler_cli.shutdown()
    
    asyncio.run(reset_limiter())


if __name__ == '__main__':
    cli()