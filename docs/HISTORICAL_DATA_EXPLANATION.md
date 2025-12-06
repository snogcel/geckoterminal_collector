# Historical Data Collection - Understanding Rolling Windows

## The "Overwriting" Behavior Explained

### What You're Seeing

When you look at `new_pools_history` records collected every 15 seconds, you might notice that `transactions_h1_buys` and `transactions_h1_sells` appear similar across multiple records. **This is actually correct behavior**, not data loss!

### Why This Happens: Rolling Windows

The API returns **rolling window metrics**:

| Field | Meaning | Window Type |
|-------|---------|-------------|
| `transactions_h1_buys` | Buys in the **last 1 hour** | Rolling 1-hour window |
| `transactions_h1_sells` | Sells in the **last 1 hour** | Rolling 1-hour window |
| `transactions_h24_buys` | Buys in the **last 24 hours** | Rolling 24-hour window |
| `transactions_h24_sells` | Sells in the **last 24 hours** | Rolling 24-hour window |
| `volume_usd_h24` | Volume in the **last 24 hours** | Rolling 24-hour window |
| `price_change_percentage_h1` | Price change in **last 1 hour** | Rolling 1-hour window |
| `price_change_percentage_h24` | Price change in **last 24 hours** | Rolling 24-hour window |

### Example Timeline

```
Time: 10:00:00 - Collect data
  transactions_h1_buys: 50  (buys from 09:00-10:00)
  
Time: 10:00:15 - Collect data (15 seconds later)
  transactions_h1_buys: 50  (buys from 09:00:15-10:00:15)
  ↑ Almost the same! Only 15 seconds of difference

Time: 10:00:30 - Collect data (30 seconds later)
  transactions_h1_buys: 51  (buys from 09:00:30-10:00:30)
  ↑ One new buy in the last 30 seconds

Time: 10:05:00 - Collect data (5 minutes later)
  transactions_h1_buys: 55  (buys from 09:05-10:05)
  ↑ More noticeable change over 5 minutes
```

## This is NOT Data Loss

### Each Record is Unique and Valuable

Every record in `new_pools_history` is unique because:

1. **Different `collected_at` timestamp** - Exact moment of collection
2. **Different rolling window** - Each collection captures a slightly different time window
3. **Captures market evolution** - Shows how metrics change over time

### What You're Actually Storing

```sql
-- Example: Same pool, different collection times
pool_id: solana_ABC123
collected_at: 2025-11-25 10:00:00.123456
transactions_h1_buys: 50  (window: 09:00:00 - 10:00:00)

pool_id: solana_ABC123
collected_at: 2025-11-25 10:00:15.789012  ← Different time
transactions_h1_buys: 50  (window: 09:00:15 - 10:00:15)  ← Different window

pool_id: solana_ABC123
collected_at: 2025-11-25 10:00:30.456789  ← Different time
transactions_h1_buys: 51  (window: 09:00:30 - 10:00:30)  ← Different window, new buy!
```

## Why Collect Every 15 Seconds?

### Benefits of High-Frequency Collection

1. **Detect Rapid Changes:**
   - Catch sudden volume spikes
   - Identify momentum shifts quickly
   - Spot new trading activity immediately

2. **Better Signal Analysis:**
   - More data points for trend detection
   - Smoother signal calculations
   - Earlier warning of changes

3. **Capture Short-Lived Opportunities:**
   - Meme tokens can pump and dump in minutes
   - Early detection = better entry points
   - Don't miss fast-moving opportunities

### The Trade-off

- **More records:** Yes, you'll have many records per pool
- **Similar values:** Yes, adjacent records will be similar
- **Storage cost:** Higher, but disk is cheap
- **Value:** High for trading signals and analysis

## How to Analyze This Data

### 1. Look at Changes Over Time

```sql
-- See how metrics evolve for a pool
SELECT 
    collected_at,
    transactions_h1_buys,
    transactions_h1_buys - LAG(transactions_h1_buys) OVER (ORDER BY collected_at) as new_buys,
    volume_usd_h24,
    signal_score
FROM new_pools_history
WHERE pool_id = 'solana_ABC123'
ORDER BY collected_at DESC
LIMIT 20;
```

### 2. Calculate Rate of Change

```sql
-- Calculate how fast metrics are changing
SELECT 
    pool_id,
    collected_at,
    transactions_h1_buys,
    (transactions_h1_buys - LAG(transactions_h1_buys) OVER (PARTITION BY pool_id ORDER BY collected_at)) 
        / EXTRACT(EPOCH FROM (collected_at - LAG(collected_at) OVER (PARTITION BY pool_id ORDER BY collected_at))) * 60 
        as buys_per_minute
FROM new_pools_history
WHERE collected_at >= NOW() - INTERVAL '1 hour'
ORDER BY buys_per_minute DESC NULLS LAST
LIMIT 10;
```

### 3. Detect Acceleration

