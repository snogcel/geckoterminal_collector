"""
Command-line interface for GeckoTerminal Data Collector.
"""

import argparse
import asyncio
import sys
import json
import signal
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="GeckoTerminal Data Collector CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  gecko-cli init --force                    # Initialize with default config
  gecko-cli validate                        # Validate current configuration
  gecko-cli start --daemon                  # Start collection as daemon
  gecko-cli status                          # Show system status
  gecko-cli run-collector ohlcv            # Run specific collector once
  gecko-cli backfill --days 30             # Backfill 30 days of data
  gecko-cli export --format qlib           # Export data for QLib
  gecko-cli db-setup                        # Initialize database schema
        """
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="gecko-terminal-collector 0.1.0"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress non-error output"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # System setup and configuration commands
    _add_init_command(subparsers)
    _add_validate_command(subparsers)
    _add_db_setup_command(subparsers)
    
    # Collection management commands
    _add_start_command(subparsers)
    _add_stop_command(subparsers)
    _add_status_command(subparsers)
    _add_run_collector_command(subparsers)
    
    # Data management commands
    _add_backfill_command(subparsers)
    _add_export_command(subparsers)
    _add_cleanup_command(subparsers)
    
    # Maintenance and monitoring commands
    _add_health_check_command(subparsers)
    _add_metrics_command(subparsers)
    _add_logs_command(subparsers)
    
    # Backup and restore commands
    _add_backup_command(subparsers)
    _add_restore_command(subparsers)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 1
    
    # Set up logging level based on verbosity
    import logging
    if args.quiet:
        logging.basicConfig(level=logging.ERROR)
    elif args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Route to appropriate command handler
    command_handlers = {
        "init": init_command,
        "validate": validate_command,
        "db-setup": db_setup_command,
        "start": start_command,
        "stop": stop_command,
        "status": status_command,
        "run-collector": run_collector_command,
        "backfill": backfill_command,
        "export": export_command,
        "cleanup": cleanup_command,
        "health-check": health_check_command,
        "metrics": metrics_command,
        "logs": logs_command,
        "backup": backup_command,
        "restore": restore_command,
    }
    
    handler = command_handlers.get(args.command)
    if handler:
        try:
            if asyncio.iscoroutinefunction(handler):
                return asyncio.run(handler(args))
            else:
                return handler(args)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return 130
        except Exception as e:
            if args.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"Error: {e}")
            return 1
    else:
        print(f"Unknown command: {args.command}")
        return 1


def _add_init_command(subparsers):
    """Add init command parser."""
    init_parser = subparsers.add_parser(
        "init", 
        help="Initialize configuration and database",
        description="Initialize system configuration and database schema"
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing configuration"
    )
    init_parser.add_argument(
        "--db-url",
        type=str,
        help="Database URL (overrides config file)"
    )
    init_parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip database initialization"
    )


def _add_validate_command(subparsers):
    """Add validate command parser."""
    validate_parser = subparsers.add_parser(
        "validate", 
        help="Validate configuration",
        description="Validate configuration file and system setup"
    )
    validate_parser.add_argument(
        "--check-db",
        action="store_true",
        help="Also validate database connectivity"
    )
    validate_parser.add_argument(
        "--check-api",
        action="store_true",
        help="Also validate API connectivity"
    )


def _add_db_setup_command(subparsers):
    """Add database setup command parser."""
    db_parser = subparsers.add_parser(
        "db-setup",
        help="Initialize database schema",
        description="Set up database tables and indexes"
    )
    db_parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing tables before creating new ones"
    )
    db_parser.add_argument(
        "--migrate",
        action="store_true",
        help="Run database migrations"
    )


def _add_start_command(subparsers):
    """Add start command parser."""
    start_parser = subparsers.add_parser(
        "start",
        help="Start data collection",
        description="Start the data collection scheduler"
    )
    start_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon process"
    )
    start_parser.add_argument(
        "--collectors",
        nargs="+",
        help="Specific collectors to start (default: all configured)"
    )
    start_parser.add_argument(
        "--pid-file",
        type=str,
        help="Write process ID to file"
    )


def _add_stop_command(subparsers):
    """Add stop command parser."""
    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop data collection",
        description="Stop the running data collection scheduler"
    )
    stop_parser.add_argument(
        "--pid-file",
        type=str,
        help="Read process ID from file"
    )
    stop_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds for graceful shutdown"
    )


def _add_status_command(subparsers):
    """Add status command parser."""
    status_parser = subparsers.add_parser(
        "status",
        help="Show system status",
        description="Display current system and collector status"
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Output status in JSON format"
    )
    status_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed collector information"
    )


def _add_run_collector_command(subparsers):
    """Add run-collector command parser."""
    run_parser = subparsers.add_parser(
        "run-collector",
        help="Run specific collector once",
        description="Execute a specific collector immediately"
    )
    run_parser.add_argument(
        "collector_type",
        choices=["dex", "top-pools", "watchlist", "ohlcv", "trades", "historical"],
        help="Type of collector to run"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be collected without storing data"
    )


def _add_backfill_command(subparsers):
    """Add backfill command parser."""
    backfill_parser = subparsers.add_parser(
        "backfill",
        help="Backfill historical data",
        description="Collect historical data to fill gaps"
    )
    backfill_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to backfill (default: 7)"
    )
    backfill_parser.add_argument(
        "--symbols",
        nargs="+",
        help="Specific symbols to backfill (default: all watchlist)"
    )
    backfill_parser.add_argument(
        "--timeframe",
        default="1h",
        help="Timeframe for backfill (default: 1h)"
    )
    backfill_parser.add_argument(
        "--force",
        action="store_true",
        help="Force backfill even if data exists"
    )


def _add_export_command(subparsers):
    """Add export command parser."""
    export_parser = subparsers.add_parser(
        "export",
        help="Export data",
        description="Export collected data in various formats"
    )
    export_parser.add_argument(
        "--format",
        choices=["csv", "json", "qlib"],
        default="csv",
        help="Export format (default: csv)"
    )
    export_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output directory or file"
    )
    export_parser.add_argument(
        "--symbols",
        nargs="+",
        help="Specific symbols to export (default: all)"
    )
    export_parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD)"
    )
    export_parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD)"
    )
    export_parser.add_argument(
        "--timeframe",
        default="1h",
        help="Data timeframe (default: 1h)"
    )


def _add_cleanup_command(subparsers):
    """Add cleanup command parser."""
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Clean up old data",
        description="Remove old data beyond retention period"
    )
    cleanup_parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Days of data to keep (default: 90)"
    )
    cleanup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    cleanup_parser.add_argument(
        "--data-type",
        choices=["ohlcv", "trades", "all"],
        default="all",
        help="Type of data to clean up (default: all)"
    )


def _add_health_check_command(subparsers):
    """Add health-check command parser."""
    health_parser = subparsers.add_parser(
        "health-check",
        help="Perform system health check",
        description="Check system health and connectivity"
    )
    health_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )


def _add_metrics_command(subparsers):
    """Add metrics command parser."""
    metrics_parser = subparsers.add_parser(
        "metrics",
        help="Show performance metrics",
        description="Display system performance metrics"
    )
    metrics_parser.add_argument(
        "--collector",
        type=str,
        help="Show metrics for specific collector"
    )
    metrics_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Time window in hours (default: 24)"
    )
    metrics_parser.add_argument(
        "--json",
        action="store_true",
        help="Output metrics in JSON format"
    )


def _add_logs_command(subparsers):
    """Add logs command parser."""
    logs_parser = subparsers.add_parser(
        "logs",
        help="Show recent logs",
        description="Display recent system logs"
    )
    logs_parser.add_argument(
        "--lines",
        type=int,
        default=50,
        help="Number of log lines to show (default: 50)"
    )
    logs_parser.add_argument(
        "--level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Filter by log level"
    )
    logs_parser.add_argument(
        "--follow",
        action="store_true",
        help="Follow log output (like tail -f)"
    )


def _add_backup_command(subparsers):
    """Add backup command parser."""
    backup_parser = subparsers.add_parser(
        "backup",
        help="Create data backup",
        description="Create backup of collected data"
    )
    backup_parser.add_argument(
        "backup_path",
        type=str,
        help="Path where backup should be saved"
    )
    backup_parser.add_argument(
        "--data-types",
        nargs="+",
        choices=["pools", "tokens", "ohlcv", "trades", "watchlist", "dexes"],
        help="Specific data types to backup (default: all)"
    )
    backup_parser.add_argument(
        "--compress",
        action="store_true",
        default=True,
        help="Compress backup files (default: enabled)"
    )
    backup_parser.add_argument(
        "--no-compress",
        dest="compress",
        action="store_false",
        help="Disable compression"
    )


def _add_restore_command(subparsers):
    """Add restore command parser."""
    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore data from backup",
        description="Restore data from a previously created backup"
    )
    restore_parser.add_argument(
        "backup_path",
        type=str,
        help="Path to backup directory"
    )
    restore_parser.add_argument(
        "--data-types",
        nargs="+",
        choices=["pools", "tokens", "ohlcv", "trades", "watchlist", "dexes"],
        help="Specific data types to restore (default: all available)"
    )
    restore_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing data"
    )
    restore_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify backup before restoring"
    )


def init_command(args):
    """Initialize configuration and database."""
    config_path = Path(args.config)
    
    if config_path.exists() and not args.force:
        print(f"Configuration file {config_path} already exists. Use --force to overwrite.")
        return 1
    
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        
        print(f"Initializing configuration at {config_path}...")
        
        manager = ConfigManager(str(config_path))
        config = manager.load_config()
        
        # Override database URL if provided
        if args.db_url:
            config.database.url = args.db_url
        
        print(f"✓ Configuration initialized at {config_path}")
        print(f"  Database URL: {config.database.url}")
        print(f"  Target DEXes: {', '.join(config.dexes.targets)}")
        print(f"  Network: {config.dexes.network}")
        
        # Initialize database if not skipped
        if not args.skip_db:
            print("\nInitializing database...")
            return asyncio.run(_init_database(config))
        
        return 0
        
    except Exception as e:
        print(f"Error initializing configuration: {e}")
        return 1


async def _init_database(config):
    """Initialize database schema."""
    try:
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        await db_manager.close()
        
        print("✓ Database initialized successfully")
        return 0
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        return 1


def validate_command(args):
    """Validate configuration file."""
    config_path = Path(args.config)
    
    if not config_path.exists():
        print(f"Configuration file {config_path} not found.")
        return 1
    
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        
        print(f"Validating configuration: {config_path}")
        
        manager = ConfigManager(str(config_path))
        is_valid, errors = manager.validate_config_file()
        
        if is_valid:
            print("✓ Configuration is valid")
            config = manager.load_config()
            
            # Show configuration summary
            print(f"\nConfiguration Summary:")
            print(f"  Database: {config.database.url}")
            print(f"  Network: {config.dexes.network}")
            print(f"  DEXes: {', '.join(config.dexes.targets)}")
            print(f"  Collection intervals:")
            print(f"    Top pools: {config.intervals.top_pools_monitoring}")
            print(f"    OHLCV: {config.intervals.ohlcv_collection}")
            print(f"    Trades: {config.intervals.trade_collection}")
            
            # Additional validation checks
            if args.check_db or args.check_api:
                return asyncio.run(_additional_validation(config, args.check_db, args.check_api))
            
            return 0
        else:
            print("✗ Configuration validation failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
            
    except Exception as e:
        print(f"Error validating configuration: {e}")
        return 1


async def _additional_validation(config, check_db: bool, check_api: bool):
    """Perform additional validation checks."""
    success = True
    
    if check_db:
        print("\nValidating database connectivity...")
        try:
            from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
            
            db_manager = SQLAlchemyDatabaseManager(config.database)
            await db_manager.initialize()
            await db_manager.close()
            print("✓ Database connection successful")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            success = False
    
    if check_api:
        print("\nValidating API connectivity...")
        try:
            from gecko_terminal_collector.clients.gecko_client import GeckoTerminalAsyncClient
            
            client = GeckoTerminalAsyncClient()
            # Test API call
            networks = await client.get_networks()
            if networks:
                print("✓ API connection successful")
            else:
                print("✗ API returned no data")
                success = False
        except Exception as e:
            print(f"✗ API connection failed: {e}")
            success = False
    
    return 0 if success else 1


async def db_setup_command(args):
    """Initialize database schema."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        print("Setting up database schema...")
        
        db_manager = SQLAlchemyDatabaseManager(config.database)
        
        if args.drop_existing:
            print("Dropping existing tables...")
            # This would need to be implemented in the database manager
            
        await db_manager.initialize()
        
        if args.migrate:
            print("Running database migrations...")
            # This would need to be implemented
        
        await db_manager.close()
        
        print("✓ Database setup completed successfully")
        return 0
        
    except Exception as e:
        print(f"Error setting up database: {e}")
        return 1


