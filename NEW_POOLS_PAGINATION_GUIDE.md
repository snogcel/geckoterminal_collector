# New Pools Pagination Implementation Guide

## Overview

Pagination support has been added to the new pools collection process to improve data coverage and reduce gaps in historical data. The GeckoTerminal API allows fetching up to 10 pages of new pools data (free tier limit).

## What Changed

### 1. API Client Layer (`gecko_terminal_collector/clients/gecko_client.py`)

- **Updated `get_new_pools_by_network()` method** to accept a `page` parameter (1-10)
- Uses direct API calls to support pagination since the SDK may not support it
- Maintains backward compatibility (defaults to page 1)

```python
async def get_new_pools_by_network(self, network: str, page: int = 1) -> Any:
    """Get new pools by network with pagination support."""
```

### 2. Collector Layer (`gecko_terminal_collector/collectors/new_pools_collector.py`)

- **Enhanced `collect()` method** to loop through multiple pages
- **Deduplication logic** to avoid storing duplicate pools across pages
- **Smart pagination** that stops early if pages are empty or have fewer pools
- **Configurable settings** for max pages and delay between requests

Key features:
- Fetches up to `max_pages` per collection cycle
- Adds configurable delay between page requests to respect rate limits
- Tracks unique pool IDs to filter duplicates
- Stops early if a page is empty or has fewer pools than expected
- Includes detailed pagination metrics in collection results

### 3. Configuration (`config.yaml`)

Added pagination settings at both global and network-specific levels:

```yaml
new_pools:
  # Global pagination settings
  max_pages: 10                   # Maximum pages to fetch (1-10 for free tier)
  page_delay: 1.0                 # Delay between page requests in seconds
  
  networks:
    solana:
      enabled: true
      max_pages: 10               # Network-specific override
      page_delay: 1.0             # Network-specific override
```

### 4. Configuration Models (`gecko_terminal_collector/config/models.py`)

Added pagination fields to config classes:

```python
@dataclass
class NewPoolsConfig:
    max_pages: int = 10          # Global default
    page_delay: float = 1.0      # Global default

@dataclass
class NetworkConfig:
    max_pages: Optional[int] = None      # Network-specific override
    page_delay: Optional[float] = None   # Network-specific override
```

## Benefits

1. **Better Coverage**: Capture up to 10x more pools per collection cycle
2. **Reduced Gaps**: Minimize missing pools during high-activity periods
3. **Historical Completeness**: More comprehensive data for signal analysis
4. **Better Signal Detection**: More pools = more opportunities to detect strong signals
5. **Configurable**: Adjust pages and delays per network based on activity levels

## Configuration Options

### Global Settings

Set defaults for all networks:

```yaml
new_pools:
  max_pages: 10        # 1-10 for free tier
  page_delay: 1.0      # Seconds between requests
```

### Network-Specific Settings

Override global settings per network:

```yaml
new_pools:
  networks:
    solana:
      max_pages: 10    # High activity network - fetch all pages
      page_delay: 1.0  # Standard delay
    ethereum:
      max_pages: 5     # Lower activity - fewer pages needed
      page_delay: 1.5  # Longer delay for safety
```

### Recommended Settings

**High Activity Networks (Solana, BSC)**:
- `max_pages: 10` - Fetch all available pages
- `page_delay: 1.0` - Standard delay

**Medium Activity Networks (Ethereum, Polygon)**:
- `max_pages: 5-7` - Moderate page count
- `page_delay: 1.0-1.5` - Standard to cautious delay

**Low Activity Networks**:
- `max_pages: 3-5` - Fewer pages needed
- `page_delay: 1.5-2.0` - Longer delay to be safe

## Rate Limiting Considerations

### API Limits
- Free tier: 30 calls/minute
- Each page = 1 API call
- 10 pages with 1s delay = ~15 seconds per collection

### Collection Frequency
With `interval: "15s"` and `max_pages: 10`:
- 4 collections/minute × 10 pages = 40 calls/minute (EXCEEDS LIMIT)

**Recommended**: Adjust interval when using multiple pages:
- `max_pages: 10` → `interval: "30s"` (2 collections/min × 10 = 20 calls/min)
- `max_pages: 5` → `interval: "20s"` (3 collections/min × 5 = 15 calls/min)
- `max_pages: 3` → `interval: "15s"` (4 collections/min × 3 = 12 calls/min)

## Monitoring

### Collection Metadata

Each collection now includes pagination metrics:

