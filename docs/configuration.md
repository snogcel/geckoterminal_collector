# Configuration Guide

This guide covers all configuration options for the GeckoTerminal Data Collector system.

## Configuration File Structure

The system uses a YAML configuration file (`config.yaml`) with the following structure:

```yaml
# Example config.yaml
dexes:
  targets: ["heaven", "pumpswap"]
  network: "solana"

intervals:
  top_pools_monitoring: "1h"
  ohlcv_collection: "1h"
  trade_collection: "30m"
  watchlist_check: "1h"
  historical_backfill: "6h"

thresholds:
  min_trade_volume_usd: 100
  max_retries: 3
  rate_limit_delay: 1.0
  max_concurrent_requests: 5

timeframes:
  ohlcv_default: "1h"
  supported: ["1m", "5m", "15m", "1h", "4h", "12h", "1d"]

database:
  url: "sqlite:///gecko_data.db"
  pool_size: 10
  echo: false
  backup_enabled: true
  backup_interval: "24h"

api:
  base_url: "https://api.geckoterminal.com/api/v2"
  timeout: 30
  max_concurrent: 5
  retry_backoff_factor: 2.0

logging:
  level: "INFO"
  format: "structured"
  file_path: "logs/gecko_collector.log"
  max_file_size: "100MB"
  backup_count: 5

watchlist:
  file_path: "watchlist.csv"
  check_interval: "1h"
  auto_reload: true

qlib:
  export_path: "qlib_data"
  symbol_format: "gecko_{symbol}"
  timezone: "UTC"
```

## Configuration Sections

### DEX Configuration

```yaml
dexes:
  targets: ["heaven", "pumpswap"]  # DEXes to monitor
  network: "solana"                # Blockchain network
  auto_discover: false             # Auto-discover new DEXes
```

**Options:**
- `targets`: List of DEX identifiers to monitor
- `network`: Blockchain network (currently supports "solana")
- `auto_discover`: Whether to automatically discover new DEXes

### Interval Configuration

```yaml
intervals:
  top_pools_monitoring: "1h"    # How often to check top pools
  ohlcv_collection: "1h"        # OHLCV data collection frequency
  trade_collection: "30m"       # Trade data collection frequency
  watchlist_check: "1h"         # Watchlist file check frequency
  historical_backfill: "6h"     # Historical data backfill frequency
```

**Supported Interval Formats:**
- `"30s"` - 30 seconds
- `"5m"` - 5 minutes
- `"1h"` - 1 hour
- `"2h"` - 2 hours
- `"1d"` - 1 day

### Threshold Configuration

```yaml
thresholds:
  min_trade_volume_usd: 100      # Minimum trade volume to collect
  max_retries: 3                 # Maximum API retry attempts
  rate_limit_delay: 1.0          # Delay between API calls (seconds)
  max_concurrent_requests: 5     # Maximum concurrent API requests
  circuit_breaker_threshold: 10  # Failures before circuit breaker opens
  circuit_breaker_timeout: 300   # Circuit breaker timeout (seconds)
```

### Timeframe Configuration

```yaml
timeframes:
  ohlcv_default: "1h"                                    # Default OHLCV timeframe
  supported: ["1m", "5m", "15m", "1h", "4h", "12h", "1d"]  # Supported timeframes
  historical_limit: "6M"                                 # Historical data limit
```

**Supported Timeframes:**
- `"1m"` - 1 minute
- `"5m"` - 5 minutes
- `"15m"` - 15 minutes
- `"1h"` - 1 hour
- `"4h"` - 4 hours
- `"12h"` - 12 hours
- `"1d"` - 1 day

### Database Configuration

#### SQLite Configuration
```yaml
database:
  url: "sqlite:///gecko_data.db"
  pool_size: 10
  echo: false
  backup_enabled: true
  backup_interval: "24h"
  backup_retention: 7
```

#### PostgreSQL Configuration
```yaml
database:
  url: "postgresql://user:password@localhost/gecko_terminal_data"
  pool_size: 20
  max_overflow: 30
  pool_timeout: 30
  pool_recycle: 3600
  echo: false
```

**Database Options:**
- `url`: Database connection string
- `pool_size`: Connection pool size
- `max_overflow`: Maximum overflow connections
- `pool_timeout`: Connection timeout (seconds)
- `pool_recycle`: Connection recycle time (seconds)
- `echo`: Enable SQL query logging

### API Configuration

```yaml
api:
  base_url: "https://api.geckoterminal.com/api/v2"
  timeout: 30
  max_concurrent: 5
  retry_backoff_factor: 2.0
  user_agent: "GeckoTerminalCollector/1.0"
  headers:
    Accept: "application/json"
```

### Logging Configuration

```yaml
logging:
  level: "INFO"                              # Log level
  format: "structured"                       # Log format
  file_path: "logs/gecko_collector.log"      # Log file path
  max_file_size: "100MB"                     # Maximum log file size
  backup_count: 5                            # Number of backup files
  console_output: true                       # Enable console logging
  correlation_id: true                       # Include correlation IDs
```