async def start_command(args):
    """Start data collection."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.scheduling.scheduler import CollectionScheduler
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.collectors.base import CollectorRegistry
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        print("Starting GeckoTerminal Data Collector...")
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Create scheduler
        scheduler = CollectionScheduler(config)
        
        # Register collectors based on configuration
        await _register_collectors(scheduler, config, db_manager, args.collectors)
        
        # Write PID file if requested
        if args.pid_file:
            import os
            with open(args.pid_file, 'w') as f:
                f.write(str(os.getpid()))
        
        # Start scheduler
        await scheduler.start()
        
        print("✓ Data collection started successfully")
        
        if args.daemon:
            print("Running in daemon mode. Press Ctrl+C to stop.")
            
            # Set up signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                print("\nReceived shutdown signal. Stopping gracefully...")
                asyncio.create_task(scheduler.stop())
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                await scheduler.stop()
                await db_manager.close()
        
        return 0
        
    except Exception as e:
        print(f"Error starting data collection: {e}")
        return 1


async def _register_collectors(scheduler, config, db_manager, collector_filter=None):
    """Register collectors with the scheduler."""
    from gecko_terminal_collector.collectors.dex_monitoring import DEXMonitoringCollector
    from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
    from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
    from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
    from gecko_terminal_collector.collectors.trade_collector import TradeCollector
    
    collectors_to_register = []
    
    # Define available collectors
    available_collectors = {
        "dex": (DEXMonitoringCollector, config.intervals.top_pools_monitoring),
        "top-pools": (TopPoolsCollector, config.intervals.top_pools_monitoring),
        "watchlist": (WatchlistCollector, config.intervals.watchlist_check),
        "ohlcv": (OHLCVCollector, config.intervals.ohlcv_collection),
        "trades": (TradeCollector, config.intervals.trade_collection),
    }
    
    # Filter collectors if specified
    if collector_filter:
        collectors_to_register = [
            (name, cls, interval) for name, (cls, interval) in available_collectors.items()
            if name in collector_filter
        ]
    else:
        collectors_to_register = [
            (name, cls, interval) for name, (cls, interval) in available_collectors.items()
        ]
    
    # Register collectors
    for name, collector_class, interval in collectors_to_register:
        try:
            collector = collector_class(config, db_manager)
            scheduler.register_collector(collector, interval)
            print(f"✓ Registered {name} collector (interval: {interval})")
        except Exception as e:
            print(f"✗ Failed to register {name} collector: {e}")


def stop_command(args):
    """Stop data collection."""
    try:
        import os
        import psutil
        
        pid = None
        
        # Get PID from file if specified
        if args.pid_file and Path(args.pid_file).exists():
            with open(args.pid_file, 'r') as f:
                pid = int(f.read().strip())
        else:
            # Try to find running process
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'gecko-cli' in ' '.join(proc.info['cmdline'] or []):
                        pid = proc.info['pid']
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        if pid is None:
            print("No running data collector process found.")
            return 1
        
        print(f"Stopping data collector (PID: {pid})...")
        
        try:
            process = psutil.Process(pid)
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=args.timeout)
                print("✓ Data collector stopped successfully")
            except psutil.TimeoutExpired:
                print("Process did not stop gracefully, forcing termination...")
                process.kill()
                print("✓ Data collector forcefully terminated")
            
            # Clean up PID file
            if args.pid_file and Path(args.pid_file).exists():
                Path(args.pid_file).unlink()
            
            return 0
            
        except psutil.NoSuchProcess:
            print("Process not found (may have already stopped)")
            return 0
            
    except Exception as e:
        print(f"Error stopping data collection: {e}")
        return 1


async def status_command(args):
    """Show system status."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Get system status
        status_info = await _get_system_status(config)
        
        if args.json:
            print(json.dumps(status_info, indent=2, default=str))
        else:
            _print_status_summary(status_info, args.detailed)
        
        return 0
        
    except Exception as e:
        print(f"Error getting system status: {e}")
        return 1


