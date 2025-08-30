"""
Utility functions for QLib data export and transformation.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class QLibDataValidator:
    """Validator for QLib-compatible data formats."""
    
    REQUIRED_COLUMNS = ['datetime', 'symbol', 'open', 'high', 'low', 'close']
    OPTIONAL_COLUMNS = ['volume']
    
    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame, require_volume: bool = False) -> Dict[str, Any]:
        """
        Validate DataFrame for QLib compatibility.
        
        Args:
            df: DataFrame to validate
            require_volume: Whether volume column is required
            
        Returns:
            Validation result dictionary
        """
        result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }
        
        if df.empty:
            result['is_valid'] = False
            result['errors'].append("DataFrame is empty")
            return result
        
        # Check required columns
        missing_cols = [col for col in cls.REQUIRED_COLUMNS if col not in df.columns]
        if require_volume and 'volume' not in df.columns:
            missing_cols.append('volume')
        
        if missing_cols:
            result['is_valid'] = False
            result['errors'].append(f"Missing required columns: {missing_cols}")
        
        # Check data types
        if 'datetime' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
                result['warnings'].append("datetime column is not datetime type")
        
        # Check for numeric columns
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                result['warnings'].append(f"{col} column is not numeric type")
        
        # Check for missing values
        null_counts = df.isnull().sum()
        if null_counts.any():
            result['warnings'].append(f"Missing values found: {null_counts[null_counts > 0].to_dict()}")
        
        # Check OHLC relationships
        if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            invalid_ohlc = df[
                (df['high'] < df['low']) | 
                (df['high'] < df['open']) | 
                (df['high'] < df['close']) |
                (df['low'] > df['open']) |
                (df['low'] > df['close'])
            ]
            
            if not invalid_ohlc.empty:
                result['warnings'].append(f"Invalid OHLC relationships found in {len(invalid_ohlc)} rows")
        
        # Generate statistics
        result['stats'] = {
            'total_rows': len(df),
            'unique_symbols': df['symbol'].nunique() if 'symbol' in df.columns else 0,
            'date_range': {
                'start': df['datetime'].min().isoformat() if 'datetime' in df.columns else None,
                'end': df['datetime'].max().isoformat() if 'datetime' in df.columns else None
            } if 'datetime' in df.columns else None,
            'columns': list(df.columns)
        }
        
        return result


class QLibSymbolManager:
    """Manager for QLib symbol naming and mapping."""
    
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """
        Normalize symbol name for QLib compatibility.
        
        Args:
            symbol: Raw symbol string
            
        Returns:
            Normalized symbol string
        """
        # Remove special characters except underscore
        normalized = ''.join(c if c.isalnum() or c == '_' else '' for c in symbol.upper())
        
        # Ensure it doesn't start with a number
        if normalized and normalized[0].isdigit():
            normalized = f"S_{normalized}"
        
        # Limit length
        if len(normalized) > 50:
            normalized = normalized[:50]
        
        return normalized
    
    @staticmethod
    def create_symbol_mapping(pools: List[Any]) -> Dict[str, str]:
        """
        Create mapping from pool IDs to QLib symbols.
        
        Args:
            pools: List of pool objects
            
        Returns:
            Dictionary mapping pool_id to symbol
        """
        mapping = {}
        
        for pool in pools:
            # Generate symbol from pool information
            dex_part = pool.dex_id.upper()[:10]
            
            # Extract meaningful part from pool ID
            if hasattr(pool, 'name') and pool.name:
                # Use pool name if available
                name_part = pool.name.replace(' ', '_').upper()[:20]
            else:
                # Use last part of pool ID
                pool_part = pool.id.split('_')[-1][:20] if '_' in pool.id else pool.id[:20]
                name_part = pool_part.upper()
            
            symbol = f"{dex_part}_{name_part}"
            symbol = QLibSymbolManager.normalize_symbol(symbol)
            
            # Handle duplicates
            original_symbol = symbol
            counter = 1
            while symbol in mapping.values():
                symbol = f"{original_symbol}_{counter}"
                counter += 1
            
            mapping[pool.id] = symbol
        
        return mapping


class QLibDataProcessor:
    """Processor for QLib-specific data transformations."""
    
    @staticmethod
    def resample_ohlcv(df: pd.DataFrame, 
                      target_freq: str,
                      datetime_col: str = 'datetime') -> pd.DataFrame:
        """
        Resample OHLCV data to different frequency.
        
        Args:
            df: Input DataFrame with OHLCV data
            target_freq: Target frequency (e.g., '1H', '1D')
            datetime_col: Name of datetime column
            
        Returns:
            Resampled DataFrame
        """
        if df.empty:
            return df
        
        # Set datetime as index
        df_copy = df.copy()
        df_copy[datetime_col] = pd.to_datetime(df_copy[datetime_col])
        df_copy = df_copy.set_index(datetime_col)
        
        # Group by symbol and resample
        resampled_data = []
        
        for symbol in df_copy['symbol'].unique():
            symbol_data = df_copy[df_copy['symbol'] == symbol]
            
            # Resample OHLCV data
            resampled = symbol_data.resample(target_freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum' if 'volume' in symbol_data.columns else 'first'
            }).dropna()
            
            # Add symbol back
            resampled['symbol'] = symbol
            resampled_data.append(resampled.reset_index())
        
        if resampled_data:
            return pd.concat(resampled_data, ignore_index=True)
        else:
            return pd.DataFrame()
    
    @staticmethod
    def fill_missing_data(df: pd.DataFrame,
                         method: str = 'forward',
                         datetime_col: str = 'datetime') -> pd.DataFrame:
        """
        Fill missing data in OHLCV DataFrame.
        
        Args:
            df: Input DataFrame
            method: Fill method ('forward', 'backward', 'interpolate')
            datetime_col: Name of datetime column
            
        Returns:
            DataFrame with filled missing data
        """
        if df.empty:
            return df
        
        df_copy = df.copy()
        df_copy[datetime_col] = pd.to_datetime(df_copy[datetime_col])
        
        # Process each symbol separately
        filled_data = []
        
        for symbol in df_copy['symbol'].unique():
            symbol_data = df_copy[df_copy['symbol'] == symbol].copy()
            symbol_data = symbol_data.sort_values(datetime_col)
            
            if method == 'forward':
                symbol_data = symbol_data.ffill()
            elif method == 'backward':
                symbol_data = symbol_data.bfill()
            elif method == 'interpolate':
                numeric_cols = symbol_data.select_dtypes(include=['number']).columns
                symbol_data[numeric_cols] = symbol_data[numeric_cols].interpolate()
            
            filled_data.append(symbol_data)
        
        if filled_data:
            return pd.concat(filled_data, ignore_index=True)
        else:
            return df_copy
    
    @staticmethod
    def calculate_returns(df: pd.DataFrame,
                         price_col: str = 'close',
                         datetime_col: str = 'datetime') -> pd.DataFrame:
        """
        Calculate returns for each symbol.
        
        Args:
            df: Input DataFrame with price data
            price_col: Column name for price data
            datetime_col: Name of datetime column
            
        Returns:
            DataFrame with returns added
        """
        if df.empty or price_col not in df.columns:
            return df
        
        df_copy = df.copy()
        df_copy[datetime_col] = pd.to_datetime(df_copy[datetime_col])
        
        # Calculate returns for each symbol
        df_copy['return'] = df_copy.groupby('symbol')[price_col].pct_change()
        
        # Calculate log returns
        returns = df_copy['return']
        df_copy['log_return'] = returns.apply(lambda r: np.log(1 + r) if pd.notna(r) and r > -1 else np.nan)
        
        return df_copy


def create_qlib_calendar(start_date: Union[str, datetime],
                        end_date: Union[str, datetime],
                        freq: str = '1H') -> List[datetime]:
    """
    Create QLib-compatible trading calendar.
    
    Args:
        start_date: Start date
        end_date: End date  
        freq: Frequency string
        
    Returns:
        List of datetime objects representing trading calendar
    """
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # Create date range (crypto markets are 24/7)
    calendar = pd.date_range(start=start_dt, end=end_dt, freq=freq)
    
    return calendar.to_pydatetime().tolist()


def export_qlib_instruments(symbols: List[str], 
                           output_path: Union[str, Path]) -> None:
    """
    Export instrument list for QLib.
    
    Args:
        symbols: List of symbol names
        output_path: Path to save instruments file
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create instruments DataFrame
    instruments_df = pd.DataFrame({
        'symbol': symbols,
        'market': 'crypto',
        'sector': 'defi'
    })
    
    # Save to CSV
    instruments_df.to_csv(output_file, index=False)
    logger.info(f"Exported {len(symbols)} instruments to {output_file}")


