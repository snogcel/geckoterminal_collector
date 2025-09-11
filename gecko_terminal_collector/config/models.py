"""
Configuration data models and validation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    url: str = "sqlite:///gecko_data.db"
    async_url: Optional[str] = None
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False
    timeout: int = 30


@dataclass
class APIConfig:
    """API client configuration."""
    base_url: str = "https://api.geckoterminal.com/api/v2"
    timeout: int = 30
    max_concurrent: int = 5
    rate_limit_delay: float = 1.0


@dataclass
class IntervalConfig:
    """Collection interval configuration."""
    top_pools_monitoring: str = "1h"
    ohlcv_collection: str = "1h"
    trade_collection: str = "30m"
    watchlist_check: str = "1h"


@dataclass
class ThresholdConfig:
    """Threshold and limit configuration."""
    min_trade_volume_usd: Decimal = Decimal("100")
    max_retries: int = 3
    rate_limit_delay: float = 1.0
    backoff_factor: float = 2.0


@dataclass
class TimeframeConfig:
    """OHLCV timeframe configuration."""
    ohlcv_default: str = "1h"
    supported: List[str] = field(default_factory=lambda: [
        "1m", "5m", "15m", "1h", "4h", "12h", "1d"
    ])


@dataclass
class DEXConfig:
    """DEX monitoring configuration."""
    targets: List[str] = field(default_factory=lambda: ["heaven", "pumpswap"])
    network: str = "solana"


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    requests_per_minute: int = 60
    daily_limit: int = 10000
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300  # seconds
    backoff_base_delay: float = 1.0
    backoff_max_delay: float = 300.0
    backoff_jitter_factor: float = 0.3
    state_file_dir: str = ".rate_limiter_state"


@dataclass
class ErrorConfig:
    """Error handling configuration."""
    max_retries: int = 3
    backoff_factor: float = 2.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300  # seconds


@dataclass
class WatchlistConfig:
    """Watchlist monitoring configuration."""
    file_path: str = "watchlist.csv"
    check_interval: str = "1h"
    auto_add_new_tokens: bool = True
    remove_inactive_tokens: bool = False


@dataclass
class NetworkConfig:
    """Network-specific configuration for new pools collection."""
    enabled: bool = True
    interval: str = "30m"
    rate_limit_key: Optional[str] = None


@dataclass
class NewPoolsConfig:
    """New pools collection configuration."""
    networks: Dict[str, NetworkConfig] = field(default_factory=lambda: {
        "solana": NetworkConfig(enabled=True, interval="30m", rate_limit_key="new_pools_solana"),
        "ethereum": NetworkConfig(enabled=False, interval="30m", rate_limit_key="new_pools_ethereum")
    })


@dataclass
class CollectionConfig:
    """Main collection configuration container."""
    dexes: DEXConfig = field(default_factory=DEXConfig)
    intervals: IntervalConfig = field(default_factory=IntervalConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    timeframes: TimeframeConfig = field(default_factory=TimeframeConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    api: APIConfig = field(default_factory=APIConfig)
    error_handling: ErrorConfig = field(default_factory=ErrorConfig)
    rate_limiting: RateLimitConfig = field(default_factory=RateLimitConfig)
    watchlist: WatchlistConfig = field(default_factory=WatchlistConfig)
    new_pools: NewPoolsConfig = field(default_factory=NewPoolsConfig)
    
    def validate(self) -> List[str]:
        """
        Validate configuration settings.
        
        Returns:
            List of validation errors, empty if valid
        """
        errors = []
        
        # Validate timeframes
        if self.timeframes.ohlcv_default not in self.timeframes.supported:
            errors.append(
                f"Default timeframe '{self.timeframes.ohlcv_default}' "
                f"not in supported timeframes: {self.timeframes.supported}"
            )
        
        # Validate DEX targets
        if not self.dexes.targets:
            errors.append("At least one DEX target must be specified")
        
        # Validate intervals (basic format check)
        interval_fields = [
            self.intervals.top_pools_monitoring,
            self.intervals.ohlcv_collection,
            self.intervals.trade_collection,
            self.intervals.watchlist_check
        ]
        
        for interval in interval_fields:
            if not self._is_valid_interval(interval):
                errors.append(f"Invalid interval format: {interval}")
        
        # Validate thresholds
        if self.thresholds.min_trade_volume_usd < 0:
            errors.append("Minimum trade volume must be non-negative")
        
        if self.thresholds.max_retries < 0:
            errors.append("Max retries must be non-negative")
        
        # Validate new pools configuration
        for network_name, network_config in self.new_pools.networks.items():
            if not network_name:
                errors.append("Network name cannot be empty")
            
            if not self._is_valid_interval(network_config.interval):
                errors.append(f"Invalid interval format for network '{network_name}': {network_config.interval}")
        
        return errors
    
    def _is_valid_interval(self, interval: str) -> bool:
        """Check if interval string has valid format (e.g., '1h', '30m')."""
        if not interval:
            return False
        
        # Basic validation - ends with 'm', 'h', or 'd'
        return interval[-1] in ['m', 'h', 'd'] and interval[:-1].isdigit()