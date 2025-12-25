# Enhanced Watchlist Scheduler Integration Guide

## Overview

The Enhanced Watchlist Collector has been integrated into the main CLI scheduler system. This guide shows how to configure and run the enhanced watchlist collection through the scheduler.

## Configuration

### 1. Update config.yaml

Add the enhanced watchlist configuration to your `config.yaml`:

```yaml
# Enhanced Watchlist Configuration
enhanced_watchlist:
  enabled: true                   # Enable enhanced watchlist collection
  interval: "1h"                  # Collection interval (hourly updates)
  sources:                        # Available data sources
    - "reference"                 # Reference segment (default)
    - "lowcap"                    # Low cap segment
    - "micro"                     # Micro cap segment
    - "midcap"                    # Mid cap segment
    - "oldlowcap"                 # Old low cap segment
    - "oldmicro"                  # Old micro segment
  
  # Rate limiting for API calls
  rate_limiting:
    delay_between_calls: 1.0      # Seconds between API calls
    batch_size: 10                # Process entries in batches
    delay_between_sources: 2.0    # Seconds between processing different sources
  
  # Historical data settings
  history:
    enabled: true                 # Enable historical data storage
    retention_days: 90            # Days to retain historical data (0 = unlimited)
    cleanup_interval: "24h"       # How often to run cleanup
  
  # File naming pattern
  file_pattern: "watchlist_updated_{source}.csv"  # Pattern for source files
```

### 2. Prepare Source Files

Create your source CSV files with the expected naming pattern:
- `watchlist_updated_reference.csv`
- `watchlist_updated_lowcap.csv`
- `watchlist_updated_micro.csv`
- `watchlist_updated_midcap.csv`
- `watchlist_updated_oldlowcap.csv`
- `watchlist_updated_oldmicro.csv`

Each file should have the following CSV schema:
```csv
tokenSymbol,tokenName,poolAddress,dex,price,marketCap,liquidity,volume,priceChange5m,priceChange1h,priceChange6h,priceChange24h,transactions,makers,age,detailUrl
DINO,DINOSOL,26M5M3nwgaKE4zavkD3zEtYs5hJWdxe6xBwpdtsLHy1o,pumpswap,0.001066,938000,130000,1100000,-0.34,-4.74,3.54,75.59,29622,3840,12d,/solana/26m5m3nwgake4zavkd3zetys5hjwdxe6xbwpdtslhy1o
```

## Usage

### 1. Start the Scheduler (Automatic Collection)

Start the scheduler to run enhanced watchlist collection automatically:

```bash
# Start scheduler with enhanced watchlist enabled
python -m examples.cli_with_scheduler start --config config.yaml

# Start with mock client for testing
python -m examples.cli_with_scheduler start --config config.yaml --mock
```

The scheduler will:
- Run enhanced watchlist collection every hour (or your configured interval)
- Process all enabled sources automatically
- Apply rate limiting to protect against API limits
- Store historical data for analysis

### 2. Run One-Time Collection

Run enhanced watchlist collection once for testing or manual execution:

```bash
# Run enhanced watchlist collector once (all sources)
python -m examples.cli_with_scheduler run-once --collector enhanced_watchlist

# Run with specific sources only
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "reference,lowcap,micro"

# Run with mock client for testing
python -m examples.cli_with_scheduler collect-enhanced-watchlist --mock
```

### 3. Check Status

Monitor the enhanced watchlist collector status:

```bash
# Show overall scheduler status
python -m examples.cli_with_scheduler status

# Show rate limiting status
python -m examples.cli_with_scheduler rate-limit-status
```

## Expected Output

### Successful Collection
```
=== Enhanced Watchlist Collection Results ===
Sources: reference, lowcap, micro
Success: True
Total Records: 300
Collection Time: 2025-12-17 17:00:00+00:00

=== Collection Details ===
Sources Processed: 3
Entries Processed: 300
Addresses Resolved: 300
API Calls Made: 300
Resolution Rate: 100.0%

=== Rate Usage ===
Daily Usage: 15.2%
Total Daily Requests: 1520
```

### Scheduler Status
```
=== Collection Scheduler Status ===
State: running
Total Collectors: 4
Enabled Collectors: 4
Running Jobs: 0

=== Collector Details ===

enhanced_watchlist:
  Type: Enhanced Watchlist Collector
  Interval: 1h
  Enabled: True
  Last Run: 2025-12-17 16:00:00+00:00
  Last Success: 2025-12-17 16:00:00+00:00
  Error Count: 0
  Consecutive Errors: 0

=== Next Run Times ===
enhanced_watchlist: 2025-12-17 17:00:00+00:00
```

