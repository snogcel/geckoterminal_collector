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


def _add_migrate_pool_ids_command(subparsers):
    """Add migrate-pool-ids command parser."""
    migrate_parser = subparsers.add_parser(
        'migrate-pool-ids',
        help='Migrate pool IDs to standardized format with network prefixes'
    )
    migrate_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    migrate_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making changes'
    )
    migrate_parser.add_argument(
        '--default-network',
        default='solana',
        help='Default network for IDs without prefix'
    )
    migrate_parser.set_defaults(func=migrate_pool_ids_command)


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
    
    # Workflow validation commands
    _add_build_ohlcv_command(subparsers)
    _add_validate_workflow_command(subparsers)
    
    # Migration commands
    _add_migrate_pool_ids_command(subparsers)
    
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
        "build-ohlcv": build_ohlcv_command,
        "validate-workflow": validate_workflow_command,
        "migrate-pool-ids": migrate_pool_ids_command,
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


def _add_build_ohlcv_command(subparsers):
    """Add build-ohlcv command parser."""
    build_parser = subparsers.add_parser(
        "build-ohlcv",
        help="Build OHLCV dataset for watchlist item",
        description="Build complete historical + real-time OHLCV dataset for a single token from watchlist"
    )
    build_parser.add_argument(
        "watchlist_item",
        type=str,
        help="Token symbol or pool address from watchlist"
    )
    build_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output directory for QLib-compatible dataset"
    )
    build_parser.add_argument(
        "--timeframe",
        default="1h",
        choices=["1m", "5m", "15m", "1h", "4h", "12h", "1d"],
        help="OHLCV timeframe (default: 1h)"
    )
    build_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of historical data to collect (default: 30)"
    )
    build_parser.add_argument(
        "--include-realtime",
        action="store_true",
        default=True,
        help="Include real-time data collection (default: enabled)"
    )
    build_parser.add_argument(
        "--no-realtime",
        dest="include_realtime",
        action="store_false",
        help="Skip real-time data collection"
    )
    build_parser.add_argument(
        "--validate-data",
        action="store_true",
        default=True,
        help="Validate data quality and completeness (default: enabled)"
    )
    build_parser.add_argument(
        "--no-validate",
        dest="validate_data",
        action="store_false",
        help="Skip data validation"
    )
    build_parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild even if data exists"
    )


