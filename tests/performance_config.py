"""
Performance testing configuration and utilities.

This module provides configuration settings and utility functions
for performance and load testing of the GeckoTerminal collector system.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PerformanceThresholds:
    """Performance thresholds for different test scenarios."""
    
    # Write throughput thresholds (records per second) - Realistic values
    ohlcv_write_min_throughput: float = 50.0
    trade_write_min_throughput: float = 100.0
    concurrent_write_min_throughput: float = 200.0
    
    # Response time thresholds (seconds) - Relaxed for real-world conditions
    max_query_response_time: float = 10.0
    max_write_operation_time: float = 60.0
    max_concurrent_operation_time: float = 120.0
    
    # Memory usage thresholds (MB) - More realistic for development environments
    max_memory_usage: float = 1000.0
    max_memory_growth: float = 500.0
    
    # Database size thresholds
    max_database_size_mb: float = 1000.0
    max_bytes_per_record: float = 1000.0
    
    # Concurrency thresholds
    min_concurrent_users: int = 3
    max_lock_wait_time: float = 1.0
    max_contention_ratio: float = 0.1
    
    # Rate limiting thresholds (based on GeckoTerminal Free API limits)
    min_success_rate: float = 0.8
    min_backoff_delay: float = 1.0
    api_calls_per_minute: int = 30  # GeckoTerminal Free API limit
    api_calls_per_month: int = 10000  # GeckoTerminal Free API monthly cap


@dataclass
class TestDataConfig:
    """Configuration for test data generation."""
    
    # OHLCV test data settings
    ohlcv_baseline_records: int = 1000
    ohlcv_volume_test_records: List[int] = None
    ohlcv_timeframes: List[str] = None
    
    # Trade test data settings
    trade_baseline_records: int = 1000
    trade_volume_test_records: List[int] = None
    
    # Concurrent test settings
    concurrent_collectors: int = 3
    concurrent_records_per_collector: int = 500
    
    # Batch size test settings
    batch_sizes: List[int] = None
    
    def __post_init__(self):
        """Set default values for list fields."""
        if self.ohlcv_volume_test_records is None:
            self.ohlcv_volume_test_records = [5000, 25000, 100000, 500000]
        
        if self.ohlcv_timeframes is None:
            self.ohlcv_timeframes = ["1m", "5m", "1h", "1d"]
        
        if self.trade_volume_test_records is None:
            self.trade_volume_test_records = [5000, 25000, 100000]
        
        if self.batch_sizes is None:
            self.batch_sizes = [100, 500, 1000, 2000, 5000]


@dataclass
class PostgreSQLMigrationThresholds:
    """Thresholds that indicate PostgreSQL migration is needed."""
    
    # Performance degradation thresholds
    min_write_throughput: float = 50.0  # records/sec
    max_query_response_time: float = 10.0  # seconds
    min_concurrent_users: int = 2
    max_database_size_mb: float = 500.0  # MB
    
    # Resource usage thresholds
    max_memory_usage_mb: float = 1000.0
    max_cpu_usage_percent: float = 80.0
    
    # Reliability thresholds
    max_lock_timeout_rate: float = 0.05  # 5% of operations
    max_connection_failure_rate: float = 0.01  # 1% of connections


class PerformanceTestConfig:
    """Main configuration class for performance testing."""
    
    def __init__(self):
        self.thresholds = PerformanceThresholds()
        self.test_data = TestDataConfig()
        self.migration_thresholds = PostgreSQLMigrationThresholds()
        
        # Test execution settings
        self.enable_memory_monitoring = True
        self.memory_sample_interval = 0.5  # seconds
        self.enable_detailed_logging = True
        self.cleanup_test_data = True
        
        # API rate limiting settings (GeckoTerminal Free API)
        self.api_rate_limit_settings = {
            'calls_per_minute': 30,
            'monthly_call_limit': 10000,
            'backoff_base_delay': 2.0,  # seconds
            'backoff_max_delay': 60.0,  # seconds
            'backoff_multiplier': 2.0,
            'max_retries': 3,
            'use_jitter': True,
            'circuit_breaker_threshold': 0.8  # Stop at 80% of rate limit
        }
        
        # Database settings for testing
        self.test_database_settings = {
            'sqlite_pragma_settings': {
                'journal_mode': 'WAL',
                'synchronous': 'NORMAL',
                'cache_size': -64000,  # 64MB cache
                'temp_store': 'MEMORY',
                'mmap_size': 268435456,  # 256MB mmap
            },
            'connection_pool_settings': {
                'pool_size': 5,
                'max_overflow': 10,
                'pool_pre_ping': True,
                'pool_recycle': 3600,
            }
        }
    
    def get_test_scenarios(self) -> Dict[str, Dict]:
        """Get predefined test scenarios."""
        return {
            'baseline_performance': {
                'description': 'Basic performance baseline tests',
                'ohlcv_records': self.test_data.ohlcv_baseline_records,
                'trade_records': self.test_data.trade_baseline_records,
                'concurrent_collectors': 1,
                'expected_duration': 30,
            },
            'moderate_load': {
                'description': 'Moderate load testing',
                'ohlcv_records': 10000,
                'trade_records': 15000,
                'concurrent_collectors': 2,
                'expected_duration': 60,
            },
            'high_load': {
                'description': 'High load stress testing',
                'ohlcv_records': 50000,
                'trade_records': 75000,
                'concurrent_collectors': 5,
                'expected_duration': 180,
            },
            'migration_threshold': {
                'description': 'Test conditions that trigger PostgreSQL migration',
                'ohlcv_records': 100000,
                'trade_records': 150000,
                'concurrent_collectors': 8,
                'expected_duration': 300,
            }
        }
    
    def get_benchmark_queries(self) -> List[Dict]:
        """Get benchmark queries for performance testing."""
        return [
            {
                'name': 'recent_ohlcv_data',
                'description': 'Retrieve recent OHLCV data for a pool',
                'type': 'ohlcv_query',
                'time_range_hours': 24,
                'expected_max_duration': 2.0,
            },
            {
                'name': 'historical_ohlcv_data',
                'description': 'Retrieve historical OHLCV data',
                'type': 'ohlcv_query',
                'time_range_hours': 720,  # 30 days
                'expected_max_duration': 5.0,
            },
            {
                'name': 'high_volume_trades',
                'description': 'Retrieve high-volume trades',
                'type': 'trade_query',
                'min_volume_usd': 10000,
                'time_range_hours': 168,  # 7 days
                'expected_max_duration': 3.0,
            },
            {
                'name': 'gap_detection',
                'description': 'Detect gaps in OHLCV data',
                'type': 'gap_query',
                'time_range_hours': 168,  # 7 days
                'expected_max_duration': 8.0,
            },
            {
                'name': 'data_integrity_check',
                'description': 'Comprehensive data integrity check',
                'type': 'integrity_query',
                'expected_max_duration': 15.0,
            }
        ]


# Global configuration instance
performance_config = PerformanceTestConfig()


def get_performance_config() -> PerformanceTestConfig:
    """Get the global performance configuration instance."""
    return performance_config


def create_custom_config(**kwargs) -> PerformanceTestConfig:
    """Create a custom performance configuration with overrides."""
    config = PerformanceTestConfig()
    
    # Apply any provided overrides
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
        elif hasattr(config.thresholds, key):
            setattr(config.thresholds, key, value)
        elif hasattr(config.test_data, key):
            setattr(config.test_data, key, value)
        elif hasattr(config.migration_thresholds, key):
            setattr(config.migration_thresholds, key, value)
    
    return config


def calculate_safe_api_usage(
    calls_per_minute: int = 30,
    monthly_limit: int = 10000,
    safety_margin: float = 0.2
) -> Dict[str, int]:
    """
    Calculate safe API usage patterns for GeckoTerminal Free API.
    
    Args:
        calls_per_minute: API rate limit per minute
        monthly_limit: Monthly API call limit
        safety_margin: Safety margin (0.2 = 20% buffer)
    
    Returns:
        Dictionary with safe usage recommendations
    """
    safe_calls_per_minute = int(calls_per_minute * (1 - safety_margin))
    safe_monthly_calls = int(monthly_limit * (1 - safety_margin))
    
    # Calculate daily budget
    days_in_month = 30
    safe_daily_calls = safe_monthly_calls // days_in_month
    
    # Calculate hourly budget
    safe_hourly_calls = safe_calls_per_minute * 60
    
    return {
        'safe_calls_per_minute': safe_calls_per_minute,
        'safe_calls_per_hour': min(safe_hourly_calls, safe_daily_calls),
        'safe_calls_per_day': safe_daily_calls,
        'safe_calls_per_month': safe_monthly_calls,
        'recommended_batch_size': min(safe_calls_per_minute // 2, 10),
        'recommended_delay_between_batches': 60,  # seconds
    }


def estimate_collection_time(
    pools_to_collect: int,
    data_points_per_pool: int = 3,  # OHLCV + trades + metadata
    calls_per_minute: int = 25  # Safe rate with buffer
) -> Dict[str, float]:
    """
    Estimate time required for data collection within API limits.
    
    Args:
        pools_to_collect: Number of pools to collect data for
        data_points_per_pool: API calls needed per pool
        calls_per_minute: Safe API calls per minute
    
    Returns:
        Dictionary with time estimates
    """
    total_calls_needed = pools_to_collect * data_points_per_pool
    
    if total_calls_needed <= calls_per_minute:
        # Can complete in one batch
        estimated_minutes = 1
    else:
        # Need multiple batches
        estimated_minutes = (total_calls_needed / calls_per_minute)
    
    return {
        'total_api_calls_needed': total_calls_needed,
        'estimated_minutes': estimated_minutes,
        'estimated_hours': estimated_minutes / 60,
        'batches_required': max(1, total_calls_needed // calls_per_minute),
        'calls_per_batch': min(calls_per_minute, total_calls_needed)
    }