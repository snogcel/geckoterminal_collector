# GeckoTerminal Data Collector

A Python-based system for collecting, storing, and managing cryptocurrency trading data from the GeckoTerminal API for Solana DEXes. The system supports real-time monitoring and historical data collection with robust error handling and data integrity controls.

## Features

- **Multi-DEX Support**: Monitor Heaven and PumpSwap DEXes with extensible architecture
- **Real-time Data Collection**: OHLCV, trade data, and pool monitoring
- **Historical Data**: Backfill up to 6 months of historical OHLCV data
- **Watchlist Management**: CSV-based token monitoring with automatic updates
- **QLib Integration**: Compatible data export for predictive modeling
- **Robust Error Handling**: Rate limiting, retry logic, and circuit breaker patterns
- **Configurable Scheduling**: Flexible intervals for different data collection types
- **Data Integrity**: Duplicate prevention and continuity verification

## Quick Start

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd gecko-terminal-collector
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up the database:
```bash
python -m gecko_terminal_collector.cli init-db
```

4. Configure the system:
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

5. Start the collector:
```bash
python -m gecko_terminal_collector.cli start
```

## Documentation

- [Installation Guide](installation.md) - Detailed installation instructions
- [Configuration Guide](configuration.md) - Complete configuration reference
- [User Guide](user_guide.md) - Operating the system
- [API Documentation](api_documentation.md) - Developer API reference
- [Developer Guide](developer_guide.md) - Extending the system
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [Operational Best Practices](operational_best_practices.md) - Production deployment

## Architecture

The system follows a modular architecture with these main components:

- **Configuration Manager**: Centralized configuration with hot-reloading
- **Data Collectors**: Modular collectors for different data types
- **Database Layer**: SQLAlchemy-based storage with integrity controls
- **Scheduler**: Configurable interval-based execution
- **QLib Integration**: Export interface for predictive modeling

## Supported Data Types

- **DEX Information**: Available DEXes and their metadata
- **Pool Data**: Top pools by volume and liquidity
- **OHLCV Data**: Open, High, Low, Close, Volume with multiple timeframes
- **Trade Data**: Individual trades with volume filtering
- **Token Information**: Detailed token metadata and relationships

## Requirements

- Python 3.8+
- SQLite (default) or PostgreSQL
- Internet connection for GeckoTerminal API access
- Minimum 1GB RAM for normal operation
- 10GB+ storage for historical data collection

## License

[Add your license information here]

## Support

For issues and questions:
- Check the [Troubleshooting Guide](troubleshooting.md)
- Review [Operational Best Practices](operational_best_practices.md)
- Open an issue on the project repository