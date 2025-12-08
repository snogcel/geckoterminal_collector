# Trade Collection Batch Configuration

## Changes Made

Removed the hardcoded 10-pool batch limit and made it fully configurable.

## New Configuration

### config.yaml
```yaml
# Collection Intervals
intervals:
  trade_collection: "3m"  # Reduced from 5m for faster rotation

# Trade Collection Configuration
trade_collection:
  max_pools_per_batch: 20        # Configurable batch size (was hardcoded at 10)
  rotation_window_minutes: 30    # Time window for fair rotation tracking

# Thresholds
thresholds:
  high_volume_threshold_usd: 10000.0  # For pool prioritization
```

## Performance for 78 Pools

With the new settings:
- **Batch size**: 20 pools per collection
- **Collection interval**: 3 minutes
- **Full cycle time**: ~12 minutes (4 batches × 3 min)
- **API usage**: 20 calls per 3 min = 6.7 calls/min (22% of 30/min limit)

### Comparison

| Setting | Old | New |
|---------|-----|-----|
| Batch size | 10 (hardcoded) | 20 (configurable) |
| Interval | 5 minutes | 3 minutes |
| Full cycle | ~40 minutes | ~12 minutes |
| API usage | 2 calls/min | 6.7 calls/min |
| Data freshness | Pool updated every 40 min | Pool updated every 12 min |

## Tuning Recommendations

### Conservative (Current)
- `max_pools_per_batch: 20`
- `trade_collection: "3m"`
- API usage: 22% of limit
- Full cycle: 12 minutes

### Balanced
- `max_pools_per_batch: 26`
- `trade_collection: "3m"`
- API usage: 29% of limit
- Full cycle: 9 minutes

### Aggressive
- `max_pools_per_batch: 39`
- `trade_collection: "2m"`
- API usage: 33% of limit
- Full cycle: 4 minutes

### Maximum (Use with caution)
- `max_pools_per_batch: 78`
- `trade_collection: "2m"`
- API usage: 65% of limit
- Full cycle: 2 minutes (all pools every cycle)

## Environment Variable Override

You can override the batch size without editing config:
```bash
export GECKO_TRADE_MAX_POOLS_PER_BATCH=30
export GECKO_TRADE_ROTATION_WINDOW_MINUTES=20
```

## Fair Rotation Logic

The collector still implements intelligent prioritization:
- High-volume pools (>$10k USD) get priority
- Pools are rotated based on last collection time
- Oldest-collected pools are prioritized for fairness
- If approaching API limits, batch size auto-reduces

## Benefits

1. **Flexibility**: Adjust batch size without code changes
2. **Scalability**: Easily handle growing watchlists
3. **Efficiency**: Better API utilization (was using only 6.7%, now 22%)
4. **Freshness**: 3x faster data updates (12 min vs 40 min cycles)
5. **Safety**: Still well under rate limits with headroom for retries
