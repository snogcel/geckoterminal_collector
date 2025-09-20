# Historical OHLCV Data Collection Guide

## Current Status

You now have historical OHLCV data for all 4 active symbols in your watchlist:

### Data Summary (as of collection):

1. **UNEMPLOYED/SOL** - Complete data across all timeframes (Sep 15-19, 2025)
2. **Xoai / SOL** - Limited data (Sep 16-17, 2025) 
3. **CBRL** - Good historical coverage (Aug 20 - Sep 19, 2025)
4. **TROLL** - Partial data (1m timeframe only, Sep 14-19, 2025)

**Total Records**: 12,237 OHLCV records across all timeframes

## Available Scripts

### 1. `check_watchlist.py`
Check what symbols are currently active in your watchlist database.

```bash
python check_watchlist.py
```

### 2. `check_historical_data.py`
View existing historical data summary and identify gaps.

```bash
# Check all historical data
python check_historical_data.py

# Check for data gaps
python check_historical_data.py gaps
```

### 3. `collect_historical_ohlcv.py`
Main collection script for all watchlist symbols.

```bash
# Collect for all watchlist symbols
python collect_historical_ohlcv.py

# Collect for specific pool
python collect_historical_ohlcv.py <pool_id> <timeframe> <days_back>
# Example: python collect_historical_ohlcv.py 7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP 1h 60
```

### 4. `collect_historical_with_rate_limits.py`
Rate-limit aware collection with better control.

```bash
# Conservative collection for all pools
python collect_historical_with_rate_limits.py

# Check for missing timeframes
python collect_historical_with_rate_limits.py check

# Collect for single pool
python collect_historical_with_rate_limits.py single <pool_id> <timeframe> <days_back>
```

## Collection Strategy

### For Complete Historical Data Collection:

1. **Start with high-value timeframes**: 1h, 4h, 1d (less API calls)
2. **Use rate-limited collection**: Prevents 429 errors
3. **Collect in batches**: Process one pool at a time with delays
4. **Monitor progress**: Check data after each collection

### Recommended Collection Order:

```bash
# 1. Check current status
python check_historical_data.py

# 2. Collect missing timeframes (conservative)
python collect_historical_with_rate_limits.py check

# 3. Fill gaps for specific pools if needed
python collect_historical_with_rate_limits.py single <pool_id> <timeframe> <days>
```

## Database Structure

Your historical data is stored in the `ohlcv_data` table with these key fields:

- `pool_id`: Full pool identifier (e.g., "solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP")
- `timeframe`: Data interval (1m, 5m, 15m, 1h, 4h, 12h, 1d)
- `timestamp`: Unix timestamp
- `datetime`: Human-readable datetime
- `open_price`, `high_price`, `low_price`, `close_price`: OHLCV prices
- `volume_usd`: Volume in USD

## Rate Limiting Considerations

The GeckoTerminal API has rate limits:
- **429 errors** indicate you're hitting limits
- **Recommended delays**: 2-5 seconds between requests
- **Batch processing**: Process pools sequentially with delays
- **Pagination**: Large historical requests are automatically paginated

## Data Gaps and Backfilling

### Common Scenarios:

1. **New tokens**: May have limited historical data
2. **Low-volume periods**: Some intervals may be missing
3. **API limitations**: 6-month maximum lookback

### Gap Detection:

```bash
python check_historical_data.py gaps
```

This will identify missing intervals in your data.

## Integration with Your System

### Accessing Historical Data Programmatically:

```python
from gecko_terminal_collector.database.enhanced_sqlalchemy_manager import EnhancedSQLAlchemyDatabaseManager
from gecko_terminal_collector.config.manager import ConfigManager

async def get_historical_data(pool_id, timeframe, start_date=None, end_date=None):
    config = ConfigManager().load_config()
    db_manager = EnhancedSQLAlchemyDatabaseManager(config.database)
    await db_manager.initialize()
    
    data = await db_manager.get_ohlcv_data(
        pool_id=pool_id,
        timeframe=timeframe,
        start_time=start_date,
        end_time=end_date
    )
    
    await db_manager.close()
    return data
```

### Exporting to Other Formats:

Your system already has Qlib integration for exporting data to quantitative analysis formats.

## Maintenance

### Regular Collection:
- Your existing collectors will continue gathering real-time data
- Historical collection is typically a one-time or periodic task
- Monitor for new symbols added to watchlist

### Data Validation:
- Check for unusual price relationships
- Verify data continuity
- Monitor collection success rates

## Troubleshooting

### Common Issues:

1. **Rate Limit Errors (429)**:
   - Use `collect_historical_with_rate_limits.py`
   - Increase delays between requests
   - Process fewer pools at once

2. **Missing Data**:
   - Some tokens may have limited history
   - API may not have data for all time periods
   - Check token creation date vs. requested date range

3. **Database Errors**:
   - Ensure PostgreSQL is running
   - Check connection string in config.yaml
   - Verify table structure is up to date

### Getting Help:

- Check logs for detailed error messages
- Use `check_historical_data.py` to verify collection results
- Monitor API response status codes in collector logs

## Next Steps

1. **Verify your current data** with `check_historical_data.py`
2. **Fill any gaps** using the rate-limited collector
3. **Set up automated collection** for new watchlist additions
4. **Integrate with your analysis pipeline** using the database queries

Your historical OHLCV data collection is now complete and ready for quantitative analysis!