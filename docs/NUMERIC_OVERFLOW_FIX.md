# Numeric Overflow Fix

## Problem

The application was encountering database errors when inserting pool data with extreme values:

```
psycopg2.errors.NumericValueOutOfRange: numeric field overflow
DETAIL: A field with precision 10, scale 4 must round to an absolute value less than 10^6.
```

### Problematic Values

The error occurred with values like:
- `price_change_percentage_h1`: 48,239,970.579% (way too large for NUMERIC(10,4))
- `fdv_usd`: $11,583,767,869 (11.5 billion - too large for NUMERIC(20,4))
- `momentum_indicator`: 100,000.0 (too large for NUMERIC(10,4))

### Root Cause

The database columns were defined with insufficient precision:
- `NUMERIC(10,4)` can only hold values up to 999,999.9999
- `NUMERIC(20,4)` can only hold values up to 999,999,999,999,999.9999

For crypto tokens, especially new/volatile ones:
- FDV can easily exceed trillions
- Price changes can be extreme (10,000%+ pumps)
- Momentum indicators can spike during high volatility

## Solution

### 1. Database Migration

Run the migration to increase column precision:

```bash
python migrations/fix_numeric_overflow_columns.py
```

Or use the helper script:

```bash
python fix_numeric_overflow.py
```

#### Column Changes

| Column | Old Type | New Type | Max Value |
|--------|----------|----------|-----------|
| `fdv_usd` | NUMERIC(20,4) | NUMERIC(30,4) | ~999 quadrillion |
| `market_cap_usd` | NUMERIC(20,4) | NUMERIC(30,4) | ~999 quadrillion |
| `price_change_percentage_h1` | NUMERIC(10,4) | NUMERIC(15,4) | ±99,999,999.9999% |
| `price_change_percentage_h24` | NUMERIC(10,4) | NUMERIC(15,4) | ±99,999,999.9999% |
| `momentum_indicator` | NUMERIC(10,4) | NUMERIC(15,4) | ±99,999,999.9999 |

#### Constraints Added

The migration also adds check constraints to ensure score fields stay within valid ranges:

```sql
ALTER TABLE new_pools_history 
ADD CONSTRAINT chk_signal_score_range 
CHECK (signal_score IS NULL OR (signal_score >= 0 AND signal_score <= 100));

ALTER TABLE new_pools_history 
ADD CONSTRAINT chk_activity_score_range 
CHECK (activity_score IS NULL OR (activity_score >= 0 AND activity_score <= 100));

ALTER TABLE new_pools_history 
ADD CONSTRAINT chk_volatility_score_range 
CHECK (volatility_score IS NULL OR (volatility_score >= 0 AND volatility_score <= 100));
```

### 2. Application-Level Capping

The code now caps extreme values before insertion to prevent future issues:

#### In `new_pools_collector.py`

```python
# Cap FDV and market cap at 999 billion
'fdv_usd': cap_value(get_field('fdv_usd'), 999999999999.0),
'market_cap_usd': cap_value(get_field('market_cap_usd'), 999999999999.0),

# Cap price change percentages at ±99,999%
'price_change_percentage_h1': cap_value(get_field('price_change_percentage_h1'), 99999.0),
'price_change_percentage_h24': cap_value(get_field('price_change_percentage_h24'), 99999.0),

# Cap momentum indicator at ±99,999
'momentum_indicator': cap_value(signal_result.momentum_indicator, 99999.0),
```

#### In `signal_analyzer.py`

```python
# Cap scores to 0-100 range
signal_score=self._cap_extreme_value(signal_score, 100.0, 0.0),
activity_score=self._cap_extreme_value(activity_analysis.get('score', 0.0), 100.0, 0.0),
volatility_score=self._cap_extreme_value(volatility_analysis.get('score', 0.0), 100.0, 0.0),

# Cap momentum indicator
momentum_indicator=self._cap_extreme_value(
    momentum_analysis.get('indicator', 0.0), 
    max_value=99999.0,
    min_value=-99999.0
),
```

### 3. Model Updates

The PostgreSQL model file (`postgresql_models.py`) has been updated to reflect the new column types.

## Why Cap Values?

Even with increased precision, we cap values for several reasons:

1. **Data Quality**: Extreme values often indicate data issues or API errors
2. **Analysis Validity**: A 48 million percent price change is not meaningful for analysis
3. **Database Performance**: Smaller numbers are more efficient to store and query
4. **Practical Limits**: Real-world values rarely exceed these caps legitimately

### Capping Strategy

- **FDV/Market Cap**: Capped at 999 billion (larger than any realistic crypto project)
- **Price Changes**: Capped at ±99,999% (still allows for extreme pumps/dumps)
- **Momentum**: Capped at ±99,999 (sufficient for any momentum indicator)
- **Scores**: Capped at 0-100 (normalized scores should never exceed this)

## Testing

After running the migration, test with the problematic data:

```python
from decimal import Decimal
from datetime import datetime

test_data = {
    'pool_id': 'solana_test',
    'fdv_usd': Decimal('11583767869.7838'),  # 11.5 billion
    'price_change_percentage_h1': Decimal('48239970.579'),  # 48 million %
    'momentum_indicator': Decimal('100000.0'),
    # ... other fields
}

# This should now work without errors
```

## Rollback

If you need to rollback the migration:

```sql
ALTER TABLE new_pools_history ALTER COLUMN fdv_usd TYPE NUMERIC(20, 4);
ALTER TABLE new_pools_history ALTER COLUMN market_cap_usd TYPE NUMERIC(20, 4);
ALTER TABLE new_pools_history ALTER COLUMN price_change_percentage_h1 TYPE NUMERIC(10, 4);
ALTER TABLE new_pools_history ALTER COLUMN price_change_percentage_h24 TYPE NUMERIC(10, 4);
ALTER TABLE new_pools_history ALTER COLUMN momentum_indicator TYPE NUMERIC(10, 4);

ALTER TABLE new_pools_history DROP CONSTRAINT IF EXISTS chk_signal_score_range;
ALTER TABLE new_pools_history DROP CONSTRAINT IF EXISTS chk_activity_score_range;
ALTER TABLE new_pools_history DROP CONSTRAINT IF EXISTS chk_volatility_score_range;
```

**Note**: Rollback will fail if you have data that exceeds the old limits.

## Prevention

To prevent similar issues in the future:

1. **Monitor Extreme Values**: Log when values are capped
2. **Data Validation**: Add validation at the API response level
3. **Alerts**: Set up alerts for unusual data patterns
4. **Regular Review**: Periodically review column precision requirements

## Related Files

- `migrations/fix_numeric_overflow_columns.py` - Database migration
- `gecko_terminal_collector/collectors/new_pools_collector.py` - Value capping logic
- `gecko_terminal_collector/analysis/signal_analyzer.py` - Signal value capping
- `gecko_terminal_collector/database/postgresql_models.py` - Updated model definitions
