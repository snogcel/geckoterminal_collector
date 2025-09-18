"""
QLib Integration Module for New Pools History Data

This module provides functionality to export new pools history data
in QLib-compatible bin format for quantitative analysis and model training.
Supports incremental updates and follows QLib-Server data structure requirements.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from pathlib import Path
import json
import shutil
from functools import partial
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

from sqlalchemy import text
from gecko_terminal_collector.database.manager import DatabaseManager

logger = logging.getLogger(__name__)


class QLibBinDataExporter:
    """
    Export new pools history data in QLib-compatible bin format.
    
    This class follows QLib's bin file structure requirements:
    - Binary files with date_index + feature data
    - Proper calendar alignment
    - Incremental update support
    - Symbol-based directory structure
    """
    
    # QLib constants
    CALENDARS_DIR_NAME = "calendars"
    FEATURES_DIR_NAME = "features"
    INSTRUMENTS_DIR_NAME = "instruments"
    DUMP_FILE_SUFFIX = ".bin"
    INSTRUMENTS_SEP = "\t"
    INSTRUMENTS_FILE_NAME = "all.txt"
    INSTRUMENTS_START_FIELD = "start_datetime"
    INSTRUMENTS_END_FIELD = "end_datetime"
    
    def __init__(
        self, 
        db_manager: DatabaseManager, 
        qlib_dir: str = "./qlib_data",
        freq: str = "60min",
        max_workers: int = 16,
        backup_dir: str = None
    ):
        self.db_manager = db_manager
        self.qlib_dir = Path(qlib_dir).expanduser()
        self.freq = freq
        self.max_workers = max_workers
        
        # Create backup if specified
        if backup_dir:
            self.backup_dir = Path(backup_dir).expanduser()
            self._backup_qlib_dir()
        
        # Initialize directories
        self._calendars_dir = self.qlib_dir.joinpath(self.CALENDARS_DIR_NAME)
        self._features_dir = self.qlib_dir.joinpath(self.FEATURES_DIR_NAME)
        self._instruments_dir = self.qlib_dir.joinpath(self.INSTRUMENTS_DIR_NAME)
        
        # QLib feature mapping (database field -> qlib field)
        self.feature_mapping = {
            'open_price_usd': 'open',
            'high_price_usd': 'high', 
            'low_price_usd': 'low',
            'close_price_usd': 'close',
            'volume_usd_h24': 'volume',
            'reserve_in_usd': 'liquidity',
            'market_cap_usd': 'market_cap',
            'fdv_usd': 'fdv',
            'relative_strength_index': 'rsi',
            'moving_average_convergence': 'macd',
            'volatility_score': 'volatility',
            'activity_score': 'activity',
            'signal_score': 'signal',
            'transactions_h24_buys': 'buy_count',
            'transactions_h24_sells': 'sell_count',
            'price_change_percentage_h1': 'return_1h',
            'price_change_percentage_h24': 'return_24h'
        }
        
        # Date format for QLib
        self.calendar_format = "%Y-%m-%d %H:%M:%S" if freq != "day" else "%Y-%m-%d"
    
    def _backup_qlib_dir(self):
        """Backup existing QLib directory."""
        if self.qlib_dir.exists():
            shutil.copytree(str(self.qlib_dir.resolve()), str(self.backup_dir.resolve()))
            logger.info(f"Backed up QLib directory to {self.backup_dir}")
    
    def _format_datetime(self, datetime_obj: pd.Timestamp) -> str:
        """Format datetime for QLib calendar."""
        return datetime_obj.strftime(self.calendar_format)
    
    async def export_bin_data(
        self,
        start_date: datetime,
        end_date: datetime,
        networks: List[str] = None,
        min_liquidity_usd: float = 1000,
        min_volume_usd: float = 100,
        export_name: str = None,
        mode: str = "all"  # "all", "update", "fix"
    ) -> Dict[str, Any]:
        """
        Export data in QLib bin format for QLib-Server integration.
        
        Args:
            start_date: Start date for data export
            end_date: End date for data export
            networks: List of networks to include (None for all)
            min_liquidity_usd: Minimum liquidity threshold
            min_volume_usd: Minimum volume threshold
            export_name: Name for the export (auto-generated if None)
            mode: Export mode - "all" (full export), "update" (incremental), "fix" (repair)
            
        Returns:
            Dictionary with export metadata
        """
        try:
            if not export_name:
                export_name = f"qlib_bin_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            
            logger.info(f"Starting QLib bin data export: {export_name} (mode: {mode})")
            
            # Get raw data from database
            raw_data = await self._fetch_history_data(
                start_date, end_date, networks, min_liquidity_usd, min_volume_usd
            )
            
            if raw_data.empty:
                logger.warning("No data found for specified criteria")
                return {'success': False, 'error': 'No data found'}
            
            logger.info(f"Fetched {len(raw_data)} records for {raw_data['pool_id'].nunique()} unique pools")
            
            # Process data for QLib bin format
            processed_data = self._process_for_qlib_bin(raw_data)
            
            # Export based on mode
            if mode == "all":
                result = await self._export_all_bin_data(processed_data, export_name)
            elif mode == "update":
                result = await self._export_update_bin_data(processed_data, export_name)
            elif mode == "fix":
                result = await self._export_fix_bin_data(processed_data, export_name)
            else:
                raise ValueError(f"Unknown export mode: {mode}")
            
            # Record export metadata
            export_metadata = {
                'success': result['success'],
                'export_name': export_name,
                'mode': mode,
                'start_date': start_date,
                'end_date': end_date,
                'total_records': len(raw_data),
                'unique_pools': raw_data['pool_id'].nunique(),
                'networks': networks or 'all',
                'qlib_dir': str(self.qlib_dir),
                'freq': self.freq,
                'created_at': datetime.now(),
                **result
            }
            
            await self._record_export_metadata(export_metadata)
            
            logger.info(f"QLib bin export completed: {export_name}")
            return export_metadata
            
        except Exception as e:
            logger.error(f"Error exporting QLib bin data: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _fetch_history_data(
        self,
        start_date: datetime,
        end_date: datetime,
        networks: List[str] = None,
        min_liquidity_usd: float = 1000,
        min_volume_usd: float = 100
    ) -> pd.DataFrame:
        """Fetch history data from database."""
        try:
            # Build query
            query = """
            SELECT 
                pool_id,
                timestamp,
                datetime,
                collection_interval,
                network_id,
                dex_id,
                qlib_symbol,
                
                -- Price data
                open_price_usd,
                high_price_usd,
                low_price_usd,
                close_price_usd,
                
                -- Volume and liquidity
                volume_usd_h24,
                volume_usd_h1,
                reserve_in_usd,
                liquidity_depth_usd,
                
                -- Market metrics
                market_cap_usd,
                fdv_usd,
                
                -- Price changes
                price_change_percentage_h1,
                price_change_percentage_h24,
                price_change_percentage_interval,
                
                -- Trading activity
                transactions_h24_buys,
                transactions_h24_sells,
                transactions_h1_buys,
                transactions_h1_sells,
                buy_sell_ratio_h24,
                
                -- Technical indicators
                relative_strength_index,
                moving_average_convergence,
                trend_strength,
                volatility_score,
                
                -- Signal analysis
                signal_score,
                activity_score,
                momentum_indicator,
                
                -- Pool characteristics
                pool_age_hours,
                is_new_pool,
                data_quality_score,
                
                -- QLib features
                qlib_features_json
                
            FROM new_pools_history_enhanced
            WHERE datetime >= :start_date 
                AND datetime <= :end_date
                AND reserve_in_usd >= :min_liquidity
                AND volume_usd_h24 >= :min_volume
                AND data_quality_score >= 50
            """
            
            params = {
                'start_date': start_date,
                'end_date': end_date,
                'min_liquidity': min_liquidity_usd,
                'min_volume': min_volume_usd
            }
            
            # Add network filter if specified
            if networks:
                query += " AND network_id = ANY(:networks)"
                params['networks'] = networks
            
            query += " ORDER BY pool_id, datetime"
            
            # Execute query
            with self.db_manager.connection.get_session() as session:
                result = session.execute(text(query), params)
                data = result.fetchall()
                
                if not data:
                    return pd.DataFrame()
                
                # Convert to DataFrame
                columns = result.keys()
                df = pd.DataFrame(data, columns=columns)
                
                return df
                
        except Exception as e:
            logger.error(f"Error fetching history data: {e}")
            return pd.DataFrame()
    
    def _process_for_qlib_bin(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Process raw data for QLib bin format."""
        try:
            df = raw_data.copy()
            
            # Convert datetime column to proper datetime type
            df['datetime'] = pd.to_datetime(df['datetime'])
            
            # Sort by pool_id and datetime
            df.sort_values(['pool_id', 'datetime'], inplace=True)
            
            # Handle missing values - forward fill then zero fill
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            df[numeric_columns] = df.groupby('pool_id')[numeric_columns].ffill().fillna(0)
            
            # Ensure we have required OHLCV columns with valid data
            required_columns = ['open_price_usd', 'high_price_usd', 'low_price_usd', 'close_price_usd', 'volume_usd_h24']
            for col in required_columns:
                if col not in df.columns:
                    logger.warning(f"Missing required column: {col}")
                    df[col] = 0.0
                else:
                    # Replace any remaining NaN or inf values
                    df[col] = df[col].replace([np.inf, -np.inf], np.nan).fillna(0.0)
            
            # Create QLib-compatible symbol from qlib_symbol or pool_id
            df['symbol'] = df['qlib_symbol'].fillna(df['pool_id'])
            
            # Ensure symbols are valid (alphanumeric + underscore)
            df['symbol'] = df['symbol'].str.replace(r'[^a-zA-Z0-9_]', '_', regex=True)
            
            # Add date field for QLib compatibility
            df['date'] = df['datetime']
            
            return df
            
        except Exception as e:
            logger.error(f"Error processing data for QLib bin: {e}")
            return pd.DataFrame()
    
    async def _export_all_bin_data(self, data: pd.DataFrame, export_name: str) -> Dict[str, Any]:
        """Export all data in QLib bin format (full export)."""
        try:
            logger.info("Starting full bin data export...")
            
            # Get all unique dates for calendar
            all_dates = sorted(data['datetime'].unique())
            calendar_list = [pd.Timestamp(dt) for dt in all_dates]
            
            # Save calendar
            self._save_calendar(calendar_list)
            
            # Prepare instruments data
            instruments_data = self._prepare_instruments_data(data)
            self._save_instruments(instruments_data)
            
            # Export features for each symbol
            symbols_processed = 0
            errors = []
            
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                
                for symbol, symbol_data in data.groupby('symbol'):
                    future = executor.submit(
                        self._dump_symbol_bin_data, 
                        symbol, 
                        symbol_data, 
                        calendar_list,
                        "all"
                    )
                    futures[future] = symbol
                
                with tqdm(total=len(futures), desc="Exporting symbols") as pbar:
                    for future in as_completed(futures):
                        try:
                            future.result()
                            symbols_processed += 1
                        except Exception as e:
                            symbol = futures[future]
                            error_msg = f"Error processing symbol {symbol}: {e}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                        pbar.update(1)
            
            return {
                'success': len(errors) == 0,
                'symbols_processed': symbols_processed,
                'calendar_entries': len(calendar_list),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error in full bin export: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _export_update_bin_data(self, data: pd.DataFrame, export_name: str) -> Dict[str, Any]:
        """Export incremental updates to existing QLib bin data."""
        try:
            logger.info("Starting incremental bin data export...")
            
            # Load existing calendar
            existing_calendar = self._load_existing_calendar()
            if not existing_calendar:
                logger.warning("No existing calendar found, falling back to full export")
                return await self._export_all_bin_data(data, export_name)
            
            # Get new dates that aren't in existing calendar
            all_dates = sorted(data['datetime'].unique())
            new_dates = [dt for dt in all_dates if pd.Timestamp(dt) not in existing_calendar]
            
            if not new_dates:
                logger.info("No new dates to add")
                return {'success': True, 'symbols_processed': 0, 'new_dates': 0}
            
            # Update calendar
            updated_calendar = existing_calendar + [pd.Timestamp(dt) for dt in new_dates]
            updated_calendar = sorted(set(updated_calendar))
            self._save_calendar(updated_calendar)
            
            # Load existing instruments
            existing_instruments = self._load_existing_instruments()
            
            # Update instruments with new symbols and date ranges
            updated_instruments = self._update_instruments_data(data, existing_instruments)
            self._save_instruments(updated_instruments)
            
            # Export only new data for each symbol
            symbols_processed = 0
            errors = []
            
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                
                for symbol, symbol_data in data.groupby('symbol'):
                    # Filter to only new dates for this symbol
                    new_symbol_data = symbol_data[symbol_data['datetime'].isin(new_dates)]
                    if not new_symbol_data.empty:
                        future = executor.submit(
                            self._dump_symbol_bin_data, 
                            symbol, 
                            new_symbol_data, 
                            updated_calendar,
                            "update"
                        )
                        futures[future] = symbol
                
                with tqdm(total=len(futures), desc="Updating symbols") as pbar:
                    for future in as_completed(futures):
                        try:
                            future.result()
                            symbols_processed += 1
                        except Exception as e:
                            symbol = futures[future]
                            error_msg = f"Error updating symbol {symbol}: {e}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                        pbar.update(1)
            
            return {
                'success': len(errors) == 0,
                'symbols_processed': symbols_processed,
                'new_dates': len(new_dates),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error in incremental bin export: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _export_fix_bin_data(self, data: pd.DataFrame, export_name: str) -> Dict[str, Any]:
        """Fix/repair existing QLib bin data."""
        try:
            logger.info("Starting bin data repair...")
            
            # Load existing calendar and instruments
            existing_calendar = self._load_existing_calendar()
            existing_instruments = self._load_existing_instruments()
            
            if not existing_calendar or not existing_instruments:
                logger.warning("Missing existing data, falling back to full export")
                return await self._export_all_bin_data(data, export_name)
            
            # Update instruments with any new symbols
            updated_instruments = self._update_instruments_data(data, existing_instruments)
            self._save_instruments(updated_instruments)
            
            # Process only new symbols that aren't in existing instruments
            existing_symbols = set(existing_instruments['symbol']) if 'symbol' in existing_instruments.columns else set()
            new_symbols = set(data['symbol']) - existing_symbols
            
            symbols_processed = 0
            errors = []
            
            if new_symbols:
                logger.info(f"Processing {len(new_symbols)} new symbols")
                
                with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {}
                    
                    for symbol in new_symbols:
                        symbol_data = data[data['symbol'] == symbol]
                        future = executor.submit(
                            self._dump_symbol_bin_data, 
                            symbol, 
                            symbol_data, 
                            existing_calendar,
                            "all"  # New symbols get full treatment
                        )
                        futures[future] = symbol
                    
                    with tqdm(total=len(futures), desc="Adding new symbols") as pbar:
                        for future in as_completed(futures):
                            try:
                                future.result()
                                symbols_processed += 1
                            except Exception as e:
                                symbol = futures[future]
                                error_msg = f"Error adding symbol {symbol}: {e}"
                                logger.error(error_msg)
                                errors.append(error_msg)
                            pbar.update(1)
            
            return {
                'success': len(errors) == 0,
                'symbols_processed': symbols_processed,
                'new_symbols': len(new_symbols),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error in bin data repair: {e}")
            return {'success': False, 'error': str(e)}
    
    def _dump_symbol_bin_data(
        self, 
        symbol: str, 
        symbol_data: pd.DataFrame, 
        calendar_list: List[pd.Timestamp],
        mode: str = "all"
    ):
        """Dump binary data for a single symbol."""
        try:
            if symbol_data.empty:
                logger.warning(f"No data for symbol {symbol}")
                return
            
            # Create symbol directory
            symbol_dir = self._features_dir / symbol.lower()
            symbol_dir.mkdir(parents=True, exist_ok=True)
            
            # Prepare data with calendar alignment
            aligned_data = self._align_data_with_calendar(symbol_data, calendar_list)
            
            if aligned_data.empty:
                logger.warning(f"No aligned data for symbol {symbol}")
                return
            
            # Get date index for this symbol's data
            date_index = self._get_date_index(aligned_data, calendar_list)
            
            # Export each feature as a bin file
            for db_field, qlib_field in self.feature_mapping.items():
                if db_field in aligned_data.columns:
                    self._write_feature_bin_file(
                        symbol_dir, 
                        qlib_field, 
                        aligned_data[db_field], 
                        date_index,
                        mode
                    )
            
        except Exception as e:
            logger.error(f"Error dumping bin data for symbol {symbol}: {e}")
            raise
    
    def _align_data_with_calendar(self, data: pd.DataFrame, calendar_list: List[pd.Timestamp]) -> pd.DataFrame:
        """Align symbol data with QLib calendar."""
        try:
            # Create calendar DataFrame
            calendar_df = pd.DataFrame({'datetime': calendar_list})
            calendar_df['datetime'] = pd.to_datetime(calendar_df['datetime'])
            
            # Filter calendar to data range
            data_start = data['datetime'].min()
            data_end = data['datetime'].max()
            
            filtered_calendar = calendar_df[
                (calendar_df['datetime'] >= data_start) & 
                (calendar_df['datetime'] <= data_end)
            ].copy()
            
            # Set datetime as index for both
            filtered_calendar.set_index('datetime', inplace=True)
            data_indexed = data.set_index('datetime')
            
            # Reindex data to calendar (forward fill missing values)
            aligned_data = data_indexed.reindex(filtered_calendar.index, method='ffill')
            
            return aligned_data
            
        except Exception as e:
            logger.error(f"Error aligning data with calendar: {e}")
            return pd.DataFrame()
    
    def _get_date_index(self, aligned_data: pd.DataFrame, calendar_list: List[pd.Timestamp]) -> int:
        """Get the starting date index in the calendar."""
        try:
            start_date = aligned_data.index.min()
            return calendar_list.index(start_date)
        except ValueError:
            logger.error(f"Start date {start_date} not found in calendar")
            return 0
    
    def _write_feature_bin_file(
        self, 
        symbol_dir: Path, 
        feature_name: str, 
        feature_data: pd.Series, 
        date_index: int,
        mode: str
    ):
        """Write feature data to QLib bin file."""
        try:
            bin_file = symbol_dir / f"{feature_name.lower()}.{self.freq}{self.DUMP_FILE_SUFFIX}"
            
            # Convert data to float32 array
            data_array = feature_data.fillna(0.0).astype(np.float32).values
            
            if mode == "update" and bin_file.exists():
                # Append mode - just add the new data
                with bin_file.open("ab") as fp:
                    data_array.astype("<f").tofile(fp)
            else:
                # Full mode - include date index + data
                full_array = np.hstack([date_index, data_array])
                full_array.astype("<f").tofile(str(bin_file))
            
        except Exception as e:
            logger.error(f"Error writing bin file for {feature_name}: {e}")
            raise
    
    def _save_calendar(self, calendar_list: List[pd.Timestamp]):
        """Save QLib calendar file."""
        try:
            self._calendars_dir.mkdir(parents=True, exist_ok=True)
            calendar_file = self._calendars_dir / f"{self.freq}.txt"
            
            calendar_strings = [self._format_datetime(dt) for dt in calendar_list]
            
            with calendar_file.open('w', encoding='utf-8') as f:
                for date_str in calendar_strings:
                    f.write(f"{date_str}\n")
            
            logger.info(f"Saved calendar with {len(calendar_strings)} entries")
            
        except Exception as e:
            logger.error(f"Error saving calendar: {e}")
            raise
    
    def _prepare_instruments_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Prepare instruments data for QLib."""
        try:
            instruments_list = []
            
            for symbol, symbol_data in data.groupby('symbol'):
                start_date = symbol_data['datetime'].min()
                end_date = symbol_data['datetime'].max()
                
                instruments_list.append({
                    'symbol': symbol.upper(),
                    self.INSTRUMENTS_START_FIELD: self._format_datetime(pd.Timestamp(start_date)),
                    self.INSTRUMENTS_END_FIELD: self._format_datetime(pd.Timestamp(end_date))
                })
            
            return pd.DataFrame(instruments_list)
            
        except Exception as e:
            logger.error(f"Error preparing instruments data: {e}")
            return pd.DataFrame()
    
    def _save_instruments(self, instruments_df: pd.DataFrame):
        """Save QLib instruments file."""
        try:
            self._instruments_dir.mkdir(parents=True, exist_ok=True)
            instruments_file = self._instruments_dir / self.INSTRUMENTS_FILE_NAME
            
            instruments_df.to_csv(
                instruments_file, 
                sep=self.INSTRUMENTS_SEP, 
                header=False, 
                index=False,
                encoding='utf-8'
            )
            
            logger.info(f"Saved instruments file with {len(instruments_df)} entries")
            
        except Exception as e:
            logger.error(f"Error saving instruments: {e}")
            raise
    
    def _load_existing_calendar(self) -> List[pd.Timestamp]:
        """Load existing QLib calendar."""
        try:
            calendar_file = self._calendars_dir / f"{self.freq}.txt"
            if not calendar_file.exists():
                return []
            
            with calendar_file.open('r', encoding='utf-8') as f:
                dates = [pd.Timestamp(line.strip()) for line in f if line.strip()]
            
            return sorted(dates)
            
        except Exception as e:
            logger.error(f"Error loading existing calendar: {e}")
            return []
    
    def _load_existing_instruments(self) -> pd.DataFrame:
        """Load existing QLib instruments."""
        try:
            instruments_file = self._instruments_dir / self.INSTRUMENTS_FILE_NAME
            if not instruments_file.exists():
                return pd.DataFrame()
            
            df = pd.read_csv(
                instruments_file,
                sep=self.INSTRUMENTS_SEP,
                names=['symbol', self.INSTRUMENTS_START_FIELD, self.INSTRUMENTS_END_FIELD],
                encoding='utf-8'
            )
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading existing instruments: {e}")
            return pd.DataFrame()
    
    def _update_instruments_data(self, new_data: pd.DataFrame, existing_instruments: pd.DataFrame) -> pd.DataFrame:
        """Update instruments data with new symbols and date ranges."""
        try:
            # Prepare new instruments data
            new_instruments = self._prepare_instruments_data(new_data)
            
            if existing_instruments.empty:
                return new_instruments
            
            # Merge with existing, updating date ranges for existing symbols
            existing_dict = existing_instruments.set_index('symbol').to_dict('index')
            
            for _, row in new_instruments.iterrows():
                symbol = row['symbol']
                start_date = row[self.INSTRUMENTS_START_FIELD]
                end_date = row[self.INSTRUMENTS_END_FIELD]
                
                if symbol in existing_dict:
                    # Update existing symbol's date range
                    existing_start = existing_dict[symbol][self.INSTRUMENTS_START_FIELD]
                    existing_end = existing_dict[symbol][self.INSTRUMENTS_END_FIELD]
                    
                    # Extend date range if necessary
                    if pd.Timestamp(start_date) < pd.Timestamp(existing_start):
                        existing_dict[symbol][self.INSTRUMENTS_START_FIELD] = start_date
                    if pd.Timestamp(end_date) > pd.Timestamp(existing_end):
                        existing_dict[symbol][self.INSTRUMENTS_END_FIELD] = end_date
                else:
                    # Add new symbol
                    existing_dict[symbol] = {
                        self.INSTRUMENTS_START_FIELD: start_date,
                        self.INSTRUMENTS_END_FIELD: end_date
                    }
            
            # Convert back to DataFrame
            updated_df = pd.DataFrame.from_dict(existing_dict, orient='index')
            updated_df.index.name = 'symbol'
            updated_df = updated_df.reset_index()
            
            return updated_df
            
        except Exception as e:
            logger.error(f"Error updating instruments data: {e}")
            return existing_instruments
    
    def _generate_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate additional features for ML models."""
        try:
            df = data.copy()
            
            # Technical indicators
            for pool_id in df['pool_id'].unique():
                pool_mask = df['pool_id'] == pool_id
                pool_data = df[pool_mask].copy()
                
                if len(pool_data) < 10:  # Need minimum data points
                    continue
                
                # Moving averages
                if 'close_price_usd' in pool_data.columns:
                    pool_data['ma_5'] = pool_data['close_price_usd'].rolling(5).mean()
                    pool_data['ma_20'] = pool_data['close_price_usd'].rolling(20).mean()
                    pool_data['ma_ratio'] = pool_data['ma_5'] / pool_data['ma_20']
                
                # Volume indicators
                if 'volume_usd_h24' in pool_data.columns:
                    pool_data['volume_ma_5'] = pool_data['volume_usd_h24'].rolling(5).mean()
                    pool_data['volume_ratio'] = pool_data['volume_usd_h24'] / pool_data['volume_ma_5']
                
                # Volatility
                if 'close_price_usd_return' in pool_data.columns:
                    pool_data['volatility_5'] = pool_data['close_price_usd_return'].rolling(5).std()
                    pool_data['volatility_20'] = pool_data['close_price_usd_return'].rolling(20).std()
                
                # Update main dataframe
                df.loc[pool_mask, pool_data.columns] = pool_data
            
            # Cross-sectional features
            df['volume_rank'] = df.groupby(df.index)['volume_usd_h24'].rank(pct=True)
            df['liquidity_rank'] = df.groupby(df.index)['reserve_in_usd'].rank(pct=True)
            df['signal_rank'] = df.groupby(df.index)['signal_score'].rank(pct=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error generating features: {e}")
            return data
    
    def _create_labels(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create target labels for supervised learning."""
        try:
            df = data.copy()
            
            # Forward returns as labels
            for pool_id in df['pool_id'].unique():
                pool_mask = df['pool_id'] == pool_id
                pool_data = df[pool_mask].copy()
                
                if 'close_price_usd' in pool_data.columns:
                    # Calculate forward returns
                    pool_data['label_return_1h'] = pool_data['close_price_usd'].pct_change(periods=-1)
                    pool_data['label_return_4h'] = pool_data['close_price_usd'].pct_change(periods=-4)
                    pool_data['label_return_24h'] = pool_data['close_price_usd'].pct_change(periods=-24)
                    
                    # Binary classification labels
                    pool_data['label_up_1h'] = (pool_data['label_return_1h'] > 0).astype(int)
                    pool_data['label_up_4h'] = (pool_data['label_return_4h'] > 0).astype(int)
                    pool_data['label_up_24h'] = (pool_data['label_return_24h'] > 0).astype(int)
                    
                    # Volatility labels
                    pool_data['label_high_vol'] = (pool_data['label_return_1h'].abs() > 0.05).astype(int)
                
                # Volume surge labels
                if 'volume_usd_h24' in pool_data.columns:
                    volume_ma = pool_data['volume_usd_h24'].rolling(24).mean()
                    pool_data['label_volume_surge'] = (pool_data['volume_usd_h24'] > volume_ma * 2).astype(int)
                
                # Update main dataframe
                df.loc[pool_mask, pool_data.columns] = pool_data
            
            return df
            
        except Exception as e:
            logger.error(f"Error creating labels: {e}")
            return data
    
    def _split_datasets(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Split data into train/validation/test sets."""
        try:
            # Sort by datetime
            df = data.sort_index()
            
            # Time-based split (70% train, 15% validation, 15% test)
            total_time = df.index.max() - df.index.min()
            train_end = df.index.min() + total_time * 0.7
            val_end = df.index.min() + total_time * 0.85
            
            train_data = df[df.index <= train_end]
            val_data = df[(df.index > train_end) & (df.index <= val_end)]
            test_data = df[df.index > val_end]
            
            logger.info(f"Dataset split - Train: {len(train_data)}, Val: {len(val_data)}, Test: {len(test_data)}")
            
            return {
                'train': train_data,
                'validation': val_data,
                'test': test_data,
                'full': df
            }
            
        except Exception as e:
            logger.error(f"Error splitting datasets: {e}")
            return {'full': data}
    
    async def _save_datasets(self, datasets: Dict[str, pd.DataFrame], export_name: str) -> Dict[str, str]:
        """Save datasets to files."""
        try:
            export_paths = {}
            
            for split_name, data in datasets.items():
                if data.empty:
                    continue
                
                # Save as parquet for efficiency
                file_path = self.output_dir / f"{export_name}_{split_name}.parquet"
                data.to_parquet(file_path)
                export_paths[split_name] = str(file_path)
                
                # Also save as CSV for compatibility
                csv_path = self.output_dir / f"{export_name}_{split_name}.csv"
                data.to_csv(csv_path)
                export_paths[f"{split_name}_csv"] = str(csv_path)
                
                logger.info(f"Saved {split_name} dataset: {len(data)} records to {file_path}")
            
            return export_paths
            
        except Exception as e:
            logger.error(f"Error saving datasets: {e}")
            return {}
    
    def _create_qlib_config(self, datasets: Dict[str, pd.DataFrame], export_name: str) -> Dict:
        """Create QLib configuration for the exported data."""
        try:
            # Get feature columns (exclude metadata and labels)
            full_data = datasets.get('full', pd.DataFrame())
            if full_data.empty:
                return {}
            
            # Define feature columns
            feature_columns = [col for col in full_data.columns 
                             if not col.startswith('label_') 
                             and col not in ['pool_id', 'symbol', 'network_id', 'dex_id']]
            
            # Define label columns
            label_columns = [col for col in full_data.columns if col.startswith('label_')]
            
            config = {
                'data_config': {
                    'name': export_name,
                    'description': f'New pools history data export for QLib - {export_name}',
                    'created_at': datetime.now().isoformat(),
                    'data_path': str(self.output_dir),
                    'symbol_column': 'symbol',
                    'datetime_column': 'datetime'
                },
                'features': {
                    'columns': feature_columns,
                    'count': len(feature_columns),
                    'types': {
                        'price': [col for col in feature_columns if 'price' in col],
                        'volume': [col for col in feature_columns if 'volume' in col],
                        'technical': [col for col in feature_columns if any(x in col for x in ['rsi', 'ma_', 'volatility'])],
                        'fundamental': [col for col in feature_columns if any(x in col for x in ['market_cap', 'fdv', 'liquidity'])]
                    }
                },
                'labels': {
                    'columns': label_columns,
                    'count': len(label_columns),
                    'types': {
                        'returns': [col for col in label_columns if 'return' in col],
                        'binary': [col for col in label_columns if 'up_' in col or 'surge' in col or 'high_vol' in col]
                    }
                },
                'datasets': {
                    split: {
                        'records': len(data),
                        'unique_symbols': data['symbol'].nunique() if 'symbol' in data.columns else 0,
                        'date_range': {
                            'start': data.index.min().isoformat() if not data.empty else None,
                            'end': data.index.max().isoformat() if not data.empty else None
                        }
                    }
                    for split, data in datasets.items()
                },
                'qlib_workflow': {
                    'data_handler': 'Alpha158',  # QLib data handler
                    'model_configs': {
                        'linear': {
                            'class': 'LinearModel',
                            'kwargs': {'estimator': 'ridge'}
                        },
                        'lgb': {
                            'class': 'LGBModel',
                            'kwargs': {}
                        },
                        'transformer': {
                            'class': 'TransformerModel',
                            'kwargs': {'d_model': 64, 'nhead': 4}
                        }
                    }
                }
            }
            
            return config
            
        except Exception as e:
            logger.error(f"Error creating QLib config: {e}")
            return {}
    
    async def _record_export_metadata(self, metadata: Dict) -> None:
        """Record export metadata in database."""
        try:
            from enhanced_new_pools_history_model import QLibDataExport
            
            export_record = QLibDataExport(
                export_name=metadata['export_name'],
                export_type='training',
                start_timestamp=int(metadata['start_date'].timestamp()),
                end_timestamp=int(metadata['end_date'].timestamp()),
                networks=metadata['networks'],
                pool_count=metadata['unique_pools'],
                record_count=metadata['total_records'],
                file_path=str(metadata.get('export_paths', {})),
                status='completed',
                qlib_config_json=metadata.get('config', {}),
                created_at=metadata['created_at'],
                completed_at=datetime.now()
            )
            
            with self.db_manager.connection.get_session() as session:
                session.add(export_record)
                session.commit()
            
            logger.info(f"Recorded export metadata for {metadata['export_name']}")
            
        except Exception as e:
            logger.error(f"Error recording export metadata: {e}")


class QLibModelTrainer:
    """
    Train QLib models using exported new pools data.
    """
    
    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
    
    def create_qlib_workflow(self, config_path: str) -> Dict:
        """Create QLib workflow configuration."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # QLib workflow template
            workflow = {
                'task': {
                    'model': {
                        'class': 'LGBModel',
                        'module_path': 'qlib.contrib.model.gbdt',
                        'kwargs': {
                            'loss': 'mse',
                            'colsample_bytree': 0.8879,
                            'learning_rate': 0.0421,
                            'subsample': 0.8789,
                            'lambda_l1': 205.6999,
                            'lambda_l2': 580.9768,
                            'max_depth': 8,
                            'num_leaves': 210,
                            'num_threads': 20
                        }
                    },
                    'dataset': {
                        'class': 'DatasetH',
                        'module_path': 'qlib.data.dataset',
                        'kwargs': {
                            'handler': {
                                'class': 'Alpha158',
                                'module_path': 'qlib.contrib.data.handler',
                                'kwargs': {
                                    'start_time': config['datasets']['train']['date_range']['start'],
                                    'end_time': config['datasets']['test']['date_range']['end'],
                                    'fit_start_time': config['datasets']['train']['date_range']['start'],
                                    'fit_end_time': config['datasets']['train']['date_range']['end'],
                                    'instruments': 'all',
                                    'infer_processors': [
                                        {'class': 'RobustZScoreNorm', 'kwargs': {'fields_group': 'feature', 'clip_outlier': True}},
                                        {'class': 'Fillna', 'kwargs': {'fields_group': 'feature'}}
                                    ],
                                    'learn_processors': [
                                        {'class': 'DropnaLabel'},
                                        {'class': 'CSRankNorm', 'kwargs': {'fields_group': 'label'}}
                                    ]
                                }
                            },
                            'segments': {
                                'train': (config['datasets']['train']['date_range']['start'], 
                                         config['datasets']['train']['date_range']['end']),
                                'valid': (config['datasets']['validation']['date_range']['start'], 
                                         config['datasets']['validation']['date_range']['end']),
                                'test': (config['datasets']['test']['date_range']['start'], 
                                        config['datasets']['test']['date_range']['end'])
                            }
                        }
                    }
                },
                'port_analysis_config': {
                    'strategy': {
                        'class': 'TopkDropoutStrategy',
                        'module_path': 'qlib.contrib.strategy.signal_strategy',
                        'kwargs': {
                            'signal': '<PRED>',
                            'topk': 50,
                            'n_drop': 5
                        }
                    },
                    'backtest': {
                        'start_time': config['datasets']['test']['date_range']['start'],
                        'end_time': config['datasets']['test']['date_range']['end'],
                        'account': 100000,
                        'benchmark': None,
                        'exchange_kwargs': {
                            'freq': 'day',
                            'limit_threshold': 0.095,
                            'deal_price': 'close',
                            'open_cost': 0.0005,
                            'close_cost': 0.0015,
                            'min_cost': 5
                        }
                    }
                }
            }
            
            return workflow
            
        except Exception as e:
            logger.error(f"Error creating QLib workflow: {e}")
            return {}


# Usage example and CLI integration
async def export_qlib_bin_data_cli(
    db_manager: DatabaseManager,
    start_date: str,
    end_date: str,
    networks: List[str] = None,
    qlib_dir: str = "./qlib_data",
    freq: str = "60min",
    min_liquidity: float = 1000,
    min_volume: float = 100,
    mode: str = "all",
    backup_dir: str = None
):
    """CLI function to export QLib bin data."""
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        exporter = QLibBinDataExporter(
            db_manager=db_manager, 
            qlib_dir=qlib_dir,
            freq=freq,
            backup_dir=backup_dir
        )
        
        result = await exporter.export_bin_data(
            start_date=start_dt,
            end_date=end_dt,
            networks=networks,
            min_liquidity_usd=min_liquidity,
            min_volume_usd=min_volume,
            mode=mode
        )
        
        if result['success']:
            print(f"✅ QLib bin export completed: {result['export_name']}")
            print(f"📊 Total records: {result['total_records']}")
            print(f"🏊 Unique pools: {result['unique_pools']}")
            print(f"📁 QLib directory: {qlib_dir}")
            print(f"⏱️  Frequency: {freq}")
            print(f"🔄 Mode: {mode}")
            
            if 'symbols_processed' in result:
                print(f"🎯 Symbols processed: {result['symbols_processed']}")
            if 'calendar_entries' in result:
                print(f"📅 Calendar entries: {result['calendar_entries']}")
            if 'new_dates' in result:
                print(f"📈 New dates added: {result['new_dates']}")
                
        else:
            print(f"❌ Export failed: {result['error']}")
            if 'errors' in result and result['errors']:
                print("Detailed errors:")
                for error in result['errors']:
                    print(f"  - {error}")
        
        return result
        
    except Exception as e:
        logger.error(f"CLI bin export error: {e}")
        print(f"❌ Export error: {e}")
        return {'success': False, 'error': str(e)}


class QLibDataHealthChecker:
    """
    Health checker for QLib bin data based on QLib's DataHealthChecker.
    Validates data completeness and correctness.
    """
    
    def __init__(
        self,
        qlib_dir: str,
        freq: str = "60min",
        large_step_threshold_price: float = 0.5,
        large_step_threshold_volume: float = 3.0,
        missing_data_threshold: int = 0
    ):
        self.qlib_dir = Path(qlib_dir)
        self.freq = freq
        self.large_step_threshold_price = large_step_threshold_price
        self.large_step_threshold_volume = large_step_threshold_volume
        self.missing_data_threshold = missing_data_threshold
        
        self.data = {}
        self.problems = {}
    
    def load_qlib_data(self) -> Dict[str, pd.DataFrame]:
        """Load QLib bin data for health checking."""
        try:
            # This would require QLib to be properly initialized
            # For now, return placeholder
            logger.warning("QLib data loading requires QLib initialization")
            return {}
            
        except Exception as e:
            logger.error(f"Error loading QLib data: {e}")
            return {}
    
    def check_required_columns(self) -> Optional[pd.DataFrame]:
        """Check if required OHLCV columns are present."""
        required_columns = ["open", "high", "low", "close", "volume"]
        problems = []
        
        for symbol, df in self.data.items():
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                problems.append({
                    'symbol': symbol,
                    'missing_columns': missing_cols
                })
        
        if problems:
            return pd.DataFrame(problems)
        return None
    
    def check_missing_data(self) -> Optional[pd.DataFrame]:
        """Check for missing data in OHLCV columns."""
        problems = []
        
        for symbol, df in self.data.items():
            missing_counts = df.isnull().sum()
            significant_missing = missing_counts[missing_counts > self.missing_data_threshold]
            
            if not significant_missing.empty:
                problems.append({
                    'symbol': symbol,
                    'missing_data': significant_missing.to_dict()
                })
        
        if problems:
            return pd.DataFrame(problems)
        return None
    
    def check_large_step_changes(self) -> Optional[pd.DataFrame]:
        """Check for unrealistic price/volume changes."""
        problems = []
        
        for symbol, df in self.data.items():
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    pct_change = df[col].pct_change().abs()
                    threshold = self.large_step_threshold_volume if col == 'volume' else self.large_step_threshold_price
                    
                    large_changes = pct_change[pct_change > threshold]
                    if not large_changes.empty:
                        problems.append({
                            'symbol': symbol,
                            'column': col,
                            'max_change': large_changes.max(),
                            'change_dates': large_changes.index.tolist()
                        })
        
        if problems:
            return pd.DataFrame(problems)
        return None
    
    def run_health_check(self) -> Dict[str, Any]:
        """Run complete health check on QLib data."""
        try:
            logger.info("Starting QLib data health check...")
            
            # Load data
            self.data = self.load_qlib_data()
            
            if not self.data:
                return {'success': False, 'error': 'No data loaded for health check'}
            
            # Run checks
            results = {
                'total_symbols': len(self.data),
                'required_columns_check': self.check_required_columns(),
                'missing_data_check': self.check_missing_data(),
                'large_step_changes_check': self.check_large_step_changes()
            }
            
            # Determine overall health
            has_problems = any(result is not None for result in [
                results['required_columns_check'],
                results['missing_data_check'], 
                results['large_step_changes_check']
            ])
            
            results['overall_health'] = 'HEALTHY' if not has_problems else 'ISSUES_FOUND'
            results['success'] = True
            
            return results
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'success': False, 'error': str(e)}