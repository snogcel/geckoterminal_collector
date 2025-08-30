"""
Demo script showing how to use the QLib data export functionality.

This example demonstrates:
1. Exporting OHLCV data in QLib-compatible format
2. Generating data availability reports
3. Validating exported data
4. Using the CLI interface
"""

import asyncio
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from gecko_terminal_collector.qlib.exporter import QLibExporter
from gecko_terminal_collector.qlib.utils import (
    QLibDataValidator,
    validate_qlib_export_directory,
    export_qlib_instruments
)
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.config.models import DatabaseConfig


async def demo_qlib_export():
    """Demonstrate QLib export functionality."""
    
    print("🚀 QLib Export Demo")
    print("=" * 50)
    
    # Initialize database connection
    db_config = DatabaseConfig(url="sqlite:///demo_gecko_data.db")
    db_manager = SQLAlchemyDatabaseManager(db_config)
    
    try:
        await db_manager.initialize()
        print("✓ Database connection established")
        
        # Create QLib exporter
        exporter = QLibExporter(db_manager)
        print("✓ QLib exporter initialized")
        
        # 1. Get available symbols
        print("\n📊 Getting available symbols...")
        symbols = await exporter.get_symbol_list(
            network="solana",
            dex_filter=["heaven", "pumpswap"],
            active_only=True
        )
        
        if symbols:
            print(f"✓ Found {len(symbols)} symbols:")
            for symbol in symbols[:5]:  # Show first 5
                print(f"  - {symbol}")
            if len(symbols) > 5:
                print(f"  ... and {len(symbols) - 5} more")
        else:
            print("⚠ No symbols found. Make sure you have data in your database.")
            return
        
        # 2. Generate data availability report
        print("\n📈 Generating data availability report...")
        availability_report = await exporter.get_data_availability_report(
            symbols=symbols[:3],  # Check first 3 symbols
            timeframe="1h"
        )
        
        print("Data Availability Summary:")
        for symbol, info in availability_report.items():
            if info.get('available', False):
                print(f"  ✓ {symbol}: {info['total_records']} records, "
                      f"quality score: {info['data_quality_score']:.2f}")
            else:
                print(f"  ✗ {symbol}: {info.get('reason', 'No data')}")
        
        # 3. Export OHLCV data
        print("\n💾 Exporting OHLCV data...")
        
        # Define date range (last 7 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        df = await exporter.export_ohlcv_data(
            symbols=symbols[:2],  # Export first 2 symbols
            start_date=start_date,
            end_date=end_date,
            timeframe="1h",
            include_volume=True
        )
        
        if not df.empty:
            print(f"✓ Exported {len(df)} records")
            print(f"  Columns: {list(df.columns)}")
            print(f"  Date range: {df['datetime'].min()} to {df['datetime'].max()}")
            print(f"  Symbols: {df['symbol'].unique().tolist()}")
            
            # Show sample data
            print("\nSample data:")
            print(df.head(3).to_string(index=False))
        else:
            print("⚠ No data exported")
        
        # 4. Export to QLib format files
        print("\n📁 Exporting to QLib format files...")
        
        output_dir = Path("qlib_export_demo")
        export_result = await exporter.export_to_qlib_format(
            output_dir=output_dir,
            symbols=symbols[:2],
            start_date=start_date,
            end_date=end_date,
            timeframe="1h"
        )
        
        if export_result['success']:
            print(f"✓ Export completed successfully!")
            print(f"  Files created: {export_result['files_created']}")
            print(f"  Total records: {export_result['total_records']}")
            print(f"  Output directory: {output_dir.absolute()}")
        else:
            print(f"✗ Export failed: {export_result['message']}")
        
        # 5. Validate exported data
        if export_result['success']:
            print("\n🔍 Validating exported data...")
            
            validation_result = validate_qlib_export_directory(output_dir)
            
            if validation_result['is_valid']:
                print("✓ Export directory is valid for QLib")
            else:
                print("⚠ Export directory has validation issues:")
                for error in validation_result['errors']:
                    print(f"  ✗ {error}")
            
            # Show validation statistics
            stats = validation_result['stats']
            print(f"  CSV files: {stats['csv_files']}")
            print(f"  Symbols: {len(stats['symbols'])}")
        
        # 6. Export instruments list
        print("\n📋 Exporting instruments list...")
        instruments_file = output_dir / "instruments.csv"
        export_qlib_instruments(symbols, instruments_file)
        print(f"✓ Instruments list saved to {instruments_file}")
        
        # 7. Demonstrate data validation
        if not df.empty:
            print("\n✅ Validating DataFrame...")
            validation = QLibDataValidator.validate_dataframe(df, require_volume=True)
            
            if validation['is_valid']:
                print("✓ DataFrame is valid for QLib")
            else:
                print("⚠ DataFrame has validation issues:")
                for error in validation['errors']:
                    print(f"  ✗ {error}")
            
            if validation['warnings']:
                print("Warnings:")
                for warning in validation['warnings']:
                    print(f"  ⚠ {warning}")
        
        print("\n🎉 Demo completed successfully!")
        print("\nNext steps:")
        print("1. Use the exported CSV files with QLib")
        print("2. Try the CLI interface: python -m gecko_terminal_collector.qlib.cli --help")
        print("3. Integrate with your QLib workflows")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await db_manager.close()
        print("\n✓ Database connection closed")


