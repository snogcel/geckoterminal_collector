# Viewing Collector Logs - Complete Guide

## Quick Answer

To see `logger.info()` outputs when running the enhanced watchlist collector:

```bash
# Method 1: View in console (real-time)
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"

# Method 2: Save to file
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro" 2>&1 | tee collection.log

# Method 3: View saved logs
grep "Skipping unresolved" collection.log
```

---

## Understanding the Current API-First Approach

Looking at your `database_address_resolver.py`, the code is now **API-first**:

```python
async def get_pool_data_by_address(self, address: str) -> Optional[Dict[str, Any]]:
    """Get complete pool data for an address via API."""
    
    # Calls GeckoTerminal API directly
    api_payload = await self._fetch_pool_data_from_api(address)
    
    if not api_payload:
        # API call failed - entry will be skipped
        return None
```

This means:
- ✅ No database cache needed
- ✅ Always gets fresh data
- ❌ Makes API calls for every entry
- ❌ Subject to rate limiting
- ❌ Slower than database lookups

---

## Viewing Logs - Multiple Methods

### Method 1: Console Output (Simplest)

Just run the command and watch the output:

```bash
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"
```

You'll see output like:
```
2026-07-24 14:30:00 - INFO - Starting enhanced watchlist collection...
2026-07-24 14:30:01 - INFO - Skipping unresolved pool data for abc123; continuing with next row
2026-07-24 14:30:02 - WARNING - Failed to fetch pool data from API for abc123 after 10 attempts
2026-07-24 14:30:03 - INFO - Processed 10 entries...
```

### Method 2: Save to File While Viewing

Use `tee` to both see output AND save it:

```bash
# Save and view simultaneously
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro" 2>&1 | tee collection_$(date +%Y%m%d_%H%M%S).log
```

### Method 3: Redirect to File Only

Save all output to a file:

```bash
# Save to file (includes stderr)
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro" > collection.log 2>&1

# Then view it
cat collection.log

# Or search for specific messages
grep "Skipping" collection.log
grep "Failed to fetch" collection.log
```

### Method 4: Increase Logging Detail

Add debug logging to see MORE information:

**Option A**: Environment variable
```bash
export LOG_LEVEL=DEBUG
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"
```

**Option B**: Modify the collector temporarily

In `enhanced_watchlist_collector.py`, change the logging level:

```python
# At the top of the file
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # ← Add this line
```

### Method 5: Filter Specific Messages

```bash
# Run and filter for "Skipping" messages only
python -m examples.cli_with_scheduler collect-enhanced-watchlist 2>&1 | grep "Skipping"

# Count how many were skipped
python -m examples.cli_with_scheduler collect-enhanced-watchlist 2>&1 | grep -c "Skipping"

# Show last 20 failures
python -m examples.cli_with_scheduler collect-enhanced-watchlist 2>&1 | grep "Skipping" | tail -20
```

---

## Understanding API Failures

When you see:
```
INFO - Skipping unresolved pool data for abc123; continuing with next row
```

This means `_fetch_pool_data_from_api()` returned `None`. Let's see WHY:

### Common API Failure Reasons

1. **Rate Limiting (429)**
   ```
   WARNING - 429 rate limit - waiting 30s before retry 3/10
   ```
   - You hit GeckoTerminal rate limits
   - System will retry with backoff
   - If all retries fail → returns None → entry skipped

2. **Pool Not Found (404)**
   ```
   WARNING - Failed to fetch pool data from API for abc123 after 10 attempts
   ```
   - Pool doesn't exist on GeckoTerminal
   - Invalid/old pool address
   - Token not tracked by GeckoTerminal

3. **Network Errors**
   ```
   WARNING - Transient API error for pool lookup abc123; retrying in 2s (attempt 1/10)
   ```
   - Temporary network issues
   - API timeouts
   - Connection problems

4. **Circuit Breaker Open**
   ```
   WARNING - Circuit breaker is open for abc123, waiting 10s...
   ```
   - Too many failures, protection kicked in
   - System pauses API calls temporarily

### Checking API Call Stats

Add this to your collector to see API statistics:

```python
# After collection completes
logger.info(f"API calls made: {self._api_calls_made}")
logger.info(f"Entries resolved: {self._addresses_resolved}")
logger.info(f"Success rate: {self._addresses_resolved / self._entries_processed * 100:.1f}%")
```

---

## Diagnostic Script for API Failures

Let me create a script that shows exactly what's happening with each entry:

