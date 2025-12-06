# DEX Filtering for Auto-Watchlist

## Overview

Added DEX filtering to auto-watchlist functionality to match the behavior of signal alerts. Now only pools from target DEXes (configured in `config.yaml`) will be automatically added to the watchlist.

## Problem

Auto-watchlist was adding pools from **all DEXes** when signal scores were high enough, but signal alerts were already filtering to only show alerts for target DEXes. This created inconsistency where:
- Signal alerts: Only "heaven" and "pumpswap" 
- Auto-watchlist: All DEXes (meteora-dbc, raydium, etc.)

## Solution

Updated `_handle_auto_watchlist()` method in `gecko_terminal_collector/collectors/new_pools_collector.py` to use the same DEX filtering logic as signal alerts.

### Code Changes

Added DEX filtering check after signal score validation:

```python
# Check if pool's DEX is in our target list (same logic as signal alerts)
pool_dex_id = self._get_pool_dex_id(pool_data)
should_add = not self.target_dexes or (pool_dex_id and pool_dex_id.lower() in self.target_dexes)

if not should_add:
    self.logger.debug(
        f"Auto-watchlist: Pool {pool_id} DEX '{pool_dex_id}' not in target dexes {self.target_dexes} - skipping"
    )
    return
```

### Configuration

Target DEXes are configured in `config.yaml`:

```yaml
dexes:
  targets:
    - heaven
    - pumpswap
  network: solana
```

## Behavior

### Before Fix
- ✅ Signal score >= 75.0 → Add to watchlist
- ❌ No DEX filtering

**Result**: Pools from meteora-dbc, raydium, and other DEXes were added

### After Fix
- ✅ Signal score >= 75.0
- ✅ DEX must be in target list (heaven or pumpswap)
- ✅ Both conditions required → Add to watchlist

**Result**: Only pools from heaven and pumpswap are added

## Filtering Logic

The filtering uses the same logic as signal alerts:

```python
should_add = not self.target_dexes or (pool_dex_id and pool_dex_id.lower() in self.target_dexes)
```

This means:
- If `target_dexes` is empty → Allow all DEXes
- If `target_dexes` has values → Only allow pools from those DEXes
- Case-insensitive matching (PUMPSWAP matches pumpswap)
- None or empty DEX IDs are filtered out

## Test Results

All test cases passed:

```
✓ pumpswap → Added (in target list)
✓ heaven → Added (in target list)
✓ meteora-dbc → Filtered out (not in target list)
✓ raydium → Filtered out (not in target list)
✓ PUMPSWAP → Added (case-insensitive match)
✓ None → Filtered out (no DEX ID)
✓ Empty string → Filtered out (no DEX ID)
✓ Empty target list → Allows all DEXes
```

## Logging

### Pool Added (Target DEX)
```
INFO: Auto-watchlist: Pool solana_ABC123... has strong signal (85.5 >= 75.0) and is from target DEX 'pumpswap' - checking if already in watchlist...
INFO: ✅ Successfully added pool solana_ABC123... to watchlist
```

### Pool Filtered (Non-Target DEX)
```
DEBUG: Auto-watchlist: Pool solana_XYZ789... DEX 'meteora-dbc' not in target dexes ['heaven', 'pumpswap'] - skipping
```

## Consistency with Signal Alerts

Both features now use identical DEX filtering:

| Feature | DEX Filtering | Target DEXes |
|---------|---------------|--------------|
| Signal Alerts | ✅ Yes | heaven, pumpswap |
| Auto-Watchlist | ✅ Yes | heaven, pumpswap |

## Impact

### Positive
- ✅ Consistent behavior between signal alerts and auto-watchlist
- ✅ Reduces noise in watchlist (only relevant DEXes)
- ✅ Focuses monitoring on configured target DEXes
- ✅ Easier to manage watchlist size

### Considerations
- Pools from non-target DEXes with high signals won't be auto-added
- Can still manually add pools from any DEX to watchlist
- To include more DEXes, update `config.yaml` dexes.targets

## Configuration Examples

### Current (Focused)
```yaml
dexes:
  targets:
    - heaven
    - pumpswap
```
**Result**: Only heaven and pumpswap pools auto-added

### All DEXes (No Filtering)
```yaml
dexes:
  targets: []  # Empty list
```
**Result**: All DEXes allowed (no filtering)

### Multiple DEXes
```yaml
dexes:
  targets:
    - heaven
    - pumpswap
    - raydium
    - meteora-dbc
```
**Result**: Pools from any of these 4 DEXes auto-added

## Monitoring

### Check Auto-Watchlist by DEX
```sql
-- Count auto-added pools by DEX
SELECT 
    p.dex_id,
    COUNT(*) as pool_count
FROM watchlist w
JOIN pools p ON w.pool_id = p.id
WHERE w.metadata_json::jsonb->>'auto_added' = 'true'
GROUP BY p.dex_id
ORDER BY pool_count DESC;
```

### Verify Only Target DEXes
```sql
-- Should only show heaven and pumpswap
SELECT DISTINCT p.dex_id
FROM watchlist w
JOIN pools p ON w.pool_id = p.id
WHERE w.metadata_json::jsonb->>'auto_added' = 'true'
  AND w.created_at >= NOW() - INTERVAL '24 hours';
```

## Files Modified

- `gecko_terminal_collector/collectors/new_pools_collector.py`
  - Updated `_handle_auto_watchlist()` method
  - Added DEX filtering logic matching signal alerts

## Backward Compatibility

- ✅ Fully backward compatible
- ✅ Existing watchlist entries unchanged
- ✅ Only affects new auto-additions
- ✅ Manual watchlist additions still work for any DEX

## Summary

Auto-watchlist now filters by target DEXes, matching the behavior of signal alerts. Only pools from "heaven" and "pumpswap" with signal scores >= 75.0 will be automatically added to the watchlist, providing consistent and focused monitoring.
