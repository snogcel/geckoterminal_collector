# Decimal Conversion Error Fix

## Problem

The NewPoolsCollector was throwing two related decimal conversion errors:

1. **In _extract_pool_info**: `decimal.ConversionSyntax` error
2. **In _store_history_record**: `conversion from NoneType to Decimal is not supported`

### Error Messages
```
Error extracting pool info: [<class 'decimal.ConversionSyntax'>]
Error storing new pools history record: conversion from NoneType to Decimal is not supported
```

## Root Causes

### Issue 1: ConversionSyntax in _extract_pool_info
The error occurred when trying to convert `None` values to `Decimal` in the `_extract_pool_info` method. When the API returns `None` for fields like `reserve_in_usd`, the code was doing:

```python
'reserve_usd': Decimal(str(get_field('reserve_in_usd', 0)))
```

When `reserve_in_usd` is `None`, `str(None)` produces the string `"None"`, which causes a `ConversionSyntax` error when passed to `Decimal()`.

### Issue 2: NoneType to Decimal in _store_history_record
When creating the `NewPoolsHistory` SQLAlchemy object with `None` values in the dictionary, SQLAlchemy/PostgreSQL was trying to validate the Numeric fields and failing because:
- `Decimal(None)` raises `TypeError: conversion from NoneType to Decimal is not supported`
- The None values were being passed directly to SQLAlchemy, which tried to convert them

### Error Format Explanation

The error format `[<class 'decimal.ConversionSyntax'>]` is how Python's decimal module represents `InvalidOperation` exceptions caused by `ConversionSyntax` errors. This happens when:
- Empty strings: `Decimal("")`
- Whitespace: `Decimal("   ")`
- Invalid formats: `Decimal("abc")`, `Decimal("None")`

## Solutions

### Solution 1: Safe Decimal Conversion in _extract_pool_info

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

### Solution 2: Filter None Values Before Database Insert

Added filtering in `_create_history_record` to remove None values from the record dictionary before creating the SQLAlchemy object:

```python
# Filter out None values to let SQLAlchemy use column defaults (NULL)
# This prevents "conversion from NoneType to Decimal" errors
record_data = {k: v for k, v in record_data.items() if v is not None}
```

This allows SQLAlchemy to use the column's default value (NULL) instead of trying to convert None to Decimal.

### Solution 3: Safe Comparison in sqlalchemy_manager.py

Fixed the duplicate detection logic to handle None values in comparisons:

```python
def safe_compare_decimal(val1, val2):
    """Compare two values that might be None or Decimal."""
    if val1 is None and val2 is None:
        return True
    if val1 is None or val2 is None:
        return False
    try:
        return Decimal(str(val1)) == Decimal(str(val2))
    except (ValueError, TypeError, decimal.InvalidOperation):
        return False
```

## Changes Made

### gecko_terminal_collector/collectors/new_pools_collector.py
1. Added `safe_decimal()` helper function to `_extract_pool_info` method
2. Changed unsafe `Decimal(str(...))` conversion to `safe_decimal(..., Decimal('0'))`
3. Added None value filtering at the end of `_create_history_record` method

### gecko_terminal_collector/database/sqlalchemy_manager.py
1. Added `import decimal` for exception handling
2. Added `safe_compare_decimal()` helper function
3. Updated duplicate detection logic to use safe comparison

## Testing

The fixes handle:
- ✓ `None` values → filtered out or returns default (Decimal('0'))
- ✓ Empty strings → returns default
- ✓ Valid decimal strings → converts successfully
- ✓ Extremely long decimal strings (67+ digits) → converts successfully
- ✓ Invalid formats → returns default with warning
- ✓ SQLAlchemy inserts with None values → None values filtered, uses column defaults
- ✓ Decimal comparisons with None → safe comparison returns False

## Impact

- Pools with `None` values for numeric fields will now be processed successfully
- Fields with None values will be stored as NULL in the database (using column defaults)
- No data loss - all other pool fields are still extracted correctly
- Consistent error handling across all decimal conversions in the collector
- Duplicate detection works correctly even when comparing None values
