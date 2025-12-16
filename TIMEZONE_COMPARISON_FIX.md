# Timezone Comparison Fix

## Problem
After fixing the timestamp storage to use UTC timezone-aware datetimes, several collectors were experiencing "can't compare offset-naive and offset-aware datetimes" errors.

## Root Cause
The collectors were using `datetime.now()` (which creates naive local time) to compare against timezone-aware UTC datetimes stored in the database.

## Files Fixed

### 1. Trade Collector (`gecko_terminal_collector/collectors/trade_collector.py`)
**Error Location**: Trade age validation comparing `block_timestamp` (UTC timezone-aware) with `datetime.now()` (naive local time)

**Changes Made**:
- Fixed all `datetime.now()` calls to `datetime.now(tz=timezone.utc)`
- Added timezone import
- Fixed comparisons in:
  - Trade age validation
  - Timestamp validation
  - Activity assessment queries
  - Gap recovery logic
  - Rotation window management

### 2. Historical OHLCV Collector (`gecko_terminal_collector/collectors/historical_ohlcv_collector.py`)
**Error Location**: Date range filtering comparing timezone-aware record datetimes with naive start/end times

**Changes Made**:
- Fixed all `datetime.now()` and `datetime.utcnow()` calls to `datetime.now(tz=timezone.utc)`
- Added timezone-aware comparison logic for date range filtering
- Fixed validation comparisons for future/past timestamp checks

### 3. OHLCV Collector (`gecko_terminal_collector/collectors/ohlcv_collector.py`)
**Changes Made**:
- Fixed all `datetime.now()` calls to `datetime.now(tz=timezone.utc)`
- Fixed timestamp validation comparisons
- Fixed activity assessment queries

### 4. Base Collector (`gecko_terminal_collector/collectors/base.py`)
**Changes Made**:
- Fixed `datetime.now()` calls in result creation methods
- Added timezone import
- Ensures all collection timestamps are UTC

### 5. Main Collection Script (`collect_historical_with_rate_limits_1m.py`)
**Changes Made**:
- Fixed `datetime.utcnow()` to `datetime.now(tz=timezone.utc)`
- Added timezone import

### 6. Monitoring System
**Files Fixed**:
- `gecko_terminal_collector/monitoring/collection_monitor.py`
- `gecko_terminal_collector/monitoring/database_manager.py` 
- `gecko_terminal_collector/monitoring/execution_history.py`

**Error Location**: Collection monitor comparing `datetime.now()` (naive) with `health.last_success` (timezone-aware)

**Changes Made**:
- Fixed all `datetime.now()` calls to `datetime.now(tz=timezone.utc)`
- Fixed alert timestamp creation and cooldown checks
- Fixed database metadata timestamps
- Fixed execution history tracking timestamps

## Key Changes Pattern

### Before (WRONG)
```python
# Creates naive local time
now = datetime.now()
if record.block_timestamp > now + timedelta(hours=1):
    # ERROR: Can't compare timezone-aware with naive
```

### After (CORRECT)
```python
# Creates timezone-aware UTC time
now = datetime.now(tz=timezone.utc)
if record.block_timestamp > now + timedelta(hours=1):
    # OK: Both are timezone-aware UTC
```

## Additional Fixes

### 7. Execution Duration Calculation
**Error**: "can't subtract offset-naive and offset-aware datetimes" in duration calculation
**Fix**: Added timezone-aware comparison logic in `ExecutionRecord.duration` property to handle mixed timezone records

### 8. Trade Collector Type Error  
**Error**: "unsupported operand type(s) for /: 'float' and 'decimal.Decimal'"
**Fix**: Ensured Decimal arithmetic by converting int divisors to Decimal in volume calculations

### 9. Additional Monitoring System Fixes
**Files Fixed**:
- `gecko_terminal_collector/monitoring/performance_metrics.py`
- `gecko_terminal_collector/monitoring/health_endpoints.py`

**Error**: Persistent timezone comparison errors in monitoring components
**Fix**: Added timezone-aware comparison logic to handle mixed timezone scenarios in:
- Collection monitor stale checks (with fallback for naive datetimes)
- Alert cooldown comparisons (with fallback for naive datetimes)  
- Performance metrics cleanup operations
- Health endpoint response time calculations

### 10. Performance Metrics Time Series Fix
**Error**: "can't compare offset-naive and offset-aware datetimes" in time series cleanup
**Fix**: 
- Fixed time series timestamp storage to use timezone-aware datetimes
- Added timezone compatibility logic for comparing stored timestamps with cutoff times
- Fixed custom metrics timestamp creation and cleanup comparisons
- Ensured all new metric timestamps are UTC timezone-aware

## Impact

✅ **Fixed**: "can't compare offset-naive and offset-aware datetimes" errors in collectors
✅ **Fixed**: "can't subtract offset-naive and offset-aware datetimes" errors in monitoring  
✅ **Fixed**: "can't subtract offset-naive and offset-aware datetimes" errors in execution duration
✅ **Fixed**: "unsupported operand type(s) for /: 'float' and 'decimal.Decimal'" in trade prioritization
✅ **Consistent**: All datetime operations now use UTC timezone-aware datetimes
✅ **Compatible**: Works with the timezone-corrected database timestamps
✅ **Stable**: Scheduler and monitoring system no longer crash due to timezone mismatches

## Testing

The fix was verified by:
1. Running the historical collection script without timezone comparison errors
2. Confirming no syntax errors in updated files
3. Ensuring the trade collector error is resolved

## Future Prevention

All new datetime operations should use:
- `datetime.now(tz=timezone.utc)` instead of `datetime.now()`
- `datetime.now(tz=timezone.utc)` instead of `datetime.utcnow()`
- Always import `timezone` from datetime module when using datetime operations