def demo_cli_usage():
    """Show CLI usage examples."""
    
    print("\n🖥️  CLI Usage Examples")
    print("=" * 50)
    
    print("1. List available symbols:")
    print("   python -m gecko_terminal_collector.qlib.cli list-symbols")
    
    print("\n2. Export data to CSV files:")
    print("   python -m gecko_terminal_collector.qlib.cli export-data \\")
    print("     --output-dir ./qlib_data \\")
    print("     --start-date 2023-01-01 \\")
    print("     --end-date 2023-01-31 \\")
    print("     --timeframe 1h")
    
    print("\n3. Generate availability report:")
    print("   python -m gecko_terminal_collector.qlib.cli availability-report \\")
    print("     --timeframe 1h \\")
    print("     --output-file availability_report.json")
    
    print("\n4. Validate export directory:")
    print("   python -m gecko_terminal_collector.qlib.cli validate-export ./qlib_data")
    
    print("\n5. Export instruments list:")
    print("   python -m gecko_terminal_collector.qlib.cli export-instruments \\")
    print("     --output-file instruments.csv")


def demo_qlib_integration():
    """Show how to use exported data with QLib."""
    
    print("\n🔗 QLib Integration Example")
    print("=" * 50)
    
    qlib_code = '''
# Example QLib integration code
import qlib
import pandas as pd
from qlib.data import D

# Initialize QLib with your exported data
qlib.init(provider_uri="./qlib_data", region="crypto")

# Get available instruments
instruments = D.instruments(market="crypto")
print(f"Available instruments: {len(instruments)}")

# Load OHLCV data
data = D.features(
    instruments=instruments[:5],  # First 5 instruments
    fields=["$open", "$high", "$low", "$close", "$volume"],
    start_time="2023-01-01",
    end_time="2023-01-31",
    freq="1h"
)

print("Data shape:", data.shape)
print("Sample data:")
print(data.head())

# Use with QLib models
from qlib.contrib.model.gbdt import LGBModel
from qlib.contrib.data.handler import Alpha158

# Create data handler
handler = Alpha158(
    instruments=instruments[:5],
    start_time="2023-01-01",
    end_time="2023-01-31",
    freq="1h"
)

# Train a simple model
model = LGBModel()
model.fit(handler.fetch(col_set="feature"), handler.fetch(col_set="label"))
'''
    
    print("Python code for QLib integration:")
    print(qlib_code)


if __name__ == "__main__":
    print("GeckoTerminal QLib Export Demo")
    print("This demo shows how to export data for QLib integration")
    
    # Run the main demo
    asyncio.run(demo_qlib_export())
    
    # Show CLI examples
    demo_cli_usage()
    
    # Show QLib integration
    demo_qlib_integration()