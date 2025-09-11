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
from gecko_terminal_collector.database.enhanced_manager import EnhancedDatabaseManager
from gecko_terminal_collector.qlib.integrated_symbol_mapper import IntegratedSymbolMapper
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
    
    def __init__(self, db_manager: DatabaseManager, symbol_mapper: Optional[IntegratedSymbolMapper] = None):
        """
        Initialize QLib exporter with database manager and optional symbol mapper.
        
        Args:
            db_manager: Database manager instance for data access
            symbol_mapper: Optional integrated symbol mapper for enhanced symbol handling
        """
        self.db_manager = db_manager
        self._symbol_cache = {}
        self._pool_cache = {}
        
        # Initialize symbol mapper if enhanced database manager is available
        if isinstance(db_manager, EnhancedDatabaseManager):
            self.symbol_mapper = symbol_mapper or IntegratedSymbolMapper(db_manager)
        else:
            self.symbol_mapper = None
            
        logger.info(f"QLibExporter initialized with {'integrated' if self.symbol_mapper else 'basic'} symbol mapping")
    
    async def initialize_symbol_cache(self, limit: Optional[int] = None) -> int:
        """
        Initialize symbol mapper cache from database.
        
        Args:
            limit: Optional limit on number of symbols to cache
            
        Returns:
            Number of symbols loaded into cache
        """
        if self.symbol_mapper:
            return await self.symbol_mapper.populate_cache_from_database(limit=limit)
        return 0
        
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
                               include_volume: bool = True,
                               normalize_timezone: bool = True,
                               fill_missing: bool = False) -> pd.DataFrame:
        """
        Export OHLCV data in QLib-compatible format with enhanced filtering and normalization.
        
        Args:
            symbols: List of symbols to export (None for all available)
            start_date: Start date for data export (inclusive)
            end_date: End date for data export (inclusive)
            timeframe: Data timeframe (e.g., '1h', '1d')
            include_volume: Whether to include volume data
            normalize_timezone: Whether to normalize timestamps to UTC
            fill_missing: Whether to fill missing data points
            
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
                    
                    # Convert to DataFrame format - use canonical symbol from pool
                    canonical_symbol = self._generate_symbol_name(pool)
                    symbol_data = self._convert_ohlcv_to_qlib_format(
                        ohlcv_records, canonical_symbol, include_volume
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
            
            # Apply date range filtering if specified
            if start_dt or end_dt:
                combined_df = self._apply_date_range_filter(combined_df, start_dt, end_dt)
            
            # Normalize timezone if requested
            if normalize_timezone:
                combined_df = self._normalize_timezone(combined_df)
            
            # Fill missing data if requested
            if fill_missing and not combined_df.empty:
                combined_df = self._fill_missing_data_points(combined_df, timeframe)
            
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
        # Use integrated symbol mapper if available
        if self.symbol_mapper:
            return self.symbol_mapper.generate_symbol(pool)
        
        # Fallback to original logic
        # Use the full pool ID as the symbol to ensure uniqueness and reversibility
        # Keep original case to maintain exact mapping
        symbol = pool.id
        
        # Ensure valid symbol format (alphanumeric + underscore)
        symbol = ''.join(c if c.isalnum() or c == '_' else '_' for c in symbol)
        
        # Remove duplicate underscores
        while '__' in symbol:
            symbol = symbol.replace('__', '_')
        
        # Remove leading/trailing underscores
        symbol = symbol.strip('_')
        
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
        # Use integrated symbol mapper if available
        if self.symbol_mapper:
            return await self.symbol_mapper.lookup_pool_with_fallback(symbol)
        
        # Fallback to original logic
        # Check cache first
        if symbol in self._pool_cache:
            return self._pool_cache[symbol]
        
        # Since our symbol is based on the pool ID, we can reverse-engineer the pool ID
        # The symbol should match the pool ID exactly now
        pool_id = symbol
        
        # Try to get the pool directly
        pool = await self.db_manager.get_pool(pool_id)
        if pool:
            self._pool_cache[symbol] = pool
            return pool
        
        # If direct lookup fails, search through watchlist pools
        watchlist_pools = await self.db_manager.get_watchlist_pools()
        
        for watchlist_pool_id in watchlist_pools:
            pool = await self.db_manager.get_pool(watchlist_pool_id)
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
    
    def _apply_date_range_filter(self, 
                                df: pd.DataFrame, 
                                start_date: Optional[datetime], 
                                end_date: Optional[datetime]) -> pd.DataFrame:
        """
        Apply date range filtering to DataFrame.
        
        Args:
            df: Input DataFrame
            start_date: Start date filter (inclusive)
            end_date: End date filter (inclusive)
            
        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df
        
        filtered_df = df.copy()
        
        if start_date:
            filtered_df = filtered_df[filtered_df['datetime'] >= start_date]
        
        if end_date:
            filtered_df = filtered_df[filtered_df['datetime'] <= end_date]
        
        return filtered_df.reset_index(drop=True)
    
    def _normalize_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize datetime column to UTC timezone for QLib compatibility.
        
        Args:
            df: Input DataFrame with datetime column
            
        Returns:
            DataFrame with normalized timezone
        """
        if df.empty or 'datetime' not in df.columns:
            return df
        
        df_copy = df.copy()
        
        # Ensure datetime column is timezone-aware UTC
        if not pd.api.types.is_datetime64_any_dtype(df_copy['datetime']):
            df_copy['datetime'] = pd.to_datetime(df_copy['datetime'])
        
        # Convert to UTC if not already
        if df_copy['datetime'].dt.tz is None:
            # Assume UTC if no timezone info
            df_copy['datetime'] = df_copy['datetime'].dt.tz_localize('UTC')
        else:
            # Convert to UTC
            df_copy['datetime'] = df_copy['datetime'].dt.tz_convert('UTC')
        
        # Remove timezone info for QLib compatibility (keep as UTC but naive)
        df_copy['datetime'] = df_copy['datetime'].dt.tz_localize(None)
        
        return df_copy
    
    def _fill_missing_data_points(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Fill missing data points in time series for QLib compatibility.
        
        Args:
            df: Input DataFrame
            timeframe: Data timeframe for determining expected intervals
            
        Returns:
            DataFrame with filled missing data points
        """
        if df.empty:
            return df
        
        try:
            from gecko_terminal_collector.qlib.utils import QLibDataProcessor
            return QLibDataProcessor.fill_missing_data(df, method='forward')
        except ImportError:
            logger.warning("QLibDataProcessor not available, skipping missing data fill")
            return df
    
    async def export_ohlcv_data_by_date_range(self,
                                             symbols: Optional[List[str]] = None,
                                             start_date: Union[str, datetime] = None,
                                             end_date: Union[str, datetime] = None,
                                             timeframe: str = "1h",
                                             max_records_per_symbol: Optional[int] = None) -> pd.DataFrame:
        """
        Export OHLCV data with strict date range filtering and record limits.
        
        Args:
            symbols: List of symbols to export
            start_date: Start date (required)
            end_date: End date (required)
            timeframe: Data timeframe
            max_records_per_symbol: Maximum records per symbol (for memory management)
            
        Returns:
            DataFrame with filtered OHLCV data
        """
        if not start_date or not end_date:
            raise ValueError("Both start_date and end_date are required")
        
        # Parse dates
        start_dt = self._parse_date(start_date)
        end_dt = self._parse_date(end_date)
        
        if start_dt >= end_dt:
            raise ValueError("start_date must be before end_date")
        
        # Get symbols if not provided
        if symbols is None:
            symbols = await self.get_symbol_list()
        
        if not symbols:
            logger.warning("No symbols available for export")
            return pd.DataFrame()
        
        # Collect data with limits
        all_data = []
        
        for symbol in symbols:
            try:
                pool = await self._get_pool_for_symbol(symbol)
                if not pool:
                    logger.warning(f"Pool not found for symbol: {symbol}")
                    continue
                
                # Get OHLCV data for this pool with date range
                ohlcv_records = await self.db_manager.get_ohlcv_data(
                    pool_id=pool.id,
                    timeframe=timeframe,
                    start_time=start_dt,
                    end_time=end_dt
                )
                
                if not ohlcv_records:
                    logger.debug(f"No OHLCV data found for symbol: {symbol}")
                    continue
                
                # Apply record limit if specified
                if max_records_per_symbol and len(ohlcv_records) > max_records_per_symbol:
                    # Take the most recent records
                    ohlcv_records = sorted(ohlcv_records, key=lambda x: x.datetime, reverse=True)
                    ohlcv_records = ohlcv_records[:max_records_per_symbol]
                    logger.info(f"Limited {symbol} to {max_records_per_symbol} most recent records")
                
                # Convert to DataFrame format
                symbol_data = self._convert_ohlcv_to_qlib_format(
                    ohlcv_records, symbol, include_volume=True
                )
                
                if not symbol_data.empty:
                    all_data.append(symbol_data)
                    
            except Exception as e:
                logger.error(f"Error processing symbol {symbol}: {e}")
                continue
        
        if not all_data:
            logger.warning("No data collected for any symbols")
            return pd.DataFrame()
        
        # Combine and normalize
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_df = self._normalize_timezone(combined_df)
        combined_df = combined_df.sort_values(['datetime', 'symbol']).reset_index(drop=True)
        
        logger.info(f"Exported {len(combined_df)} records for {len(symbols)} symbols "
                   f"from {start_dt.date()} to {end_dt.date()}")
        
        return combined_df
    
    async def export_symbol_data_with_validation(self,
                                               symbol: str,
                                               start_date: Optional[Union[str, datetime]] = None,
                                               end_date: Optional[Union[str, datetime]] = None,
                                               timeframe: str = "1h",
                                               validate_data: bool = True) -> Dict[str, Any]:
        """
        Export data for a single symbol with comprehensive validation.
        
        Args:
            symbol: Symbol to export
            start_date: Start date for export
            end_date: End date for export
            timeframe: Data timeframe
            validate_data: Whether to perform data validation
            
        Returns:
            Dictionary containing data and validation results
        """
        result = {
            'symbol': symbol,
            'data': pd.DataFrame(),
            'validation': None,
            'metadata': {}
        }
        
        try:
            # Export data for single symbol
            df = await self.export_ohlcv_data(
                symbols=[symbol],
                start_date=start_date,
                end_date=end_date,
                timeframe=timeframe,
                normalize_timezone=True
            )
            
            result['data'] = df
            
            # Add metadata
            if not df.empty:
                result['metadata'] = {
                    'record_count': len(df),
                    'date_range': {
                        'start': df['datetime'].min().isoformat(),
                        'end': df['datetime'].max().isoformat()
                    },
                    'timeframe': timeframe,
                    'has_volume': 'volume' in df.columns
                }
            
            # Validate data if requested
            if validate_data and not df.empty:
                from gecko_terminal_collector.qlib.utils import QLibDataValidator
                result['validation'] = QLibDataValidator.validate_dataframe(df, require_volume=True)
            
            return result
            
        except Exception as e:
            logger.error(f"Error exporting data for symbol {symbol}: {e}")
            result['error'] = str(e)
            return result