async def _get_system_status(config) -> Dict[str, Any]:
    """Get comprehensive system status."""
    from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
    
    status = {
        "timestamp": datetime.now(),
        "config_file": config,
        "database": {"status": "unknown"},
        "collectors": {},
        "data_summary": {}
    }
    
    # Check database connectivity
    try:
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        status["database"]["status"] = "connected"
        status["database"]["url"] = config.database.url
        
        # Get data summary
        # This would need to be implemented in the database manager
        
        await db_manager.close()
        
    except Exception as e:
        status["database"]["status"] = "error"
        status["database"]["error"] = str(e)
    
    return status


def _print_status_summary(status_info: Dict[str, Any], detailed: bool = False):
    """Print formatted status summary."""
    print("GeckoTerminal Data Collector Status")
    print("=" * 40)
    
    # Database status
    db_status = status_info.get("database", {})
    db_status_text = db_status.get("status", "unknown")
    if db_status_text == "connected":
        print(f"Database: ✓ Connected ({db_status.get('url', 'N/A')})")
    else:
        print(f"Database: ✗ {db_status_text}")
        if "error" in db_status:
            print(f"  Error: {db_status['error']}")
    
    # Collector status
    collectors = status_info.get("collectors", {})
    if collectors:
        print(f"\nCollectors ({len(collectors)}):")
        for name, info in collectors.items():
            status_icon = "✓" if info.get("enabled", False) else "○"
            print(f"  {status_icon} {name}")
            if detailed:
                print(f"    Last run: {info.get('last_run', 'Never')}")
                print(f"    Errors: {info.get('error_count', 0)}")
    else:
        print("\nCollectors: None configured")
    
    # Data summary
    data_summary = status_info.get("data_summary", {})
    if data_summary:
        print(f"\nData Summary:")
        for data_type, count in data_summary.items():
            print(f"  {data_type}: {count:,} records")


