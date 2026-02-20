# Enhanced Watchlist Sync Guide

## Overview

The Enhanced Watchlist sync process maintains synchronization between the `watchlist_updated_micro.csv` file and the database `watchlist` table using a simple two-step approach.

**Performance Note:** The sync now uses lazy loading for address resolution, completing in ~5-10 seconds instead of 5+ minutes. See `DATABASE_RESOLVER_OPTIMIZATION.md` for details.

## How It Works

### Step 1: Reset All Entries
```bash
python -m examples.cli_with_scheduler reset-watchlist
```

This command sets `is_active = False` for all existing watchlist entries in the database. This effectively marks all entries as "stale" until they're refreshed from the CSV.

### Step 2: Sync from CSV
```bash
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"
```

This command:
- Reads `watchlist_updated_micro.csv`
- For each entry in the CSV:
  - If the pool already exists in the database → Updates it and sets `is_active = True`
  - If the pool is new → Inserts it with `is_active = True`

### Result
After both steps complete:
- Entries that exist in the CSV have `is_active = True` (current watchlist)
- Entries that were removed from the CSV have `is_active = False` (historical data preserved)

## Automated Sync

### Using the Batch Script (Windows)
```bash
sync_watchlist.bat
```

### Using the Shell Script (Linux/Mac)
```bash
chmod +x sync_watchlist.sh
./sync_watchlist.sh
```

### Scheduling with Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to "Daily" and repeat every 1 hour
4. Set action to "Start a program"
5. Program: `C:\path\to\your\project\sync_watchlist.bat`
6. Start in: `C:\path\to\your\project`

### Scheduling with Cron (Linux/Mac)

Add to crontab:
```bash
# Run every hour at minute 0
0 * * * * cd /path/to/your/project && ./sync_watchlist.sh >> logs/watchlist_sync.log 2>&1
```

## Manual Commands

### Reset only
```bash
python -m examples.cli_with_scheduler reset-watchlist
```

### Sync from specific sources
```bash
# Single source
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"

# Multiple sources
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro,lowcap,reference"
```

### Check watchlist status
```bash
# View all active entries
python -m examples.cli_with_scheduler status
```

## Database Schema

The `watchlist` table includes:
- `id` (primary key, auto-increment)
- `pool_id`
- `token_symbol`
- `token_name`
- `network_address`
- `is_active` (boolean) - Key field for sync process
- `created_at`
- `updated_at`
- `metadata_json`

## Benefits of This Approach

1. **Simple**: Two clear steps that are easy to understand and debug
2. **Safe**: Historical data is preserved (entries are marked inactive, not deleted)
3. **Atomic**: Each step is a complete operation
4. **Flexible**: Can be run manually or automated
5. **Auditable**: `updated_at` timestamp tracks when entries were last synced
6. **Efficient**: Uses upsert logic to minimize database operations

## Troubleshooting

### Check how many entries are active
```sql
SELECT COUNT(*) FROM watchlist WHERE is_active = TRUE;
```

### Check how many entries are inactive
```sql
SELECT COUNT(*) FROM watchlist WHERE is_active = FALSE;
```

### View recently updated entries
```sql
SELECT token_symbol, is_active, updated_at 
FROM watchlist 
ORDER BY updated_at DESC 
LIMIT 10;
```

### Manually reactivate an entry
```sql
UPDATE watchlist 
SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP 
WHERE pool_id = 'your_pool_id';
```

## Alternative Approaches Considered

### Option 1: Single Command with Flag (More Atomic)
```bash
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro" --reset-before-sync
```
- Pros: Single transaction, no race conditions
- Cons: More complex implementation, less flexible

### Option 2: Soft Delete with Timestamp (Most Flexible)
Track `last_synced_at` and automatically deactivate entries not seen in X days.
- Pros: Gradual deactivation, more forgiving
- Cons: More complex logic, harder to reason about

### Option 3: Full Delete and Recreate (Simplest)
Delete all entries and recreate from CSV.
- Pros: Simplest implementation
- Cons: Loses historical data, no audit trail

**We chose the two-step approach for its balance of simplicity, safety, and flexibility.**


## Performance Optimization

### Lazy Loading (Default)

The sync process now uses lazy loading for address resolution, which provides dramatic performance improvements:

- **Before:** 5+ minutes to load 1.8M address mappings
- **After:** <1 second initialization, ~5-10 seconds total for 100 entries

No configuration needed - lazy loading is enabled by default.

### Database Indexes (Recommended)

For optimal performance, add database indexes:

```bash
# Apply indexes automatically
python add_address_indexes.py

# Or manually
psql -U your_user -d your_database -f add_address_indexes.sql
```

These indexes enable fast case-insensitive address lookups, which are critical for lazy loading performance.

### Performance Monitoring

Check resolution performance:

```python
from gecko_terminal_collector.utils.database_address_resolver import EnhancedWatchlistDatabaseParser

parser = EnhancedWatchlistDatabaseParser(db_manager)
await parser.initialize()

# Get statistics
stats = await parser.get_resolution_statistics()
print(f"Mode: {stats.get('mode', 'cached')}")
print(f"Cache size: {stats['total_mappings']} addresses")
print(f"Memory: {stats['cache_size_mb']:.2f} MB")
```

See `DATABASE_RESOLVER_OPTIMIZATION.md` for detailed performance information and tuning options.
