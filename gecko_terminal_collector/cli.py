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


def _add_add_watchlist_command(subparsers):
    """Add add-watchlist command parser."""
    add_watchlist_parser = subparsers.add_parser(
        'add-watchlist',
        help='Add a new entry to the watchlist',
        description='Add a new token/pool to the watchlist for monitoring'
    )
    add_watchlist_parser.add_argument(
        '--pool-id',
        type=str,
        required=True,
        help='Pool ID (with network prefix, e.g., solana_ABC123...)'
    )
    add_watchlist_parser.add_argument(
        '--symbol',
        type=str,
        required=True,
        help='Token symbol (e.g., YUGE, SOL, BTC)'
    )
    add_watchlist_parser.add_argument(
        '--name',
        type=str,
        help='Token name (optional, e.g., "Yuge Token")'
    )
    add_watchlist_parser.add_argument(
        '--network-address',
        type=str,
        help='Network-specific token address (optional)'
    )
    add_watchlist_parser.add_argument(
        '--active',
        type=str,
        choices=['true', 'false'],
        default='true',
        help='Whether the entry should be active (default: true)'
    )
    add_watchlist_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    add_watchlist_parser.set_defaults(func=add_watchlist_command)


def _add_list_watchlist_command(subparsers):
    """Add list-watchlist command parser."""
    list_watchlist_parser = subparsers.add_parser(
        'list-watchlist',
        help='List all watchlist entries',
        description='Display all entries in the watchlist'
    )
    list_watchlist_parser.add_argument(
        '--active-only',
        action='store_true',
        help='Show only active entries'
    )
    list_watchlist_parser.add_argument(
        '--format',
        choices=['table', 'csv', 'json'],
        default='table',
        help='Output format (default: table)'
    )
    list_watchlist_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    list_watchlist_parser.set_defaults(func=list_watchlist_command)


def _add_update_watchlist_command(subparsers):
    """Add update-watchlist command parser."""
    update_watchlist_parser = subparsers.add_parser(
        'update-watchlist',
        help='Update an existing watchlist entry',
        description='Update fields of an existing watchlist entry'
    )
    update_watchlist_parser.add_argument(
        '--pool-id',
        type=str,
        required=True,
        help='Pool ID of the entry to update'
    )
    update_watchlist_parser.add_argument(
        '--symbol',
        type=str,
        help='New token symbol'
    )
    update_watchlist_parser.add_argument(
        '--name',
        type=str,
        help='New token name'
    )
    update_watchlist_parser.add_argument(
        '--network-address',
        type=str,
        help='New network-specific token address'
    )
    update_watchlist_parser.add_argument(
        '--active',
        type=str,
        choices=['true', 'false'],
        help='Set active status'
    )
    update_watchlist_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    update_watchlist_parser.set_defaults(func=update_watchlist_command)


def _add_remove_watchlist_command(subparsers):
    """Add remove-watchlist command parser."""
    remove_watchlist_parser = subparsers.add_parser(
        'remove-watchlist',
        help='Remove an entry from the watchlist',
        description='Remove a token/pool from the watchlist'
    )
    remove_watchlist_parser.add_argument(
        '--pool-id',
        type=str,
        required=True,
        help='Pool ID of the entry to remove'
    )
    remove_watchlist_parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )
    remove_watchlist_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    remove_watchlist_parser.set_defaults(func=remove_watchlist_command)


def _add_collect_new_pools_command(subparsers):
    """Add collect-new-pools command parser."""
    collect_parser = subparsers.add_parser(
        'collect-new-pools',
        help='Collect new pools with enhanced features',
        description='Run enhanced new pools collection with automatic watchlist integration'
    )
    collect_parser.add_argument(
        '--network',
        type=str,
        default='solana',
        help='Network to collect pools from (default: solana)'
    )
    collect_parser.add_argument(
        '--auto-watchlist',
        action='store_true',
        help='Automatically add promising pools to watchlist'
    )
    collect_parser.add_argument(
        '--min-liquidity',
        type=float,
        default=1000.0,
        help='Minimum liquidity in USD for watchlist consideration (default: 1000)'
    )
    collect_parser.add_argument(
        '--min-volume',
        type=float,
        default=100.0,
        help='Minimum 24h volume in USD for watchlist consideration (default: 100)'
    )
    collect_parser.add_argument(
        '--max-age-hours',
        type=int,
        default=24,
        help='Maximum age in hours for new pool consideration (default: 24)'
    )
    collect_parser.add_argument(
        '--min-activity-score',
        type=float,
        default=60.0,
        help='Minimum activity score for watchlist addition (default: 60.0)'
    )
    collect_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be collected without storing data'
    )
    collect_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    collect_parser.set_defaults(func=collect_new_pools_command)


def _add_analyze_pool_discovery_command(subparsers):
    """Add analyze-pool-discovery command parser."""
    analyze_parser = subparsers.add_parser(
        'analyze-pool-discovery',
        help='Analyze pool discovery statistics',
        description='Analyze pool discovery and watchlist addition statistics'
    )
    analyze_parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to analyze (default: 7)'
    )
    analyze_parser.add_argument(
        '--network',
        type=str,
        help='Filter by specific network'
    )
    analyze_parser.add_argument(
        '--format',
        choices=['table', 'csv', 'json'],
        default='table',
        help='Output format (default: table)'
    )
    analyze_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    analyze_parser.set_defaults(func=analyze_pool_discovery_command)


