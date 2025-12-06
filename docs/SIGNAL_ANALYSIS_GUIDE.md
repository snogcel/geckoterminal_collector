# Signal Analysis System - Complete Guide

## Overview

The Signal Analysis System evaluates new pools to identify high-potential trading opportunities. It analyzes multiple dimensions of pool data and generates a comprehensive signal score (0-100) along with detailed metrics.

## Signal Components

The system analyzes **5 key components**, each contributing to the overall signal score:

### 1. Volume Analysis (Weight: 30%)

**Purpose:** Detect unusual trading volume activity that may indicate growing interest.

**Metrics Analyzed:**
- Current 24h volume (USD)
- Historical average volume
- Volume growth rate
- Volume spike detection

**Calculation:**
```python
growth_rate = (current_volume / avg_historical_volume) - 1
spike_detected = growth_rate >= volume_spike_threshold (default: 2.0 = 100% increase)

volume_score = min(100, (
    (current_volume / 1000) * 10 +      # Base volume component
    (growth_rate * 50) +                 # Growth component
    (50 if spike_detected else 0)        # Spike bonus
))
```

**Trend Classification:**
- `spike`: Growth rate > 100% (spike detected)
- `increasing`: Growth rate > 10%
- `decreasing`: Growth rate < -30%
- `stable`: Growth rate between -30% and 10%
- `unknown`: Insufficient historical data

**Example:**
- Current volume: $50,000
- Historical average: $20,000
- Growth rate: 150% (spike detected)
- Volume score: ~85/100

---

### 2. Liquidity Analysis (Weight: 20%)

**Purpose:** Identify pools with growing liquidity, indicating increased market confidence.

**Metrics Analyzed:**
- Current reserve (USD)
- Historical average reserve
- Liquidity growth rate
- Significant growth detection

**Calculation:**
```python
growth_rate = (current_liquidity / avg_historical_liquidity) - 1
growth_detected = growth_rate >= liquidity_growth_threshold (default: 1.5 = 50% increase)

liquidity_score = min(100, (
    (current_liquidity / 10000) * 20 +   # Base liquidity component
    (growth_rate * 30) +                  # Growth component
    (30 if growth_detected else 0)        # Growth bonus
))
```

**Trend Classification:**
- `growing`: Growth rate > 30%
- `shrinking`: Growth rate < -20%
- `stable`: Growth rate between -20% and 30%
- `unknown`: Insufficient historical data

**Example:**
- Current liquidity: $100,000
- Historical average: $60,000
- Growth rate: 67% (growth detected)
- Liquidity score: ~70/100

---

### 3. Momentum Analysis (Weight: 20%)

**Purpose:** Measure price momentum and direction to identify trending opportunities.

**Metrics Analyzed:**
- 1-hour price change %
- 24-hour price change %
- Momentum indicator (weighted average)
- Momentum direction

**Calculation:**
```python
momentum_indicator = (price_change_1h * 2 + price_change_24h) / 3
strong_momentum = abs(momentum_indicator) > 10  # >10% momentum

momentum_score = min(100, (
    abs(momentum_indicator) * 5 +        # Base momentum
    (20 if strong_momentum else 0) +     # Strong momentum bonus
    (10 if direction == 'bullish' else 0) # Bullish bias
))
```

**Direction Classification:**
- `bullish`: Momentum indicator > 5%
- `bearish`: Momentum indicator < -5%
- `neutral`: Momentum indicator between -5% and 5%

**Example:**
- 1h price change: +15%
- 24h price change: +8%
- Momentum indicator: +12.67% (strong bullish)
- Momentum score: ~93/100

---

### 4. Activity Analysis (Weight: 20%)

**Purpose:** Detect increased trading activity and buy/sell pressure.

**Metrics Analyzed:**
- Transactions in last 1 hour (buys + sells)
- Transactions in last 24 hours (buys + sells)
- Buy/sell ratio
- Activity increase vs historical average

**Calculation:**
```python
total_1h = buys_1h + sells_1h
total_24h = buys_24h + sells_24h
buy_ratio_1h = buys_1h / total_1h if total_1h > 0 else 0.5
high_activity = total_1h > 50 or total_24h > 500

activity_score = min(100, (
    (total_1h * 0.5) +                   # 1h activity component
    (total_24h * 0.1) +                  # 24h activity component
    (activity_increase * 30) +           # Activity increase bonus
    (20 if high_activity else 0) +       # High activity bonus
    (abs(buy_ratio_1h - 0.5) * 40)      # Imbalance component
))
```

**Activity Classification:**
- `high_activity`: >50 transactions in 1h OR >500 in 24h
- Activity increase: Percentage increase vs historical average

**Example:**
- 1h transactions: 75 (60 buys, 15 sells)
- 24h transactions: 800
- Buy ratio: 80% (strong buy pressure)
- Activity score: ~85/100

