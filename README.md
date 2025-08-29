# GeckoTerminal Data Collector

A Python-based system for collecting cryptocurrency trading data from the GeckoTerminal API for Solana DEXes with QLib integration support.

## Features

- **DEX Monitoring**: Monitor specific DEXes (Heaven and PumpSwap) with extensible architecture
- **Real-time Data Collection**: Collect OHLCV and trade data with configurable intervals
- **Watchlist Support**: Monitor specific tokens from CSV watchlist files
- **Historical Data**: Collect up to 6 months of historical OHLCV data
- **Data Integrity**: Robust duplicate prevention and data continuity checking
- **QLib Integration**: Compatible with QLib framework for predictive modeling
- **Configuration Management**: Hot-reloadable configuration with environment variable support

## Project Structure

```
gecko_terminal_collector/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── core.py              # Core data models
├── collectors/
│   ├── __init__.py
│   └── base.py              # Base collector interface
├── database/
│   ├── __init__.py
│   └── manager.py           # Database manager interface
└── config/
    ├── __init__.py
    ├── models.py            # Configuration data models
    └── manager.py           # Configuration manager
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd gecko-terminal-collector

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Configuration

The system uses YAML configuration files with environment variable overrides:

```yaml
# config.yaml
dexes:
  targets: ["heaven", "pumpswap"]
  network: "solana"

intervals:
  top_pools_monitoring: "1h"
  ohlcv_collection: "1h"
  trade_collection: "30m"
  watchlist_check: "1h"

thresholds:
  min_trade_volume_usd: 100
  max_retries: 3
  rate_limit_delay: 1.0

database:
  url: "sqlite:///gecko_data.db"
  pool_size: 10
  echo: false
```

## Environment Variables

- `GECKO_DB_URL`: Database connection URL
- `GECKO_API_TIMEOUT`: API request timeout
- `GECKO_MIN_TRADE_VOLUME`: Minimum trade volume filter
- `GECKO_MAX_RETRIES`: Maximum retry attempts
- `GECKO_DEX_TARGETS`: Comma-separated list of DEX targets
- `GECKO_NETWORK`: Target network (default: solana)

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black gecko_terminal_collector/
isort gecko_terminal_collector/

# Type checking
mypy gecko_terminal_collector/
```

## License

MIT License - see LICENSE file for details.