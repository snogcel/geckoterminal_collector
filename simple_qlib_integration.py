#!/usr/bin/env python3
"""
Simple QLib Integration Example

This script shows the most common ways to access your historical OHLCV data
for quantitative analysis using QLib methods.
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.qlib.exporter import QLibExporter

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_historical_data_simple():
    """
    Simple example: Get historical data for your watchlist symbols.
    """
    print("🚀 Getting Historical Data for Analysis")
    print("=" * 50)
    
    # Initialize components
    config = ConfigManager().load_config()
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    # Create QLib exporter
    qlib_exporter = QLibExporter(db_manager)
    
    try:
        # Get your watchlist symbols
        symbols = await qlib_exporter.get_symbol_list(active_only=True)
        print(f"📊 Found {len(symbols)} symbols in watchlist")
        
        # Get last 7 days of hourly data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        print(f"📅 Fetching data from {start_date.date()} to {end_date.date()}")
        
        # Export historical data
        df = await qlib_exporter.export_ohlcv_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            timeframe="1h",
            include_volume=True
        )
        
        if df.empty:
            print("❌ No data found")
            return
        
        print(f"✅ Retrieved {len(df)} records for {len(df['symbol'].unique())} symbols")
        
        # Show data summary
        print("\n📈 Data Summary:")
        print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
        print(f"Symbols: {list(df['symbol'].unique())}")
        
        # Show sample data
        print("\n📋 Sample Data:")
        print(df[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volume']].head(10))
        
        # Calculate basic statistics
        print("\n📊 Basic Statistics:")
        for symbol in df['symbol'].unique():
            symbol_data = df[df['symbol'] == symbol]
            if len(symbol_data) > 1:
                first_price = symbol_data['close'].iloc[0]
                last_price = symbol_data['close'].iloc[-1]
                return_pct = (last_price - first_price) / first_price * 100
                avg_volume = symbol_data['volume'].mean()
                
                print(f"  {symbol}:")
                print(f"    Return: {return_pct:+.2f}%")
                print(f"    Avg Volume: ${avg_volume:,.0f}")
                print(f"    Records: {len(symbol_data)}")
        
        return df
        
    finally:
        await db_manager.close()

async def create_qlib_dataset_simple():
    """
    Simple example: Create a QLib dataset from your historical data.
    """
    print("\n🔧 Creating QLib Dataset")
    print("=" * 50)
    
    # Initialize components
    config = ConfigManager().load_config()
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    qlib_exporter = QLibExporter(db_manager)
    
    try:
        # Export to QLib format
        result = await qlib_exporter.export_to_qlib_format(
            output_dir="./my_qlib_data",
            symbols=None,  # All watchlist symbols
            start_date="2025-09-01",
            end_date="2025-09-19",
            timeframe="1h"
        )
        
        if result.get('success'):
            print(f"✅ QLib dataset created successfully!")
            print(f"📁 Location: ./my_qlib_data")
            print(f"📄 Files created: {result.get('files_created', 0)}")
            print(f"📊 Total records: {result.get('total_records', 0)}")
            
            print("\n🐍 How to use with QLib:")
            print("""
import qlib
from qlib.data import D

# Initialize QLib with your data
qlib.init(provider_uri='./my_qlib_data', region='crypto')

# Get available instruments (your symbols)
instruments = D.instruments(market='all')
print(f"Available symbols: {instruments}")

# Load OHLCV data
fields = ['$open', '$high', '$low', '$close', '$volume']
data = D.features(instruments, fields, freq='1h')
print(data.head())