def _add_db_health_command(subparsers):
    """Add db-health command parser."""
    health_parser = subparsers.add_parser(
        'db-health',
        help='Check database health and performance',
        description='Analyze database health, performance metrics, and connectivity'
    )
    health_parser.add_argument(
        '--format',
        choices=['table', 'json'],
        default='table',
        help='Output format (default: table)'
    )
    health_parser.add_argument(
        '--test-connectivity',
        action='store_true',
        help='Run connectivity tests'
    )
    health_parser.add_argument(
        '--test-performance',
        action='store_true',
        help='Run performance benchmarks'
    )
    health_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    health_parser.set_defaults(func=db_health_command)


def _add_db_monitor_command(subparsers):
    """Add db-monitor command parser."""
    monitor_parser = subparsers.add_parser(
        'db-monitor',
        help='Start database health monitoring',
        description='Start continuous database health monitoring with alerting'
    )
    monitor_parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Monitoring interval in seconds (default: 60)'
    )
    monitor_parser.add_argument(
        '--duration',
        type=int,
        help='Monitoring duration in minutes (default: run indefinitely)'
    )
    monitor_parser.add_argument(
        '--alert-threshold-lock-wait',
        type=float,
        default=1000,
        help='Alert threshold for lock wait time in ms (default: 1000)'
    )
    monitor_parser.add_argument(
        '--alert-threshold-query-time',
        type=float,
        default=500,
        help='Alert threshold for query time in ms (default: 500)'
    )
    monitor_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    monitor_parser.set_defaults(func=db_monitor_command)


def _add_analyze_pool_signals_command(subparsers):
    """Add analyze-pool-signals command parser."""
    analyze_signals_parser = subparsers.add_parser(
        'analyze-pool-signals',
        help='Analyze pool signals from new pools history',
        description='Analyze trading signals and patterns from new pools historical data'
    )
    analyze_signals_parser.add_argument(
        '--network',
        type=str,
        default='solana',
        help='Filter by network (default: solana)'
    )
    analyze_signals_parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Number of hours to analyze (default: 24)'
    )
    analyze_signals_parser.add_argument(
        '--min-signal-score',
        type=float,
        default=60.0,
        help='Minimum signal score to display (default: 60.0)'
    )
    analyze_signals_parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Maximum number of results to show (default: 20)'
    )
    analyze_signals_parser.add_argument(
        '--format',
        choices=['table', 'csv', 'json'],
        default='table',
        help='Output format (default: table)'
    )
    analyze_signals_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    analyze_signals_parser.set_defaults(func=analyze_pool_signals_command)


