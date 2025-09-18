"""
Example script demonstrating QLib integration with new pools history data.

This script shows how to:
1. Export new pools data to QLib bin format
2. Use the data with QLib for analysis
3. Perform health checks on the data
4. Set up incremental updates

Usage:
    python examples/qlib_integration_example.py --mode export --start-date 2024-01-01 --end-date 2024-12-31
    python examples/qlib_integration_example.py --mode health-check --qlib-dir ./qlib_data
    python examples/qlib_integration_example.py --mode qlib-demo --qlib-dir ./qlib_data
"""

import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from qlib_integration import QLibBinDataExporter, QLibDataHealthChecker, export_qlib_bin_data_cli
from gecko_terminal_collector.database.manager import DatabaseManager


async def export_example(args):
    """Example of exporting data to QLib bin format."""
    print("🚀 Starting QLib bin export example...")
    
    # Initialize database manager (you'll need to adapt this to your setup)
    # db_manager = DatabaseManager(your_config)
    
    # For demonstration, we'll show the process
    print(f"📅 Export date range: {args.start_date} to {args.end_date}")
    print(f"📁 QLib directory: {args.qlib_dir}")
    print(f"⏱️  Frequency: {args.freq}")
    print(f"🔄 Mode: {args.mode}")
    
    # Example export call (uncomment when you have db_manager):
    """
    result = await export_qlib_bin_data_cli(
        db_manager=db_manager,
        start_date=args.start_date,
        end_date=args.end_date,
        networks=['solana', 'ethereum'] if args.networks else None,
        qlib_dir=args.qlib_dir,
        freq=args.freq,
        min_liquidity=args.min_liquidity,
        min_volume=args.min_volume,
        mode=args.export_mode,
        backup_dir=args.backup_dir
    )
    
    if result['success']:
        print(f"✅ Export completed successfully!")
        print(f"📊 Symbols processed: {result.get('symbols_processed', 0)}")
        print(f"📅 Calendar entries: {result.get('calendar_entries', 0)}")
        
        # Show directory structure
        qlib_path = Path(args.qlib_dir)
        print(f"\n📁 QLib directory structure:")
        print(f"  {qlib_path}/")
        print(f"  ├── calendars/{args.freq}.txt")
        print(f"  ├── instruments/all.txt")
        print(f"  └── features/")
        print(f"      ├── symbol1/")
        print(f"      │   ├── open.{args.freq}.bin")
        print(f"      │   ├── high.{args.freq}.bin")
        print(f"      │   ├── low.{args.freq}.bin")
        print(f"      │   ├── close.{args.freq}.bin")
        print(f"      │   └── volume.{args.freq}.bin")
        print(f"      └── symbol2/...")
        
    else:
        print(f"❌ Export failed: {result.get('error', 'Unknown error')}")
    """
    
    print("\n⚠️  To run actual export, uncomment the code above and provide a DatabaseManager instance")


def health_check_example(args):
    """Example of checking QLib data health."""
    print("🏥 Starting QLib data health check example...")
    
    qlib_dir = Path(args.qlib_dir)
    
    if not qlib_dir.exists():
        print(f"❌ QLib directory does not exist: {qlib_dir}")
        return
    
    print(f"📁 Checking directory: {qlib_dir}")
    
    # Check directory structure
    calendars_dir = qlib_dir / "calendars"
    instruments_dir = qlib_dir / "instruments"
    features_dir = qlib_dir / "features"
    
    print(f"\n📋 Directory structure check:")
    print(f"  📅 Calendars: {'✅' if calendars_dir.exists() else '❌'}")
    print(f"  📊 Instruments: {'✅' if instruments_dir.exists() else '❌'}")
    print(f"  📈 Features: {'✅' if features_dir.exists() else '❌'}")
    
    if features_dir.exists():
        symbols = list(features_dir.iterdir())
        print(f"  🎯 Symbols found: {len(symbols)}")
        
        if symbols:
            # Check first symbol's files
            first_symbol = symbols[0]
            bin_files = list(first_symbol.glob("*.bin"))
            print(f"  📁 Example symbol '{first_symbol.name}': {len(bin_files)} bin files")
            
            for bin_file in bin_files[:5]:  # Show first 5 files
                size_mb = bin_file.stat().st_size / (1024 * 1024)
                print(f"    - {bin_file.name}: {size_mb:.2f} MB")
    
    # Example health check (uncomment when QLib is available):
    """
    checker = QLibDataHealthChecker(
        qlib_dir=str(qlib_dir),
        freq=args.freq,
        large_step_threshold_price=0.5,
        large_step_threshold_volume=3.0
    )
    
    results = checker.run_health_check()
    
    if results['success']:
        print(f"\n✅ Health check completed")
        print(f"📊 Total symbols: {results['total_symbols']}")
        print(f"🏥 Overall health: {results['overall_health']}")
        
        if results['overall_health'] == 'ISSUES_FOUND':
            print("⚠️  Issues found:")
            
            if results['required_columns_check'] is not None:
                print("  - Missing required columns detected")
            
            if results['missing_data_check'] is not None:
                print("  - Missing data detected")
            
            if results['large_step_changes_check'] is not None:
                print("  - Large step changes detected")
    else:
        print(f"❌ Health check failed: {results['error']}")
    """
    
    print("\n⚠️  To run actual health check, uncomment the code above and ensure QLib is installed")


