# OHLCV Collection Troubleshooting

## Issue: "No data found in database after collection"

### Symptom
```
✓ Collected 28 records
Verifying data in database...
⚠️  No data found in database after collection
```

### Root Cause
**Pool ID mismatch** - The pool ID in your watchlist doesn't match the pool ID used during collection.

---

## Understanding the Problem

### What Happened
1. You ran collection for a pool
2. Collection succeeded and stored 28 records
3. Verification query used a different pool ID
4. No data found because it's looking for the wrong pool

### Why It Happens
- Watchlist has: `solana_4dg2tRXLCn8eHLJg42stV9bzooEG1pMnLkk5imF8wRYp`
- Collection stored data for: `solana_FjQTDcJ18m2nmot5Ny6LjAgn2bB4TT53C4BteBRsw79Y`
- These don't match, so verification fails

---

## Quick Fix

### Step 1: Find What Data You Actually Have
```bash
python debug_ohlcv_collection.py
```

This shows:
- ✅ What's in your watchlist
- ✅ What OHLCV data exists
- ✅ Which pool IDs match (or don't match)

### Step 2: Fix Your Watchlist
```bash
python fix_watchlist_pool_id.py
```

This will:
- Show pools with most OHLCV data
- Let you pick one to add to watchlist
- Verify data is accessible

### Step 3: Verify It Works
```bash
python collect_1m_data.py check
```

Should now show data for your watchlist pools.

---

## Prevention

### Always Use Watchlist Pool IDs
```bash
# Get pool ID from watchlist first
psql -d gecko_terminal_collector -c "SELECT pool_id FROM watchlist WHERE is_active = true;"

# Output: solana_4dg2tRXLCn8eHLJg42stV9bzooEG1pMnLkk5imF8wRYp

# Use the EXACT pool ID (without solana_ prefix)
python collect_1m_data.py 4dg2tRXLCn8eHLJg42stV9bzooEG1pMnLkk5imF8wRYp 1
```

### Or Use Batch Collection
```bash
# This automatically uses watchlist pool IDs
python collect_1m_data.py batch 3 10
```

---

## Manual Verification

### Check What's in Watchlist
```sql
SELECT pool_id, token_symbol, network_address
FROM watchlist
WHERE is_active = true;
```

### Check What OHLCV Data Exists
```sql
SELECT 
    pool_id,
    timeframe,
    COUNT(*) as records,
    MIN(datetime) as start_date,
    MAX(datetime) as end_date
FROM ohlcv_data
GROUP BY pool_id, timeframe
ORDER BY MAX(datetime) DESC
LIMIT 20;
```

### Check for Matches
```sql
-- Pools in watchlist that have OHLCV data
SELECT DISTINCT w.pool_id, w.token_symbol, COUNT(o.id) as ohlcv_records
FROM watchlist w
LEFT JOIN ohlcv_data o ON w.pool_id = o.pool_id
WHERE w.is_active = true
GROUP BY w.pool_id, w.token_symbol;
```

---

## Common Scenarios

### Scenario 1: Collected for Wrong Pool
**Problem:** You typed the wrong pool ID

**Solution:**
```bash
# Get correct pool ID from watchlist
psql -d gecko_terminal_collector -c "SELECT pool_id FROM watchlist;"

# Collect for correct pool
python collect_1m_data.py <correct_pool_id> 1
```

---

### Scenario 2: Watchlist Has Wrong Pool
**Problem:** Watchlist entry is for a pool you don't want

**Solution:**
```bash
# Remove old entry
psql -d gecko_terminal_collector -c "DELETE FROM watchlist WHERE pool_id = 'old_pool_id';"

# Add correct entry
python fix_watchlist_pool_id.py
```

---

### Scenario 3: Pool ID Format Confusion
**Problem:** Not sure if you need `solana_` prefix

**Rule:**
- **Database storage:** Always includes `solana_` prefix
- **Collection command:** Never includes `solana_` prefix (script adds it)
- **Watchlist:** Always includes `solana_` prefix

**Example:**
```bash
# Watchlist has: solana_abc123
# Collection command: python collect_1m_data.py abc123
# Database stores as: solana_abc123
```

---

## Diagnostic Commands

### Quick Check
```bash
# See everything
python debug_ohlcv_collection.py
```

### Check Specific Pool
```sql
-- Replace with your pool ID
SELECT 
    timeframe,
    COUNT(*) as records,
    MIN(datetime) as start,
    MAX(datetime) as end
FROM ohlcv_data
WHERE pool_id = 'solana_YOUR_POOL_ID'
GROUP BY timeframe;
```

### Find Pool with Most Data
```sql
SELECT 
    pool_id,
    COUNT(*) as total_records
FROM ohlcv_data
GROUP BY pool_id
ORDER BY COUNT(*) DESC
LIMIT 5;
```

---

## Understanding Pool IDs

### Format
```
solana_<base58_address>

Example:
solana_4dg2tRXLCn8eHLJg42stV9bzooEG1pMnLkk5imF8wRYp
       └─────────────────┬─────────────────────────────┘
                    Pool address
```

### Where They Come From
1. **GeckoTerminal API** - Returns pool IDs with network prefix
2. **Your Watchlist** - Should match API format exactly
3. **Collection Scripts** - Add prefix automatically if needed

---

## Best Practices

### 1. Always Verify After Collection
```bash
python collect_1m_data.py <pool_id> 1
# Then immediately:
python collect_1m_data.py check
```

### 2. Use Batch Collection for Watchlist
```bash
# Safest - uses exact watchlist pool IDs
python collect_1m_data.py batch 3 10
```

### 3. Keep Watchlist Clean
```sql
-- Remove inactive or wrong entries
DELETE FROM watchlist WHERE is_active = false;

-- Verify all entries have data
SELECT 
    w.pool_id,
    w.token_symbol,
    COUNT(o.id) as has_data
FROM watchlist w
LEFT JOIN ohlcv_data o ON w.pool_id = o.pool_id
WHERE w.is_active = true
GROUP BY w.pool_id, w.token_symbol;
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python debug_ohlcv_collection.py` | Diagnose pool ID mismatches |
| `python fix_watchlist_pool_id.py` | Add pool with data to watchlist |
| `python collect_1m_data.py check` | Verify watchlist has data |
| `python collect_1m_data.py batch 3 10` | Safe batch collection |

---

## Still Having Issues?

### Check These:
1. ✅ Database connection is working
2. ✅ Pool ID format is correct (with `solana_` prefix in DB)
3. ✅ Watchlist entry exists and is active
4. ✅ Collection actually succeeded (check logs)
5. ✅ Using correct database (not test DB)

### Get Help:
```bash
# Full diagnostic
python debug_ohlcv_collection.py > ohlcv_debug.txt

# Check the output file for details
```

---

## Summary

**The Issue:** Pool ID mismatch between watchlist and collection
**The Fix:** Use `fix_watchlist_pool_id.py` to align them
**Prevention:** Always use watchlist pool IDs or batch collection

Your data is there - it's just stored under a different pool ID! 🎯
