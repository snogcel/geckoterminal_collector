# Quick Fix Summary: Numeric Overflow Error

## The Problem
Your collector was crashing with:
```
psycopg2.errors.NumericValueOutOfRange: numeric field overflow
DETAIL: A field with precision 10, scale 4 must round to an absolute value less than 10^6.
```

The issue: Database columns were too small for extreme crypto values (48 million % price change, 11 billion FDV).

## The Fix (3 Steps)

### Step 1: Run the Migration
```bash
python fix_numeric_overflow.py
```

This will:
- Increase column precision for FDV, market cap, price changes, and momentum
- Add constraints to keep scores in 0-100 range
- Update your database schema

### Step 2: Restart Your Collector
The code now automatically caps extreme values before insertion:
- Price changes capped at ±99,999%
- FDV/Market cap capped at 999 billion
- Scores capped at 0-100

### Step 3: Verify
Run your collector again - the error should be gone!

## What Changed

### Database Schema
- `fdv_usd`: Can now hold up to 999 quadrillion (was 999 trillion)
- `price_change_percentage_h1/h24`: Can now hold ±99,999,999% (was ±999,999%)
- `momentum_indicator`: Can now hold ±99,999,999 (was ±999,999)

### Application Code
- `new_pools_collector.py`: Caps values before database insertion
- `signal_analyzer.py`: Caps calculated signal values
- `postgresql_models.py`: Updated column definitions

## Files Modified
1. ✅ `migrations/fix_numeric_overflow_columns.py` (NEW - run this!)
2. ✅ `gecko_terminal_collector/collectors/new_pools_collector.py`
3. ✅ `gecko_terminal_collector/analysis/signal_analyzer.py`
4. ✅ `gecko_terminal_collector/database/postgresql_models.py`
5. ✅ `fix_numeric_overflow.py` (NEW - helper script)
6. ✅ `docs/NUMERIC_OVERFLOW_FIX.md` (NEW - detailed docs)

## Need Help?
See `docs/NUMERIC_OVERFLOW_FIX.md` for detailed information.
