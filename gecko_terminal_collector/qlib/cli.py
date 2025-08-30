"""
Command-line interface for QLib data export functionality.
"""

import asyncio
import click
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from gecko_terminal_collector.qlib.exporter import QLibExporter
from gecko_terminal_collector.qlib.utils import (
    QLibDataValidator, 
    validate_qlib_export_directory,
    export_qlib_instruments
)
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.config.models import DatabaseConfig


@click.group()
def qlib_cli():
    """QLib data export commands."""
    pass


@qlib_cli.command()
@click.option('--db-url', default='sqlite:///demo_gecko_data.db', 
              help='Database URL')
@click.option('--network', default='solana', 
              help='Network to filter symbols')
@click.option('--dex-filter', multiple=True, 
              help='DEX IDs to filter by (can specify multiple)')
@click.option('--active-only/--all', default=True,
              help='Include only active watchlist symbols')
def list_symbols(db_url: str, network: str, dex_filter: tuple, active_only: bool):
    """List available symbols for QLib export."""
    
    async def _list_symbols():
        # Initialize database manager
        db_config = DatabaseConfig(url=db_url)
        db_manager = SQLAlchemyDatabaseManager(db_config)
        await db_manager.initialize()
        
        try:
            # Create exporter
            exporter = QLibExporter(db_manager)
            
            # Get symbols
            dex_list = list(dex_filter) if dex_filter else None
            symbols = await exporter.get_symbol_list(
                network=network,
                dex_filter=dex_list,
                active_only=active_only
            )
            
            if symbols:
                click.echo(f"Found {len(symbols)} symbols:")
                for symbol in symbols:
                    click.echo(f"  {symbol}")
            else:
                click.echo("No symbols found.")
                
        finally:
            await db_manager.close()
    
    asyncio.run(_list_symbols())


@qlib_cli.command()
@click.option('--db-url', default='sqlite:///demo_gecko_data.db',
              help='Database URL')
@click.option('--output-dir', required=True, type=click.Path(),
              help='Output directory for CSV files')
@click.option('--symbols', multiple=True,
              help='Specific symbols to export (default: all available)')
@click.option('--start-date', type=click.DateTime(formats=['%Y-%m-%d']),
              help='Start date for export (YYYY-MM-DD)')
@click.option('--end-date', type=click.DateTime(formats=['%Y-%m-%d']),
              help='End date for export (YYYY-MM-DD)')
@click.option('--timeframe', default='1h',
              help='Data timeframe (1m, 5m, 15m, 1h, 4h, 12h, 1d)')
@click.option('--include-volume/--no-volume', default=True,
              help='Include volume data')
@click.option('--date-field-name', default='datetime',
              help='Name of date field in output')
def export_data(db_url: str, output_dir: str, symbols: tuple, 
               start_date: Optional[datetime], end_date: Optional[datetime],
               timeframe: str, include_volume: bool, date_field_name: str):
    """Export OHLCV data to QLib-compatible CSV files."""
    
    async def _export_data():
        # Initialize database manager
        db_config = DatabaseConfig(url=db_url)
        db_manager = SQLAlchemyDatabaseManager(db_config)
        await db_manager.initialize()
        
        try:
            # Create exporter
            exporter = QLibExporter(db_manager)
            
            # Convert symbols tuple to list
            symbol_list = list(symbols) if symbols else None
            
            # Export data
            click.echo(f"Exporting data to {output_dir}...")
            click.echo(f"Timeframe: {timeframe}")
            click.echo(f"Date range: {start_date} to {end_date}")
            click.echo(f"Symbols: {len(symbol_list) if symbol_list else 'all available'}")
            
            result = await exporter.export_to_qlib_format(
                output_dir=output_dir,
                symbols=symbol_list,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                date_field_name=date_field_name
            )
            
            if result['success']:
                click.echo(f"✓ Export completed successfully!")
                click.echo(f"  Files created: {result['files_created']}")
                click.echo(f"  Total records: {result['total_records']}")
            else:
                click.echo(f"✗ Export failed: {result['message']}")
                
        finally:
            await db_manager.close()
    
    asyncio.run(_export_data())


@qlib_cli.command()
@click.option('--db-url', default='sqlite:///demo_gecko_data.db',
              help='Database URL')
@click.option('--symbols', multiple=True,
              help='Specific symbols to check (default: all available)')
@click.option('--timeframe', default='1h',
              help='Timeframe to check availability for')
@click.option('--output-file', type=click.Path(),
              help='Save report to JSON file')
