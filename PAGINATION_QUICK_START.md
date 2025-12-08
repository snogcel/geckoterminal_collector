# Pagination Quick Start Guide

## TL;DR

Pagination is now enabled for new pools collection. You can fetch up to 10 pages per collection cycle instead of just 1.

## Quick Setup (3 steps)

### 1. Update Config

Edit `config.yaml`:

```yaml
new_pools:
  max_pages: 10        # Fetch 10 pages (default)
  page_delay: 1.0      # 1 second between pages
  
  networks:
    solana:
      interval: "30s"  # IMPORTANT: Increase from 15s to avoid rate limits
      max_pages: 10
```

### 2. Test It

```bash
python test_pagination.py
```

Expected output:
```
Page 1: Received 20 pools, 20 new (after deduplication)
Page 2: Received 18 pools, 18 new (after deduplication)
Page 3: Received 19 pools, 19 new (after deduplication)
Total unique pools collected: 57
```

### 3. Run Collector

```bash
python -m gecko_terminal_collector.main
```

Watch logs for:
```
INFO - Pagination enabled: fetching up to 10 pages with 1.0s delay
INFO - Pagination complete: collected 180 unique pools across 10 pages
```

## What You Get

**Before**: ~20 pools per collection  
**After**: ~150-200 pools per collection (10x improvement!)

## Important: Rate Limits

⚠️ **With 10 pages, you MUST increase the collection interval**

| max_pages | Recommended interval | Calls/min |
|-----------|---------------------|-----------|
| 3         | 15s                 | 12        |
| 5         | 20s                 | 15        |
| 10        | 30s                 | 20        |

Free tier limit: 30 calls/minute

## Recommended Settings

### Balanced (Recommended for Solana)
```yaml
solana:
  max_pages: 5          # ~100 pools per collection
  page_delay: 1.5       # Safe delay to avoid rate limits
  interval: "45s"       # Allows collection to complete
```

### Aggressive (Maximum Data)
```yaml
solana:
  max_pages: 10         # ~200 pools per collection
  page_delay: 2.0       # Longer delay for safety
  interval: "60s"       # Ensure completion before next run
```

### Conservative (If Experiencing Issues)
```yaml
solana:
  max_pages: 3          # ~60 pools per collection
  page_delay: 1.5       # Safe delay
  interval: "30s"       # Frequent but fast
```

## Troubleshooting

### Getting 429 errors?
- Increase `interval` to "30s" or "45s"
- Increase `page_delay` to 1.5 or 2.0
- Reduce `max_pages` to 5

### Collection too slow?
- Reduce `max_pages` to 5
- Reduce `page_delay` to 0.8 (watch rate limits!)

### Not seeing more pools?
- Check network activity (may not have 10 full pages)
- Check logs for "Empty page" messages
- Verify config is loaded correctly

## Verify It's Working

Check collection metadata in logs:
```python
{
    'pages_fetched': 10,           # Should be > 1
    'unique_pools_collected': 180, # Should be > 20
    'duplicates_filtered': 0       # Should be low
}
```

## Need Help?

See full documentation: `NEW_POOLS_PAGINATION_GUIDE.md`
