"""
Q50 Signal Loader for NautilusTrader integration.

This module provides the Q50SignalLoader class that bridges between the existing
Q50 quantile prediction system and NautilusTrader trading framework.
"""

import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any, List

import pandas as pd
from sqlalchemy.orm import Session

from gecko_terminal_collector.database.connection import DatabaseConnection
from gecko_terminal_collector.config.models import DatabaseConfig

logger = logging.getLogger(__name__)


class Q50SignalLoader:
    """
    Loads and manages Q50 signals for NautilusTrader integration.
    
    This class handles loading Q50 signals from the existing macro_features.pkl file,
    provides timestamp-based signal retrieval with tolerance, and integrates with
    the existing PostgreSQL database connection.
    """
    
    # Required Q50 columns for validation
    REQUIRED_COLUMNS = [
        'q10', 'q50', 'q90', 'vol_raw', 'vol_risk', 
        'prob_up', 'economically_significant', 'high_quality', 'tradeable'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Q50SignalLoader.
        
        Args:
            config: Configuration dictionary containing:
                - q50.features_path: Path to macro_features.pkl
                - q50.signal_tolerance_minutes: Tolerance for timestamp matching
                - database: Database configuration
        """
        self.config = config
        self.features_path = Path(config['q50']['features_path'])
        self.signal_tolerance_minutes = config['q50'].get('signal_tolerance_minutes', 5)
        
        # Initialize database connection
        db_config = DatabaseConfig(**config['database'])
        self.db_connection = DatabaseConnection(db_config)
        self.db_connection.initialize()
        
        # Signal data storage
        self.signals_df: Optional[pd.DataFrame] = None
        self.last_loaded: Optional[datetime] = None
        self.signal_cache: Dict[str, Dict] = {}
        
        logger.info(f"Q50SignalLoader initialized with features path: {self.features_path}")
    
    async def load_signals(self) -> bool:
        """
        Load Q50 signals from macro_features.pkl file.
        
        Returns:
            True if signals loaded successfully, False otherwise
        """
        try:
            if not self.features_path.exists():
                logger.error(f"Features file not found: {self.features_path}")
                return False
            
            logger.info(f"Loading Q50 signals from {self.features_path}")
            
            # Load pickle file
            with open(self.features_path, 'rb') as f:
                data = pickle.load(f)
            
            # Handle different data formats
            if isinstance(data, pd.DataFrame):
                self.signals_df = data
            elif isinstance(data, dict) and 'signals' in data:
                self.signals_df = data['signals']
            elif isinstance(data, dict) and 'macro_features' in data:
                self.signals_df = data['macro_features']
            else:
                logger.error(f"Unexpected data format in {self.features_path}")
                return False
            
            # Validate signal columns
            if not self.validate_signal_columns(self.signals_df):
                logger.error("Signal validation failed - missing required columns")
                return False
            
            # Ensure timestamp index
            if not isinstance(self.signals_df.index, pd.DatetimeIndex):
                if 'timestamp' in self.signals_df.columns:
                    self.signals_df.set_index('timestamp', inplace=True)
                elif 'datetime' in self.signals_df.columns:
                    self.signals_df.set_index('datetime', inplace=True)
                else:
                    logger.error("No timestamp column found in signals data")
                    return False
            
            # Sort by timestamp
            self.signals_df.sort_index(inplace=True)
            
            self.last_loaded = datetime.now()
            self.signal_cache.clear()  # Clear cache on reload
            
            logger.info(f"Successfully loaded {len(self.signals_df)} Q50 signals")
            logger.info(f"Signal date range: {self.signals_df.index.min()} to {self.signals_df.index.max()}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Q50 signals: {e}")
            return False
    
    def validate_signal_columns(self, df: pd.DataFrame) -> bool:
        """
        Validate that required Q50 columns are present in the DataFrame.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if all required columns are present, False otherwise
        """
        missing_columns = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        
        if missing_columns:
            logger.error(f"Missing required Q50 columns: {missing_columns}")
            return False
        
        logger.info("All required Q50 columns validated successfully")
        return True
    
    async def get_signal_for_timestamp(self, timestamp: pd.Timestamp) -> Optional[Dict]:
        """
        Get Q50 signal for a specific timestamp with tolerance.
        
        Args:
            timestamp: Target timestamp for signal retrieval
            
        Returns:
            Dictionary containing signal data, or None if no signal found
        """
        if self.signals_df is None:
            logger.warning("No signals loaded - call load_signals() first")
            return None
        
        # Convert timestamp to pandas Timestamp if needed
        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.Timestamp(timestamp)
        
        # Check cache first
        cache_key = timestamp.isoformat()
        if cache_key in self.signal_cache:
            return self.signal_cache[cache_key]
        
        try:
            # Define tolerance window
            tolerance = pd.Timedelta(minutes=self.signal_tolerance_minutes)
            start_time = timestamp - tolerance
            end_time = timestamp + tolerance
            
            # Find signals within tolerance window
            mask = (self.signals_df.index >= start_time) & (self.signals_df.index <= end_time)
            matching_signals = self.signals_df[mask]
            
            if matching_signals.empty:
                logger.debug(f"No signals found within {self.signal_tolerance_minutes} minutes of {timestamp}")
                return None
            
            # Get the closest signal by timestamp
            time_diffs = abs(matching_signals.index - timestamp)
            closest_idx = time_diffs.idxmin()
            closest_signal = matching_signals.loc[closest_idx]
            
            # Convert to dictionary
            signal_dict = {
                'timestamp': closest_idx,
                'time_diff_minutes': time_diffs.loc[closest_idx].total_seconds() / 60,
                **closest_signal.to_dict()
            }
            
            # Cache the result
            self.signal_cache[cache_key] = signal_dict
            
            logger.debug(f"Found signal for {timestamp} (closest: {closest_idx}, diff: {signal_dict['time_diff_minutes']:.2f} min)")
            
            return signal_dict
            
        except Exception as e:
            logger.error(f"Error retrieving signal for timestamp {timestamp}: {e}")
            return None
    
    def get_latest_signal(self) -> Optional[Dict]:
        """
        Get the most recent signal from the loaded data.
        
        Returns:
            Dictionary containing the latest signal data, or None if no signals loaded
        """
        if self.signals_df is None or self.signals_df.empty:
            return None
        
        try:
            latest_timestamp = self.signals_df.index.max()
            latest_signal = self.signals_df.loc[latest_timestamp]
            
            return {
                'timestamp': latest_timestamp,
                'time_diff_minutes': 0.0,
                **latest_signal.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error retrieving latest signal: {e}")
            return None
    
    def get_signal_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the loaded signals.
        
        Returns:
            Dictionary containing signal statistics
        """
        if self.signals_df is None:
            return {'status': 'no_signals_loaded'}
        
        try:
            stats = {
                'total_signals': len(self.signals_df),
                'date_range': {
                    'start': self.signals_df.index.min().isoformat(),
                    'end': self.signals_df.index.max().isoformat()
                },
                'tradeable_signals': int(self.signals_df['tradeable'].sum()) if 'tradeable' in self.signals_df.columns else 0,
                'economically_significant': int(self.signals_df['economically_significant'].sum()) if 'economically_significant' in self.signals_df.columns else 0,
                'high_quality': int(self.signals_df['high_quality'].sum()) if 'high_quality' in self.signals_df.columns else 0,
                'last_loaded': self.last_loaded.isoformat() if self.last_loaded else None,
                'cache_size': len(self.signal_cache)
            }
            
            # Add Q50 value statistics
            if 'q50' in self.signals_df.columns:
                q50_series = self.signals_df['q50']
                stats['q50_stats'] = {
                    'mean': float(q50_series.mean()),
                    'std': float(q50_series.std()),
                    'min': float(q50_series.min()),
                    'max': float(q50_series.max()),
                    'positive_signals': int((q50_series > 0).sum()),
                    'negative_signals': int((q50_series < 0).sum())
                }
            
            # Add volatility risk statistics
            if 'vol_risk' in self.signals_df.columns:
                vol_risk_series = self.signals_df['vol_risk']
                stats['vol_risk_stats'] = {
                    'mean': float(vol_risk_series.mean()),
                    'std': float(vol_risk_series.std()),
                    'percentiles': {
                        '30': float(vol_risk_series.quantile(0.30)),
                        '70': float(vol_risk_series.quantile(0.70)),
                        '90': float(vol_risk_series.quantile(0.90))
                    }
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating signal statistics: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_signals_in_range(self, start_time: pd.Timestamp, end_time: pd.Timestamp) -> pd.DataFrame:
        """
        Get all signals within a specific time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            DataFrame containing signals in the specified range
        """
        if self.signals_df is None:
            return pd.DataFrame()
        
        try:
            mask = (self.signals_df.index >= start_time) & (self.signals_df.index <= end_time)
            return self.signals_df[mask].copy()
            
        except Exception as e:
            logger.error(f"Error retrieving signals in range {start_time} to {end_time}: {e}")
            return pd.DataFrame()
    
    def clear_cache(self) -> None:
        """Clear the signal cache."""
        self.signal_cache.clear()
        logger.info("Signal cache cleared")
    
    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.db_connection:
            self.db_connection.close()
        logger.info("Q50SignalLoader closed")
    
    async def close_async(self) -> None:
        """Close database connections asynchronously."""
        if self.db_connection:
            await self.db_connection.close_async()
        logger.info("Q50SignalLoader closed (async)")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the signal loader.
        
        Returns:
            Dictionary containing health check results
        """
        health_status = {
            'signals_loaded': self.signals_df is not None,
            'features_file_exists': self.features_path.exists(),
            'database_healthy': False,
            'last_loaded': self.last_loaded.isoformat() if self.last_loaded else None,
            'signal_count': len(self.signals_df) if self.signals_df is not None else 0
        }
        
        # Check database health
        try:
            health_status['database_healthy'] = self.db_connection.health_check()
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status['database_error'] = str(e)
        
        return health_status