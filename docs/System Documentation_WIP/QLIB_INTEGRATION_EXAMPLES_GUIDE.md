# QLib Integration Examples Guide

This guide provides practical examples of how to access and use your collected historical OHLCV data with QLib methods for quantitative analysis and trading strategies.

## 📁 Available Example Scripts

### 1. `simple_qlib_integration.py` - Basic Data Access
**Purpose**: Simple examples for accessing your historical data through QLib methods.

**Key Features**:
- Get historical data for watchlist symbols
- Create QLib-compatible datasets
- Analyze symbol performance
- Check data quality

**Usage**:
```bash
# Run all examples
python simple_qlib_integration.py

# Or run specific examples in the script
```

**What it shows**:
- How to retrieve your historical OHLCV data
- Basic performance analysis of your symbols
- Data quality checks
- Creating QLib datasets for further analysis

### 2. `qlib_historical_data_example.py` - Advanced Integration
**Purpose**: Comprehensive examples with advanced QLib integration features.

**Key Features**:
- Advanced symbol mapping
- Technical indicator calculation
- Data availability reporting
- Export to QLib binary format

**Usage**:
```bash
# Run all examples
python qlib_historical_data_example.py

# Run specific examples
python qlib_historical_data_example.py basic      # Basic data access
python qlib_historical_data_example.py analysis  # Symbol analysis
python qlib_historical_data_example.py qlib      # Create QLib dataset
python qlib_historical_data_example.py report    # Data availability report
```

### 3. `qlib_trading_strategy_example.py` - Trading Strategies
**Purpose**: Demonstrates how to create and backtest trading strategies using your historical data.

**Key Features**:
- Signal generation based on technical indicators
- Strategy backtesting
- Performance analysis
- Signal effectiveness evaluation

**Usage**:
```bash
python qlib_trading_strategy_example.py
```

**What it includes**:
- RSI-based trading signals
- Volume-based confirmations
- Simple backtesting engine
- Performance metrics calculation

## 🚀 Quick Start Examples

### Example 1: Get Your Historical Data

```python
import asyncio
from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager
from gecko_terminal_collector.qlib.exporter import QLibExporter

async def get_my_data():
    # Initialize
    config = ConfigManager().load_config()
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    qlib_exporter = QLibExporter(db_manager)
    
    # Get your watchlist symbols
    symbols = await qlib_exporter.get_symbol_list(active_only=True)
    print(f"Your symbols: {symbols}")
    
    # Get recent hourly data
    df = await qlib_exporter.export_ohlcv_data(
        symbols=symbols,
        start_date="2025-09-15",
        end_date="2025-09-19",
        timeframe="1h"
    )
    
    print(f"Data shape: {df.shape}")
    print(df.head())
    
    await db_manager.close()

# Run it
asyncio.run(get_my_data())
```

### Example 2: Create QLib Dataset

```python
async def create_qlib_dataset():
    # ... initialization code ...
    
    # Export to QLib format
    result = await qlib_exporter.export_to_qlib_format(
        output_dir="./my_crypto_data",
        symbols=None,  # All your watchlist symbols
        start_date="2025-09-01",
        end_date="2025-09-19",
        timeframe="1h"
    )
    
    if result['success']:
        print(f"✅ Created QLib dataset with {result['files_created']} files")
        
        # Now use with QLib
        import qlib
        from qlib.data import D
        
        qlib.init(provider_uri='./my_crypto_data', region='crypto')
        instruments = D.instruments(market='all')
        data = D.features(instruments, ['$open', '$high', '$low', '$close', '$volume'])
        print(data.head())
```

### Example 3: Simple Performance Analysis

```python
async def analyze_performance():
    # ... get data ...
    
    # Calculate returns for each symbol
    for symbol in df['symbol'].unique():
        symbol_data = df[df['symbol'] == symbol].sort_values('datetime')
        
        if len(symbol_data) > 1:
            first_price = symbol_data['close'].iloc[0]
            last_price = symbol_data['close'].iloc[-1]
            return_pct = (last_price - first_price) / first_price * 100
            
            print(f"{symbol}: {return_pct:+.2f}% return")
```

## 📊 Data Structure and Access Patterns

### Your Historical Data Structure

Your collected data includes:
- **UNEMPLOYED/SOL**: Complete data (Sep 15-19, 2025)
- **Xoai / SOL**: Limited data (Sep 16-17, 2025)
- **CBRL**: Good coverage (Aug 20 - Sep 19, 2025)
- **TROLL**: Partial data (Sep 14-19, 2025)

### Available Timeframes
- `1m`: Minute-level data
- `5m`: 5-minute intervals
- `15m`: 15-minute intervals
- `1h`: Hourly data (recommended for analysis)
- `4h`: 4-hour intervals
- `12h`: 12-hour intervals
- `1d`: Daily data

### QLib Data Format

When exported to QLib format, your data becomes:

