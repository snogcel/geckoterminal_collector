# 1-Minute Data Collection Guide

## 🎯 Quick Commands

### **Check Current Coverage**
```bash
python collect_1m_data.py check
```
Shows which pools have 1m data and how much.

### **Collect for Single Pool**
```bash
# Last 7 days (recommended)
python collect_1m_data.py <pool_id> 7

# Last 24 hours (quick test)
python collect_1m_data.py <pool_id> 1

# Last 30 days (maximum recommended)
python collect_1m_data.py <pool_id> 30
```

### **Collect for Multiple Pools (Batch)**
```bash
# 3 days for first 10 watchlist pools
python collect_1m_data.py batch 3 10

# 7 days for first 5 pools
python collect_1m_data.py batch 7 5
```

---

## 📊 Data Volume Reference

| Days | Records/Pool | 10 Pools | 50 Pools | Time Estimate |
|------|--------------|----------|----------|---------------|
| 1 | 1,440 | 14,400 | 72,000 | 2 min |
| 3 | 4,320 | 43,200 | 216,000 | 6 min |
| 7 | 10,080 | 100,800 | 504,000 | 14 min |
| 14 | 20,160 | 201,600 | 1,008,000 | 28 min |
| 30 | 43,200 | 432,000 | 2,160,000 | 60 min |

**Recommendation:** Start with 7 days, expand if needed.

---

## ⚡ Why 1m Data is Different

### **Volume**
- 1m data = 1,440 records/day
- 1h data = 24 records/day
- **1m is 60x more data than 1h**

### **API Calls**
- GeckoTerminal returns max 1,000 records per call
- 7 days of 1m data = ~10 API calls per pool
- 30 days of 1m data = ~43 API calls per pool

### **Use Cases**
- ✅ High-frequency trading strategies
- ✅ Intraday pattern analysis
- ✅ Precise entry/exit timing
- ✅ Scalping strategies
- ❌ Long-term trend analysis (use 1h or 1d)
- ❌ Storage-constrained systems

---

## 🚀 Recommended Workflow

### **Step 1: Check What You Have**
```bash
python collect_1m_data.py check
```

**Output:**
```
✓ SOL/USDC    10,080 records  (2025-11-19 to 2025-11-26, 7 days)
✓ BONK/SOL     4,320 records  (2025-11-23 to 2025-11-26, 3 days)
✗ ORCA/USDC    No 1m data
```

### **Step 2: Collect for Priority Pools**
```bash
# Get pool IDs from watchlist
psql -d gecko_terminal_collector -c "
SELECT pool_id, token_symbol 
FROM watchlist 
WHERE is_active = true 
ORDER BY metadata_json->>'signal_score' DESC 
LIMIT 10;
"

# Collect for each high-priority pool
python collect_1m_data.py pool_id_1 7
python collect_1m_data.py pool_id_2 7
python collect_1m_data.py pool_id_3 7
```

### **Step 3: Verify**
```bash
python collect_1m_data.py check
```

---

## 💡 Best Practices

### **1. Start Small**
```bash
# Test with 1 day first
python collect_1m_data.py <pool_id> 1

# If successful, expand to 7 days
python collect_1m_data.py <pool_id> 7
```

### **2. Prioritize Pools**
Collect 1m data only for pools you actively trade:
```sql
-- Get your most active pools
SELECT 
    pool_id,
    token_symbol,
    metadata_json->>'signal_score' as score
FROM watchlist
WHERE is_active = true
ORDER BY (metadata_json->>'signal_score')::float DESC
LIMIT 10;
```

### **3. Use Appropriate Timeframes**
| Strategy | Recommended Timeframe |
|----------|----------------------|
| Scalping | 1m, 5m |
| Day trading | 5m, 15m, 1h |
| Swing trading | 1h, 4h |
| Position trading | 4h, 1d |

### **4. Monitor Storage**
```sql
-- Check database size
SELECT 
    pg_size_pretty(pg_database_size('gecko_terminal_collector')) as db_size;

-- Check OHLCV table size
SELECT 
    pg_size_pretty(pg_total_relation_size('ohlcv_data')) as table_size;

-- Count records by timeframe
SELECT 
    timeframe,
    COUNT(*) as records,
    pg_size_pretty(SUM(pg_column_size(ohlcv_data.*))) as size
FROM ohlcv_data
GROUP BY timeframe
ORDER BY COUNT(*) DESC;
```

---

## 🎯 Example Sessions

### **Example 1: Quick Test**
```bash
# Check current state
python collect_1m_data.py check

# Collect 24 hours for one pool
python collect_1m_data.py abc123 1

# Verify
python collect_1m_data.py check
```

**Time:** ~2 minutes

---

