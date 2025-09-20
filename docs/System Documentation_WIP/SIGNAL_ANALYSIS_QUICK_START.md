# New Pools Signal Analysis System - Quick Start Guide

## Overview

The enhanced new pools data capture system now includes comprehensive signal analysis to detect trading opportunities and automatically manage watchlists based on pool activity patterns.

## 🚀 Quick Setup

### 1. Run Database Migration

First, add the new signal analysis fields to your database:

```bash
python migrations/add_signal_fields_to_new_pools_history.py
```

### 2. Update Configuration

The system is already configured with enhanced settings in `config.yaml`:

- **Collection Frequency**: Increased to every 10 minutes (from 30 minutes)
- **Signal Analysis**: Enabled by default
- **Auto-Watchlist**: Enabled for high-signal pools

### 3. Test the System

Run the comprehensive test suite:

```bash
python test_signal_analysis_system.py
```

## 📊 Signal Analysis Features

### Signal Components

The system analyzes multiple signal components:

1. **Volume Trends** - Detects volume spikes and growth patterns
2. **Liquidity Analysis** - Monitors liquidity growth and stability
3. **Price Momentum** - Calculates momentum indicators from price changes
4. **Trading Activity** - Analyzes buy/sell ratios and transaction patterns
5. **Volatility Scoring** - Measures price volatility levels

### Signal Scoring

- **Signal Score Range**: 0-100
- **Watchlist Threshold**: 75+ (configurable)
- **Alert Threshold**: 60+ (configurable)

## 🔧 Usage Examples

### 1. Enhanced Collection with Signal Analysis

```bash
# Run new pools collection with signal analysis
gecko-cli collect-new-pools --network solana --auto-watchlist --min-liquidity 5000

# Run with custom signal thresholds
gecko-cli run-collector new-pools --network solana --auto-watchlist --min-activity-score 70
```

### 2. Analyze Historical Signals

```bash
# Analyze signals from the last 24 hours
gecko-cli analyze-pool-signals --network solana --hours 24 --min-signal-score 70

# Export results as JSON
gecko-cli analyze-pool-signals --network solana --format json --limit 50

# CSV export for analysis
gecko-cli analyze-pool-signals --network solana --format csv > signals.csv
```

### 3. Real-time Signal Monitoring

```bash
# Monitor for high-signal pools (alert threshold 80)
gecko-cli monitor-pool-signals --network solana --alert-threshold 80 --interval 300

# Monitor specific pool
gecko-cli monitor-pool-signals --pool-id solana_ABC123... --alert-threshold 75

# Run for specific duration
gecko-cli monitor-pool-signals --network solana --duration 60 --interval 180
```

## 📈 Signal Interpretation

### High-Value Signals (Score 80+)

- **Volume Spike**: >200% volume increase
- **Liquidity Growth**: >150% liquidity increase
- **Strong Momentum**: >10% price movement with consistent direction
- **High Activity**: >50 transactions/hour with buy bias

### Medium Signals (Score 60-79)

- **Volume Growth**: 50-200% volume increase
- **Moderate Momentum**: 5-10% price movement
- **Increased Activity**: 20-50 transactions/hour

### Low Signals (Score <60)

- **Stable Patterns**: Normal trading activity
- **Low Volatility**: <5% price movement
- **Minimal Growth**: <50% volume/liquidity changes

## 🎯 Auto-Watchlist Integration

### Automatic Addition Criteria

Pools are automatically added to the watchlist when:

1. **Signal Score** ≥ 75 (configurable)
2. **Volume** ≥ $1,000 (24h)
3. **Liquidity** ≥ $1,000
4. **Pool Age** ≤ 24 hours

### Watchlist Metadata

Auto-added pools include metadata:

```json
{
  "auto_added": true,
  "signal_score": 85.5,
  "added_at": "2025-09-16T10:30:00",
  "source": "new_pools_signal_detection"
}
```

## 🔍 Monitoring Dashboard Queries

### Top Signal Pools (Last 24h)

```sql
SELECT 
    pool_id,
    signal_score,
    volume_trend,
    liquidity_trend,
    volume_usd_h24,
    collected_at
FROM new_pools_history 
WHERE collected_at > NOW() - INTERVAL '24 hours'
    AND signal_score >= 70
ORDER BY signal_score DESC
LIMIT 20;
```

