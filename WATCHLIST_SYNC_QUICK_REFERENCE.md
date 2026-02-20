# Watchlist Sync - Quick Reference

## One-Time Setup

```bash
# 1. Add database indexes for performance
python add_address_indexes.py

# 2. Test manual sync
sync_watchlist.bat  # Windows
./sync_watchlist.sh # Linux/Mac
```

## Manual Sync Commands

```bash
# Full sync (both steps)
sync_watchlist.bat

# Or run steps individually:
python -m examples.cli_with_scheduler reset-watchlist
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"
```

## Scheduling

### Windows Task Scheduler
- Program: `C:\path\to\your\project\sync_watchlist.bat`
- Start in: `C:\path\to\your\project`
- Trigger: Daily, repeat every 1 hour

### Linux/Mac Cron
```bash
0 * * * * cd /path/to/project && ./sync_watchlist.sh >> logs/watchlist_sync.log 2>&1
```

## Monitoring

```bash
# Check active entries
psql -c "SELECT COUNT(*) FROM watchlist WHERE is_active = TRUE;"

# Check recent updates
psql -c "SELECT token_symbol, is_active, updated_at FROM watchlist ORDER BY updated_at DESC LIMIT 10;"

# View sync logs
tail -f logs/watchlist_sync.log
```

## Troubleshooting

```bash
# If sync is slow, add indexes
python add_address_indexes.py

# Check if indexes exist
psql -c "SELECT indexname FROM pg_indexes WHERE tablename = 'pools' AND indexname LIKE 'idx_%';"

# Test individual commands
python -m examples.cli_with_scheduler reset-watchlist
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"
```

## Performance

- **Initialization:** <1 second (lazy loading)
- **Sync 100 entries:** 5-10 seconds
- **Memory usage:** ~5MB

## Files

- `sync_watchlist.bat` - Windows sync script
- `sync_watchlist.sh` - Unix sync script  
- `WATCHLIST_SYNC_GUIDE.md` - Full documentation
- `DATABASE_RESOLVER_OPTIMIZATION.md` - Performance details
