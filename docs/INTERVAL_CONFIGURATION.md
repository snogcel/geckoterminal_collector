# Interval Configuration Guide

## Supported Interval Formats

The GeckoTerminal Data Collector supports flexible interval configurations using time units:

### Time Units

- `s` - Seconds
- `m` - Minutes  
- `h` - Hours
- `d` - Days

### Examples

```yaml
# Seconds (for high-frequency collection)
interval: "15s"   # Every 15 seconds (4 calls/minute)
interval: "30s"   # Every 30 seconds (2 calls/minute)
interval: "45s"   # Every 45 seconds (1.33 calls/minute)

# Minutes (standard frequency)
interval: "1m"    # Every 1 minute (1 call/minute)
interval: "5m"    # Every 5 minutes
interval: "15m"   # Every 15 minutes
interval: "30m"   # Every 30 minutes

# Hours (low frequency)
interval: "1h"    # Every 1 hour
interval: "4h"    # Every 4 hours
interval: "12h"   # Every 12 hours

# Days (very low frequency)
interval: "1d"    # Once per day
```

## API Rate Limits

**GeckoTerminal Public API Limit:** 30 calls per minute

### Recommended Intervals for New Pools Collection

To stay well under the rate limit while maximizing data freshness:

| Interval | Calls/Minute | % of Limit | Use Case |
|----------|--------------|------------|----------|
| `15s` | 4 | 13% | High-frequency trading signals |
| `20s` | 3 | 10% | Balanced frequency |
| `30s` | 2 | 7% | Conservative approach |
| `1m` | 1 | 3% | Standard monitoring |
| `2m` | 0.5 | 2% | Low-frequency monitoring |

### Configuration Locations

1. **New Pools Collection** (per network):
   ```yaml
   new_pools:
     networks:
       solana:
         interval: "15s"  # Adjust as needed
   ```

2. **General Collection Intervals**:
   ```yaml
   intervals:
     top_pools_monitoring: "5m"
     ohlcv_collection: "1h"
     trade_collection: "30m"
     watchlist_check: "1h"
   ```

## Best Practices

1. **Start Conservative**: Begin with longer intervals (30s-1m) and decrease if needed
2. **Monitor Rate Limits**: Watch for rate limit errors in logs
3. **Consider Your Use Case**: 
   - Trading signals: 15-30s
   - Data collection: 1-5m
   - Historical analysis: 15m-1h
4. **Multiple Networks**: If collecting from multiple networks, ensure total calls/minute < 30

## Example Configurations

### High-Frequency Trading Setup
```yaml
new_pools:
  networks:
    solana:
      interval: "15s"  # 4 calls/min
      signal_analysis: true
```

### Balanced Monitoring Setup
```yaml
new_pools:
  networks:
    solana:
      interval: "30s"  # 2 calls/min
    ethereum:
      interval: "30s"  # 2 calls/min
    # Total: 4 calls/min (13% of limit)
```

### Conservative Data Collection
```yaml
new_pools:
  networks:
    solana:
      interval: "2m"   # 0.5 calls/min
      signal_analysis: true
```