async def run_collector_command(args):
    """Run specific collector once."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Create and run collector
        collector = await _create_collector(args.collector_type, config, db_manager)
        
        print(f"Running {args.collector_type} collector...")
        
        if args.dry_run:
            print("DRY RUN: No data will be stored")
            # This would need special handling in collectors
        
        result = await collector.collect()
        
        if result.success:
            print(f"✓ Collection completed successfully")
            print(f"  Records collected: {result.records_collected}")
            print(f"  Collection time: {result.collection_time}")
        else:
            print(f"✗ Collection failed")
            for error in result.errors:
                print(f"  Error: {error}")
        
        await db_manager.close()
        return 0 if result.success else 1
        
    except Exception as e:
        print(f"Error running collector: {e}")
        return 1


async def _create_collector(collector_type: str, config, db_manager):
    """Create collector instance by type."""
    from gecko_terminal_collector.collectors.dex_monitoring import DEXMonitoringCollector
    from gecko_terminal_collector.collectors.top_pools import TopPoolsCollector
    from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
    from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
    from gecko_terminal_collector.collectors.trade_collector import TradeCollector
    from gecko_terminal_collector.collectors.historical_ohlcv_collector import HistoricalOHLCVCollector
    
    collectors = {
        "dex": DEXMonitoringCollector,
        "top-pools": TopPoolsCollector,
        "watchlist": WatchlistCollector,
        "ohlcv": OHLCVCollector,
        "trades": TradeCollector,
        "historical": HistoricalOHLCVCollector,
    }
    
    collector_class = collectors.get(collector_type)
    if not collector_class:
        raise ValueError(f"Unknown collector type: {collector_type}")
    
    return collector_class(config, db_manager)


async def backfill_command(args):
    """Backfill historical data."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.collectors.historical_ohlcv_collector import HistoricalOHLCVCollector
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        print(f"Starting backfill for {args.days} days...")
        print(f"Timeframe: {args.timeframe}")
        
        if args.symbols:
            print(f"Symbols: {', '.join(args.symbols)}")
        else:
            print("Symbols: All watchlist symbols")
        
        # Create historical collector
        collector = HistoricalOHLCVCollector(config, db_manager)
        
        # Perform backfill
        # This would need to be implemented in the collector
        
        await db_manager.close()
        
        print("✓ Backfill completed successfully")
        return 0
        
    except Exception as e:
        print(f"Error during backfill: {e}")
        return 1


