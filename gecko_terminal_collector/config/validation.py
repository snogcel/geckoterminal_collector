"""
Enhanced configuration validation using Pydantic.
"""

import re
from typing import List, Any, Dict
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class TimeframeEnum(str, Enum):
    """Supported OHLCV timeframes."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"


class NetworkEnum(str, Enum):
    """Supported blockchain networks."""
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"


class DatabaseConfigValidator(BaseModel):
    """Pydantic model for database configuration validation."""
    url: str = Field(default="sqlite:///gecko_data.db", description="Database connection URL")
    pool_size: int = Field(default=10, ge=1, le=100, description="Connection pool size")
    echo: bool = Field(default=False, description="Enable SQL query logging")
    timeout: int = Field(default=30, ge=1, le=300, description="Connection timeout in seconds")
    
    @field_validator('url')
    @classmethod
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v:
            raise ValueError("Database URL cannot be empty")
        
        # Basic URL validation for common database types
        valid_prefixes = ['sqlite:///', 'postgresql://', 'mysql://', 'mysql+pymysql://']
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(f"Unsupported database URL format: {v}")
        
        return v


class APIConfigValidator(BaseModel):
    """Pydantic model for API configuration validation."""
    base_url: str = Field(
        default="https://api.geckoterminal.com/api/v2",
        description="GeckoTerminal API base URL"
    )
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    max_concurrent: int = Field(default=5, ge=1, le=50, description="Maximum concurrent requests")
    rate_limit_delay: float = Field(default=1.0, ge=0.1, le=10.0, description="Rate limit delay in seconds")
    
    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        """Validate API base URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("API base URL must start with http:// or https://")
        return v.rstrip('/')


class IntervalConfigValidator(BaseModel):
    """Pydantic model for interval configuration validation."""
    top_pools_monitoring: str = Field(default="1h", description="Top pools monitoring interval")
    ohlcv_collection: str = Field(default="1h", description="OHLCV data collection interval")
    trade_collection: str = Field(default="30m", description="Trade data collection interval")
    watchlist_check: str = Field(default="1h", description="Watchlist check interval")
    
    @field_validator('top_pools_monitoring', 'ohlcv_collection', 'trade_collection', 'watchlist_check')
    @classmethod
    def validate_interval_format(cls, v):
        """Validate interval format (e.g., '1h', '30m', '1d')."""
        if not v:
            raise ValueError("Interval cannot be empty")
        
        pattern = r'^(\d+)([mhd])$'
        match = re.match(pattern, v)
        if not match:
            raise ValueError(f"Invalid interval format: {v}. Expected format: number + unit (m/h/d)")
        
        number, unit = match.groups()
        number = int(number)
        
        # Validate reasonable ranges
        if unit == 'm' and (number < 1 or number > 1440):  # 1 minute to 24 hours
            raise ValueError(f"Minute interval must be between 1 and 1440: {v}")
        elif unit == 'h' and (number < 1 or number > 168):  # 1 hour to 1 week
            raise ValueError(f"Hour interval must be between 1 and 168: {v}")
        elif unit == 'd' and (number < 1 or number > 30):  # 1 day to 30 days
            raise ValueError(f"Day interval must be between 1 and 30: {v}")
        
        return v


class ThresholdConfigValidator(BaseModel):
    """Pydantic model for threshold configuration validation."""
    min_trade_volume_usd: Decimal = Field(
        default=Decimal("100"),
        ge=Decimal("0"),
        description="Minimum trade volume in USD"
    )
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    rate_limit_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="Rate limit delay")
    backoff_factor: float = Field(default=2.0, ge=1.0, le=10.0, description="Exponential backoff factor")


class TimeframeConfigValidator(BaseModel):
    """Pydantic model for timeframe configuration validation."""
    ohlcv_default: TimeframeEnum = Field(default=TimeframeEnum.ONE_HOUR, description="Default OHLCV timeframe")
    supported: List[TimeframeEnum] = Field(
        default_factory=lambda: list(TimeframeEnum),
        description="Supported OHLCV timeframes"
    )
    
    @model_validator(mode='after')
    def validate_default_in_supported(self):
        """Ensure default timeframe is in supported list."""
        if self.ohlcv_default and self.ohlcv_default not in self.supported:
            raise ValueError(f"Default timeframe '{self.ohlcv_default}' must be in supported timeframes: {self.supported}")
        
        return self


