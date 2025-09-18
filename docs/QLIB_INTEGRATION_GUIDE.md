# QLib Integration Guide

This guide explains how to integrate new pools history data with QLib for quantitative analysis and predictive modeling.

## Overview

The QLib integration provides:
- **Binary data export** compatible with QLib-Server
- **Incremental updates** for efficient data management
- **Health checking** to ensure data quality
- **Feature engineering** for ML-ready datasets
- **Time series optimization** for quantitative analysis

## Architecture

```
New Pools History Data → QLib Bin Export → QLib-Server → Analysis & Models
                     ↓
              Enhanced Database
              ├── OHLCV data
              ├── Technical indicators  
              ├── Signal analysis
              └── Feature vectors
```

## Quick Start

### 1. Export Data to QLib Format

```python
from qlib_integration import export_qlib_bin_data_cli

# Full export
result = await export_qlib_bin_data_cli(
    db_manager=your_db_manager,
    start_date="2024-01-01",
    end_date="2024-12-31",
    networks=['solana', 'ethereum'],
    qlib_dir="./qlib_data",
    freq="60min",
    mode="all"
)
```

### 2. Use with QLib

```python
import qlib
from qlib.data import D

# Initialize QLib
qlib.init(provider_uri="./qlib_data", region="us")

# Load data
instruments = D.instruments(market="all")
fields = ['$open', '$high', '$low', '$close', '$volume']
data = D.features(instruments[:10], fields, freq="60min")
```

### 3. Incremental Updates

```python
# Add new data without re-exporting everything
result = await export_qlib_bin_data_cli(
    db_manager=your_db_manager,
    start_date="2024-12-01",
    end_date="2024-12-31", 
    qlib_dir="./qlib_data",
    mode="update"  # Only new data
)
```

## Data Structure

### QLib Directory Layout

```
qlib_data/
├── calendars/
│   └── 60min.txt              # Trading calendar
├── instruments/
│   └── all.txt                # Symbol definitions
└── features/
    ├── pool_abc123_solana/    # Symbol directory
    │   ├── open.60min.bin     # OHLC data
    │   ├── high.60min.bin
    │   ├── low.60min.bin
    │   ├── close.60min.bin
    │   ├── volume.60min.bin
    │   ├── liquidity.60min.bin # Custom features
    │   ├── signal.60min.bin
    │   └── activity.60min.bin
    └── pool_def456_ethereum/
        └── ...
```

### Feature Mapping

| Database Field | QLib Field | Description |
|---------------|------------|-------------|
| `open_price_usd` | `open` | Opening price |
| `high_price_usd` | `high` | Highest price |
| `low_price_usd` | `low` | Lowest price |
| `close_price_usd` | `close` | Closing price |
| `volume_usd_h24` | `volume` | 24h volume |
| `reserve_in_usd` | `liquidity` | Pool liquidity |
| `signal_score` | `signal` | Signal strength |
| `activity_score` | `activity` | Activity score |
| `relative_strength_index` | `rsi` | RSI indicator |

## Export Modes

### All Mode (`mode="all"`)
- **Use case**: Initial setup, full data refresh
- **Process**: Exports complete dataset
- **Output**: Full QLib directory structure
- **Time**: Longer processing time

```python
# Full export example
result = await export_qlib_bin_data_cli(
    db_manager=db_manager,
    start_date="2024-01-01",
    end_date="2024-12-31",
    mode="all",
    backup_dir="./backup"  # Optional backup
)
```

### Update Mode (`mode="update"`)
- **Use case**: Daily/hourly data updates
- **Process**: Appends only new data
- **Output**: Updated bin files
- **Time**: Fast processing

```python
# Incremental update example
result = await export_qlib_bin_data_cli(
    db_manager=db_manager,
    start_date="2024-12-01",  # Only new data
    end_date="2024-12-31",
    mode="update"
)
```

### Fix Mode (`mode="fix"`)
- **Use case**: Adding missing symbols
- **Process**: Adds new symbols to existing data
- **Output**: Extended symbol coverage
- **Time**: Medium processing time

```python
# Fix missing symbols
result = await export_qlib_bin_data_cli(
    db_manager=db_manager,
    start_date="2024-01-01",
    end_date="2024-12-31",
    mode="fix"
)
```

## Data Quality & Health Checks

### Automated Health Checking

```python
from qlib_integration import QLibDataHealthChecker

checker = QLibDataHealthChecker(
    qlib_dir="./qlib_data",
    freq="60min",
    large_step_threshold_price=0.5,
    large_step_threshold_volume=3.0
)

results = checker.run_health_check()

if results['overall_health'] == 'HEALTHY':
    print("✅ Data is healthy")
else:
    print("⚠️ Issues found:", results)
```

### Health Check Categories

1. **Required Columns**: Ensures OHLCV data is present
2. **Missing Data**: Identifies gaps in time series
3. **Large Step Changes**: Detects unrealistic price/volume jumps
4. **Data Consistency**: Validates data integrity

## CLI Usage

### Export Commands

```bash
# Full export
python -m cli_enhancements new-pools-enhanced export-qlib-bin \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --qlib-dir ./qlib_data \
    --freq 60min \
    --mode all

# Incremental update
python -m cli_enhancements new-pools-enhanced export-qlib-bin \
    --start-date 2024-12-01 \
    --end-date 2024-12-31 \
    --mode update

# Health check
python -m cli_enhancements new-pools-enhanced check-qlib-health \
    --qlib-dir ./qlib_data \
    --freq 60min
```