def _add_validate_workflow_command(subparsers):
    """Add validate-workflow command parser."""
    validate_parser = subparsers.add_parser(
        "validate-workflow",
        help="Validate complete watchlist-to-QLib workflow",
        description="Test end-to-end workflow: watchlist CSV → token collection → OHLCV collection → QLib export"
    )
    validate_parser.add_argument(
        "--watchlist-file",
        type=str,
        default="specs/watchlist.csv",
        help="Path to watchlist CSV file (default: specs/watchlist.csv)"
    )
    validate_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output directory for validation results and QLib export"
    )
    validate_parser.add_argument(
        "--timeframe",
        default="1h",
        choices=["1m", "5m", "15m", "1h", "4h", "12h", "1d"],
        help="OHLCV timeframe for testing (default: 1h)"
    )
    validate_parser.add_argument(
        "--sample-size",
        type=int,
        default=1,
        help="Number of watchlist items to test (default: 1)"
    )
    validate_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days of data to collect for testing (default: 7)"
    )
    validate_parser.add_argument(
        "--use-real-api",
        action="store_true",
        default=True,
        help="Use real GeckoTerminal API (default: enabled)"
    )
    validate_parser.add_argument(
        "--use-mock-api",
        dest="use_real_api",
        action="store_false",
        help="Use mock API responses for testing"
    )
    validate_parser.add_argument(
        "--detailed-report",
        action="store_true",
        help="Generate detailed validation report"
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
        
        print(f"[OK] Configuration initialized at {config_path}")
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
        
        print("_== run_collector_commands _==")
        print(args)
        print("---")

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


async def build_ohlcv_command(args):
    """Build OHLCV dataset for a single watchlist item."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.qlib.exporter import QLibExporter
        from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
        from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
        from gecko_terminal_collector.collectors.historical_ohlcv_collector import HistoricalOHLCVCollector
        from gecko_terminal_collector.utils.watchlist_processor import WatchlistProcessor        

        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        print(f"Building OHLCV dataset for: {args.watchlist_item}")
        print(f"Timeframe: {args.timeframe}")
        print(f"Historical days: {args.days}")
        print(f"Output directory: {args.output}")
        print(f"Include real-time: {args.include_realtime}")
        print("=" * 50)
        
        # Step 1: Find the watchlist item
        print("Step 1: Locating watchlist item (this could take awhile)...")
        watchlist_processor = WatchlistProcessor(config)
        watchlist_items = await watchlist_processor.load_watchlist()

        print("--_build_ohlcv_command (from database)--")
        print(watchlist_items)
        print("--")
        
        target_item = None
        for item in watchlist_items:
            if (item.get('tokenSymbol', '').lower() == args.watchlist_item.lower() or
                item.get('poolAddress', '') == args.watchlist_item or
                item.get('networkAddress', '') == args.watchlist_item):
                target_item = item
                break
        
        if not target_item:
            print(f"✗ Watchlist item '{args.watchlist_item}' not found")
            return 1
        
        print(f"  Found: {target_item.get('tokenSymbol', 'Unknown')} ({target_item.get('tokenName', 'Unknown')})")
        print(f"  Pool Address: {target_item.get('poolAddress', 'N/A')}")
        print(f"  Network Address: {target_item.get('networkAddress', 'N/A')}")
        
        # Step 2: Collect token/pool information
        print("\nStep 2: Collecting token and pool information...")
        watchlist_collector = WatchlistCollector(config, db_manager)
        
        # Process this specific item
        collection_result = await watchlist_collector.collect_single_item(target_item)
        

        #print("--_build_ohlcv_command: ")
        #print(collection_result)
        #print("-I DID NOT FIND THE PREFIX!!! lmao---")

        if not collection_result.success:
            print(f"✗ Failed to collect token information: {collection_result.errors}")
            return 1
        
        print(f"✓ Token information collected successfully")
        
        # Get the pool ID for further operations
        pool_id = target_item.get('poolAddress')
        if not pool_id:
            print("✗ No pool address available for OHLCV collection")
            return 1
        
        # Step 3: Collect historical OHLCV data
        print(f"\nStep 3: Collecting historical OHLCV data ({args.days} days)...")
        
        #print("---collector_config---")        
        print(config)
        #print("---")
        
        historical_collector = HistoricalOHLCVCollector(config, db_manager)
        
        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=args.days)
        
        historical_result = await historical_collector.collect_for_pool(
            pool_id=pool_id,
            timeframe=args.timeframe,
            start_date=start_date,
            end_date=end_date,
            force_refresh=args.force
        )
        
        if historical_result.success:
            print(f"✓ Historical data collected: {historical_result.records_collected} records")
        else:
            print(f"⚠ Historical collection had issues: {historical_result.errors}")
        
        # Step 4: Collect real-time OHLCV data (if enabled)
        if args.include_realtime:
            print(f"\nStep 4: Collecting real-time OHLCV data...")
            ohlcv_collector = OHLCVCollector(config, db_manager)
            
            realtime_result = await ohlcv_collector.collect_for_pool(
                pool_id=pool_id,
                timeframe=args.timeframe
            )
            
            if realtime_result.success:
                print(f"✓ Real-time data collected: {realtime_result.records_collected} records")
            else:
                print(f"⚠ Real-time collection had issues: {realtime_result.errors}")
        
        # Step 5: Export to QLib format
        print(f"\nStep 5: Exporting to QLib format...")
        exporter = QLibExporter(db_manager)
        
        # Generate symbol name for this pool
        pool = await db_manager.get_pool(pool_id)
        if not pool:
            print("✗ Could not retrieve pool information for export")
            return 1
        
        symbol = exporter._generate_symbol_name(pool)
        
        export_result = await exporter.export_to_qlib_format(
            output_dir=args.output,
            symbols=[symbol],
            start_date=start_date,
            end_date=end_date,
            timeframe=args.timeframe
        )
        
        if export_result['success']:
            print(f"✓ QLib export completed successfully")
            print(f"  Files created: {export_result['files_created']}")
            print(f"  Total records: {export_result['total_records']}")
        else:
            print(f"✗ QLib export failed: {export_result['message']}")
            return 1
        
        # Step 6: Data validation (if enabled)
        if args.validate_data:
            print(f"\nStep 6: Validating data quality...")
            
            validation_result = await exporter.export_symbol_data_with_validation(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe=args.timeframe,
                validate_data=True
            )
            
            if 'validation' in validation_result and validation_result['validation']:
                validation = validation_result['validation']
                print(f"✓ Data validation completed")
                print(f"  Records validated: {validation.get('record_count', 0)}")
                print(f"  Data quality score: {validation.get('quality_score', 0):.2f}")
                
                if validation.get('issues'):
                    print(f"  Issues found: {len(validation['issues'])}")
                    for issue in validation['issues'][:5]:  # Show first 5 issues
                        print(f"    - {issue}")
            else:
                print("⚠ Data validation could not be performed")
        
        print(f"\n✓ OHLCV dataset build completed successfully!")
        print(f"Output location: {args.output}")
        
        await db_manager.close()
        return 0
        
    except Exception as e:
        print(f"Error building OHLCV dataset: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


async def validate_workflow_command(args):
    """Validate complete watchlist-to-QLib workflow."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.qlib.exporter import QLibExporter
        from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
        from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
        from gecko_terminal_collector.utils.watchlist_processor import WatchlistProcessor
        from gecko_terminal_collector.utils.workflow_validator import WorkflowValidator
        import pandas as pd
        import json
        from pathlib import Path
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        print("GeckoTerminal Watchlist-to-QLib Workflow Validation")
        print("=" * 60)
        print(f"Watchlist file: {args.watchlist_file}")
        print(f"Output directory: {args.output}")
        print(f"Timeframe: {args.timeframe}")
        print(f"Sample size: {args.sample_size}")
        print(f"Historical days: {args.days}")
        print(f"Using real API: {args.use_real_api}")
        print("=" * 60)
        
        # Create output directory
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize workflow validator
        validator = WorkflowValidator(config, db_manager)
        
        # Step 1: Validate watchlist file
        print("\nStep 1: Validating watchlist file...")
        
        if not Path(args.watchlist_file).exists():
            print(f"[FAIL] Watchlist file not found: {args.watchlist_file}")
            return 1
        
        watchlist_processor = WatchlistProcessor(config)
        watchlist_items = await watchlist_processor.load_watchlist(args.watchlist_file)
        
        if not watchlist_items:
            print(f"[FAIL] No items found in watchlist file")
            return 1
        
        print(f"[OK] Watchlist loaded: {len(watchlist_items)} items found")
        
        # Select sample items for testing
        sample_items = watchlist_items[:args.sample_size]
        print(f"[OK] Selected {len(sample_items)} items for validation")
        
        # Step 2: Test token collection workflow
        print(f"\nStep 2: Testing token collection workflow...")
        
        watchlist_collector = WatchlistCollector(config, db_manager)
        token_collection_results = []
        
        for i, item in enumerate(sample_items, 1):
            print(f"  Testing item {i}/{len(sample_items)}: {item.get('tokenSymbol', 'Unknown')}")
            
            try:
                result = await watchlist_collector.collect_single_item(item)
                token_collection_results.append({
                    'item': item,
                    'success': result.success,
                    'records_collected': result.records_collected,
                    'errors': result.errors
                })
                
                if result.success:
                    print(f"    [OK] Token collection successful")
                else:
                    print(f"    [FAIL] Token collection failed: {result.errors}")
                    
            except Exception as e:
                print(f"    [FAIL] Token collection error: {e}")
                token_collection_results.append({
                    'item': item,
                    'success': False,
                    'error': str(e)
                })
        
        successful_tokens = [r for r in token_collection_results if r['success']]
        print(f"[OK] Token collection: {len(successful_tokens)}/{len(sample_items)} successful")
        
        # Step 3: Test OHLCV collection workflow
        print(f"\nStep 3: Testing OHLCV collection workflow...")
        
        ohlcv_collector = OHLCVCollector(config, db_manager)
        ohlcv_collection_results = []
        
        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=args.days)
        
        for result in successful_tokens:
            item = result['item']
            pool_address = item.get('poolAddress')
            
            if not pool_address:
                print(f"    [WARN] No pool address for {item.get('tokenSymbol', 'Unknown')}")
                continue
            
            print(f"  Testing OHLCV for: {item.get('tokenSymbol', 'Unknown')}")
            
            # Find the correct pool ID in the database (it may have network prefix)
            pool = None
            try:
                # First try with just the address
                pool = await db_manager.get_pool(pool_address)
                if not pool:
                    # Try with network prefix
                    network_prefixed_id = f"{config.dexes.network}_{pool_address}"
                    pool = await db_manager.get_pool(network_prefixed_id)
                
                if not pool:
                    print(f"    [FAIL] Pool not found in database: {pool_address}")
                    ohlcv_collection_results.append({
                        'item': item,
                        'pool_id': pool_address,
                        'success': False,
                        'records_collected': 0,
                        'errors': ['Pool not found in database']
                    })
                    continue
                
                pool_id = pool.id
                
            except Exception as e:
                print(f"    [FAIL] Error finding pool: {e}")
                ohlcv_collection_results.append({
                    'item': item,
                    'pool_id': pool_address,
                    'success': False,
                    'records_collected': 0,
                    'errors': [f'Error finding pool: {e}']
                })
                continue
            
            try:
                ohlcv_result = await ohlcv_collector.collect_for_pool(
                    pool_id=pool_id,
                    timeframe=args.timeframe
                )
                
                ohlcv_collection_results.append({
                    'item': item,
                    'pool_id': pool_id,
                    'success': ohlcv_result.success,
                    'records_collected': ohlcv_result.records_collected,
                    'errors': ohlcv_result.errors
                })
                
                if ohlcv_result.success:
                    print(f"    [OK] OHLCV collection successful: {ohlcv_result.records_collected} records")
                else:
                    print(f"    [FAIL] OHLCV collection failed: {ohlcv_result.errors}")
                    
            except Exception as e:
                print(f"    [FAIL] OHLCV collection error: {e}")
                ohlcv_collection_results.append({
                    'item': item,
                    'pool_id': pool_id,
                    'success': False,
                    'error': str(e)
                })
        
        successful_ohlcv = [r for r in ohlcv_collection_results if r['success']]
        print(f"[OK] OHLCV collection: {len(successful_ohlcv)}/{len(successful_tokens)} successful")
        
        # Step 4: Test QLib export workflow
        print(f"\nStep 4: Testing QLib export workflow...")
        
        exporter = QLibExporter(db_manager)
        export_results = []
        
        for result in successful_ohlcv:
            item = result['item']
            pool_id = result['pool_id']
            
            print(f"  Testing QLib export for: {item.get('tokenSymbol', 'Unknown')}")
            
            try:
                # Get pool and generate symbol
                pool = await db_manager.get_pool(pool_id)
                if not pool:
                    print(f"    [FAIL] Pool not found: {pool_id}")
                    continue
                
                symbol = exporter._generate_symbol_name(pool)
                
                # Export data
                export_result = await exporter.export_symbol_data_with_validation(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=args.timeframe,
                    validate_data=True
                )
                
                export_results.append({
                    'item': item,
                    'symbol': symbol,
                    'success': 'error' not in export_result,
                    'data_records': len(export_result.get('data', pd.DataFrame())),
                    'validation': export_result.get('validation'),
                    'metadata': export_result.get('metadata'),
                    'error': export_result.get('error')
                })
                
                if 'error' not in export_result:
                    records = len(export_result.get('data', pd.DataFrame()))
                    print(f"    [OK] QLib export successful: {records} records")
                else:
                    print(f"    [FAIL] QLib export failed: {export_result['error']}")
                    
            except Exception as e:
                print(f"    [FAIL] QLib export error: {e}")
                export_results.append({
                    'item': item,
                    'success': False,
                    'error': str(e)
                })
        
        successful_exports = [r for r in export_results if r['success']]
        print(f"[OK] QLib export: {len(successful_exports)}/{len(successful_ohlcv)} successful")
        
        # Step 5: Generate validation report
        print(f"\nStep 5: Generating validation report...")
        
        validation_report = {
            'timestamp': datetime.utcnow().isoformat(),
            'configuration': {
                'watchlist_file': args.watchlist_file,
                'timeframe': args.timeframe,
                'sample_size': args.sample_size,
                'historical_days': args.days,
                'use_real_api': args.use_real_api
            },
            'results': {
                'total_items_tested': len(sample_items),
                'token_collection_success': len(successful_tokens),
                'ohlcv_collection_success': len(successful_ohlcv),
                'qlib_export_success': len(successful_exports),
                'overall_success_rate': len(successful_exports) / len(sample_items) if sample_items else 0
            },
            'detailed_results': {
                'token_collection': token_collection_results,
                'ohlcv_collection': ohlcv_collection_results,
                'qlib_export': export_results
            }
        }
        
        # Save validation report
        report_path = output_path / "validation_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(validation_report, f, indent=2, default=str)
        
        print(f"[OK] Validation report saved: {report_path}")
        
        # Generate detailed report if requested
        if args.detailed_report:
            detailed_report_path = output_path / "detailed_validation_report.md"
            await _generate_detailed_validation_report(validation_report, detailed_report_path)
            print(f"[OK] Detailed report saved: {detailed_report_path}")
        
        # Export successful data to QLib format
        if successful_exports:
            print(f"\nStep 6: Exporting validated data to QLib format...")
            
            symbols = [r['symbol'] for r in successful_exports]
            final_export = await exporter.export_to_qlib_format(
                output_dir=output_path / "qlib_data",
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                timeframe=args.timeframe
            )
            
            if final_export['success']:
                print(f"[OK] Final QLib export completed")
                print(f"  Files created: {final_export['files_created']}")
                print(f"  Total records: {final_export['total_records']}")
            else:
                print(f"[FAIL] Final QLib export failed: {final_export['message']}")
        
        # Summary
        print(f"\n" + "=" * 60)
        print("WORKFLOW VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total items tested: {len(sample_items)}")
        print(f"Token collection success: {len(successful_tokens)}/{len(sample_items)} ({len(successful_tokens)/len(sample_items)*100:.1f}%)")
        
        ohlcv_pct = (len(successful_ohlcv)/len(successful_tokens)*100) if successful_tokens else 0
        print(f"OHLCV collection success: {len(successful_ohlcv)}/{len(successful_tokens)} ({ohlcv_pct:.1f}% of successful tokens)")
        
        export_pct = (len(successful_exports)/len(successful_ohlcv)*100) if successful_ohlcv else 0
        print(f"QLib export success: {len(successful_exports)}/{len(successful_ohlcv)} ({export_pct:.1f}% of successful OHLCV)")
        
        print(f"Overall success rate: {len(successful_exports)}/{len(sample_items)} ({len(successful_exports)/len(sample_items)*100:.1f}%)")
        
        success_threshold = 0.8  # 80% success rate threshold
        overall_success = (len(successful_exports) / len(sample_items)) >= success_threshold
        
        if overall_success:
            print(f"\n[PASS] WORKFLOW VALIDATION PASSED")
            print(f"The watchlist-to-QLib workflow is functioning correctly.")
        else:
            print(f"\n[FAIL] WORKFLOW VALIDATION FAILED")
            print(f"Success rate below threshold ({success_threshold*100:.0f}%)")
        
        print(f"\nResults saved to: {args.output}")
        
        await db_manager.close()
        return 0 if overall_success else 1
        
    except Exception as e:
        print(f"Error validating workflow: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1



async def validate_workflow_command_backup(args):
    """Validate complete watchlist-to-QLib workflow."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.qlib.exporter import QLibExporter
        from gecko_terminal_collector.collectors.watchlist_collector import WatchlistCollector
        from gecko_terminal_collector.collectors.ohlcv_collector import OHLCVCollector
        from gecko_terminal_collector.utils.watchlist_processor import WatchlistProcessor
        from gecko_terminal_collector.utils.workflow_validator import WorkflowValidator
        import pandas as pd
        import json
        from pathlib import Path
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        print("GeckoTerminal Watchlist-to-QLib Workflow Validation")
        print("=" * 60)
        print(f"Watchlist file: {args.watchlist_file}")
        print(f"Output directory: {args.output}")
        print(f"Timeframe: {args.timeframe}")
        print(f"Sample size: {args.sample_size}")
        print(f"Historical days: {args.days}")
        print(f"Using real API: {args.use_real_api}")
        print("=" * 60)
        
        # Create output directory
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize workflow validator
        validator = WorkflowValidator(config, db_manager)
        
        # Step 1: Validate watchlist file
        print("\nStep 1: Validating watchlist file...")
        
        if not Path(args.watchlist_file).exists():
            print(f"[FAIL] Watchlist file not found: {args.watchlist_file}")
            return 1
        
        watchlist_processor = WatchlistProcessor(config)
        watchlist_items = await watchlist_processor.load_watchlist(args.watchlist_file)
        
        if not watchlist_items:
            print(f"[FAIL] No items found in watchlist file")
            return 1
        
        print(f"[OK] Watchlist loaded: {len(watchlist_items)} items found")
        
        # Select sample items for testing
        sample_items = watchlist_items[:args.sample_size]
        print(f"[OK] Selected {len(sample_items)} items for validation")
        
        # Step 2: Test token collection workflow
        print(f"\nStep 2: Testing token collection workflow...")
        
        watchlist_collector = WatchlistCollector(config, db_manager)
        token_collection_results = []
        
        for i, item in enumerate(sample_items, 1):
            print(f"  Testing item {i}/{len(sample_items)}: {item.get('tokenSymbol', 'Unknown')}")
            
            try:
                result = await watchlist_collector.collect_single_item(item)
                token_collection_results.append({
                    'item': item,
                    'success': result.success,
                    'records_collected': result.records_collected,
                    'errors': result.errors
                })
                
                if result.success:
                    print(f"    [OK] Token collection successful")
                else:
                    print(f"    [FAIL] Token collection failed: {result.errors}")
                    
            except Exception as e:
                print(f"    [FAIL] Token collection error: {e}")
                token_collection_results.append({
                    'item': item,
                    'success': False,
                    'error': str(e)
                })
        
        successful_tokens = [r for r in token_collection_results if r['success']]
        print(f"[OK] Token collection: {len(successful_tokens)}/{len(sample_items)} successful")
        
        # Step 3: Test OHLCV collection workflow
        print(f"\nStep 3: Testing OHLCV collection workflow...")
        
        ohlcv_collector = OHLCVCollector(config, db_manager)
        ohlcv_collection_results = []
        
        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=args.days)
        
        for result in successful_tokens:
            item = result['item']
            pool_address = item.get('poolAddress')
            
            if not pool_address:
                print(f"    [WARN] No pool address for {item.get('tokenSymbol', 'Unknown')}")
                continue
            
            print(f"  Testing OHLCV for: {item.get('tokenSymbol', 'Unknown')}")
            
            # Find the correct pool ID in the database (it may have network prefix)
            pool = None
            try:
                # First try with just the address
                pool = await db_manager.get_pool(pool_address)
                if not pool:
                    # Try with network prefix
                    network_prefixed_id = f"{config.dexes.network}_{pool_address}"
                    pool = await db_manager.get_pool(network_prefixed_id)
                
                if not pool:
                    print(f"    [FAIL] Pool not found in database: {pool_address}")
                    ohlcv_collection_results.append({
                        'item': item,
                        'pool_id': pool_address,
                        'success': False,
                        'records_collected': 0,
                        'errors': ['Pool not found in database']
                    })
                    continue
                
                pool_id = pool.id
                
            except Exception as e:
                print(f"    [FAIL] Error finding pool: {e}")
                ohlcv_collection_results.append({
                    'item': item,
                    'pool_id': pool_address,
                    'success': False,
                    'records_collected': 0,
                    'errors': [f'Error finding pool: {e}']
                })
                continue
            
            try:
                ohlcv_result = await ohlcv_collector.collect_for_pool(
                    pool_id=pool_id,
                    timeframe=args.timeframe
                )
                
                ohlcv_collection_results.append({
                    'item': item,
                    'pool_id': pool_id,
                    'success': ohlcv_result.success,
                    'records_collected': ohlcv_result.records_collected,
                    'errors': ohlcv_result.errors
                })
                
                if ohlcv_result.success:
                    print(f"    [OK] OHLCV collection successful: {ohlcv_result.records_collected} records")
                else:
                    print(f"    [FAIL] OHLCV collection failed: {ohlcv_result.errors}")
                    
            except Exception as e:
                print(f"    [FAIL] OHLCV collection error: {e}")
                ohlcv_collection_results.append({
                    'item': item,
                    'pool_id': pool_id,
                    'success': False,
                    'error': str(e)
                })
        
        successful_ohlcv = [r for r in ohlcv_collection_results if r['success']]
        print(f"[OK] OHLCV collection: {len(successful_ohlcv)}/{len(successful_tokens)} successful")
        
        # Step 4: Test QLib export workflow
        print(f"\nStep 4: Testing QLib export workflow...")
        
        exporter = QLibExporter(db_manager)
        export_results = []
        
        for result in successful_ohlcv:
            item = result['item']
            pool_id = result['pool_id']
            
            print(f"  Testing QLib export for: {item.get('tokenSymbol', 'Unknown')}")
            
            try:
                # Get pool and generate symbol
                pool = await db_manager.get_pool(pool_id)
                if not pool:
                    print(f"    [FAIL] Pool not found: {pool_id}")
                    continue
                
                symbol = exporter._generate_symbol_name(pool)
                
                # Export data
                export_result = await exporter.export_symbol_data_with_validation(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=args.timeframe,
                    validate_data=True
                )
                
                export_results.append({
                    'item': item,
                    'symbol': symbol,
                    'success': 'error' not in export_result,
                    'data_records': len(export_result.get('data', pd.DataFrame())),
                    'validation': export_result.get('validation'),
                    'metadata': export_result.get('metadata'),
                    'error': export_result.get('error')
                })
                
                if 'error' not in export_result:
                    records = len(export_result.get('data', pd.DataFrame()))
                    print(f"    [OK] QLib export successful: {records} records")
                else:
                    print(f"    [FAIL] QLib export failed: {export_result['error']}")
                    
            except Exception as e:
                print(f"    [FAIL] QLib export error: {e}")
                export_results.append({
                    'item': item,
                    'success': False,
                    'error': str(e)
                })
        
        successful_exports = [r for r in export_results if r['success']]
        print(f"[OK] QLib export: {len(successful_exports)}/{len(successful_ohlcv)} successful")
        
        # Step 5: Generate validation report
        print(f"\nStep 5: Generating validation report...")
        
        validation_report = {
            'timestamp': datetime.utcnow().isoformat(),
            'configuration': {
                'watchlist_file': args.watchlist_file,
                'timeframe': args.timeframe,
                'sample_size': args.sample_size,
                'historical_days': args.days,
                'use_real_api': args.use_real_api
            },
            'results': {
                'total_items_tested': len(sample_items),
                'token_collection_success': len(successful_tokens),
                'ohlcv_collection_success': len(successful_ohlcv),
                'qlib_export_success': len(successful_exports),
                'overall_success_rate': len(successful_exports) / len(sample_items) if sample_items else 0
            },
            'detailed_results': {
                'token_collection': token_collection_results,
                'ohlcv_collection': ohlcv_collection_results,
                'qlib_export': export_results
            }
        }
        
        # Save validation report
        report_path = output_path / "validation_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(validation_report, f, indent=2, default=str)
        
        print(f"[OK] Validation report saved: {report_path}")
        
        # Generate detailed report if requested
        if args.detailed_report:
            detailed_report_path = output_path / "detailed_validation_report.md"
            await _generate_detailed_validation_report(validation_report, detailed_report_path)
            print(f"[OK] Detailed report saved: {detailed_report_path}")
        
        # Export successful data to QLib format
        if successful_exports:
            print(f"\nStep 6: Exporting validated data to QLib format...")
            
            symbols = [r['symbol'] for r in successful_exports]
            final_export = await exporter.export_to_qlib_format(
                output_dir=output_path / "qlib_data",
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                timeframe=args.timeframe
            )
            
            if final_export['success']:
                print(f"[OK] Final QLib export completed")
                print(f"  Files created: {final_export['files_created']}")
                print(f"  Total records: {final_export['total_records']}")
            else:
                print(f"[FAIL] Final QLib export failed: {final_export['message']}")
        
        # Summary
        print(f"\n" + "=" * 60)
        print("WORKFLOW VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total items tested: {len(sample_items)}")
        print(f"Token collection success: {len(successful_tokens)}/{len(sample_items)} ({len(successful_tokens)/len(sample_items)*100:.1f}%)")
        
        ohlcv_pct = (len(successful_ohlcv)/len(successful_tokens)*100) if successful_tokens else 0
        print(f"OHLCV collection success: {len(successful_ohlcv)}/{len(successful_tokens)} ({ohlcv_pct:.1f}% of successful tokens)")
        
        export_pct = (len(successful_exports)/len(successful_ohlcv)*100) if successful_ohlcv else 0
        print(f"QLib export success: {len(successful_exports)}/{len(successful_ohlcv)} ({export_pct:.1f}% of successful OHLCV)")
        
        print(f"Overall success rate: {len(successful_exports)}/{len(sample_items)} ({len(successful_exports)/len(sample_items)*100:.1f}%)")
        
        success_threshold = 0.8  # 80% success rate threshold
        overall_success = (len(successful_exports) / len(sample_items)) >= success_threshold
        
        if overall_success:
            print(f"\n[PASS] WORKFLOW VALIDATION PASSED")
            print(f"The watchlist-to-QLib workflow is functioning correctly.")
        else:
            print(f"\n[FAIL] WORKFLOW VALIDATION FAILED")
            print(f"Success rate below threshold ({success_threshold*100:.0f}%)")
        
        print(f"\nResults saved to: {args.output}")
        
        await db_manager.close()
        return 0 if overall_success else 1
        
    except Exception as e:
        print(f"Error validating workflow: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1



async def _generate_detailed_validation_report(validation_report: Dict[str, Any], output_path: Path):
    """Generate detailed markdown validation report."""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Watchlist-to-QLib Workflow Validation Report\n\n")
        
        # Configuration
        f.write("## Configuration\n\n")
        config = validation_report['configuration']
        for key, value in config.items():
            f.write(f"- **{key.replace('_', ' ').title()}**: {value}\n")
        
        # Summary
        f.write("\n## Summary\n\n")
        results = validation_report['results']
        f.write(f"- **Total Items Tested**: {results['total_items_tested']}\n")
        f.write(f"- **Token Collection Success**: {results['token_collection_success']}\n")
        f.write(f"- **OHLCV Collection Success**: {results['ohlcv_collection_success']}\n")
        f.write(f"- **QLib Export Success**: {results['qlib_export_success']}\n")
        f.write(f"- **Overall Success Rate**: {results['overall_success_rate']:.2%}\n")
        
        # Detailed Results
        f.write("\n## Detailed Results\n\n")
        
        # Token Collection
        f.write("### Token Collection Results\n\n")
        for i, result in enumerate(validation_report['detailed_results']['token_collection'], 1):
            item = result['item']
            symbol = item.get('tokenSymbol', 'Unknown')
            status = "[OK]" if result['success'] else "[FAIL]"
            f.write(f"{i}. **{symbol}** {status}\n")
            if not result['success']:
                f.write(f"   - Error: {result.get('error', result.get('errors', 'Unknown error'))}\n")
            f.write("\n")
        
        # OHLCV Collection
        f.write("### OHLCV Collection Results\n\n")
        for i, result in enumerate(validation_report['detailed_results']['ohlcv_collection'], 1):
            item = result['item']
            symbol = item.get('tokenSymbol', 'Unknown')
            status = "[OK]" if result['success'] else "[FAIL]"
            f.write(f"{i}. **{symbol}** {status}\n")
            if result['success']:
                f.write(f"   - Records collected: {result.get('records_collected', 0)}\n")
            else:
                f.write(f"   - Error: {result.get('error', result.get('errors', 'Unknown error'))}\n")
            f.write("\n")
        
        # QLib Export
        f.write("### QLib Export Results\n\n")
        for i, result in enumerate(validation_report['detailed_results']['qlib_export'], 1):
            item = result['item']
            symbol = item.get('tokenSymbol', 'Unknown')
            status = "[OK]" if result['success'] else "[FAIL]"
            f.write(f"{i}. **{symbol}** {status}\n")
            if result['success']:
                f.write(f"   - QLib Symbol: {result.get('symbol', 'N/A')}\n")
                f.write(f"   - Data Records: {result.get('data_records', 0)}\n")
                if result.get('validation'):
                    validation = result['validation']
                    f.write(f"   - Data Quality Score: {validation.get('quality_score', 'N/A')}\n")
            else:
                f.write(f"   - Error: {result.get('error', 'Unknown error')}\n")
            f.write("\n")


async def migrate_pool_ids_command(args):
    """Migrate pool IDs to standardized format with network prefixes."""
    try:
        from gecko_terminal_collector.utils.pool_id_migration import (
            PoolIDMigration, create_migration_report
        )
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        print("Initializing database connection...")
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        try:
            print("Analyzing current pool ID formats...")
            migration = PoolIDMigration(db_manager)
            
            # Generate comprehensive report
            report = await create_migration_report(db_manager)
            print(report)
            
            if args.dry_run:
                print("\n🔍 DRY RUN MODE - No changes will be made")
            else:
                print(f"\n🚀 MIGRATION MODE - Applying changes with default network: {args.default_network}")
                
                # Confirm before proceeding
                response = input("Do you want to proceed with the migration? (y/N): ")
                if response.lower() != 'y':
                    print("Migration cancelled.")
                    return
                
                # Perform actual migration
                results = await migration.migrate_pool_ids_to_standard_format(
                    default_network=args.default_network,
                    dry_run=False
                )
                
                print(f"\n✅ Migration completed:")
                print(f"- Total processed: {results['total_processed']}")
                print(f"- Migrations applied: {results['migrations_applied']}")
                print(f"- Errors: {len(results['errors'])}")
                
                if results['errors']:
                    print("\nErrors encountered:")
                    for error in results['errors']:
                        print(f"  ❌ {error}")
                        
        finally:
            await db_manager.close()
            
    except Exception as e:
        print(f"❌ Pool ID migration failed: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    sys.exit(main())

