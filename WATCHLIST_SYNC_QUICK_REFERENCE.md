# Watchlist Active Status Sync - Quick Reference

## 🚀 Quick Commands

### CLI Command (Recommended for Production)
```bash
# Basic usage (matches your workflow)
python -m examples.cli_with_scheduler sync-watchlist-status

# Dry run (preview only)
python -m examples.cli_with_scheduler sync-watchlist-status --dry-run

# Diagnose missing tokens
python -m examples.cli_with_scheduler diagnose-watchlist

# Custom paths
python -m examples.cli_with_scheduler sync-watchlist-status \
    --config config.yaml \
    --json-path watchlist_state.json
```

### Shell Script (Linux)
```bash
# Make executable (first time)
chmod +x sync_watchlist_status.sh

# Run sync
./sync_watchlist_status.sh

# Dry run
./sync_watchlist_status.sh --dry-run
```

### Standalone Scripts (Alternative)
```cmd
# Test/preview changes
python test_watchlist_sync.py

# Run sync (Windows)
sync_watchlist_status.bat

# Run sync (Python)
python sync_watchlist_active_status.py
```

## 📋 What It Does

✅ Reads `watchlist_state.json`  
✅ Extracts active/inactive token addresses  
✅ Bulk updates database `watchlist.is_active` field  
✅ Reports statistics (active, inactive, not found)  

## 🎯 When to Use

- After enhanced watchlist collector runs
- When `watchlist_state.json` changes
- To sync database with JSON state
- Before sending notifications (ensure accurate active status)

## 📊 Example Results

```
=== Watchlist State Analysis ===
Total tokens: 66
✅ Active: 0
❌ Inactive: 66

=== Synchronization Results ===
✅ Tokens set to active: 0
❌ Tokens set to inactive: 66
⚠️  Tokens not found in DB: 0

✅ Synchronization completed successfully!
```

## ⚡ Performance

- **Small** (< 100 tokens): < 1 second
- **Medium** (100-1K tokens): 1-3 seconds  
- **Large** (1K-10K tokens): 3-10 seconds

## 🔍 Command Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config` / `-c` | Configuration file path | `config.yaml` |
| `--json-path` / `-j` | Watchlist state JSON path | `watchlist_state.json` |
| `--dry-run` | Preview without updating | disabled |

## 🔗 Integration with Workflow

Your current workflow:
```bash
python -m examples.cli_with_scheduler reset-watchlist
```

New sync command:
```bash
python -m examples.cli_with_scheduler sync-watchlist-status
```

Complete workflow:
```bash
# 1. Collect watchlist
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"

# 2. Sync active status
python -m examples.cli_with_scheduler sync-watchlist-status

# 3. Monitor or notify
python -m examples.cli_with_scheduler run-once --collector watchlist_monitor
```

## 🔍 Files Involved

| File | Purpose |
|------|---------|
| `watchlist_state.json` | Source of truth for active status |
| `examples/cli_with_scheduler.py` | CLI command implementation |
| `sync_watchlist_status.sh` | Linux shell script wrapper |
| `config.yaml` | Database configuration |

## ⚠️ Important Notes

1. Always test with `--dry-run` first
2. Tokens "not found" means they're in JSON but not in database watchlist
3. Sync is idempotent - safe to run multiple times
4. Uses bulk update for efficiency
5. Automatically creates backup transaction

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| "File not found" | Check `watchlist_state.json` path |
| "Database locked" | Wait or stop other DB operations |
| "Tokens not found" | Normal - tokens in JSON but not in DB watchlist |
| Import errors | Install requirements: `pip install -r requirements.txt` |
| Permission denied | `chmod +x sync_watchlist_status.sh` |

## 📖 Full Documentation

- **CLI Guide**: `WATCHLIST_SYNC_CLI_GUIDE.md` ← **Start here for CLI usage**
- **Status Guide**: `WATCHLIST_SYNC_STATUS_GUIDE.md`
- **Implementation**: `WATCHLIST_SYNC_IMPLEMENTATION.md`
- **Examples**: `example_integration_sync.py`