## Integration with QLib Workflows

### Basic Analysis

```python
import qlib
from qlib.data import D
import pandas as pd

# Initialize
qlib.init(provider_uri="./qlib_data", region="us")

# Get new pools data
instruments = D.instruments(market="all")
fields = ['$open', '$high', '$low', '$close', '$volume', '$signal', '$activity']

# Load recent data
data = D.features(
    instruments=instruments,
    fields=fields,
    start_time='2024-12-01',
    end_time='2024-12-31',
    freq='60min'
)

# Find high-signal pools
high_signal_pools = data[data['$signal'] > 80].index.get_level_values(0).unique()
print(f"High signal pools: {len(high_signal_pools)}")
```

### Strategy Backtesting

```python
from qlib.contrib.strategy import TopkDropoutStrategy
from qlib.backtest import backtest
from qlib.contrib.evaluate import risk_analysis

# Define strategy
strategy = TopkDropoutStrategy(
    signal="$signal",  # Use our signal score
    topk=20,           # Top 20 pools
    n_drop=2           # Drop 2 worst performers
)

# Run backtest
portfolio_metric_dict, indicator_dict = backtest(
    start_time='2024-06-01',
    end_time='2024-12-31',
    strategy=strategy,
    executor=executor_config,
    benchmark=None
)

# Analyze results
analysis = risk_analysis(portfolio_metric_dict)
print(analysis)
```

### Model Training

```python
from qlib.contrib.model.gbdt import LGBModel
from qlib.data.dataset import DatasetH

# Prepare dataset
dataset = DatasetH(
    handler={
        "class": "Alpha158",
        "kwargs": {
            "start_time": "2024-01-01",
            "end_time": "2024-10-31",
            "instruments": "all"
        }
    },
    segments={
        "train": ("2024-01-01", "2024-08-31"),
        "valid": ("2024-09-01", "2024-10-31"),
        "test": ("2024-11-01", "2024-12-31")
    }
)

# Train model
model = LGBModel()
model.fit(dataset)

# Make predictions
predictions = model.predict(dataset)
```

## Performance Optimization

### Batch Processing

```python
# Process data in batches for large datasets
async def batch_export(db_manager, start_date, end_date, batch_days=30):
    current_date = start_date
    
    while current_date < end_date:
        batch_end = min(current_date + timedelta(days=batch_days), end_date)
        
        result = await export_qlib_bin_data_cli(
            db_manager=db_manager,
            start_date=current_date.strftime('%Y-%m-%d'),
            end_date=batch_end.strftime('%Y-%m-%d'),
            mode="update" if current_date > start_date else "all"
        )
        
        current_date = batch_end
```

### Parallel Processing

```python
# Configure parallel processing
exporter = QLibBinDataExporter(
    db_manager=db_manager,
    qlib_dir="./qlib_data",
    max_workers=8  # Adjust based on system
)
```

## Troubleshooting

### Common Issues

1. **Missing Calendar Entries**
   ```python
   # Check calendar file
   with open("./qlib_data/calendars/60min.txt") as f:
       calendar_entries = f.readlines()
   print(f"Calendar entries: {len(calendar_entries)}")
   ```

2. **Symbol Directory Issues**
   ```python
   # Check symbol directories
   features_dir = Path("./qlib_data/features")
   symbols = list(features_dir.iterdir())
   print(f"Symbols: {len(symbols)}")
   ```

3. **Bin File Corruption**
   ```python
   # Validate bin files
   import numpy as np
   
   bin_file = Path("./qlib_data/features/symbol/open.60min.bin")
   data = np.fromfile(bin_file, dtype="<f")
   print(f"Data points: {len(data)}")
   ```

### Performance Issues

- **Large datasets**: Use batch processing
- **Memory usage**: Reduce `max_workers`
- **Disk space**: Implement data retention policies
- **Update frequency**: Use incremental updates

## Best Practices

### Data Management

1. **Regular backups** before major updates
2. **Incremental updates** for daily operations
3. **Health checks** after each export
4. **Data retention** policies for old data

### Performance

1. **Batch processing** for large date ranges
2. **Parallel processing** for multiple symbols
3. **Incremental updates** to minimize processing time
4. **Index optimization** in database queries

### Quality Assurance

1. **Validate exports** with health checks
2. **Monitor data gaps** in time series
3. **Check for outliers** in price/volume data
4. **Verify symbol mappings** are correct

## Advanced Usage

### Custom Feature Engineering

```python
# Add custom features to the export
class CustomQLibExporter(QLibBinDataExporter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add custom feature mappings
        self.feature_mapping.update({
            'custom_momentum': 'momentum',
            'custom_volatility': 'vol',
            'whale_activity': 'whale'
        })
```

### Integration with External Data

```python
# Combine with external market data
async def enhanced_export(db_manager, external_data_source):
    # Export pools data
    result = await export_qlib_bin_data_cli(...)
    
    # Add external market data
    market_data = await external_data_source.get_market_data()
    
    # Merge and re-export
    # ... custom merging logic
```

This integration provides a robust foundation for quantitative analysis of new pools data using QLib's powerful framework.