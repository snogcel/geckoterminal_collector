# Extreme Value Handling

## Overview

The system now includes safeguards to handle extreme price movements that can occur in volatile crypto markets, particularly with new meme tokens that can experience 1000x+ price changes.

## Problem

Some tokens experience extreme price changes (e.g., 1,893,002% = 18,930x increase) that exceed database field precision limits:
- Database field: `NUMERIC(10, 4)` 
- Maximum value: 999,999.9999
- Error: `numeric field overflow`

## Solution

### 1. Signal Analyzer Capping

**Location:** `gecko_terminal_collector/analysis/signal_analyzer.py`

Price changes are capped at **100,000%** (1000x) before calculations:

```python
MAX_PRICE_CHANGE = Decimal('100000')  # Cap at 100,000% (1000x)

# Momentum Analysis
if abs(price_change_1h) > MAX_PRICE_CHANGE:
    price_change_1h = MAX_PRICE_CHANGE if price_change_1h > 0 else -MAX_PRICE_CHANGE

# Volatility Analysis  
price_change_1h = min(price_change_1h, MAX_PRICE_CHANGE)
```

### 2. Database Storage Capping

**Location:** `gecko_terminal_collector/collectors/new_pools_collector.py`

All signal values are capped before database insertion:

```python
def cap_value(value, max_val=999999.0):
    """Cap value to database field limits."""
    if decimal_val > Decimal(str(max_val)):
        return Decimal(str(max_val))
    elif decimal_val < Decimal(str(-max_val)):
        return Decimal(str(-max_val))
    return decimal_val

# Applied to:
- signal_score: max 100.0
- momentum_indicator: max 999,999.0
- activity_score: max 100.0
- volatility_score: max 100.0
```

## Value Limits

| Field | Database Type | Max Value | Cap Applied |
|-------|---------------|-----------|-------------|
| `signal_score` | NUMERIC(10,4) | 999,999.9999 | 100.0 |
| `momentum_indicator` | NUMERIC(10,4) | 999,999.9999 | 999,999.0 |
| `activity_score` | NUMERIC(10,4) | 999,999.9999 | 100.0 |
| `volatility_score` | NUMERIC(10,4) | 999,999.9999 | 100.0 |
| `volume_trend` | VARCHAR(20) | N/A | None |
| `liquidity_trend` | VARCHAR(20) | N/A | None |

## Impact on Signal Analysis

### Extreme Price Changes (>100,000%)

**Before Capping:**
- Price change: 1,893,002%
- Momentum indicator: 1,893,002.622
- Result: Database error ❌

**After Capping:**
- Price change: 100,000% (capped)
- Momentum indicator: 100,000.0 (capped)
- Result: Stored successfully ✅

### Signal Interpretation

When you see capped values:

1. **Momentum = 100,000**: Extreme bullish movement (>1000x)
2. **Volatility = 100**: Extreme volatility (>1000x change)
3. **Signal Score = 100**: Maximum signal strength

**Note:** Capped values still indicate exceptional opportunities but prevent database errors.

## Examples

### Example 1: Extreme Pump (Real Case)

**Raw Data:**
```json
{
  "price_change_percentage_h1": 1893002.622,
  "price_change_percentage_h24": 1893002.622
}
```

**After Processing:**
```json
{
  "momentum_indicator": 100000.0,  // Capped from 1,893,002.622
  "volatility_score": 100.0,       // Capped (extreme volatility)
  "signal_score": 39.4             // Calculated normally
}
```

**Interpretation:**
- Extreme price movement detected (>1000x)
- High volatility warning
- Moderate overall signal (other factors considered)

### Example 2: Normal Movement

**Raw Data:**
```json
{
  "price_change_percentage_h1": 15.5,
  "price_change_percentage_h24": 8.3
}
```

**After Processing:**
```json
{
  "momentum_indicator": 13.1,      // No capping needed
  "volatility_score": 14.4,        // No capping needed
  "signal_score": 75.2             // Calculated normally
}
```

**Interpretation:**
- Normal price movement
- No capping applied
- Strong signal

## Why Cap at 100,000%?

1. **Database Compatibility:** Fits within NUMERIC(10,4) limits
2. **Practical Threshold:** 1000x is already an extreme movement
3. **Signal Quality:** Beyond 1000x, exact percentage less meaningful
4. **Risk Management:** Extreme movements = extreme risk

## Monitoring Capped Values

### Query Capped Records

```sql
-- Find records with capped momentum
SELECT 
    pool_id,
    momentum_indicator,
    price_change_percentage_h1,
    price_change_percentage_h24,
    collected_at
FROM new_pools_history
WHERE momentum_indicator >= 99999  -- Near cap
ORDER BY collected_at DESC
LIMIT 20;
```

### Count Extreme Movements

```sql
-- Count how often capping occurs
SELECT 
    DATE(collected_at) as date,
    COUNT(*) as extreme_movements
FROM new_pools_history
WHERE momentum_indicator >= 99999
   OR volatility_score >= 99
GROUP BY DATE(collected_at)
ORDER BY date DESC;
```

## Best Practices

1. **Treat Capped Values as Warnings:**
   - Momentum = 100,000 → Extreme volatility, high risk
   - Volatility = 100 → Unpredictable price action
   
2. **Additional Due Diligence:**
   - Check liquidity depth
   - Verify token contract
   - Assess holder distribution
   - Review project legitimacy

3. **Position Sizing:**
   - Use smaller positions for extreme movements
   - Set tight stop losses
   - Consider the risk/reward carefully

4. **Historical Context:**
   - Compare to similar tokens
   - Check if sustainable
   - Look for manipulation signs

## Troubleshooting

### Still Getting Overflow Errors?

**Check:**
1. Database field types match schema
2. Migration applied correctly
3. Using latest code version

**Verify Field Types:**
```sql
-- PostgreSQL
SELECT column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_name = 'new_pools_history'
  AND column_name IN ('signal_score', 'momentum_indicator', 'activity_score', 'volatility_score');

-- SQLite
PRAGMA table_info(new_pools_history);
```

### Values Not Being Capped?

**Check:**
1. Code changes applied
2. Application restarted
3. No caching issues

**Test Capping:**
```python
from gecko_terminal_collector.analysis.signal_analyzer import NewPoolsSignalAnalyzer

analyzer = NewPoolsSignalAnalyzer()

# Test extreme value
test_data = {
    'price_change_percentage_h1': 2000000,  # 2 million %
    'price_change_percentage_h24': 2000000
}

result = analyzer._analyze_price_momentum(test_data, [])
print(f"Momentum: {result['indicator']}")  # Should be capped at 100,000
```

## Related Documentation

- [Signal Analysis Guide](SIGNAL_ANALYSIS_GUIDE.md) - Complete signal calculation details
- [Signal Updates Summary](SIGNAL_UPDATES_SUMMARY.md) - Recent changes
- [Database Schema](../migrations/README.md) - Field definitions

## Version History

- **2025-11-25:** Added extreme value capping for price changes and signal metrics
- **2025-11-25:** Fixed numeric field overflow errors