```python
metadata = {
    'network': 'solana',
    'pools_created': 45,
    'history_records': 180,
    'api_pools_received': 180,
    'pages_fetched': 10,              # NEW: Pages actually fetched
    'max_pages_configured': 10,       # NEW: Max pages setting
    'unique_pools_collected': 180,    # NEW: Unique pools after dedup
    'duplicates_filtered': 0          # NEW: Duplicates removed
}
```

### Log Messages

Look for these log messages:

```
INFO - Pagination enabled: fetching up to 10 pages with 1.0s delay
INFO - Fetching page 1/10 for network: solana
INFO - Page 1: Received 20 pools, 20 new (after deduplication)
INFO - Page 2: Received 18 pools, 18 new (after deduplication)
...
INFO - Pagination complete: collected 180 unique pools across 10 pages
```

## Testing

### Test Script

Run the included test script to verify pagination:

```bash
python test_pagination.py
```

This will:
- Fetch the first 3 pages of Solana new pools
- Show pool counts per page
- Display sample pool IDs
- Report deduplication statistics

### Manual Testing

1. **Enable pagination** in `config.yaml`:
   ```yaml
   new_pools:
     max_pages: 3
     page_delay: 1.5
   ```

2. **Run collector**:
   ```bash
   python -m gecko_terminal_collector.main
   ```

3. **Check logs** for pagination messages

4. **Verify database** has more records than before

## Troubleshooting

### Issue: Rate Limit Errors

**Symptoms**: 429 errors, "too many requests"

**Solutions**:
- Increase `page_delay` (try 1.5-2.0 seconds)
- Reduce `max_pages` (try 5 instead of 10)
- Increase collection `interval` (try "30s" instead of "15s")

### Issue: Duplicate Pools

**Symptoms**: Same pool appearing multiple times in database

**Solutions**:
- Deduplication is automatic in the collector
- Check database constraints on `pool_id` in `new_pools_history` table
- Verify `seen_pool_ids` logic in collector

### Issue: Empty Pages

**Symptoms**: Pagination stops early, fewer pools than expected

**Solutions**:
- This is normal - API may not have 10 full pages
- Collector automatically stops when pages are empty
- Check network activity - low activity = fewer pages

### Issue: Slow Collection / Timeouts

**Symptoms**: 
- Collection takes too long
- "maximum number of running instances reached" warning
- API timeouts on later pages

**Solutions**:
- **Increase interval**: If collection takes 15s, use 45s+ interval
- **Reduce `max_pages`**: Try 5 instead of 10 (still 5x improvement!)
- **Increase `page_delay`**: Try 1.5-2.0 seconds for more stability
- **Check timing**: Collection time = (max_pages × page_delay) + API time

**Example Fix**:
```yaml
# Before (causes overlapping collections)
max_pages: 10
page_delay: 1.0
interval: "30s"  # ❌ Too short!

# After (allows completion)
max_pages: 5
page_delay: 1.5
interval: "45s"  # ✅ Enough time
```

## Performance Impact

### Before Pagination
- 1 API call per collection
- ~20 pools per collection
- Potential gaps during high activity

### After Pagination (10 pages)
- 10 API calls per collection
- ~150-200 pools per collection
- Better coverage, fewer gaps
- ~15 seconds per collection (with 1s delay)

### Memory Usage
- Minimal increase (pools accumulated in list)
- ~1-2 MB for 200 pools with full data

### Database Load
- 10x more records per collection
- Ensure database can handle increased write volume
- Consider batch inserts if performance issues

## Future Enhancements

Potential improvements:
1. **Adaptive pagination**: Adjust pages based on pool count
2. **Parallel page fetching**: Fetch multiple pages concurrently
3. **Smart caching**: Cache recent pools to reduce duplicates
4. **Page size detection**: Dynamically determine optimal page count
5. **Metrics dashboard**: Visualize pagination effectiveness

## API Reference

### GeckoTerminal API Endpoint

```
GET https://api.geckoterminal.com/api/v2/networks/{network}/new_pools?page={page}
```

**Parameters**:
- `network`: Network identifier (e.g., "solana")
- `page`: Page number (1-10 for free tier)
- `include`: Related data to include (e.g., "base_token,quote_token,dex")

**Response**: JSON with pool data

**Rate Limits**:
- Free tier: 30 calls/minute
- No daily limit specified

## Summary

Pagination support significantly improves new pools data collection by:
- Capturing more pools per collection cycle
- Reducing data gaps during high activity
- Providing better historical data for analysis
- Maintaining configurability and flexibility

The implementation is backward compatible, configurable, and includes comprehensive monitoring and error handling.
