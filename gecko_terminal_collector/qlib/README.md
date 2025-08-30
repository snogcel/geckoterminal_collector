# QLib Integration for GeckoTerminal Data

This module provides QLib-compatible data export functionality for the GeckoTerminal data collector, enabling seamless integration with QLib's predictive modeling framework.

## Overview

The QLib integration follows the crypto collector pattern established by QLib and provides:

- **Data Export**: Export OHLCV data in QLib-compatible formats
- **Symbol Management**: Generate QLib-compatible symbol names from pool information
- **Data Validation**: Validate exported data for QLib compatibility
- **CLI Interface**: Command-line tools for data export operations
- **Availability Reporting**: Generate reports on data availability and quality

## Quick Start

### Basic Usage

```python
import asyncio
from gecko_terminal_collector.qlib.exporter import QLibExporter
from gecko_terminal_collector.database.sqlalchemy_manager import SQLAlchemyDatabaseManager
from gecko_terminal_collector.config.models import DatabaseConfig

async def export_data():
    # Initialize database connection
    db_config = DatabaseConfig(url="sqlite:///demo_gecko_data.db")
    db_manager = SQLAlchemyDatabaseManager(db_config)
    await db_manager.initialize()
    
    # Create QLib exporter
    exporter = QLibExporter(db_manager)
    
    # Get available symbols
    symbols = await exporter.get_symbol_list()
    print(f"Available symbols: {symbols}")
    
    # Export OHLCV data
    df = await exporter.export_ohlcv_data(
        symbols=symbols[:5],  # First 5 symbols
        timeframe="1h",
        include_volume=True
    )
    
    print(f"Exported {len(df)} records")
    print(df.head())
    
    await db_manager.close()

# Run the example
asyncio.run(export_data())
```

### Export to Files

```python
# Export to QLib-compatible CSV files
result = await exporter.export_to_qlib_format(
    output_dir="./qlib_data",
    symbols=["HEAVEN_POOL_123", "PUMPSWAP_POOL_456"],
    start_date="2023-01-01",
    end_date="2023-12-31",
    timeframe="1h"
)

if result['success']:
    print(f"Exported {result['files_created']} files")
    print(f"Total records: {result['total_records']}")
```

## CLI Interface

The module includes a comprehensive CLI for data export operations:

### List Available Symbols

```bash
python -m gecko_terminal_collector.qlib.cli list-symbols \
    --network solana \
    --dex-filter heaven pumpswap \
    --active-only
```

### Export Data to CSV Files

```bash
python -m gecko_terminal_collector.qlib.cli export-data \
    --output-dir ./qlib_export \
    --start-date 2023-01-01 \
    --end-date 2023-12-31 \
    --timeframe 1h \
    --include-volume
```

### Generate Availability Report

```bash
python -m gecko_terminal_collector.qlib.cli availability-report \
    --timeframe 1h \
    --output-file availability.json
```

### Validate Export Directory

```bash
python -m gecko_terminal_collector.qlib.cli validate-export ./qlib_export
```

### Export Instruments List

```bash
python -m gecko_terminal_collector.qlib.cli export-instruments \
    --output-file instruments.csv
```

## Data Format

### OHLCV Data Format

The exported data follows QLib's standard format:

| Column   | Type     | Description                    |
|----------|----------|--------------------------------|
| datetime | datetime | Timestamp of the data point    |
| symbol   | string   | QLib-compatible symbol name    |
| open     | float    | Opening price in USD           |
| high     | float    | Highest price in USD           |
| low      | float    | Lowest price in USD            |
| close    | float    | Closing price in USD           |
| volume   | float    | Volume in USD (optional)       |

### Symbol Naming Convention

Symbols are generated using the format: `{DEX}_{POOL_IDENTIFIER}`

Examples:
- `HEAVEN_TEST_POOL_123`
- `PUMPSWAP_SOLANA_POOL_456`

## QLib Integration

### Using Exported Data with QLib

```python
import qlib
from qlib.data import D

# Initialize QLib with exported data
qlib.init(provider_uri="./qlib_export", region="crypto")

# Get available instruments
instruments = D.instruments(market="crypto")
print(f"Available instruments: {len(instruments)}")

# Load OHLCV data
data = D.features(
    instruments=instruments[:5],
    fields=["$open", "$high", "$low", "$close", "$volume"],
    start_time="2023-01-01",
    end_time="2023-12-31",
    freq="1h"
)

print("Data shape:", data.shape)
print(data.head())
```

### QLib Model Training Example