### Volume Spike Detection

```sql
SELECT 
    pool_id,
    signal_score,
    volume_usd_h24,
    volume_trend,
    collected_at
FROM new_pools_history 
WHERE volume_trend = 'spike'
    AND collected_at > NOW() - INTERVAL '6 hours'
ORDER BY signal_score DESC;
```

### Auto-Watchlist Additions

```sql
SELECT 
    w.pool_id,
    w.token_symbol,
    w.created_at,
    w.metadata_json->>'signal_score' as signal_score
FROM watchlist w
WHERE w.metadata_json->>'auto_added' = 'true'
    AND w.created_at > NOW() - INTERVAL '24 hours'
ORDER BY w.created_at DESC;
```

## ⚙️ Configuration Options

### Signal Detection Settings

```yaml
new_pools:
  signal_detection:
    enabled: true
    min_signal_score: 60.0
    volume_spike_threshold: 2.0      # 200% increase
    liquidity_growth_threshold: 1.5   # 150% increase
    momentum_lookback_hours: 6
    auto_watchlist_threshold: 75.0
```

### Collection Settings

```yaml
new_pools:
  networks:
    solana:
      interval: "10m"                 # Collection frequency
      signal_analysis: true
      auto_watchlist_integration: true
```

## 🚨 Alerts and Notifications

### Signal Alerts

The system generates alerts for:

- **Volume Spikes**: Sudden volume increases
- **Liquidity Growth**: Significant liquidity additions
- **Strong Momentum**: Consistent price movements
- **High Activity**: Unusual trading activity

### Alert Message Format

```
Pool solana_ABC123... - Signal Score: 85.2 - Volume spike detected (250% increase), Strong bullish momentum
```

## 📊 Performance Metrics

### Expected Performance

- **Collection Speed**: 100+ pools per minute
- **Signal Analysis**: <1 second per pool
- **Database Storage**: <100ms per record
- **Watchlist Accuracy**: 80%+ of auto-added pools show continued activity

### Monitoring Collection Health

```bash
# Check collection status
gecko-cli status --detailed

# Monitor database performance
gecko-cli db-health --test-performance

# View recent collection metrics
gecko-cli metrics --collector new_pools_solana --hours 24
```

## 🔧 Troubleshooting

### Common Issues

1. **No Signals Detected**
   - Check if signal analysis is enabled in config
   - Verify database migration was successful
   - Ensure sufficient historical data exists

2. **Auto-Watchlist Not Working**
   - Verify `auto_watchlist_integration: true` in config
   - Check signal score thresholds
   - Ensure watchlist table exists

3. **Performance Issues**
   - Monitor database connection pool
   - Check for index usage on signal fields
   - Consider reducing collection frequency if needed

### Debug Commands

```bash
# Test signal analyzer directly
python -c "
from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer
analyzer = NewPoolsSignalAnalyzer()
print('Signal analyzer initialized successfully')
"

# Check database connectivity
gecko-cli db-health --test-connectivity

# Validate configuration
gecko-cli validate --check-db --check-api
```

## 🎯 Next Steps

1. **Monitor Signal Performance**: Track which signals lead to profitable opportunities
2. **Tune Thresholds**: Adjust signal thresholds based on performance data
3. **Expand Networks**: Enable signal analysis for additional networks
4. **Custom Alerts**: Implement custom notification systems for high-value signals
5. **Machine Learning**: Consider ML models for signal prediction enhancement

## 📚 Additional Resources

- **Database Schema**: See `gecko_terminal_collector/database/postgresql_models.py`
- **Signal Analysis Code**: See `gecko_terminal_collector/analysis/signal_analyzer.py`
- **Configuration Reference**: See `config.yaml` for all available options
- **API Documentation**: Check collector base classes for extension points

---

**Ready to start detecting signals!** 🎯

The system is now configured to automatically collect new pools data every 10 minutes, analyze signals, and add promising pools to your watchlist. Monitor the logs and use the CLI commands to track signal performance and adjust thresholds as needed.