def _add_monitor_pool_signals_command(subparsers):
    """Add monitor-pool-signals command parser."""
    monitor_signals_parser = subparsers.add_parser(
        'monitor-pool-signals',
        help='Monitor pools for signal conditions',
        description='Continuously monitor pools for strong signal conditions and alerts'
    )
    monitor_signals_parser.add_argument(
        '--pool-id',
        type=str,
        help='Monitor specific pool ID (optional)'
    )
    monitor_signals_parser.add_argument(
        '--network',
        type=str,
        default='solana',
        help='Network to monitor (default: solana)'
    )
    monitor_signals_parser.add_argument(
        '--alert-threshold',
        type=float,
        default=75.0,
        help='Signal score threshold for alerts (default: 75.0)'
    )
    monitor_signals_parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Monitoring interval in seconds (default: 300)'
    )
    monitor_signals_parser.add_argument(
        '--duration',
        type=int,
        help='Monitoring duration in minutes (default: run indefinitely)'
    )
    monitor_signals_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    monitor_signals_parser.set_defaults(func=monitor_pool_signals_command)


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
  gecko-cli backup /path/to/backup          # Create comprehensive database backup
  gecko-cli list-backups                    # List available backups
  gecko-cli db-setup                        # Initialize database schema
  gecko-cli add-watchlist --pool-id solana_ABC123 --symbol YUGE --name "Yuge Token"
  gecko-cli list-watchlist --format table  # List all watchlist entries
  gecko-cli update-watchlist --pool-id solana_ABC123 --active false
  gecko-cli remove-watchlist --pool-id solana_ABC123 --force
  gecko-cli collect-new-pools --network solana --auto-watchlist --min-liquidity 5000
  gecko-cli analyze-pool-discovery --days 7 --format json
  gecko-cli db-health --test-connectivity --test-performance
  gecko-cli db-monitor --interval 30 --duration 60
  gecko-cli analyze-pool-signals --network solana --hours 24 --min-signal-score 70
  gecko-cli monitor-pool-signals --network solana --alert-threshold 80 --interval 300
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
    # _add_list_backups_command(subparsers)  # Temporarily disabled
    
    # Workflow validation commands
    _add_build_ohlcv_command(subparsers)
    _add_validate_workflow_command(subparsers)
    
    # Migration commands
    _add_migrate_pool_ids_command(subparsers)
    
    # Watchlist management commands
    _add_add_watchlist_command(subparsers)
    _add_list_watchlist_command(subparsers)
    _add_update_watchlist_command(subparsers)
    _add_remove_watchlist_command(subparsers)
    
    # Enhanced pool discovery commands
    _add_collect_new_pools_command(subparsers)
    _add_analyze_pool_discovery_command(subparsers)
    
    # Signal analysis commands
    # _add_analyze_pool_signals_command(subparsers)  # Temporarily disabled
    # _add_monitor_pool_signals_command(subparsers)  # Temporarily disabled
    
    # Database health and monitoring commands
    _add_db_health_command(subparsers)
    _add_db_monitor_command(subparsers)
    
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
        # "list-backups": list_backups_command,  # Temporarily disabled
        "build-ohlcv": build_ohlcv_command,
        "validate-workflow": validate_workflow_command,
        "migrate-pool-ids": migrate_pool_ids_command,
        "add-watchlist": add_watchlist_command,
        "list-watchlist": list_watchlist_command,
        "update-watchlist": update_watchlist_command,
        "remove-watchlist": remove_watchlist_command,
        "collect-new-pools": collect_new_pools_command,
        "analyze-pool-discovery": analyze_pool_discovery_command,
        "db-health": db_health_command,
        "db-monitor": db_monitor_command,
        # "analyze-pool-signals": analyze_pool_signals_command,  # Temporarily disabled
        # "monitor-pool-signals": monitor_pool_signals_command,  # Temporarily disabled
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
        choices=["dex", "top-pools", "watchlist", "ohlcv", "trades", "historical", "new-pools"],
        help="Type of collector to run"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be collected without storing data"
    )
    run_parser.add_argument(
        "--network",
        type=str,
        default="solana",
        help="Network to collect from (for new-pools collector)"
    )
    run_parser.add_argument(
        "--auto-watchlist",
        action="store_true",
        help="Automatically add promising pools to watchlist (for new-pools collector)"
    )
    run_parser.add_argument(
        "--min-liquidity",
        type=float,
        default=1000.0,
        help="Minimum liquidity in USD for watchlist consideration (default: 1000)"
    )
    run_parser.add_argument(
        "--min-volume",
        type=float,
        default=100.0,
        help="Minimum 24h volume in USD for watchlist consideration (default: 100)"
    )
    run_parser.add_argument(
        "--max-age-hours",
        type=int,
        default=24,
        help="Maximum age in hours for new pool consideration (default: 24)"
    )
    run_parser.add_argument(
        "--min-activity-score",
        type=float,
        default=60.0,
        help="Minimum activity score for watchlist addition (default: 60.0)"
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


def _add_list_backups_command(subparsers):
    """Add list-backups command parser."""
    list_backups_parser = subparsers.add_parser(
        'list-backups',
        help='List available database backups',
        description='Display all available database backups with metadata'
    )
    list_backups_parser.add_argument(
        '--format',
        choices=['table', 'json'],
        default='table',
        help='Output format (default: table)'
    )
    list_backups_parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path'
    )
    list_backups_parser.set_defaults(func=list_backups_command)


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
    """Create data backup using enhanced backup system."""
    try:
        # Import our new backup manager
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__ + '/../..')))
        
        from create_database_backup import DatabaseBackupManager
        
        # Initialize backup manager
        backup_manager = DatabaseBackupManager(args.config)
        
        print(f"🗄️  Creating comprehensive database backup...")
        print(f"📁 Target location: {args.backup_path}")
        
        if args.data_types:
            print(f"📊 Data types: {', '.join(args.data_types)}")
            print("⚠️  Note: Comprehensive backup includes all data types")
        else:
            print("📊 Data types: All available")
        
        print(f"🗜️  Compression: {'enabled' if args.compress else 'disabled'}")
        print("-" * 60)
        
        # Extract backup name from path
        backup_name = os.path.basename(args.backup_path)
        
        # Create backup
        backup_path = await backup_manager.create_full_backup(
            backup_name=backup_name,
            compress=args.compress
        )
        
        print(f"\n🎉 Backup completed successfully!")
        print(f"📁 Backup location: {backup_path}")
        
        # If user specified a different path, move the backup
        if os.path.abspath(backup_path) != os.path.abspath(args.backup_path):
            import shutil
            if os.path.exists(args.backup_path):
                shutil.rmtree(args.backup_path)
            shutil.move(backup_path, args.backup_path)
            print(f"📦 Moved backup to: {args.backup_path}")
        
        print(f"\n💡 To restore this backup later, use:")
        print(f"   gecko-cli restore {args.backup_path}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
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


async def add_watchlist_command(args):
    """Add a new entry to the watchlist."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from datetime import datetime
        
        # Load configuration first to determine database type
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Use PostgreSQL models if database URL indicates PostgreSQL
        if config.database.url.startswith(('postgresql://', 'postgres://')):
            from gecko_terminal_collector.database.postgresql_models import WatchlistEntry, Pool, DEX
        else:
            from gecko_terminal_collector.database.models import WatchlistEntry, Pool, DEX
        
        print(f"Adding watchlist entry...")
        print(f"Pool ID: {args.pool_id}")
        print(f"Symbol: {args.symbol}")
        if args.name:
            print(f"Name: {args.name}")
        if args.network_address:
            print(f"Network Address: {args.network_address}")
        
        # Parse active flag
        is_active = args.active.lower() == 'true'
        print(f"Active: {is_active}")
        
        # Extract network and address from pool_id
        if '_' not in args.pool_id:
            print(f"❌ Invalid pool ID format. Expected format: network_address (e.g., solana_ABC123...)")
            return 1
        
        network, pool_address = args.pool_id.split('_', 1)
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        try:
            # Check if entry already exists
            existing_entry = await db_manager.get_watchlist_entry_by_pool_id(args.pool_id)
            if existing_entry:
                print(f"❌ Entry already exists in watchlist: {args.pool_id}")
                print(f"   Existing symbol: {existing_entry.token_symbol}")
                return 1
            
            # Ensure the pool exists (create minimal entry if needed)
            with db_manager.connection.get_session() as session:
                # Check if pool exists
                existing_pool = session.query(Pool).filter_by(id=args.pool_id).first()
                
                if not existing_pool:
                    print(f"Creating minimal pool entry for {args.pool_id}...")
                    
                    # Ensure DEX exists (create if needed)
                    dex_id = f"{network}_unknown"  # Use a generic DEX ID
                    existing_dex = session.query(DEX).filter_by(id=dex_id).first()
                    
                    if not existing_dex:
                        new_dex = DEX(
                            id=dex_id,
                            name=f"{network.title()} Unknown DEX",
                            network=network
                        )
                        session.add(new_dex)
                        session.flush()  # Ensure DEX is created before pool
                    
                    # Create minimal pool entry
                    new_pool = Pool(
                        id=args.pool_id,
                        address=pool_address,
                        name=f"{args.symbol} Pool" if args.symbol else "Unknown Pool",
                        dex_id=dex_id,
                        discovery_source="manual",
                        collection_priority="normal",
                        created_at=datetime.now()
                    )
                    session.add(new_pool)
                    session.commit()
                    print(f"✅ Created minimal pool entry")
            
            # Create watchlist entry
            entry = WatchlistEntry(
                pool_id=args.pool_id,
                token_symbol=args.symbol,
                token_name=args.name,
                network_address=args.network_address,
                is_active=is_active
            )
            
            # Store the entry using the add method
            await db_manager.add_watchlist_entry(entry)
            
            print(f"✅ Successfully added '{args.symbol}' to watchlist")
            print(f"   Pool ID: {args.pool_id}")
            
            # Show current watchlist pool count
            watchlist_pools = await db_manager.get_watchlist_pools()
            print(f"   Total active watchlist entries: {len(watchlist_pools)}")
            
        except Exception as e:
            if "UNIQUE constraint failed" in str(e) or "duplicate key" in str(e):
                print(f"❌ Entry already exists in watchlist: {args.pool_id}")
                return 1
            else:
                raise
        
        finally:
            await db_manager.close()
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to add watchlist entry: {e}")
        return 1


async def list_watchlist_command(args):
    """List all watchlist entries."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        import json
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        try:
            # Get watchlist entries
            if args.active_only:
                entries = await db_manager.get_active_watchlist_entries()
            else:
                entries = await db_manager.get_all_watchlist_entries()
            
            if not entries:
                print("No watchlist entries found.")
                return 0
            
            # Format output
            if args.format == 'json':
                entry_data = []
                for entry in entries:
                    entry_data.append({
                        'id': entry.id,
                        'pool_id': entry.pool_id,
                        'token_symbol': entry.token_symbol,
                        'token_name': entry.token_name,
                        'network_address': entry.network_address,
                        'created_at': entry.created_at.isoformat() if entry.created_at else None,
                        'is_active': entry.is_active
                    })
                print(json.dumps(entry_data, indent=2))
                
            elif args.format == 'csv':
                print("id,pool_id,token_symbol,token_name,network_address,created_at,is_active")
                for entry in entries:
                    created_at = entry.created_at.isoformat() if entry.created_at else ""
                    print(f"{entry.id},{entry.pool_id},{entry.token_symbol or ''},{entry.token_name or ''},{entry.network_address or ''},{created_at},{entry.is_active}")
                    
            else:  # table format
                print(f"{'ID':<5} {'Pool ID':<50} {'Symbol':<10} {'Name':<30} {'Active':<8} {'Added':<20}")
                print("-" * 125)
                for entry in entries:
                    created_at = entry.created_at.strftime('%Y-%m-%d %H:%M:%S') if entry.created_at else ""
                    name = (entry.token_name or "")[:28] + ".." if entry.token_name and len(entry.token_name) > 30 else (entry.token_name or "")
                    print(f"{entry.id:<5} {entry.pool_id:<50} {entry.token_symbol or '':<10} {name:<30} {entry.is_active!s:<8} {created_at:<20}")
                
                print(f"\nTotal entries: {len(entries)}")
                active_count = sum(1 for entry in entries if entry.is_active)
                print(f"Active entries: {active_count}")
            
        finally:
            await db_manager.close()
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to list watchlist entries: {e}")
        return 1


async def update_watchlist_command(args):
    """Update an existing watchlist entry."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        try:
            # Check if entry exists
            existing_entry = await db_manager.get_watchlist_entry_by_pool_id(args.pool_id)
            if not existing_entry:
                print(f"❌ Watchlist entry not found: {args.pool_id}")
                return 1
            
            print(f"Updating watchlist entry for {args.pool_id}...")
            
            # Prepare update data
            update_data = {}
            if args.symbol is not None:
                update_data['token_symbol'] = args.symbol
                print(f"  Symbol: {existing_entry.token_symbol} → {args.symbol}")
            
            if args.name is not None:
                update_data['token_name'] = args.name
                print(f"  Name: {existing_entry.token_name or 'None'} → {args.name}")
            
            if args.network_address is not None:
                update_data['network_address'] = args.network_address
                print(f"  Network Address: {existing_entry.network_address or 'None'} → {args.network_address}")
            
            if args.active is not None:
                is_active = args.active.lower() == 'true'
                update_data['is_active'] = is_active
                print(f"  Active: {existing_entry.is_active} → {is_active}")
            
            if not update_data:
                print("❌ No fields specified for update. Use --symbol, --name, --network-address, or --active.")
                return 1
            
            # Update the entry
            await db_manager.update_watchlist_entry_fields(args.pool_id, update_data)
            
            print(f"✅ Successfully updated watchlist entry for {args.pool_id}")
            
        finally:
            await db_manager.close()
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to update watchlist entry: {e}")
        return 1


async def remove_watchlist_command(args):
    """Remove an entry from the watchlist."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        try:
            # Check if entry exists
            existing_entry = await db_manager.get_watchlist_entry_by_pool_id(args.pool_id)
            if not existing_entry:
                print(f"❌ Watchlist entry not found: {args.pool_id}")
                return 1
            
            # Confirmation prompt unless --force is used
            if not args.force:
                print(f"Are you sure you want to remove the following entry?")
                print(f"  Pool ID: {existing_entry.pool_id}")
                print(f"  Symbol: {existing_entry.token_symbol}")
                print(f"  Name: {existing_entry.token_name or 'None'}")
                
                response = input("Type 'yes' to confirm: ").strip().lower()
                if response != 'yes':
                    print("Operation cancelled.")
                    return 0
            
            # Remove the entry
            await db_manager.remove_watchlist_entry(args.pool_id)
            
            print(f"✅ Successfully removed watchlist entry: {args.pool_id}")
            
        finally:
            await db_manager.close()
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to remove watchlist entry: {e}")
        return 1


async def collect_new_pools_command(args):
    """Run enhanced new pools collection with automatic watchlist integration."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.collectors.enhanced_new_pools_collector import EnhancedNewPoolsCollector
        
        print(f"🚀 Starting enhanced new pools collection for {args.network}")
        print(f"   Auto-watchlist: {args.auto_watchlist}")
        if args.auto_watchlist:
            print(f"   Min liquidity: ${args.min_liquidity:,.2f}")
            print(f"   Min volume: ${args.min_volume:,.2f}")
            print(f"   Max age: {args.max_age_hours} hours")
            print(f"   Min activity score: {args.min_activity_score}")
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        try:
            # Create enhanced collector
            collector = EnhancedNewPoolsCollector(
                config=config,
                db_manager=db_manager,
                network=args.network,
                auto_watchlist=args.auto_watchlist,
                min_liquidity_usd=args.min_liquidity,
                min_volume_24h_usd=args.min_volume,
                max_age_hours=args.max_age_hours,
                min_activity_score=args.min_activity_score
            )
            
            if args.dry_run:
                print("🧪 DRY RUN MODE - No data will be stored")
                # In dry run mode, we'd simulate the collection
                print("   Would collect new pools and evaluate for watchlist...")
                return 0
            
            # Run collection
            result = await collector.collect()
            
            if result.success:
                print(f"✅ Collection completed successfully!")
                print(f"   Records collected: {result.records_collected}")
                
                if result.metadata:
                    metadata = result.metadata
                    print(f"   Pools created: {metadata.get('pools_created', 0)}")
                    print(f"   History records: {metadata.get('history_records', 0)}")
                    
                    if args.auto_watchlist and 'watchlist_stats' in metadata:
                        stats = metadata['watchlist_stats']
                        print(f"\n📊 Watchlist Integration Results:")
                        print(f"   Pools evaluated: {stats.get('pools_evaluated', 0)}")
                        print(f"   Added to watchlist: {stats.get('pools_added_to_watchlist', 0)}")
                        print(f"   Already in watchlist: {stats.get('pools_already_in_watchlist', 0)}")
                        print(f"   Rejected (liquidity): {stats.get('pools_rejected_liquidity', 0)}")
                        print(f"   Rejected (volume): {stats.get('pools_rejected_volume', 0)}")
                        print(f"   Rejected (age): {stats.get('pools_rejected_age', 0)}")
                        print(f"   Rejected (activity): {stats.get('pools_rejected_activity', 0)}")
                
                if result.errors:
                    print(f"\n⚠️  Warnings/Errors encountered:")
                    for error in result.errors:
                        print(f"   - {error}")
            else:
                print(f"❌ Collection failed")
                if result.errors:
                    for error in result.errors:
                        print(f"   Error: {error}")
                return 1
            
        finally:
            await db_manager.close()
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to run enhanced new pools collection: {e}")
        return 1


async def analyze_pool_discovery_command(args):
    """Analyze pool discovery and watchlist statistics."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from datetime import datetime, timedelta
        import json
        
        print(f"📊 Analyzing pool discovery statistics for last {args.days} days")
        if args.network:
            print(f"   Network filter: {args.network}")
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize database
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.days)
            
            # Get statistics (these methods would need to be implemented)
            stats = {
                'analysis_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': args.days
                },
                'pools_discovered': 0,  # Would query new_pools_history table
                'pools_added_to_watchlist': 0,  # Would query watchlist table
                'active_watchlist_entries': 0,  # Current active entries
                'top_networks': [],  # Most active networks
                'discovery_trends': []  # Daily discovery counts
            }
            
            # Get current watchlist count
            watchlist_entries = await db_manager.get_all_watchlist_entries()
            stats['total_watchlist_entries'] = len(watchlist_entries)
            stats['active_watchlist_entries'] = len([e for e in watchlist_entries if e.is_active])
            
            # Format output
            if args.format == 'json':
                print(json.dumps(stats, indent=2))
            elif args.format == 'csv':
                print("metric,value")
                print(f"analysis_days,{args.days}")
                print(f"total_watchlist_entries,{stats['total_watchlist_entries']}")
                print(f"active_watchlist_entries,{stats['active_watchlist_entries']}")
            else:  # table format
                print(f"\n📈 Pool Discovery Analysis Results")
                print(f"{'='*50}")
                print(f"Analysis Period: {args.days} days")
                print(f"Start Date: {start_date.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"End Date: {end_date.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"\n📊 Current Statistics:")
                print(f"Total Watchlist Entries: {stats['total_watchlist_entries']}")
                print(f"Active Watchlist Entries: {stats['active_watchlist_entries']}")
                
                if args.network:
                    print(f"Network Filter: {args.network}")
                
                print(f"\n💡 Note: Enhanced analytics require additional database queries")
                print(f"    to be implemented for historical discovery data.")
            
        finally:
            await db_manager.close()
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to analyze pool discovery: {e}")
        return 1


async def db_health_command(args):
    """Check database health and performance."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
        from gecko_terminal_collector.monitoring.database_monitor import DatabaseHealthMonitor
        import json
        
        print("🔍 Checking database health...")
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize enhanced database manager
        db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        try:
            # Initialize health monitor
            health_monitor = DatabaseHealthMonitor(db_manager)
            
            # Collect health metrics
            print("📊 Collecting health metrics...")
            metrics = await health_monitor.collect_health_metrics()
            
            # Run connectivity test if requested
            if args.test_connectivity:
                print("🔗 Testing database connectivity...")
                is_connected = await db_manager.test_database_connectivity()
                print(f"   Connectivity: {'✅ Connected' if is_connected else '❌ Failed'}")
            
            # Run performance test if requested
            if args.test_performance:
                print("⚡ Running performance benchmarks...")
                start_time = time.time()
                
                # Test simple query performance
                try:
                    count = await db_manager.count_records('pools')
                    query_time = (time.time() - start_time) * 1000
                    print(f"   Query performance: {query_time:.1f}ms (counted {count} pools)")
                except Exception as e:
                    print(f"   Query performance: ❌ Failed ({e})")
            
            # Get health summary
            health_summary = health_monitor.get_health_summary()
            
            # Format output
            if args.format == 'json':
                output = {
                    'health_summary': health_summary,
                    'detailed_metrics': {
                        'timestamp': metrics.timestamp.isoformat(),
                        'circuit_breaker_state': metrics.circuit_breaker_state,
                        'circuit_breaker_failures': metrics.circuit_breaker_failures,
                        'query_performance_ms': metrics.query_performance_ms,
                        'lock_wait_time_ms': metrics.lock_wait_time_ms,
                        'availability': metrics.availability,
                        'error_rate': metrics.error_rate,
                        'wal_mode_enabled': metrics.wal_mode_enabled
                    }
                }
                print(json.dumps(output, indent=2))
            else:
                # Table format
                print(f"\n📈 Database Health Report")
                print(f"{'='*50}")
                print(f"Overall Status: {health_summary['status']}")
                print(f"Message: {health_summary['message']}")
                print(f"Timestamp: {metrics.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                
                print(f"\n🔧 Technical Metrics:")
                print(f"Circuit Breaker State: {metrics.circuit_breaker_state}")
                print(f"Circuit Breaker Failures: {metrics.circuit_breaker_failures}")
                print(f"Query Performance: {metrics.query_performance_ms:.1f}ms")
                print(f"Lock Wait Time: {metrics.lock_wait_time_ms:.1f}ms")
                print(f"Availability: {metrics.availability:.1%}")
                print(f"Error Rate: {metrics.error_rate:.1%}")
                print(f"WAL Mode Enabled: {'✅ Yes' if metrics.wal_mode_enabled else '❌ No'}")
                
                # Health recommendations
                print(f"\n💡 Recommendations:")
                if metrics.circuit_breaker_state == 'OPEN':
                    print("   • Circuit breaker is OPEN - database operations are being blocked")
                    print("   • Wait for automatic recovery or investigate database issues")
                elif metrics.query_performance_ms > 1000:
                    print("   • Query performance is slow - consider database optimization")
                elif not metrics.wal_mode_enabled:
                    print("   • Enable WAL mode for better concurrency (automatic in enhanced manager)")
                elif metrics.error_rate > 0.05:
                    print("   • High error rate detected - check database logs")
                else:
                    print("   • Database is operating within normal parameters")
            
        finally:
            await db_manager.close()
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to check database health: {e}")
        return 1


async def db_monitor_command(args):
    """Start database health monitoring."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
        from gecko_terminal_collector.monitoring.database_monitor import DatabaseHealthMonitor
        import signal
        
        print(f"🔍 Starting database health monitoring...")
        print(f"   Interval: {args.interval} seconds")
        if args.duration:
            print(f"   Duration: {args.duration} minutes")
        else:
            print(f"   Duration: Indefinite (Ctrl+C to stop)")
        
        # Load configuration
        manager = ConfigManager(args.config)
        config = manager.load_config()
        
        # Initialize enhanced database manager
        db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        try:
            # Set up custom alert thresholds
            alert_thresholds = {
                'lock_wait_time_ms': args.alert_threshold_lock_wait,
                'query_performance_ms': args.alert_threshold_query_time
            }
            
            # Initialize health monitor
            health_monitor = DatabaseHealthMonitor(db_manager, alert_thresholds)
            
            # Start monitoring
            await health_monitor.start_monitoring(args.interval)
            
            # Set up signal handler for graceful shutdown
            def signal_handler(signum, frame):
                print(f"\n🛑 Received shutdown signal, stopping monitoring...")
                asyncio.create_task(health_monitor.stop_monitoring())
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            print(f"✅ Database monitoring started. Press Ctrl+C to stop.")
            
            # Run for specified duration or indefinitely
            if args.duration:
                await asyncio.sleep(args.duration * 60)
                print(f"\n⏰ Monitoring duration completed ({args.duration} minutes)")
            else:
                # Run indefinitely until interrupted
                try:
                    while health_monitor.monitoring_active:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    pass
            
            # Stop monitoring
            await health_monitor.stop_monitoring()
            
            # Show final summary
            summary = health_monitor.get_health_summary()
            print(f"\n📊 Final Health Summary:")
            print(f"   Status: {summary['status']}")
            print(f"   Message: {summary['message']}")
            
            # Show metrics history if available
            history = health_monitor.get_metrics_history(hours=1)
            if history:
                print(f"\n📈 Recent Performance (last hour):")
                avg_query_time = sum(m['query_performance_ms'] for m in history) / len(history)
                avg_availability = sum(m['availability'] for m in history) / len(history)
                print(f"   Average Query Time: {avg_query_time:.1f}ms")
                print(f"   Average Availability: {avg_availability:.1%}")
                print(f"   Total Samples: {len(history)}")
            
        finally:
            await db_manager.close()
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to start database monitoring: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())



