#!/usr/bin/env python3
"""
QLib Historical Data Integration Example

This script demonstrates how to access and use your collected historical OHLCV data
with QLib for quantitative analysis and predictive modeling.
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional

from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.qlib.exporter import QLibExporter
from gecko_terminal_collector.qlib.integrated_symbol_mapper import IntegratedSymbolMapper

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HistoricalDataQLibIntegration:
    """
    Integration class for accessing historical OHLCV data through QLib methods.
    """
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        self.db_manager = None
        self.qlib_exporter = None
        self.symbol_mapper = None
    
    async def initialize(self):
        """Initialize database connections and QLib components."""
        # Initialize database manager
        self.db_manager = EnhancedSQLAlchemyDatabaseManager(self.config.database)
        await self.db_manager.initialize()
        
        # Initialize symbol mapper
        self.symbol_mapper = IntegratedSymbolMapper(self.db_manager)
        await self.symbol_mapper.populate_cache_from_database()
        
        # Initialize QLib exporter
        self.qlib_exporter = QLibExporter(self.db_manager, self.symbol_mapper)
        
        logger.info("QLib integration initialized successfully")
    
    async def get_available_symbols(self) -> List[str]:
        """
        Get all available symbols from your watchlist.
        
        Returns:
            List of available symbol identifiers
        """
        try:
            symbols = await self.qlib_exporter.get_symbol_list(
                network="solana",
                active_only=True
            )
            
            logger.info(f"Found {len(symbols)} available symbols")
            return symbols
            
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            return []
    
    async def get_historical_data_for_analysis(self,
                                             symbols: Optional[List[str]] = None,
                                             start_date: str = "2025-08-01",
                                             end_date: str = "2025-09-19",
                                             timeframe: str = "1h") -> pd.DataFrame:
        """
        Get historical OHLCV data formatted for quantitative analysis.
        
        Args:
            symbols: List of symbols (None for all watchlist symbols)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            timeframe: Data timeframe (1m, 5m, 15m, 1h, 4h, 12h, 1d)
            
        Returns:
            DataFrame with QLib-compatible OHLCV data
        """
        try:
            logger.info(f"Fetching historical data for timeframe: {timeframe}")
            
            # Export data using QLib exporter
            df = await self.qlib_exporter.export_ohlcv_data(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                include_volume=True,
                normalize_timezone=True,
                fill_missing=False
            )
            
            if df.empty:
                logger.warning("No historical data found for the specified criteria")
                return df
            
            logger.info(f"Retrieved {len(df)} records for {len(df['symbol'].unique())} symbols")
            
            # Add some basic technical indicators
            df = self._add_technical_indicators(df)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return pd.DataFrame()
    
    async def analyze_symbol_performance(self, symbol: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Analyze performance metrics for a specific symbol.
        
        Args:
            symbol: Symbol to analyze
            days_back: Number of days to look back
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Get data for the symbol
            df = await self.get_historical_data_for_analysis(
                symbols=[symbol],
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                timeframe="1h"
            )
            
            if df.empty:
                return {'error': 'No data available for symbol'}
            
            # Calculate performance metrics
            df = df.sort_values('datetime')
            
            # Price metrics
            first_price = df['close'].iloc[0]
            last_price = df['close'].iloc[-1]
            total_return = (last_price - first_price) / first_price * 100
            
            # Volatility (standard deviation of returns)
            df['returns'] = df['close'].pct_change()
            volatility = df['returns'].std() * np.sqrt(24)  # Annualized for hourly data
            
            # Volume metrics
            avg_volume = df['volume'].mean()
            volume_trend = df['volume'].iloc[-7:].mean() / df['volume'].iloc[:-7].mean() if len(df) > 7 else 1.0
            
            # Technical indicators
            current_rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else None
            current_sma_20 = df['sma_20'].iloc[-1] if 'sma_20' in df.columns else None
            
            # Price levels
            high_price = df['high'].max()
            low_price = df['low'].min()
            price_range = (high_price - low_price) / low_price * 100
            
            analysis = {
                'symbol': symbol,
                'analysis_period_days': days_back,
                'data_points': len(df),
                'price_metrics': {
                    'first_price': float(first_price),
                    'last_price': float(last_price),
                    'total_return_pct': float(total_return),
                    'high_price': float(high_price),
                    'low_price': float(low_price),
                    'price_range_pct': float(price_range)
                },
                'risk_metrics': {
                    'volatility_annualized': float(volatility),
                    'max_drawdown_pct': self._calculate_max_drawdown(df['close'])
                },
                'volume_metrics': {
                    'avg_volume_usd': float(avg_volume),
                    'volume_trend': float(volume_trend)
                },
                'technical_indicators': {
                    'current_rsi': float(current_rsi) if current_rsi is not None else None,
                    'current_sma_20': float(current_sma_20) if current_sma_20 is not None else None,
                    'price_vs_sma_20': float((last_price - current_sma_20) / current_sma_20 * 100) if current_sma_20 else None
                }
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing symbol {symbol}: {e}")
            return {'error': str(e)}
    
    async def create_qlib_dataset(self,
                                symbols: Optional[List[str]] = None,
                                start_date: str = "2025-08-01",
                                end_date: str = "2025-09-19",
                                output_dir: str = "./qlib_data") -> Dict[str, Any]:
        """
        Create a QLib-compatible dataset from your historical data.
        
        Args:
            symbols: List of symbols to include
            start_date: Start date for dataset
            end_date: End date for dataset
            output_dir: Directory to save QLib dataset
            
        Returns:
            Dictionary with export results
        """
        try:
            logger.info("Creating QLib dataset from historical data...")
            
            # Export to QLib format
            result = await self.qlib_exporter.export_to_qlib_format(
                output_dir=output_dir,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                timeframe="1h",
                date_field_name="datetime"
            )
            
            if result.get('success'):
                logger.info(f"Successfully created QLib dataset with {result['files_created']} files")
                
                # Create instruments file for QLib
                await self._create_instruments_file(output_dir, symbols)
                
                # Create calendar file for QLib
                await self._create_calendar_file(output_dir, start_date, end_date)
                
                logger.info("QLib dataset creation completed")
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating QLib dataset: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_data_availability_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive data availability report.
        
        Returns:
            Dictionary with availability information
        """
        try:
            logger.info("Generating data availability report...")
            
            # Get availability report from QLib exporter
            report = await self.qlib_exporter.get_data_availability_report(
                symbols=None,  # All symbols
                timeframe="1h"
            )
            
            # Add summary statistics
            available_symbols = [s for s, info in report.items() if info.get('available', False)]
            unavailable_symbols = [s for s, info in report.items() if not info.get('available', False)]
            
            # Calculate date ranges
            date_ranges = []
            for symbol, info in report.items():
                if info.get('available') and 'start_date' in info and 'end_date' in info:
                    date_ranges.append({
                        'symbol': symbol,
                        'start': info['start_date'],
                        'end': info['end_date'],
                        'records': info.get('total_records', 0)
                    })
            
            summary = {
                'total_symbols': len(report),
                'available_symbols': len(available_symbols),
                'unavailable_symbols': len(unavailable_symbols),
                'availability_rate': len(available_symbols) / len(report) * 100 if report else 0,
                'total_records': sum(info.get('total_records', 0) for info in report.values()),
                'date_coverage': {
                    'earliest_date': min([dr['start'] for dr in date_ranges]) if date_ranges else None,
                    'latest_date': max([dr['end'] for dr in date_ranges]) if date_ranges else None
                }
            }
            
            return {
                'summary': summary,
                'detailed_report': report,
                'available_symbols': available_symbols,
                'unavailable_symbols': unavailable_symbols
            }
            
        except Exception as e:
            logger.error(f"Error generating availability report: {e}")
            return {'error': str(e)}
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add basic technical indicators to the DataFrame.
        
        Args:
            df: Input DataFrame with OHLCV data
            
        Returns:
            DataFrame with added technical indicators
        """
        if df.empty:
            return df
        
        try:
            # Sort by symbol and datetime
            df = df.sort_values(['symbol', 'datetime'])
            
            # Calculate indicators for each symbol
            for symbol in df['symbol'].unique():
                mask = df['symbol'] == symbol
                symbol_data = df[mask].copy()
                
                # Simple Moving Averages
                symbol_data['sma_20'] = symbol_data['close'].rolling(window=20).mean()
                symbol_data['sma_50'] = symbol_data['close'].rolling(window=50).mean()
                
                # RSI (Relative Strength Index)
                symbol_data['rsi'] = self._calculate_rsi(symbol_data['close'])
                
                # Bollinger Bands
                sma_20 = symbol_data['close'].rolling(window=20).mean()
                std_20 = symbol_data['close'].rolling(window=20).std()
                symbol_data['bb_upper'] = sma_20 + (std_20 * 2)
                symbol_data['bb_lower'] = sma_20 - (std_20 * 2)
                
                # Volume indicators
                symbol_data['volume_sma_20'] = symbol_data['volume'].rolling(window=20).mean()
                symbol_data['volume_ratio'] = symbol_data['volume'] / symbol_data['volume_sma_20']
                
                # Price change indicators
                symbol_data['price_change'] = symbol_data['close'].pct_change()
                symbol_data['price_change_20'] = symbol_data['close'].pct_change(periods=20)
                
                # Update the main DataFrame
                df.loc[mask, symbol_data.columns] = symbol_data
            
            logger.debug("Added technical indicators to DataFrame")
            return df
            
        except Exception as e:
            logger.error(f"Error adding technical indicators: {e}")
            return df
    
    def _calculate_rsi(self, prices: pd.Series, window: int = 14) -> pd.Series:
        """Calculate RSI (Relative Strength Index)."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_max_drawdown(self, prices: pd.Series) -> float:
        """Calculate maximum drawdown percentage."""
        peak = prices.expanding().max()
        drawdown = (prices - peak) / peak
        return float(drawdown.min() * 100)
    
    async def _create_instruments_file(self, output_dir: str, symbols: Optional[List[str]]):
        """Create QLib instruments file."""
        try:
            instruments_dir = Path(output_dir) / "instruments"
            instruments_dir.mkdir(parents=True, exist_ok=True)
            
            if symbols is None:
                symbols = await self.get_available_symbols()
            
            # Create instruments file
            with open(instruments_dir / "all.txt", 'w') as f:
                for symbol in symbols:
                    f.write(f"{symbol}\n")
            
            logger.debug(f"Created instruments file with {len(symbols)} symbols")
            
        except Exception as e:
            logger.error(f"Error creating instruments file: {e}")
    
    async def _create_calendar_file(self, output_dir: str, start_date: str, end_date: str):
        """Create QLib calendar file for hourly data."""
        try:
            calendars_dir = Path(output_dir) / "calendars"
            calendars_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate hourly timestamps
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # Create hourly calendar (24/7 for crypto)
            calendar_dates = pd.date_range(start=start_dt, end=end_dt, freq='H')
            
            # Write calendar file
            with open(calendars_dir / "1h.txt", 'w') as f:
                for date in calendar_dates:
                    f.write(f"{date.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            logger.debug(f"Created calendar file with {len(calendar_dates)} entries")
            
        except Exception as e:
            logger.error(f"Error creating calendar file: {e}")
    
    async def close(self):
        """Clean up resources."""
        if self.db_manager:
            await self.db_manager.close()

# Example usage functions
async def example_basic_data_access():
    """Example: Basic historical data access."""
    integration = HistoricalDataQLibIntegration()
    
    try:
        await integration.initialize()
        
        print("=== Basic Historical Data Access ===")
        
        # Get available symbols
        symbols = await integration.get_available_symbols()
        print(f"Available symbols: {symbols}")
        
        # Get historical data for all symbols
        df = await integration.get_historical_data_for_analysis(
            symbols=symbols[:2],  # First 2 symbols for demo
            start_date="2025-09-01",
            end_date="2025-09-19",
            timeframe="1h"
        )
        
        if not df.empty:
            print(f"\nData shape: {df.shape}")
            print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
            print(f"Symbols: {df['symbol'].unique()}")
            print("\nSample data:")
            print(df.head())
            
            # Show technical indicators
            if 'rsi' in df.columns:
                print(f"\nTechnical indicators added:")
                print(f"RSI range: {df['rsi'].min():.2f} - {df['rsi'].max():.2f}")
                print(f"SMA 20 available: {'sma_20' in df.columns}")
        
    finally:
        await integration.close()

async def example_symbol_analysis():
    """Example: Detailed symbol analysis."""
    integration = HistoricalDataQLibIntegration()
    
    try:
        await integration.initialize()
        
        print("=== Symbol Performance Analysis ===")
        
        # Get available symbols
        symbols = await integration.get_available_symbols()
        
        if symbols:
            # Analyze first symbol
            symbol = symbols[0]
            analysis = await integration.analyze_symbol_performance(symbol, days_back=14)
            
            print(f"\nAnalysis for {symbol}:")
            print(f"Data points: {analysis.get('data_points', 'N/A')}")
            
            price_metrics = analysis.get('price_metrics', {})
            print(f"Total return: {price_metrics.get('total_return_pct', 0):.2f}%")
            print(f"Price range: {price_metrics.get('price_range_pct', 0):.2f}%")
            
            risk_metrics = analysis.get('risk_metrics', {})
            print(f"Volatility: {risk_metrics.get('volatility_annualized', 0):.2f}")
            print(f"Max drawdown: {risk_metrics.get('max_drawdown_pct', 0):.2f}%")
            
            volume_metrics = analysis.get('volume_metrics', {})
            print(f"Avg volume: ${volume_metrics.get('avg_volume_usd', 0):,.2f}")
            
            tech_indicators = analysis.get('technical_indicators', {})
            if tech_indicators.get('current_rsi'):
                print(f"Current RSI: {tech_indicators['current_rsi']:.2f}")
    
    finally:
        await integration.close()

async def example_qlib_dataset_creation():
    """Example: Create QLib dataset."""
    integration = HistoricalDataQLibIntegration()
    
    try:
        await integration.initialize()
        
        print("=== QLib Dataset Creation ===")
        
        # Create QLib dataset
        result = await integration.create_qlib_dataset(
            symbols=None,  # All symbols
            start_date="2025-09-01",
            end_date="2025-09-19",
            output_dir="./qlib_historical_data"
        )
        
        if result.get('success'):
            print(f"✅ QLib dataset created successfully!")
            print(f"Files created: {result.get('files_created', 0)}")
            print(f"Total records: {result.get('total_records', 0)}")
            print(f"Output directory: ./qlib_historical_data")
            
            # Show how to use with QLib
            print("\n=== Using with QLib ===")
            print("To use this data with QLib:")
            print("```python")
            print("import qlib")
            print("from qlib.data import D")
            print("")
            print("# Initialize QLib")
            print("qlib.init(provider_uri='./qlib_historical_data', region='crypto')")
            print("")
            print("# Load data")
            print("instruments = D.instruments(market='all')")
            print("fields = ['$open', '$high', '$low', '$close', '$volume']")
            print("data = D.features(instruments, fields, freq='1h')")
            print("```")
        else:
            print(f"❌ Failed to create QLib dataset: {result.get('error', 'Unknown error')}")
    
    finally:
        await integration.close()

async def example_data_availability_report():
    """Example: Generate data availability report."""
    integration = HistoricalDataQLibIntegration()
    
    try:
        await integration.initialize()
        
        print("=== Data Availability Report ===")
        
        report = await integration.get_data_availability_report()
        
        if 'summary' in report:
            summary = report['summary']
            print(f"Total symbols: {summary['total_symbols']}")
            print(f"Available symbols: {summary['available_symbols']}")
            print(f"Availability rate: {summary['availability_rate']:.1f}%")
            print(f"Total records: {summary['total_records']:,}")
            
            if summary['date_coverage']['earliest_date']:
                print(f"Date coverage: {summary['date_coverage']['earliest_date']} to {summary['date_coverage']['latest_date']}")
            
            print(f"\nAvailable symbols: {report['available_symbols']}")
            if report['unavailable_symbols']:
                print(f"Unavailable symbols: {report['unavailable_symbols']}")
    
    finally:
        await integration.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example = sys.argv[1]
        
        if example == "basic":
            asyncio.run(example_basic_data_access())
        elif example == "analysis":
            asyncio.run(example_symbol_analysis())
        elif example == "qlib":
            asyncio.run(example_qlib_dataset_creation())
        elif example == "report":
            asyncio.run(example_data_availability_report())
        else:
            print("Unknown example. Use: basic, analysis, qlib, or report")
    else:
        print("QLib Historical Data Integration Examples")
        print("Usage: python qlib_historical_data_example.py <example>")
        print("")
        print("Available examples:")
        print("  basic    - Basic historical data access")
        print("  analysis - Symbol performance analysis")
        print("  qlib     - Create QLib dataset")
        print("  report   - Data availability report")
        print("")
        print("Running all examples...")
        
        # Run all examples
        asyncio.run(example_basic_data_access())
        print("\n" + "="*60 + "\n")
        asyncio.run(example_symbol_analysis())
        print("\n" + "="*60 + "\n")
        asyncio.run(example_data_availability_report())
        print("\n" + "="*60 + "\n")
        asyncio.run(example_qlib_dataset_creation())