```
my_qlib_data/
├── instruments/
│   └── all.txt                    # Your symbol list
├── calendars/
│   └── 1h.txt                     # Trading calendar
└── features/
    ├── solana_Cnd9CKtG6meUJqKu9NkSeriAgzPSbQpZV5qwq5B44Spz/
    │   ├── open.1h.bin            # OHLCV data
    │   ├── high.1h.bin
    │   ├── low.1h.bin
    │   ├── close.1h.bin
    │   └── volume.1h.bin
    └── [other symbols]/
```

## 🔧 Technical Indicators Available

The examples automatically calculate:

### Price Indicators
- **SMA (Simple Moving Average)**: 20-period and 50-period
- **RSI (Relative Strength Index)**: 14-period default
- **Bollinger Bands**: 20-period with 2 standard deviations
- **Price Change**: Percentage change from previous period

### Volume Indicators
- **Volume SMA**: 20-period volume average
- **Volume Ratio**: Current volume vs. average volume
- **Volume Trend**: Recent volume vs. historical average

### Custom Indicators
You can add your own indicators by extending the `_add_technical_indicators` method in the examples.

## 🎯 Trading Strategy Framework

The trading strategy example includes:

### Signal Generation
- **RSI Oversold/Overbought**: Default thresholds at 30/70
- **Volume Confirmation**: Requires above-average volume
- **Momentum Signals**: Price breakouts above moving averages

### Risk Management
- **Position Sizing**: Maximum 20% of capital per position
- **Transaction Costs**: 0.1% default (adjustable)
- **Stop Losses**: Can be added to the strategy

### Performance Metrics
- **Total Return**: Overall strategy performance
- **Volatility**: Risk measurement
- **Max Drawdown**: Worst peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Sharpe Ratio**: Risk-adjusted returns (can be added)

## 📈 Analysis Workflows

### Workflow 1: Data Exploration
1. Run `simple_qlib_integration.py` to explore your data
2. Check data quality and availability
3. Identify symbols with good data coverage
4. Analyze basic performance metrics

### Workflow 2: Strategy Development
1. Use `qlib_trading_strategy_example.py` as a starting point
2. Modify signal generation logic
3. Adjust risk management parameters
4. Backtest on your historical data
5. Analyze signal effectiveness

### Workflow 3: QLib Integration
1. Create QLib dataset with `qlib_historical_data_example.py`
2. Use QLib's advanced features for modeling
3. Implement more sophisticated strategies
4. Use QLib's built-in evaluation tools

## 🛠️ Customization Examples

### Custom Signal Strategy

```python
class MyCustomStrategy(SimpleSignalStrategy):
    def calculate_signals(self, df):
        df = super().calculate_signals(df)
        
        # Add your custom logic
        for symbol in df['symbol'].unique():
            mask = df['symbol'] == symbol
            symbol_data = df[mask]
            
            # Example: Add volume spike detection
            volume_spike = symbol_data['volume'] > symbol_data['volume'].rolling(20).mean() * 3
            
            # Modify signals based on volume spikes
            df.loc[mask & volume_spike, 'signal_strength'] *= 1.5
        
        return df
```

### Custom Technical Indicators

```python
def add_custom_indicators(df):
    # MACD
    exp1 = df['close'].ewm(span=12).mean()
    exp2 = df['close'].ewm(span=26).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    
    # Stochastic Oscillator
    low_14 = df['low'].rolling(14).min()
    high_14 = df['high'].rolling(14).max()
    df['stoch_k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14))
    df['stoch_d'] = df['stoch_k'].rolling(3).mean()
    
    return df
```

## 🔍 Troubleshooting

### Common Issues

1. **No Data Found**
   - Check if symbols are in your watchlist
   - Verify date ranges match your collected data
   - Run `check_historical_data.py` to see what's available

2. **QLib Dataset Creation Fails**
   - Ensure output directory is writable
   - Check for sufficient disk space
   - Verify data format consistency

3. **Strategy Returns Poor Results**
   - Adjust signal thresholds
   - Add more sophisticated risk management
   - Test on different time periods
   - Consider transaction costs

### Performance Optimization

1. **Large Datasets**
   - Use specific date ranges
   - Filter to most active symbols
   - Use higher timeframes (1h instead of 1m)

2. **Memory Usage**
   - Process symbols in batches
   - Use generators for large datasets
   - Clear unused DataFrames

## 📚 Next Steps

### Immediate Actions
1. Run the simple examples to familiarize yourself with the data
2. Experiment with different timeframes and date ranges
3. Try the trading strategy example with your data

### Advanced Development
1. Integrate with QLib's machine learning models
2. Implement more sophisticated trading strategies
3. Add real-time data collection for live trading
4. Create custom risk management systems

### Production Considerations
1. Set up automated data collection
2. Implement proper error handling
3. Add logging and monitoring
4. Consider paper trading before live implementation

## 🎉 Success Metrics

After running these examples, you should be able to:
- ✅ Access your historical OHLCV data programmatically
- ✅ Create QLib-compatible datasets
- ✅ Generate and backtest trading signals
- ✅ Analyze symbol performance
- ✅ Understand data quality and coverage
- ✅ Build custom trading strategies

Your historical data collection is now fully integrated with QLib for quantitative analysis and algorithmic trading development!