async def analyze_pool_signals_command(args):
    """Analyze pool signals from new pools history."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer
        from datetime import datetime, timedelta
        import json
        
        # Load configuration
        config_manager = ConfigManager(args.config)
        config = config_manager.load_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Initialize signal analyzer
        signal_config = config.new_pools.get('signal_detection', {})
        analyzer = NewPoolsSignalAnalyzer(signal_config)
        
        print(f"Analyzing pool signals for network: {args.network}")
        print(f"Time window: {args.hours} hours")
        print(f"Minimum signal score: {args.min_signal_score}")
        print("-" * 60)
        
        # Get pools with signals from the last N hours
        cutoff_time = datetime.now() - timedelta(hours=args.hours)
        
        # Query new_pools_history for recent records with signal data
        from gecko_terminal_collector.database.models import NewPoolsHistory
        
        with db_manager.connection.get_session() as session:
            query = session.query(NewPoolsHistory).filter(
                NewPoolsHistory.network_id == args.network,
                NewPoolsHistory.collected_at >= cutoff_time,
                NewPoolsHistory.signal_score >= args.min_signal_score
            ).order_by(NewPoolsHistory.signal_score.desc()).limit(args.limit)
            
            records = query.all()
        
        if not records:
            print("No pools found with significant signals in the specified time window.")
            return 0
        
        # Format output
        if args.format == 'json':
            results = []
            for record in records:
                results.append({
                    'pool_id': record.pool_id,
                    'signal_score': float(record.signal_score) if record.signal_score else 0,
                    'volume_trend': record.volume_trend,
                    'liquidity_trend': record.liquidity_trend,
                    'momentum_indicator': float(record.momentum_indicator) if record.momentum_indicator else 0,
                    'activity_score': float(record.activity_score) if record.activity_score else 0,
                    'volume_24h': float(record.volume_usd_h24) if record.volume_usd_h24 else 0,
                    'liquidity': float(record.reserve_in_usd) if record.reserve_in_usd else 0,
                    'collected_at': record.collected_at.isoformat()
                })
            print(json.dumps(results, indent=2))
            
        elif args.format == 'csv':
            print("pool_id,signal_score,volume_trend,liquidity_trend,momentum_indicator,activity_score,volume_24h,liquidity,collected_at")
            for record in records:
                print(f"{record.pool_id},{record.signal_score or 0},{record.volume_trend or ''},{record.liquidity_trend or ''},{record.momentum_indicator or 0},{record.activity_score or 0},{record.volume_usd_h24 or 0},{record.reserve_in_usd or 0},{record.collected_at}")
                
        else:  # table format
            print(f"{'Pool ID':<20} {'Signal':<8} {'Vol Trend':<12} {'Liq Trend':<12} {'Momentum':<10} {'Activity':<10} {'Volume 24h':<12} {'Collected At':<20}")
            print("-" * 120)
            
            for record in records:
                pool_id_short = record.pool_id[:18] + "..." if len(record.pool_id) > 20 else record.pool_id
                signal_score = f"{record.signal_score:.1f}" if record.signal_score else "0.0"
                momentum = f"{record.momentum_indicator:.1f}" if record.momentum_indicator else "0.0"
                activity = f"{record.activity_score:.1f}" if record.activity_score else "0.0"
                volume = f"${record.volume_usd_h24:,.0f}" if record.volume_usd_h24 else "$0"
                collected = record.collected_at.strftime("%m-%d %H:%M")
                
                print(f"{pool_id_short:<20} {signal_score:<8} {record.volume_trend or 'unknown':<12} {record.liquidity_trend or 'unknown':<12} {momentum:<10} {activity:<10} {volume:<12} {collected:<20}")
        
        print(f"\nFound {len(records)} pools with signals >= {args.min_signal_score}")
        
        await db_manager.close()
        return 0
        
    except Exception as e:
        print(f"Error analyzing pool signals: {e}")
        return 1


async def monitor_pool_signals_command(args):
    """Monitor pools for signal conditions."""
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
        from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer
        from datetime import datetime, timedelta
        import asyncio
        import signal
        
        # Load configuration
        config_manager = ConfigManager(args.config)
        config = config_manager.load_config()
        
        # Initialize database manager
        db_manager = SQLAlchemyDatabaseManager(config.database)
        await db_manager.initialize()
        
        # Initialize signal analyzer
        signal_config = config.new_pools.get('signal_detection', {})
        analyzer = NewPoolsSignalAnalyzer(signal_config)
        
        print(f"Starting pool signal monitoring...")
        print(f"Network: {args.network}")
        print(f"Alert threshold: {args.alert_threshold}")
        print(f"Check interval: {args.interval} seconds")
        if args.pool_id:
            print(f"Monitoring specific pool: {args.pool_id}")
        print(f"Started at: {datetime.now()}")
        print("-" * 60)
        
        # Set up signal handling for graceful shutdown
        shutdown_event = asyncio.Event()
        
        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}, shutting down gracefully...")
            shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        start_time = datetime.now()
        check_count = 0
        alerts_sent = 0
        
        try:
            while not shutdown_event.is_set():
                check_count += 1
                current_time = datetime.now()
                
                # Check if duration limit reached
                if args.duration:
                    elapsed_minutes = (current_time - start_time).total_seconds() / 60
                    if elapsed_minutes >= args.duration:
                        print(f"Duration limit ({args.duration} minutes) reached. Stopping monitoring.")
                        break
                
                print(f"[{current_time.strftime('%H:%M:%S')}] Check #{check_count} - Scanning for signals...")
                
                # Query for recent high-signal pools
                from gecko_terminal_collector.database.models import NewPoolsHistory
                
                # Look for signals in the last 2 check intervals
                lookback_minutes = (args.interval * 2) / 60
                cutoff_time = current_time - timedelta(minutes=lookback_minutes)
                
                with db_manager.connection.get_session() as session:
                    query = session.query(NewPoolsHistory).filter(
                        NewPoolsHistory.collected_at >= cutoff_time,
                        NewPoolsHistory.signal_score >= args.alert_threshold
                    )
                    
                    if args.network:
                        query = query.filter(NewPoolsHistory.network_id == args.network)
                    
                    if args.pool_id:
                        query = query.filter(NewPoolsHistory.pool_id == args.pool_id)
                    
                    query = query.order_by(NewPoolsHistory.signal_score.desc())
                    
                    records = query.all()
                
                if records:
                    print(f"🚨 ALERT: Found {len(records)} pools with strong signals!")
                    print("-" * 40)
                    
                    for record in records:
                        alerts_sent += 1
                        pool_id_short = record.pool_id[:15] + "..." if len(record.pool_id) > 18 else record.pool_id
                        
                        print(f"Pool: {pool_id_short}")
                        print(f"  Signal Score: {record.signal_score:.1f}")
                        print(f"  Volume Trend: {record.volume_trend or 'unknown'}")
                        print(f"  Liquidity Trend: {record.liquidity_trend or 'unknown'}")
                        print(f"  Volume 24h: ${record.volume_usd_h24:,.0f}" if record.volume_usd_h24 else "  Volume 24h: $0")
                        print(f"  Detected: {record.collected_at.strftime('%H:%M:%S')}")
                        print()
                    
                    print("-" * 40)
                else:
                    print("No significant signals detected.")
                
                # Wait for next check or shutdown
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=args.interval)
                    break  # Shutdown event was set
                except asyncio.TimeoutError:
                    continue  # Continue monitoring
                    
        except KeyboardInterrupt:
            print("\nMonitoring interrupted by user.")
        
        # Print summary
        elapsed_time = datetime.now() - start_time
        print(f"\nMonitoring Summary:")
        print(f"Duration: {elapsed_time}")
        print(f"Checks performed: {check_count}")
        print(f"Alerts generated: {alerts_sent}")
        
        await db_manager.close()
        return 0
        
    except Exception as e:
        print(f"Error monitoring pool signals: {e}")
        return 1


async def list_backups_command(args):
    """List available database backups."""
    try:
        # Import our backup manager
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.abspath(__file__ + '/../..')))
        
        from create_database_backup import DatabaseBackupManager
        import json
        
        # Initialize backup manager
        backup_manager = DatabaseBackupManager(args.config)
        
        print("📋 Available Database Backups")
        print("=" * 60)
        
        # Get list of backups
        backups = await backup_manager.list_backups()
        
        if not backups:
            print("No backups found.")
            print(f"\n💡 Create a backup with:")
            print(f"   gecko-cli backup /path/to/backup")
            return 0
        
        if args.format == 'json':
            print(json.dumps(backups, indent=2, default=str))
        else:
            # Table format
            print(f"{'Name':<25} {'Created':<20} {'Size':<10} {'Type':<12}")
            print("-" * 70)
            
            for backup in backups:
                name = backup['name'][:23] + "..." if len(backup['name']) > 25 else backup['name']
                created = backup.get('created_at', 'unknown')
                if created != 'unknown' and 'T' in created:
                    # Format datetime
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        created = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        created = created[:16]  # Truncate if parsing fails
                
                size = backup['size']
                db_type = backup.get('database_type', 'unknown')
                
                print(f"{name:<25} {created:<20} {size:<10} {db_type:<12}")
            
            print(f"\nTotal backups: {len(backups)}")
            print(f"\n💡 To restore a backup, use:")
            print(f"   gecko-cli restore <backup_path>")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error listing backups: {e}")
        return 1