def qlib_demo_example(args):
    """Example of using exported data with QLib."""
    print("📊 QLib usage demonstration...")
    
    qlib_dir = Path(args.qlib_dir)
    
    if not qlib_dir.exists():
        print(f"❌ QLib directory does not exist: {qlib_dir}")
        return
    
    print(f"📁 QLib directory: {qlib_dir}")
    
    # Show how to use with QLib (requires QLib installation)
    print(f"\n📖 QLib usage example:")
    print(f"```python")
    print(f"import qlib")
    print(f"from qlib.data import D")
    print(f"from qlib.constant import REG_US")
    print(f"")
    print(f"# Initialize QLib with your data")
    print(f"provider_uri = '{qlib_dir}'")
    print(f"qlib.init(provider_uri=provider_uri, region=REG_US)")
    print(f"")
    print(f"# Get available instruments")
    print(f"instruments = D.instruments(market='all')")
    print(f"print(f'Available instruments: {{len(instruments)}}')") 
    print(f"")
    print(f"# Load data for analysis")
    print(f"fields = ['$open', '$high', '$low', '$close', '$volume']")
    print(f"data = D.features(instruments[:10], fields, freq='{args.freq}')")
    print(f"print(data.head())")
    print(f"")
    print(f"# Calculate returns")
    print(f"returns = data['$close'].pct_change()")
    print(f"print(f'Average return: {{returns.mean():.4f}}')")
    print(f"```")
    
    # Show example analysis
    print(f"\n📈 Example analysis workflow:")
    print(f"1. Load new pools data from QLib")
    print(f"2. Calculate technical indicators (RSI, MACD, etc.)")
    print(f"3. Identify high-potential pools based on signals")
    print(f"4. Backtest trading strategies")
    print(f"5. Generate performance reports")
    
    # Show incremental update process
    print(f"\n🔄 Incremental update workflow:")
    print(f"1. Export new data with mode='update'")
    print(f"2. QLib automatically handles new dates and symbols")
    print(f"3. Existing analysis continues with updated data")
    print(f"4. No need to re-export historical data")


def show_directory_structure(qlib_dir: Path):
    """Show the QLib directory structure."""
    print(f"\n📁 QLib directory structure: {qlib_dir}")
    
    if not qlib_dir.exists():
        print("  Directory does not exist")
        return
    
    # Show main directories
    for subdir in ['calendars', 'instruments', 'features']:
        subdir_path = qlib_dir / subdir
        if subdir_path.exists():
            print(f"  📂 {subdir}/")
            
            if subdir == 'calendars':
                calendar_files = list(subdir_path.glob("*.txt"))
                for file in calendar_files:
                    print(f"    📅 {file.name}")
            
            elif subdir == 'instruments':
                instrument_files = list(subdir_path.glob("*.txt"))
                for file in instrument_files:
                    print(f"    📊 {file.name}")
            
            elif subdir == 'features':
                symbol_dirs = [d for d in subdir_path.iterdir() if d.is_dir()]
                print(f"    🎯 {len(symbol_dirs)} symbol directories")
                
                if symbol_dirs:
                    # Show first few symbols
                    for symbol_dir in symbol_dirs[:3]:
                        bin_files = list(symbol_dir.glob("*.bin"))
                        print(f"      📈 {symbol_dir.name}/ ({len(bin_files)} bin files)")
                    
                    if len(symbol_dirs) > 3:
                        print(f"      ... and {len(symbol_dirs) - 3} more")
        else:
            print(f"  📂 {subdir}/ (missing)")


async def main():
    parser = argparse.ArgumentParser(description='QLib Integration Example')
    parser.add_argument('--mode', choices=['export', 'health-check', 'qlib-demo', 'structure'], 
                       default='export', help='Example mode to run')
    
    # Export options
    parser.add_argument('--start-date', default='2024-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2024-12-31', help='End date (YYYY-MM-DD)')
    parser.add_argument('--networks', help='Networks to include (comma-separated)')
    parser.add_argument('--qlib-dir', default='./qlib_data', help='QLib data directory')
    parser.add_argument('--freq', default='60min', help='Data frequency')
    parser.add_argument('--min-liquidity', type=float, default=1000, help='Minimum liquidity USD')
    parser.add_argument('--min-volume', type=float, default=100, help='Minimum volume USD')
    parser.add_argument('--export-mode', choices=['all', 'update', 'fix'], default='all', help='Export mode')
    parser.add_argument('--backup-dir', help='Backup directory')
    
    args = parser.parse_args()
    
    print(f"🎯 Running QLib integration example: {args.mode}")
    print(f"=" * 60)
    
    if args.mode == 'export':
        await export_example(args)
    elif args.mode == 'health-check':
        health_check_example(args)
    elif args.mode == 'qlib-demo':
        qlib_demo_example(args)
    elif args.mode == 'structure':
        show_directory_structure(Path(args.qlib_dir))
    
    print(f"\n" + "=" * 60)
    print(f"✅ Example completed!")


if __name__ == "__main__":
    asyncio.run(main())