def validate_qlib_export_directory(export_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Validate QLib export directory structure and contents.
    
    Args:
        export_dir: Directory to validate
        
    Returns:
        Validation result dictionary
    """
    export_path = Path(export_dir)
    
    result = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'stats': {
            'total_files': 0,
            'csv_files': 0,
            'symbols': []
        }
    }
    
    if not export_path.exists():
        result['is_valid'] = False
        result['errors'].append(f"Export directory does not exist: {export_path}")
        return result
    
    # Count files
    csv_files = list(export_path.glob("*.csv"))
    result['stats']['total_files'] = len(list(export_path.iterdir()))
    result['stats']['csv_files'] = len(csv_files)
    
    # Extract symbols from filenames
    symbols = []
    for csv_file in csv_files:
        if csv_file.name != 'export_summary.json':
            symbol = csv_file.stem
            symbols.append(symbol)
    
    result['stats']['symbols'] = symbols
    
    # Validate each CSV file
    invalid_files = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            validation = QLibDataValidator.validate_dataframe(df)
            if not validation['is_valid']:
                invalid_files.append(csv_file.name)
        except Exception as e:
            invalid_files.append(f"{csv_file.name}: {str(e)}")
    
    if invalid_files:
        result['warnings'].append(f"Invalid CSV files: {invalid_files}")
    
    return result