**Log Levels:**
- `DEBUG`: Detailed debugging information
- `INFO`: General information messages
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical error messages

### Watchlist Configuration

```yaml
watchlist:
  file_path: "watchlist.csv"     # Path to watchlist CSV file
  check_interval: "1h"           # How often to check for changes
  auto_reload: true              # Automatically reload on changes
  backup_enabled: true           # Backup watchlist changes
```

### QLib Integration Configuration

```yaml
qlib:
  export_path: "qlib_data"              # Export directory
  symbol_format: "gecko_{symbol}"       # Symbol naming format
  timezone: "UTC"                       # Timezone for data export
  date_format: "%Y-%m-%d"              # Date format
  include_volume: true                  # Include volume data
  normalize_prices: false               # Normalize price data
```

## Environment Variable Overrides

You can override any configuration value using environment variables with the prefix `GECKO_`:

```bash
# Override database URL
export GECKO_DATABASE_URL="postgresql://user:pass@localhost/db"

# Override log level
export GECKO_LOGGING_LEVEL="DEBUG"

# Override API timeout
export GECKO_API_TIMEOUT=60

# Override collection intervals
export GECKO_INTERVALS_OHLCV_COLLECTION="30m"
```

**Environment Variable Naming:**
- Use `GECKO_` prefix
- Replace dots with underscores
- Convert to uppercase
- Example: `database.url` → `GECKO_DATABASE_URL`

## Configuration Validation

### Validate Configuration File
```bash
python -m gecko_terminal_collector.cli validate-config
```

### Check Configuration Values
```bash
python -m gecko_terminal_collector.cli show-config
```

### Test Configuration
```bash
python -m gecko_terminal_collector.cli test-config
```

## Hot Reloading

The system supports hot reloading for most configuration changes:

**Supported Hot Reload:**
- Collection intervals
- Thresholds and limits
- Logging configuration
- Watchlist settings

**Requires Restart:**
- Database configuration
- API base URL
- Core system settings

### Trigger Hot Reload
```bash
# Send SIGHUP signal to reload configuration
kill -HUP <process_id>

# Or use CLI command
python -m gecko_terminal_collector.cli reload-config
```

## Configuration Examples

### Development Configuration
```yaml
# config-dev.yaml
intervals:
  top_pools_monitoring: "5m"
  ohlcv_collection: "5m"
  trade_collection: "2m"

thresholds:
  min_trade_volume_usd: 10
  max_retries: 5

logging:
  level: "DEBUG"
  console_output: true

database:
  url: "sqlite:///dev_gecko_data.db"
  echo: true
```

### Production Configuration
```yaml
# config-prod.yaml
intervals:
  top_pools_monitoring: "1h"
  ohlcv_collection: "1h"
  trade_collection: "30m"

thresholds:
  min_trade_volume_usd: 1000
  max_concurrent_requests: 10

logging:
  level: "INFO"
  file_path: "/var/log/gecko-collector/app.log"
  console_output: false

database:
  url: "postgresql://gecko_user:${DB_PASSWORD}@db-server/gecko_terminal_data"
  pool_size: 50
```

### High-Volume Configuration
```yaml
# config-high-volume.yaml
intervals:
  ohlcv_collection: "15m"
  trade_collection: "10m"

thresholds:
  max_concurrent_requests: 20
  rate_limit_delay: 0.5

database:
  pool_size: 100
  max_overflow: 50

api:
  timeout: 60
  max_concurrent: 15
```

## Troubleshooting Configuration

### Common Configuration Issues

**Invalid Interval Format**
```yaml
# Wrong
intervals:
  ohlcv_collection: "1 hour"

# Correct
intervals:
  ohlcv_collection: "1h"
```

**Database Connection Issues**
```yaml
# Check connection string format
database:
  url: "postgresql://user:password@host:port/database"
```

**Timeframe Validation**
```yaml
# Ensure timeframes are supported
timeframes:
  supported: ["1m", "5m", "15m", "1h", "4h", "12h", "1d"]
```

### Configuration Debugging

1. **Validate Syntax**
```bash
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

2. **Check Environment Variables**
```bash
env | grep GECKO_
```

3. **Test Database Connection**
```bash
python -m gecko_terminal_collector.cli test-db
```

4. **Verify API Settings**
```bash
python -m gecko_terminal_collector.cli test-api
```

## Security Considerations

### Sensitive Information
- Store database passwords in environment variables
- Use secure file permissions for config files
- Avoid logging sensitive configuration values

### File Permissions
```bash
chmod 600 config.yaml  # Read/write for owner only
```

### Environment Variables for Secrets
```bash
export GECKO_DATABASE_PASSWORD="secure_password"
export GECKO_API_KEY="api_key_if_needed"
```

## Next Steps

After configuring the system:
1. Review the [User Guide](user_guide.md) for operation instructions
2. Check [Operational Best Practices](operational_best_practices.md) for production tips
3. See [Troubleshooting](troubleshooting.md) for common issues