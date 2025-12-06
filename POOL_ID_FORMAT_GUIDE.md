# Pool ID Format Guide

## The Problem

Different parts of the system handle pool IDs differently, causing confusion and data mismatches.

---

## Pool ID Formats

### **Database Storage (Watchlist & OHLCV)**
```
Format: solana_<address>
Example: solana_4dg2tRXLCn8eHLJg42stV9bzooEG1pMnLkk5imF8wRYp
```

### **API Requests**
```
Format: <address> (no prefix)
Example: 4dg2tRXLCn8eHLJg42stV9bzooEG1pMnLkk5imF8wRYp
```

### **Collection Scripts**
```
Command line: <address> (no prefix)
Internal: Depends on collector type
```

---

## Collector Behavior

### **OHLCVCollector (Regular)**
- **Input:** Accepts both formats
- **Processing:** Strips prefix if present
- **Storage:** Adds prefix back
- **Result:** Always stores as `solana_<address>`

```python
# From ohlcv_collector.py line 169-170
if pool_id.startswith(f"{self.network}_"):
    pool_address = pool_id[len(f"{self.network}_"):]
```

### **HistoricalOHLCVCollector**
- **Input:** Expects NO prefix
- **Processing:** Adds prefix internally
- **Storage:** Stores as `solana_<address>`
- **Result:** Always stores as `solana_<address>`

```python
# From historical_ohlcv_collector.py line 237
database_id = self.network+"_"+pool_id
```

**⚠️ Bug:** If you pass `solana_abc123`, it becomes `solana_solana_abc123`!

---

## Script Fixes

### **collect_historical_with_rate_limits_1m.py** ✅ FIXED

**Before:**
```python
pool_ids = [entry.pool_id for entry in entries]
# Passes: solana_abc123
# Collector makes: solana_solana_abc123 ❌
```

**After:**
```python
pool_ids = [entry.pool_id.replace('solana_', '') for entry in entries]
# Passes: abc123
# Collector makes: solana_abc123 ✅
```

### **collect_1m_data.py** ✅ FIXED

**Before:**
```python
sample_data = await db_manager.get_ohlcv_data(
    pool_id=f"solana_{pool_id}",  # Adds prefix
    ...
)
# If pool_id already has prefix: solana_solana_abc123 ❌
```

**After:**
```python
# Strip prefix first, then add it
pool_id_clean = pool_id.replace('solana_', '')
sample_data = await db_manager.get_ohlcv_data(
    pool_id=f"solana_{pool_id_clean}",
    ...
)
# Always results in: solana_abc123 ✅
```

---

## Best Practices

### **1. When Reading from Watchlist**
```python
entries = await db_manager.get_active_watchlist_entries()

# For HistoricalOHLCVCollector - strip prefix
pool_ids = [entry.pool_id.replace('solana_', '') for entry in entries]

# For OHLCVCollector - either format works
pool_ids = [entry.pool_id for entry in entries]  # OK
pool_ids = [entry.pool_id.replace('solana_', '') for entry in entries]  # Also OK
```

### **2. When Querying Database**
```python
# Always use full format with prefix
data = await db_manager.get_ohlcv_data(
    pool_id='solana_abc123',  # ✅ Correct
    ...
)

# NOT this:
data = await db_manager.get_ohlcv_data(
    pool_id='abc123',  # ❌ Won't find data
    ...
)
```

### **3. When Calling Collectors**
```python
# HistoricalOHLCVCollector - NO prefix
result = await historical_collector.collect_for_pool(
    pool_id='abc123',  # ✅ Correct
    ...
)

# OHLCVCollector - either format
result = await ohlcv_collector.collect_for_pool(
    pool_id='solana_abc123',  # ✅ OK
    ...
)
result = await ohlcv_collector.collect_for_pool(
    pool_id='abc123',  # ✅ Also OK
    ...
)
```

### **4. When Adding to Watchlist**
```python
# Always include prefix
watchlist_data = {
    'pool_id': 'solana_abc123',  # ✅ Correct
    ...
}
```

---

## Quick Reference Table