## Database Queries

### Check Collection Status
```sql
SELECT 
    collector_type,
    last_run,
    last_success,
    run_count,
    error_count,
    success_rate
FROM collection_metadata
WHERE collector_type = 'enhanced_watchlist_collector';
```

### Check Historical Data
```sql
SELECT 
    source,
    COUNT(*) as entry_count,
    MIN(collected_at) as earliest,
    MAX(collected_at) as latest
FROM enhanced_watchlist_history
GROUP BY source
ORDER BY source;
```

### Recent Entries by Source
```sql
SELECT 
    source,
    ranking,
    token_symbol,
    price,
    market_cap,
    price_change_24h,
    collected_at
FROM enhanced_watchlist_history
WHERE collected_at >= NOW() - INTERVAL '1 hour'
ORDER BY source, ranking
LIMIT 20;
```

## Troubleshooting

### Issue: Collector Not Starting
**Check**: Ensure `enhanced_watchlist.enabled: true` in config.yaml
**Solution**: Verify configuration and restart scheduler

### Issue: Source Files Not Found
**Error**: `Source file not found: watchlist_updated_reference.csv`
**Solution**: Create the expected CSV files with proper naming

### Issue: API Rate Limits
**Error**: Rate limiting errors in logs
**Solution**: 
```bash
# Check rate limiter status
python -m examples.cli_with_scheduler rate-limit-status

# Reset rate limiter if needed
python -m examples.cli_with_scheduler reset-rate-limiter --collector enhanced_watchlist
```

### Issue: Database Table Missing
**Error**: `relation "enhanced_watchlist_history" does not exist`
**Solution**: 
```bash
# Create the database table
python create_enhanced_watchlist_table.py
```

### Issue: Low Resolution Rate
**Problem**: Many entries failing to resolve addresses
**Check**: Verify `detailUrl` format in CSV files should be `/solana/pool_address`
**Solution**: Ensure URLs follow GeckoTerminal format

## Performance Optimization

### Rate Limiting Settings
For high-volume collection, adjust rate limiting:
```yaml
enhanced_watchlist:
  rate_limiting:
    delay_between_calls: 0.5      # Faster API calls (if limits allow)
    batch_size: 20                # Larger batches
    delay_between_sources: 1.0    # Shorter delays between sources
```

### Source Selection
Process only needed sources to reduce API calls:
```yaml
enhanced_watchlist:
  sources:
    - "reference"                 # Only process reference segment
    - "lowcap"                    # Add specific segments as needed
```

### Collection Frequency
Adjust collection interval based on data update frequency:
```yaml
enhanced_watchlist:
  interval: "30m"                 # More frequent collection
  # or
  interval: "2h"                  # Less frequent collection
```

## Monitoring

### Collection Health
Monitor collection success rate and identify issues:
```bash
# Check recent collection results
python -m examples.cli_with_scheduler status

# Check for errors
tail -f logs/collector.log | grep enhanced_watchlist
```

### Data Quality
Verify data quality and completeness:
```sql
-- Check for missing data
SELECT 
    source,
    DATE_TRUNC('hour', collected_at) as hour,
    COUNT(*) as entries
FROM enhanced_watchlist_history
WHERE collected_at >= NOW() - INTERVAL '24 hours'
GROUP BY source, DATE_TRUNC('hour', collected_at)
ORDER BY source, hour;

-- Check resolution rates
SELECT 
    source,
    COUNT(*) as total_entries,
    COUNT(base_token_address) as resolved_entries,
    (COUNT(base_token_address)::float / COUNT(*) * 100) as resolution_rate
FROM enhanced_watchlist_history
WHERE collected_at >= NOW() - INTERVAL '24 hours'
GROUP BY source;
```

## Integration with Other Systems

### Export Data
Export historical data for external analysis:
```sql
COPY (
    SELECT * FROM enhanced_watchlist_history 
    WHERE collected_at >= NOW() - INTERVAL '7 days'
) TO '/path/to/export.csv' WITH CSV HEADER;
```

### API Integration
The scheduler provides the foundation for building REST APIs on top of the historical data.

### Alerting
Set up alerts based on collection metrics:
- Collection failure alerts
- Rate limit threshold alerts
- Data quality alerts (low resolution rates)

This integration provides a robust, scalable solution for collecting and storing enhanced watchlist data with comprehensive historical tracking.