# Get data for specific date range
data_recent = D.features(
    instruments, 
    fields, 
    start_time='2025-09-15',
    end_time='2025-09-19',
    freq='1h'
)
            """)
        else:
            print(f"❌ Failed to create dataset: {result.get('error', 'Unknown error')}")
    
    finally:
        await db_manager.close()

async def analyze_symbol_performance_simple():
    """
    Simple example: Analyze performance of your symbols.
    """
    print("\n📈 Symbol Performance Analysis")
    print("=" * 50)
    
    # Initialize components
    config = ConfigManager().load_config()
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    qlib_exporter = QLibExporter(db_manager)
    
    try:
        # Get recent data for analysis
        df = await qlib_exporter.export_ohlcv_data(
            symbols=None,  # All symbols
            start_date="2025-09-15",
            end_date="2025-09-19",
            timeframe="1h"
        )
        
        if df.empty:
            print("❌ No data available for analysis")
            return
        
        print(f"📊 Analyzing {len(df['symbol'].unique())} symbols")
        
        # Calculate performance metrics for each symbol
        performance_results = []
        
        for symbol in df['symbol'].unique():
            symbol_data = df[df['symbol'] == symbol].sort_values('datetime')
            
            if len(symbol_data) < 2:
                continue
            
            # Calculate metrics
            first_price = symbol_data['close'].iloc[0]
            last_price = symbol_data['close'].iloc[-1]
            high_price = symbol_data['high'].max()
            low_price = symbol_data['low'].min()
            
            total_return = (last_price - first_price) / first_price * 100
            max_gain = (high_price - first_price) / first_price * 100
            max_loss = (low_price - first_price) / first_price * 100
            
            # Volatility (standard deviation of returns)
            symbol_data['returns'] = symbol_data['close'].pct_change()
            volatility = symbol_data['returns'].std() * 100
            
            # Average volume
            avg_volume = symbol_data['volume'].mean()
            
            performance_results.append({
                'symbol': symbol,
                'total_return_pct': total_return,
                'max_gain_pct': max_gain,
                'max_loss_pct': max_loss,
                'volatility_pct': volatility,
                'avg_volume_usd': avg_volume,
                'data_points': len(symbol_data)
            })
        
        # Sort by total return
        performance_results.sort(key=lambda x: x['total_return_pct'], reverse=True)
        
        print("\n🏆 Performance Rankings:")
        print(f"{'Symbol':<30} {'Return':<10} {'Max Gain':<10} {'Max Loss':<10} {'Volatility':<12} {'Avg Volume':<15}")
        print("-" * 90)
        
        for result in performance_results:
            print(f"{result['symbol']:<30} "
                  f"{result['total_return_pct']:>+7.2f}% "
                  f"{result['max_gain_pct']:>+7.2f}% "
                  f"{result['max_loss_pct']:>+7.2f}% "
                  f"{result['volatility_pct']:>9.2f}% "
                  f"${result['avg_volume_usd']:>12,.0f}")
        
        # Find best and worst performers
        if performance_results:
            best = performance_results[0]
            worst = performance_results[-1]
            
            print(f"\n🥇 Best Performer: {best['symbol']} ({best['total_return_pct']:+.2f}%)")
            print(f"🥉 Worst Performer: {worst['symbol']} ({worst['total_return_pct']:+.2f}%)")
            
            # High volatility warning
            high_vol_symbols = [r for r in performance_results if r['volatility_pct'] > 10]
            if high_vol_symbols:
                print(f"\n⚠️  High Volatility Symbols (>10%): {[s['symbol'] for s in high_vol_symbols]}")
    
    finally:
        await db_manager.close()

async def check_data_quality_simple():
    """
    Simple example: Check the quality of your historical data.
    """
    print("\n🔍 Data Quality Check")
    print("=" * 50)
    
    # Initialize components
    config = ConfigManager().load_config()
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    qlib_exporter = QLibExporter(db_manager)
    
    try:
        # Get data availability report
        report = await qlib_exporter.get_data_availability_report(
            symbols=None,
            timeframe="1h"
        )
        
        available_symbols = [s for s, info in report.items() if info.get('available', False)]
        unavailable_symbols = [s for s, info in report.items() if not info.get('available', False)]
        
        print(f"✅ Available symbols: {len(available_symbols)}")
        print(f"❌ Unavailable symbols: {len(unavailable_symbols)}")
        
        if available_symbols:
            print("\n📊 Data Coverage:")
            total_records = 0
            earliest_date = None
            latest_date = None
            
            for symbol in available_symbols:
                info = report[symbol]
                records = info.get('total_records', 0)
                total_records += records
                
                start_date = info.get('start_date')
                end_date = info.get('end_date')
                
                if start_date and (earliest_date is None or start_date < earliest_date):
                    earliest_date = start_date
                if end_date and (latest_date is None or end_date > latest_date):
                    latest_date = end_date
                
                print(f"  {symbol}: {records:,} records ({start_date} to {end_date})")
            
            print(f"\n📈 Summary:")
            print(f"  Total records: {total_records:,}")
            print(f"  Date range: {earliest_date} to {latest_date}")
            print(f"  Average records per symbol: {total_records // len(available_symbols):,}")
        
        if unavailable_symbols:
            print(f"\n❌ Symbols with no data: {unavailable_symbols}")
    
    finally:
        await db_manager.close()

async def main():
    """Run all simple examples."""
    print("🎯 QLib Integration Examples for Historical Data")
    print("=" * 60)
    
    try:
        # 1. Get historical data
        await get_historical_data_simple()
        
        # 2. Analyze performance
        await analyze_symbol_performance_simple()
        
        # 3. Check data quality
        await check_data_quality_simple()
        
        # 4. Create QLib dataset
        await create_qlib_dataset_simple()
        
        print("\n🎉 All examples completed successfully!")
        print("\nNext steps:")
        print("1. Use the created QLib dataset in your analysis")
        print("2. Implement trading strategies using QLib")
        print("3. Set up automated data collection for new data")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        logger.error(f"Error in main: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())