def availability_report(db_url: str, symbols: tuple, timeframe: str, 
                       output_file: Optional[str]):
    """Generate data availability report."""
    
    async def _availability_report():
        # Initialize database manager
        db_config = DatabaseConfig(url=db_url)
        db_manager = SQLAlchemyDatabaseManager(db_config)
        await db_manager.initialize()
        
        try:
            # Create exporter
            exporter = QLibExporter(db_manager)
            
            # Convert symbols tuple to list
            symbol_list = list(symbols) if symbols else None
            
            # Generate report
            click.echo("Generating availability report...")
            report = await exporter.get_data_availability_report(
                symbols=symbol_list,
                timeframe=timeframe
            )
            
            if not report:
                click.echo("No data availability information found.")
                return
            
            # Display summary
            available_count = sum(1 for info in report.values() if info.get('available', False))
            click.echo(f"\nAvailability Summary:")
            click.echo(f"  Total symbols: {len(report)}")
            click.echo(f"  Available: {available_count}")
            click.echo(f"  Unavailable: {len(report) - available_count}")
            
            # Display details
            click.echo(f"\nDetailed Report:")
            for symbol, info in report.items():
                if info.get('available', False):
                    click.echo(f"  ✓ {symbol}")
                    click.echo(f"    Records: {info.get('total_records', 0)}")
                    click.echo(f"    Date range: {info.get('start_date', 'N/A')} to {info.get('end_date', 'N/A')}")
                    click.echo(f"    Quality score: {info.get('data_quality_score', 0):.2f}")
                    click.echo(f"    Gaps: {info.get('total_gaps', 0)}")
                else:
                    click.echo(f"  ✗ {symbol}: {info.get('reason', 'Unknown error')}")
            
            # Save to file if requested
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(report, f, indent=2, default=str)
                click.echo(f"\nReport saved to {output_file}")
                
        finally:
            await db_manager.close()
    
    asyncio.run(_availability_report())


@qlib_cli.command()
@click.argument('export_dir', type=click.Path(exists=True))
def validate_export(export_dir: str):
    """Validate QLib export directory and files."""
    
    click.echo(f"Validating export directory: {export_dir}")
    
    result = validate_qlib_export_directory(export_dir)
    
    if result['is_valid']:
        click.echo("✓ Export directory is valid")
    else:
        click.echo("✗ Export directory has issues")
    
    # Display statistics
    stats = result['stats']
    click.echo(f"\nStatistics:")
    click.echo(f"  Total files: {stats['total_files']}")
    click.echo(f"  CSV files: {stats['csv_files']}")
    click.echo(f"  Symbols: {len(stats['symbols'])}")
    
    # Display errors
    if result['errors']:
        click.echo(f"\nErrors:")
        for error in result['errors']:
            click.echo(f"  ✗ {error}")
    
    # Display warnings
    if result['warnings']:
        click.echo(f"\nWarnings:")
        for warning in result['warnings']:
            click.echo(f"  ⚠ {warning}")
    
    if stats['symbols']:
        click.echo(f"\nSymbols found:")
        for symbol in stats['symbols'][:10]:  # Show first 10
            click.echo(f"  {symbol}")
        if len(stats['symbols']) > 10:
            click.echo(f"  ... and {len(stats['symbols']) - 10} more")


@qlib_cli.command()
@click.argument('csv_file', type=click.Path(exists=True))
@click.option('--require-volume/--no-require-volume', default=False,
              help='Require volume column')
def validate_csv(csv_file: str, require_volume: bool):
    """Validate individual CSV file for QLib compatibility."""
    
    import pandas as pd
    
    click.echo(f"Validating CSV file: {csv_file}")
    
    try:
        df = pd.read_csv(csv_file)
        result = QLibDataValidator.validate_dataframe(df, require_volume=require_volume)
        
        if result['is_valid']:
            click.echo("✓ CSV file is valid for QLib")
        else:
            click.echo("✗ CSV file has validation issues")
        
        # Display statistics
        stats = result['stats']
        click.echo(f"\nStatistics:")
        click.echo(f"  Total rows: {stats['total_rows']}")
        click.echo(f"  Unique symbols: {stats['unique_symbols']}")
        click.echo(f"  Columns: {', '.join(stats['columns'])}")
        
        if stats['date_range']:
            click.echo(f"  Date range: {stats['date_range']['start']} to {stats['date_range']['end']}")
        
        # Display errors
        if result['errors']:
            click.echo(f"\nErrors:")
            for error in result['errors']:
                click.echo(f"  ✗ {error}")
        
        # Display warnings
        if result['warnings']:
            click.echo(f"\nWarnings:")
            for warning in result['warnings']:
                click.echo(f"  ⚠ {warning}")
                
    except Exception as e:
        click.echo(f"✗ Error reading CSV file: {e}")


@qlib_cli.command()
@click.option('--db-url', default='sqlite:///demo_gecko_data.db',
              help='Database URL')
@click.option('--output-file', required=True, type=click.Path(),
              help='Output file for instruments list')
@click.option('--network', default='solana',
              help='Network to filter symbols')
def export_instruments(db_url: str, output_file: str, network: str):
    """Export instruments list for QLib."""
    
    async def _export_instruments():
        # Initialize database manager
        db_config = DatabaseConfig(url=db_url)
        db_manager = SQLAlchemyDatabaseManager(db_config)
        await db_manager.initialize()
        
        try:
            # Create exporter
            exporter = QLibExporter(db_manager)
            
            # Get symbols
            symbols = await exporter.get_symbol_list(network=network)
            
            if symbols:
                export_qlib_instruments(symbols, output_file)
                click.echo(f"✓ Exported {len(symbols)} instruments to {output_file}")
            else:
                click.echo("No symbols found to export.")
                
        finally:
            await db_manager.close()
    
    asyncio.run(_export_instruments())


if __name__ == '__main__':
    qlib_cli()