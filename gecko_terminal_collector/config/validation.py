"""
Enhanced configuration validation using Pydantic.
"""

import re
from typing import List, Any, Dict, Optional
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
        """Validate interval format (e.g., '15s', '1h', '30m', '1d')."""
        if not v:
            raise ValueError("Interval cannot be empty")
        
        pattern = r'^(\d+)([smhd])$'
        match = re.match(pattern, v)
        if not match:
            raise ValueError(f"Invalid interval format: {v}. Expected format: number + unit (s/m/h/d)")
        
        number, unit = match.groups()
        number = int(number)
        
        # Validate reasonable ranges
        if unit == 's' and (number < 1 or number > 3600):  # 1 second to 1 hour
            raise ValueError(f"Second interval must be between 1 and 3600: {v}")
        elif unit == 'm' and (number < 1 or number > 1440):  # 1 minute to 24 hours
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
    high_volume_threshold_usd: Decimal = Field(
        default=Decimal("10000"),
        ge=Decimal("0"),
        description="Threshold for high-volume pool prioritization in USD"
    )


class TradeCollectionConfigValidator(BaseModel):
    """Pydantic model for trade collection configuration validation."""
    max_pools_per_batch: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Maximum pools to collect per batch (round-robin rotation)"
    )
    rotation_window_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Time window for fair rotation tracking in minutes"
    )


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


class RateLimitConfigValidator(BaseModel):
    """Pydantic model for rate limiting configuration validation."""
    requests_per_minute: int = Field(
        default=60,
        ge=1,
        le=1000,
        description="Maximum requests per minute"
    )
    daily_limit: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum requests per day"
    )
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
    backoff_base_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Base delay for exponential backoff"
    )
    backoff_max_delay: float = Field(
        default=300.0,
        ge=1.0,
        le=3600.0,
        description="Maximum delay for exponential backoff"
    )
    backoff_jitter_factor: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Jitter factor for backoff randomization"
    )
    state_file_dir: str = Field(
        default=".rate_limiter_state",
        description="Directory for rate limiter state files"
    )


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


class NetworkConfigValidator(BaseModel):
    """Pydantic model for network-specific configuration validation."""
    enabled: bool = Field(default=True, description="Enable collection for this network")
    interval: str = Field(default="30m", description="Collection interval for this network")
    rate_limit_key: str = Field(default=None, description="Rate limiter key for this network")
    signal_analysis: bool = Field(default=True, description="Enable signal analysis for collected pools")
    auto_watchlist_integration: bool = Field(default=False, description="Auto-add high-signal pools to watchlist")
    max_pages: Optional[int] = Field(default=None, ge=1, le=10, description="Network-specific max pages (overrides global)")
    page_delay: Optional[float] = Field(default=None, ge=0.1, le=10.0, description="Network-specific page delay (overrides global)")
    
    @field_validator('interval')
    @classmethod
    def validate_interval(cls, v):
        """Validate interval format."""
        return IntervalConfigValidator.validate_interval_format(v)
    
    @field_validator('rate_limit_key')
    @classmethod
    def validate_rate_limit_key(cls, v):
        """Validate rate limit key format."""
        if v and not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError(f"Invalid rate limit key format: {v}")
        return v


class SignalDetectionConfigValidator(BaseModel):
    """Pydantic model for signal detection configuration validation."""
    enabled: bool = Field(default=True, description="Enable signal detection system")
    min_signal_score: float = Field(default=60.0, ge=0.0, le=100.0, description="Minimum signal score for alerts")
    volume_spike_threshold: float = Field(default=2.0, ge=1.0, le=10.0, description="Volume spike detection threshold")
    liquidity_growth_threshold: float = Field(default=1.5, ge=1.0, le=10.0, description="Liquidity growth threshold")
    momentum_lookback_hours: int = Field(default=6, ge=1, le=168, description="Hours to look back for momentum")
    auto_watchlist_threshold: float = Field(default=75.0, ge=0.0, le=100.0, description="Signal score threshold for auto-watchlist")
    use_colors: bool = Field(default=True, description="Use colors in console output")
    use_emojis: bool = Field(default=True, description="Use emojis in console output")
    enable_file_alerts: bool = Field(default=True, description="Enable file-based alerts")
    enable_sound_alerts: bool = Field(default=False, description="Enable sound alerts")
    enable_desktop_notifications: bool = Field(default=False, description="Enable desktop notifications")
    enable_webhook: bool = Field(default=False, description="Enable webhook alerts")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for alerts")
    alerts_dir: str = Field(default="alerts", description="Directory for alert files")