class DEXConfigValidator(BaseModel):
    """Pydantic model for DEX configuration validation."""
    targets: List[str] = Field(
        default_factory=lambda: ["heaven", "pumpswap"],
        min_length=1,
        description="Target DEX identifiers"
    )
    network: NetworkEnum = Field(default=NetworkEnum.SOLANA, description="Blockchain network")
    
    @field_validator('targets')
    @classmethod
    def validate_dex_targets(cls, v):
        """Validate DEX target names."""
        if not v:
            raise ValueError("At least one DEX target must be specified")
        
        # Validate DEX name format (alphanumeric and underscores)
        for target in v:
            if not re.match(r'^[a-zA-Z0-9_]+$', target):
                raise ValueError(f"Invalid DEX target name: {target}")
        
        return v


class ErrorConfigValidator(BaseModel):
    """Pydantic model for error handling configuration validation."""
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    backoff_factor: float = Field(default=2.0, ge=1.0, le=10.0, description="Exponential backoff factor")
    circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Circuit breaker failure threshold"
    )
    circuit_breaker_timeout: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Circuit breaker timeout in seconds"
    )


class WatchlistConfigValidator(BaseModel):
    """Pydantic model for watchlist configuration validation."""
    file_path: str = Field(default="watchlist.csv", description="Watchlist CSV file path")
    check_interval: str = Field(default="1h", description="Watchlist check interval")
    auto_add_new_tokens: bool = Field(default=True, description="Automatically add new tokens")
    remove_inactive_tokens: bool = Field(default=False, description="Remove inactive tokens")
    
    @field_validator('check_interval')
    @classmethod
    def validate_check_interval(cls, v):
        """Validate check interval format."""
        return IntervalConfigValidator.validate_interval_format(v)
    
    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v):
        """Validate file path format."""
        if not v:
            raise ValueError("Watchlist file path cannot be empty")
        
        if not v.endswith('.csv'):
            raise ValueError("Watchlist file must be a CSV file")
        
        return v


class CollectionConfigValidator(BaseModel):
    """Main configuration validator using Pydantic."""
    dexes: DEXConfigValidator = Field(default_factory=DEXConfigValidator)
    intervals: IntervalConfigValidator = Field(default_factory=IntervalConfigValidator)
    thresholds: ThresholdConfigValidator = Field(default_factory=ThresholdConfigValidator)
    timeframes: TimeframeConfigValidator = Field(default_factory=TimeframeConfigValidator)
    database: DatabaseConfigValidator = Field(default_factory=DatabaseConfigValidator)
    api: APIConfigValidator = Field(default_factory=APIConfigValidator)
    error_handling: ErrorConfigValidator = Field(default_factory=ErrorConfigValidator)
    watchlist: WatchlistConfigValidator = Field(default_factory=WatchlistConfigValidator)
    
    model_config = {
        "validate_assignment": True,
        "extra": "forbid",  # Prevent extra fields
        "use_enum_values": True
    }
    
    def to_legacy_config(self) -> 'CollectionConfig':
        """Convert to legacy CollectionConfig format for backward compatibility."""
        from gecko_terminal_collector.config.models import (
            CollectionConfig, DEXConfig, IntervalConfig, ThresholdConfig,
            TimeframeConfig, DatabaseConfig, APIConfig, ErrorConfig, WatchlistConfig
        )
        
        return CollectionConfig(
            dexes=DEXConfig(
                targets=self.dexes.targets,
                network=self.dexes.network.value
            ),
            intervals=IntervalConfig(
                top_pools_monitoring=self.intervals.top_pools_monitoring,
                ohlcv_collection=self.intervals.ohlcv_collection,
                trade_collection=self.intervals.trade_collection,
                watchlist_check=self.intervals.watchlist_check
            ),
            thresholds=ThresholdConfig(
                min_trade_volume_usd=self.thresholds.min_trade_volume_usd,
                max_retries=self.thresholds.max_retries,
                rate_limit_delay=self.thresholds.rate_limit_delay,
                backoff_factor=self.thresholds.backoff_factor
            ),
            timeframes=TimeframeConfig(
                ohlcv_default=self.timeframes.ohlcv_default.value,
                supported=[tf.value for tf in self.timeframes.supported]
            ),
            database=DatabaseConfig(
                url=self.database.url,
                pool_size=self.database.pool_size,
                echo=self.database.echo,
                timeout=self.database.timeout
            ),
            api=APIConfig(
                base_url=self.api.base_url,
                timeout=self.api.timeout,
                max_concurrent=self.api.max_concurrent,
                rate_limit_delay=self.api.rate_limit_delay
            ),
            error_handling=ErrorConfig(
                max_retries=self.error_handling.max_retries,
                backoff_factor=self.error_handling.backoff_factor,
                circuit_breaker_threshold=self.error_handling.circuit_breaker_threshold,
                circuit_breaker_timeout=self.error_handling.circuit_breaker_timeout
            ),
            watchlist=WatchlistConfig(
                file_path=self.watchlist.file_path,
                check_interval=self.watchlist.check_interval,
                auto_add_new_tokens=self.watchlist.auto_add_new_tokens,
                remove_inactive_tokens=self.watchlist.remove_inactive_tokens
            )
        )