---

### 5. Volatility Analysis (Weight: 10%)

**Purpose:** Measure price volatility to assess risk and opportunity.

**Metrics Analyzed:**
- Absolute 1-hour price change
- Absolute 24-hour price change
- Volatility score (weighted average)

**Calculation:**
```python
volatility_score = (abs(price_change_1h) * 2 + abs(price_change_24h)) / 3
high_volatility = volatility_score > 15  # >15% volatility

volatility_score = min(100, volatility_score * 3)
```

**Volatility Classification:**
- `extreme`: Volatility > 20%
- `high`: Volatility > 10%
- `moderate`: Volatility > 5%
- `low`: Volatility ≤ 5%

**Example:**
- 1h price change: ±18%
- 24h price change: ±12%
- Volatility score: 16% (high)
- Volatility score: ~48/100

---

## Overall Signal Score Calculation

The final signal score is a **weighted average** of all components plus bonuses:

```python
overall_score = (
    volume_score * 0.3 +        # 30% weight
    liquidity_score * 0.2 +     # 20% weight
    momentum_score * 0.2 +      # 20% weight
    activity_score * 0.2 +      # 20% weight
    volatility_score * 0.1      # 10% weight
)

# Apply bonuses for strong signals
if volume_spike_detected:
    overall_score += 10
if liquidity_growth_detected:
    overall_score += 8
if strong_momentum:
    overall_score += 5
if high_activity:
    overall_score += 5

# Cap at 100
overall_score = min(100, overall_score)
```

### Signal Score Interpretation

| Score Range | Interpretation | Action |
|-------------|----------------|--------|
| 90-100 | Exceptional signal | Strong buy consideration |
| 75-89 | Strong signal | Buy consideration |
| 60-74 | Moderate signal | Monitor closely |
| 40-59 | Weak signal | Watch for development |
| 0-39 | No significant signal | Pass |

---

## Configuration

### Default Thresholds

```yaml
signal_detection:
  enabled: true                      # Enable/disable signal detection
  min_signal_score: 60.0             # Minimum score for alerts
  volume_spike_threshold: 2.0        # 2x volume increase = spike
  liquidity_growth_threshold: 1.5    # 1.5x liquidity increase = growth
  momentum_lookback_hours: 6         # Hours to analyze for momentum
  auto_watchlist_threshold: 75.0     # Score needed for auto-watchlist
```

### Customizing Thresholds

**More Aggressive (catch more signals):**
```yaml
signal_detection:
  min_signal_score: 50.0             # Lower threshold
  volume_spike_threshold: 1.5        # 50% increase triggers spike
  liquidity_growth_threshold: 1.3    # 30% increase triggers growth
```

**More Conservative (fewer, higher-quality signals):**
```yaml
signal_detection:
  min_signal_score: 75.0             # Higher threshold
  volume_spike_threshold: 3.0        # 200% increase required
  liquidity_growth_threshold: 2.0    # 100% increase required
```

---

## Signal Alert Messages

When a strong signal is detected, the system generates an alert message:

**Format:**
```
Strong signal detected: Pool {pool_id} - Signal Score: {score} - {reasons}
```

**Example:**
```
Strong signal detected: Pool solana_ABC123... - Signal Score: 82.5 - 
Volume spike detected (150% increase), Liquidity growth (67% increase), 
Strong bullish momentum
```

**Alert Conditions:**
1. Signal score ≥ `min_signal_score` (default: 60)
2. Signal detection `enabled: true` in config
3. Pool's DEX matches target DEXes (if configured)

---

## Historical Data Requirements

The signal analyzer works best with historical data but can function without it:

### With Historical Data (Recommended)
- Compares current metrics to historical averages
- Detects growth rates and trends
- More accurate signal scoring
- Requires at least 2 historical data points

### Without Historical Data
- Uses absolute thresholds
- Basic heuristics for scoring
- Less accurate but still functional
- Useful for brand new pools

**Historical Data Collection:**
- Automatically collected every interval (e.g., 15s)
- Stored in `new_pools_history` table
- Lookback period: 24 hours (configurable)

---

## Database Fields

Signal analysis results are stored in the `new_pools_history` table:

```sql
-- Signal Analysis Fields
signal_score NUMERIC(10, 4)          -- Overall score (0-100)
volume_trend VARCHAR(20)             -- 'spike', 'increasing', 'stable', 'decreasing'
liquidity_trend VARCHAR(20)          -- 'growing', 'stable', 'shrinking'
momentum_indicator NUMERIC(10, 4)    -- Momentum value
activity_score NUMERIC(10, 4)        -- Activity score (0-100)
volatility_score NUMERIC(10, 4)      -- Volatility score (0-100)
```

---

## Example: Complete Signal Analysis