### **Example 2: Single Pool Deep Dive**
```bash
# Collect 30 days of 1m data for detailed analysis
python collect_1m_data.py abc123 30

# Output:
# Expected records: ~43,200
# Estimated API calls: ~44
# Estimated time: ~88 seconds
```

**Time:** ~2 minutes

---

### **Example 3: Batch Collection**
```bash
# Collect 7 days for top 10 pools
python collect_1m_data.py batch 7 10

# Output:
# Expected total records: ~100,800
# Estimated time: ~20 minutes
```

**Time:** ~20 minutes

---

## 🔧 Advanced Usage

### **Collect Specific Date Range**
Edit `collect_1m_data.py` to add custom date range:

```python
# Around line 30, modify:
start_date = datetime(2025, 11, 20)  # Specific start
end_date = datetime(2025, 11, 26)    # Specific end
```

### **Adjust Pagination Delay**
```python
# Around line 50, modify:
collector.pagination_delay = 1.0  # Faster (risky)
# or
collector.pagination_delay = 3.0  # Slower (safer)
```

### **Force Refresh Existing Data**
```python
# Around line 120, modify:
force_refresh = True  # Always overwrite
```

---

## 📈 Monitoring Progress

### **Watch Logs**
```bash
tail -f logs/collector.log | grep -i "1m\|minute"
```

### **Check Database in Real-Time**
```sql
-- Count 1m records
SELECT COUNT(*) FROM ohlcv_data WHERE timeframe = '1m';

-- Watch it grow (run repeatedly)
SELECT 
    pool_id,
    COUNT(*) as records,
    MAX(datetime) as latest
FROM ohlcv_data
WHERE timeframe = '1m'
GROUP BY pool_id
ORDER BY latest DESC;
```

---

## ⚠️ Troubleshooting

### **Issue: Rate Limit Errors**
**Solution:** Increase pagination delay
```python
collector.pagination_delay = 3.0  # Increase from 2.0
```

### **Issue: Incomplete Data**
**Symptom:** Coverage < 90%

**Causes:**
1. Pool is too new (no historical data)
2. Pool had low activity (gaps in data)
3. API returned partial data

**Solution:**
```bash
# Try collecting again with force refresh
# Edit script to set force_refresh = True
python collect_1m_data.py <pool_id> 7
```

### **Issue: Database Growing Too Large**
**Solution:** Archive or delete old 1m data
```sql
-- Delete 1m data older than 30 days
DELETE FROM ohlcv_data 
WHERE timeframe = '1m' 
AND datetime < NOW() - INTERVAL '30 days';

-- Or archive to separate table
CREATE TABLE ohlcv_data_archive AS 
SELECT * FROM ohlcv_data 
WHERE timeframe = '1m' 
AND datetime < NOW() - INTERVAL '30 days';

DELETE FROM ohlcv_data 
WHERE timeframe = '1m' 
AND datetime < NOW() - INTERVAL '30 days';
```

---

## 🎯 Quick Decision Matrix

| Scenario | Command | Time | Records |
|----------|---------|------|---------|
| Quick test | `python collect_1m_data.py pool_id 1` | 2 min | 1,440 |
| Standard collection | `python collect_1m_data.py pool_id 7` | 2 min | 10,080 |
| Deep analysis | `python collect_1m_data.py pool_id 30` | 2 min | 43,200 |
| Batch (10 pools) | `python collect_1m_data.py batch 7 10` | 20 min | 100,800 |
| Check coverage | `python collect_1m_data.py check` | 1 min | - |

---

## 📚 Comparison with Other Methods

### **Using collect_historical_with_rate_limits.py**
```bash
# Also works, but less optimized for 1m
python collect_historical_with_rate_limits.py single <pool_id> 1m 7
```

### **Using collect_1m_data.py (Recommended)**
```bash
# Optimized for 1m data with:
# - Progress monitoring
# - Coverage calculation
# - Batch processing
# - Better error handling
python collect_1m_data.py <pool_id> 7
```

---

## ✅ Success Checklist

After collecting 1m data:

- [ ] Run `python collect_1m_data.py check`
- [ ] Verify coverage is > 90%
- [ ] Check database size is acceptable
- [ ] Test querying the data
- [ ] Verify date ranges are correct

```sql
-- Quick verification
SELECT 
    pool_id,
    COUNT(*) as records,
    MIN(datetime) as start_date,
    MAX(datetime) as end_date,
    ROUND(COUNT(*) / EXTRACT(EPOCH FROM (MAX(datetime) - MIN(datetime))) * 60) as coverage_pct
FROM ohlcv_data
WHERE timeframe = '1m'
GROUP BY pool_id;
```

---

## 🚀 You're Ready!

**Start with:**
```bash
python collect_1m_data.py check
python collect_1m_data.py <your_pool_id> 7
```

**For high-frequency trading, 1m data is essential. Collect it for your most active pools!** 📈