def validate_config_dict(config_data: Dict[str, Any]) -> CollectionConfigValidator:
    """
    Validate configuration dictionary using Pydantic.
    
    Args:
        config_data: Configuration dictionary
        
    Returns:
        Validated configuration object
        
    Raises:
        ValueError: If validation fails
    """
    try:
        return CollectionConfigValidator(**config_data)
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")


def get_env_var_mappings() -> Dict[str, str]:
    """
    Get mapping of environment variables to configuration paths.
    
    Returns:
        Dictionary mapping environment variable names to config paths
    """
    return {
        # Database configuration
        'GECKO_DB_URL': 'database.url',
        'GECKO_DB_POOL_SIZE': 'database.pool_size',
        'GECKO_DB_ECHO': 'database.echo',
        'GECKO_DB_TIMEOUT': 'database.timeout',
        
        # API configuration
        'GECKO_API_BASE_URL': 'api.base_url',
        'GECKO_API_TIMEOUT': 'api.timeout',
        'GECKO_API_MAX_CONCURRENT': 'api.max_concurrent',
        'GECKO_API_RATE_LIMIT_DELAY': 'api.rate_limit_delay',
        
        # DEX configuration
        'GECKO_DEX_TARGETS': 'dexes.targets',
        'GECKO_DEX_NETWORK': 'dexes.network',
        
        # Threshold configuration
        'GECKO_MIN_TRADE_VOLUME': 'thresholds.min_trade_volume_usd',
        'GECKO_MAX_RETRIES': 'thresholds.max_retries',
        'GECKO_RATE_LIMIT_DELAY': 'thresholds.rate_limit_delay',
        'GECKO_BACKOFF_FACTOR': 'thresholds.backoff_factor',
        
        # Interval configuration
        'GECKO_TOP_POOLS_INTERVAL': 'intervals.top_pools_monitoring',
        'GECKO_OHLCV_INTERVAL': 'intervals.ohlcv_collection',
        'GECKO_TRADE_INTERVAL': 'intervals.trade_collection',
        'GECKO_WATCHLIST_INTERVAL': 'intervals.watchlist_check',
        
        # Timeframe configuration
        'GECKO_OHLCV_DEFAULT_TIMEFRAME': 'timeframes.ohlcv_default',
        
        # Error handling configuration
        'GECKO_ERROR_MAX_RETRIES': 'error_handling.max_retries',
        'GECKO_ERROR_BACKOFF_FACTOR': 'error_handling.backoff_factor',
        'GECKO_ERROR_CIRCUIT_BREAKER_THRESHOLD': 'error_handling.circuit_breaker_threshold',
        'GECKO_ERROR_CIRCUIT_BREAKER_TIMEOUT': 'error_handling.circuit_breaker_timeout',
        
        # Watchlist configuration
        'GECKO_WATCHLIST_FILE_PATH': 'watchlist.file_path',
        'GECKO_WATCHLIST_CHECK_INTERVAL': 'watchlist.check_interval',
        'GECKO_WATCHLIST_AUTO_ADD': 'watchlist.auto_add_new_tokens',
        'GECKO_WATCHLIST_REMOVE_INACTIVE': 'watchlist.remove_inactive_tokens',
    }