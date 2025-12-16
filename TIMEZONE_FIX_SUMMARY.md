# Timezone Fix Summary

## Problem Identified

Your database timestamps were being stored with incorrect timezone offsets:

- **OHLCV Data**: `datetime` column showed UTC-07:00 offset but represented UTC times
- **Trades**: `block_timestamp` column showed UTC-07:00, making times 7 hours off from UTC

### Root Cause

The code was using `datetime.fromtimestamp()` without the `timezone` parameter, which creates timestamps in the **local system timezone** (UTC-07:00) instead of UTC.

## Changes Made

### 1. Code Fixes (Future Data)

Updated the following files to use UTC timezone:

- `gecko_terminal_collector/collectors/ohlcv_collector.py`
  - Changed `datetime.fromtimestamp(timestamp)` → `datetime.fromtimestamp(timestamp, tz=timezone.utc)`
  - Added `timezone` import
  - Fixed logging statements

- `gecko_terminal_collector/collectors/historical_ohlcv_collector.py`
  - Changed `datetime.fromtimestamp(timestamp)` → `datetime.fromtimestamp(timestamp, tz=timezone.utc)`
  - Added `timezone` import

- `gecko_terminal_collector/collectors/trade_collector.py`
  - Updated timestamp parsing to use `tz=timezone.utc` parameter
  - Removed the line that stripped timezone info
  - Added `timezone` import

- `gecko_terminal_collector/utils/structured_logging.py`
  - Fixed log timestamps to use UTC
  - Added `timezone` import

### 2. Migration Script (Existing Data)

Created `fix_timezone_offsets.py` to correct existing database records:

- Converts existing datetime values from local time to UTC
- Handles both timezone-aware and naive datetime columns
- Includes verification step to confirm the fix

## How to Apply the Fix

### Step 1: Fix Existing Data (Optional but Recommended)

```bash
python fix_timezone_offsets.py
```

This will:
- Add 7 hours to all existing `datetime` and `block_timestamp` values
- Convert them to proper UTC times
- Show verification results

**WARNING**: This modifies your database. Make a backup first if needed.

### Step 2: Verify the Fix

Run the diagnostic script to check timestamps:

```bash
python check_timestamp_offsets.py
```

You should see:
- OHLCV `datetime` values matching the UTC time from Unix timestamps
- Trade `block_timestamp` values in UTC
- Offset showing 0.0 hours

### Step 3: Collect New Data

New data collected after the code changes will automatically be stored in UTC.

## For Your Spreadsheets

### Before the Fix

- **OHLCV**: Add 7 hours to `datetime` column OR use `timestamp` column (always UTC)
- **Trades**: Add 7 hours to `block_timestamp` column

### After the Fix

- **OHLCV**: Use `datetime` column directly (now in UTC)
- **Trades**: Use `block_timestamp` column directly (now in UTC)
- **OHLCV Alternative**: Continue using `timestamp` column (Unix timestamps are always UTC)

## Technical Details

### Unix Timestamps

The `timestamp` column in `ohlcv_data` stores Unix timestamps (seconds since epoch), which are **always UTC** by definition. This column was never affected by the timezone issue.

### Datetime Conversion

```python
# Before (WRONG - uses local timezone)
datetime_obj = datetime.fromtimestamp(timestamp)

# After (CORRECT - uses UTC)
datetime_obj = datetime.fromtimestamp(timestamp, tz=timezone.utc)
```

### ISO Format Timestamps

The code already handled ISO format timestamps correctly:
```python
datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
```

This creates timezone-aware UTC datetimes, which was working correctly.

## Verification

After applying the fix, you can verify by:

1. Checking that `datetime` values match Unix timestamp conversions
2. Confirming timezone shows as UTC or +00:00
3. Comparing with external sources (blockchain explorers, etc.)

## Impact

- **Existing data**: Needs migration script to fix (one-time operation)
- **New data**: Automatically correct after code changes
- **Queries**: No changes needed - datetime comparisons will work correctly
- **Exports**: Timestamps will now be in UTC as expected
