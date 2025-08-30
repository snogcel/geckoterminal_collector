"""
QLib-compatible data export interface for GeckoTerminal data.

This module provides data export functionality compatible with QLib's
crypto data collector pattern, enabling seamless integration with
QLib's predictive modeling framework.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import logging
from decimal import Decimal

from gecko_terminal_collector.database.manager import DatabaseManager
from gecko_terminal_collector.models.core import OHLCVRecord, Pool, Token


logger = logging.getLogger(__name__)


class QLibExporter:
    """
    QLib-compatible data exporter for GeckoTerminal data.
    
    This class follows the QLib crypto collector pattern to provide
    data export functionality that integrates seamlessly with QLib's
    data processing and modeling framework.
    """
    
    # QLib standard column names
    QLIB_COLUMNS = {
        'datetime': 'datetime',
        'symbol': 'symbol', 
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume'
    }
    
    # Supported timeframes mapping to QLib frequencies
    TIMEFRAME_MAPPING = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '1h': '1h',
        '4h': '4h',
        '12h': '12h',
        '1d': '1d'
    }
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize QLib exporter with database manager.
        
        Args:
            db_manager: Database manager instance for data access
        """
        self.db_manager = db_manager
        self._symbol_cache = {}
        self._pool_cache = {}
        
    async def get_symbol_list(self, 
                             network: str = "solana",
                             dex_filter: Optional[List[str]] = None,
                             active_only: bool = True) -> List[str]:
        """
        Get available symbols for QLib consumption.
        
        Args:
            network: Network to filter symbols (default: "solana")
            dex_filter: Optional list of DEX IDs to filter by
            active_only: Whether to include only active watchlist symbols
            
        Returns:
            List of available symbol identifiers
        """
        try:
            symbols = []
            
            if active_only:
                # Get symbols from active watchlist
                watchlist_pools = await self.db_manager.get_watchlist_pools()
                for pool_id in watchlist_pools:
                    pool = await self.db_manager.get_pool(pool_id)
                    if pool and (not dex_filter or pool.dex_id in dex_filter):
                        symbol = self._generate_symbol_name(pool)
                        symbols.append(symbol)
                        self._pool_cache[symbol] = pool
            else:
                # Get all pools from specified DEXes
                if dex_filter:
                    for dex_id in dex_filter:
                        pools = await self.db_manager.get_pools_by_dex(dex_id)
                        for pool in pools:
                            symbol = self._generate_symbol_name(pool)
                            symbols.append(symbol)
                            self._pool_cache[symbol] = pool
            
            logger.info(f"Retrieved {len(symbols)} symbols for QLib export")
            return sorted(list(set(symbols)))
            
        except Exception as e:
            logger.error(f"Error retrieving symbol list: {e}")
            return []
    
    async def export_ohlcv_data(self,
                               symbols: Optional[List[str]] = None,
                               start_date: Optional[Union[str, datetime]] = None,
                               end_date: Optional[Union[str, datetime]] = None,
                               timeframe: str = "1h",
                               include_volume: bool = True) -> pd.DataFrame:
        """
        Export OHLCV data in QLib-compatible format.
        
        Args:
            symbols: List of symbols to export (None for all available)
            start_date: Start date for data export
            end_date: End date for data export  
            timeframe: Data timeframe (e.g., '1h', '1d')
            include_volume: Whether to include volume data
            
        Returns:
            DataFrame with QLib-compatible OHLCV data format
        """
        try:
            # Validate timeframe
            if timeframe not in self.TIMEFRAME_MAPPING:
                raise ValueError(f"Unsupported timeframe: {timeframe}. "
                               f"Supported: {list(self.TIMEFRAME_MAPPING.keys())}")
            
            # Parse dates
            start_dt = self._parse_date(start_date) if start_date else None
            end_dt = self._parse_date(end_date) if end_date else None
            
            # Get symbols if not provided
            if symbols is None:
                symbols = await self.get_symbol_list()
            
            if not symbols:
                logger.warning("No symbols available for export")
                return pd.DataFrame()
            
            # Collect data for all symbols
            all_data = []
            
            for symbol in symbols:
                try:
                    pool = await self._get_pool_for_symbol(symbol)
                    if not pool:
                        logger.warning(f"Pool not found for symbol: {symbol}")
                        continue
                    
                    # Get OHLCV data for this pool
                    ohlcv_records = await self.db_manager.get_ohlcv_data(
                        pool_id=pool.id,
                        timeframe=timeframe,
                        start_time=start_dt,
                        end_time=end_dt
                    )
                    
                    if not ohlcv_records:
                        logger.debug(f"No OHLCV data found for symbol: {symbol}")
                        continue
                    
                    # Convert to DataFrame format
                    symbol_data = self._convert_ohlcv_to_qlib_format(
                        ohlcv_records, symbol, include_volume
                    )
                    
                    if not symbol_data.empty:
                        all_data.append(symbol_data)
                        
                except Exception as e:
                    logger.error(f"Error processing symbol {symbol}: {e}")
                    continue
            
            if not all_data:
                logger.warning("No data collected for any symbols")
                return pd.DataFrame()
            
            # Combine all data
            combined_df = pd.concat(all_data, ignore_index=True)
            
            # Sort by datetime and symbol
            combined_df = combined_df.sort_values(['datetime', 'symbol']).reset_index(drop=True)
            
            logger.info(f"Exported {len(combined_df)} records for {len(symbols)} symbols")
            return combined_df
            
        except Exception as e:
            logger.error(f"Error exporting OHLCV data: {e}")
            return pd.DataFrame()
    
    async def get_data_availability_report(self,
                                         symbols: Optional[List[str]] = None,
                                         timeframe: str = "1h") -> Dict[str, Dict[str, Any]]:
        """
        Generate data availability report for QLib consumers.
        
        Args:
            symbols: List of symbols to check (None for all available)
            timeframe: Timeframe to check availability for
            
        Returns:
            Dictionary with availability information per symbol
        """
        try:
            if symbols is None:
                symbols = await self.get_symbol_list()
            
            availability_report = {}
            
            for symbol in symbols:
                try:
                    pool = await self._get_pool_for_symbol(symbol)
                    if not pool:
                        availability_report[symbol] = {
                            'available': False,
                            'reason': 'Pool not found'
                        }
                        continue
                    
                    # Get data range
                    ohlcv_records = await self.db_manager.get_ohlcv_data(
                        pool_id=pool.id,
                        timeframe=timeframe
                    )
                    
                    if not ohlcv_records:
                        availability_report[symbol] = {
                            'available': False,
                            'reason': 'No OHLCV data found'
                        }
                        continue
                    
                    # Calculate availability metrics
                    dates = [record.datetime for record in ohlcv_records]
                    min_date = min(dates)
                    max_date = max(dates)
                    total_records = len(ohlcv_records)
                    
                    # Check data continuity
                    continuity_report = await self.db_manager.check_data_continuity(
                        pool.id, timeframe
                    )
                    
                    availability_report[symbol] = {
                        'available': True,
                        'pool_id': pool.id,
                        'dex_id': pool.dex_id,
                        'start_date': min_date.isoformat(),
                        'end_date': max_date.isoformat(),
                        'total_records': total_records,
                        'data_quality_score': continuity_report.data_quality_score,
                        'total_gaps': continuity_report.total_gaps,
                        'timeframe': timeframe
                    }
                    
                except Exception as e:
                    availability_report[symbol] = {
                        'available': False,
                        'reason': f'Error: {str(e)}'
                    }
            
            return availability_report
            
        except Exception as e:
            logger.error(f"Error generating availability report: {e}")
            return {}
    
    async def export_to_qlib_format(self,
                                   output_dir: Union[str, Path],
                                   symbols: Optional[List[str]] = None,
                                   start_date: Optional[Union[str, datetime]] = None,
                                   end_date: Optional[Union[str, datetime]] = None,
                                   timeframe: str = "1h",
                                   date_field_name: str = "datetime") -> Dict[str, Any]:
        """
        Export data to QLib-compatible CSV files.
        
        Args:
            output_dir: Directory to save CSV files
            symbols: List of symbols to export
            start_date: Start date for export
            end_date: End date for export
            timeframe: Data timeframe
            date_field_name: Name of the date field in output
            
        Returns:
            Export summary statistics
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Get data
            df = await self.export_ohlcv_data(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe
            )
            
            if df.empty:
                return {'success': False, 'message': 'No data to export'}
            
            # Rename datetime column if needed
            if date_field_name != 'datetime':
                df = df.rename(columns={'datetime': date_field_name})
            
            export_stats = {'success': True, 'files_created': 0, 'total_records': 0}
            
            # Export each symbol to separate CSV file (QLib pattern)
            for symbol in df['symbol'].unique():
                symbol_data = df[df['symbol'] == symbol].copy()
                
                # Sort by date
                symbol_data = symbol_data.sort_values(date_field_name)
                
                # Save to CSV
                filename = f"{symbol}.csv"
                file_path = output_path / filename
                symbol_data.to_csv(file_path, index=False)
                
                export_stats['files_created'] += 1
                export_stats['total_records'] += len(symbol_data)
                
                logger.debug(f"Exported {len(symbol_data)} records for {symbol}")
            
            # Create summary file
            summary_path = output_path / "export_summary.json"
            import json
            with open(summary_path, 'w') as f:
                json.dump({
                    'export_date': datetime.utcnow().isoformat(),
                    'timeframe': timeframe,
                    'symbols_exported': len(df['symbol'].unique()),
                    'date_range': {
                        'start': df[date_field_name].min().isoformat(),
                        'end': df[date_field_name].max().isoformat()
                    },
                    **export_stats
                }, f, indent=2)
            
            logger.info(f"Successfully exported {export_stats['files_created']} files "
                       f"with {export_stats['total_records']} total records")
            
            return export_stats
            
        except Exception as e:
            logger.error(f"Error exporting to QLib format: {e}")
            return {'success': False, 'message': str(e)}
    
    def _generate_symbol_name(self, pool: Pool) -> str:
        """
        Generate QLib-compatible symbol name from pool information.
        
        Args:
            pool: Pool object
            
        Returns:
            Symbol name string
        """
        # Format: DEX_POOL_ID (simplified for QLib compatibility)
        # Remove special characters and limit length
        dex_part = pool.dex_id.upper()[:10]
        
        # Extract meaningful part from pool ID
        if '_' in pool.id:
            # Take the part after the last underscore, but keep more context
            parts = pool.id.split('_')
            if len(parts) >= 3:
                pool_part = '_'.join(parts[1:])[:30].upper()  # Keep more of the ID and uppercase
            else:
                pool_part = parts[-1][:20].upper()
        else:
            pool_part = pool.id[:20].upper()
        
        symbol = f"{dex_part}_{pool_part}"
        
        # Ensure valid symbol format (alphanumeric + underscore)
        symbol = ''.join(c if c.isalnum() or c == '_' else '' for c in symbol)
        
        return symbol
    
    def _convert_ohlcv_to_qlib_format(self,
                                     ohlcv_records: List[OHLCVRecord],
                                     symbol: str,
                                     include_volume: bool = True) -> pd.DataFrame:
        """
        Convert OHLCV records to QLib-compatible DataFrame format.
        
        Args:
            ohlcv_records: List of OHLCV records
            symbol: Symbol identifier
            include_volume: Whether to include volume column
            
        Returns:
            QLib-formatted DataFrame
        """
        if not ohlcv_records:
            return pd.DataFrame()
        
        # Convert to list of dictionaries
        data = []
        for record in ohlcv_records:
            row = {
                'datetime': record.datetime,
                'symbol': symbol,
                'open': float(record.open_price),
                'high': float(record.high_price),
                'low': float(record.low_price),
                'close': float(record.close_price)
            }
            
            if include_volume:
                row['volume'] = float(record.volume_usd)
            
            data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Ensure datetime is properly formatted
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        # Sort by datetime
        df = df.sort_values('datetime').reset_index(drop=True)
        
        return df
    
    async def _get_pool_for_symbol(self, symbol: str) -> Optional[Pool]:
        """
        Get pool object for a given symbol.
        
        Args:
            symbol: Symbol identifier
            
        Returns:
            Pool object or None if not found
        """
        # Check cache first
        if symbol in self._pool_cache:
            return self._pool_cache[symbol]
        
        # If not in cache, we need to search by symbol pattern
        # This is a simplified approach - in production you might want
        # to maintain a symbol-to-pool mapping table
        watchlist_pools = await self.db_manager.get_watchlist_pools()
        
        for pool_id in watchlist_pools:
            pool = await self.db_manager.get_pool(pool_id)
            if pool:
                generated_symbol = self._generate_symbol_name(pool)
                if generated_symbol == symbol:
                    self._pool_cache[symbol] = pool
                    return pool
        
        return None
    
    def _parse_date(self, date_input: Union[str, datetime]) -> datetime:
        """
        Parse date input to datetime object.
        
        Args:
            date_input: Date as string or datetime object
            
        Returns:
            Parsed datetime object
        """
        if isinstance(date_input, datetime):
            return date_input
        
        if isinstance(date_input, str):
            try:
                return pd.to_datetime(date_input).to_pydatetime()
            except Exception as e:
                logger.error(f"Error parsing date '{date_input}': {e}")
                raise ValueError(f"Invalid date format: {date_input}")
        
        raise ValueError(f"Unsupported date type: {type(date_input)}")