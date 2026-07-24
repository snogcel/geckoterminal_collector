# Watchlist Active Status Synchronization Guide

## Overview

This guide explains how to synchronize the `is_active` field in the database watchlist table with the `watchlist_state.json` file. The synchronization is performed in bulk for efficiency and can handle large datasets.

## Components

### 1. `sync_watchlist_active_status.py`
Main synchronization script that:
- Reads the `watchlist_state.json` file
- Extracts active/inactive token addresses
- Performs bulk database update using the existing `bulk_update_watchlist_active_status` method
- Provides detailed logging and statistics

### 2. `sync_watchlist_status.bat`
Windows batch file for easy execution:
- Simple command-line interface
- Automatic error handling
- Default parameters with override options

### 3. `test_watchlist_sync.py`
Analysis and testing tool that:
- Analyzes the watchlist state file without modifying the database
- Shows statistics on active/inactive tokens
- Displays deactivation reasons
- Previews what changes would be made

## Usage

### Quick Start (Windows)

Simply double-click `sync_watchlist_status.bat` or run:
```cmd
sync_watchlist_status.bat
```

### Command Line Usage

#### Run synchronization with default paths:
```cmd
python sync_watchlist_active_status.py
```

#### Specify custom paths:
```cmd
python sync_watchlist_active_status.py "path/to/watchlist_state.json" "path/to/config.yaml"
```

#### Test/analyze before syncing:
```cmd
python test_watchlist_sync.py
```

#### Analyze custom JSON file:
```cmd
python test_watchlist_sync.py "path/to/watchlist_state.json"
```

## Watchlist State JSON Format

The script expects a JSON file with this structure:

```json
{
  "tokens": {
    "TOKEN_ADDRESS_1": {
      "first_seen": "2026-07-22T22:25:52.695757+00:00",
      "last_seen": "2026-07-22T23:15:37.931258+00:00",
      "active": false,
      "deactivation_reason": "absent_3_cycles",
      "deactivated_at": "2026-07-22T23:30:38.715115+00:00",
      "peak_score": 53,
      "prev_metrics": {
        "liquidity": 172600,
        "smart_degen_count": 6
      }
    },
    "TOKEN_ADDRESS_2": {
      "first_seen": "2026-07-23T20:40:31.557443+00:00",
      "active": true,
      "peak_score": 73,
      "prev_metrics": {
        "liquidity": 10853.4
      }
    }
  },
  "meta": {
    "total_cycles": 301,
    "last_run": "2026-07-23T23:20:44.302970+00:00"
  }
}
```

## How It Works

### Synchronization Process

1. **Load JSON File**
   - Reads the `watchlist_state.json` file
   - Validates the structure

2. **Extract Status**
   - Iterates through all tokens
   - Separates into `active` and `inactive` lists based on the `active` field

3. **Bulk Update**
   - Uses SQLAlchemy's bulk update for efficiency
   - Updates all active tokens: `SET is_active = TRUE`
   - Updates all inactive tokens: `SET is_active = FALSE`
   - Updates the `updated_at` timestamp

4. **Report Results**
   - Number of tokens set to active
   - Number of tokens set to inactive
   - Number of token addresses not found in database

### Database Function

The synchronization uses the existing `bulk_update_watchlist_active_status` method in `SQLAlchemyDatabaseManager`:

```python
async def bulk_update_watchlist_active_status(self, token_addresses: dict) -> dict:
    """
    Bulk update active status for watchlist entries based on token addresses.
    
    Args:
        token_addresses: Dict with keys 'active' and 'inactive', each containing 
                        list of token addresses
    
    Returns:
        Dict with counts of updated entries
    """
```

## Example Output

### Synchronization Output
```
🚀 Starting watchlist active status synchronization...
✅ Loaded watchlist state from watchlist_state.json
📊 Total tokens in state file: 73
📊 Status breakdown:
   ✅ Active tokens: 0
   ❌ Inactive tokens: 73
✅ Database connection established
🔄 Updating watchlist active status in database...
🔄 Updating 73 tokens to inactive status...
✅ Set 73 tokens to inactive
============================================================
✅ Synchronization completed successfully!
📊 Results:
   ✅ Tokens set to active: 0
   ❌ Tokens set to inactive: 73
   ⚠️  Tokens not found in DB: 0
============================================================
🔒 Database connection closed
```

