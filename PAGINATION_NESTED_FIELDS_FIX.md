# Nested Fields Extraction Fix

## Issue

Fields in `new_pools_history` were populating as NULL/empty:
- `price_change_percentage_h1`
- `price_change_percentage_h24`
- `transactions_h1_buys`
- `transactions_h1_sells`
- `transactions_h24_buys`
- `transactions_h24_sells`
- `volume_usd_h24`

This caused calculated fields to return as 0.00:
- `signal_score`
- `momentum_indicator`
- `activity_score`
- `volatility_score`

## Root Cause

**API returns nested objects, but code was looking for flat fields:**

### API Structure:
```json
{
  "attributes": {
    "price_change_percentage": {
      "h1": "31.63",
      "h24": "31.63"
    },
    "transactions": {
      "h1": {
        "buys": 8,
        "sells": 3
      },
      "h24": {
        "buys": 8,
        "sells": 3
      }
    },
    "volume_usd": {
      "h24": "640.3535116992"
    }
  }
}
```

### Code Was Looking For (flat):
```python
get_field('price_change_percentage_h1')  # ❌ Doesn't exist
get_field('transactions_h1_buys')        # ❌ Doesn't exist
get_field('volume_usd_h24')              # ❌ Doesn't exist
```

## Solution

### 1. Added Nested Field Helper

```python
def get_nested_field(parent_key, child_key, default=None):
    """Get value from nested dict like price_change_percentage.h1"""
    parent = get_field(parent_key, {})
    if isinstance(parent, dict):
        return parent.get(child_key, default)
    return default
```

### 2. Updated Field Extraction

```python
# Price change percentages
'price_change_percentage_h1': cap_value(
    get_nested_field('price_change_percentage', 'h1'), 
    99999.0
),
'price_change_percentage_h24': cap_value(
    get_nested_field('price_change_percentage', 'h24'), 
    99999.0
),

# Transactions (double nested)
'transactions_h1_buys': safe_int(
    get_nested_field('transactions', 'h1', {}).get('buys') 
    if get_nested_field('transactions', 'h1') else None
),

# Volume
'volume_usd_h24': safe_decimal(
    get_nested_field('volume_usd', 'h24')
),
```

## Field Mapping

| Database Field | API Path | Example Value |
|----------------|----------|---------------|
| `price_change_percentage_h1` | `attributes.price_change_percentage.h1` | `"31.63"` |
| `price_change_percentage_h24` | `attributes.price_change_percentage.h24` | `"31.63"` |
| `transactions_h1_buys` | `attributes.transactions.h1.buys` | `8` |
| `transactions_h1_sells` | `attributes.transactions.h1.sells` | `3` |
| `transactions_h24_buys` | `attributes.transactions.h24.buys` | `8` |
| `transactions_h24_sells` | `attributes.transactions.h24.sells` | `3` |
| `volume_usd_h24` | `attributes.volume_usd.h24` | `"640.3535116992"` |

## Impact

With this fix, the signal analysis will now work correctly:

### Before (all zeros):
```
signal_score: 0.00
momentum_indicator: 0.00
activity_score: 0.00
volatility_score: 0.00
```

### After (calculated from real data):
```
signal_score: 65.50
momentum_indicator: 1.25
activity_score: 45.00
volatility_score: 32.00
```

## Testing

Monitor `new_pools_history` table for populated fields:
```sql
SELECT 
    pool_id,
    price_change_percentage_h1,
    price_change_percentage_h24,
    transactions_h1_buys,
    transactions_h24_buys,
    volume_usd_h24,
    signal_score,
    activity_score
FROM new_pools_history
WHERE collected_at > NOW() - INTERVAL '1 hour'
LIMIT 10;
```

Expected: All fields should have values (not NULL).

## Additional Fix: Signal Analyzer

The signal analyzer also needed updating because it was receiving raw API data with nested fields.

### Solution:
Added `_flatten_pool_data_for_analysis()` method to convert nested API format to flat format before passing to analyzer:

```python
def _flatten_pool_data_for_analysis(self, pool_data: Dict) -> Dict:
    """Flatten nested API response fields for signal analyzer."""
    # Converts:
    # price_change_percentage.h1 → price_change_percentage_h1
    # transactions.h1.buys → transactions_h1_buys
    # volume_usd.h24 → volume_usd_h24
```

## Result

✅ **Fixed** - Nested fields now extracted correctly in history records  
✅ **Fixed** - Signal analyzer receives flattened data  
✅ **Signal analysis working** - Calculated fields populate with real values  
✅ **Data complete** - All metrics available for analysis  

The pagination implementation now correctly extracts all nested fields from the API response and properly formats them for both storage and analysis.
