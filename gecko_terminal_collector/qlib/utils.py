"""
QLib data processing and validation utilities.
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger(__name__)


class QLibDataValidator:
    """
    Utility class for validating QLib-compatible data formats.
    """
    
    @staticmethod
    def validate_dataframe(df: pd.DataFrame, require_volume: bool = True) -> Dict[str, Any]:
        """
        Validate DataFrame for QLib compatibility.
        
        Args:
            df: DataFrame to validate
            require_volume: Whether volume column is required
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'is_valid': True,
            'record_count': len(df),
            'issues': [],
            'warnings': [],
            'quality_score': 1.0
        }
        
        if df.empty:
            validation_result['is_valid'] = False
            validation_result['issues'].append("DataFrame is empty")
            validation_result['quality_score'] = 0.0
            return validation_result
        
        # Check required columns
        required_columns = ['datetime', 'symbol', 'open', 'high', 'low', 'close']
        if require_volume:
            required_columns.append('volume')
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            validation_result['is_valid'] = False
            validation_result['issues'].extend([f"Missing column: {col}" for col in missing_columns])
        
        # Check data types
        if 'datetime' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
                validation_result['issues'].append("datetime column is not datetime type")
        
        # Check for null values
        null_counts = df.isnull().sum()
        if null_counts.any():
            validation_result['warnings'].append(f"Found null values: {null_counts.to_dict()}")
        
        # Check price relationships (high >= low, etc.)
        price_issues = 0
        if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            invalid_prices = df[
                ~((df['low'] <= df['open']) & (df['open'] <= df['high']) &
                  (df['low'] <= df['close']) & (df['close'] <= df['high']))
            ]
            price_issues = len(invalid_prices)
            
            if price_issues > 0:
                validation_result['issues'].append(f"Found {price_issues} records with invalid price relationships")
        
        # Check for negative values
        numeric_columns = ['open', 'high', 'low', 'close']
        if require_volume:
            numeric_columns.append('volume')
        
        negative_issues = 0
        for col in numeric_columns:
            if col in df.columns:
                negative_count = (df[col] < 0).sum()
                if negative_count > 0:
                    negative_issues += negative_count
                    validation_result['issues'].append(f"Found {negative_count} negative values in {col}")
        
        # Calculate quality score
        total_issues = price_issues + negative_issues + len(null_counts[null_counts > 0])
        if len(df) > 0:
            validation_result['quality_score'] = max(0, 1 - (total_issues / len(df)))
        
        # Update overall validity
        if validation_result['issues']:
            validation_result['is_valid'] = False
        
        return validation_result
    
    @staticmethod
    def validate_symbol_format(symbol: str) -> bool:
        """
        Validate symbol format for QLib compatibility.
        
        Args:
            symbol: Symbol string to validate
            
        Returns:
            True if symbol format is valid
        """
        if not symbol or not isinstance(symbol, str):
            return False
        
        # QLib symbols should be alphanumeric with underscores
        return symbol.replace('_', '').isalnum()
    
    @staticmethod
    def validate_date_range(df: pd.DataFrame, 
                           expected_start: Optional[datetime] = None,
                           expected_end: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Validate date range coverage in DataFrame.
        
        Args:
            df: DataFrame with datetime column
            expected_start: Expected start date
            expected_end: Expected end date
            
        Returns:
            Dictionary with date range validation results
        """
        result = {
            'is_valid': True,
            'issues': [],
            'actual_start': None,
            'actual_end': None,
            'coverage_percentage': 0.0
        }
        
        if df.empty or 'datetime' not in df.columns:
            result['is_valid'] = False
            result['issues'].append("No datetime data available")
            return result
        
        actual_start = df['datetime'].min()
        actual_end = df['datetime'].max()
        
        result['actual_start'] = actual_start
        result['actual_end'] = actual_end
        
        if expected_start and actual_start > expected_start:
            result['issues'].append(f"Data starts later than expected: {actual_start} > {expected_start}")
        
        if expected_end and actual_end < expected_end:
            result['issues'].append(f"Data ends earlier than expected: {actual_end} < {expected_end}")
        
        # Calculate coverage percentage
        if expected_start and expected_end:
            expected_duration = (expected_end - expected_start).total_seconds()
            actual_duration = (actual_end - actual_start).total_seconds()
            
            if expected_duration > 0:
                result['coverage_percentage'] = min(100.0, (actual_duration / expected_duration) * 100)
        
        if result['issues']:
            result['is_valid'] = False
        
        return result


class QLibDataProcessor:
    """
    Utility class for processing data into QLib-compatible formats.
    """
    
    @staticmethod
    def fill_missing_data(df: pd.DataFrame, method: str = 'forward') -> pd.DataFrame:
        """
        Fill missing data points in time series.
        
        Args:
            df: DataFrame with time series data
            method: Fill method ('forward', 'backward', 'interpolate')
            
        Returns:
            DataFrame with filled missing data
        """
        if df.empty:
            return df
        
        df_filled = df.copy()
        
        if method == 'forward':
            df_filled = df_filled.fillna(method='ffill')
        elif method == 'backward':
            df_filled = df_filled.fillna(method='bfill')
        elif method == 'interpolate':
            numeric_columns = df_filled.select_dtypes(include=[np.number]).columns
            df_filled[numeric_columns] = df_filled[numeric_columns].interpolate()
        
        return df_filled
    
    @staticmethod
    def resample_data(df: pd.DataFrame, 
                     target_frequency: str,
                     datetime_column: str = 'datetime') -> pd.DataFrame:
        """
        Resample data to target frequency.
        
        Args:
            df: DataFrame to resample
            target_frequency: Target frequency (e.g., '1H', '1D')
            datetime_column: Name of datetime column
            
        Returns:
            Resampled DataFrame
        """
        if df.empty or datetime_column not in df.columns:
            return df
        
        df_resampled = df.copy()
        df_resampled = df_resampled.set_index(datetime_column)
        
        # Define aggregation rules for OHLCV data
        agg_rules = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        # Only aggregate columns that exist
        available_agg_rules = {k: v for k, v in agg_rules.items() if k in df_resampled.columns}
        
        if available_agg_rules:
            df_resampled = df_resampled.resample(target_frequency).agg(available_agg_rules)
            df_resampled = df_resampled.reset_index()
        
        return df_resampled
    
    @staticmethod
    def normalize_symbols(df: pd.DataFrame, symbol_column: str = 'symbol') -> pd.DataFrame:
        """
        Normalize symbol names for QLib compatibility.
        
        Args:
            df: DataFrame with symbol column
            symbol_column: Name of symbol column
            
        Returns:
            DataFrame with normalized symbols
        """
        if df.empty or symbol_column not in df.columns:
            return df
        
        df_normalized = df.copy()
        
        # Normalize symbols: uppercase, replace special characters with underscores
        df_normalized[symbol_column] = (
            df_normalized[symbol_column]
            .str.upper()
            .str.replace(r'[^A-Z0-9_]', '_', regex=True)
            .str.replace(r'_+', '_', regex=True)  # Replace multiple underscores with single
            .str.strip('_')  # Remove leading/trailing underscores
        )
        
        return df_normalized
    
    @staticmethod
    def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Add basic technical indicators to OHLCV data.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with additional technical indicators
        """
        if df.empty:
            return df
        
        df_enhanced = df.copy()
        
        # Add returns
        if 'close' in df_enhanced.columns:
            df_enhanced['returns'] = df_enhanced['close'].pct_change()
        
        # Add moving averages
        if 'close' in df_enhanced.columns:
            df_enhanced['ma_5'] = df_enhanced['close'].rolling(window=5).mean()
            df_enhanced['ma_20'] = df_enhanced['close'].rolling(window=20).mean()
        
        # Add volatility (rolling standard deviation of returns)
        if 'returns' in df_enhanced.columns:
            df_enhanced['volatility'] = df_enhanced['returns'].rolling(window=20).std()
        
        return df_enhanced
    
    @staticmethod
    def create_qlib_dataset_structure(df: pd.DataFrame, 
                                    output_dir: str,
                                    symbol_column: str = 'symbol',
                                    datetime_column: str = 'datetime') -> Dict[str, Any]:
        """
        Create QLib dataset directory structure and files.
        
        Args:
            df: DataFrame with multi-symbol data
            output_dir: Output directory path
            symbol_column: Name of symbol column
            datetime_column: Name of datetime column
            
        Returns:
            Dictionary with creation results
        """
        from pathlib import Path
        import json
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        result = {
            'success': True,
            'files_created': 0,
            'symbols_processed': 0,
            'errors': []
        }
        
        try:
            if df.empty:
                result['success'] = False
                result['errors'].append("Empty DataFrame provided")
                return result
            
            # Group by symbol and save individual files
            for symbol in df[symbol_column].unique():
                try:
                    symbol_data = df[df[symbol_column] == symbol].copy()
                    symbol_data = symbol_data.sort_values(datetime_column)
                    
                    # Save symbol data
                    symbol_file = output_path / f"{symbol}.csv"
                    symbol_data.to_csv(symbol_file, index=False)
                    
                    result['files_created'] += 1
                    result['symbols_processed'] += 1
                    
                except Exception as e:
                    result['errors'].append(f"Error processing symbol {symbol}: {e}")
            
            # Create metadata file
            metadata = {
                'created_at': datetime.utcnow().isoformat(),
                'total_symbols': result['symbols_processed'],
                'date_range': {
                    'start': df[datetime_column].min().isoformat(),
                    'end': df[datetime_column].max().isoformat()
                },
                'columns': list(df.columns),
                'total_records': len(df)
            }
            
            metadata_file = output_path / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            result['files_created'] += 1
            
        except Exception as e:
            result['success'] = False
            result['errors'].append(f"Error creating dataset structure: {e}")
        
        return result