```bash
# This will show detailed API call results
python diagnose_api_failures.py enhanced_watchlist.csv
```

The script will:
- Try to fetch each pool from API
- Show which ones succeed
- Show which ones fail and why
- Report rate limiting issues
- Give recommendations

---

## Checking for Specific Address

If you want to test a specific address:

```bash
# Create a test script
cat > test_single_address.py << 'EOF'
import asyncio
import logging
from gecko_terminal_collector.utils.database_address_resolver import AddressResolver

logging.basicConfig(level=logging.DEBUG)

async def test_address(address):
    resolver = AddressResolver(None)  # No DB needed for API-only
    await resolver._ensure_rate_limiter()
    
    print(f"\nTesting address: {address}")
    result = await resolver._fetch_pool_data_from_api(address)
    
    if result:
        print(f"✅ SUCCESS: Found pool data")
        print(f"   Pool: {result['data']['attributes'].get('name')}")
    else:
        print(f"❌ FAILED: Could not fetch pool data")

asyncio.run(test_address("YOUR_ADDRESS_HERE"))
EOF

python test_single_address.py
```

---

## Monitoring in Production

### Option 1: Log to File with Rotation

Set up proper logging in production:

```python
# In your collector or CLI
import logging
from logging.handlers import RotatingFileHandler

# Setup file logging with rotation
handler = RotatingFileHandler(
    '/var/log/watchlist_collector.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logger = logging.getLogger('gecko_terminal_collector')
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

### Option 2: Systemd Journal

If running as a service:

```bash
# View logs
journalctl -u watchlist-collector.service -f

# Filter for specific messages
journalctl -u watchlist-collector.service | grep "Skipping"

# Show only errors
journalctl -u watchlist-collector.service -p err
```

### Option 3: Cron with Log File

```bash
# In crontab
0 * * * * cd /path/to/project && python -m examples.cli_with_scheduler collect-enhanced-watchlist >> /var/log/watchlist_cron.log 2>&1

# View logs
tail -f /var/log/watchlist_cron.log
```

---

## Rate Limiting Detection

Look for these patterns in logs:

```bash
# Check for rate limiting
grep "429" collection.log
grep "rate limit" collection.log
grep "Circuit breaker" collection.log

# Count rate limit hits
grep -c "429" collection.log

# See backoff times
grep "waiting.*before retry" collection.log
```

---

## Quick Health Check

Create a simple health check script:

```python
# health_check.py
import sys
import re

log_file = sys.argv[1] if len(sys.argv) > 1 else "collection.log"

with open(log_file) as f:
    content = f.read()
    
    total_processed = len(re.findall(r'Processed.*entry', content))
    skipped = len(re.findall(r'Skipping unresolved', content))
    rate_limits = len(re.findall(r'429|rate limit', content))
    api_errors = len(re.findall(r'Failed to fetch.*API', content))
    
    print(f"Health Check Results:")
    print(f"  Total processed: {total_processed}")
    print(f"  Skipped entries: {skipped}")
    print(f"  Rate limit hits: {rate_limits}")
    print(f"  API errors: {api_errors}")
    
    if skipped > total_processed * 0.5:
        print("\n⚠️  WARNING: More than 50% entries skipped!")
    if rate_limits > 0:
        print(f"\n⚠️  WARNING: {rate_limits} rate limit events detected")
```

Usage:
```bash
python -m examples.cli_with_scheduler collect-enhanced-watchlist > collection.log 2>&1
python health_check.py collection.log
```

---

## Summary

**To view logger.info outputs:**

1. **Simple**: Just run the command and watch console
   ```bash
   python -m examples.cli_with_scheduler collect-enhanced-watchlist
   ```

2. **Save for analysis**: Use tee or redirect
   ```bash
   python -m examples.cli_with_scheduler collect-enhanced-watchlist 2>&1 | tee log.txt
   ```

3. **Filter specific messages**: Use grep
   ```bash
   python -m examples.cli_with_scheduler collect-enhanced-watchlist 2>&1 | grep "Skipping"
   ```

4. **Debug mode**: Set LOG_LEVEL=DEBUG for more detail
   ```bash
   LOG_LEVEL=DEBUG python -m examples.cli_with_scheduler collect-enhanced-watchlist
   ```

**Current System (API-First):**
- Makes API call for every CSV entry
- Subject to rate limiting
- Failures logged as "Skipping unresolved pool data"
- Retries up to 10 times before giving up

**To diagnose specific failures:**
```bash
# Run diagnostics
python diagnose_api_failures.py enhanced_watchlist.csv
```
