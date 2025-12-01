# Quick Guide: Duplicate Detection Fix

## What Was Fixed

The system now prevents duplicate entries in `new_pools_history` when the GeckoTerminal API hasn't updated (typically updates once per minute, but we collect every 15 seconds).

## How It Works

Before inserting a new history record, the system:
1. Checks the last 2 minutes of records for the same pool
2. Compares these 6 key fields:
   - `reserve_in_usd`
   - `transactions_h1_buys`
   - `transactions_h1_sells`
   - `transactions_h24_buys`
   - `transactions_h24_sells`
   - `volume_usd_h24`
3. If all fields match → Skip (duplicate)
4. If any field differs → Store (new data)

## Testing

Run the test script to verify:
```bash
python test_duplicate_detection.py
```

Expected output: "TEST PASSED: Duplicate detection working correctly!"

## What You'll See

### In Logs (Debug Level)
```
DEBUG: Skipping duplicate new pools history record for pool solana_ABC123... - data unchanged since 2025-12-01 12:35:00
```

### In Database
- Fewer records in `new_pools_history`
- Only records with actual data changes
- Better signal score accuracy

## No Action Required

The fix is automatic and transparent. Your existing collection scripts will work exactly as before, but without storing duplicates.

## Rollback (If Needed)

If you need to disable this feature, edit `gecko_terminal_collector/database/sqlalchemy_manager.py` and remove the duplicate check in the `store_new_pools_history` method (lines ~2001-2040).
