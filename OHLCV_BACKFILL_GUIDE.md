# OHLCV Data Backfill Guide

## Quick Reference

You have hit API rate limits and want to backfill OHLCV data for your watchlist pools with complete datasets.

---

## 🚀 Quick Commands

### 1. Check What's Missing
```bash
python collect_historical_with_rate_limits.py check
```

This will:
- ✅ Check all watchlist pools
- ✅ Show which timeframes are missing
- ✅ Show how many records exist for each timeframe
- ✅ List pools that need backfilling

**Example output:**
```
Checking SOL/USDC (abc123)...
  Has 720 1h records
  Has 180 4h records
  Missing 1d data
  Missing 5m data
```

---

### 2. Backfill All Watchlist Pools (Conservative)
```bash
python collect_historical_with_rate_limits.py
```

**Default settings:**
- Timeframes: `1h`, `4h`, `1d` (most important for analysis)
- Days back: 30 days
- Delay between pools: 10 seconds
- Delay between timeframes: 5 seconds

**Rate limit friendly:** ~6 pools per minute (well under 30 req/min limit)

---

### 3. Backfill Single Pool
```bash
python collect_historical_with_rate_limits.py single <pool_id> [timeframe] [days_back]
```

**Examples:**
```bash
# Collect 1h data for 30 days (default)
python collect_historical_with_rate_limits.py single abc123

# Collect 5m data for 7 days
python collect_historical_with_rate_limits.py single abc123 5m 7

# Collect 1d data for 90 days
python collect_historical_with_rate_limits.py single abc123 1d 90
```

---

## 📊 Available Timeframes

| Timeframe | Description | Records/Day | Best For |
|-----------|-------------|-------------|----------|
| `1m` | 1 minute | 1,440 | High-frequency trading |
| `5m` | 5 minutes | 288 | Intraday analysis |
| `15m` | 15 minutes | 96 | Short-term patterns |
| `1h` | 1 hour | 24 | **General analysis** ⭐ |
| `4h` | 4 hours | 6 | **Swing trading** ⭐ |
| `12h` | 12 hours | 2 | Position trading |
| `1d` | 1 day | 1 | **Long-term trends** ⭐ |

**Recommended for backfill:** `1h`, `4h`, `1d` (marked with ⭐)

---

## ⚙️ Rate Limit Strategy

### API Limits
- **30 requests per minute** (hard limit)
- **10,000 requests per day** (soft limit)

### Script Protection
The script automatically:
- ✅ Waits between pools (default: 10s)
- ✅ Waits between timeframes (default: 5s)
- ✅ Waits between paginated requests (2s)
- ✅ Handles 429 errors with exponential backoff

### Calculation
```
Time per pool = (num_timeframes × 5s) + 10s
Example: 3 timeframes = (3 × 5s) + 10s = 25s per pool

Pools per hour = 3600s / 25s = 144 pools
API calls per hour = 144 pools × 3 timeframes = 432 calls (well under limit)
```

---

## 🎯 Recommended Workflows

### Workflow 1: Quick Backfill (Most Important Data)
```bash
# Step 1: Check what's missing
python collect_historical_with_rate_limits.py check

# Step 2: Collect essential timeframes (1h, 4h, 1d)
python collect_historical_with_rate_limits.py
```

**Time estimate:** ~25 seconds per pool
- 10 pools = ~4 minutes
- 50 pools = ~20 minutes
- 100 pools = ~40 minutes

---

### Workflow 2: Complete Backfill (All Timeframes)
```python
# Edit collect_historical_with_rate_limits.py
# Change line ~60:
timeframes = ['1m', '5m', '15m', '1h', '4h', '12h', '1d']  # All timeframes

# Then run:
python collect_historical_with_rate_limits.py
```

**Time estimate:** ~50 seconds per pool
- 10 pools = ~8 minutes
- 50 pools = ~40 minutes
- 100 pools = ~80 minutes

---

### Workflow 3: Targeted Backfill (Specific Pools)
```bash
# Get pool IDs from watchlist
psql -d gecko_terminal_collector -c "SELECT pool_id, token_symbol FROM watchlist WHERE is_active = true;"

# Backfill specific pools
python collect_historical_with_rate_limits.py single pool_id_1 1h 30
python collect_historical_with_rate_limits.py single pool_id_2 1h 30
python collect_historical_with_rate_limits.py single pool_id_3 1h 30
```

---

## 🔧 Customization

### Adjust Delays (Faster Collection)
Edit `collect_historical_with_rate_limits.py`:

```python
# Line ~60 - More aggressive (use with caution)
asyncio.run(collect_historical_with_delays(
    timeframes=['1h', '4h', '1d'],
    days_back=30,
    delay_between_pools=5,      # Reduced from 10s
    delay_between_timeframes=2  # Reduced from 5s
))
```

**Risk:** Higher chance of hitting rate limits

---

### Adjust Date Range
```python
# Collect more history
asyncio.run(collect_historical_with_delays(
    days_back=90,  # 90 days instead of 30
))
```

---

### Collect Specific Timeframes
```python
# Only collect what you need
asyncio.run(collect_historical_with_delays(
    timeframes=['1h'],  # Just 1h data
    days_back=30,
))
```

---

## 📈 Monitoring Progress

### Watch Logs
```bash
# In another terminal
tail -f logs/collector.log | grep -i "ohlcv\|historical"
```

