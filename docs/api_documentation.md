# API Documentation

This document provides comprehensive API documentation for the GeckoTerminal Data Collector system, including internal APIs, data models, and integration interfaces.

## Table of Contents

- [Core APIs](#core-apis)
- [Data Models](#data-models)
- [Collection APIs](#collection-apis)
- [Database APIs](#database-apis)
- [Configuration APIs](#configuration-apis)
- [QLib Integration APIs](#qlib-integration-apis)
- [Error Handling](#error-handling)
- [Examples](#examples)

## Core APIs

### ConfigManager

Central configuration management with hot-reloading support.

```python
from gecko_terminal_collector.config import ConfigManager

class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize configuration manager."""
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        
    def reload_config(self) -> bool:
        """Reload configuration with validation."""
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        
    def validate(self) -> ValidationResult:
        """Validate current configuration."""
        
    def watch_changes(self, callback: Callable) -> None:
        """Watch for configuration file changes."""
```

**Example Usage:**
```python
config = ConfigManager("config.yaml")
db_url = config.get("database.url")
intervals = config.get("intervals")

# Validate configuration
result = config.validate()
if not result.is_valid:
    print(f"Configuration errors: {result.errors}")
```

### DatabaseManager

Database abstraction layer with integrity controls.

```python
from gecko_terminal_collector.database import DatabaseManager

class DatabaseManager:
    def __init__(self, config: DatabaseConfig):
        """Initialize database manager."""
        
    async def store_ohlcv_data(self, data: List[OHLCVRecord]) -> int:
        """Store OHLCV data with duplicate prevention."""
        
    async def store_trade_data(self, data: List[TradeRecord]) -> int:
        """Store trade data with duplicate prevention."""
        
    async def store_pool_data(self, data: List[Pool]) -> int:
        """Store pool information."""
        
    async def get_ohlcv_data(self, pool_id: str, timeframe: str, 
                           start: datetime, end: datetime) -> List[OHLCVRecord]:
        """Retrieve OHLCV data for specified period."""
        
    async def get_trade_data(self, pool_id: str, 
                           start: datetime, end: datetime) -> List[TradeRecord]:
        """Retrieve trade data for specified period."""
        
    async def get_data_gaps(self, pool_id: str, timeframe: str,
                          start: datetime, end: datetime) -> List[Gap]:
        """Identify missing data intervals."""
        
    async def get_collection_metadata(self, collector_type: str) -> CollectionMetadata:
        """Get collection execution metadata."""
        
    async def update_collection_metadata(self, collector_type: str, 
                                       metadata: CollectionMetadata) -> None:
        """Update collection execution metadata."""
```

**Example Usage:**
```python
db_manager = DatabaseManager(config.database)

# Store OHLCV data
ohlcv_records = [OHLCVRecord(...), ...]
stored_count = await db_manager.store_ohlcv_data(ohlcv_records)

# Check for data gaps
gaps = await db_manager.get_data_gaps(
    pool_id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
    timeframe="1h",
    start=datetime(2024, 1, 1),
    end=datetime(2024, 8, 30)
)
```

## Data Models

### Core Data Models

#### Pool
```python
@dataclass
class Pool:
    id: str                    # GeckoTerminal pool ID
    address: str               # Pool contract address
    name: str                  # Pool display name
    dex_id: str               # DEX identifier
    base_token_id: str        # Base token ID
    quote_token_id: str       # Quote token ID
    reserve_usd: Decimal      # Total reserve in USD
    created_at: datetime      # Pool creation time
    last_updated: datetime    # Last update time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Pool':
        """Create from dictionary."""
```

#### Token
```python
@dataclass
class Token:
    id: str                           # GeckoTerminal token ID
    address: str                      # Token contract address
    name: str                         # Token name
    symbol: str                       # Token symbol
    decimals: int                     # Token decimals
    network: str                      # Blockchain network
    price_usd: Optional[Decimal]      # Current price in USD
    last_updated: datetime            # Last update time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Token':
        """Create from dictionary."""
```

#### OHLCVRecord
```python
@dataclass
class OHLCVRecord:
    pool_id: str              # Pool identifier
    timeframe: str            # Timeframe (1m, 5m, 1h, etc.)
    timestamp: int            # Unix timestamp
    open_price: Decimal       # Opening price
    high_price: Decimal       # Highest price
    low_price: Decimal        # Lowest price
    close_price: Decimal      # Closing price
    volume_usd: Decimal       # Volume in USD
    datetime: datetime        # Datetime representation
    
    def validate(self) -> ValidationResult:
        """Validate OHLCV data integrity."""
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        
    @classmethod
    def from_api_response(cls, data: Dict[str, Any], pool_id: str, 
                         timeframe: str) -> 'OHLCVRecord':
        """Create from API response data."""
```

#### TradeRecord
```python
@dataclass
class TradeRecord:
    id: str                   # Trade identifier
    pool_id: str             # Pool identifier
    block_number: int        # Block number
    tx_hash: str             # Transaction hash
    tx_from_address: str     # Transaction sender
    from_token_amount: Decimal  # Input token amount
    to_token_amount: Decimal    # Output token amount
    price_usd: Decimal       # Trade price in USD
    volume_usd: Decimal      # Trade volume in USD
    side: str                # Trade side (buy/sell)
    block_timestamp: datetime # Block timestamp
    
    def validate(self) -> ValidationResult:
        """Validate trade data."""
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'TradeRecord':
        """Create from API response data."""
```

### Result Models

#### CollectionResult
```python
@dataclass
class CollectionResult:
    collector_type: str       # Type of collector
    success: bool            # Collection success status
    records_collected: int   # Number of records collected
    records_stored: int      # Number of records stored
    errors: List[str]        # Collection errors
    duration: float          # Collection duration (seconds)
    timestamp: datetime      # Collection timestamp
    metadata: Dict[str, Any] # Additional metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
```

#### ValidationResult
```python
@dataclass
class ValidationResult:
    is_valid: bool           # Validation success
    errors: List[str]        # Validation errors
    warnings: List[str]      # Validation warnings
    
    def add_error(self, error: str) -> None:
        """Add validation error."""
        
    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
```

## Collection APIs

### BaseDataCollector

Abstract base class for all data collectors.

```python
from gecko_terminal_collector.collectors import BaseDataCollector

class BaseDataCollector(ABC):
    def __init__(self, config: CollectionConfig, db_manager: DatabaseManager):
        """Initialize collector."""
        
    @abstractmethod
    async def collect(self) -> CollectionResult:
        """Perform data collection."""
        
    @abstractmethod
    def get_collection_key(self) -> str:
        """Get unique collection identifier."""
        
    async def validate_data(self, data: List[Any]) -> ValidationResult:
        """Validate collected data."""
        
    async def handle_error(self, error: Exception, context: str) -> None:
        """Handle collection errors."""
        
    def get_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff."""
```

### Specific Collectors

#### DEXMonitoringCollector
```python
class DEXMonitoringCollector(BaseDataCollector):
    async def collect(self) -> CollectionResult:
        """Collect available DEX information."""
        
    async def get_available_dexes(self, network: str) -> List[Dict[str, Any]]:
        """Get available DEXes for network."""
        
    async def validate_dex_availability(self, dex_ids: List[str]) -> ValidationResult:
        """Validate DEX availability."""
```

#### TopPoolsCollector
```python
class TopPoolsCollector(BaseDataCollector):
    async def collect(self) -> CollectionResult:
        """Collect top pools data."""
        
    async def get_top_pools_by_dex(self, network: str, dex_id: str, 
                                  limit: int = 100) -> List[Pool]:
        """Get top pools for specific DEX."""
        
    async def process_pool_data(self, pools_data: List[Dict[str, Any]]) -> List[Pool]:
        """Process raw pool data from API."""
```

#### OHLCVCollector
```python
class OHLCVCollector(BaseDataCollector):
    async def collect(self) -> CollectionResult:
        """Collect OHLCV data for watchlist tokens."""
        
    async def get_ohlcv_data(self, pool_id: str, timeframe: str, 
                           limit: int = 1000) -> List[OHLCVRecord]:
        """Get OHLCV data for specific pool."""
        
    async def backfill_missing_data(self, pool_id: str, timeframe: str,
                                  gaps: List[Gap]) -> CollectionResult:
        """Backfill missing OHLCV data."""
```

#### TradeCollector
```python
class TradeCollector(BaseDataCollector):
    async def collect(self) -> CollectionResult:
        """Collect trade data for watchlist tokens."""
        
    async def get_trade_data(self, pool_id: str, limit: int = 300) -> List[TradeRecord]:
        """Get trade data for specific pool."""
        
    async def filter_trades_by_volume(self, trades: List[TradeRecord], 
                                    min_volume_usd: Decimal) -> List[TradeRecord]:
        """Filter trades by minimum volume."""
```

#### WatchlistCollector
```python
class WatchlistCollector(BaseDataCollector):
    async def collect(self) -> CollectionResult:
        """Process watchlist and collect token data."""
        
    async def load_watchlist(self, file_path: str) -> List[WatchlistEntry]:
        """Load watchlist from CSV file."""
        
    async def get_multiple_pools_data(self, pool_ids: List[str]) -> List[Pool]:
        """Get data for multiple pools efficiently."""
        
    async def get_token_data(self, network_address: str) -> Token:
        """Get individual token data."""
```

## Database APIs

### Query Interface

```python
class DatabaseQuery:
    def __init__(self, db_manager: DatabaseManager):
        """Initialize query interface."""
        
    async def get_pools(self, dex_id: Optional[str] = None, 
                       limit: int = 100) -> List[Pool]:
        """Get pools with optional filtering."""
        
    async def get_ohlcv_range(self, pool_id: str, timeframe: str,
                            start: datetime, end: datetime) -> List[OHLCVRecord]:
        """Get OHLCV data for date range."""
        
    async def get_trades_range(self, pool_id: str,
                             start: datetime, end: datetime) -> List[TradeRecord]:
        """Get trades for date range."""
        
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        
    async def get_data_coverage(self, pool_id: str) -> Dict[str, Any]:
        """Get data coverage statistics for pool."""
```

### Statistics Interface

```python
class DatabaseStats:
    def __init__(self, db_manager: DatabaseManager):
        """Initialize statistics interface."""
        
    async def get_table_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tables."""
        
    async def get_collection_performance(self) -> Dict[str, Any]:
        """Get collection performance metrics."""
        
    async def get_data_quality_report(self) -> Dict[str, Any]:
        """Generate data quality report."""
        
    async def get_storage_usage(self) -> Dict[str, Any]:
        """Get database storage usage statistics."""
```

## Configuration APIs

### Configuration Schema

```python
class ConfigSchema:
    @staticmethod
    def validate_intervals(intervals: Dict[str, str]) -> ValidationResult:
        """Validate interval configuration."""
        
    @staticmethod
    def validate_thresholds(thresholds: Dict[str, Any]) -> ValidationResult:
        """Validate threshold configuration."""
        
    @staticmethod
    def validate_database_config(db_config: Dict[str, Any]) -> ValidationResult:
        """Validate database configuration."""
        
    @staticmethod
    def validate_timeframes(timeframes: Dict[str, Any]) -> ValidationResult:
        """Validate timeframe configuration."""
```

### Environment Integration

```python
class EnvironmentConfig:
    @staticmethod
    def load_from_environment() -> Dict[str, Any]:
        """Load configuration from environment variables."""
        
    @staticmethod
    def override_config(config: Dict[str, Any], 
                       env_overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides."""
        
    @staticmethod
    def get_env_var_name(config_key: str) -> str:
        """Convert config key to environment variable name."""
```

## QLib Integration APIs

### QLibExporter

```python
class QLibExporter:
    def __init__(self, db_manager: DatabaseManager, config: QLibConfig):
        """Initialize QLib exporter."""
        
    async def export_ohlcv_data(self, symbols: List[str], 
                              start_date: datetime, end_date: datetime,
                              timeframe: str = "1d") -> pd.DataFrame:
        """Export OHLCV data in QLib format."""
        
    async def export_symbol_list(self) -> List[str]:
        """Export available symbols for QLib."""
        
    async def export_calendar(self, start_date: datetime, 
                            end_date: datetime) -> List[datetime]:
        """Export trading calendar for QLib."""
        
    async def validate_qlib_format(self, data: pd.DataFrame) -> ValidationResult:
        """Validate data format for QLib compatibility."""
        
    def get_symbol_mapping(self) -> Dict[str, str]:
        """Get symbol mapping for QLib format."""
```

### Data Format Conversion

```python
class QLibFormatter:
    @staticmethod
    def format_ohlcv_dataframe(records: List[OHLCVRecord]) -> pd.DataFrame:
        """Format OHLCV records as QLib DataFrame."""
        
    @staticmethod
    def normalize_symbol_names(symbols: List[str]) -> List[str]:
        """Normalize symbol names for QLib."""
        
    @staticmethod
    def handle_missing_data(df: pd.DataFrame, method: str = "forward_fill") -> pd.DataFrame:
        """Handle missing data in QLib format."""
```

## Error Handling

### Exception Classes

```python
class GeckoCollectorError(Exception):
    """Base exception for collector errors."""
    
class APIError(GeckoCollectorError):
    """API-related errors."""
    
class DatabaseError(GeckoCollectorError):
    """Database-related errors."""
    
class ConfigurationError(GeckoCollectorError):
    """Configuration-related errors."""
    
class ValidationError(GeckoCollectorError):
    """Data validation errors."""
    
class CollectionError(GeckoCollectorError):
    """Data collection errors."""
```

### Error Handler

```python
class ErrorHandler:
    def __init__(self, config: ErrorConfig):
        """Initialize error handler."""
        
    async def handle_api_error(self, error: APIError, context: str) -> RecoveryAction:
        """Handle API errors with appropriate recovery."""
        
    async def handle_database_error(self, error: DatabaseError, context: str) -> RecoveryAction:
        """Handle database errors with recovery."""
        
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if operation should be retried."""
        
    def get_retry_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """Calculate retry delay with exponential backoff."""
```

## Examples

### Basic Collection Example

```python
from gecko_terminal_collector.config import ConfigManager
from gecko_terminal_collector.database import DatabaseManager
from gecko_terminal_collector.collectors import OHLCVCollector

# Initialize components
config = ConfigManager("config.yaml")
db_manager = DatabaseManager(config.get("database"))
collector = OHLCVCollector(config.get("collection"), db_manager)

# Perform collection
result = await collector.collect()
print(f"Collected {result.records_collected} OHLCV records")
```

### Data Query Example

```python
from gecko_terminal_collector.database import DatabaseQuery
from datetime import datetime, timedelta

# Initialize query interface
query = DatabaseQuery(db_manager)

# Get OHLCV data for last 7 days
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

ohlcv_data = await query.get_ohlcv_range(
    pool_id="solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP",
    timeframe="1h",
    start=start_date,
    end=end_date
)

print(f"Retrieved {len(ohlcv_data)} OHLCV records")
```

### QLib Export Example

```python
from gecko_terminal_collector.qlib import QLibExporter
import pandas as pd

# Initialize exporter
exporter = QLibExporter(db_manager, config.get("qlib"))

# Export data for QLib
symbols = ["BONK", "SOL"]
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 8, 30)

qlib_data = await exporter.export_ohlcv_data(
    symbols=symbols,
    start_date=start_date,
    end_date=end_date,
    timeframe="1d"
)

# Save to file
qlib_data.to_csv("qlib_export.csv")
```

### Custom Collector Example

```python
from gecko_terminal_collector.collectors import BaseDataCollector

class CustomCollector(BaseDataCollector):
    async def collect(self) -> CollectionResult:
        """Custom collection logic."""
        try:
            # Implement custom collection logic
            data = await self.fetch_custom_data()
            
            # Validate data
            validation = await self.validate_data(data)
            if not validation.is_valid:
                return CollectionResult(
                    collector_type=self.get_collection_key(),
                    success=False,
                    errors=validation.errors
                )
            
            # Store data
            stored_count = await self.db_manager.store_custom_data(data)
            
            return CollectionResult(
                collector_type=self.get_collection_key(),
                success=True,
                records_collected=len(data),
                records_stored=stored_count
            )
            
        except Exception as e:
            await self.handle_error(e, "custom_collection")
            return CollectionResult(
                collector_type=self.get_collection_key(),
                success=False,
                errors=[str(e)]
            )
    
    def get_collection_key(self) -> str:
        return "custom_collector"
    
    async def fetch_custom_data(self) -> List[Any]:
        """Implement custom data fetching logic."""
        pass
```

## API Versioning

The API follows semantic versioning:
- Major version: Breaking changes
- Minor version: New features, backward compatible
- Patch version: Bug fixes, backward compatible

Current API version: `1.0.0`

## Rate Limiting

All API calls respect rate limiting:
- Default: 100 requests per minute
- Configurable via `api.rate_limit` setting
- Automatic backoff on rate limit exceeded
- Circuit breaker pattern for repeated failures

## Authentication

Currently, the GeckoTerminal API doesn't require authentication, but the system is designed to support API keys if needed in the future:

```python
# Future API key support
api_config = {
    "api_key": "your_api_key",
    "headers": {
        "Authorization": "Bearer your_api_key"
    }
}
```

For more detailed examples and advanced usage, see the [Developer Guide](developer_guide.md).