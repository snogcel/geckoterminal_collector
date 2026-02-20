# Rate Limiting Fix for OHLCV Collector

## Problem

The OHLCV collector was hitting 429 (Too Many Requests) errors despite having rate limiting configuration in `config.yaml`. The requests were happening too quickly (1-3 seconds apart) even though `rate_limit_delay: 5.0` was configured.

### Observed Behavior
```
13:24:50 - Request 1 (200 OK)
13:24:51 - Request 2 (200 OK) - 1 second later
13:24:54 - Request 3 (200 OK) - 3 seconds later  
13:24:57 - Request 4 (429 Too Many Requests) - 3 seconds later
```

## Root Cause

The `EnhancedRateLimiter` was only enforcing a **per-minute request limit** (e.g., 30 requests/minute) but had **no minimum delay between individual requests**. This meant:

1. Requests could fire as fast as possible until hitting the per-minute limit
2. The `rate_limit_delay` config value in `config.yaml` was being ignored
3. GeckoTerminal's API has stricter rate limiting than just requests/minute

The rate limiter would allow rapid-fire requests like:
- Request 1 at 0s
- Request 2 at 1s  
- Request 3 at 2s
- Request 4 at 3s
- ... (up to 30 requests in the first 30 seconds)

This violated GeckoTerminal's actual rate limits, which likely require spacing between requests.

## Solution

Added a **minimum request interval** feature to `EnhancedRateLimiter`:

### 1. Added `min_request_interval` Parameter

```python
def __init__(
    self,
    requests_per_minute: int = 60,
    daily_limit: int = 10000,
    min_request_interval: float = 0.0,  # NEW: Minimum seconds between requests
    ...
):
```

### 2. Track Last Request Time

```python
self.last_request_time: Optional[float] = None
```

### 3. Enforce Minimum Interval in `_wait_for_rate_limit()`

```python
async def _wait_for_rate_limit(self) -> None:
    """Wait if necessary to respect per-minute rate limits and minimum request interval."""
    now = time.time()
    
    # Enforce minimum request interval if configured
    if self.min_request_interval > 0 and self.last_request_time is not None:
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            logger.debug(f"Enforcing minimum request interval, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
            now = time.time()
    
    # ... rest of per-minute limit logic
```

### 4. Update Base Collector to Use Config Values

Modified `BaseDataCollector.__init__()` to read rate limiting config and pass it to the rate limiter:

```python
# Extract rate limiting config
rate_limit_config = getattr(config, 'rate_limiting', None)
api_config = getattr(config, 'api', None)

# Get rate limit parameters from config
requests_per_minute = 30  # Default to 30 (GeckoTerminal free tier)
min_request_interval = 2.0  # Default to 2 seconds between requests

if rate_limit_config:
    if hasattr(rate_limit_config, 'requests_per_minute'):
        requests_per_minute = rate_limit_config.requests_per_minute

if api_config and hasattr(api_config, 'rate_limit_delay'):
    min_request_interval = api_config.rate_limit_delay

self.rate_limiter = EnhancedRateLimiter(
    requests_per_minute=requests_per_minute,
    min_request_interval=min_request_interval
)
```

## Configuration

The fix now respects these config values from `config.yaml`:

```yaml
# API Configuration
api:
  rate_limit_delay: 5.0  # NOW ENFORCED: Minimum 5 seconds between requests

# Rate Limiting Configuration  
rate_limiting:
  requests_per_minute: 30  # Maximum 30 requests per minute
```

## Expected Behavior After Fix

With `rate_limit_delay: 5.0` configured:

```
13:24:50 - Request 1 (200 OK)
13:24:55 - Request 2 (200 OK) - 5 seconds later (enforced minimum)
13:25:00 - Request 3 (200 OK) - 5 seconds later (enforced minimum)
13:25:05 - Request 4 (200 OK) - 5 seconds later (enforced minimum)
```

This ensures:
- ✓ Minimum 5 seconds between requests (configurable)
- ✓ Maximum 30 requests per minute (configurable)
- ✓ No 429 errors from rate limiting
- ✓ Respects GeckoTerminal API limits

## Changes Made

### gecko_terminal_collector/utils/enhanced_rate_limiter.py
1. Added `min_request_interval` parameter to `__init__()`
2. Added `last_request_time` tracking
3. Updated `_wait_for_rate_limit()` to enforce minimum interval
4. Updated `acquire()` to track last request time

### gecko_terminal_collector/collectors/base.py
1. Updated `__init__()` to read rate limiting config
2. Pass `min_request_interval` from `api.rate_limit_delay` config
3. Pass `requests_per_minute` from `rate_limiting.requests_per_minute` config

## Testing

To test the fix:

1. Set `rate_limit_delay: 5.0` in `config.yaml`
2. Run OHLCV collection
3. Observe logs - requests should be spaced 5+ seconds apart
4. No 429 errors should occur

To adjust rate limiting:
- Increase `rate_limit_delay` for slower, safer requests (e.g., 10.0 for 10 seconds)
- Decrease for faster collection (minimum 2.0 recommended for free tier)
- Adjust `requests_per_minute` if you have a paid plan with higher limits

## Impact

- OHLCV collection will be slower but more reliable
- No more 429 rate limit errors
- Configurable via `config.yaml` without code changes
- Works for all collectors that use `BaseDataCollector.make_api_request()`