### Check Database
```sql
-- Count records per timeframe
SELECT 
    timeframe,
    COUNT(*) as record_count,
    COUNT(DISTINCT pool_id) as pool_count,
    MIN(datetime) as earliest,
    MAX(datetime) as latest
FROM ohlcv_data
GROUP BY timeframe
ORDER BY timeframe;

-- Check specific pool
SELECT 
    timeframe,
    COUNT(*) as records,
    MIN(datetime) as start_date,
    MAX(datetime) as end_date
FROM ohlcv_data
WHERE pool_id = 'solana_your_pool_id'
GROUP BY timeframe;

-- Find pools with incomplete data
SELECT 
    w.pool_id,
    w.token_symbol,
    COUNT(DISTINCT o.timeframe) as timeframes_collected
FROM watchlist w
LEFT JOIN ohlcv_data o ON w.pool_id = o.pool_id
WHERE w.is_active = true
GROUP BY w.pool_id, w.token_symbol
HAVING COUNT(DISTINCT o.timeframe) < 7  -- Less than all 7 timeframes
ORDER BY timeframes_collected;
```

---

## 🚨 Troubleshooting

### Issue 1: Rate Limit Errors (429)
**Symptom:** `Rate limit exceeded` errors

**Solution:**
```python
# Increase delays in the script
delay_between_pools=15,      # Increase from 10s
delay_between_timeframes=7   # Increase from 5s
```

---

### Issue 2: Slow Progress
**Symptom:** Taking too long

**Solution:**
```bash
# Collect fewer timeframes first
# Edit script to use only: ['1h', '1d']

# Or collect in batches
python collect_historical_with_rate_limits.py single pool1 1h
python collect_historical_with_rate_limits.py single pool2 1h
# ... etc
```

---

### Issue 3: Missing Data for Some Pools
**Symptom:** Some pools have no data

**Possible causes:**
1. Pool is too new (no historical data available)
2. Pool ID format is wrong (check if it needs 'solana_' prefix)
3. Pool was delisted/removed from exchange

**Check:**
```sql
-- See which pools have data
SELECT DISTINCT pool_id FROM ohlcv_data;

-- Compare with watchlist
SELECT pool_id FROM watchlist WHERE is_active = true;
```

---

### Issue 4: Duplicate Data
**Symptom:** Same data collected multiple times

**Solution:** The script uses `force_refresh=False` by default, which skips existing data. If you want to force re-collection:

```python
result = await collector.collect_for_pool(
    pool_id=pool_id,
    timeframe=timeframe,
    start_date=start_date,
    end_date=end_date,
    force_refresh=True  # Change to True
)
```

---

## 💡 Pro Tips

1. **Start with essential timeframes** (`1h`, `4h`, `1d`) - these cover 90% of use cases

2. **Run during off-peak hours** - Less competition for API limits

3. **Use `check` command first** - Know what you need before starting

4. **Monitor the first few pools** - Make sure it's working before leaving it running

5. **Keep delays conservative** - Better slow and complete than fast and incomplete

6. **Check database after completion** - Verify data was actually collected

7. **For large watchlists (>50 pools)** - Consider running overnight

---

## 📝 Example Session

```bash
# 1. Check current state
python collect_historical_with_rate_limits.py check

# Output shows:
# - 25 pools in watchlist
# - Most have 1h data
# - Missing 4h and 1d data

# 2. Backfill missing timeframes
python collect_historical_with_rate_limits.py

# 3. Monitor progress (in another terminal)
tail -f logs/collector.log

# 4. Verify completion
psql -d gecko_terminal_collector -c "
SELECT timeframe, COUNT(*) 
FROM ohlcv_data 
GROUP BY timeframe;
"

# Output:
# timeframe | count
# ----------+-------
# 1h        | 18000
# 4h        | 4500
# 1d        | 750
```

---

## 🎯 Quick Decision Matrix

| Scenario | Command | Time Estimate |
|----------|---------|---------------|
| Just checking | `check` | 1 minute |
| Essential data only | Default (1h, 4h, 1d) | 25s × pools |
| Complete dataset | Edit to all timeframes | 50s × pools |
| Single pool urgent | `single pool_id 1h` | 30 seconds |
| Overnight backfill | Default with 100+ pools | 6-8 hours |

---

## 📚 Related Files

- `collect_historical_with_rate_limits.py` - Main backfill script
- `collect_historical_ohlcv.py` - Alternative collection script
- `docs/HISTORICAL_DATA_EXPLANATION.md` - Detailed documentation
- `config.yaml` - Rate limit configuration

---

## ✅ Success Checklist

After backfilling, verify:

- [ ] All watchlist pools have data
- [ ] All desired timeframes are present
- [ ] Date ranges are complete (no gaps)
- [ ] No error messages in logs
- [ ] Database record counts match expectations

```sql
-- Quick verification query
SELECT 
    'Total pools' as metric,
    COUNT(DISTINCT pool_id) as value
FROM ohlcv_data
UNION ALL
SELECT 
    'Total records',
    COUNT(*)
FROM ohlcv_data
UNION ALL
SELECT 
    'Timeframes',
    COUNT(DISTINCT timeframe)
FROM ohlcv_data;
```

---

**You're all set to backfill your OHLCV data!** 🚀

Start with `python collect_historical_with_rate_limits.py check` to see what you need.