```sql
-- Find pools where activity is accelerating
WITH changes AS (
    SELECT 
        pool_id,
        collected_at,
        transactions_h1_buys - LAG(transactions_h1_buys) OVER (PARTITION BY pool_id ORDER BY collected_at) as delta
    FROM new_pools_history
    WHERE collected_at >= NOW() - INTERVAL '5 minutes'
)
SELECT 
    pool_id,
    AVG(delta) as avg_change,
    MAX(delta) as max_change,
    COUNT(*) as samples
FROM changes
WHERE delta IS NOT NULL
GROUP BY pool_id
HAVING AVG(delta) > 0
ORDER BY avg_change DESC
LIMIT 10;
```

## Understanding the Data Pattern

### Normal Pattern (Healthy)

```
Time    Buys  Change
10:00   50    -
10:01   51    +1
10:02   52    +1
10:03   53    +1
10:04   54    +1
```
**Interpretation:** Steady growth, consistent activity

### Spike Pattern (Signal!)

```
Time    Buys  Change
10:00   50    -
10:01   51    +1
10:02   52    +1
10:03   67    +15  ← Spike!
10:04   82    +15  ← Continuing!
```
**Interpretation:** Sudden surge in activity, potential signal

### Plateau Pattern

```
Time    Buys  Change
10:00   50    -
10:01   50    0
10:02   50    0
10:03   50    0
10:04   50    0
```
**Interpretation:** No new activity, stable/declining interest

## Verification: Is Data Actually Unique?

### Run This Query

```sql
-- Check if you have truly unique records
SELECT 
    pool_id,
    collected_at,
    transactions_h1_buys,
    transactions_h1_sells,
    volume_usd_h24,
    signal_score
FROM new_pools_history
WHERE pool_id = (
    SELECT pool_id 
    FROM new_pools_history 
    GROUP BY pool_id 
    ORDER BY COUNT(*) DESC 
    LIMIT 1
)
ORDER BY collected_at DESC
LIMIT 20;
```

**What to Look For:**
- ✅ Different `collected_at` values (should all be unique)
- ✅ Gradually changing metrics (not identical)
- ✅ Occasional jumps in values (new activity)

### Check for Actual Duplicates

```sql
-- This should return 0 rows if everything is working correctly
SELECT pool_id, collected_at, COUNT(*)
FROM new_pools_history
GROUP BY pool_id, collected_at
HAVING COUNT(*) > 1;
```

If this returns rows, you have actual duplicates (a problem).
If it returns 0 rows, your data is unique (correct behavior).

## Common Misconceptions

### ❌ Misconception 1: "Same values = duplicate data"
**Reality:** Rolling windows naturally have overlapping data. This is expected and valuable.

### ❌ Misconception 2: "I should only collect once per hour"
**Reality:** High-frequency collection catches rapid changes that hourly collection would miss.

### ❌ Misconception 3: "This wastes storage space"
**Reality:** Storage is cheap. Missing a profitable trade signal is expensive.

### ❌ Misconception 4: "The data isn't changing"
**Reality:** Look at the deltas between records, not absolute values.

## Best Practices

### 1. Focus on Deltas, Not Absolutes

```python
# Good: Look at changes
current_buys = 51
previous_buys = 50
new_activity = current_buys - previous_buys  # +1 new buy

# Less useful: Look at absolute values
current_buys = 51  # Doesn't tell you if this is new or old activity
```

### 2. Use Time-Weighted Analysis

```python
# Calculate rate of change
time_diff_seconds = (current_time - previous_time).total_seconds()
buys_per_second = (current_buys - previous_buys) / time_diff_seconds
buys_per_minute = buys_per_second * 60
```

### 3. Look for Acceleration

```python
# Detect when activity is speeding up
recent_rate = calculate_rate(last_5_records)
historical_rate = calculate_rate(last_20_records)

if recent_rate > historical_rate * 2:
    print("Activity is accelerating!")  # Strong signal
```

## Summary

**Your data is NOT being overwritten.** Each record is unique and captures a different moment in time with a different rolling window. The similarity between adjacent records is expected and normal.

**Key Points:**
- ✅ Each record has a unique `collected_at` timestamp
- ✅ Rolling windows naturally overlap
- ✅ High-frequency collection is valuable for trading signals
- ✅ Focus on changes (deltas) between records
- ✅ Look for acceleration and spikes, not absolute values

**To Verify:**
Run the diagnostic script: `python check_history_uniqueness.py`

This will show you that:
1. No duplicate (pool_id, collected_at) combinations exist
2. Metrics do change over time
3. Timestamps have microsecond precision
4. Data is being collected correctly

## Further Reading

- [Signal Analysis Guide](SIGNAL_ANALYSIS_GUIDE.md) - How signals use this historical data
- [Interval Configuration](INTERVAL_CONFIGURATION.md) - Optimizing collection frequency