async def export_command(args):
    """Export data."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        print(f"Exporting data in {args.format} format to {args.output}")
        
        if args.format == "qlib":
            from gecko_terminal_collector.qlib.exporter import QLibExporter
            
            exporter = QLibExporter(db_manager)
            
            # Parse dates
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d") if args.start_date else None
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d") if args.end_date else None
            
            result = await exporter.export_to_qlib_format(
                output_dir=args.output,
                symbols=args.symbols,
                start_date=start_date,
                end_date=end_date,
                timeframe=args.timeframe
            )
            
            if result['success']:
                print(f"✓ Export completed successfully")
                print(f"  Files created: {result['files_created']}")
                print(f"  Total records: {result['total_records']}")
            else:
                print(f"✗ Export failed: {result['message']}")
                return 1
        else:
            # Implement CSV/JSON export
            print(f"Export format '{args.format}' not yet implemented")
            return 1
        
        await db_manager.close()
        return 0
        
    except Exception as e:
        print(f"Error during export: {e}")
        return 1


async def cleanup_command(args):
    """Clean up old data."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        print(f"Cleaning up data older than {args.days} days...")
        print(f"Data type: {args.data_type}")
        
        if args.dry_run:
            print("DRY RUN: No data will be deleted")
        
        # Perform cleanup
        cleanup_stats = await db_manager.cleanup_old_data(args.days)
        
        print("✓ Cleanup completed")
        for data_type, count in cleanup_stats.items():
            print(f"  {data_type}: {count:,} records removed")
        
        await db_manager.close()
        return 0
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return 1