```python
from qlib.contrib.model.gbdt import LGBModel
from qlib.contrib.data.handler import Alpha158

# Create data handler
handler = Alpha158(
    instruments=instruments[:10],
    start_time="2023-01-01",
    end_time="2023-10-31",
    freq="1h"
)

# Train a model
model = LGBModel()
model.fit(
    handler.fetch(col_set="feature"), 
    handler.fetch(col_set="label")
)

# Make predictions
predictions = model.predict(handler.fetch(col_set="feature"))
```

## Data Validation

### Validate DataFrame

```python
from gecko_terminal_collector.qlib.utils import QLibDataValidator

# Validate exported data
validation_result = QLibDataValidator.validate_dataframe(df, require_volume=True)

if validation_result['is_valid']:
    print("✓ Data is valid for QLib")
else:
    print("✗ Data validation issues:")
    for error in validation_result['errors']:
        print(f"  - {error}")
```

### Validate Export Directory

```python
from gecko_terminal_collector.qlib.utils import validate_qlib_export_directory

result = validate_qlib_export_directory("./qlib_export")
print(f"Valid: {result['is_valid']}")
print(f"CSV files: {result['stats']['csv_files']}")
print(f"Symbols: {len(result['stats']['symbols'])}")
```

## Data Processing Utilities

### Resample Data

```python
from gecko_terminal_collector.qlib.utils import QLibDataProcessor

# Resample hourly data to daily
daily_data = QLibDataProcessor.resample_ohlcv(df, target_freq='1D')
```

### Fill Missing Data

```python
# Forward fill missing values
filled_data = QLibDataProcessor.fill_missing_data(df, method='forward')
```

### Calculate Returns

```python
# Add return columns
data_with_returns = QLibDataProcessor.calculate_returns(df)
print(data_with_returns[['close', 'return', 'log_return']].head())
```

## Configuration

### Supported Timeframes

The exporter supports all GeckoTerminal API timeframes:

- `1m` - 1 minute
- `5m` - 5 minutes  
- `15m` - 15 minutes
- `1h` - 1 hour
- `4h` - 4 hours
- `12h` - 12 hours
- `1d` - 1 day

### Database Configuration

```python
from gecko_terminal_collector.config.models import DatabaseConfig

# SQLite (default)
db_config = DatabaseConfig(url="sqlite:///gecko_data.db")

# PostgreSQL
db_config = DatabaseConfig(
    url="postgresql://user:password@localhost/gecko_data"
)
```

## Error Handling

The QLib exporter includes comprehensive error handling:

```python
try:
    df = await exporter.export_ohlcv_data(symbols=["INVALID_SYMBOL"])
except Exception as e:
    print(f"Export failed: {e}")
    
# Check availability first
availability = await exporter.get_data_availability_report(["SYMBOL"])
if availability["SYMBOL"]["available"]:
    df = await exporter.export_ohlcv_data(symbols=["SYMBOL"])
```

## Performance Considerations

- **Batch Processing**: Export multiple symbols in a single call for better performance
- **Date Ranges**: Limit date ranges for large datasets to avoid memory issues
- **Caching**: The exporter caches pool information to reduce database queries
- **Concurrent Exports**: Use separate exporter instances for concurrent operations

## Troubleshooting

### Common Issues

1. **No symbols found**: Ensure you have active watchlist entries in your database
2. **Empty data export**: Check that OHLCV data exists for the specified timeframe and date range
3. **Symbol not found**: Verify the symbol name matches the generated format
4. **Validation errors**: Check data integrity and format requirements

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now run your export operations
```

## API Reference

### QLibExporter

Main class for QLib data export operations.

#### Methods

- `get_symbol_list()` - Get available symbols
- `export_ohlcv_data()` - Export OHLCV data to DataFrame
- `export_to_qlib_format()` - Export data to CSV files
- `get_data_availability_report()` - Generate availability report

### QLibDataValidator

Utility class for data validation.

#### Methods

- `validate_dataframe()` - Validate DataFrame format
- `validate_export_directory()` - Validate export directory

### QLibDataProcessor

Utility class for data processing operations.

#### Methods

- `resample_ohlcv()` - Resample OHLCV data
- `fill_missing_data()` - Fill missing values
- `calculate_returns()` - Calculate price returns

## Contributing

When contributing to the QLib integration:

1. Follow the existing crypto collector patterns
2. Ensure all new functionality includes comprehensive tests
3. Update documentation for any API changes
4. Validate compatibility with QLib's expected formats

## License

This module is part of the GeckoTerminal Data Collector project and follows the same license terms.