"""
CLI enhancements for new pools history tracking and QLib integration.
"""

import asyncio
import click
from datetime import datetime, timedelta
from typing import List, Optional
import json
import functools

from gecko_terminal_collector.database.manager import DatabaseManager
from enhanced_new_pools_collector import EnhancedNewPoolsCollector
from qlib_integration import QLibDataExporter, export_qlib_data_cli
from migrate_to_enhanced_history import run_migration_cli


@click.group()
def new_pools_enhanced():
    """Enhanced new pools collection and analysis commands."""
    pass


def get_database_manager():
    """Get database manager instance from config."""
    try:
        from gecko_terminal_collector.config.loader import load_config
        from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
        
        config = load_config()
        db_manager = EnhancedDatabaseManager(config.database)
        return db_manager
    except Exception as e:
        click.echo(f"❌ Error initializing database manager: {e}")
        return None


def async_command(f):
    """Decorator to run async functions in click commands."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@new_pools_enhanced.command()
@click.option('--network', required=True, help='Network to collect pools for (e.g., solana, ethereum)')
@click.option('--intervals', default='1h', help='Collection intervals (comma-separated: 1h,4h,1d)')
@click.option('--enable-features', is_flag=True, default=True, help='Enable feature engineering')
@click.option('--enable-qlib', is_flag=True, default=True, help='Enable QLib integration')
@click.option('--enable-auto-watchlist', is_flag=True, default=True, help='Enable auto-watchlist integration')
@click.option('--watchlist-threshold', default=75.0, type=float, help='Signal score threshold for auto-watchlist')
@click.option('--min-liquidity', default=1000, type=float, help='Minimum liquidity USD threshold')
@click.option('--min-volume', default=100, type=float, help='Minimum volume USD threshold')
@click.option('--dry-run', is_flag=True, help='Show what would be collected without storing')
@async_command
async def collect_enhanced(
    network: str,
    intervals: str,
    enable_features: bool,
    enable_qlib: bool,
    enable_auto_watchlist: bool,
    watchlist_threshold: float,
    min_liquidity: float,
    min_volume: float,
    dry_run: bool
):
    """Collect new pools data with enhanced tracking and ML features."""
    try:
        click.echo(f"🚀 Starting enhanced new pools collection for {network}")
        
        # Parse intervals
        interval_list = [i.strip() for i in intervals.split(',')]
        click.echo(f"📊 Collection intervals: {interval_list}")
        
        if dry_run:
            click.echo("🔍 DRY RUN MODE - No data will be stored")
        
        # Initialize database manager
        db_manager = get_database_manager()
        if not db_manager:
            return
        
        click.echo("Configuration:")
        click.echo(f"  - Network: {network}")
        click.echo(f"  - Intervals: {interval_list}")
        click.echo(f"  - Feature engineering: {enable_features}")
        click.echo(f"  - QLib integration: {enable_qlib}")
        click.echo(f"  - Auto-watchlist: {enable_auto_watchlist}")
        if enable_auto_watchlist:
            click.echo(f"  - Watchlist threshold: {watchlist_threshold}")
        click.echo(f"  - Min liquidity: ${min_liquidity:,.2f}")
        click.echo(f"  - Min volume: ${min_volume:,.2f}")
        
        if dry_run:
            click.echo("✅ Configuration validated - ready for collection")
            return
        
        try:
            # Initialize database connection
            await db_manager.initialize()
            
            # Load configuration
            from gecko_terminal_collector.config.loader import load_config
            config = load_config()
            
            # Create enhanced collector
            collector = EnhancedNewPoolsCollector(
                config=config,
                db_manager=db_manager,
                network=network,
                collection_intervals=interval_list,
                enable_feature_engineering=enable_features,
                qlib_integration=enable_qlib,
                auto_watchlist_enabled=enable_auto_watchlist,
                auto_watchlist_threshold=watchlist_threshold
            )
            
            # Run collection
            result = await collector.collect()
            
            if result.success:
                click.echo(f"✅ Collection completed: {result.records_collected} records")
                if result.metadata:
                    click.echo(f"📊 Metadata: {result.metadata}")
            else:
                click.echo(f"❌ Collection failed")
                for error in result.errors:
                    click.echo(f"   - {error}")
                    
        except Exception as e:
            click.echo(f"❌ Collection error: {e}")
        finally:
            if db_manager:
                await db_manager.close()
        
    except Exception as e:
        click.echo(f"❌ Collection error: {e}")


@new_pools_enhanced.command()
@click.option('--start-date', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end-date', required=True, help='End date (YYYY-MM-DD)')
@click.option('--networks', help='Networks to include (comma-separated)')
@click.option('--qlib-dir', default='./qlib_data', help='QLib data directory')
@click.option('--freq', default='60min', help='Data frequency (60min, day)')
@click.option('--min-liquidity', default=1000, type=float, help='Minimum liquidity USD')
@click.option('--min-volume', default=100, type=float, help='Minimum volume USD')
@click.option('--mode', default='all', type=click.Choice(['all', 'update', 'fix']), help='Export mode')
@click.option('--backup-dir', help='Backup directory (optional)')
@click.option('--export-name', help='Custom export name')
@async_command
async def export_qlib_bin(
    start_date: str,
    end_date: str,
    networks: Optional[str],
    qlib_dir: str,
    freq: str,
    min_liquidity: float,
    min_volume: float,
    mode: str,
    backup_dir: Optional[str],
    export_name: Optional[str]
):
    """Export new pools history data in QLib bin format for QLib-Server integration."""
    try:
        click.echo("📊 Exporting data for QLib in bin format...")
        
        # Parse networks
        network_list = None
        if networks:
            network_list = [n.strip() for n in networks.split(',')]
        
        # Parse dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        click.echo(f"📅 Date range: {start_dt.date()} to {end_dt.date()}")
        click.echo(f"🌐 Networks: {network_list or 'all'}")
        click.echo(f"💰 Min liquidity: ${min_liquidity:,.2f}")
        click.echo(f"📈 Min volume: ${min_volume:,.2f}")
        click.echo(f"📁 QLib directory: {qlib_dir}")
        click.echo(f"⏱️  Frequency: {freq}")
        click.echo(f"🔄 Mode: {mode}")
        
        if backup_dir:
            click.echo(f"💾 Backup directory: {backup_dir}")
        
        # Show what the command would do
        click.echo("\n🔧 Export configuration:")
        click.echo(f"  - Export mode: {mode}")
        if mode == "all":
            click.echo("    → Full export of all data")
        elif mode == "update":
            click.echo("    → Incremental update of existing data")
        elif mode == "fix":
            click.echo("    → Repair/add missing symbols")
        
        click.echo(f"  - Data frequency: {freq}")
        click.echo(f"  - QLib bin format: Compatible with dump_bin.py")
        click.echo(f"  - Incremental updates: Supported")
        
        # Initialize database manager and run export
        db_manager = get_database_manager()
        if not db_manager:
            return
        
        try:
            await db_manager.initialize()
            
            from qlib_integration import QLibBinDataExporter
            
            exporter = QLibBinDataExporter(
                db_manager=db_manager,
                qlib_dir=qlib_dir,
                freq=freq,
                backup_dir=backup_dir
            )
            
            result = await exporter.export_bin_data(
                start_date=start_dt,
                end_date=end_dt,
                networks=network_list,
                min_liquidity_usd=min_liquidity,
                min_volume_usd=min_volume,
                export_name=export_name,
                mode=mode
            )
            
            if result['success']:
                click.echo(f"✅ Export completed successfully!")
                click.echo(f"📊 Symbols processed: {result.get('symbols_processed', 0)}")
                if 'calendar_entries' in result:
                    click.echo(f"📅 Calendar entries: {result['calendar_entries']}")
                if 'new_dates' in result:
                    click.echo(f"🆕 New dates added: {result['new_dates']}")
            else:
                click.echo(f"❌ Export failed: {result.get('error', 'Unknown error')}")
                if 'errors' in result:
                    for error in result['errors']:
                        click.echo(f"   - {error}")
                        
        except Exception as e:
            click.echo(f"❌ Export error: {e}")
        finally:
            if db_manager:
                await db_manager.close()
        
        # Show example QLib usage
        click.echo(f"\n📖 After export, use with QLib:")
        click.echo(f"   import qlib")
        click.echo(f"   qlib.init(provider_uri='{qlib_dir}', region='us')")
        
    except Exception as e:
        click.echo(f"❌ Export error: {e}")


@new_pools_enhanced.command()
@click.option('--qlib-dir', required=True, help='QLib data directory to check')
@click.option('--freq', default='60min', help='Data frequency')
@click.option('--price-threshold', default=0.5, type=float, help='Price change threshold')
@click.option('--volume-threshold', default=3.0, type=float, help='Volume change threshold')
@async_command
async def check_qlib_health(
    qlib_dir: str,
    freq: str,
    price_threshold: float,
    volume_threshold: float
):
    """Check health of QLib bin data."""
    try:
        click.echo("🏥 Checking QLib data health...")
        
        click.echo(f"📁 QLib directory: {qlib_dir}")
        click.echo(f"⏱️  Frequency: {freq}")
        click.echo(f"📈 Price change threshold: {price_threshold}")
        click.echo(f"📊 Volume change threshold: {volume_threshold}")
        
        # For actual implementation:
        """
        from qlib_integration import QLibDataHealthChecker
        
        checker = QLibDataHealthChecker(
            qlib_dir=qlib_dir,
            freq=freq,
            large_step_threshold_price=price_threshold,
            large_step_threshold_volume=volume_threshold
        )
        
        results = checker.run_health_check()
        
        if results['success']:
            click.echo(f"✅ Health check completed")
            click.echo(f"📊 Total symbols: {results['total_symbols']}")
            click.echo(f"🏥 Overall health: {results['overall_health']}")
            
            if results['overall_health'] == 'ISSUES_FOUND':
                click.echo("⚠️  Issues found - check detailed results")
        else:
            click.echo(f"❌ Health check failed: {results['error']}")
        """
        
        click.echo("⚠️  Actual health check requires QLib setup")
        click.echo("   Import and use QLibDataHealthChecker class")
        
    except Exception as e:
        click.echo(f"❌ Health check error: {e}")


@new_pools_enhanced.command()
@click.option('--backup/--no-backup', default=True, help='Create backup before migration')
@click.option('--dry-run', is_flag=True, help='Show what would be done without making changes')
@async_command
async def migrate_tables(backup: bool, dry_run: bool):
    """Migrate existing new_pools_history to enhanced format."""
    try:
        click.echo("🔄 New pools history table migration")
        
        if dry_run:
            click.echo("🔍 DRY RUN MODE - Checking current state...")
        
        if backup and not dry_run:
            click.echo("💾 Backup will be created before migration")
        
        # Initialize database manager and run migration
        db_manager = get_database_manager()
        if not db_manager:
            return
        
        try:
            await db_manager.initialize()
            
            result = await run_migration_cli(
                db_manager=db_manager,
                backup=backup,
                dry_run=dry_run
            )
            
            if result['success']:
                if dry_run:
                    click.echo("✅ Migration validation completed")
                else:
                    click.echo("✅ Migration completed successfully!")
                    click.echo(f"📊 Records migrated: {result.get('records_migrated', 0)}")
            else:
                click.echo("❌ Migration failed!")
                if 'errors' in result:
                    for error in result['errors']:
                        click.echo(f"   - {error}")
                        
        except Exception as e:
            click.echo(f"❌ Migration error: {e}")
        finally:
            if db_manager:
                await db_manager.close()
        
    except Exception as e:
        click.echo(f"❌ Migration error: {e}")


@new_pools_enhanced.command()
@click.option('--pool-id', help='Specific pool ID to analyze')
@click.option('--network', help='Network to analyze')
@click.option('--days', default=7, type=int, help='Number of days to analyze')
@click.option('--format', 'output_format', default='table', type=click.Choice(['table', 'json', 'csv']))
@async_command
async def analyze_signals(
    pool_id: Optional[str],
    network: Optional[str],
    days: int,
    output_format: str
):
    """Analyze signal patterns in new pools data."""
    try:
        click.echo("📈 Analyzing new pools signals...")
        
        if pool_id:
            click.echo(f"🎯 Analyzing specific pool: {pool_id}")
        elif network:
            click.echo(f"🌐 Analyzing network: {network}")
        else:
            click.echo("📊 Analyzing all pools")
        
        click.echo(f"📅 Analysis period: {days} days")
        click.echo(f"📋 Output format: {output_format}")
        
        # Example analysis queries that would be run:
        analysis_queries = [
            "Top pools by signal score",
            "Volume trend analysis",
            "Liquidity growth patterns",
            "Activity score distribution",
            "Price volatility analysis"
        ]
        
        click.echo("\n🔍 Analysis components:")
        for i, query in enumerate(analysis_queries, 1):
            click.echo(f"  {i}. {query}")
        
        click.echo("\n⚠️  Actual analysis requires DatabaseManager setup")
        click.echo("   This would query the new_pools_history_enhanced table")
        
    except Exception as e:
        click.echo(f"❌ Analysis error: {e}")


@new_pools_enhanced.command()
@click.option('--export-name', required=True, help='Name of the QLib export to use')
@click.option('--model-type', default='lgb', type=click.Choice(['linear', 'lgb', 'transformer']), help='Model type to train')
@click.option('--target', default='return_24h', help='Target variable to predict')
@click.option('--output-dir', default='./models', help='Output directory for trained models')
@async_command
async def train_model(
    export_name: str,
    model_type: str,
    target: str,
    output_dir: str
):
    """Train predictive models using QLib exported data."""
    try:
        click.echo(f"🤖 Training {model_type} model...")
        click.echo(f"📊 Using export: {export_name}")
        click.echo(f"🎯 Target variable: {target}")
        click.echo(f"📁 Output directory: {output_dir}")
        
        # This would integrate with QLib for actual model training
        training_steps = [
            "Load QLib exported data",
            "Prepare feature matrix",
            "Split train/validation/test sets",
            f"Train {model_type} model",
            "Evaluate model performance",
            "Save trained model",
            "Generate performance report"
        ]
        
        click.echo("\n🔄 Training pipeline:")
        for i, step in enumerate(training_steps, 1):
            click.echo(f"  {i}. {step}")
        
        click.echo("\n⚠️  Actual training requires QLib setup and exported data")
        click.echo("   This would use the QLib framework for model training")
        
    except Exception as e:
        click.echo(f"❌ Training error: {e}")


@new_pools_enhanced.command()
@click.option('--days', default=30, type=int, help='Number of days to report on')
@click.option('--format', 'output_format', default='table', type=click.Choice(['table', 'json']))
@async_command
async def performance_report(days: int, output_format: str):
    """Generate performance report for new pools collection system."""
    try:
        click.echo(f"📊 Generating {days}-day performance report...")
        
        # Example metrics that would be calculated
        metrics = {
            "Collection Statistics": [
                "Total pools collected",
                "Unique pools discovered",
                "Average collection frequency",
                "Data quality score distribution"
            ],
            "Signal Analysis": [
                "High-signal pools identified",
                "Signal accuracy rate",
                "False positive rate",
                "Top performing signals"
            ],
            "Watchlist Integration": [
                "Auto-added pools count",
                "Watchlist success rate",
                "Manual vs auto additions",
                "Removal rate"
            ],
            "System Performance": [
                "Collection success rate",
                "Average processing time",
                "Error rate by network",
                "Database performance metrics"
            ]
        }
        
        click.echo(f"\n📋 Report sections ({output_format} format):")
        for section, items in metrics.items():
            click.echo(f"\n  📈 {section}:")
            for item in items:
                click.echo(f"    - {item}")
        
        click.echo("\n⚠️  Actual report requires DatabaseManager setup")
        click.echo("   This would query collection_metadata and history tables")
        
    except Exception as e:
        click.echo(f"❌ Report error: {e}")


# Integration with existing CLI
def add_enhanced_commands_to_cli(cli_group):
    """Add enhanced new pools commands to existing CLI."""
    cli_group.add_command(new_pools_enhanced, name='new-pools-enhanced')


# Example usage functions for integration
async def collect_enhanced_pools_example(db_manager, network: str):
    """Example function showing how to use enhanced collector."""
    try:
        from gecko_terminal_collector.config.models import CollectionConfig
        
        # Create collector with enhanced features
        collector = EnhancedNewPoolsCollector(
            config=CollectionConfig(),  # Your config
            db_manager=db_manager,
            network=network,
            collection_intervals=['1h', '4h'],
            enable_feature_engineering=True,
            qlib_integration=True
        )
        
        # Run collection
        result = await collector.collect()
        
        return result
        
    except Exception as e:
        print(f"Collection error: {e}")
        return None


async def export_for_ml_example(db_manager, start_date: str, end_date: str):
    """Example function showing how to export data for ML."""
    try:
        exporter = QLibDataExporter(db_manager, "./ml_data")
        
        result = await exporter.export_training_data(
            start_date=datetime.fromisoformat(start_date),
            end_date=datetime.fromisoformat(end_date),
            networks=['solana', 'ethereum'],
            min_liquidity_usd=1000,
            min_volume_usd=100
        )
        
        return result
        
    except Exception as e:
        print(f"Export error: {e}")
        return None


if __name__ == "__main__":
    # Run CLI commands
    new_pools_enhanced()