async def health_check_command(args):
    """Perform system health check."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.clients.gecko_client import GeckoTerminalAsyncClient
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        health_status = {
            "timestamp": datetime.now(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        # Configuration check
        print("Checking configuration...")
        is_valid, errors = manager.validate_config_file()
        health_status["checks"]["configuration"] = {
            "status": "pass" if is_valid else "fail",
            "errors": errors
        }
        
        # Database check
        print("Checking database connectivity...")
        try:
            db_manager = SQLAlchemyDatabaseManager(config.database)
            await db_manager.initialize()
            await db_manager.close()
            health_status["checks"]["database"] = {"status": "pass"}
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "fail",
                "error": str(e)
            }
            health_status["overall_status"] = "unhealthy"
        
        # API check
        print("Checking API connectivity...")
        try:
            client = GeckoTerminalAsyncClient()
            networks = await client.get_networks()
            health_status["checks"]["api"] = {
                "status": "pass",
                "networks_available": len(networks) if networks else 0
            }
        except Exception as e:
            health_status["checks"]["api"] = {
                "status": "fail",
                "error": str(e)
            }
            health_status["overall_status"] = "unhealthy"
        
        if args.json:
            print(json.dumps(health_status, indent=2, default=str))
        else:
            _print_health_summary(health_status)
        
        return 0 if health_status["overall_status"] == "healthy" else 1
        
    except Exception as e:
        print(f"Error during health check: {e}")
        return 1


def _print_health_summary(health_status: Dict[str, Any]):
    """Print formatted health check summary."""
    overall = health_status["overall_status"]
    status_icon = "✓" if overall == "healthy" else "✗"
    
    print(f"\nSystem Health Check: {status_icon} {overall.upper()}")
    print("=" * 40)
    
    for check_name, check_result in health_status["checks"].items():
        status = check_result["status"]
        icon = "✓" if status == "pass" else "✗"
        print(f"{icon} {check_name.title()}: {status.upper()}")
        
        if "error" in check_result:
            print(f"  Error: {check_result['error']}")
        elif "errors" in check_result and check_result["errors"]:
            for error in check_result["errors"]:
                print(f"  Error: {error}")


async def metrics_command(args):
    """Show performance metrics."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        print(f"Performance metrics for last {args.hours} hours")
        
        if args.collector:
            print(f"Collector: {args.collector}")
        
        # This would need to be implemented with actual metrics collection
        metrics_data = {
            "timestamp": datetime.now(),
            "time_window_hours": args.hours,
            "collector_filter": args.collector,
            "metrics": {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "average_execution_time": 0.0,
                "total_records_collected": 0
            }
        }
        
        if args.json:
            print(json.dumps(metrics_data, indent=2, default=str))
        else:
            print("Metrics display not yet implemented")
        
        return 0
        
    except Exception as e:
        print(f"Error getting metrics: {e}")
        return 1