**Pool Data:**
```json
{
  "id": "solana_ABC123",
  "volume_usd_h24": 75000,
  "reserve_in_usd": 150000,
  "price_change_percentage_h1": 12.5,
  "price_change_percentage_h24": 8.3,
  "transactions_h1_buys": 45,
  "transactions_h1_sells": 15,
  "transactions_h24_buys": 520,
  "transactions_h24_sells": 180
}
```

**Historical Average:**
- Volume: $30,000
- Liquidity: $90,000

**Analysis Results:**

1. **Volume Analysis:**
   - Growth: 150% (spike detected ✓)
   - Score: 85/100
   - Trend: `spike`

2. **Liquidity Analysis:**
   - Growth: 67% (growth detected ✓)
   - Score: 70/100
   - Trend: `growing`

3. **Momentum Analysis:**
   - Indicator: +11.1% (strong bullish ✓)
   - Score: 91/100
   - Direction: `bullish`

4. **Activity Analysis:**
   - Total 1h: 60 transactions
   - Buy ratio: 75%
   - Score: 82/100
   - High activity: ✓

5. **Volatility Analysis:**
   - Score: 11.4%
   - Classification: `high`
   - Score: 34/100

**Overall Signal Score:**
```
Base: (85*0.3 + 70*0.2 + 91*0.2 + 82*0.2 + 34*0.1) = 75.9
Bonuses: +10 (volume spike) +8 (liquidity growth) +5 (momentum) +5 (activity) = +28
Final: 75.9 + 28 = 103.9 → capped at 100

Final Score: 100/100 ⭐
```

**Alert Message:**
```
Strong signal detected: Pool solana_ABC123 - Signal Score: 100.0 - 
Volume spike detected (150.0% increase), Liquidity growth (66.7% increase), 
Strong bullish momentum, High trading activity
```

---

## Extreme Value Handling

The system automatically caps extreme price movements to prevent database errors:

- **Price changes capped at:** 100,000% (1000x)
- **Momentum indicator max:** 100,000
- **Signal scores max:** 100

**When you see capped values:**
- Indicates extreme volatility (>1000x movement)
- Proceed with extra caution
- Higher risk, potential manipulation
- See [Extreme Value Handling Guide](EXTREME_VALUE_HANDLING.md) for details

---

## Best Practices

1. **Monitor Signal Quality:**
   - Track which signals lead to profitable trades
   - Adjust thresholds based on results
   - Consider market conditions

2. **Combine with Other Analysis:**
   - Check token contract security
   - Verify liquidity depth
   - Assess team/project legitimacy
   - Review tokenomics

3. **Risk Management:**
   - Higher scores don't guarantee success
   - Use position sizing
   - Set stop losses
   - Don't chase every signal

4. **Historical Data:**
   - Let system collect data for 24h for best results
   - More history = better signal accuracy
   - Consider time of day patterns

5. **DEX Filtering:**
   - Focus on target DEXes (heaven, pumpswap)
   - Reduces noise
   - Improves signal relevance

---

## Troubleshooting

### No Signals Appearing

**Check:**
1. `signal_detection.enabled: true` in config
2. `min_signal_score` not too high
3. Target DEXes configured correctly
4. Pools actually meeting thresholds

### Too Many Signals

**Solutions:**
1. Increase `min_signal_score` (e.g., 75)
2. Increase `volume_spike_threshold` (e.g., 3.0)
3. Increase `liquidity_growth_threshold` (e.g., 2.0)
4. Add more specific DEX filters

### Signals Not Accurate

**Improvements:**
1. Wait for more historical data (24h+)
2. Adjust thresholds for your market
3. Consider market volatility
4. Review false positives/negatives

---

## API Reference

### SignalResult Object

```python
@dataclass
class SignalResult:
    signal_score: float              # Overall score (0-100)
    volume_trend: str                # Volume trend classification
    liquidity_trend: str             # Liquidity trend classification
    momentum_indicator: float        # Momentum value
    activity_score: float            # Activity score (0-100)
    volatility_score: float          # Volatility score (0-100)
    signals: Dict[str, Any]          # Detailed signal breakdown
```

### Analyzer Methods

```python
# Initialize analyzer
analyzer = NewPoolsSignalAnalyzer(config)

# Analyze pool
signal_result = analyzer.analyze_pool_signals(current_data, historical_data)

# Check if should add to watchlist
should_add = analyzer.should_add_to_watchlist(signal_result, threshold=75.0)

# Generate alert message
message = analyzer.generate_alert_message(pool_id, signal_result)
```

---

## Further Reading

- [Interval Configuration Guide](INTERVAL_CONFIGURATION.md)
- [Database Schema Documentation](../migrations/README.md)
- [API Rate Limiting Guide](../README.md#rate-limiting)
