# Decimal Conversion Error Fix

## Problem

The NewPoolsCollector was throwing a `decimal.ConversionSyntax` error when processing pool data:

```
Error extracting pool info: [<class 'decimal.ConversionSyntax'>]
```

## Root Cause

The error occurred when trying to convert `None` values to `Decimal` in the `_extract_pool_info` method. When the API returns `None` for fields like `reserve_in_usd`, the code was doing:

```python
'reserve_usd': Decimal(str(get_field('reserve_in_usd', 0)))
```

When `reserve_in_usd` is `None`, `str(None)` produces the string `"None"`, which causes a `ConversionSyntax` error when passed to `Decimal()`.

### Error Format Explanation

The error format `[<class 'decimal.ConversionSyntax'>]` is how Python's decimal module represents `InvalidOperation` exceptions caused by `ConversionSyntax` errors. This happens when:
- Empty strings: `Decimal("")`
- Whitespace: `Decimal("   ")`
- Invalid formats: `Decimal("abc")`, `Decimal("None")`

## Solution

Added a `safe_decimal()` helper function to `_extract_pool_info` that:
1. Checks if the value is `None` or empty string BEFORE conversion
2. Catches all decimal conversion exceptions
3. Returns a safe default value instead of crashing

```python
def safe_decimal(value, default=None):
    if value is None or value == '':
        return default
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, decimal.InvalidOperation):
        self.logger.warning(f"Failed to convert value to Decimal: {value}")
        return default
```

## Changes Made

Modified `gecko_terminal_collector/collectors/new_pools_collector.py`:
- Added `safe_decimal()` helper function to `_extract_pool_info` method
- Changed unsafe `Decimal(str(...))` conversion to `safe_decimal(..., Decimal('0'))`
- This matches the pattern already used in `_create_history_record` method

## Testing

The fix handles:
- ✓ `None` values → returns default (Decimal('0'))
- ✓ Empty strings → returns default
- ✓ Valid decimal strings → converts successfully
- ✓ Extremely long decimal strings (67+ digits) → converts successfully
- ✓ Invalid formats → returns default with warning

## Impact

- Pools with `None` values for `reserve_in_usd` will now be processed successfully
- The pool will be created with `reserve_usd = 0` instead of failing
- No data loss - all other pool fields are still extracted correctly
- Consistent error handling across all decimal conversions in the collector