class NewPoolsConfigValidator(BaseModel):
    """Pydantic model for new pools configuration validation."""
    networks: Dict[str, NetworkConfigValidator] = Field(
        default_factory=lambda: {
            "solana": NetworkConfigValidator(enabled=True, interval="30m", rate_limit_key="new_pools_solana"),
            "ethereum": NetworkConfigValidator(enabled=False, interval="30m", rate_limit_key="new_pools_ethereum")
        },
        description="Network-specific new pools collection configuration"
    )
    signal_detection: SignalDetectionConfigValidator = Field(
        default_factory=SignalDetectionConfigValidator,
        description="Signal detection configuration"
    )
    max_pages: int = Field(default=10, ge=1, le=10, description="Maximum pages to fetch per collection (1-10 for free tier)")
    page_delay: float = Field(default=1.0, ge=0.1, le=10.0, description="Delay between page requests in seconds")
    
    @field_validator('networks')
    @classmethod
    def validate_networks(cls, v):
        """Validate network configurations."""
        if not v:
            raise ValueError("At least one network must be configured")
        
        for network_name, network_config in v.items():
            if not network_name:
                raise ValueError("Network name cannot be empty")
            
            if not re.match(r'^[a-zA-Z0-9_]+$', network_name):
                raise ValueError(f"Invalid network name format: {network_name}")
        
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
    rate_limiting: RateLimitConfigValidator = Field(default_factory=RateLimitConfigValidator)
    watchlist: WatchlistConfigValidator = Field(default_factory=WatchlistConfigValidator)
    new_pools: NewPoolsConfigValidator = Field(default_factory=NewPoolsConfigValidator)
    trade_collection: TradeCollectionConfigValidator = Field(default_factory=TradeCollectionConfigValidator)
    
    model_config = {
        "validate_assignment": True,
        "extra": "forbid",  # Prevent extra fields
        "use_enum_values": True
    }
    
    def to_legacy_config(self) -> 'CollectionConfig':
        """Convert to legacy CollectionConfig format for backward compatibility."""
        from gecko_terminal_collector.config.models import (
            CollectionConfig, DEXConfig, IntervalConfig, ThresholdConfig,
            TimeframeConfig, DatabaseConfig, APIConfig, ErrorConfig, RateLimitConfig, WatchlistConfig,
            NewPoolsConfig, NetworkConfig, TradeCollectionConfig
        )
        
        # Convert new pools configuration
        new_pools_networks = {}
        for network_name, network_validator in self.new_pools.networks.items():
            new_pools_networks[network_name] = NetworkConfig(
                enabled=network_validator.enabled,
                interval=network_validator.interval,
                rate_limit_key=network_validator.rate_limit_key,
                signal_analysis=network_validator.signal_analysis,
                auto_watchlist_integration=network_validator.auto_watchlist_integration,
                max_pages=network_validator.max_pages,
                page_delay=network_validator.page_delay
            )
        
        # Convert signal detection configuration
        from gecko_terminal_collector.config.models import SignalDetectionConfig
        signal_detection = SignalDetectionConfig(
            enabled=self.new_pools.signal_detection.enabled,
            min_signal_score=self.new_pools.signal_detection.min_signal_score,
            volume_spike_threshold=self.new_pools.signal_detection.volume_spike_threshold,
            liquidity_growth_threshold=self.new_pools.signal_detection.liquidity_growth_threshold,
            momentum_lookback_hours=self.new_pools.signal_detection.momentum_lookback_hours,
            auto_watchlist_threshold=self.new_pools.signal_detection.auto_watchlist_threshold,
            use_colors=self.new_pools.signal_detection.use_colors,
            use_emojis=self.new_pools.signal_detection.use_emojis,
            enable_file_alerts=self.new_pools.signal_detection.enable_file_alerts,
            enable_sound_alerts=self.new_pools.signal_detection.enable_sound_alerts,
            enable_desktop_notifications=self.new_pools.signal_detection.enable_desktop_notifications,
            enable_webhook=self.new_pools.signal_detection.enable_webhook,
            webhook_url=self.new_pools.signal_detection.webhook_url,
            alerts_dir=self.new_pools.signal_detection.alerts_dir
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
                backoff_factor=self.thresholds.backoff_factor,
                high_volume_threshold_usd=self.thresholds.high_volume_threshold_usd
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
            rate_limiting=RateLimitConfig(
                requests_per_minute=self.rate_limiting.requests_per_minute,
                daily_limit=self.rate_limiting.daily_limit,
                circuit_breaker_threshold=self.rate_limiting.circuit_breaker_threshold,
                circuit_breaker_timeout=self.rate_limiting.circuit_breaker_timeout,
                backoff_base_delay=self.rate_limiting.backoff_base_delay,
                backoff_max_delay=self.rate_limiting.backoff_max_delay,
                backoff_jitter_factor=self.rate_limiting.backoff_jitter_factor,
                state_file_dir=self.rate_limiting.state_file_dir
            ),
            watchlist=WatchlistConfig(
                file_path=self.watchlist.file_path,
                check_interval=self.watchlist.check_interval,
                auto_add_new_tokens=self.watchlist.auto_add_new_tokens,
                remove_inactive_tokens=self.watchlist.remove_inactive_tokens
            ),
            new_pools=NewPoolsConfig(
                networks=new_pools_networks,
                signal_detection=signal_detection,
                max_pages=self.new_pools.max_pages,
                page_delay=self.new_pools.page_delay
            ),
            trade_collection=TradeCollectionConfig(
                max_pools_per_batch=self.trade_collection.max_pools_per_batch,
                rotation_window_minutes=self.trade_collection.rotation_window_minutes
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
        
        # Rate limiting configuration
        'GECKO_RATE_LIMIT_REQUESTS_PER_MINUTE': 'rate_limiting.requests_per_minute',
        'GECKO_RATE_LIMIT_DAILY_LIMIT': 'rate_limiting.daily_limit',
        'GECKO_RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD': 'rate_limiting.circuit_breaker_threshold',
        'GECKO_RATE_LIMIT_CIRCUIT_BREAKER_TIMEOUT': 'rate_limiting.circuit_breaker_timeout',
        'GECKO_RATE_LIMIT_BACKOFF_BASE_DELAY': 'rate_limiting.backoff_base_delay',
        'GECKO_RATE_LIMIT_BACKOFF_MAX_DELAY': 'rate_limiting.backoff_max_delay',
        'GECKO_RATE_LIMIT_BACKOFF_JITTER_FACTOR': 'rate_limiting.backoff_jitter_factor',
        'GECKO_RATE_LIMIT_STATE_FILE_DIR': 'rate_limiting.state_file_dir',
        
        # Watchlist configuration
        'GECKO_WATCHLIST_FILE_PATH': 'watchlist.file_path',
        'GECKO_WATCHLIST_CHECK_INTERVAL': 'watchlist.check_interval',
        'GECKO_WATCHLIST_AUTO_ADD': 'watchlist.auto_add_new_tokens',
        'GECKO_WATCHLIST_REMOVE_INACTIVE': 'watchlist.remove_inactive_tokens',
        
        # Trade collection configuration
        'GECKO_TRADE_MAX_POOLS_PER_BATCH': 'trade_collection.max_pools_per_batch',
        'GECKO_TRADE_ROTATION_WINDOW_MINUTES': 'trade_collection.rotation_window_minutes',
    }