### Analysis Output (test_watchlist_sync.py)
```
======================================================================
WATCHLIST STATE ANALYSIS
======================================================================

📊 OVERALL STATISTICS
   Total tokens: 73
   ✅ Active: 0 (0.0%)
   ❌ Inactive: 73 (100.0%)
   📅 Total cycles: 301
   🕐 Last run: 2026-07-23T23:20:44.302970+00:00

📋 DEACTIVATION REASONS
   absent_3_cycles: 72
   liq_drop:54%>50%: 1

❌ SAMPLE INACTIVE TOKENS (Most recent 5)
   1. 3LAmxkAZGM...
      Peak Score: 52
      Reason: absent_3_cycles
      Deactivated: 2026-07-23T23:10:46

🔄 SYNC PREVIEW
   Addresses to set ACTIVE: 0
   Addresses to set INACTIVE: 73
   Total database updates: 73
======================================================================
✅ Analysis completed!
======================================================================
```

## Performance

### Optimization Features

1. **Bulk Updates**: Uses single SQL queries instead of row-by-row updates
2. **Efficient Query**: `WHERE network_address IN (...)` clause for fast matching
3. **Transaction Management**: Single transaction for all updates
4. **Minimal Memory**: Streams data without loading entire database into memory

### Expected Performance

- **Small datasets** (< 100 tokens): < 1 second
- **Medium datasets** (100-1,000 tokens): 1-3 seconds
- **Large datasets** (1,000-10,000 tokens): 3-10 seconds
- **Very large datasets** (> 10,000 tokens): 10-30 seconds

## Error Handling

The script handles several error scenarios:

1. **Missing JSON file**: Clear error message and exit
2. **Invalid JSON format**: Exception caught and logged
3. **Database connection failure**: Detailed error message
4. **SQL errors**: Transaction rollback and error reporting
5. **Missing token addresses**: Counted and reported as "not_found"

## Best Practices

### Before Running

1. **Test first**: Run `test_watchlist_sync.py` to preview changes
2. **Backup database**: Create a backup if dealing with critical data
3. **Check JSON file**: Ensure `watchlist_state.json` is up-to-date

### Regular Operations

1. **Schedule sync**: Run after each watchlist update cycle
2. **Monitor logs**: Check for "not_found" tokens that might need investigation
3. **Verify results**: Spot-check a few tokens in the database after sync

### Troubleshooting

**Issue**: "Token addresses not found in watchlist"
- **Cause**: Tokens in JSON file but not in database watchlist table
- **Solution**: These tokens were never added to watchlist, or were deleted

**Issue**: "Database locked" error
- **Cause**: Another process is writing to the database
- **Solution**: Wait and retry, or stop other database operations

**Issue**: "Failed to load watchlist data"
- **Cause**: JSON file missing or corrupted
- **Solution**: Check file path and JSON syntax

## Integration with Enhanced Watchlist Collector

This synchronization works seamlessly with the enhanced watchlist collector:

1. Collector updates `watchlist_state.json` with active/inactive status
2. Run sync script to update database
3. Other components query database for `is_active` field
4. Notifications only sent for active watchlist entries

### Automated Workflow

```python
# In your collector script or scheduler:

# 1. Run watchlist collector
await enhanced_watchlist_collector.collect()

# 2. Sync active status to database
from sync_watchlist_active_status import sync_watchlist_active_status
await sync_watchlist_active_status()

# 3. Continue with other operations using updated database
```

## Future Enhancements

Potential improvements for future versions:

1. **Incremental sync**: Only update changed tokens
2. **Bi-directional sync**: Update JSON from database changes
3. **Conflict resolution**: Handle concurrent updates
4. **Webhook support**: Trigger sync automatically on JSON file changes
5. **Historical tracking**: Log all status changes with timestamps

## Appendix

### Related Files

- `gecko_terminal_collector/database/sqlalchemy_manager.py` - Database manager with bulk update method
- `gecko_terminal_collector/database/models.py` - WatchlistEntry model definition
- `watchlist_state.json` - Source of truth for token active status
- `config.yaml` - Database configuration

### Database Schema

```sql
CREATE TABLE watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id VARCHAR(200) NOT NULL UNIQUE,
    token_symbol VARCHAR(50),
    token_name VARCHAR(200),
    network_address VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT DEFAULT '{}'
);
```

### Configuration Requirements

The script requires a valid `config.yaml` with database connection settings:

```yaml
database:
  url: "sqlite:///gecko_data.db"
  # or
  # url: "postgresql://user:pass@localhost/dbname"
```

## Support

For issues or questions:
1. Check the logs for detailed error messages
2. Run the test script to analyze your data
3. Verify your database connection and JSON file format
4. Review the existing watchlist entries in your database