| Component | Format | Example |
|-----------|--------|---------|
| **Watchlist (DB)** | `solana_<addr>` | `solana_abc123` |
| **OHLCV Data (DB)** | `solana_<addr>` | `solana_abc123` |
| **API Request** | `<addr>` | `abc123` |
| **HistoricalOHLCVCollector Input** | `<addr>` | `abc123` |
| **OHLCVCollector Input** | Both OK | `abc123` or `solana_abc123` |
| **Command Line** | `<addr>` | `abc123` |
| **Database Query** | `solana_<addr>` | `solana_abc123` |

---

## Common Mistakes

### ❌ **Mistake 1: Double Prefix**
```python
# Watchlist has: solana_abc123
pool_id = entry.pool_id  # solana_abc123
await historical_collector.collect_for_pool(pool_id)
# Collector makes: solana_solana_abc123 ❌
```

**Fix:**
```python
pool_id = entry.pool_id.replace('solana_', '')  # abc123
await historical_collector.collect_for_pool(pool_id)
# Collector makes: solana_abc123 ✅
```

### ❌ **Mistake 2: Missing Prefix in Query**
```python
# Collected with: abc123
# Stored as: solana_abc123
data = await db_manager.get_ohlcv_data(pool_id='abc123')
# Returns: Nothing ❌
```

**Fix:**
```python
data = await db_manager.get_ohlcv_data(pool_id='solana_abc123')
# Returns: Data ✅
```

### ❌ **Mistake 3: Inconsistent Format**
```python
# Collection
await collector.collect_for_pool('abc123')  # Stores as solana_abc123

# Query
data = await db_manager.get_ohlcv_data(pool_id='abc123')  # ❌ Mismatch
```

**Fix:**
```python
# Collection
await collector.collect_for_pool('abc123')  # Stores as solana_abc123

# Query
data = await db_manager.get_ohlcv_data(pool_id='solana_abc123')  # ✅ Match
```

---

## Debugging Pool ID Issues

### **Step 1: Check What's in Database**
```bash
python debug_ohlcv_collection.py
```

Shows:
- Watchlist pool IDs
- OHLCV pool IDs
- Mismatches

### **Step 2: Verify Format**
```sql
-- Check watchlist format
SELECT pool_id FROM watchlist LIMIT 5;

-- Check OHLCV format
SELECT DISTINCT pool_id FROM ohlcv_data LIMIT 5;

-- Should both show: solana_<address>
```

### **Step 3: Fix Mismatches**
```bash
python fix_watchlist_pool_id.py
```

---

## Testing Your Fix

### **Test 1: Collection**
```bash
# Get pool ID from watchlist
psql -c "SELECT pool_id FROM watchlist LIMIT 1;"
# Output: solana_abc123

# Collect (strip prefix for historical collector)
python collect_historical_with_rate_limits_1m.py single abc123 1m 1
```

### **Test 2: Verification**
```bash
# Check data was stored correctly
psql -c "SELECT pool_id, COUNT(*) FROM ohlcv_data WHERE pool_id = 'solana_abc123' GROUP BY pool_id;"
# Should show records
```

### **Test 3: Query**
```python
# Query with full prefix
data = await db_manager.get_ohlcv_data(
    pool_id='solana_abc123',
    timeframe='1m'
)
# Should return data
```

---

## Summary

**Golden Rule:** 
- **Storage = Always with prefix** (`solana_abc123`)
- **HistoricalOHLCVCollector = Always without prefix** (`abc123`)
- **OHLCVCollector = Either format works**
- **Queries = Always with prefix** (`solana_abc123`)

**When in doubt:**
1. Check what's in the database: `python debug_ohlcv_collection.py`
2. Strip prefix before passing to HistoricalOHLCVCollector
3. Add prefix when querying database

---

## Files Fixed

1. ✅ `collect_historical_with_rate_limits_1m.py` - Strips prefix before collection
2. ✅ `collect_1m_data.py` - Handles prefix correctly in verification
3. ✅ `debug_ohlcv_collection.py` - Shows format mismatches
4. ✅ `fix_watchlist_pool_id.py` - Fixes watchlist entries

**Your scripts should now work correctly with watchlist pool IDs!** 🎯