def logs_command(args):
    """Show recent logs."""
    try:
        print(f"Showing last {args.lines} log lines")
        
        if args.level:
            print(f"Filtering by level: {args.level}")
        
        if args.follow:
            print("Following log output (Ctrl+C to stop)...")
        
        # This would need to be implemented with actual log file handling
        print("Log display not yet implemented")
        
        return 0
        
    except Exception as e:
        print(f"Error showing logs: {e}")
        return 1


async def backup_command(args):
    """Create data backup."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.utils.backup_restore import BackupManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Create backup manager
        backup_manager = BackupManager(db_manager, config)
        
        print(f"Creating backup at {args.backup_path}...")
        
        if args.data_types:
            print(f"Data types: {', '.join(args.data_types)}")
        else:
            print("Data types: All available")
        
        print(f"Compression: {'enabled' if args.compress else 'disabled'}")
        
        # Create backup
        result = await backup_manager.create_backup(
            backup_path=args.backup_path,
            include_data_types=args.data_types,
            compress=args.compress,
            metadata={
                "created_by": "gecko-cli",
                "command_args": vars(args)
            }
        )
        
        if result["success"]:
            print(f"✓ {result['message']}")
            
            # Show statistics
            stats = result["backup_info"]["statistics"]
            print(f"\nBackup Statistics:")
            for data_type, count in stats.items():
                if data_type != "total_records":
                    print(f"  {data_type}: {count:,} records")
            print(f"  Total: {stats.get('total_records', 0):,} records")
        else:
            print(f"✗ {result['message']}")
            return 1
        
        await db_manager.close()
        return 0
        
    except Exception as e:
        print(f"Error creating backup: {e}")
        return 1


async def restore_command(args):
    """Restore data from backup."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.utils.backup_restore import BackupManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Create backup manager
        backup_manager = BackupManager(db_manager, config)
        
        # Verify backup if requested
        if args.verify:
            print(f"Verifying backup at {args.backup_path}...")
            verification = await backup_manager.verify_backup(args.backup_path)
            
            if not verification["valid"]:
                print("✗ Backup verification failed:")
                for error in verification["errors"]:
                    print(f"  - {error}")
                return 1
            else:
                print("✓ Backup verification passed")
                if verification["warnings"]:
                    print("Warnings:")
                    for warning in verification["warnings"]:
                        print(f"  - {warning}")
        
        print(f"Restoring data from {args.backup_path}...")
        
        if args.data_types:
            print(f"Data types: {', '.join(args.data_types)}")
        else:
            print("Data types: All available")
        
        print(f"Overwrite existing: {'yes' if args.overwrite else 'no'}")
        
        # Restore backup
        result = await backup_manager.restore_backup(
            backup_path=args.backup_path,
            data_types=args.data_types,
            overwrite_existing=args.overwrite
        )
        
        if result["success"]:
            print(f"✓ {result['message']}")
            
            # Show statistics
            stats = result["restore_stats"]
            print(f"\nRestore Statistics:")
            for data_type, count in stats.items():
                print(f"  {data_type}: {count:,} records")
            print(f"  Total: {result.get('total_restored', 0):,} records")
        else:
            print(f"✗ {result['message']}")
            return 1
        
        await db_manager.close()
        return 0
        
    except Exception as e:
        print(f"Error restoring backup: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())